"""w12_tight_stop.py -- W12: what the C-only tight-stop gate is about to inherit.

`signal_runner._route` runs the minimum-viable-stop check on ONE grade:

    if sig["grade"] != "C" or self._min_viable_stop(...):

so a signal is only ever tested for a too-tight stop when it is graded `C`.
That was a defensible calibration in the legacy ladder, where `C` meant
alert-only. It is about to stop being defensible: `_calibration_grade`'s
first-with-trend floor makes 1,000 of the 1,017 traded rows `B`, and the
2026-08-28 ladder deletes `B` and re-files those rows as S/A/C/X. 331 of them
land on `C` (research/w12_bug_sweep.md #2), and every one of them will meet a
gate it has never met, whose constants -- `STOP_RANGE_MULT = 0.75`, the 0.5%
risk floor, the $0.20 premium floor -- are three of the 33 that
`research/hallucination-audit.md` found Austin never stated.

This file prices that: it re-derives `_min_viable_stop` on the exact bar each
traded row was graded on and counts how many of the 1,017 would fail it.

Bars from `data_archive/` via `polygon_feed`, RTH, index 0 = the 09:30 bar --
the convention `backtest_2y.py` writes into `entry_i`. Nothing is fetched.

    python research/w12_tight_stop.py
"""
from __future__ import annotations

import collections
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polygon_feed as pf                                      # noqa: E402
import signal_runner as sr                                     # noqa: E402

BOOK = os.path.join(ROOT, "research", "g3_arm_ow1.json")
OUT = os.path.join(ROOT, "research", "_w12", "tight_stop.json")


def viable(entry, stop, bars, i):
    """`SignalRunner._min_viable_stop`, re-derived on plain bars.

    Kept as a transcription rather than a call so the row's own `entry_i` can
    stand in for `self.candles[-1]` -- the method reads `self.candles[-11:-1]`,
    which on the graded bar is bars[i-10:i]."""
    if entry == stop:
        return False
    risk = abs(entry - stop)
    recent = bars[max(0, i - 10):i]
    if recent:
        avg_range = sum(b["h"] - b["l"] for b in recent) / len(recent)
        if risk < sr.STOP_RANGE_MULT * avg_range:
            return False
    return (risk / entry) >= 0.005 or (risk * 0.5) >= 0.20


def sac(r):
    net = len(r.get("downgrades") or []) - (1 if r.get("confluence") == "yes" else 0)
    return "S" if net <= 0 else ("A" if net == 1 else ("C" if net == 2 else "X"))


def main():
    rows = [r for r in json.load(open(BOOK, encoding="utf-8"))["trades"]
            if r.get("traded")]
    cache, c = {}, collections.Counter()
    killed_r, kept_r = [], []
    by_new = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        key = (r["sym"], r["day"])
        if key not in cache:
            rth = pf.rth(pf.fetch_day(*key))
            cache[key] = [{"o": x.open, "h": x.high, "l": x.low,
                           "c": x.close, "v": x.volume} for x in rth]
        bars = cache[key]
        i = r["entry_i"]
        if i >= len(bars):
            c["skipped"] += 1
            continue
        ok = viable(r["entry"], r["stop"], bars, i)
        c["rows"] += 1
        c["would_pass" if ok else "would_fail"] += 1
        (kept_r if ok else killed_r).append(r["r"])
        g = sac(r)
        by_new[g][0 if ok else 1] += 1

    res = {"traded_rows": c["rows"], "skipped": c["skipped"],
           "pass": c["would_pass"], "fail": c["would_fail"],
           "failed_mean_r": round(statistics.fmean(killed_r), 4) if killed_r else None,
           "failed_median_r": round(statistics.median(killed_r), 4) if killed_r else None,
           "passed_mean_r": round(statistics.fmean(kept_r), 4) if kept_r else None,
           "passed_median_r": round(statistics.median(kept_r), 4) if kept_r else None,
           "by_new_ladder_grade": {k: {"pass": v[0], "fail": v[1]}
                                   for k, v in sorted(by_new.items())},
           "STOP_RANGE_MULT": sr.STOP_RANGE_MULT}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
