"""g101 -- the two things Austin delegated on 2026-09-02, measured on one book.

He answered two questions and handed both derivations back to us:

  1. "Price target 1 is high of day or low of day. Price target 2, 3, 4, and 5
     I believe you need to decide on yourself based on all the numbers you
     have."  -> the LADDER SHAPE is ours to prove, from the book, not asserted.
  2. "How the open behaved" -- what tells him at 9:45 whether the day trends.
     -> a CAUSAL day filter off the first 15-30 minutes of the symbol's own
     tape. No other symbol, no lookahead.

This script measures both on the SAME 444 rows every other g9x script uses:
`research/bt2y_trades_retest_on.json`, first-of-day (g86.candidates), size-gated
on `signal_runner.min_risk_floor`. It APPLIES NOTHING. No engine file is
touched; the ladder here is the research replica introduced by
research/g99_ladder_ab.py (see that file's BLOCKER 1) extended to five rungs.

Fills route through the shared primitives only: `backtest_week._target_hit` /
`_stop_hit`, `stop_rule.stop_fill_price` / `disaster_stop_*`. Nothing is
re-implemented. A bar that touches a rung and closes past the stop goes to the
STOP (house rule).

    python research/g101_open_and_ladder.py

Denominator note: every arm divides by the SAME 444, including the day-filter
arms. Sitting a day out earns $0 that day; it does not shrink the denominator.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter, defaultdict, namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g97_mfe as g97                             # noqa: E402
import signal_runner as sr                        # noqa: E402
import stop_rule as SR                            # noqa: E402
import backtest_week as bw                        # noqa: E402
from research import g80_ordertype_grid as G      # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
BASELINE = os.path.join(HERE, "g97_mfe.json")
OUT_JSON = os.path.join(HERE, "g101_open_and_ladder.json")
WIN_END = "11:00:00"
RISK = g86.RISK

OR_BARS = 15          # 09:30-09:44 inclusive -- "the first 15 minutes"
EVAL_MAX = 30         # never read past 09:59 -- "15 to 30 minutes"
MIN_GAP_R = 0.20
PSYCH_STEP = 1.00
PSYCH_TOL_R = 0.25

Rung = namedtuple("Rung", "price weight name")


# ---------------------------------------------------------------- open read
def open_state(bars, entry_i):
    """How the open behaved, judged ONLY on bars[0:T+1], T <= entry_i.

    Opening range = high/low of the first OR_BARS one-minute bars. Then read
    the closes from OR_BARS up to T = min(entry_i, EVAL_MAX-1):

      trend_up / trend_dn  the tape broke the range and HELD it: the majority
                           of read closes are outside on one side, the last one
                           is outside, and it crossed the boundary at most once.
      chop                 it came back through: two or more boundary crossings.
      inside               it never closed outside the range at all.
      no_read              the entry landed inside the opening range window, so
                           there is nothing yet to read (this is a fact about
                           the ENGINE's entry timing, not about the day).

    Returns (state, read_len, orh, orl).
    """
    if entry_i is None or entry_i < OR_BARS or len(bars) <= OR_BARS:
        return "no_read", 0, None, None
    orh = max(c.high for c in bars[:OR_BARS])
    orl = min(c.low for c in bars[:OR_BARS])
    T = min(entry_i, EVAL_MAX - 1)
    seg = bars[OR_BARS:T + 1]
    if not seg:
        return "no_read", 0, orh, orl
    sides = [1 if c.close > orh else (-1 if c.close < orl else 0) for c in seg]
    out_up = sides.count(1)
    out_dn = sides.count(-1)
    flips = sum(1 for a, b in zip(sides, sides[1:]) if a != b)
    n = len(sides)
    last = sides[-1]
    if out_up == 0 and out_dn == 0:
        return "inside", n, orh, orl
    if flips >= 2:
        return "chop", n, orh, orl
    if last == 1 and out_up / n >= 0.5:
        return "trend_up", n, orh, orl
    if last == -1 and out_dn / n >= 0.5:
        return "trend_dn", n, orh, orl
    return "chop", n, orh, orl


def aligned_with_open(state, long):
    return (state == "trend_up" and long) or (state == "trend_dn" and not long)


# ------------------------------------------------------------------- rungs
def _substitute(px, entry, risk, long, named, tol_r=PSYCH_TOL_R,
                step=PSYCH_STEP):
    """Snap a synthetic R-price to a nearby whole dollar or named level.

    Named level beats whole dollar on a tie; still tied, nearer entry wins.
    Exactly the precedence g99_ladder_ab.build_rungs uses for its 2R rung."""
    tol = tol_r * risk
    subs = []
    k0 = round(px / step)
    for dk in (-1, 0, 1):
        wd = (k0 + dk) * step
        if abs(wd - px) <= tol:
            subs.append(("whole$", wd, abs(wd - px)))
    for nm, v in named.items():
        if v is not None and abs(v - px) <= tol:
            subs.append((nm, v, abs(v - px)))
    if not subs:
        return px
    best = min(s[2] for s in subs)
    tied = [s for s in subs if abs(s[2] - best) < 1e-9]
    tied.sort(key=lambda s: (0 if s[0] != "whole$" else 1, abs(s[1] - entry)))
    return tied[0][1]


def build_rungs(entry, stop, long, extreme, named, weights, plan):
    """Build the priced rungs for `plan`, causal inputs only.

    plan "4"  PT1 extreme / PT2 next named beyond it / PT3 2R / PT4 max(4R, next
              named beyond 2R)              -- the g99 shape, reproduced
    plan "5"  the same plus PT5 = 6.0R      -- a fifth PRICED rung
    plan "4t" the "4" rungs; the caller runs the remainder as a trailing tranche

    Returns list[Rung] sorted by R, monotonic at MIN_GAP_R, weights renormalised
    to sum to 1.0 over the rungs that survived.
    """
    risk = abs(entry - stop)
    sign = 1.0 if long else -1.0

    def R(px):
        return sign * (px - entry) / risk

    def beyond(pivot):
        return {k: v for k, v in named.items()
                if v is not None and ((v > pivot) if long else (v < pivot))}

    cands = []
    if R(extreme) >= MIN_GAP_R:
        cands.append(("PT1 hod/lod", extreme))
    b1 = beyond(extreme)
    if b1:
        nm = min(b1, key=lambda k: R(b1[k]))
        cands.append(("PT2 %s" % nm, b1[nm]))
    px2 = _substitute(entry + sign * 2.0 * risk, entry, risk, long, named)
    cands.append(("PT3 2R", px2))
    rm4 = entry + sign * 4.0 * risk
    b3 = beyond(px2)
    px4 = rm4
    if b3:
        nm = min(b3, key=lambda k: R(b3[k]))
        if R(b3[nm]) > R(rm4):
            px4 = b3[nm]
    cands.append(("PT4 runner", px4))
    if plan == "5":
        cands.append(("PT5 6R", entry + sign * 6.0 * risk))

    items = [(nm, px) for nm, px in cands if R(px) > 0]
    items.sort(key=lambda x: R(x[1]))
    kept = []
    for nm, px in items:
        if not kept or R(px) - R(kept[-1][1]) >= MIN_GAP_R:
            kept.append((nm, px))
    w = list(weights[:len(kept)])
    s = sum(w)
    w = [x / s for x in w]
    return [Rung(px, wt, nm) for (nm, px), wt in zip(kept, w)]


def walk_ladder(row, bars, rungs, trail="be", runner_w=0.0):
    """Bar-ordered fill of one trade against its ladder.

    trail "be"       stop -> entry after the first rung fills (g99 behaviour)
    trail "ratchet"  stop -> the previously filled rung's price (a real trail)

    runner_w > 0 holds that fraction back from the priced rungs entirely and
    rides it on the trailing stop to the 11:00 mark -- the "let the runner run"
    tranche, which has no price and therefore no cap.
    """
    entry, stop = row["entry"], row["stop"]
    risk = abs(entry - stop)
    long = row["dir"] == "call"
    i = row["entry_i"]

    remaining = 1.0
    fills = []
    filled = set()
    stop_lv = stop
    last_px = None
    last_close = entry
    scale = 1.0 - runner_w

    seg = [c for c in bars[i + 1:] if c.timestamp <= WIN_END]
    for c in seg:
        last_close = c.close
        if stop_lv == stop:
            dz = SR.disaster_stop_price(entry, risk, long, SR.DISASTER_STOP_R)
            if SR.disaster_stop_hit(c.high, c.low, dz, long):
                fills.append((remaining, dz))
                remaining = 0.0
                break
        touched = [k for k, r in enumerate(rungs)
                   if k not in filled and bw._target_hit(c, r.price, long)]
        if bw._stop_hit(c, stop_lv, long):
            px = SR.stop_fill_price(c.close, entry, risk, long)
            if touched:
                px = min(px, stop_lv) if long else max(px, stop_lv)
            # NOTE: a breakeven/trailed stop still fills at the CLOSE-derived
            # price from stop_rule, not at the trail level. Filling at the level
            # is the optimistic fill this repo has already been burned by
            # (CLAUDE.md, "why every dollar figure before 2026-08-30 was wrong");
            # it inflated the 30/30/30/10 control from $92/day to $143/day when
            # tried here on 2026-09-02.
            fills.append((remaining, px))
            remaining = 0.0
            break
        if touched:
            for k in sorted(touched, key=lambda j: rungs[j].price if long
                            else -rungs[j].price):
                r = rungs[k]
                filled.add(k)
                fills.append((r.weight * scale, r.price))
                remaining -= r.weight * scale
                if trail == "ratchet" and last_px is not None:
                    stop_lv = last_px
                elif stop_lv == stop:
                    stop_lv = entry
                last_px = r.price
            if trail == "be" and stop_lv == stop:
                stop_lv = entry
            if len(filled) == len(rungs) and remaining <= 1e-9:
                remaining = 0.0
                break
    if remaining > 1e-9:
        fills.append((remaining, last_close))
    return fills


def r_of(fills, entry, stop, long):
    risk = abs(entry - stop)
    sign = 1.0 if long else -1.0
    return sum(w * sign * (px - entry) / risk for w, px in fills)


# -------------------------------------------------------------------- main
PLANS = {
    # label:                (plan, weights, trail, runner_w)
    "4-rung 30/30/30/10 (g99 control)": ("4", (.30, .30, .30, .10), "be", 0.0),
    "4-rung + ratchet trail":           ("4", (.30, .30, .30, .10), "ratchet", 0.0),
    "5-rung 30/25/20/15/10":            ("5", (.30, .25, .20, .15, .10), "be", 0.0),
    "5-rung 20/20/20/20/20":            ("5", (.20, .20, .20, .20, .20), "be", 0.0),
    "5-rung 40/20/20/10/10":            ("5", (.40, .20, .20, .10, .10), "be", 0.0),
    "5-rung 30/25/20/15/10 ratchet":    ("5", (.30, .25, .20, .15, .10), "ratchet", 0.0),
    "4 priced + 10% free runner":       ("4", (.30, .30, .30, .10), "ratchet", 0.10),
    "4 priced + 20% free runner":       ("4", (.30, .30, .30, .10), "ratchet", 0.20),
    "4 priced + 20% runner, BE trail":  ("4", (.30, .30, .30, .10), "be", 0.20),
    "4 priced + 30% free runner":       ("4", (.30, .30, .30, .10), "ratchet", 0.30),
    "4 priced + 40% free runner":       ("4", (.30, .30, .30, .10), "ratchet", 0.40),
    "4 priced + 60% free runner":       ("4", (.30, .30, .30, .10), "ratchet", 0.60),
}


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    rows_all = b["trades"] if isinstance(b, dict) else b
    byday = g86.candidates(rows_all)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]
    print("first-of-day rows (pre-gate): %d" % len(firsts))

    base = json.load(open(BASELINE, encoding="utf-8"))
    arms = defaultdict(list)
    recs = []
    gated = nobars = 0

    for k, r in enumerate(firsts, 1):
        entry, stop = r["entry"], r["stop"]
        risk = abs(entry - stop)
        if risk < sr.min_risk_floor(entry):
            gated += 1
            continue
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r.get("entry_i")
        if not bars or i is None or i >= len(bars):
            nobars += 1
            continue
        long = r["dir"] == "call"
        w = g97.walk(r, bars)
        if w is None:
            gated += 1
            continue
        mfe, stopped, outcomes = w
        state, read_len, orh, orl = open_state(bars, i)
        named = ({"PDH": pdh, "PMH": pmh, "ORH": orh} if long
                 else {"PDL": pdl, "PML": pml, "ORL": orl})
        extreme = (max(c.high for c in bars[:i + 1]) if long
                   else min(c.low for c in bars[:i + 1]))
        base_row = dict(day=r["day"], et=r["et"], sym=r["sym"])

        rec = {"sym": r["sym"], "day": r["day"], "dir": r["dir"],
               "entry_i": i, "state": state, "read_len": read_len,
               "aligned_open": aligned_with_open(state, long),
               "mfe": round(mfe, 3), "runner": mfe >= 3.0,
               "reach2r": mfe >= 2.0, "book_pnl": r["pnl"],
               "rangeb": r.get("rangeb"), "dow": r.get("dow")}

        arms["book today"].append(dict(base_row, pnl=r["pnl"]))
        arms["flat 2.5R"].append(dict(base_row, pnl=outcomes[2.5] * RISK))
        for label, (plan, weights, trail, rw) in PLANS.items():
            rungs = build_rungs(entry, stop, long, extreme, named, weights, plan)
            fills = walk_ladder(r, bars, rungs, trail=trail, runner_w=rw)
            tot = sum(x for x, _ in fills)
            assert abs(tot - 1.0) < 1e-6, "%s weights %.6f" % (label, tot)
            rr = r_of(fills, entry, stop, long)
            assert rr >= -1.2501, "floor breached %.4fR %s %s" % (rr, r["sym"], r["day"])
            arms[label].append(dict(base_row, pnl=rr * RISK))
            rec["r_" + label] = round(rr, 4)
        recs.append(rec)
        if k % 150 == 0:
            print("  ... %d/%d" % (k, len(firsts)))

    n = len(recs)
    print("\nmeasured %d  (%d below min_risk_floor, %d no bars)" % (n, gated, nobars))
    if n != base["n"] or gated != base["gated"]:
        raise SystemExit("BASELINE DRIFT vs g97_mfe.json: n=%d/%d gated=%d/%d"
                         % (n, base["n"], gated, base["gated"]))
    print("baseline check OK -- same 444 rows as g97/g99\n")

    # ---------------------------------------------------------- open read
    print("=== 1. HOW THE OPEN BEHAVED (causal, first 15-30 min, own tape) ===")
    by_state = defaultdict(list)
    for rec in recs:
        by_state[rec["state"]].append(rec)
    print("| open state | n | %% of book | runner (MFE>=3R) | reach 2R | book $/trade |")
    print("|---|---:|---:|---:|---:|---:|")
    state_tbl = {}
    for st in ("trend_up", "trend_dn", "chop", "inside", "no_read"):
        v = by_state.get(st, [])
        if not v:
            continue
        run = sum(1 for x in v if x["runner"])
        r2 = sum(1 for x in v if x["reach2r"])
        pt = statistics.fmean(x["book_pnl"] for x in v)
        state_tbl[st] = {"n": len(v), "pct": round(len(v) / n * 100, 1),
                         "runner_pct": round(run / len(v) * 100, 1),
                         "reach2r_pct": round(r2 / len(v) * 100, 1),
                         "book_per_trade": round(pt)}
        print("| %-9s | %3d | %5.1f%% | %5.1f%% | %5.1f%% | $%d |"
              % (st, len(v), len(v) / n * 100, run / len(v) * 100,
                 r2 / len(v) * 100, round(pt)))

    al = [x for x in recs if x["aligned_open"]]
    ag = [x for x in recs if x["state"] in ("trend_up", "trend_dn")
          and not x["aligned_open"]]
    for label, v in (("trend + trade ALIGNED", al), ("trend + trade AGAINST", ag)):
        if v:
            run = sum(1 for x in v if x["runner"])
            print("  %-24s n=%3d  runner %.1f%%  reach2R %.1f%%  book $%d/trade"
                  % (label, len(v), run / len(v) * 100,
                     sum(1 for x in v if x["reach2r"]) / len(v) * 100,
                     round(statistics.fmean(x["book_pnl"] for x in v))))
    rl = [x["read_len"] for x in recs if x["state"] != "no_read"]
    print("  entries with NO read available (entry inside the first 15 min): %d/%d = %.1f%%"
          % (len(by_state.get("no_read", [])), n,
             len(by_state.get("no_read", [])) / n * 100))
    if rl:
        print("  median read length where a read exists: %.0f bars" % statistics.median(rl))

    # ------------------------------------------------------------- ladder
    print("\n=== 2. THE LADDER, PRICED (same 444 rows, $/day over all 444) ===")
    print("| arm | $/day | win | months green | max DD | mean R |")
    print("|---|---:|---:|---:|---:|---:|")
    out_arms = {}
    order = ["book today", "flat 2.5R"] + list(PLANS)
    for label in order:
        st = g86.stats(arms[label], n)
        out_arms[label] = st
        print("| %-33s | $%-5d | %5.1f%% | %5s | $%-7d | %+.4f |"
              % (label, st["per_day"], st["win_pct"],
                 "%d/%d" % (st["months_green"], st["months"]),
                 st["worst_drawdown"], st["mean_r"]))

    # -------------------------------- 3. the two combined: filter x ladder
    print("\n=== 3. THE OPEN FILTER APPLIED (denominator stays %d) ===" % n)
    print("| arm | filter | trades kept | $/day | win | months green | max DD |")
    print("|---|---|---:|---:|---:|---:|---:|")
    keep_sets = {
        "no filter": lambda x: True,
        "drop chop": lambda x: x["state"] != "chop",
        "trend only": lambda x: x["state"] in ("trend_up", "trend_dn"),
        "trend + aligned": lambda x: x["aligned_open"],
    }
    combo = {}
    for label in ("book today", "4-rung 30/30/30/10 (g99 control)",
                  "5-rung 30/25/20/15/10", "4 priced + 20% free runner"):
        for fl, fn in keep_sets.items():
            keep = {(x["day"], x["sym"]) for x in recs if fn(x)}
            rows = [a for a, rec in zip(arms[label], recs)
                    if (rec["day"], rec["sym"]) in keep]
            st = g86.stats(rows, n) if rows else {"trades": 0}
            combo["%s | %s" % (label, fl)] = st
            if st.get("trades"):
                print("| %-33s | %-15s | %3d | $%-5d | %5.1f%% | %5s | $%-7d |"
                      % (label, fl, st["trades"], st["per_day"], st["win_pct"],
                         "%d/%d" % (st["months_green"], st["months"]),
                         st["worst_drawdown"]))

    json.dump({"n": n, "gated": gated, "no_bars": nobars,
               "open_states": state_tbl, "arms": out_arms, "combo": combo,
               "rows": recs},
              open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("\n  -> %s" % OUT_JSON)


if __name__ == "__main__":
    main()
