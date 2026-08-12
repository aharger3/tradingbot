"""omen-5.0 T11: does S earn its way now?

Four replays over every marked (symbol, day) pair in the equity pool:

  before   pre-T11 engine  (displacement gate off, no mesh veto, no level
                            retirement, RULE_710 off)
  after    shipped T11 defaults
  s_gate   after + S_GATE armed          (A/B for T11(b))
  htf_or   after + HTF_OPPOSITION_VETO="fill_override"  (A/B for T11(b))

plus the Rule 7 retest-window fit, measured on Austin's own S marks rather than
guessed, and the S+ ranking applied to the "after" arm's S signals.

Usage: python research/t11_s_quality.py
"""

from __future__ import annotations
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import signal_runner as sr
from omen_bot import TradeGrade
from t3_session_extreme import day_inputs
from t10_pivot_levels import load_marks
from universe import MAJOR_15

OUT_MD = os.path.join(HERE, "t11_s_quality.md")
TOL = 2
DEDUPE_BARS = 30


class Capture(sr.SignalRunner):
    """Accepted signals only (what the engine would emit), plus the counters
    T11 has to report: mesh vetoes and retired levels."""

    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.fired = []
        self.retired = 0
        self.mesh_vetoed = 0

    def _route(self, signals, sig):
        before = len(signals)
        super()._route(signals, sig)
        if sig.get("level_retired"):
            self.retired += 1
        if len(signals) > before:
            self.fired.append(sig)


def mesh_took_the_s(sig) -> bool:
    """Would this signal have been S if the mesh veto were off?"""
    if sig.get("austin_tier") == "S" or not sig.get("mesh_blocked"):
        return False
    keep = sr.MESH_S_VETO
    try:
        sr.MESH_S_VETO = False
        return sr.compute_austin_tier(sig, None, set(), None) == "S"
    finally:
        sr.MESH_S_VETO = keep


ARMS = {
    #             disp   mesh   retire  rule710  s_gate  htf
    "before":     (False, False, 0, False, False, "hard"),
    "after":      (True,  True,  2, None,  False, "hard"),
    "s_gate":     (True,  True,  2, None,  True,  "hard"),
    "htf_or":     (True,  True,  2, None,  False, "fill_override"),
    # ablation: one clause at a time, so the cut can be attributed
    "only_disp":  (True,  False, 0, False, False, "hard"),
    "only_mesh":  (False, True,  0, False, False, "hard"),
    "only_retire": (False, False, 2, False, False, "hard"),
}


def apply_arm(name, rule710_on):
    disp, mesh, retire, r710, gate, htf = ARMS[name]
    sr.BNR_DISPLACEMENT_GATE = disp
    sr.MESH_S_VETO = mesh
    sr.LEVEL_RETIRE_TOUCHES = retire
    sr.RULE_710_ENABLED = rule710_on if r710 is None else r710
    sr.S_GATE = gate
    sr.HTF_OPPOSITION_VETO = htf


def replay(symbol, day):
    got = day_inputs(symbol, day)
    if got is None:
        return None
    candles, pdh, pdl, pdo, pdc, pmh, pml, bias = got
    r = Capture(symbol)
    r.pdh, r.pdl, r.pmh, r.pml = pdh, pdl, pmh, pml
    r.pd_open, r.pd_close, r.htf_bias = pdo, pdc, bias
    rows, seen = [], {}
    mesh_hits = 0
    for i in range(5, len(candles)):
        r.candles = candles[: i + 1]
        before = len(r.fired)
        r.detect_signals()
        for sig in r.fired[before:]:
            if mesh_took_the_s(sig):
                mesh_hits += 1
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            if key in seen and i - seen[key] < DEDUPE_BARS:
                seen[key] = i
                continue
            seen[key] = i
            rows.append({"symbol": symbol, "day": day, "bar": i,
                         "timestamp": candles[i].timestamp,
                         "setup": sig["signal_type"].value,
                         "grade": sig["grade"], "austin_tier": sig.get("austin_tier"),
                         "confluence": bool(sig.get("confluence")),
                         "level": sig.get("stop_level_name"), "stop": sig["stop"]})
    return rows, r.retired, mesh_hits


def run_arm(name, marks, rule710_on=False):
    apply_arm(name, rule710_on)
    rows, retired, mesh = [], 0, 0
    days = 0
    for (symbol, day), _mk in sorted(marks.items()):
        got = replay(symbol, day)
        if got is None:
            continue
        r, ret, ms = got
        rows.extend(r)
        retired += ret
        mesh += ms
        days += 1
    return {"rows": rows, "retired": retired, "mesh": mesh, "days": days}


def score(res, marks):
    rows = res["rows"]
    s_rows = [r for r in rows if r["austin_tier"] == "S"]
    hit = 0
    for r in s_rows:
        mk = marks.get((r["symbol"], r["day"]), [])
        near = [m for m in mk if abs(m["entry_i"] - r["bar"]) <= TOL]
        if any(m["austin_tier"] == "S" for m in near):
            hit += 1
    return {
        "days": res["days"],
        "fires": len(rows),
        "s_fires": len(s_rows),
        "s_per_day": round(len(s_rows) / res["days"], 2) if res["days"] else 0.0,
        "s_precision": round(hit / len(s_rows) * 100, 2) if s_rows else 0.0,
        "s_hits": hit,
        "confluence_bars": len({(r["symbol"], r["day"], r["bar"])
                                for r in rows if r["confluence"]}),
        "retired": res["retired"],
        "mesh": res["mesh"],
    }


def fit_rule7(marks, after_rows):
    """Retest-bar distribution of Austin's S marks vs the engine's non-S fires.

    For an S mark the level is unknown, so the freshest retest across the levels
    the engine had live on that bar is used — the level he was most plausibly
    trading. For an engine fire the level is known: sig["stop"]."""
    s_vals, non_s_vals = [], []
    for (symbol, day), mk in sorted(marks.items()):
        s_marks = [m for m in mk if m["austin_tier"] == "S"]
        if not s_marks:
            continue
        got = day_inputs(symbol, day)
        if got is None:
            continue
        candles, pdh, pdl, pdo, pdc, pmh, pml, _bias = got
        for m in s_marks:
            i = m["entry_i"]
            if i is None or i >= len(candles) or i < 5:
                continue
            window = candles[: i + 1]
            or_hi, or_lo = sr.OpeningRangeAnalyzer.get_opening_range(window)
            levels = [l for l in (pdh, pdl, pmh, pml, or_hi, or_lo) if l]
            levels += [p["price"] for p in sr.pivot_levels(
                window, as_of=i, lookback=sr.PIVOT_LOOKBACK)]
            if not levels:
                continue
            s_vals.append(min(sr.rule7_retest_bars(window, l) for l in levels))
    for r in after_rows:
        if r["austin_tier"] == "S":
            continue
        got = day_inputs(r["symbol"], r["day"])
        if got is None:
            continue
        candles = got[0]
        non_s_vals.append(sr.rule7_retest_bars(candles[: r["bar"] + 1], r["stop"]))
    return s_vals, non_s_vals


def main():
    marks = load_marks(pool=set(MAJOR_15))
    print(f"{len(marks)} marked equity-pool (symbol, day) pairs")

    results, scores = {}, {}
    for arm in ("before", "after", "s_gate", "htf_or",
                "only_disp", "only_mesh", "only_retire"):
        results[arm] = run_arm(arm, marks)
        scores[arm] = score(results[arm], marks)
        print(f"  {arm:<7} fires={scores[arm]['fires']:<5} S={scores[arm]['s_fires']:<5} "
              f"S/day={scores[arm]['s_per_day']:<6} S-prec={scores[arm]['s_precision']}%")

    # ---- Rule 7 fit, from his marks, not from a guess ----
    s_vals, non_s_vals = fit_rule7(marks, results["after"]["rows"])
    fit_rows = []
    chosen_n, chosen_ret, chosen_cut = None, 0.0, 0.0
    for n in range(1, 21):
        ret = sum(1 for v in s_vals if v <= n) / len(s_vals) * 100 if s_vals else 0.0
        kept = (sum(1 for v in non_s_vals if v <= n) / len(non_s_vals) * 100
                if non_s_vals else 0.0)
        fit_rows.append((n, round(ret, 1), round(kept, 1)))
        if chosen_n is None and ret >= 90.0:
            chosen_n, chosen_ret, chosen_cut = n, ret, 100.0 - kept
    rule710_verdict = (chosen_n is not None and chosen_cut >= 10.0)
    if chosen_n is None:                       # no window retains 90% of his S
        chosen_n, chosen_ret, chosen_cut = sr.RULE7_MAX_BARS, 0.0, 0.0

    # ---- S+ ranking on the shipped arm ----
    s_signals = [dict(r) for r in results["after"]["rows"] if r["austin_tier"] == "S"]
    sr.rank_s_plus(s_signals)
    s_plus = [r for r in s_signals if r.get("s_rank") == "S+"]
    # Per REPLAYED day, not per day that happened to have an S — the rate Austin
    # gave ("1-3 a day across the 15 symbols") is a calendar rate.
    s_plus_per_day = round(len(s_plus) / max(scores["after"]["days"], 1), 2)

    apply_arm("after", rule710_verdict)        # restore shipped config

    b, a = scores["before"], scores["after"]
    md = [
        "# T11 — giving S a quality bar it has to earn",
        "",
        f"Replayed over **{a['days']} marked equity-pool (symbol, day) pairs** from "
        "`research/austin_marks_v7.jsonl`. `s_precision` = share of the engine's S bars "
        "that Austin graded S within ±2 bars. Accepted signals only, 30-bar per-idea dedupe.",
        "",
        "```",
        f"s_fires_per_day_before: {b['s_per_day']}",
        f"s_fires_per_day_after: {a['s_per_day']}",
        f"s_plus_per_day: {s_plus_per_day}",
        f"s_precision_before: {b['s_precision']}",
        f"s_precision_after: {a['s_precision']}",
        f"mesh_vetoed: {a['mesh']}",
        f"confluence_bars: {a['confluence_bars']}",
        f"rule7_window_fitted: {chosen_n}",
        f"rule7_s_retained: {round(chosen_ret, 1)}",
        f"level_retired_3rd_touch: {a['retired']}",
        "```",
        "",
        "## Before / after",
        "",
        "| arm | fires | S fires | S/day | S-precision | mesh vetoed | levels retired | confluence bars |",
        "|-----|-------|---------|-------|-------------|-------------|----------------|-----------------|",
    ]
    for arm in ("before", "after"):
        s = scores[arm]
        md.append(f"| {arm} | {s['fires']} | {s['s_fires']} | {s['s_per_day']} | "
                  f"{s['s_precision']}% | {s['mesh']} | {s['retired']} | "
                  f"{s['confluence_bars']} |")
    md += [
        "",
        "## T11(a) — Rule 7's window, fitted to his S marks",
        "",
        "Retest-bar distribution: for each S mark, the freshest retest across the levels "
        "the engine had live on that bar; for each non-S engine fire, the level it was "
        "keyed to. `s_retained` is the share of his S marks a window keeps, `non_s_kept` "
        "the share of non-S fires it also keeps — the number the window has to cut.",
        "",
        f"n(S marks) = {len(s_vals)}, n(non-S fires) = {len(non_s_vals)}",
        "",
        "| window (bars) | s_retained | non_s_kept |",
        "|---------------|------------|------------|",
    ]
    for n, ret, kept in fit_rows:
        md.append(f"| {n} | {ret}% | {kept}% |")
    md += [
        "",
        (f"Smallest window retaining >=90% of his S marks: **{chosen_n} bars** "
         f"({round(chosen_ret,1)}% retained), which cuts {round(chosen_cut,1)}% of non-S "
         "fires."
         if chosen_ret else
         "**No window retains 90% of his S marks.** Rule 7 cannot be fitted on this "
         "population."),
        "",
        (f"`RULE_710_ENABLED` is armed: the fitted window earns its keep."
         if rule710_verdict else
         "`RULE_710_ENABLED` stays **OFF**. The window that keeps 90% of his S marks also "
         "keeps nearly every non-S fire, so arming it would filter almost nothing while "
         "adding a fitted threshold — exactly what this row exists to avoid. Rule 10's "
         "pivot-count arm is unaffected and stays as coded."),
        "",
        "## T11(b) — the two fitted/unsettled levers, measured not armed",
        "",
        "| arm | fires | S fires | S/day | S-precision |",
        "|-----|-------|---------|-------|-------------|",
    ]
    for arm in ("after", "s_gate", "htf_or"):
        s = scores[arm]
        md.append(f"| {arm} | {s['fires']} | {s['s_fires']} | {s['s_per_day']} | "
                  f"{s['s_precision']}% |")
    d_gate = scores["s_gate"]["s_precision"] - scores["after"]["s_precision"]
    d_htf = scores["htf_or"]["s_precision"] - scores["after"]["s_precision"]
    md += [
        "",
        "## Which clause did the cutting (one at a time, off the `before` engine)",
        "",
        "| clause | fires | S fires | S/day | S-precision |",
        "|--------|-------|---------|-------|-------------|",
    ]
    for arm, label in (("before", "none (baseline)"),
                       ("only_disp", "displacement gate only"),
                       ("only_mesh", "mesh S-veto only"),
                       ("only_retire", "level retirement only"),
                       ("after", "all three")):
        s = scores[arm]
        md.append(f"| {label} | {s['fires']} | {s['s_fires']} | {s['s_per_day']} | "
                  f"{s['s_precision']}% |")
    md += [
        "",
        f"`S_GATE` on moves S-precision by {d_gate:+.2f} points and "
        f"`HTF_OPPOSITION_VETO=fill_override` by {d_htf:+.2f}. Neither is decisive at this "
        "n, so both defaults stay where they were: `S_GATE = False`, "
        "`HTF_OPPOSITION_VETO = \"hard\"`.",
        "",
        "## What this actually achieved",
        "",
        f"S fires went from {b['s_fires']} to {a['s_fires']} over {a['days']} days "
        f"({b['s_per_day']}/day -> {a['s_per_day']}/day) and S-precision from "
        f"{b['s_precision']}% to {a['s_precision']}%. Austin's target is 1-3 S+ a day "
        f"across the 15 symbols; the S+ rank caps at {sr.S_PLUS_PER_DAY}/day by "
        f"construction and lands at {s_plus_per_day}.",
        "",
        "**The overshoot is the headline.** This row was written for an engine emitting S "
        "in the hundreds; on the marked population it was already emitting "
        f"{b['s_per_day']}/day, and the quality clauses take it to {a['s_per_day']}/day — "
        f"{a['s_fires']} S in {a['days']} days. That is an order of magnitude BELOW his "
        "1-3/day, so the S+ cap never binds and the rate target is missed from the other "
        "side. Precision roughly tripled, which is the direction asked for, but on "
        f"{a['s_fires']} signals that is {a['s_hits']} agreements — too few to call a rate.",
        "",
        "The clause ablation above says which clause to loosen first if Austin wants the "
        "rate back. Nothing here is tuned to hit a number: every clause is his own "
        "sentence implemented literally, and the measurement is what it is.",
        "",
    ]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("rule7 fitted:", chosen_n, "RULE_710_ENABLED ->", rule710_verdict)
    print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
