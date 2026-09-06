"""V4 referee: does research/test_live_follows_loop.py actually catch drift?

Builder commit 79d6f57f. This script does NOT trust the test's green run. It
asks three questions the test's own docstring makes claims about:

  A. Does the test fail when a live flag value drifts?           (must FAIL)
  B. Does the test fail when cycles.md ships a NEW flag the live
     lane does not carry?  (docstring: "a future cycle that ships
     a new flag fails this test until ... updated to match")     (must FAIL)
  C. Does the test fail when DAY_POLICY's decision flips away
     from ship (e.g. the L5 referee's refutation is written back
     into the tape)?                                             (must FAIL)

Run: python research/v4_referee.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import research.test_live_follows_loop as T  # noqa: E402

REAL = (ROOT / "research" / "tape" / "cycles.md").read_text(encoding="utf-8")


def a_value_drift() -> tuple[bool, str]:
    """Run the test in a subprocess with TREND_DEF drifted to '15m'."""
    env = dict(os.environ)
    env["TREND_DEF"] = "15m"
    r = subprocess.run([sys.executable, "research/test_live_follows_loop.py"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       env=env, timeout=180)
    caught = r.returncode != 0
    return caught, (r.stdout + r.stderr).strip()[-400:]


def b_new_shipped_flag() -> tuple[bool, str]:
    """A future cycle ships a brand-new flag the live lane never heard of."""
    text = REAL + ("| 2026-09-06 | a brand new rule | BRAND_NEW_FLAG | ship | "
                   "0 -> 0 | 11 -> 12 | pass | pass | 700 | a | b | s |\n")
    decisions = T.parse_cycles_md(text)
    caught = "BRAND_NEW_FLAG" in decisions
    return caught, f"parsed flags = {sorted(decisions)}"


def c_day_policy_unships() -> tuple[bool, str]:
    """cycles.md flips DAY_POLICY back to hold (the L5 referee refuted it).
    The test should then demand the OFF value, not the shipped string."""
    want = T.expected_env_value("DAY_POLICY", "hold")
    caught = want != "3fires_stop_win_or_2loss"
    return caught, f"expected_env_value('DAY_POLICY','hold') = {want!r}"


def main() -> int:
    results = []
    for name, fn in (("A value-drift", a_value_drift),
                     ("B new shipped flag", b_new_shipped_flag),
                     ("C DAY_POLICY un-ships", c_day_policy_unships)):
        caught, detail = fn()
        results.append((name, caught, detail))
        print(f"{'CAUGHT ' if caught else 'MISSED '} {name}: {detail}")
    missed = [n for n, c, _ in results if not c]
    print()
    print("MISSED:" if missed else "all three caught", ", ".join(missed))
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
