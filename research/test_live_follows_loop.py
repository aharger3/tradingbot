"""OMEN 10.0 V4: the live lane must always carry the loop's shipped defaults.

research/tape/cycles.md is the loop's ledger of every gate it has run. Every
row that is still `hold` must load with its off/default value; the one row
that is `ship` (DAY_POLICY) must load with its shipped value. This test reads
research/tape/cycles.md itself (not a hardcoded copy of it) so a future cycle
that ships a new flag fails this test until live_scanner.py / signal_runner.py
are updated to match -- the live lane can never silently drift from the loop.

Run directly (no pytest needed): python research/test_live_follows_loop.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CYCLES_MD = ROOT / "research" / "tape" / "cycles.md"

# Every flag the loop has gated so far, and how to read its live-lane value.
# (flag name -> env var read by signal_runner.py, which live_scanner.py
# imports at module-import time -- see the imports around line 158 there.)
FLAG_ENV = {
    "MIN_PT1_R": "MIN_PT1_R",
    "RULE84_DECIDED": "RULE84_DECIDED",
    "OCR_RETEST_DISPLACEMENT": "OCR_RETEST_DISPLACEMENT",
    "TREND_DEF": "TREND_DEF",
    "DAY_POLICY": "DAY_POLICY",
}

OFF_VALUES = {
    "MIN_PT1_R": "0",
    "RULE84_DECIDED": "0",
    "OCR_RETEST_DISPLACEMENT": "0",
    "TREND_DEF": "off",
    # DAY_POLICY is a string-valued flag, not a boolean -- "first3" was the
    # prior default (signal_runner.py's comment above the DAY_POLICY line)
    # and is what a "hold" decision means for this flag.
    "DAY_POLICY": "first3",
}

DAY_POLICY_SHIP_VALUE = "3fires_stop_win_or_2loss"


def parse_cycles_md(text: str) -> dict:
    """Return {flag: decision} for the LAST row of each flag in the table
    (a flag can appear more than once across cycles; the most recent row
    wins, matching how loop_state.json's history is read elsewhere).

    Returns EVERY flag row found, including ones this test does not yet
    know how to check -- the caller must fail loudly on those rather than
    silently drop them, or a newly-shipped flag would pass this test by
    never being looked at."""
    decisions = {}
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("|---") or "flag" in line.lower() and "decision" in line.lower():
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        flag, decision = cells[2], cells[3]
        if not flag or flag == "n/a":
            continue
        decisions[flag] = decision
    return decisions


def expected_env_value(flag: str, decision: str) -> str:
    if flag == "DAY_POLICY":
        # DAY_POLICY's value is a string, not an on/off switch -- follow
        # the tape's decision like every other flag: "ship" carries the
        # shipped policy string, "hold" carries the prior default.
        return DAY_POLICY_SHIP_VALUE if decision == "ship" else OFF_VALUES[flag]
    if decision == "ship":
        return "1"
    return OFF_VALUES[flag]


def read_live_value(flag: str) -> str:
    """Import live_scanner in a fresh subprocess (it has side effects at
    import time) with a clean env and read the flag's runtime value back."""
    code = (
        "import os, sys; sys.path.insert(0, r'%s'); "
        "import live_scanner as ls; "
        "import signal_runner as sr; "
        "print(getattr(ls, '_LIVE_%s', None) if hasattr(ls, '_LIVE_%s') "
        "else getattr(sr, '%s'))"
    ) % (str(ROOT), flag, flag, flag)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        "importing live_scanner failed:\n%s" % result.stderr[-4000:])
    return result.stdout.strip()


def test_live_flags_match_cycles_md_shipped_set():
    assert CYCLES_MD.exists(), "research/tape/cycles.md is missing"
    decisions = parse_cycles_md(CYCLES_MD.read_text(encoding="utf-8"))
    assert decisions, "parsed zero flag rows out of cycles.md -- table format changed"

    unknown_flags = sorted(f for f in decisions if f not in FLAG_ENV)
    assert not unknown_flags, (
        "research/tape/cycles.md ships/holds flag(s) this test does not "
        "know how to check against the live lane -- add them to FLAG_ENV "
        "(and OFF_VALUES / expected_env_value if needed) before trusting "
        "this test again: %r" % unknown_flags
    )

    mismatches = []
    for flag, decision in decisions.items():
        want = expected_env_value(flag, decision)
        got = read_live_value(flag)
        # bool-flag values render as True/False in Python repr; normalize.
        got_norm = {"True": "1", "False": "0"}.get(got, got)
        try:
            numeric_match = float(got) == float(want)
        except ValueError:
            numeric_match = False
        if got_norm != want and got != want and not numeric_match:
            mismatches.append((flag, decision, want, got))

    assert not mismatches, (
        "live lane does not carry the loop's shipped defaults:\n" +
        "\n".join(
            f"  {flag}: cycles.md says {decision!r} (want {want!r}), "
            f"live_scanner has {got!r}"
            for flag, decision, want, got in mismatches
        )
    )


if __name__ == "__main__":
    test_live_flags_match_cycles_md_shipped_set()
    print("OK: live lane matches research/tape/cycles.md's shipped defaults.")
