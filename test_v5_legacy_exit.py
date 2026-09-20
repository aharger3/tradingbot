"""test_v5_legacy_exit.py -- omen-v5-legacy-exit-test (2026-09-20).

The legacy g88 arm (live_scanner._emit_signal's alert_only branch, see
_alpaca_submit_entry's `legacy` extra) has no marking loop revisiting it --
flatten_legacy() at MANAGE_END is the only code that ever closes one. This
test is the nightly check that promise held: every legacy entry that
actually filled has a matching session_end close/cancel row in the same
ledger. It does NOT touch signal_runner.py or place any order -- it only
reads journal/alpaca-paper.jsonl.

Run: `python -m pytest test_v5_legacy_exit.py -q`
"""
from __future__ import annotations

import json
from pathlib import Path

LEDGER = Path(__file__).parent / "journal" / "alpaca-paper.jsonl"


def _read_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def test_every_filled_legacy_entry_has_a_close_or_cancel():
    rows = _read_ledger(LEDGER)

    filled_legacy_entries = [
        r for r in rows
        if r.get("event") == "entry" and r.get("arm") == "engine"
        and r.get("legacy") is True and r.get("status") == "filled"
    ]

    if not filled_legacy_entries:
        # Nothing filled on the legacy arm yet -- nothing to check.
        assert True
        return

    # session_end rows (flatten_legacy's own output) key off the same
    # symbol+ts the matching entry was logged under (see live_scanner.py's
    # flatten_legacy: `row["ts"] = rec.get("ts")`, `row["symbol"] =
    # rec.get("symbol")`), not the entry's broker_order_id -- a flatten
    # submits a brand-new MARKET order with its own id.
    closed = {
        (r.get("symbol"), r.get("ts"))
        for r in rows
        if r.get("event") == "session_end" and r.get("legacy") is True
        and r.get("action") in ("cancel", "flatten")
    }

    missing = [
        (e.get("symbol"), e.get("ts")) for e in filled_legacy_entries
        if (e.get("symbol"), e.get("ts")) not in closed
    ]
    assert not missing, (
        f"filled legacy entries with no session_end close/cancel: {missing}")


if __name__ == "__main__":
    test_every_filled_legacy_entry_has_a_close_or_cancel()
    print("PASS: every filled legacy entry has a matching close/cancel (or none are filled yet)")
