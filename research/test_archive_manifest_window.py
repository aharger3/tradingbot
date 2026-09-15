"""research/test_archive_manifest_window.py -- OMEN 10.0 G0.

The manifest is window-scoped (research/build_archive_manifest.py): it hashes
only the sessions with start <= date <= end from research/tape/loop.json's
pinned window, so research/daily_fetch.py's routine appends AFTER the
pinned end date never trip backtest_2y.py's --manifest guard. Two checks,
against a temp copy of a tiny archive so nothing here touches the real
data_archive/:

  1. Mutate one IN-WINDOW bar -> check() reports a mismatch for that symbol.
  2. Append a POST-WINDOW session (dated after `end`) -> check() reports no
     problems at all -- the guard is blind to it by design.

    python research/test_archive_manifest_window.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research import build_archive_manifest as bam  # noqa: E402

FAILURES = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {label}")
    if not cond:
        FAILURES.append(label)


WINDOW_START = "2024-09-04"
WINDOW_END = "2026-09-04"
SYM = "AAPL"


def _write_bar(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


def _make_archive(root: Path):
    """One symbol, three in-window sessions plus one already past the
    pinned end (mimicking daily_fetch's legitimate append)."""
    d = root / SYM
    d.mkdir(parents=True)
    _write_bar(d / "2024-09-04.csv", "t,o,h,l,c,v\n1,1,1,1,1,1\n")
    _write_bar(d / "2025-06-02.csv", "t,o,h,l,c,v\n2,2,2,2,2,2\n")
    _write_bar(d / "2026-09-04.csv", "t,o,h,l,c,v\n3,3,3,3,3,3\n")
    _write_bar(d / "2026-09-11.csv", "t,o,h,l,c,v\n9,9,9,9,9,9\n")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="omen_g0_manifest_"))
    try:
        _make_archive(tmp)

        # Point build_archive_manifest at the temp archive and a fake
        # universe of just SYM, rather than the real data_archive/.
        saved_archive = bam.ARCHIVE
        saved_all_syms = bam.universe.ALL_SYMS
        bam.ARCHIVE = tmp
        bam.universe.ALL_SYMS = [SYM]
        try:
            manifest = {"generated": "test", "window": {"start": WINDOW_START, "end": WINDOW_END},
                        "symbols": bam.build(WINDOW_START, WINDOW_END)}
            manifest_path = tmp / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            check("manifest scoped in-window count excludes the post-window session",
                  manifest["symbols"][SYM]["sessions"] == 3)
            check("clean archive checks clean",
                  bam.check(str(manifest_path)) == [])

            # 1. Mutate one IN-WINDOW bar -> guard refuses.
            _write_bar(tmp / SYM / "2025-06-02.csv", "t,o,h,l,c,v\n2,2,2,2,999,2\n")
            problems = bam.check(str(manifest_path))
            check("mutating an in-window bar trips the guard",
                  len(problems) == 1 and SYM in problems[0])

            # restore, then re-verify clean before the append case
            _write_bar(tmp / SYM / "2025-06-02.csv", "t,o,h,l,c,v\n2,2,2,2,2,2\n")
            check("restoring the in-window bar checks clean again",
                  bam.check(str(manifest_path)) == [])

            # 2. Append a POST-WINDOW session -> guard passes (blind to it).
            _write_bar(tmp / SYM / "2026-09-12.csv", "t,o,h,l,c,v\n4,4,4,4,4,4\n")
            check("appending a post-window session does not trip the guard",
                  bam.check(str(manifest_path)) == [])
        finally:
            bam.ARCHIVE = saved_archive
            bam.universe.ALL_SYMS = saved_all_syms
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S):")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
