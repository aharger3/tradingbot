"""research/test_nightly_receipt.py -- nightly.md must show loop_cycle's real
verdict, not a silently-empty one.

2026-09-19: the first real OmenNightlyLoop run shipped BNR_DISPLACEMENT_GATE
(research/tape/cycles.md got the real row: ship, -52.0 -> -54.0, 11 -> 11) but
research/tape/nightly.md wrote "hold | - | - | - -> -" for the same cycle.

Root cause: research/loop_cycle.py prints its result as one pretty-printed
`json.dumps(out, indent=2)` block, and pretty-printing means every nested
dict inside it (before_whole, after_whole, h1, h2, ...) opens with its own
'{'. research/nightly_loop.py's old `parse_result()` anchored on
`stdout.rfind("{")` -- the LAST brace in the text, which sits inside one of
those nested dicts, not at the top of the block. Slicing from there produced
a truncated fragment missing "decision"/"before_whole"/"after_whole", so
`run_candidate()` fell through to its empty-receipt branch even though
loop_cycle.py's own `append_cycle_row()` had already written the correct row
to cycles.md moments earlier in the same process.

This test locks two things down:
  1. `parse_result()` recovers the full dict from a realistically nested,
     pretty-printed stdout blob (regression case for the bug above).
  2. `run_candidate()` end to end, with `subprocess.run` faked, writes a
     nightly.md line carrying the decision and both number pairs -- once
     from loop_cycle's own stdout, and once via the cycles.md fallback when
     that stdout can't be parsed at all.

    python research/test_nightly_receipt.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from research import nightly_loop as nl  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    assert cond, f"{name}: {detail}"


def _run(fn, *args) -> None:
    """Call a test function, catching check()'s AssertionError into FAILURES
    so main()'s direct-run summary still lists every failing test. Under
    pytest, fn is called directly instead (not through _run), so check()'s
    assert fails that test for real."""
    try:
        fn(*args)
    except AssertionError as exc:
        FAILURES.append(str(exc))


def fake_gate_stdout() -> str:
    """A realistic loop_cycle.py --stage all stdout: the "building OFF/ON
    arm" progress lines a real run prints to stdout too (build_book's own
    print), followed by the final pretty-printed gate dict -- nested dicts
    and all, exactly what tripped the rfind("{") bug."""
    out = {
        "decision": "ship", "flag": "BNR_DISPLACEMENT_GATE",
        "label": "drop the no-touch displacement gate on break-and-retest setups",
        "unit": "day", "cycle": 12, "consecutive_holds": 0, "target_met": False,
        "stop": False, "stop_reason": None,
        "before_whole": {"per_day": -52.0, "months_green": 11, "trades": 770},
        "after_whole": {"per_day": -54.0, "months_green": 11, "trades": 770},
        "before_h1": {"per_day": 9.0}, "after_h1": {"per_day": 9.0},
        "before_h2": {"per_day": -111.0}, "after_h2": {"per_day": -111.0},
        "h1": {"enough": True, "pass": True}, "h2": {"enough": True, "pass": True},
        "off_book": "research/tape/book_BNR_DISPLACEMENT_GATE_off.json.gz",
        "on_book": "research/tape/book_BNR_DISPLACEMENT_GATE_on.json.gz",
    }
    progress = ("building OFF arm (BNR_DISPLACEMENT_GATE left at its default) -> ...\n"
                "building ON arm (BNR_DISPLACEMENT_GATE=1) -> ...\n")
    return progress + json.dumps(out, indent=2, default=str) + "\n"


def test_parse_result_survives_nested_pretty_json() -> None:
    result = nl.parse_result(fake_gate_stdout())
    check("parse_result decision", result.get("decision") == "ship",
          repr(result.get("decision")))
    check("parse_result before_whole", result.get("before_whole", {}).get("per_day") == -52.0,
          repr(result.get("before_whole")))
    check("parse_result after_whole", result.get("after_whole", {}).get("per_day") == -54.0,
          repr(result.get("after_whole")))
    check("parse_result months_green before", result.get("before_whole", {}).get("months_green") == 11)
    check("parse_result months_green after", result.get("after_whole", {}).get("months_green") == 11)


def test_run_candidate_uses_real_loop_cycle_result(monkeypatch) -> None:
    class FakeProc:
        stdout = fake_gate_stdout()
        stderr = ""

    monkeypatch.setattr(nl.subprocess, "run", lambda *a, **k: FakeProc())
    monkeypatch.setattr(nl, "book_id_for", lambda p: "OFFID" if p and "off" in p else "ONID")

    line = nl.run_candidate({"flag": "BNR_DISPLACEMENT_GATE", "on": "1",
                             "label": "drop the no-touch displacement gate"})

    check("run_candidate decision", "| ship |" in line, line)
    check("run_candidate $/day pair", "-52.0 -> -54.0" in line, line)
    check("run_candidate green pair", "11 -> 11" in line, line)
    check("run_candidate book ids", "OFFID -> ONID" in line, line)


def test_run_candidate_falls_back_to_cycles_md(monkeypatch) -> None:
    """Even if loop_cycle.py's stdout is unparsable (a crash, a future format
    change, whatever) -- as long as append_cycle_row() already wrote the real
    verdict to cycles.md before that happened, the nightly receipt must still
    carry it rather than reporting an empty hold."""
    class FakeProc:
        stdout = "no json here, the subprocess died after cycles.md was written\n"
        stderr = "Traceback (most recent call last): ...\n"

    monkeypatch.setattr(nl.subprocess, "run", lambda *a, **k: FakeProc())
    monkeypatch.setattr(nl, "cycles_md_row", lambda flag, today: {
        "decision": "ship", "per_day": "-52.0 -> -54.0", "green": "11 -> 11",
        "off_book": "-", "on_book": "-",
    })

    line = nl.run_candidate({"flag": "BNR_DISPLACEMENT_GATE", "on": "1", "label": "l"})

    check("fallback decision", "| ship |" in line, line)
    check("fallback $/day pair", "-52.0 -> -54.0" in line, line)
    check("fallback green pair", "11 -> 11" in line, line)


class _Monkeypatch:
    """Tiny stand-in for pytest's monkeypatch fixture -- this repo's tests
    run as plain scripts (see test_universe_single_source.py), not under
    pytest."""

    def __init__(self):
        self._restore = []

    def setattr(self, obj, name, value):
        self._restore.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def undo(self):
        for obj, name, old in reversed(self._restore):
            setattr(obj, name, old)


def main() -> None:
    _run(test_parse_result_survives_nested_pretty_json)

    mp = _Monkeypatch()
    try:
        _run(test_run_candidate_uses_real_loop_cycle_result, mp)
    finally:
        mp.undo()

    mp = _Monkeypatch()
    try:
        _run(test_run_candidate_falls_back_to_cycles_md, mp)
    finally:
        mp.undo()

    if FAILURES:
        print("NIGHTLY RECEIPT TEST FAILED: %d check(s)" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)

    print("nightly receipt test ok: parse_result survives nested pretty JSON, "
          "run_candidate carries loop_cycle's real decision/$/day/green, and "
          "falls back to cycles.md when loop_cycle's stdout is unusable.")


if __name__ == "__main__":
    main()
