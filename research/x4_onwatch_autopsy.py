"""x4_onwatch_autopsy.py -- WHY the ON WATCH / mid-candle entry is not working.

Austin: "how is entry as candle forming 'on watch' working? not well so thats a
priority to make it work because thats another angle money is being left on the
table. good entry for good RR."

And the original statement of the problem: "the goal of my comments was for an
entry to be made BEFORE the candle closes, because most of the time the candle
closes near/above HOD/LOD and the RR is shot."

WHAT IS ALREADY KNOWN AND IS NOT RE-DERIVED HERE
------------------------------------------------
  research/p25_midcandle_entry.md   the homework page could not record a
                                    mid-candle fill at all (build_omen_test1.py
                                    :696 wrote out.entry_p = closes[i]).
  research/g12_recall_regression.md the intrabar fill BACK-DATES the entry onto
                                    the broken level; for break-and-retest
                                    BNR_STOP_MODE="level" so the level IS the
                                    stop, |entry-stop| collapses, and the
                                    minimum-risk floor deletes the signal.
  research/p26_intrabar_ambiguity.md the intrabar marker and the 2dp rounding
                                    correction that goes with it. IMPORTED, not
                                    restated.
  research/g3_onwatch_2y.md         ON_WATCH gates only near_session_extreme,
                                    reachable from 2 of fill_price's 10 call
                                    sites. The flag is not a close-fill switch.

WHAT THIS FILE ADDS
-------------------
Four measurements over the shipped 2-year book, research/g3_arm_ow1.json
(ON_WATCH=1, 45,193 signals, 1,017 traded, 2024-08-21..2026-08-21):

 1. FILL CENSUS.  intrabar vs at-close, split by which predicate fired
    (bar_extreme_veto / near_session_extreme / both), on the traded book and on
    the whole book. Plus the funnel that matters: of the B&R signals the fill
    rule moved, how many the minimum-risk floor then deleted.

 2. THE PRIZE, AND THE DENOMINATOR TRAP.  For every traded row, the distance
    from the booked entry to that bar's CLOSE, in R. Then four arms over the
    B&R book on ONE common denominator D = |close - structural_stop|, so a
    better fill cannot flatter itself by shrinking its own R unit:

      BOOKED    the published number, denominated in |entry - stop| (collapsed)
      LEVEL/D   the shipped fill, re-denominated on D
      CLOSE/D   entry = the entry bar's close
      TRIG/D    entry = level + one tolerance unit (0.25 x the PREVIOUS bar's
                range) beyond the level, filled as a stop order would fill

    Exit PRICES are held fixed in every arm, so the arms differ by entry price
    and nothing else. The realised size-weighted price move per share is
    recovered exactly as M = r_booked * |entry - stop|, which holds for the
    scale-out ladder too because the rung fractions sum to 1.

 3. THE FLOOR.  min_risk_floor() = max(0.10, 0.0015 x close), signal_runner.py
    :1054-1060, applied at :2087 (long B&R) and :2327 (short B&R). Counted: how
    many S-graded signals sit under it, how many of those are under it ONLY
    because the fill moved, and what the implied OPTION premium risk is on the
    rows that survive it (the instrument is options, not shares).

 4. THE TIME HALF.  What 1-minute OHLC can and cannot decide about a trigger
    that is half price and half clock.

LEVEL RECONSTRUCTION -- how the structural level is recovered without a replay
-----------------------------------------------------------------------------
BNR_STOP_MODE == "level" (signal_runner.py:127), so for break-and-retest the
structural stop IS the broken level. Three cases, all decidable from the book
row plus the entry bar (long; short mirrors):

  at-close fill    entry == round(close,2). intrabar_stop cannot have fired
                   (close > level == stop, so `collapsed` is False), therefore
                   level == stop.
  squeeze          level < bar.low, so fill_price clamps the fill to bar.low and
                   the stop is untouched: entry == bar.low, level == stop.
  collapse         bar.low <= level <= close, so the fill lands exactly on the
                   level and intrabar_stop moves the stop to bar.low:
                   stop == bar.low, level == entry.

Every reconstruction is checked against the emit condition `close > level`
(long) / `close < level` (short); failures are counted and excluded, never
silently kept.

USAGE
-----
    python research/x4_onwatch_autopsy.py build     # -> research/_x4_rows.json
    python research/x4_onwatch_autopsy.py report    # -> research/_x4_summary.json
    python research/x4_onwatch_autopsy.py --selfcheck

READ-ONLY. No engine default is changed, no flag is added, nothing is fetched:
bars come from data_archive/ only and a cache miss is a reported gap, so this
can never touch POLYGON_API_KEY.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import polygon_feed as pf                                              # noqa: E402
import signal_runner as sr                                             # noqa: E402
from research.p26_intrabar_ambiguity import (                          # noqa: E402
    HALF_CENT, EPS, SETUP_BNR, SETUP_84,
    bar_extreme_fires, on_watch_fires, load_day, index_day,
)

BOOK = os.path.join(HERE, "g3_arm_ow1.json")
ROWS = os.path.join(HERE, "_x4_rows.json")
SUMMARY = os.path.join(HERE, "_x4_summary.json")

FRAC = sr.BAR_EXTREME_FRAC          # 0.25, one tolerance unit
RISK_DOLLARS = 1000.0


# ---------------------------------------------------------------------------
# pass 1 -- attach the entry bar, the previous bar and the running extremes
# ---------------------------------------------------------------------------

def build(limit=None):
    with open(BOOK, encoding="utf-8") as fh:
        book = json.load(fh)
    by_day = defaultdict(list)
    for r in book["trades"]:
        by_day[(r["sym"], r["day"])].append(r)

    keys = sorted(by_day)
    if limit:
        keys = keys[:limit]

    out, miss_day, miss_bar = [], 0, 0
    for n, (sym, day) in enumerate(keys):
        rth = load_day(sym, day)
        if not rth:
            miss_day += len(by_day[(sym, day)])
            continue
        idx, run_hi, run_lo = index_day(rth)
        for r in by_day[(sym, day)]:
            i = idx.get(r["et"])
            if i is None:
                miss_bar += 1
                continue
            b = rth[i]
            prev = rth[i - 1] if i > 0 else None
            out.append({
                "sym": sym, "day": day, "et": r["et"], "dir": r["dir"],
                "setup": r["setup"], "sgrade": r["sgrade"], "grade": r["grade"],
                "traded": bool(r["traded"]), "status": r["status"],
                "r": float(r["r"]), "entry": float(r["entry"]),
                "stop": float(r["stop"]), "exit": float(r["exit"]),
                "out": r["out"], "scaled": bool(r["scaled"]),
                "o": b.open, "h": b.high, "l": b.low, "c": b.close,
                "prng": (prev.high - prev.low) if prev is not None else None,
                "shi": run_hi[i], "slo": run_lo[i],
            })
        if n and n % 2000 == 0:
            print("  %d/%d symbol-days" % (n, len(keys)), flush=True)

    payload = {"meta": book["meta"], "missing_day": miss_day,
               "missing_bar": miss_bar, "rows": out}
    with open(ROWS, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    print("wrote %s  rows=%d  missing_day=%d missing_bar=%d"
          % (ROWS, len(out), miss_day, miss_bar))
    return payload


# ---------------------------------------------------------------------------
# derived per-row geometry
# ---------------------------------------------------------------------------

def classify(x: dict) -> dict:
    """Everything the four questions need about one signal."""
    long = x["dir"] == "call"
    sgn = 1.0 if long else -1.0
    e, s, c = x["entry"], x["stop"], x["c"]
    lo, hi, op = x["l"], x["h"], x["o"]

    d = dict(x)
    d["long"] = long
    d["intrabar"] = abs(e - round(c, 2)) > EPS
    d["p_bar_extreme"] = bar_extreme_fires(_B(x), long, x["setup"])
    d["p_on_watch"] = on_watch_fires(_B(x), long, x["setup"], x["shi"], x["slo"])
    d["risk"] = abs(e - s)
    d["floor"] = sr.min_risk_floor(c)
    d["under_floor"] = d["risk"] < d["floor"]
    # the fill's own displacement from the close, signed so + = the fill was
    # BETTER than the close for this direction
    d["gain_px"] = (c - e) * sgn

    # --- structural level, break-and-retest only -------------------------
    level = None
    kind = "n/a"
    if x["setup"] == SETUP_BNR:
        edge = round(lo, 2) if long else round(hi, 2)
        if not d["intrabar"]:
            level, kind = s, "at_close"
        elif abs(s - edge) < HALF_CENT and ((e > s) if long else (e < s)):
            level, kind = e, "collapse"
        elif abs(e - edge) < HALF_CENT and ((s < e) if long else (s > e)):
            level, kind = s, "squeeze"
        else:
            # entry == stop exactly: the fill landed on the level and the
            # bar's own extreme WAS the level, so intrabar_stop had nothing
            # to widen to. level == entry == stop; risk is literally zero.
            level, kind = s, "degenerate"
        # the emit condition the engine tested: close strictly through the level
        ok = (c > level) if long else (c < level)
        if not ok:
            kind = "reject_" + kind
            level = None
    d["level"] = level
    d["lvl_kind"] = kind

    # --- the common denominator, and the three counterfactual entries ----
    if level is not None:
        D = (c - level) * sgn                   # structural risk read at the close
        d["D"] = D if D > 0 else None
        tol = (FRAC * x["prng"]) if x["prng"] else None
        d["tol"] = tol
        if tol is None:
            d["trig"] = None
            d["trig_kind"] = "no_prev_bar"
        else:
            tp = level + tol * sgn
            if (hi >= tp) if long else (lo <= tp):
                # a stop order at tp: fills at tp, or at the open if the bar
                # opened already through it
                d["trig"] = max(tp, op) if long else min(tp, op)
                d["trig_kind"] = "opened_through" if (
                    (op >= tp) if long else (op <= tp)) else "triggered"
            else:
                d["trig"] = c                   # never reached inside the bar
                d["trig_kind"] = "not_reached"
    else:
        d["D"] = None
        d["tol"] = None
        d["trig"] = None
        d["trig_kind"] = "no_level"

    # --- the realised size-weighted price move, recovered exactly --------
    # r_booked = M / |entry - stop| where M = sum_j frac_j * (exit_j - entry)*sgn
    # and sum_j frac_j == 1, so M is exact for the scale-out ladder too.
    d["M"] = x["r"] * d["risk"] if d["risk"] > 0 else None
    return d


class _B:
    """Minimal candle shim so p26's predicates can be reused verbatim."""
    __slots__ = ("open", "high", "low", "close")

    def __init__(self, x):
        self.open, self.high, self.low, self.close = x["o"], x["h"], x["l"], x["c"]


def arm_r(d: dict, entry: float) -> float:
    """R of one row under an alternative ENTRY price, on the common
    denominator D, with every exit price held fixed.

        M(entry) = M(booked) + (booked_entry - entry) * sgn
        R        = M(entry) / D
    """
    sgn = 1.0 if d["long"] else -1.0
    return (d["M"] + (d["entry"] - entry) * sgn) / d["D"]


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def mean(xs):
    return statistics.fmean(xs) if xs else float("nan")


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def report():
    with open(ROWS, encoding="utf-8") as fh:
        payload = json.load(fh)
    rows = [classify(x) for x in payload["rows"]]
    traded = [d for d in rows if d["traded"]]
    out = {"meta": payload["meta"], "n_rows": len(rows), "n_traded": len(traded),
           "missing_day": payload["missing_day"], "missing_bar": payload["missing_bar"]}
    P = print

    # === 1. fill census =================================================
    P("\n=== 1. FILL CENSUS =================================================")
    for name, pop in (("traded", traded), ("whole book", rows)):
        intra = [d for d in pop if d["intrabar"]]
        both = [d for d in intra if d["p_bar_extreme"] and d["p_on_watch"]]
        be = [d for d in intra if d["p_bar_extreme"] and not d["p_on_watch"]]
        ow = [d for d in intra if d["p_on_watch"] and not d["p_bar_extreme"]]
        nei = [d for d in intra if not d["p_bar_extreme"] and not d["p_on_watch"]]
        P("%-10s n=%-6d intrabar %d (%.1f%%)  at-close %d (%.1f%%)"
          % (name, len(pop), len(intra), pct(len(intra), len(pop)),
             len(pop) - len(intra), pct(len(pop) - len(intra), len(pop))))
        P("           of the intrabar: bar_extreme only %d | on_watch only %d | both %d | neither %d"
          % (len(be), len(ow), len(both), len(nei)))
        out["census_" + name.replace(" ", "_")] = {
            "n": len(pop), "intrabar": len(intra),
            "bar_extreme_only": len(be), "on_watch_only": len(ow),
            "both": len(both), "neither": len(nei)}
    # predicate reach: how many rows COULD have filled intrabar
    bnr = [d for d in rows if d["setup"] == SETUP_BNR]
    P("\nB&R signals %d; predicate fired on %d (%.1f%%); intrabar marker on %d (%.1f%%)"
      % (len(bnr),
         sum(1 for d in bnr if d["p_bar_extreme"] or d["p_on_watch"]),
         pct(sum(1 for d in bnr if d["p_bar_extreme"] or d["p_on_watch"]), len(bnr)),
         sum(1 for d in bnr if d["intrabar"]),
         pct(sum(1 for d in bnr if d["intrabar"]), len(bnr))))
    P("level reconstruction on B&R (whole book): %s"
      % Counter(d["lvl_kind"] for d in bnr).most_common())
    P("level reconstruction on B&R (traded)    : %s"
      % Counter(d["lvl_kind"] for d in bnr if d["traded"]).most_common())
    out["lvl_kind_bnr"] = dict(Counter(d["lvl_kind"] for d in bnr))
    out["lvl_kind_bnr_traded"] = dict(Counter(d["lvl_kind"] for d in bnr if d["traded"]))
    # what the unclassified rows are: the fill is neither the bar's extreme nor
    # leaves the stop on it, so the three-case reconstruction does not apply.
    unc = [d for d in bnr if d["lvl_kind"] == "degenerate"]
    P("  degenerate (entry==stop) rows: traded %d | entry==stop %d | risk median $%.4f"
      % (sum(1 for d in unc if d["traded"]),
         sum(1 for d in unc if abs(d["entry"] - d["stop"]) < 1e-9),
         med([d["risk"] for d in unc])))
    out["degenerate"] = {"n": len(unc), "traded": sum(1 for d in unc if d["traded"])}

    P("\nfill census by setup (traded rows):")
    for st in sorted(set(d["setup"] for d in traded)):
        p = [d for d in traded if d["setup"] == st]
        P("  %-18s n=%-5d intrabar %d (%.1f%%)  on_watch predicate %d"
          % (st, len(p), sum(1 for d in p if d["intrabar"]),
             pct(sum(1 for d in p if d["intrabar"]), len(p)),
             sum(1 for d in p if d["p_on_watch"])))
        out.setdefault("census_by_setup", {})[st] = {
            "n": len(p), "intrabar": sum(1 for d in p if d["intrabar"]),
            "on_watch": sum(1 for d in p if d["p_on_watch"])}

    # the flag literally named ON WATCH reaches only near_session_extreme, and
    # only where bar_extreme_veto did not already fire. That subset is the whole
    # of what ON_WATCH=0 gives back.
    owo = [d for d in traded if d["intrabar"] and d["p_on_watch"] and not d["p_bar_extreme"]]
    P("\nON_WATCH-only traded rows (the flag's entire reach): n=%d, "
      "gain vs close median %+0.4f booked R, mean R booked %+0.4f"
      % (len(owo), med([d["gain_px"] / d["risk"] for d in owo if d["risk"] > 0]),
         mean([d["r"] for d in owo])))
    out["on_watch_only"] = {
        "n": len(owo),
        "gain_median_booked_R": med([d["gain_px"] / d["risk"] for d in owo if d["risk"] > 0]),
        "mean_r": mean([d["r"] for d in owo])}

    # === the starvation funnel ==========================================
    P("\n=== THE FUNNEL: what the fill rule creates, the floor deletes ======")
    fired = [d for d in bnr if d["p_bar_extreme"] or d["p_on_watch"]]
    uf = [d for d in fired if d["under_floor"]]
    ufS = [d for d in uf if d["sgrade"] == "S"]
    P("B&R signals whose fill was moved off the close : %d" % len(fired))
    P("  ... of those, |entry-stop| lands UNDER the floor: %d (%.1f%%)"
      % (len(uf), pct(len(uf), len(fired))))
    P("  ... of those under-floor rows graded S by downgrade.py: %d" % len(ufS))
    P("  ... of those under-floor rows actually traded: %d" % sum(1 for d in uf if d["traded"]))
    # would the STRUCTURAL geometry have cleared the floor?
    resc = [d for d in uf if d["D"] is not None and d["D"] >= d["floor"]]
    P("  ... under-floor rows that CLEAR the floor on |close - level|: %d (%.1f%%)"
      % (len(resc), pct(len(resc), len(uf))))
    P("  ... of those, graded S: %d" % sum(1 for d in resc if d["sgrade"] == "S"))
    out["funnel"] = {"fill_moved": len(fired), "under_floor": len(uf),
                     "under_floor_S": len(ufS),
                     "under_floor_traded": sum(1 for d in uf if d["traded"]),
                     "rescued_by_structural": len(resc),
                     "rescued_S": sum(1 for d in resc if d["sgrade"] == "S")}
    # at-close comparison group
    notmoved = [d for d in bnr if not (d["p_bar_extreme"] or d["p_on_watch"])]
    P("control: B&R signals filled AT THE CLOSE %d, under floor %d (%.1f%%)"
      % (len(notmoved), sum(1 for d in notmoved if d["under_floor"]),
         pct(sum(1 for d in notmoved if d["under_floor"]), len(notmoved))))
    out["funnel"]["at_close_n"] = len(notmoved)
    out["funnel"]["at_close_under_floor"] = sum(1 for d in notmoved if d["under_floor"])

    # === 2. the prize ===================================================
    P("\n=== 2. THE PRIZE: entry -> that bar's close, in R ==================")
    for name, pop in (("all traded", traded),
                      ("intrabar fills", [d for d in traded if d["intrabar"]]),
                      ("at-close fills", [d for d in traded if not d["intrabar"]])):
        g_book = [d["gain_px"] / d["risk"] for d in pop if d["risk"] > 0]
        g_str = [d["gain_px"] / d["D"] for d in pop if d["D"]]
        P("%-16s n=%-5d  gain vs close, BOOKED R: median %+0.4f mean %+0.4f | "
          "STRUCTURAL R: n=%d median %+0.4f mean %+0.4f"
          % (name, len(pop), med(g_book), mean(g_book), len(g_str), med(g_str), mean(g_str)))
        out["prize_" + name.replace(" ", "_").replace("-", "_")] = {
            "n": len(pop), "booked_R_median": med(g_book), "booked_R_mean": mean(g_book),
            "struct_n": len(g_str), "struct_R_median": med(g_str),
            "struct_R_mean": mean(g_str)}
    gb = sorted(d["gain_px"] / d["risk"] for d in traded if d["risk"] > 0)
    P("distribution of gain-vs-close in BOOKED R over %d traded rows:" % len(gb))
    P("  min %+0.3f  p10 %+0.3f  p25 %+0.3f  p50 %+0.3f  p75 %+0.3f  p90 %+0.3f  max %+0.3f"
      % ((gb[0],) + tuple(gb[int(q * (len(gb) - 1))] for q in (.10, .25, .50, .75, .90))
         + (gb[-1],)))
    out["prize_quantiles_booked_R"] = {q: gb[int(q * (len(gb) - 1))]
                                       for q in (0.10, 0.25, 0.50, 0.75, 0.90)}
    P("  rows where the fill beat the close: %d (%.1f%%);  equal: %d;  worse: %d"
      % (sum(1 for v in gb if v > 1e-9), pct(sum(1 for v in gb if v > 1e-9), len(gb)),
         sum(1 for v in gb if abs(v) <= 1e-9), sum(1 for v in gb if v < -1e-9)))

    # === the four arms ==================================================
    P("\n=== THE FOUR ARMS, one common denominator D = |close - level| =====")
    pool = [d for d in traded if d["setup"] == SETUP_BNR and d["D"] and d["trig"] is not None]
    P("pool: %d of %d traded B&R rows carry a reconstructed level, D>0 and a previous bar"
      % (len(pool), sum(1 for d in traded if d["setup"] == SETUP_BNR)))
    # D is the setup's structural risk read at the close. On the bar a break
    # confirms, the close is often only cents through the level, so D can be a
    # cent or two and 1/D explodes. The full pool is therefore read on the
    # MEDIAN; the mean is read on the sub-pool where D clears the engine's own
    # minimum-risk floor -- i.e. the rows that are sizeable on the structural
    # geometry, which is exactly the question the floor exists to ask.
    sized = [d for d in pool if d["D"] >= d["floor"]]
    P("  D (structural risk at the close): median $%.4f | p10 $%.4f | under the floor on %d of %d (%.1f%%)"
      % (med([d["D"] for d in pool]),
         sorted(d["D"] for d in pool)[int(.10 * (len(pool) - 1))],
         len(pool) - len(sized), len(pool), pct(len(pool) - len(sized), len(pool))))
    out["D_stats"] = {"median": med([d["D"] for d in pool]),
                      "sized_n": len(sized), "pool_n": len(pool)}

    def armset(p):
        return {
            "BOOKED (published, collapsed denominator)": [d["r"] for d in p],
            "LEVEL / D  (shipped fill, re-denominated)": [arm_r(d, d["entry"]) for d in p],
            "CLOSE / D  (entry = the bar's close)": [arm_r(d, d["c"]) for d in p],
            "TRIG  / D  (level + one tolerance unit)": [arm_r(d, d["trig"]) for d in p],
        }

    out["arms"] = {}
    for label, p in (("FULL POOL (read the MEDIAN)", pool),
                     ("D >= floor  (read the MEAN)", sized)):
        P("\n  --- %s, n=%d ---" % (label, len(p)))
        arms = armset(p)
        for k, v in arms.items():
            P("  %-44s mean %+0.4f R  median %+0.4f  win%% %.1f"
              % (k, mean(v), med(v), pct(sum(1 for z in v if z > 0), len(v))))
            out["arms"].setdefault(label, {})[k] = {
                "n": len(v), "mean": mean(v), "median": med(v),
                "win_pct": pct(sum(1 for z in v if z > 0), len(v))}
        tr, cl, lv, bk = (arms["TRIG  / D  (level + one tolerance unit)"],
                          arms["CLOSE / D  (entry = the bar's close)"],
                          arms["LEVEL / D  (shipped fill, re-denominated)"],
                          arms["BOOKED (published, collapsed denominator)"])
        P("  delta TRIG - CLOSE  mean %+0.4f R  median %+0.4f  (the pure entry-price prize)"
          % (mean(tr) - mean(cl), med(tr) - med(cl)))
        P("  delta LEVEL - CLOSE mean %+0.4f R  median %+0.4f  (the shipped fill, honestly denominated)"
          % (mean(lv) - mean(cl), med(lv) - med(cl)))
        P("  BOOKED - LEVEL/D    mean %+0.4f R  median %+0.4f  (pure denominator collapse, no price moved)"
          % (mean(bk) - mean(lv), med(bk) - med(lv)))
        out["arms"][label]["_deltas"] = {
            "trig_minus_close_mean": mean(tr) - mean(cl),
            "trig_minus_close_median": med(tr) - med(cl),
            "level_minus_close_mean": mean(lv) - mean(cl),
            "booked_minus_level_mean": mean(bk) - mean(lv)}
    arms = armset(pool)
    P("  trigger kinds: %s" % Counter(d["trig_kind"] for d in pool).most_common())
    out["trig_kinds"] = dict(Counter(d["trig_kind"] for d in pool))
    # S-only read
    sp = [d for d in pool if d["sgrade"] == "S"]
    if sp:
        P("  S-graded subset n=%d: BOOKED %+0.4f | LEVEL/D %+0.4f | CLOSE/D %+0.4f | TRIG/D %+0.4f"
          % (len(sp), mean([d["r"] for d in sp]), mean([arm_r(d, d["entry"]) for d in sp]),
             mean([arm_r(d, d["c"]) for d in sp]), mean([arm_r(d, d["trig"]) for d in sp])))
        out["arms_S"] = {"n": len(sp), "booked": mean([d["r"] for d in sp]),
                         "level_D": mean([arm_r(d, d["entry"]) for d in sp]),
                         "close_D": mean([arm_r(d, d["c"]) for d in sp]),
                         "trig_D": mean([arm_r(d, d["trig"]) for d in sp])}
    # how the tolerance unit compares to the floor it is meant to replace
    tv = [d["tol"] for d in pool if d["tol"]]
    fv = [d["floor"] for d in pool]
    P("  one tolerance unit (0.25 x prev bar range): median $%.4f | floor median $%.4f | "
      "tol >= floor on %d of %d (%.1f%%)"
      % (med(tv), med(fv),
         sum(1 for d in pool if d["tol"] and d["tol"] >= d["floor"]), len(pool),
         pct(sum(1 for d in pool if d["tol"] and d["tol"] >= d["floor"]), len(pool))))
    out["tol_vs_floor"] = {"tol_median": med(tv), "floor_median": med(fv),
                           "tol_ge_floor": sum(1 for d in pool if d["tol"] and d["tol"] >= d["floor"]),
                           "n": len(pool)}

    # === 2b. THE SELECTION EFFECT ======================================
    # The floor admits a B&R signal only when the close ran far enough past the
    # level. That is the same thing as "the candle closed near HOD/LOD and the
    # RR is shot" -- so the floor SELECTS FOR the entries Austin complains
    # about. Measured as D (level -> close) normalised by the previous bar's
    # range, so it is comparable across symbols and price levels.
    P("\n=== 2b. THE SELECTION EFFECT ======================================")
    bnr_lv = [d for d in bnr if d["level"] is not None and d["D"] and d["prng"]]
    tt = [d for d in bnr_lv if d["traded"]]
    dd = [d for d in bnr_lv if not d["traded"]]
    for nm, p in (("TRADED B&R", tt), ("DROPPED B&R", dd)):
        P("  %-12s n=%-6d  D median $%.4f  D/prev-bar-range median %.3f  D/close median %.4f%%"
          % (nm, len(p), med([d["D"] for d in p]),
             med([d["D"] / d["prng"] for d in p if d["prng"] > 0]),
             100 * med([d["D"] / d["c"] for d in p])))
    out["selection"] = {
        "traded_n": len(tt), "dropped_n": len(dd),
        "traded_D_median": med([d["D"] for d in tt]),
        "dropped_D_median": med([d["D"] for d in dd]),
        "traded_D_over_prng_median": med([d["D"] / d["prng"] for d in tt if d["prng"] > 0]),
        "dropped_D_over_prng_median": med([d["D"] / d["prng"] for d in dd if d["prng"] > 0])}
    P("  i.e. the book's B&R entries are the ones whose bar ran %.2fx further past the level"
      % (out["selection"]["traded_D_over_prng_median"]
         / out["selection"]["dropped_D_over_prng_median"]))

    # === 2c. THE PROPOSED ON WATCH GEOMETRY ============================
    # entry = level + one tolerance unit, filled as a stop order would fill
    # stop  = the entry BAR's own extreme -- Austin's own rule for an intrabar
    #         entry, written five times in the recovered reviews and already
    #         implemented in signal_runner.intrabar_stop, but reachable there
    #         only on FULL collapse.
    # This geometry cannot collapse: the entry is one tolerance unit above the
    # level and the bar's extreme is at or below it, so risk >= tol > 0 always.
    P("\n=== 2c. THE PROPOSED ON WATCH GEOMETRY ============================")
    prop = []
    for d in bnr_lv:
        if d["trig"] is None or d["trig_kind"] == "not_reached":
            continue
        bstop = d["l"] if d["long"] else d["h"]
        risk = (d["trig"] - bstop) if d["long"] else (bstop - d["trig"])
        if risk <= 0:
            continue
        prop.append((d, risk))
    P("  reachable on %d of %d B&R signals with a level (%.1f%%)"
      % (len(prop), len(bnr_lv), pct(len(prop), len(bnr_lv))))
    rk = [r for _, r in prop]
    P("  risk |trigger - entry bar extreme|: median $%.4f  p10 $%.4f  p90 $%.4f"
      % (med(rk), sorted(rk)[int(.10 * (len(rk) - 1))], sorted(rk)[int(.90 * (len(rk) - 1))]))
    clr = sum(1 for d, r in prop if r >= d["floor"])
    P("  clears the SHIPPED floor max(0.10, 0.0015*close): %d (%.1f%%)   "
      "[today's booked geometry clears it on %.1f%% of B&R]"
      % (clr, pct(clr, len(prop)),
         pct(sum(1 for d in bnr if not d["under_floor"]), len(bnr))))
    clrS = sum(1 for d, r in prop if r >= d["floor"] and d["sgrade"] == "S")
    P("  ... of which graded S by downgrade.py: %d  (today: %d S signals trade)"
      % (clrS, sum(1 for d in rows if d["sgrade"] == "S" and d["traded"])))
    pr = sorted(r * 0.5 for _, r in prop)
    P("  implied OPTION premium risk (delta 0.5): median $%.3f  under $0.20: %d (%.1f%%)"
      % (med(pr), sum(1 for v in pr if v < 0.20), pct(sum(1 for v in pr if v < 0.20), len(pr))))
    out["proposed"] = {
        "n": len(prop), "risk_median": med(rk), "clears_floor": clr,
        "clears_floor_pct": pct(clr, len(prop)), "clears_floor_S": clrS,
        "premium_median": med(pr),
        "premium_under_20c": sum(1 for v in pr if v < 0.20)}

    # === 3. the floor ===================================================
    P("\n=== 3. THE MINIMUM-RISK FLOOR =====================================")
    P("constant: signal_runner.min_risk_floor() = max(0.10, 0.0015 * close)  :1054-1060")
    P("applied : signal_runner.py:2087 (long B&R), :2327 (short B&R) -> TradeGrade.D")
    S = [d for d in rows if d["sgrade"] == "S"]
    Sd = [d for d in S if not d["traded"]]
    P("downgrade.py S signals in the book: %d (traded %d, dropped %d)"
      % (len(S), len(S) - len(Sd), len(Sd)))
    P("  dropped S under the floor          : %d (%.1f%% of dropped S)"
      % (sum(1 for d in Sd if d["under_floor"]), pct(sum(1 for d in Sd if d["under_floor"]), len(Sd))))
    P("  ... and intrabar-filled            : %d" % sum(1 for d in Sd if d["under_floor"] and d["intrabar"]))
    P("  ... and would CLEAR it structurally: %d" % sum(1 for d in Sd if d["under_floor"] and d["D"] and d["D"] >= d["floor"]))
    S_days = len(set((d["sym"], d["day"]) for d in Sd if d["under_floor"]))
    P("  distinct symbol-DAYS the floor suppresses at least one S on: %d" % S_days)
    out["floor"] = {
        "S_signals": len(S), "S_traded": len(S) - len(Sd), "S_dropped": len(Sd),
        "S_dropped_under_floor": sum(1 for d in Sd if d["under_floor"]),
        "S_dropped_under_floor_intrabar": sum(1 for d in Sd if d["under_floor"] and d["intrabar"]),
        "S_dropped_rescued_structural": sum(1 for d in Sd if d["under_floor"] and d["D"] and d["D"] >= d["floor"]),
        "S_days_suppressed": S_days}

    # The trigger is stated in VOLATILITY (0.25 x the previous bar's range); the
    # floor is stated in DOLLARS and PERCENT. They are not commensurable, which
    # is why one can manufacture a signal the other deletes. Express the floor in
    # the trigger's own unit and the incompatibility is a number.
    fu = [d["floor"] / d["prng"] for d in bnr if d["prng"] and d["prng"] > 0]
    P("\n  the floor expressed in the TRIGGER's unit (floor / previous bar range):")
    P("    median %.3f  p25 %.3f  p75 %.3f   -- one tolerance unit is 0.250"
      % (med(fu), sorted(fu)[int(.25 * (len(fu) - 1))], sorted(fu)[int(.75 * (len(fu) - 1))]))
    P("    so the shipped floor demands a stop %.2fx wider than the trigger it is "
      "gating, at the median" % (med(fu) / FRAC))
    out["floor_in_tolerance_units"] = {"median_over_prng": med(fu),
                                       "in_tolerance_units": med(fu) / FRAC}
    # `_min_viable_stop`'s volatility gate, the one floor already stated in the
    # trigger's unit -- but applied only to grade C (signal_runner.py:1908).
    P("    signal_runner.STOP_RANGE_MULT = %.2f x avg 1-min range is the ONE gate "
      "already in volatility units, and :1908 applies it to grade C only"
      % sr.STOP_RANGE_MULT)

    # premium arithmetic -- the instrument is options
    P("\n  the instrument is OPTIONS. _min_viable_stop uses premium = stock_risk * 0.5")
    prem = sorted(d["risk"] * 0.5 for d in traded)
    ncon = sorted(RISK_DOLLARS / (d["risk"] * 0.5 * 100.0) for d in traded if d["risk"] > 0)
    P("  traded book premium risk / contract-share: median $%.3f | p10 $%.3f | p90 $%.3f"
      % (med(prem), prem[int(.10 * (len(prem) - 1))], prem[int(.90 * (len(prem) - 1))]))
    P("  under $0.20 (the existing _min_viable_stop premium bar): %d of %d (%.1f%%)"
      % (sum(1 for v in prem if v < 0.20), len(prem), pct(sum(1 for v in prem if v < 0.20), len(prem))))
    P("  under $0.05 (one option tick, un-tradeable by any spread): %d (%.1f%%)"
      % (sum(1 for v in prem if v < 0.05), pct(sum(1 for v in prem if v < 0.05), len(prem))))
    P("  contracts needed to risk $1,000: median %.0f | p90 %.0f | max %.0f"
      % (med(ncon), ncon[int(.90 * (len(ncon) - 1))], ncon[-1]))
    out["premium"] = {"median": med(prem), "p10": prem[int(.10 * (len(prem) - 1))],
                      "p90": prem[int(.90 * (len(prem) - 1))],
                      "under_20c": sum(1 for v in prem if v < 0.20),
                      "under_5c": sum(1 for v in prem if v < 0.05),
                      "contracts_median": med(ncon), "contracts_max": ncon[-1]}

    # === 4. the time half ===============================================
    P("\n=== 4. THE TIME HALF ==============================================")
    tp_in = [d for d in pool if d["trig_kind"] in ("triggered", "opened_through")]
    P("  trigger price decidable from 1-min OHLC (did the bar trade there): %d of %d (%.1f%%)"
      % (len(tp_in), len(pool), pct(len(tp_in), len(pool))))
    P("  trigger never reached inside the entry bar: %d" % sum(1 for d in pool if d["trig_kind"] == "not_reached"))
    P("  bar opened already through the trigger (fill = open, not the trigger): %d"
      % sum(1 for d in pool if d["trig_kind"] == "opened_through"))
    # the only thing sub-minute order could change, given stops fire on closes
    amb = [d for d in pool
           if (d["l"] <= d["level"] <= d["h"]) and d["trig_kind"] != "not_reached"]
    P("  entry bar whose range ALSO contains the level/stop: %d (%.1f%%) -- "
      "irrelevant to exits (stops fire on closes), relevant only to whether a "
      "resting order filled" % (len(amb), pct(len(amb), len(pool))))
    out["time_half"] = {"pool": len(pool), "decidable": len(tp_in),
                        "not_reached": sum(1 for d in pool if d["trig_kind"] == "not_reached"),
                        "opened_through": sum(1 for d in pool if d["trig_kind"] == "opened_through"),
                        "range_contains_level": len(amb)}

    with open(SUMMARY, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    P("\nwrote %s" % SUMMARY)
    return out


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------

def selfcheck():
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(("  PASS  " if cond else "  FAIL  ") + name)
        ok = ok and bool(cond)

    print("selfcheck: constants read from the engine, never retyped")
    chk("BAR_EXTREME_FRAC is 0.25", abs(FRAC - 0.25) < 1e-12)
    chk("BNR_STOP_MODE is 'level'", sr.BNR_STOP_MODE == "level")
    chk("min_risk_floor(128) == max(0.10, 0.192)", abs(sr.min_risk_floor(128.0) - 0.192) < 1e-12)
    chk("min_risk_floor(20) floors at 0.10", abs(sr.min_risk_floor(20.0) - 0.10) < 1e-12)

    print("selfcheck: level reconstruction, all three shapes")
    # at-close long: close 100.5, level/stop 100.0
    d = classify(dict(sym="X", day="d", et="09:40", dir="call", setup=SETUP_BNR,
                      sgrade="S", grade="B", traded=True, status="t", r=1.0,
                      entry=100.5, stop=100.0, exit=101.0, out="win", scaled=False,
                      o=100.1, h=100.6, l=100.0, c=100.5, prng=0.40,
                      shi=100.6, slo=99.5))
    chk("at_close level == stop", d["lvl_kind"] == "at_close" and abs(d["level"] - 100.0) < 1e-9)
    chk("at_close D == |close - level|", abs(d["D"] - 0.5) < 1e-9)
    chk("trigger = level + 0.25*prev_range", abs(d["trig"] - 100.10) < 1e-9)
    # squeeze long: level 99.90 below the bar's low 100.00 -> fill at the low
    d = classify(dict(sym="X", day="d", et="09:40", dir="call", setup=SETUP_BNR,
                      sgrade="S", grade="B", traded=False, status="skipped_d", r=0.0,
                      entry=100.0, stop=99.90, exit=0.0, out="none", scaled=False,
                      o=100.4, h=100.6, l=100.0, c=100.55, prng=0.40,
                      shi=100.6, slo=99.5))
    chk("squeeze level == stop", d["lvl_kind"] == "squeeze" and abs(d["level"] - 99.90) < 1e-9)
    chk("squeeze is intrabar", d["intrabar"])
    # collapse long: level 100.20 inside the bar, stop moved to the bar low
    d = classify(dict(sym="X", day="d", et="09:40", dir="call", setup=SETUP_BNR,
                      sgrade="S", grade="B", traded=False, status="skipped_d", r=0.0,
                      entry=100.20, stop=100.00, exit=0.0, out="none", scaled=False,
                      o=100.4, h=100.6, l=100.00, c=100.55, prng=0.40,
                      shi=100.6, slo=99.5))
    chk("collapse level == entry", d["lvl_kind"] == "collapse" and abs(d["level"] - 100.20) < 1e-9)

    print("selfcheck: arm_r is exact and exit-path free")
    d = classify(dict(sym="X", day="d", et="09:40", dir="call", setup=SETUP_BNR,
                      sgrade="S", grade="B", traded=True, status="t", r=2.0,
                      entry=100.55, stop=100.00, exit=101.65, out="win", scaled=True,
                      o=100.1, h=100.6, l=100.0, c=100.55, prng=0.40,
                      shi=100.6, slo=99.5))
    # at-close fill: level == stop == 100.00, risk 0.55, M = r*risk = 1.10, D = 0.55
    chk("arm_r at the booked entry reproduces M/D",
        abs(arm_r(d, d["entry"]) - (1.10 / 0.55)) < 1e-9)
    chk("arm_r delta is purely the entry price over D",
        abs((arm_r(d, 100.35) - arm_r(d, 100.55)) - (0.20 / 0.55)) < 1e-9)
    chk("a short mirrors", abs(arm_r(
        classify(dict(sym="X", day="d", et="09:40", dir="put", setup=SETUP_BNR,
                      sgrade="S", grade="B", traded=True, status="t", r=2.0,
                      entry=99.45, stop=100.00, exit=98.35, out="win", scaled=True,
                      o=99.9, h=100.0, l=99.4, c=99.45, prng=0.40,
                      shi=100.6, slo=99.4)), 99.45) - (1.10 / 0.55)) < 1e-9)

    print("selfcheck: the 84% re-entry can never fill intrabar")
    chk("bar_extreme_fires is False for reentry_84_rule",
        not bar_extreme_fires(_B(dict(o=1, h=2, l=1, c=2)), True, SETUP_84))

    print("\nSELFCHECK " + ("GREEN" if ok else "RED"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["build", "report"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    if a.cmd == "build":
        build(a.limit)
        return 0
    if a.cmd == "report":
        report()
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
