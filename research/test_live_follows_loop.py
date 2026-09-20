"""OMEN 10.0 V4: the live lane must always carry the loop's shipped defaults.

research/tape/cycles.md is the loop's ledger of every gate it has run. Every
row that is still `hold` must load with its off/default value; a row that
turns `ship` must load with its shipped value (as of 2026-09-06 all five
rows, including DAY_POLICY since L5's revert 58c00a7b, read `hold`). This
test reads
research/tape/cycles.md itself (not a hardcoded copy of it) so a future cycle
that ships a new flag fails this test until live_scanner.py / signal_runner.py
are updated to match -- the live lane can never silently drift from the loop.

Run directly (no pytest needed): python research/test_live_follows_loop.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CYCLES_MD = ROOT / "research" / "tape" / "cycles.md"
SHIPPED_FLAGS_JSON = ROOT / "research" / "tape" / "shipped_flags.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.shipped_flags import latest_by_flag  # noqa: E402

# Every flag the loop has gated so far, and how to read its live-lane value.
# (flag name -> env var read by signal_runner.py, which live_scanner.py
# imports at module-import time -- see the imports around line 158 there.)
FLAG_ENV = {
    "MIN_PT1_R": "MIN_PT1_R",
    "RULE84_DECIDED": "RULE84_DECIDED",
    "OCR_RETEST_DISPLACEMENT": "OCR_RETEST_DISPLACEMENT",
    "TREND_DEF": "TREND_DEF",
    "DAY_POLICY": "DAY_POLICY",
    "HODLOD_DEF": "HODLOD_DEF",
    "RETEST_REQUIRED": "RETEST_REQUIRED",
    "BNR_DISPLACEMENT_GATE": "BNR_DISPLACEMENT_GATE",
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
    # HODLOD_DEF is also string-valued (signal_runner.py: os.getenv("HODLOD_DEF",
    # "off")). cycles.md 2026-09-14 held "prior_bar", so "off" is still the
    # live default.
    "HODLOD_DEF": "off",
    # RETEST_REQUIRED already defaults ON ("1", g93 2026-09-02) -- unlike the
    # other booleans here, its "hold" value (cycles.md 2026-09-14: holding
    # "take the first break, no retest wait") is the prior default of "1",
    # not "0".
    "RETEST_REQUIRED": "1",
    "BNR_DISPLACEMENT_GATE": "1",
}

DAY_POLICY_SHIP_VALUE = "3fires_stop_win_or_2loss"
HODLOD_DEF_SHIP_VALUE = "prior_bar"


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


def _shipped_adopt_map() -> dict:
    """flag -> latest research/tape/shipped_flags.json entry. Austin's
    2026-09-20 card ("Adopt shipped flags into the PAPER engine
    automatically -- only when $/day improves AND green months hold") made
    adoption STRICTER than cycles.md's own ship gate (research/shipped_flags.py
    docstring): a row can read `ship` in cycles.md while shipped_flags.json
    records adopt:False for it (worse $/day under the stricter rule), and the
    live lane must keep that row at its hold/off value -- never at the
    shipped value -- until it actually adopts. Missing/unparseable file
    returns {} (no shipped row overrides anything), matching
    shipped_flags.load_and_apply()'s own never-raise contract."""
    if not SHIPPED_FLAGS_JSON.exists():
        return {}
    try:
        entries = json.loads(SHIPPED_FLAGS_JSON.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(entries, list):
        return {}
    return latest_by_flag(entries)


def expected_env_value(flag: str, decision: str) -> str:
    if decision == "ship":
        shipped = _shipped_adopt_map().get(flag)
        if shipped is not None and shipped.get("adopt") is False:
            # Shipped under cycles.md's looser gate but rejected by the
            # stricter auto-adopt rule -- the live paper engine never got
            # this flag, so it must still be checked against its hold value.
            decision = "hold"
    if flag == "DAY_POLICY":
        # DAY_POLICY's value is a string, not an on/off switch -- follow
        # the tape's decision like every other flag: "ship" carries the
        # shipped policy string, "hold" carries the prior default.
        return DAY_POLICY_SHIP_VALUE if decision == "ship" else OFF_VALUES[flag]
    if flag == "HODLOD_DEF":
        return HODLOD_DEF_SHIP_VALUE if decision == "ship" else OFF_VALUES[flag]
    if decision == "ship":
        return "1"
    return OFF_VALUES[flag]


_VALUE_MARKER = "OMEN_FLAG_VALUE="


def read_live_value(flag: str) -> str:
    """Import live_scanner in a fresh subprocess (it has side effects at
    import time -- e.g. its own "adopted flags: ..." startup line from
    research/shipped_flags.load_and_apply()) and read the flag's runtime
    value back. No env= is passed, so the subprocess inherits the parent's
    full environment on purpose -- that inheritance is what lets this test
    catch env-based drift; it is not isolation. The value is printed behind
    a marker prefix so import-time stdout noise can never be mistaken for
    the flag's value."""
    code = (
        "import os, sys; sys.path.insert(0, r'%s'); "
        "import live_scanner as ls; "
        "import signal_runner as sr; "
        "v = getattr(ls, '_LIVE_%s', None) if hasattr(ls, '_LIVE_%s') "
        "else getattr(sr, '%s'); "
        "print('%s' + str(v))"
    ) % (str(ROOT), flag, flag, flag, _VALUE_MARKER)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        "importing live_scanner failed:\n%s" % result.stderr[-4000:])
    marked = [line for line in result.stdout.splitlines()
              if line.startswith(_VALUE_MARKER)]
    assert marked, (
        "read_live_value(%r): no %r line in subprocess stdout -- "
        "live_scanner/signal_runner import side effects changed:\n%s"
        % (flag, _VALUE_MARKER, result.stdout))
    return marked[-1][len(_VALUE_MARKER):].strip()


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
