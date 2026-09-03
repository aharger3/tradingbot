"""targets_level -- level-aware 2R targets, swept across the snap tolerance.

THE QUESTION (assigned slice of the 2026-09-03 backtest sweep): the shipped
ladder's PT3 rung is "2R, snapped to a whole dollar or named level within
0.25R" (research/MASTER_SPEC.md section 3). 0.25R was never itself tested
against the alternatives -- this is that test. Sweep the snap tolerance from
0.00R (the null: always flat 2R) to 0.50R and ask the sharper question than
"is level-aware better than flat 2R": IS LEVEL-AWARENESS BETTER THAN A FLAT
TARGET OF THE SAME AVERAGE DISTANCE? A level-aware target's average distance
usually is not 2.0R (nearby levels pull it in, distant ones require widening
past 2R before anything qualifies), so the fair control is not "flat 2R" but
"flat at whatever this arm's own mean target distance came out to".

METHOD, single-target only (not the 4-rung ladder -- this isolates the PT3
lever exactly, everything else held fixed):

  1. entry, stop, side are the book's own (research/bt2y_trades_retest_on.json,
     first-of-day arm, g86_honest_ceiling.candidates -- same 444-row
     denominator as every other g9x/g10x sweep on this book).
  2. flat 2R target = entry +/- 2*risk.
  3. for tolerance tol_r, snap that price to the nearest whole dollar or named
     level (PDH/PMH/ORH long, PDL/PML/ORL short -- the exact roster and
     precedence research/g101_open_and_ladder.py::_substitute uses for the
     shipped PT3 rung, reproduced verbatim here rather than imported, so this
     file does not pull in backtest_week/stop_rule through g101's module-level
     imports) if one sits within tol_r*risk; else the flat 2R price stands.
  4. walk forward bar-ordered from entry_i+1 (the fill is entry_i's own CLOSE,
     so that bar's high/low already happened -- g97_mfe.walk's convention),
     stop wins a bar that touches both (within-bar order is unknowable on
     1-minute OHLC), a bar past 11:00 never opens, and an alive position at
     11:00 marks to that last close. Stop is -1.0R hard on an intrabar touch
     (Austin's 2026-09-03 ruling R1: "the level stop is final", the -1.25R
     floor "has never fired" -- so it is not modelled; this matches g97_mfe's
     already-audited convention on this exact book).
  5. control, same tolerance arm: recompute step 3's AVERAGE realised target
     distance (in R) over the same row set, then re-walk every row against
     THAT SINGLE FLAT NUMBER. Same n, same bars, same stop -- only the fact
     that the target price varies row-to-row is switched off.
  6. paired bootstrap (10,000 resamples, seed fixed) on level-arm R minus
     matched-flat-control R, per row -- the correct interval for a same-rows
     paired comparison (research/g71_exitfam.py::paired_ci's method,
     reproduced locally for the same reason as #3).

Levels are causal throughout: PDH/PDL are the prior archived session's own
high/low (g80_ordertype_grid.day_pack), PMH/PML are that day's own pre-09:30
bars, ORH/ORL are the first 15 RTH bars and only used when entry_i >= 15 (so
the opening range has actually closed before the decision). Whole-dollar
snapping is arithmetic on the target price alone. Nothing here reads a bar at
or after the decision bar. No arm in this sweep is unshippable on that count;
the size gate (`signal_runner.min_risk_floor`, imported via
research.omen_metrics with its documented retry/fallback) removes the other
class (a risk denominator too thin to be a real position) before any target
is even built, so n is identical -- 444 -- across every arm.

    python research/sweep_targets_level.py
    writes research/sweep_targets_level.json
"""
from __future__ import annotations

import importlib
import json
import os
import statistics
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research.omen_metrics import (          # noqa: E402
    ev_r_scoreboard, min_risk_floor, evaluate_prop_challenge,
    MIN_RISK_FLOOR_SOURCE,
)

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "sweep_targets_level.json")

WIN_END = "11:00:00"
OR_BARS = 15
PSYCH_STEP = 1.00
TOLS = [round(0.05 * k, 2) for k in range(11)]     # 0.00, 0.05, ..., 0.50
BOOTSTRAP = 10000
SEED = 20260903


# --------------------------------------------------------------------------
# g80_ordertype_grid / g86_honest_ceiling import through backtest_week --
# CLAUDE.md names both mid-edit tonight. Retry once, exactly the pattern
# research/omen_metrics.py uses for signal_runner.min_risk_floor.
# --------------------------------------------------------------------------
def _resolve_module(name):
    for attempt in range(2):
        try:
            importlib.invalidate_caches()
            return importlib.import_module(name)
        except Exception:
            if attempt == 0:
                time.sleep(2)
                continue
            raise


G = _resolve_module("research.g80_ordertype_grid")
g86 = _resolve_module("research.g86_honest_ceiling")


# --------------------------------------------------------------------------
# the snap -- reproduced verbatim from g101_open_and_ladder._substitute
# (not imported: that module pulls backtest_week/stop_rule in at import time,
# which is exactly the mid-edit surface this file is told to stay off of).
# Only addition: also return the source name, for the substitution-rate table.
# --------------------------------------------------------------------------
def substitute(px, entry, risk, long, named, tol_r, step=PSYCH_STEP):
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
        return px, None
    best = min(s[2] for s in subs)
    tied = [s for s in subs if abs(s[2] - best) < 1e-9]
    tied.sort(key=lambda s: (0 if s[0] != "whole$" else 1, abs(s[1] - entry)))
    return tied[0][1], tied[0][0]


def or_extremes(bars, entry_i):
    """Causal opening-range high/low: only when the OR has actually closed
    before the entry decision (entry_i >= OR_BARS), else (None, None) --
    identical guard to g101_open_and_ladder.open_state's 'no_read'."""
    if entry_i is None or entry_i < OR_BARS or len(bars) <= OR_BARS:
        return None, None
    return (max(c.high for c in bars[:OR_BARS]),
            min(c.low for c in bars[:OR_BARS]))


def walk_to_target(bars, entry_i, entry, risk, long, target_price):
    """Bar-ordered from entry_i+1, stop wins a bar that touches both, EOD
    marks the last close at/before 11:00. g97_mfe.walk's convention, for one
    arbitrary target price instead of a menu of flat R multiples."""
    last_close = entry
    for b in bars[entry_i + 1:]:
        if b.timestamp > WIN_END:
            break
        last_close = b.close
        adv = ((entry - b.low) if long else (b.high - entry)) / risk
        if adv >= 1.0:
            return -1.0, "stop"
        touched = (b.high >= target_price) if long else (b.low <= target_price)
        if touched:
            r = (target_price - entry) / risk if long else (entry - target_price) / risk
            return r, "target"
    mark = ((last_close - entry) if long else (entry - last_close)) / risk
    return mark, "eod"


def paired_ci(diffs, n=BOOTSTRAP, seed=SEED):
    """95% paired-bootstrap interval on mean(diffs), vectorised with numpy.
    Same method as g71_exitfam.paired_ci, reproduced locally (that module's
    top-level imports pull stop_rule, the other mid-edit file)."""
    d = np.asarray(diffs, dtype=float)
    m = len(d)
    if m == 0:
        return 0.0, 0.0, 0.0, 0.0
    obs = float(d.mean())
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, m, size=(n, m))
    means = d[idx].mean(axis=1)
    means.sort()
    lo = float(means[int(0.025 * n)])
    hi = float(means[int(0.975 * n) - 1])
    return obs, lo, hi, (hi - lo) / 2.0


def survives(lo, hi):
    return (lo > 0 and hi > 0) or (lo < 0 and hi < 0)


# --------------------------------------------------------------------------
def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, allrows = blob["meta"], blob["trades"]
    sessions = meta.get("sessions") or len({r["day"] for r in allrows})

    byday = g86.candidates(allrows)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]

    print("min_risk_floor source: %s" % MIN_RISK_FLOOR_SOURCE)
    print("book: %s -- %d sessions, %d first-of-day candidates (pre-gate)"
          % (os.path.basename(BOOK_PATH), sessions, len(firsts)))

    prepared = []
    gated = nobars = no_entry_i = wrong_side = 0
    for r in firsts:
        entry, stop = r["entry"], r["stop"]
        risk = abs(entry - stop)
        if risk < min_risk_floor(entry):
            gated += 1
            continue
        i = r.get("entry_i")
        if i is None:
            no_entry_i += 1
            continue
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        if not bars or i >= len(bars):
            nobars += 1
            continue
        long = r["dir"] == "call"
        sign = 1.0 if long else -1.0
        orh, orl = or_extremes(bars, i)
        named = ({"PDH": pdh, "PMH": pmh, "ORH": orh} if long
                 else {"PDL": pdl, "PML": pml, "ORL": orl})
        flat2r_px = entry + sign * 2.0 * risk
        prepared.append(dict(sym=r["sym"], day=r["day"], entry_i=i, entry=entry,
                              stop=stop, risk=risk, long=long, sign=sign,
                              named=named, flat2r_px=flat2r_px, bars=bars))

    n = len(prepared)
    print("prepared %d rows  (%d below min_risk_floor, %d no bars, %d no entry_i)"
          % (n, gated, nobars, no_entry_i))
    if n == 0:
        raise SystemExit("nothing measurable")

    arms = {}
    for tol in TOLS:
        level_r, flat_targets_r, srcs = [], [], []
        for p in prepared:
            tgt_px, src = substitute(p["flat2r_px"], p["entry"], p["risk"],
                                      p["long"], p["named"], tol)
            intended_r = p["sign"] * (tgt_px - p["entry"]) / p["risk"]
            if intended_r <= 0:
                wrong_side += 1
                intended_r = 2.0
                tgt_px, src = p["flat2r_px"], None
            r_val, why = walk_to_target(p["bars"], p["entry_i"], p["entry"],
                                         p["risk"], p["long"], tgt_px)
            level_r.append(r_val)
            flat_targets_r.append(intended_r)
            srcs.append(src)

        avg_dist_r = statistics.fmean(flat_targets_r)
        control_r = []
        for p in prepared:
            ctrl_px = p["entry"] + p["sign"] * avg_dist_r * p["risk"]
            r_val, why = walk_to_target(p["bars"], p["entry_i"], p["entry"],
                                         p["risk"], p["long"], ctrl_px)
            control_r.append(r_val)

        level_rows = [{"r": r_val, "day": p["day"]}
                      for p, r_val in zip(prepared, level_r)]
        control_rows = [{"r": r_val, "day": p["day"]}
                        for p, r_val in zip(prepared, control_r)]
        sb_level = ev_r_scoreboard(level_rows, sessions=sessions, size_gate=False)
        sb_ctrl = ev_r_scoreboard(control_rows, sessions=sessions, size_gate=False)

        diffs = [a - b for a, b in zip(level_r, control_r)]
        obs, lo, hi, half = paired_ci(diffs)

        n_sub = sum(1 for s in srcs if s is not None)
        n_whole = sum(1 for s in srcs if s == "whole$")
        n_named = sum(1 for s in srcs if s not in (None, "whole$"))

        arms[tol] = {
            "tol_r": tol, "n": n,
            "pct_substituted": round(100.0 * n_sub / n, 1),
            "pct_whole_dollar": round(100.0 * n_whole / n, 1),
            "pct_named_level": round(100.0 * n_named / n, 1),
            "avg_target_dist_R": round(avg_dist_r, 4),
            "level": sb_level, "flat_control": sb_ctrl,
            "delta_ev_r": round(sb_level["ev_r"] - sb_ctrl["ev_r"], 4),
            "delta_ci_obs": round(obs, 4), "delta_ci_lo": round(lo, 4),
            "delta_ci_hi": round(hi, 4), "delta_survives_95ci": survives(lo, hi),
        }

    print("\n%d rows if a level snap ever lands on the wrong side of entry "
          "(clamped back to flat 2R, should be 0 or near it)" % wrong_side)

    print("\n=== targets_level: %d tolerance arms tested, %d rows each "
          "(size-gated, causal, denominator fixed) ===" % (len(TOLS), n))
    print("%-6s %6s %7s %7s %9s | %8s %6s %6s %5s | %8s %5s | %9s %-22s %s"
          % ("tol_R", "sub%", "whole%", "named%", "avgdistR",
             "ev_r_LVL", "win%", "PF", "mGrn",
             "ev_r_CTL", "mGrn", "delta", "95% paired CI", "survives"))
    for tol in TOLS:
        a = arms[tol]
        lv, ct = a["level"], a["flat_control"]
        print("%6.2f %5.1f%% %6.1f%% %6.1f%% %9.3f | %8.4f %5.1f%% %6.2f %5s | "
              "%8.4f %5s | %+9.4f [%+.4f,%+.4f]  %s"
              % (tol, a["pct_substituted"], a["pct_whole_dollar"],
                 a["pct_named_level"], a["avg_target_dist_R"],
                 lv["ev_r"], lv["win_rate"] * 100, lv["profit_factor"] or 0.0,
                 lv["months_green"], ct["ev_r"], ct["months_green"],
                 a["delta_ev_r"], a["delta_ci_lo"], a["delta_ci_hi"],
                 "YES" if a["delta_survives_95ci"] else "no"))

    best_level = max(arms.values(), key=lambda a: a["level"]["ev_r"])
    best_delta = max(arms.values(), key=lambda a: a["delta_ev_r"])
    flat_baseline = arms[0.00]["level"]

    print("\nbest raw ev_r arm: tol=%.2fR  ev_r=%.4f (vs tol=0.00R null ev_r=%.4f, "
          "delta over the null itself = %+.4f)"
          % (best_level["tol_r"], best_level["level"]["ev_r"],
             flat_baseline["ev_r"],
             best_level["level"]["ev_r"] - flat_baseline["ev_r"]))
    print("best MATCHED-DISTANCE delta (level minus flat-of-same-avg-distance): "
          "tol=%.2fR  delta=%+.4f  95%% CI [%+.4f, %+.4f]  survives=%s"
          % (best_delta["tol_r"], best_delta["delta_ev_r"],
             best_delta["delta_ci_lo"], best_delta["delta_ci_hi"],
             best_delta["delta_survives_95ci"]))

    any_survive = [a for a in arms.values() if a["delta_survives_95ci"]]
    print("\narms whose level-vs-matched-flat delta clears its own 95%% paired CI "
          "(excludes zero): %d of %d" % (len(any_survive), len(TOLS)))
    for a in any_survive:
        print("  tol=%.2fR  delta=%+.4f  [%+.4f, %+.4f]"
              % (a["tol_r"], a["delta_ev_r"], a["delta_ci_lo"], a["delta_ci_hi"]))

    # prop-eval PASS/FAIL, book baseline vs the best matched-distance arm, at
    # the risk levels omen_metrics.main() already checks -- same denominator,
    # same $50k defaults, so this is directly comparable to the other sweeps.
    print("\n=== prop-eval PASS/FAIL -- tol=0.00R null vs best matched-distance "
          "arm (tol=%.2fR), $50k eval, defaults ===" % best_delta["tol_r"])
    account_size = 50000.0

    def daily_from(tol, which):
        # rebuild the per-row R stream for this tol arm's chosen side, grouped
        # to (day, pnl) at each risk level on demand
        rs = []
        for p in prepared:
            if which == "level":
                tgt_px, _ = substitute(p["flat2r_px"], p["entry"], p["risk"],
                                        p["long"], p["named"], tol)
                intended_r = p["sign"] * (tgt_px - p["entry"]) / p["risk"]
                if intended_r <= 0:
                    tgt_px = p["flat2r_px"]
            else:
                tgt_px = p["entry"] + p["sign"] * arms[tol]["avg_target_dist_R"] * p["risk"]
            r_val, _ = walk_to_target(p["bars"], p["entry_i"], p["entry"],
                                       p["risk"], p["long"], tgt_px)
            rs.append((p["day"], r_val))
        return rs

    print("  %-16s %-6s %-6s %-24s %-12s %-10s %-8s" %
          ("risk/trade", "arm", "PASS?", "fail_reason", "fail_day", "final%", "DD%"))
    for risk_per_trade in (100, 250, 500, 1000, 2000, 5000):
        for label, tol, which in (("null(2R)", 0.00, "level"),
                                   ("best(%.2fR)" % best_delta["tol_r"],
                                    best_delta["tol_r"], "level")):
            rs = daily_from(tol, which)
            daily = [(d, r * risk_per_trade) for d, r in rs]
            res = evaluate_prop_challenge(daily, account_size=account_size)
            print("  $%-15s %-6s %-6s %-24s %-12s %-10s %-8s" % (
                risk_per_trade, label, "PASS" if res["passed"] else "FAIL",
                res["fail_reason"] or "-", res["fail_day"] or "-",
                "%.1f" % res["final_equity_pct"], "%.1f" % res["max_drawdown_seen_pct"]))

    out = {"book": os.path.basename(BOOK_PATH), "sessions": sessions, "n": n,
           "gated": gated, "nobars": nobars, "no_entry_i": no_entry_i,
           "wrong_side_clamped": wrong_side, "tols_tested": TOLS,
           "arms": {str(k): v for k, v in arms.items()}}
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("\nwrote %s" % OUT_JSON)


if __name__ == "__main__":
    main()
