"""G80 - the order-type grid. What each of five ways of GETTING IN is worth.

Austin, 2026-08-29: "now we're in the backtest and we're gonna start using
market orders limit orders trading with options part of our back test."

THE ONE THING THAT VARIES IS THE ENTRY ORDER. Nothing else moves:

  * the trade list is the shipped book (research/bt2y_trades.json, traded rows);
  * the stop LEVEL is the book's own stop, untouched;
  * every stop fill routes through stop_rule.stop_fill_price via
    backtest_week._stop_fill_px - no fill is re-implemented here;
  * the exit machinery is backtest_week._ladder_bar, the shipped SCALE_PLAN
    ladder, called directly, bar by bar, exactly as simulate_day calls it;
  * the -1R disaster stop, the break-even move, the 2R target and the EOD
    scratch are all the shipped ones because they are the shipped functions.

THE FIVE POLICIES (plus BOOK, the control)

  BOOK  the shipped fill. entry = the level clamped into the signal minute's
        own range, taken intrabar on the signal minute. Used to PROVE this
        harness reproduces the published book before any of the other five are
        believed.
  A     RESTING LIMIT at the level, placed the moment the setup arms, cancelled
        at 11:00. Fills only if the level trades after the order could have been
        placed. Never touched = NO TRADE, counted, not quietly dropped. The stop
        reacts to the fill the way the shipped engine makes it react - to the
        low/high of the bar the order filled on.
  A2    THE SAME FILL, structural stop held where the setup put it. For a
        default break-and-retest that stop IS the level, i.e. the same price as
        the order, so those rows have no trade to size and are counted as
        untakeable rather than quietly given a stop nobody chose.
  B     MARKET at the signal minute's close.
  C     MARKET at the next minute's open.
  D     LIMIT at the level live for one bar, then MARKET at the next open if it
        did not fill (chase once). Always ends in a fill.
  E     LIMIT at the level live for three bars, no chase. Unfilled = NO TRADE.

WHERE THE ORDER CAN FIRST REST (policy A)

  break-and-retest : the shipped ordered state machine (omen_bot.detect_break_
        retest) replayed bar by bar - the order can rest from the bar AFTER the
        one on which price BROKE the level and then LEFT it. That replay is
        research/g80_lookahead_refute.br_trace, imported rather than copied so
        there is one transcription of the FSM and the two reports agree.
  everything else (order block, 84% re-entry) : the latest bar before the signal
        whose own high or low IS the level. That is the tightest honest bound
        the trade record supports; rows where no such bar exists are reported as
        untraced, not guessed at.

THE STOP, AND WHY POLICY A NEEDS THE SHIPPED intrabar_stop

  For the default break-and-retest the stop IS the retested level
  (signal_runner.BNR_STOP_MODE == "level"): `stop = level_hi`. So a limit order
  resting AT the level is an order to buy at your own stop loss - zero risk
  distance, nothing to size. The shipped engine already answers this, and the
  answer is Austin's, written five times in the recovered reviews: "stop loss at
  the bottom of the wick you entered on". signal_runner.intrabar_stop moves the
  stop to the entry bar's own extreme exactly when the fill lands on the stop.
  That shipped function is called here for every policy. It is a no-op for the
  market policies (their entry is past the level, so nothing collapsed).

  Both readings are reported: the grid uses the shipped intrabar_stop, and the
  count of trades that would be untakeable WITHOUT it is printed as a diagnostic.

ONE TRADE A DAY, AND THE HONEST COST OF A LIMIT

  A no-fill is not a free option. The one-a-day arm walks the day's candidates
  in signal order and takes the FIRST ONE THAT ACTUALLY FILLS. If the first
  setup's limit is never touched the day moves to the second, and so on. A day
  where nothing filled books $0 and is counted as a MISSED DAY.

Conventions (CLAUDE.md): 1R = $1,000; R is the engineering unit, dollars are the
headline. Management starts on the bar after the one the position was opened on,
the same convention the shipped book uses. Reads only - no engine file is
edited, no mark file is opened, nothing is committed, no request URL is printed.

Usage:  python research/g80_ordertype_grid.py
Writes: research/g80_ordertype_grid.json
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf                      # noqa: E402
import backtest_week as bw                     # noqa: E402
import signal_runner as sr                     # noqa: E402
from backtest_week import SimTrade, _ladder_bar   # noqa: E402
from research import g80_lookahead_refute as rf   # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT = ROOT / "research" / "g80_ordertype_grid.json"
RISK = 1000.0
EPS = 0.005                 # the book carries levels to the cent
CUTOFF = "11:00:00"         # entry orders are cancelled here (SESSION_END)
SEED = 20260830
BOOTS = 10000

POLICIES = ["BOOK", "A", "A2", "B", "C", "D", "E"]
POLICY_NAME = {
    "BOOK": "BOOK  shipped fill (control)",
    "A": "A  resting limit @ level, stop = entry bar's low",
    "A2": "A2 resting limit @ level, structural stop held",
    "B": "B  market at the signal minute's close",
    "C": "C  market at the next minute's open",
    "D": "D  limit 1 bar, then market (chase once)",
    "E": "E  limit at the level, 3-bar expiry",
}


# --------------------------------------------------------------- bar access

_day_cache: dict = {}
_days_by_sym: dict = {}


def archive_days(sym):
    if sym not in _days_by_sym:
        d = ROOT / "data_archive" / sym
        _days_by_sym[sym] = sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []
    return _days_by_sym[sym]


def day_pack(sym, day):
    """(rth bars, pdh, pdl, pmh, pml) for one symbol-day, cache-first.

    pdh/pdl come from the previous archived session with >=30 RTH bars and
    pmh/pml from that day's own pre-09:30 bars - the same derivation
    backtest_2y.py makes before it calls simulate_day. Data preparation only;
    no fill and no grade is computed here.
    """
    k = (sym, day)
    if k in _day_cache:
        return _day_cache[k]
    if len(_day_cache) > 400:
        _day_cache.clear()
    try:
        raw = pf.fetch_day(sym, day)
        bars = pf.rth(raw)
    except Exception:
        bars, raw = [], []
    pmh, pml = pf.premarket_hi_lo(raw) if raw else (None, None)
    pdh = pdl = None
    ds = archive_days(sym)
    if day in ds:
        for prev in reversed(ds[:ds.index(day)]):
            try:
                p = pf.rth(pf.fetch_day(sym, prev))
            except Exception:
                continue
            if len(p) >= 30:
                pdh, pdl = max(c.high for c in p), min(c.low for c in p)
                break
    _day_cache[k] = (bars, pdh, pdl, pmh, pml)
    return _day_cache[k]


def cutoff_idx(bars):
    """First bar index at or after 11:00 - the bar an entry order is dead on."""
    for j, c in enumerate(bars):
        if c.timestamp >= CUTOFF:
            return j
    return len(bars)


# ------------------------------------------------------- where an order rests

def arm_index(row, bars):
    """(last bar before the order could rest, how it was established).

    A return of (None, "untraced") means the trade record does not support any
    honest arming bar; those rows are reported, never assumed.
    """
    i, lvl, long = row["entry_i"], row["level_px"], row["dir"] == "call"
    if row["setup"] == "break_and_retest":
        tr = rf.br_trace(bars[:i + 1], lvl, long)
        if tr and tr["leave_i"] is not None:
            return tr["leave_i"], "br_state_machine"
    best = None
    for j in range(min(i, len(bars))):
        c = bars[j]
        if abs(c.high - lvl) <= EPS or abs(c.low - lvl) <= EPS:
            best = j
    if best is not None:
        return best, "level_printed_by_bar"
    return None, "untraced"


def limit_touch(bars, lvl, long, j0, j1):
    """First bar in [j0, j1) that trades through a resting limit at ``lvl``.

    Returns (bar index, fill price) or (None, None). A resting order fills at
    its own price unless the bar OPENED through it, in which case the fill is
    that open - the same convention backtest_week._stop_fill_px uses for its
    touch arm.
    """
    for j in range(max(j0, 0), min(j1, len(bars))):
        c = bars[j]
        if long and c.low <= lvl + EPS:
            return j, min(lvl, c.open)
        if (not long) and c.high >= lvl - EPS:
            return j, max(lvl, c.open)
    return None, None


def resolve_entry(policy, row, bars, arm):
    """(fill_i, entry price, tag) or (None, None, reason-for-no-fill).

    ``fill_i`` is the last bar the position is NOT managed on: management runs
    bars fill_i+1 .. end of session, the convention the shipped book uses for
    its own intrabar entries. An order that fills at the OPEN of bar k is live
    for all of bar k, so it reports fill_i = k-1.
    """
    i, lvl, long = row["entry_i"], row["level_px"], row["dir"] == "call"
    cut = cutoff_idx(bars)
    n = len(bars)

    if policy == "BOOK":
        return (i, row["entry"], "shipped") if i < n else (None, None, "no_bars")

    if policy == "B":
        if i >= n - 1:
            return None, None, "signal_bar_is_last"
        return i, bars[i].close, "market_close"

    if policy == "C":
        if i + 1 >= n:
            return None, None, "no_next_bar"
        return i, bars[i + 1].open, "market_next_open"

    if policy in ("A", "A2"):
        if arm is None:
            return None, None, "arming_bar_untraced"
        j, px = limit_touch(bars, lvl, long, arm + 1, cut)
        if j is None:
            return None, None, "limit_never_touched"
        if j >= n - 1:
            return None, None, "filled_on_last_bar"
        return j, px, "limit_filled_early" if j < i else (
            "limit_filled_on_signal_bar" if j == i else "limit_filled_late")

    if policy == "D":
        j, px = limit_touch(bars, lvl, long, i + 1, min(i + 2, cut))
        if j is not None:
            if j >= n - 1:
                return None, None, "filled_on_last_bar"
            return j, px, "limit_filled"
        if i + 2 >= n:
            return None, None, "no_bar_to_chase_into"
        return i + 1, bars[i + 2].open, "chased_market"

    if policy == "E":
        j, px = limit_touch(bars, lvl, long, i + 1, min(i + 4, cut))
        if j is None:
            return None, None, "limit_never_touched"
        if j >= n - 1:
            return None, None, "filled_on_last_bar"
        return j, px, "limit_filled"

    raise ValueError(policy)


# ------------------------------------------------------------ the shipped run

class _Stub:
    """What backtest_week._arm_84 reads off the runner. Arming a 84% re-entry
    has nowhere to go here (this rig re-prices a fixed trade list, it does not
    re-detect), so the writes land on a throwaway. Nothing else touches it."""
    def __init__(self, bars, bias):
        self.candles, self.htf_bias = bars, bias
        self.session = type("S", (), {"entry_price": 0.0, "entry_direction": "",
                                      "entry_target": 0.0, "entry_stop": 0.0})()


def run_trade(row, bars, fill_i, entry_px, pdh, pdl, pmh, pml,
              move_stop_to_entry_bar=True):
    """Price one trade from ``entry_px``, opened on bar ``fill_i``.

    Every exit decision below is made by backtest_week._ladder_bar - the shipped
    ladder. The only thing this function owns is the entry price and the two
    shipped derivations that read it (the 2R target and the F1 ladder's scale
    point / runner target), plus signal_runner.intrabar_stop, which is the
    shipped answer to "the fill landed on the stop".

    Returns a dict, or None when the trade is not takeable at that price.
    """
    long = row["dir"] == "call"
    stop = row["stop"]
    # shipped: the fill lands on the stop -> the stop goes to the entry bar's
    # own extreme (signal_runner.intrabar_stop, Austin's stated rule).
    # A2 is the one policy that does NOT let the stop react to the fill: it is
    # the "keep the structural stop where the setup put it" reading, which for a
    # default break-and-retest means the stop is the level -- the same price as
    # the order -- so those rows simply have no trade and are counted as such.
    if move_stop_to_entry_bar:
        stop = sr.intrabar_stop(entry_px, stop, bars[fill_i], long)
    risk = (entry_px - stop) if long else (stop - entry_px)
    if risk <= EPS:
        return None
    # THE SIZE GATE. Not a detection gate -- a takeability test, and the number
    # is the engine's own: signal_runner.min_risk_floor, max($0.10, 0.15% of
    # price), the constant the B&R call sites already use with the comment "an
    # intrabar fill sitting on the stop has no trade to size". It matters here
    # because 1R is a FIXED $1,000: a fill one cent from its stop is a
    # 100,000-share position and an R-multiple with a one-cent denominator, and
    # that is arithmetic, not a trade. Recorded per row, applied as a filter
    # only in the gated grid, and applied there to ALL SIX policies including
    # the control so the comparison stays like-for-like.
    floor = sr.min_risk_floor(bars[fill_i].close)
    # shipped: 84% re-entries carry the ORIGINAL trade's target, everything
    # else is a flat 2R measured from its own entry.
    if row["setup"] == "reentry_84_rule":
        target = row["target"]
    else:
        target = entry_px + 2 * risk if long else entry_px - 2 * risk
    # shipped F1 ladder geometry, as-of the entry bar (no look-ahead)
    scale_level = runner_tgt = 0.0
    if bw.SCALE_PLAN:
        pre = bars[:fill_i + 1]
        if long:
            scale_level = max(c.high for c in pre)
            cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]
            cands.append(math.floor(scale_level) + 1.0)
            runner_tgt = min(cands)
        else:
            scale_level = min(c.low for c in pre)
            cands = [x for x in (pdl, pml) if x is not None and x < scale_level]
            cands.append(math.ceil(scale_level) - 1.0)
            runner_tgt = max(cands)

    t = SimTrade(symbol=row["sym"], day=row["day"], signal_type=row["setup"],
                 direction=row["dir"], grade=row["grade"], status=row["status"],
                 entry_time=bars[fill_i].timestamp, entry=entry_px, stop=stop,
                 target=target, reason=row["reason"], entry_idx=fill_i,
                 exit_idx=len(bars) - 1, be_level=0.0, scale_level=scale_level,
                 runner_target=runner_tgt, setup_type=row["setup"],
                 stop_level_name=row.get("level_name") or "")
    t.level_price = row["level_px"]

    runner = _Stub(bars, row.get("bias") if row.get("bias") != "none" else None)
    open_trades = [t]
    for i in range(fill_i + 1, len(bars)):
        if not open_trades:
            break
        _ladder_bar(t, bars[i], i, open_trades, runner)
    if open_trades:                      # EOD: whatever is open scratches
        t.outcome, t.exit_price = "scratch", bars[-1].close
        t.exit_idx = len(bars) - 1
    p = t.pnl
    return {"sym": row["sym"], "day": row["day"], "et": row["et"],
            "setup": row["setup"], "grade": row["grade"],
            "sgrade": row.get("sgrade", "n/a"),
            "entry": round(entry_px, 4), "stop": round(stop, 4),
            "exit": round(t.exit_price, 4), "out": t.outcome,
            "pnl": p, "r": round(p / RISK, 4), "fill_i": fill_i,
            "signal_i": row["entry_i"], "scaled": bool(t.scaled),
            "risk": round(risk, 4), "floor": round(floor, 4),
            "sizeable": bool(risk >= floor)}


# ------------------------------------------------------------------ pricing

def drawdown(seq):
    cum = peak = worst = 0.0
    for p in seq:
        cum += p
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def price(rows, n_days, all_days):
    if not rows:
        return {"trades": 0, "win_pct": 0.0, "total_dollars": 0, "mean_r": 0.0,
                "per_day": 0, "per_month": 0, "months_green": 0, "months": 0,
                "weeks_green": 0, "weeks": 0, "worst_drawdown": 0}
    rows = sorted(rows, key=lambda r: (r["day"], r["et"], r["sym"]))
    pnls = [r["pnl"] for r in rows]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    by_m, by_w = defaultdict(float), defaultdict(float)
    for r in rows:
        by_m[r["day"][:7]] += r["pnl"]
        y, w, _ = date.fromisoformat(r["day"]).isocalendar()
        by_w[(y, w)] += r["pnl"]
    all_m = {d[:7] for d in all_days}
    all_w = {date.fromisoformat(d).isocalendar()[:2] for d in all_days}
    total = sum(pnls)
    return {
        "trades": len(rows),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "total_dollars": round(total, 0),
        "mean_r": round(total / len(rows) / RISK, 4),
        "per_day": round(total / n_days, 0),
        "per_month": round(total / n_days * 20, 0),
        "months_green": sum(1 for k in all_m if by_m.get(k, 0.0) > 0),
        "months": len(all_m),
        "weeks_green": sum(1 for k in all_w if by_w.get(k, 0.0) > 0),
        "weeks": len(all_w),
        "worst_drawdown": round(drawdown(pnls), 0),
    }


def day_ci(rows, all_days):
    """95% interval on dollars a day, resampling whole SESSIONS. A day with no
    trade contributes $0 and stays in the draw."""
    by_d = {d: 0.0 for d in all_days}
    for r in rows:
        by_d[r["day"]] = by_d.get(r["day"], 0.0) + r["pnl"]
    v = [by_d[d] for d in sorted(by_d)]
    rng = random.Random(SEED)
    n = len(v)
    means = sorted(sum(rng.choices(v, k=n)) / n for _ in range(BOOTS))
    return {"per_day": round(sum(v) / n, 0),
            "ci95_low": round(means[int(BOOTS * 0.025)], 0),
            "ci95_high": round(means[int(BOOTS * 0.975)], 0)}


# ---------------------------------------------------------------------- main

def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, allrows = book["meta"], book["trades"]
    n_days = meta["sessions"]
    all_days = sorted({r["day"] for r in allrows})

    traded = [r for r in allrows if r.get("traded")]
    traded.sort(key=lambda r: (r["day"], r["et"], r["sym"]))
    # one-a-day candidate stream, in signal order. Same stream
    # g80_dollar_reconcile.py uses: a fired-and-traded row, or a row the
    # account-wide two-loss halt blocked (under one-a-day the halt cannot have
    # fired yet, so those days are candidates again).
    # candidates are addressed by their INDEX in the book, never by
    # (day, time, symbol): 93 symbol-minutes carry more than one traded signal
    # and a tuple key silently merges them.
    cand_by_day = defaultdict(list)
    for idx, r in enumerate(allrows):
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            cand_by_day[r["day"]].append(idx)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"]))

    print("book: %d traded rows, %d sessions, %d one-a-day candidate days"
          % (len(traded), n_days, len(cand_by_day)), flush=True)

    # ---- pass 1: price every candidate under every policy -------------------
    # keyed by (day, et, sym, entry_i) so the one-a-day walk can look a
    # candidate up without re-simulating it.
    priced = {p: {} for p in POLICIES}
    nofill = {p: Counter() for p in POLICIES}
    fillkind = {p: Counter() for p in POLICIES}
    armkind = Counter()
    collapse_without_intrabar_stop = Counter()
    lead = []          # policy A: bars the limit filled AHEAD of the signal

    universe = {}
    for idx, r in enumerate(allrows):
        if r.get("traded") or r["status"] == "halted":
            universe[idx] = r
    keys = sorted(universe, key=lambda i: (allrows[i]["day"], allrows[i]["et"],
                                           allrows[i]["sym"], i))
    print("pricing %d distinct candidates x %d policies ..." % (len(keys), len(POLICIES)),
          flush=True)

    for n, k in enumerate(keys):
        if n and n % 1000 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        bars, pdh, pdl, pmh, pml = day_pack(r["sym"], r["day"])
        if not bars or r["entry_i"] >= len(bars):
            for p in POLICIES:
                nofill[p]["no_bars"] += 1
            continue
        arm, how = arm_index(r, bars)
        armkind[(r["setup"], how)] += 1
        for p in POLICIES:
            fi, px, tag = resolve_entry(p, r, bars, arm)
            if fi is None:
                nofill[p][tag] += 1
                continue
            # diagnostic: would this fill be untakeable if the stop were held
            # at the book's stop rather than moved by the shipped intrabar_stop?
            long = r["dir"] == "call"
            raw_risk = (px - r["stop"]) if long else (r["stop"] - px)
            if raw_risk <= EPS:
                collapse_without_intrabar_stop[p] += 1
            res = run_trade(r, bars, fi, px, pdh, pdl, pmh, pml,
                            move_stop_to_entry_bar=(p != "A2"))
            if res is None:
                nofill[p]["risk_collapsed_even_after_intrabar_stop"] += 1
                continue
            fillkind[p][tag] += 1
            priced[p][k] = res
            if p == "A":
                lead.append(r["entry_i"] - fi)

    # ---- harness proof: BOOK must reproduce the published book --------------
    #
    # The strong test is the EXIT: same outcome word, same exit price. R cannot
    # match to the last digit and should not be expected to -- backtest_2y.py
    # writes `entry` and `stop` rounded to the cent, so the risk denominator
    # this rig divides by is the rounded one and the book's is not. That is a
    # rounding residue on the denominator, not a different trade. It is
    # reported in full rather than hidden behind a tolerance.
    n_out = n_exit = 0
    dr = []
    diffs = []
    tr_keys = [k for k in priced["BOOK"] if universe[k].get("traded")]
    for k in tr_keys:
        res, r = priced["BOOK"][k], universe[k]
        if res["out"] == r["out"]:
            n_out += 1
        if abs(res["exit"] - r["exit"]) <= 0.005:
            n_exit += 1
        elif len(diffs) < 12:
            diffs.append({"sym": r["sym"], "day": r["day"], "et": r["et"],
                          "setup": r["setup"], "book_exit": r["exit"],
                          "harness_exit": res["exit"], "book_r": r["r"],
                          "harness_r": res["r"]})
        dr.append(res["r"] - r["r"])
    proof = {
        "traded_rows_repriced": len(tr_keys),
        "same_outcome_word": n_out,
        "same_exit_price": n_exit,
        "r_delta_mean": round(statistics.fmean(dr), 5) if dr else None,
        "r_delta_median": round(statistics.median(dr), 5) if dr else None,
        "r_delta_max_abs": round(max(abs(x) for x in dr), 4) if dr else None,
        "r_within_0p005": sum(1 for x in dr if abs(x) <= 0.005),
        "r_within_0p05": sum(1 for x in dr if abs(x) <= 0.05),
        "why_r_differs": "backtest_2y writes entry/stop rounded to the cent; "
                         "the risk denominator here is the rounded one",
        "sample_exit_differences": diffs,
    }
    print("\nHARNESS PROOF (shipped fill re-run through this rig, %d traded rows):"
          % len(tr_keys), flush=True)
    print("   same outcome word: %d    same exit price: %d    mean R residue %+.5f "
          "(max |%.4f|)" % (n_out, n_exit, proof["r_delta_mean"] or 0.0,
                            proof["r_delta_max_abs"] or 0.0), flush=True)

    # ---- pass 2: the two arms -----------------------------------------------
    out = {"meta": {"book": meta, "policies": POLICY_NAME,
                    "risk_dollars": RISK, "cutoff": CUTOFF},
           "harness_proof": proof,
           "arming": {"%s / %s" % k: v for k, v in sorted(armkind.items())},
           "policy_A_lead_bars": {
               "n": len(lead),
               "median": statistics.median(lead) if lead else None,
               "mean": round(statistics.fmean(lead), 2) if lead else None,
               "filled_before_signal": sum(1 for x in lead if x > 0),
               "filled_on_signal_bar": sum(1 for x in lead if x == 0),
               "filled_after_signal": sum(1 for x in lead if x < 0)},
           "grid": {}}

    traded_keys = [k for k in keys if universe[k].get("traded")]

    # how tight the geometry got, policy by policy, against the book's own risk
    risk_ratio = {}
    for p in POLICIES:
        rr = []
        for k in traded_keys:
            res, r = priced[p].get(k), universe[k]
            if not res:
                continue
            long = r["dir"] == "call"
            br = (r["entry"] - r["stop"]) if long else (r["stop"] - r["entry"])
            if br > EPS and res["risk"] > EPS:
                rr.append(br / res["risk"])
        rr.sort()
        risk_ratio[p] = {
            "n": len(rr),
            "median_book_risk_over_policy_risk": round(statistics.median(rr), 3) if rr else None,
            "p90": round(rr[int(0.9 * len(rr))], 2) if rr else None,
            "max": round(rr[-1], 1) if rr else None,
            "pct_below_engine_size_floor": round(
                100 * sum(1 for k in traded_keys
                          if k in priced[p] and not priced[p][k]["sizeable"])
                / max(1, len(priced[p])), 1)}
    out["risk_geometry"] = risk_ratio

    for gated in (False, True):
        book_out = out["grid_size_gated" if gated else "grid_as_specified"] = {}
        for p in POLICIES:
            def ok(k):
                return k in priced[p] and (priced[p][k]["sizeable"] or not gated)
            everything = [priced[p][k] for k in traded_keys if ok(k)]
            # one trade a day: walk the day's candidates in signal order and
            # take the FIRST ONE THAT ACTUALLY FILLS (and, in the gated grid,
            # is big enough to size). A day where none of them do books $0 and
            # is counted as a MISSED DAY -- a no-fill is not a free option.
            one, missed, depth = [], [], Counter()
            for d in sorted(cand_by_day):
                took = None
                for pos, k in enumerate(cand_by_day[d]):
                    if ok(k):
                        took = priced[p][k]
                        depth[min(pos + 1, 4)] += 1
                        break
                if took is None:
                    missed.append(d)
                else:
                    one.append(took)
            book_out[p] = {
                "name": POLICY_NAME[p],
                "fills": len(everything),
                "no_fills": len(traded_keys) - len(everything),
                "no_fill_reasons": dict(nofill[p]),
                "fill_kinds": dict(fillkind[p]),
                "untakeable_if_stop_held_at_book_stop": collapse_without_intrabar_stop[p],
                "everything": price(everything, n_days, all_days),
                "everything_ci": day_ci(everything, all_days),
                "one_a_day": price(one, n_days, all_days),
                "one_a_day_ci": day_ci(one, all_days),
                "one_a_day_days_traded": len(one),
                "one_a_day_days_missed": len(missed),
                "one_a_day_candidate_depth": dict(sorted(depth.items())),
                "exit_mix": dict(Counter(r["out"] for r in everything)),
            }

    # ---- the console tables -------------------------------------------------
    for key, title in (("grid_as_specified",
                        "GRID 1 - AS SPECIFIED, no size gate "
                        "(A/D/E R-multiples are arithmetic, not trades)"),
                       ("grid_size_gated",
                        "GRID 2 - SIZE GATE ON, every policy incl. the control "
                        "(this is the one to read)")):
        print("\n" + "=" * 100)
        print(title)
        print("\n%-44s %6s %7s %6s %8s %10s %8s %8s"
              % ("policy - ONE TRADE A DAY", "trades", "missed", "win%", "$/day",
                 "95% CI", "months", "weeks"))
        for p in POLICIES:
            g = out[key][p]
            s, ci = g["one_a_day"], g["one_a_day_ci"]
            print("%-44s %6d %7d %5.1f%% %8s %10s %5d/%2d %4d/%3d"
                  % (g["name"][:44], s["trades"], g["one_a_day_days_missed"],
                     s["win_pct"], "$%.0f" % s["per_day"],
                     "[$%.0f,$%.0f]" % (ci["ci95_low"], ci["ci95_high"]),
                     s["months_green"], s["months"], s["weeks_green"], s["weeks"]))
        print("\n%-44s %6s %7s %6s %9s %10s %12s"
              % ("policy - EVERYTHING TAKEN", "fills", "nofill", "win%", "meanR",
                 "$/day", "worst DD"))
        for p in POLICIES:
            g = out[key][p]
            s = g["everything"]
            print("%-44s %6d %7d %5.1f%% %+9.4f %10s %12s"
                  % (g["name"][:44], g["fills"], g["no_fills"], s["win_pct"],
                     s["mean_r"], "$%.0f" % s["per_day"],
                     "$%.0f" % s["worst_drawdown"]))

    print("\nHOW TIGHT THE GEOMETRY GOT (book risk / policy risk):")
    for p in POLICIES:
        g = risk_ratio[p]
        print("   %-44s median %sx  p90 %sx  max %sx   below the engine's own "
              "size floor: %s%%"
              % (POLICY_NAME[p][:44], g["median_book_risk_over_policy_risk"],
                 g["p90"], g["max"], g["pct_below_engine_size_floor"]))

    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nwrote %s" % OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
