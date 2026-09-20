"""research/test_queue_env.py -- a loop_queue.json entry may carry extra env.

WHY. research/tape/loop_queue.json queued {"flag": "ENTRY_FLOOR_STOP", "on": "1"}
alone. backtest_week.py's ENTRY_FLOOR_STOP docstring says the flag is the
g88 option-A arm's stop widener, but option A is ONLY the arm measured at
+$256/day (research/g88_level_limit_retest_on.md) when ENTRY_FLOOR_STOP=1
rides ALONGSIDE ENTRY_FILL=limit_level -- entry_fill.py's shipped default
(ENTRY_FILL=close, entry_fill.py:82) never produces the resting-limit fill
whose risk collapses low enough for the floor to ever engage. A single-flag
queue entry could only ever measure a no-op.

THE FIX. loop_queue.json entries may now carry an optional "env" object:
extra env vars applied to research/loop_cycle.py's ON arm build ONLY -- the
OFF arm keeps the flag's code default and nothing else, so stage_build's
existing OFF-vs-baseline book_id proof is untouched. research/nightly_loop.py
threads it through as `--on-env '{"K": "V", ...}'` and stamps the combo into
the label that flows into cycles.md/nightly.md (`label [env: K=V]`), so the
referee sees the real combo a cycle tested even if the label's own prose
does not spell it out. A queue entry with no "env" key behaves exactly as
before (no --on-env flag, label untouched) -- single-flag entries still work.

This test locks down two things:
  1. research/loop_cycle.py::stage_build applies on_env to the ON arm's
     build_book() call and leaves the OFF arm's call untouched.
  2. research/nightly_loop.py::run_candidate passes a queue entry's "env"
     through as --on-env JSON and stamps it into the --label it sends
     loop_cycle.py -- and omits both when the entry carries no "env".

    python research/test_queue_env.py
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ROOT)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from research import loop_cycle as lc      # noqa: E402
from research import nightly_loop as nl    # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    assert cond, f"{name}: {detail}"


def _run(fn) -> None:
    try:
        fn()
    except AssertionError as exc:
        FAILURES.append(str(exc))


class _Monkeypatch:
    """Same tiny stand-in used across this repo's other loop_cycle/nightly_loop
    tests -- these run as plain scripts, not under pytest."""

    def __init__(self):
        self._restore = []

    def setattr(self, obj, name, value):
        self._restore.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def undo(self):
        for obj, name, old in reversed(self._restore):
            setattr(obj, name, old)


def _write_minimal_book(path: Path) -> None:
    payload = {"meta": {"stamp": {"book_id": "TESTID0000000001", "git": {}, "flags": {}}},
              "trades": []}
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as gz:
        gz.write(json.dumps(payload))


BASE_CFG = {"rebuild": {"script": "backtest_2y.py", "args": []}}


def test_stage_build_applies_on_env_to_on_arm_only() -> None:
    mp = _Monkeypatch()
    tmp = Path(tempfile.mkdtemp(prefix="loop_cycle_on_env_"))
    try:
        mp.setattr(lc, "TAPE", tmp)
        calls = []

        def fake_build_book(env_overrides, out_gz, rebuild_cfg, smoke):
            calls.append((dict(env_overrides), out_gz.name))
            _write_minimal_book(out_gz)
            return out_gz

        mp.setattr(lc, "build_book", fake_build_book)

        result = lc.stage_build(BASE_CFG, "ENTRY_FLOOR_STOP", "1", smoke=True,
                                on_env={"ENTRY_FILL": "limit_level"})

        check("build returns 'built'", result.get("decision") == "built", result)
        check("two builds happened", len(calls) == 2, calls)

        off_overrides, off_name = calls[0]
        on_overrides, on_name = calls[1]

        check("OFF arm built first", off_name == "book_ENTRY_FLOOR_STOP_off.json.gz", off_name)
        check("OFF arm only strips the flag", off_overrides == {"ENTRY_FLOOR_STOP": None},
              off_overrides)
        check("OFF arm never sees the extra env", "ENTRY_FILL" not in off_overrides,
              off_overrides)

        check("ON arm built second", on_name == "book_ENTRY_FLOOR_STOP_on.json.gz", on_name)
        check("ON arm carries the flag", on_overrides.get("ENTRY_FLOOR_STOP") == "1",
              on_overrides)
        check("ON arm carries the extra env", on_overrides.get("ENTRY_FILL") == "limit_level",
              on_overrides)
    finally:
        mp.undo()


def test_stage_build_with_no_on_env_is_unchanged() -> None:
    """A plain single-flag entry (no "env" key at all -> on_env=None/{}) must
    build the ON arm with exactly {flag: on_value}, same as before this row."""
    mp = _Monkeypatch()
    tmp = Path(tempfile.mkdtemp(prefix="loop_cycle_no_on_env_"))
    try:
        mp.setattr(lc, "TAPE", tmp)
        calls = []

        def fake_build_book(env_overrides, out_gz, rebuild_cfg, smoke):
            calls.append(dict(env_overrides))
            _write_minimal_book(out_gz)
            return out_gz

        mp.setattr(lc, "build_book", fake_build_book)

        lc.stage_build(BASE_CFG, "HTF_BIAS_GATE", "1", smoke=True)

        check("OFF overrides unchanged", calls[0] == {"HTF_BIAS_GATE": None}, calls[0])
        check("ON overrides unchanged", calls[1] == {"HTF_BIAS_GATE": "1"}, calls[1])
    finally:
        mp.undo()


def test_run_candidate_passes_env_and_stamps_label() -> None:
    mp = _Monkeypatch()
    try:
        captured_cmd = {}

        class FakeProc:
            stdout = "no json here -- only the cmd matters for this test\n"
            stderr = ""

        def fake_run(cmd, **kwargs):
            captured_cmd["cmd"] = cmd
            return FakeProc()

        mp.setattr(nl.subprocess, "run", fake_run)
        mp.setattr(nl, "cycles_md_row", lambda flag, today: None)

        nl.run_candidate({
            "flag": "ENTRY_FLOOR_STOP", "on": "1",
            "label": "g88 option A: limit at level + widen stop to floor (his pick 2026-09-20)",
            "env": {"ENTRY_FILL": "limit_level"},
        })

        cmd = captured_cmd["cmd"]
        check("--on-env is passed", "--on-env" in cmd, cmd)
        on_env_json = cmd[cmd.index("--on-env") + 1]
        check("--on-env carries the entry's env",
              json.loads(on_env_json) == {"ENTRY_FILL": "limit_level"}, on_env_json)

        label_arg = cmd[cmd.index("--label") + 1]
        check("label stamps the env combo", "[env: ENTRY_FILL=limit_level]" in label_arg,
              label_arg)
        check("label keeps the original prose",
              label_arg.startswith("g88 option A: limit at level + widen stop to floor"),
              label_arg)
    finally:
        mp.undo()


def test_run_candidate_without_env_is_unchanged() -> None:
    """A queue entry with no "env" key must build the exact same cmd as
    before this row -- no --on-env flag, label passed through untouched."""
    mp = _Monkeypatch()
    try:
        captured_cmd = {}

        class FakeProc:
            stdout = "no json here -- only the cmd matters for this test\n"
            stderr = ""

        def fake_run(cmd, **kwargs):
            captured_cmd["cmd"] = cmd
            return FakeProc()

        mp.setattr(nl.subprocess, "run", fake_run)
        mp.setattr(nl, "cycles_md_row", lambda flag, today: None)

        nl.run_candidate({"flag": "HTF_BIAS_GATE", "on": "1",
                          "label": "only trade with the daily-candle trend"})

        cmd = captured_cmd["cmd"]
        check("no --on-env flag", "--on-env" not in cmd, cmd)
        label_arg = cmd[cmd.index("--label") + 1]
        check("label untouched", label_arg == "only trade with the daily-candle trend", label_arg)
    finally:
        mp.undo()


def main() -> None:
    _run(test_stage_build_applies_on_env_to_on_arm_only)
    _run(test_stage_build_with_no_on_env_is_unchanged)
    _run(test_run_candidate_passes_env_and_stamps_label)
    _run(test_run_candidate_without_env_is_unchanged)

    if FAILURES:
        print("QUEUE ENV TEST FAILED: %d check(s)" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)

    print("queue env test ok: loop_cycle.stage_build applies a queue entry's "
          "\"env\" to the ON arm only (OFF arm untouched), and nightly_loop.run_candidate "
          "passes it through as --on-env and stamps it into the cycles.md/nightly.md label "
          "-- plain single-flag entries build and run exactly as before.")


if __name__ == "__main__":
    main()
