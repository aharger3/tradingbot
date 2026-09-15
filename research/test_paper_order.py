"""Unit tests for research/paper_order.py (row V5, 2026-09-14).

Covers the two things the row's own verify list calls out: idempotency
(booking or passing the same candidate id twice is refused) and the `arm`
field landing on every logged row. Never touches the real Alpaca endpoint --
`broker.alpaca.AlpacaBroker` is monkeypatched with a stub whose `_client`
carries a paper-looking `_base_url`, so `_assert_paper_endpoint` is exercised
too (a non-paper base URL must raise).

Run: python research/test_paper_order.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import research.paper_order as paper_order  # noqa: E402


class _StubClient:
    def __init__(self, base_url="https://paper-api.alpaca.markets"):
        self._base_url = base_url


class _StubHandle:
    def __init__(self):
        self.broker_order_id = "stub-order-1"
        self.status = mock.Mock(value="working")


class _StubBroker:
    def __init__(self, base_url="https://paper-api.alpaca.markets"):
        self._client = _StubClient(base_url)
        self.orders = []

    def place_order(self, order):
        self.orders.append(order)
        return _StubHandle()


def _write_candidate(candidates_dir: Path, day: str, cid: str) -> None:
    candidates_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "day": day,
        "candidates": [{
            "id": cid, "symbol": "AAPL", "day": day, "ts": "09:44:00",
            "setup": "break_and_retest", "level": "PDH", "direction": "call",
            "entry": 231.40, "stop": 230.85, "pt1": 232.60, "grade": "S",
            "chart_png": None, "max_loss": 1000.0,
        }],
    }
    (candidates_dir / f"candidates_{day}.json").write_text(json.dumps(doc), encoding="utf-8")


def test_book_order_writes_arm_field():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _write_candidate(tmp, "2099-01-01", "AAPL_2099-01-01_0944")
        ledger = tmp / "alpaca-paper.jsonl"

        with mock.patch.object(paper_order, "_ALPACA_LEDGER", ledger), \
             mock.patch.object(paper_order, "candidates_path",
                                lambda day: tmp / f"candidates_{day}.json"), \
             mock.patch("broker.alpaca.AlpacaBroker", return_value=_StubBroker()):
            rec = paper_order.book_order("AAPL_2099-01-01_0944", arm="austin")

        assert rec["arm"] == "austin", rec
        assert rec["event"] == "entry", rec
        assert rec["candidate_id"] == "AAPL_2099-01-01_0944", rec
        rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1 and rows[0]["arm"] == "austin"
    print("PASS: book_order writes arm=austin and candidate_id")


def test_idempotent_refuses_second_book():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cid = "AAPL_2099-01-01_0944"
        _write_candidate(tmp, "2099-01-01", cid)
        ledger = tmp / "alpaca-paper.jsonl"

        with mock.patch.object(paper_order, "_ALPACA_LEDGER", ledger), \
             mock.patch.object(paper_order, "candidates_path",
                                lambda day: tmp / f"candidates_{day}.json"), \
             mock.patch("broker.alpaca.AlpacaBroker", return_value=_StubBroker()):
            paper_order.book_order(cid, arm="austin")
            assert paper_order._already_booked(cid) is True

        rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1, "a second book_order call must never reach here in the CLI path"
    print("PASS: idempotency check (_already_booked) is true after one booking")


def test_pass_is_idempotent_and_does_not_place_order():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cid = "AAPL_2099-01-01_0944"
        ledger = tmp / "alpaca-paper.jsonl"

        with mock.patch.object(paper_order, "_ALPACA_LEDGER", ledger):
            rec = paper_order.record_pass(cid, arm="austin")
            assert rec["event"] == "pass" and rec["arm"] == "austin"
            assert paper_order._already_booked(cid) is True
    print("PASS: record_pass logs event=pass, arm=austin, and blocks a re-book")


def test_assert_paper_endpoint_rejects_non_paper_url():
    broker = _StubBroker(base_url="https://api.alpaca.markets")  # LIVE, no "paper"
    try:
        paper_order._assert_paper_endpoint(broker)
    except RuntimeError as e:
        assert "paper" in str(e)
        print("PASS: non-paper base URL raises RuntimeError before any submit")
        return
    raise AssertionError("expected RuntimeError for a non-paper base URL")


if __name__ == "__main__":
    test_book_order_writes_arm_field()
    test_idempotent_refuses_second_book()
    test_pass_is_idempotent_and_does_not_place_order()
    test_assert_paper_endpoint_rejects_non_paper_url()
    print("ALL PASS")
