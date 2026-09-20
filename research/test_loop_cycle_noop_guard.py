"""research/test_loop_cycle_noop_guard.py -- the SCALE_PLAN no-op guard.

2026-09-20: loop_queue.json queued {"flag": "SCALE_PLAN", "on": "blind_2r"} --
matching every other queue entry's convention (env var name == the Python
flag name) and book_stamp.py's own FLAG_SOURCES entry for it. But
backtest_week.py actually reads OMEN_SCALE_PLAN (legacy fallback
OMEN_LADDER_MODE), never bare SCALE_PLAN -- SCALE_PLAN and OMEN_SSCORE_SIZING
are the only two flags in FLAG_SOURCES whose real env var carries the OMEN_
prefix. loop_cycle.py's build_book() dutifully exported `SCALE_PLAN=blind_2r`
into the subprocess env; nothing ever read it. The ON arm silently rebuilt
the OFF arm's book byte-for-byte (book_id d5ba41a41d65e1e4 both sides,
research/tape/book_SCALE_PLAN_{off,on}.json.gz) and cycles.md/nightly.md
recorded "ship" for a row that tested nothing. Root cause and evidence:
research/tape/scale_plan_noop.md.

stage_build()'s existing OFF-vs-baseline check cannot catch this class of bug
-- it only proves the OFF arm reproduces the baseline, never compares the ON
arm against the OFF arm. This test locks down the guard added to
stage_gate(): whenever the ON arm's book_id equals the OFF arm's, the
decision is forced to "noop" -- never "ship", never a
shipped_flags.record_ship() call, never an ntfy line claiming "shipped" --
regardless of what the $/day gate math says. A second case proves the guard
leaves a genuine ON-vs-OFF difference alone (real "ship", record_ship IS
called).

    python research/test_loop_cycle_noop_guard.py
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

from research import loop_cycle as lc  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    assert cond, f"{name}: {detail}"


def _run(fn) -> None:
    try:
        fn()
    except AssertionError as exc:
        FAILURES.append(str(exc))


class _Monkeypatch:
    """Same tiny stand-in as research/test_nightly_receipt.py -- this repo's
    tests run as plain scripts, not under pytest."""

    def __init__(self):
        self._restore = []

    def setattr(self, obj, name, value):
        self._restore.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def undo(self):
        for obj, name, old in reversed(self._restore):
            setattr(obj, name, old)


def _write_book(path: Path, book_id: str, rows: list) -> None:
    payload = {"meta": {"stamp": {"book_id": book_id, "git": {}, "flags": {}}},
               "trades": rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as gz:
        gz.write(json.dumps(payload))


def _row(day, et, pnl, sym="TSLA"):
    return {"day": day, "et": et, "sym": sym, "dir": "call", "entry": 100.0,
            "stop": 99.0, "pnl": pnl, "status": "fired", "traded": True}


BASE_CFG = {
    "unit": "every_signal",
    "halves_boundary": "2025-06-01",
    "gate": {"max_dollar_drop_pct": 5.0},
    "targets": {"dollars_per_day": 500, "avg_win_over_avg_loss": 2.0},
}


def test_identical_book_id_forces_noop() -> None:
    """ON and OFF books carry the SAME book_id (the SCALE_PLAN shape: the env
    var never reached the engine, so both arms built the same trades) even
    though the gate's own $/day/green-months numbers, read in isolation,
    would have passed as a clean 'ship'."""
    mp = _Monkeypatch()
    tmp = Path(tempfile.mkdtemp(prefix="loop_cycle_noop_"))
    try:
        mp.setattr(lc, "TAPE", tmp)
        mp.setattr(lc, "CYCLES_MD", tmp / "cycles.md")
        mp.setattr(lc, "STATE_JSON", tmp / "loop_state.json")
        pushed = []
        mp.setattr(lc.notify_ntfy, "push", lambda title, msg: pushed.append(msg))
        ship_calls = []
        mp.setattr(lc.shipped_flags, "record_ship",
                   lambda *a, **k: ship_calls.append((a, k)) or {"adopt": False})

        rows = [_row("2025-01-15", "09:45", 100.0), _row("2026-01-15", "09:45", 100.0)]
        _write_book(tmp / "book_SCALE_PLAN_off.json.gz", "SAMEID0000000001", rows)
        _write_book(tmp / "book_SCALE_PLAN_on.json.gz", "SAMEID0000000001", rows)

        out = lc.stage_gate(BASE_CFG, "SCALE_PLAN", "blind_2r",
                            "flat 2R target vs shipped ladder", dry_run=False)

        check("decision is noop", out["decision"] == "noop", out["decision"])
        check("record_ship not called", ship_calls == [], ship_calls)
        check("ntfy line flags no-op", pushed and "NO-OP" in pushed[0], pushed)
        check("ntfy line omits shipped", pushed and "shipped" not in pushed[0].split("--")[1].split(".")[0],
              pushed)

        cycles_text = (tmp / "cycles.md").read_text(encoding="utf-8")
        check("cycles.md carries noop, not ship",
              "| noop |" in cycles_text and "| ship |" not in cycles_text, cycles_text)

        state = json.loads((tmp / "loop_state.json").read_text(encoding="utf-8"))
        check("state history records noop", state["history"][-1]["decision"] == "noop",
              state["history"])
    finally:
        mp.undo()


def test_real_book_difference_still_ships() -> None:
    """A genuine ON-vs-OFF difference (distinct book_id, ON clearly better on
    both halves) must still record a real 'ship' and call record_ship -- the
    guard must not swallow legitimate cycles."""
    mp = _Monkeypatch()
    tmp = Path(tempfile.mkdtemp(prefix="loop_cycle_noop_"))
    try:
        mp.setattr(lc, "TAPE", tmp)
        mp.setattr(lc, "CYCLES_MD", tmp / "cycles.md")
        mp.setattr(lc, "STATE_JSON", tmp / "loop_state.json")
        # Small synthetic books: relax the sample-size floor so a 2-trade book
        # can clear half_verdict's "enough" check without a 30-trade/12-month
        # fixture.
        mp.setattr(lc, "MIN_TRADES", 1)
        mp.setattr(lc, "MIN_MONTHS", 1)
        pushed = []
        mp.setattr(lc.notify_ntfy, "push", lambda title, msg: pushed.append(msg))
        ship_calls = []
        mp.setattr(lc.shipped_flags, "record_ship",
                   lambda *a, **k: ship_calls.append((a, k)) or {"adopt": True})

        off_rows = [_row("2025-01-15", "09:45", -100.0), _row("2026-01-15", "09:45", -50.0)]
        on_rows = [_row("2025-01-15", "09:45", 100.0), _row("2026-01-15", "09:45", 50.0)]
        _write_book(tmp / "book_REAL_FLAG_off.json.gz", "OFFID0000000001", off_rows)
        _write_book(tmp / "book_REAL_FLAG_on.json.gz", "ONID00000000001", on_rows)

        out = lc.stage_gate(BASE_CFG, "REAL_FLAG", "1", "a real rule change", dry_run=False)

        check("decision is ship", out["decision"] == "ship", out["decision"])
        check("record_ship called once", len(ship_calls) == 1, ship_calls)
        check("ntfy line says shipped", pushed and "shipped" in pushed[0], pushed)
    finally:
        mp.undo()


def main() -> None:
    _run(test_identical_book_id_forces_noop)
    _run(test_real_book_difference_still_ships)

    if FAILURES:
        print("LOOP CYCLE NOOP GUARD TEST FAILED: %d check(s)" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        sys.exit(1)

    print("loop_cycle noop guard test ok: an ON arm whose book_id matches the "
          "OFF arm's is always recorded as noop (never ship, never adopted, "
          "never pushed as shipped), and a genuine difference still ships.")


if __name__ == "__main__":
    main()
