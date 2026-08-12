"""omen-5.0 T10: do pivot levels explain Austin's S marks the engine missed?

Replays detection over every marked (symbol, day) pair in research/austin_marks_v7.jsonl
twice — PIVOT_LEVELS off, then on — and scores:

  s_explained  an Austin S mark where the engine emits ANY signal (fired or
               filtered) within 2 bars of his marked entry
  pivot_fires_per_day  pivot-keyed signals per replayed day

A negative result is a real finding and is reported as one.

Usage: python research/t10_pivot_levels.py
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
from t3_session_extreme import day_inputs
from universe import MAJOR_15

MARKS = os.path.join(HERE, "austin_marks_v7.jsonl")
OUT_MD = os.path.join(HERE, "t10_pivot_levels.md")
TOL = 2


class Capture(sr.SignalRunner):
    """Every signal the engine produces, fired or filtered — detection, not routing."""

    def __init__(self, symbol):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.seen = []

    def _route(self, signals, sig):
        self.seen.append(sig)
        super()._route(signals, sig)


def load_marks(pool=None):
    out = defaultdict(list)
    for line in open(MARKS, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if pool and r.get("symbol") not in pool:
            continue
        if r.get("entry_i") is None or not r.get("austin_tier"):
            continue
        out[(r["symbol"], r["day"])].append(r)
    return out


def replay(symbol, day):
    """[(bar, level_kind, signal_type, stop_level_name)] for every signal produced."""
    got = day_inputs(symbol, day)
    if got is None:
        return None
    candles, pdh, pdl, pdo, pdc, pmh, pml, bias = got
    r = Capture(symbol)
    r.pdh, r.pdl, r.pmh, r.pml = pdh, pdl, pmh, pml
    r.pd_open, r.pd_close, r.htf_bias = pdo, pdc, bias
    out = []
    for i in range(5, len(candles)):
        r.candles = candles[: i + 1]
        before = len(r.seen)
        r.detect_signals()
        for sig in r.seen[before:]:
            out.append((i, sig.get("level_kind", "named"),
                        sig["signal_type"].value, sig.get("stop_level_name")))
    return out


def run(pivots_on, marks):
    sr.PIVOT_LEVELS = pivots_on
    explained = 0
    s_total = 0
    pivot_fires = 0
    days = 0
    per_mark = {}
    for (symbol, day), mk in sorted(marks.items()):
        sigs = replay(symbol, day)
        if sigs is None:
            continue
        days += 1
        pivot_fires += sum(1 for s in sigs if s[1] == "pivot")
        for m in mk:
            if m["austin_tier"] != "S":
                continue
            s_total += 1
            near = [s for s in sigs if abs(s[0] - m["entry_i"]) <= TOL]
            if near:
                explained += 1
                per_mark[m["id"]] = sorted({s[3] for s in near})
    return {"explained": explained, "s_total": s_total, "days": days,
            "pivot_fires": pivot_fires, "per_mark": per_mark}


def main():
    marks = load_marks(pool=set(MAJOR_15))
    print(f"{len(marks)} marked equity-pool (symbol, day) pairs")

    before = run(False, marks)
    print("pivots OFF:", before["explained"], "/", before["s_total"])
    after = run(True, marks)
    print("pivots ON :", after["explained"], "/", after["s_total"],
          "pivot signals:", after["pivot_fires"])

    newly = {k: v for k, v in after["per_mark"].items() if k not in before["per_mark"]}
    lost = {k: v for k, v in before["per_mark"].items() if k not in after["per_mark"]}
    ppd = round(after["pivot_fires"] / after["days"], 2) if after["days"] else 0.0

    verdict = ("POSITIVE" if after["explained"] > before["explained"]
               else "NEGATIVE — pivots explain no S mark the engine did not already reach")

    md = [
        "# T10 — pivot structure as a first-class level: before / after",
        "",
        f"Detection replayed over **{after['days']} marked equity-pool (symbol, day) "
        "pairs** from `research/austin_marks_v7.jsonl`, once with `PIVOT_LEVELS=0` and "
        "once with it on. `s_explained` = an Austin S mark with ANY engine signal (fired "
        "or filtered) within ±2 bars of his marked entry — detection, not routing.",
        "",
        "```",
        f"s_marks_total: {after['s_total']}",
        f"s_explained_before: {before['explained']}",
        f"s_explained_after: {after['explained']}",
        f"pivot_fires_per_day: {ppd}",
        "```",
        "",
        f"**Verdict: {verdict}.**",
        "",
    ]
    if newly:
        md += ["## S marks a pivot level now accounts for", "",
               "| mark | levels the engine now fires on |",
               "|------|--------------------------------|"]
        for k, v in sorted(newly.items()):
            md.append(f"| {k} | {', '.join(str(x) for x in v)} |")
        md.append("")
    else:
        md += ["No S mark moved from unexplained to explained. Pivot levels add "
               f"{ppd} signals a day, and every S mark they land on was already reached "
               "by a named level within the same ±2 bars.", ""]
    if lost:
        md += ["## S marks that stopped being explained", "",
               "Pivot levels are additive to detection, so a mark leaving this set means "
               "a routing interaction, not a lost level:", ""]
        for k, v in sorted(lost.items()):
            md.append(f"- {k} (was: {', '.join(str(x) for x in v)})")
        md.append("")
    md += [
        "## Reading this",
        "",
        "The gap this row was built to close is real in Austin's notes — 'pivot-structure "
        "break > level break', 'no clean break it just respect pivot structures', 'dont see "
        "any levels, unless some were forgot to be marked'. What the replay measures is "
        "narrower: whether a pivot level puts an engine SIGNAL within two bars of a mark "
        "that had none. Explaining a mark is necessary for agreement, not sufficient — a "
        "signal at the right bar with the wrong grade still disagrees with him, and that is "
        "T11's row.",
        "",
        f"Pivot levels are live: {after['pivot_fires']} pivot-keyed signals across "
        f"{after['days']} days ({ppd}/day) with `PIVOT_STRENGTH=2` and a "
        f"`PIVOT_LOOKBACK={sr.PIVOT_LOOKBACK}`-bar horizon. They are fed to "
        "break-and-retest exactly as named levels are, they cannot be seen before they "
        "complete (`usable_from = index + PIVOT_STRENGTH + 1`, asserted in "
        "`test_austin_tier.py`), and a pivot-keyed B&R carries `level_rank: 0` so T11 can "
        "read the ordering Austin asked for.",
        "",
    ]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("wrote", OUT_MD)


if __name__ == "__main__":
    main()
