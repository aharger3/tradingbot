"""B3 B-02 -- `research/r3_downgrade_grader_ab.py` must not claim a third,
retired ladder mapping for `signal_runner.DOWNGRADE_TIER`.

Bug: the module's report prose said `DOWNGRADE_TIER` is `S -> A+`, and that
`_grade_pa` "can only ever emit `A+/B/C/X`". A+ was retired 2026-08-30
(signal_runner.py's own dated comment above `DOWNGRADE_TIER`); the mapping is
`S -> A`, `A -> B`, `C -> C`, and `_grade_pa`'s alphabet is `A/B/C/X`. The
stale prose is a THIRD, no-longer-real ladder living beside the two real ones
(`SAC_TIER`, `DOWNGRADE_TIER`), which is exactly what the row asks be deleted.

This does not touch signal_runner.py: `SAC_TIER` and `DOWNGRADE_TIER` are two
independently-flagged graders (`ENABLE_SAC_LADDER` vs `ENABLE_DOWNGRADE_GRADER`,
both OFF by default, never both active on one signal) with opposite, each
individually-documented and load-bearing reasons for their His-A mapping --
see signal_runner.py lines ~776-792 and ~898-909. Collapsing them into one
constant would change which live tier a real `_grade_trade` call can emit
under whichever flag is ever turned on, which is exactly the "changes
behaviour beyond the bug itself" case the row says not to ship; see
research/g182_bugs_fixed.md for the deferral.

    python research/test_g182_b02_ladder_prose.py
"""
from __future__ import annotations

import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import signal_runner as sr                                # noqa: E402

R3_TEXT = (pathlib.Path(HERE) / "r3_downgrade_grader_ab.py").read_text(encoding="utf-8")


def test_no_stale_a_plus_mapping_claim():
    assert "S -> A+" not in R3_TEXT, (
        "r3_downgrade_grader_ab.py still claims DOWNGRADE_TIER is `S -> A+`, "
        "a mapping that does not exist in signal_runner.py (A+ retired "
        "2026-08-30). Actual: %r" % sr.DOWNGRADE_TIER)
    assert "A+/B/C" not in R3_TEXT, (
        "r3_downgrade_grader_ab.py still claims the ON-arm alphabet includes "
        "A+, which _grade_pa cannot emit post-retirement.")


def test_prose_matches_the_real_ladder():
    assert sr.DOWNGRADE_TIER == {"S": "A", "A": "B", "C": "C"}, sr.DOWNGRADE_TIER
    assert "`S -> A`, `A -> B`, `C -> C`" in R3_TEXT, (
        "the stated ladder in r3_downgrade_grader_ab.py must read the real "
        "DOWNGRADE_TIER mapping verbatim")


if __name__ == "__main__":
    test_no_stale_a_plus_mapping_claim()
    test_prose_matches_the_real_ladder()
    print("OK: no stale third ladder mapping in r3_downgrade_grader_ab.py")
    sys.exit(0)
