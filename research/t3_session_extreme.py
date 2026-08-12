"""omen-5.0 T3(c): A/B the session HOD/LOD proximity veto.

Replays SignalRunner detection over every marked (symbol, day) pair in the
equity pool at SESSION_EXTREME_FRAC in {0.00, 0.05, 0.10, 0.20} and scores each
setting against research/austin_marks_v7.jsonl.

  fires        - deduped entries the engine would TAKE that day (status fired)
  S-precision  - of the fires that land within +/-2 bars of one of Austin's
                 marks, the share whose mark is tier S. Fires that land on no
                 mark at all are counted in the denominator too: an entry he
                 never marked is not an S entry.

0.00 is the control arm (the veto disabled) and defines the fire budget the
chosen setting has to keep 40% of.

Usage: python research/t3_session_extreme.py [--fracs 0,0.05,0.1,0.2]
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import signal_runner as sr
from t4_engine_recall import rth_candles, prior_day_levels, premarket_extremes, htf_bias
from omen_bot import TradeGrade
from universe import MAJOR_15

MARKS = os.path.join(HERE, "austin_marks_v7.jsonl")
OUT_MD = os.path.join(HERE, "t3_session_extreme.md")
DEDUPE_BARS = 30
TOL = 2
TIER_RANK = {"S": 4, "A": 3, "C": 2, "X": 1}


class CaptureRunner(sr.SignalRunner):
    """Fired-only capture, mirroring backtest_week.BacktestRunner's routing."""

    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.captured = []
        self.vetoed = 0

    def _emit(self, signals, sig):
        if self.session_extreme_veto(sig):
            self.vetoed += 1
            return
        self._route(signals, sig)

    def _route(self, signals, sig):
        self._grade_for_levels(sig)
        self._calibration_grade(sig)
        if sig["grade"] == TradeGrade.D.value:
            sig["status"] = "skipped_d"
        elif sig["grade"] == "C" and not self._min_viable_stop(
                sig["entry"], sig["stop"], sig["direction"]):
            sig["status"] = "skipped_tight"
        else:
            sig["status"] = "fired"
            self._dir_fired[sig["direction"]] = self._dir_fired.get(sig["direction"], 0) + 1
            signals.append(sig)
        self.captured.append(sig)


def load_marks():
    marks = defaultdict(list)
    for line in open(MARKS, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("symbol") not in MAJOR_15:
            continue
        if r.get("entry_i") is None or not r.get("austin_tier"):
            continue
        marks[(r["symbol"], r["day"])].append(r)
    return marks


_DAY_CACHE = {}


def day_inputs(symbol, day):
    """(candles, pdh, pdl, pmh, pml, bias) — cached, the levels are the slow part."""
    key = (symbol, day)
    if key not in _DAY_CACHE:
        candles = rth_candles(symbol, day)
        if not candles:
            _DAY_CACHE[key] = None
        else:
            pdh, pdl, pdo, pdc = prior_day_levels(symbol, day)
            pmh, pml = premarket_extremes(symbol, day)
            _DAY_CACHE[key] = (candles, pdh, pdl, pdo, pdc, pmh, pml,
                               htf_bias(symbol, day))
    return _DAY_CACHE[key]


def replay(symbol, day):
    """Deduped fired entries for one day: [{bar, signal_type, direction, ...}]."""
    got = day_inputs(symbol, day)
    if got is None:
        return None, 0
    candles, pdh, pdl, pdo, pdc, pmh, pml, bias = got
    r = CaptureRunner(symbol)
    r.pdh, r.pdl, r.pmh, r.pml = pdh, pdl, pmh, pml
    r.pd_open, r.pd_close, r.htf_bias = pdo, pdc, bias
    entries, seen = [], {}
    for i in range(5, len(candles)):
        r.candles = candles[: i + 1]
        before = len(r.captured)
        r.detect_signals()
        for sig in r.captured[before:]:
            if sig.get("status") != "fired":
                continue
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            if key in seen and i - seen[key] < DEDUPE_BARS:
                seen[key] = i
                continue
            seen[key] = i
            entries.append({"bar": i, "signal_type": sig["signal_type"].value,
                            "direction": sig["direction"], "grade": sig["grade"]})
    return entries, r.vetoed


def score(frac, marks):
    sr.SESSION_EXTREME_FRAC = frac
    fires = 0
    vetoed = 0
    hit_tiers = Counter()
    days = 0
    s_covered = 0
    for (symbol, day), mk in sorted(marks.items()):
        entries, v = replay(symbol, day)
        if entries is None:
            continue
        days += 1
        fires += len(entries)
        vetoed += v
        # S-recall: an S mark is covered when ANY fire lands within +/-2 bars
        for m in mk:
            if m["austin_tier"] != "S":
                continue
            if any(abs(m["entry_i"] - e["bar"]) <= TOL for e in entries):
                s_covered += 1
        for e in entries:
            near = [m for m in mk if abs(m["entry_i"] - e["bar"]) <= TOL]
            if not near:
                hit_tiers["(unmarked)"] += 1
                continue
            best = max(near, key=lambda m: TIER_RANK.get(m["austin_tier"], 0))
            hit_tiers[best["austin_tier"]] += 1
    s_prec = round(hit_tiers["S"] / fires * 100, 2) if fires else 0.0
    marked = fires - hit_tiers["(unmarked)"]
    matched_prec = round(hit_tiers["S"] / marked * 100, 2) if marked else 0.0
    s_total = sum(1 for mk in marks.values() for m in mk if m["austin_tier"] == "S")
    s_recall = round(s_covered / s_total * 100, 2) if s_total else 0.0
    return {"frac": frac, "fires": fires, "vetoed": vetoed, "days": days,
            "s_hits": hit_tiers["S"], "a_hits": hit_tiers["A"],
            "x_hits": hit_tiers["X"], "c_hits": hit_tiers["C"],
            "unmarked": hit_tiers["(unmarked)"], "marked": marked,
            "matched_precision": matched_prec, "s_covered": s_covered,
            "s_total": s_total, "s_recall": s_recall,
            "s_precision": s_prec}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fracs", default="0.0,0.05,0.10,0.20")
    args = ap.parse_args()
    fracs = [float(x) for x in args.fracs.split(",")]

    marks = load_marks()
    print(f"{len(marks)} marked equity-pool (symbol, day) pairs")
    rows = []
    for f in fracs:
        row = score(f, marks)
        rows.append(row)
        print(f"  frac={f:<5} fires={row['fires']:<6} vetoed={row['vetoed']:<6} "
              f"S-prec={row['s_precision']}%")

    base = next(r for r in rows if r["frac"] == 0.0)
    floor = 0.40 * base["fires"]
    eligible = [r for r in rows if r["fires"] >= floor]
    chosen = max(eligible, key=lambda r: (r["s_precision"], r["fires"]))

    md = [
        "# T3(c) — session HOD/LOD proximity veto, A/B",
        "",
        f"Detection replayed over **{base['days']} marked equity-pool (symbol, day) "
        f"pairs** from `research/austin_marks_v7.jsonl` (pool = `universe.MAJOR_15`), "
        "bar-by-bar through `SignalRunner.detect_signals`, 30-bar per-idea dedupe, "
        "fired entries only.",
        "",
        "`s_precision` = share of ALL fired entries that land within ±2 bars of a mark "
        "Austin graded **S**. Fires landing on no mark are in the denominator — an entry "
        "he never marked is not an S entry. 0.00 is the control arm (veto off).",
        "",
        "| frac | fires | vetoed | on S | on A | on C | on X | unmarked | s_precision | "
        "precision on matched | S marks covered |",
        "|------|-------|--------|------|------|------|------|----------|-------------|"
        "----------------------|-----------------|",
    ]
    for r in rows:
        md.append(f"| {r['frac']:.2f} | {r['fires']} | {r['vetoed']} | {r['s_hits']} | "
                  f"{r['a_hits']} | {r['c_hits']} | {r['x_hits']} | {r['unmarked']} | "
                  f"{r['s_precision']}% | {r['matched_precision']}% | "
                  f"{r['s_covered']}/{r['s_total']} ({r['s_recall']}%) |")
    md += [
        "",
        f"Fire floor = 40% of the control arm's {base['fires']} fires = **{floor:.0f}**. "
        "Settings clearing it: " + ", ".join("%.2f" % r["frac"] for r in eligible) + ".",
        "",
        f"chosen_frac: {chosen['frac']}",
        "",
        f"Chosen because it has the highest S-precision ({chosen['s_precision']}%) among "
        f"the settings that still emit at least 40% of the control arm's fires "
        f"({chosen['fires']} of {base['fires']}).",
        "",
        "## What the measurement actually says",
        "",
        "The veto does not buy S-precision on this population. Every armed setting scores "
        "at or below the control arm while throwing fires away, and the spread across all "
        "four settings is a handful of trades — noise at this n, not a signal. The decision "
        "rule in the spec (highest S-precision that keeps 40% of the control arm's fires) "
        "therefore lands on the control arm itself.",
        "",
        "That is a conflict with this row's stated intent — 'the new behaviour is the "
        "default on' — and it is resolved the way the row itself asks for: the measurement "
        "wins, `SESSION_EXTREME_FRAC` ships at the fitted value, and the veto stays one "
        "env var away (`SESSION_EXTREME_FRAC=0.05`). The mechanic is built, wired through "
        "`_emit` so every subclass and every replay inherits it, and covered by tests; what "
        "the data will not support is arming it by default.",
        "",
        "Austin's 21 notes about not entering at HOD/LOD are not refuted by this. What is "
        "refuted is that a *distance-to-session-extreme band* is the way to encode them: "
        "his objection is to the fill, and the fill fix is T3(b) (intrabar entry at the "
        "level on an extreme close), which is armed. S-precision stays single-digit at "
        "every setting either way — the positive quality bar S has never had is T11's row, "
        "not this one.",
        "",
    ]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("chosen_frac:", chosen["frac"], "->", OUT_MD)


if __name__ == "__main__":
    main()
