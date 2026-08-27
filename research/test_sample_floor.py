"""G6/T5 -- does the shared sample floor actually mark thin rows?

universe.MIN_SAMPLE_N is the one floor every per-symbol/per-pool report
imports (research/p12_sample_floor.md settled the value at 20). This is not
a framework test -- plain asserts, exits non-zero on failure -- exercising
the real row-building code in research/t60_baseline.py rather than a
reimplementation of its marking logic:

  - a slice one trade below the floor must carry the low-n marker
  - a slice exactly at the floor must NOT carry it
  - marking is cosmetic only: the row's real n is still printed either way

    python research/test_sample_floor.py
"""
from __future__ import annotations
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from universe import MIN_SAMPLE_N  # noqa: E402
import research.t60_baseline as t60  # noqa: E402

MARK = "(low n)"


def _stats(n):
    return {"n": n, "mean_r": 1.0, "median_r": 1.0, "win_rate": 0.5,
            "worst": -1.25, "mcl": 1, "ann_dollars": 1000.0}


def main():
    thin = t60.row("THINSYM", _stats(MIN_SAMPLE_N - 1))
    fat = t60.row("FATSYM", _stats(MIN_SAMPLE_N))

    assert MARK in thin, (
        "a sub-threshold row (n=%d) was not marked: %r" % (MIN_SAMPLE_N - 1, thin))
    assert MARK not in fat, (
        "an at-threshold row (n=%d) was marked: %r" % (MIN_SAMPLE_N, fat))
    # marking is a presentation flag, not suppression -- the real n survives
    assert ("| %d |" % (MIN_SAMPLE_N - 1)) in thin, "sub-threshold row lost its real n"
    assert ("| %d |" % MIN_SAMPLE_N) in fat, "at-threshold row lost its real n"

    print("sample floor ok: n=%d marked %s, n=%d clean (MIN_SAMPLE_N=%d, universe.py)"
          % (MIN_SAMPLE_N - 1, MARK, MIN_SAMPLE_N, MIN_SAMPLE_N))


if __name__ == "__main__":
    main()
