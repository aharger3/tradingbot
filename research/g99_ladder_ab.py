"""g99b -- price every exit plan on the honest book, one table.

MASTER SPEC (exit ladder lane, 2026-09-01/02). This script owns itself only:
research/g99_ladder_ab.py. It does not edit backtest_week.py, levels_ladder.py,
or any other engine file, and as of this commit none of Agent A/B/C/D's files
(levels_ladder.py, the four_rung engine, ga1_ladder_replay.py) exist yet -- so
the four-rung ladder below is a SELF-CONTAINED research replica of spec section
1-3, built only to answer the pass-test question, not the shipped engine. See
BLOCKERS at the bottom of this docstring.

Population: `bt2y_trades_retest_on.json`, first-of-day (g86_honest_ceiling.
candidates), size-gated on `signal_runner.min_risk_floor` -- the SAME 444 rows
g97_mfe.py measured (54 dropped, 0 missing bars). This script asserts that
baseline before printing anything else and fails loudly if it drifts.

Arms priced, all on the identical 444-row population, all size-gated the same
way, mean R and $/day computed with `g86_honest_ceiling.stats` (not re-derived):

  book today        the shipped SCALE_PLAN result already in the trade row
                     (r["pnl"] / r["r"]) -- no replay, it is what shipped.
  blind 2R           flat 2R target, bar-ordered, stop wins a tied bar
                     -- reused verbatim from g97_mfe.walk(row, bars)[2][2.0].
  flat 1.5R / 2.5R / 4.0R   same reuse, g97's own TARGETS tuple.
  four-rung 30/30/30/10     PT1/PT2/PT3/PT4 per spec section 1-3, default weights.
  four-rung 50/20/20/10     same ladder, the alternate size plan (section 4).

Fills route through the ONE shared primitives this repo already ships:
`backtest_week._target_hit` / `_stop_hit` (touch-target, close-stop, both
default-armed) and `stop_rule.stop_fill_price` / `disaster_stop_price` /
`disaster_stop_hit` (the -1.25R floor and the intrabar disaster stop). Nothing
here re-implements a fill.

    python research/g99_ladder_ab.py

BLOCKERS (say so, don't force it):
  1. levels_ladder.build_rungs (Agent B) and the four_rung engine in
     backtest_week.py (Agent A) do not exist on this branch. The `build_rungs`
     / `_walk_ladder` functions below are a research-only replica written from
     the same spec section 1-3/5.4, for measurement purposes ONLY -- they are
     NOT the shipped seam and must not be imported by anything that ships. When
     Agent A/B land, P4 (this replay vs. a real backtest_2y.py run, +-15%)
     still has to be re-checked against the real engine, not against this file.
  2. named_levels pool is PDH/PMH/PDL/PML/OR-high/OR-low only, matching
     g99_rung_recon.py exactly (bt2y_trades_retest_on.json's own precedent);
     intraday/HTF pivots are out of scope here (spec section 5.4 ranks HTF
     pivots last in the build order and they need `signal_runner.pivot_levels`
     wiring this script does not own).
  3. The psych-tolerance / step sweep (spec section 2's mandatory sweep,
     Agent C's `ga1_ladder_replay.py --sweep tol`) is NOT run here. This script
     prices the ladder at the spec's stated defaults (psych_tol=0.25r,
     psych_step=1.00, pt4_mode=max, pt4_r=4.0, min_gap_r=0.20) crossed with the
     two size plans only, per this dispatch's scope.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402  reuse, do not re-derive
import g91_lane_slice as g91                       # noqa: E402  reuse, do not re-derive
import g97_mfe as g97                               # noqa: E402  reuse walk() for flat targets
import signal_runner as sr                          # noqa: E402
import stop_rule as SR                              # noqa: E402
import backtest_week as bw                          # noqa: E402  read-only: _target_hit/_stop_hit
from research import g80_ordertype_grid as G        # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
BASELINE_JSON = os.path.join(HERE, "g97_mfe.json")   # committed baseline to reproduce
OUT_JSON = os.path.join(HERE, "g99_ladder_ab.json")
WIN_END = "11:00:00"
RISK_DOLLARS = g86.RISK          # 1000.0

# spec defaults -- not swept here (see BLOCKER 3)
PSYCH_STEP = 1.00
PSYCH_TOL_R = 0.25
PT4_MODE = "max"
PT4_R = 4.0
MIN_GAP_R = 0.20
DD_LIMIT = 2000.0
DD_BUDGET = 2500.0

SIZE_PLANS = {
    "30/30/30/10": (0.30, 0.30, 0.30, 0.10),
    "50/20/20/10": (0.50, 0.20, 0.20, 0.10),
}

Rung = namedtuple("Rung", "price weight name")


# --------------------------------------------------------------------------
# section 1-2 replica: build_rungs
# --------------------------------------------------------------------------

def build_rungs(entry, stop, long, session_extreme, named_levels, weights,
                psych_step=PSYCH_STEP, psych_tol_r=PSYCH_TOL_R,
                pt4_mode=PT4_MODE, pt4_r=PT4_R, min_gap_r=MIN_GAP_R):
    """Returns a list[Rung], 1-4 rungs, strictly monotonic, weights sum to 1.0.

    Pure. Never sees a bar after the entry bar -- `session_extreme` and
    `named_levels` are both supplied causal by the caller."""
    risk = abs(entry - stop)
    sign = 1.0 if long else -1.0

    def R(px):
        return sign * (px - entry) / risk

    def beyond(pivot):
        return {k: v for k, v in named_levels.items()
                if v is not None and ((v > pivot) if long else (v < pivot))}

    cands = {}

    # PT1 -- near session extreme, dropped if inside min_gap_r
    if R(session_extreme) >= min_gap_r:
        cands["PT1"] = session_extreme

    # PT2 -- nearest named level strictly beyond the session extreme
    b1 = beyond(session_extreme)
    if b1:
        nm = min(b1, key=lambda k: R(b1[k]))
        cands["PT2:%s" % nm] = b1[nm]

    # PT3 -- 2R, subject to the precedence substitution
    px_2r = entry + sign * 2.0 * risk
    tol = psych_tol_r * risk
    subs = []
    k0 = round(px_2r / psych_step)
    for dk in (-1, 0, 1):
        wd = (k0 + dk) * psych_step
        d = abs(wd - px_2r)
        if d <= tol:
            subs.append(("whole$", wd, d))
    for nm, v in named_levels.items():
        if v is None:
            continue
        d = abs(v - px_2r)
        if d <= tol:
            subs.append((nm, v, d))
    if subs:
        best_d = min(s[2] for s in subs)
        tied = [s for s in subs if abs(s[2] - best_d) < 1e-9]
        # named level beats whole dollar; still tied, nearer to entry wins
        tied.sort(key=lambda s: (0 if s[0] != "whole$" else 1, abs(s[1] - entry)))
        pt3_px = tied[0][1]
    else:
        pt3_px = px_2r
    cands["PT3"] = pt3_px

    # PT4 -- the runner
    rmult_px = entry + sign * pt4_r * risk
    if pt4_mode == "rmult":
        pt4_px = rmult_px
    else:
        b3 = beyond(pt3_px)
        struct_px = None
        if b3:
            nm = min(b3, key=lambda k: R(b3[k]))
            struct_px = b3[nm]
        if pt4_mode == "structure":
            pt4_px = struct_px if struct_px is not None else rmult_px
        else:  # "max" -- the further of the two
            pt4_px = rmult_px
            if struct_px is not None and R(struct_px) > R(rmult_px):
                pt4_px = struct_px
    cands["PT4"] = pt4_px

    # drop non-positive R, sort ascending, coalesce with min_gap_r, nearer wins
    items = [(nm, px) for nm, px in cands.items() if R(px) > 0]
    items.sort(key=lambda x: R(x[1]))
    kept = []
    for nm, px in items:
        if not kept or R(px) - R(kept[-1][1]) >= min_gap_r:
            kept.append((nm, px))
    if not kept:
        raise AssertionError("PT3 (2R) is always >= min_gap_r from entry -- unreachable")

    w = list(weights[:len(kept)])
    s = sum(w)
    w = [x / s for x in w]
    return [Rung(px, wt, nm) for (nm, px), wt in zip(kept, w)]


# --------------------------------------------------------------------------
# bar walk: fills route through backtest_week._target_hit/_stop_hit and
# stop_rule's fill/floor primitives. No fill is re-implemented here.
# --------------------------------------------------------------------------

def walk_ladder(row, bars, rungs, trail="be"):
    """Bar-ordered fill simulation for one trade against its ladder.

    Returns list[(weight, price)], weights summing to 1.0 (asserted by caller).
    A bar that closes past the stop and also touched a rung on the SAME bar
    fills no rung -- the stop wins the bar (house rule, mirrors g97.walk and
    spec section 5.4 step 4)."""
    entry, stop = row["entry"], row["stop"]
    risk = abs(entry - stop)
    long = row["dir"] == "call"
    i = row["entry_i"]

    remaining = 1.0
    fills = []
    filled = set()
    stop_lv = stop
    last_close = entry

    seg = [c for c in bars[i + 1:] if c.timestamp <= WIN_END]
    for c in seg:
        last_close = c.close

        # disaster stop: only while the original stop is still the live one
        if stop_lv == stop:
            dz = SR.disaster_stop_price(entry, risk, long, SR.DISASTER_STOP_R)
            if SR.disaster_stop_hit(c.high, c.low, dz, long):
                fills.append((remaining, dz))
                remaining = 0.0
                break

        touched = [idx for idx, r in enumerate(rungs)
                  if idx not in filled and bw._target_hit(c, r.price, long)]

        if bw._stop_hit(c, stop_lv, long):
            px = SR.stop_fill_price(c.close, entry, risk, long)
            if touched:
                px = min(px, stop_lv) if long else max(px, stop_lv)
            fills.append((remaining, px))
            remaining = 0.0
            break

        if touched:
            for idx in sorted(touched, key=lambda j: rungs[j].price if long else -rungs[j].price):
                r = rungs[idx]
                filled.add(idx)
                fills.append((r.weight, r.price))
                remaining -= r.weight
            if trail == "be":
                stop_lv = entry
            if len(filled) == len(rungs):
                remaining = 0.0
                break

    if remaining > 1e-9:
        fills.append((remaining, last_close))
    return fills


def r_of_fills(fills, entry, stop, long):
    risk = abs(entry - stop)
    sign = 1.0 if long else -1.0
    return sum(w * sign * (px - entry) / risk for w, px in fills)


# --------------------------------------------------------------------------
# named levels + session extreme, matching g99_rung_recon.py exactly
# --------------------------------------------------------------------------

def named_levels_for(row, bars, pdh, pdl, pmh, pml, orh, orl):
    long = row["dir"] == "call"
    if long:
        return {"PDH": pdh, "PMH": pmh, "ORH": orh}
    return {"PDL": pdl, "PML": pml, "ORL": orl}


def session_extreme(row, bars):
    i = row["entry_i"]
    long = row["dir"] == "call"
    if long:
        return max(c.high for c in bars[:i + 1])
    return min(c.low for c in bars[:i + 1])


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def load_firsts():
    b = json.load(open(BOOK, encoding="utf-8"))
    rows = b["trades"] if isinstance(b, dict) else b
    byday = g86.candidates(rows)
    return [byday[d][0] for d in sorted(byday) if byday[d]]


def check_baseline(n, gated, target_r):
    """Fail loudly if this run's population does not match the committed g97
    baseline (research/g97_mfe.json) -- same book, same gate, same rows."""
    if not os.path.exists(BASELINE_JSON):
        raise SystemExit("BASELINE MISSING: %s -- cannot verify population, refusing to print numbers"
                         % BASELINE_JSON)
    base = json.load(open(BASELINE_JSON, encoding="utf-8"))
    if base.get("lane") != "full":
        raise SystemExit("BASELINE lane mismatch: %r" % base.get("lane"))
    if n != base["n"] or gated != base["gated"]:
        raise SystemExit(
            "BASELINE DRIFT: this run n=%d gated=%d, committed g97_mfe.json n=%d gated=%d "
            "-- population no longer matches, refusing to trust any figure below"
            % (n, gated, base["n"], base["gated"]))
    for t in (1.5, 2.0, 2.5, 4.0):
        got = target_r[t]
        want = base["targets"][str(t)]
        if abs(got - want) > 5e-3:
            raise SystemExit(
                "BASELINE DRIFT on flat target %.1fR: this run %.4f, committed %.4f"
                % (t, got, want))
    print("baseline check OK: n=%d gated=%d, flat targets match g97_mfe.json exactly\n"
          % (n, gated))


def main():
    firsts = load_firsts()
    print("first-of-day rows (pre-gate): %d" % len(firsts))

    rows, no_bars, gated = [], 0, 0
    # per-arm daily-pnl-shaped rows for g86.stats: {"day","et","sym","pnl"}
    arm_rows = {
        "book today": [],
        "blind 2R": [],
        "flat 1.5R": [],
        "flat 2.5R": [],
        "flat 4.0R": [],
        "four-rung 30/30/30/10": [],
        "four-rung 50/20/20/10": [],
    }
    target_sum = {1.5: [], 2.0: [], 2.5: [], 4.0: []}

    for k, r in enumerate(firsts, 1):
        entry, stop = r["entry"], r["stop"]
        risk = abs(entry - stop)
        if risk < sr.min_risk_floor(entry):
            gated += 1
            continue
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r.get("entry_i")
        if not bars or i is None or i >= len(bars):
            no_bars += 1
            continue
        rows.append(r)

        long = r["dir"] == "call"
        orh = max(c.high for c in bars[:5])
        orl = min(c.low for c in bars[:5])
        base = dict(day=r["day"], et=r["et"], sym=r["sym"])

        # -- book today: the shipped result, no replay --
        arm_rows["book today"].append(dict(base, pnl=r["pnl"]))

        # -- blind flat targets, reused verbatim from g97.walk --
        w = g97.walk(r, bars)
        if w is None:
            # shouldn't happen: same gate already applied above, but be safe
            gated += 1
            rows.pop()
            continue
        _, _, outcomes = w
        for t, arm in ((1.5, "flat 1.5R"), (2.0, "blind 2R"),
                      (2.5, "flat 2.5R"), (4.0, "flat 4.0R")):
            arm_rows[arm].append(dict(base, pnl=outcomes[t] * RISK_DOLLARS))
        for t in (1.5, 2.0, 2.5, 4.0):
            target_sum[t].append(outcomes[t])

        # -- four-rung ladder, both size plans --
        named = named_levels_for(r, bars, pdh, pdl, pmh, pml, orh, orl)
        ext = session_extreme(r, bars)
        for label, weights in SIZE_PLANS.items():
            rungs = build_rungs(entry, stop, long, ext, named, weights)
            fills = walk_ladder(r, bars, rungs)
            wsum = sum(w_ for w_, _ in fills)
            assert abs(wsum - 1.0) < 1e-6, "weights must sum to 1.0, got %.6f" % wsum
            rr = r_of_fills(fills, entry, stop, long)
            assert rr >= -1.2501, "floor breached: %.4fR on %s %s" % (rr, r["sym"], r["day"])
            arm_rows["four-rung %s" % label].append(dict(base, pnl=rr * RISK_DOLLARS))

        if k % 150 == 0:
            print("  ... %d/%d" % (k, len(firsts)))

    n = len(rows)
    print("\nmeasured %d  (%d below min_risk_floor, %d no bars)" % (n, gated, no_bars))

    target_means = {t: statistics.fmean(v) for t, v in target_sum.items()}
    check_baseline(n, gated, target_means)

    print("| arm | $/day | win | months green | max drawdown | mean R |")
    print("|---|---:|---:|---:|---:|---:|")
    out = {}
    for label in ("book today", "blind 2R", "flat 1.5R", "flat 2.5R", "flat 4.0R",
                 "four-rung 30/30/30/10", "four-rung 50/20/20/10"):
        st = g86.stats(arm_rows[label], n)
        out[label] = st
        print("| %-24s | $%-6d | %5.1f%% | %6s | $%-7d | %+.4f |"
              % (label, st["per_day"], st["win_pct"],
                 "%d/%d" % (st["months_green"], st["months"]),
                 st["worst_drawdown"], st["mean_r"]))

    print("\nrow count sanity: every arm should carry exactly %d trades" % n)
    for label, st in out.items():
        flag = "" if st["trades"] == n else "  <-- MISMATCH"
        print("  %-24s %d%s" % (label, st["trades"], flag))

    json.dump({"n": n, "gated": gated, "no_bars": no_bars, "arms": out},
              open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("\n  -> %s" % OUT_JSON)


if __name__ == "__main__":
    main()
