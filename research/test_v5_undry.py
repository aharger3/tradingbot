"""research/test_v5_undry.py -- omen-v5-undry (2026-09-19).

Two checks, per the row's own verify line:

  1. `AlpacaBroker`'s real client (constructed from the real `.env`
     credentials, no order ever submitted) names the PAPER endpoint --
     never the live one. Construction alone makes no network call (the
     alpaca-py SDK's `TradingClient.__init__` only sets up a REST client
     object), so this is safe to run anywhere `.env` carries
     ALPACA_PAPER_KEY/SECRET.
  2. A synthetic legacy-grade (non-S) fire, run through
     `live_scanner._emit_signal`'s widened alert_only branch against a
     FakeBroker (no network, no real Alpaca import), produces a journal
     row with `dry: false` and `entry_rule: "g88"` -- never a live order,
     the submit is mocked throughout.

Run: `python research/test_v5_undry.py`
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from broker.base import (  # noqa: E402
    AccountSnapshot, BrokerInterface, Order, OrderHandle, OrderStatus, OrderType,
)
import live_scanner  # noqa: E402


def test_alpaca_broker_client_names_paper_endpoint():
    """No network call: TradingClient(paper=True) only sets up a REST
    client object and its base_url attribute. Never submits an order."""
    from broker.alpaca import AlpacaBroker

    broker = AlpacaBroker()
    base_url = str(getattr(broker._client, "_base_url", ""))
    assert "paper-api.alpaca.markets" in base_url.lower() or "paper" in base_url.lower(), (
        f"AlpacaBroker client base URL does not name the paper endpoint: {base_url!r}")
    assert "api.alpaca.markets" not in base_url.replace("paper-api.alpaca.markets", ""), (
        f"AlpacaBroker client base URL looks like the LIVE endpoint: {base_url!r}")
    print(f"PASS: AlpacaBroker client base URL is paper ({base_url!r})")


class _FakeBroker(BrokerInterface):
    """Records every place_order call; never touches the network. The
    submit is entirely mocked -- no real (even paper) order is placed by
    this test."""

    def __init__(self, equity: float = 100_000.0):
        self.equity = equity
        self.orders = []

    def place_order(self, order: Order) -> OrderHandle:
        self.orders.append(order)
        return OrderHandle(broker_order_id=f"fake-{len(self.orders)}",
                            idempotency_key=order.idempotency_key,
                            status=OrderStatus.WORKING, filled_quantity=0)

    def cancel_order(self, handle: OrderHandle) -> bool:
        return True

    def positions(self):
        return []

    def fills(self, since=None):
        return []

    def account(self) -> AccountSnapshot:
        return AccountSnapshot(account_number="FAKE", cash_balance=self.equity,
                                buying_power=self.equity, equity=self.equity)


def test_legacy_grade_fire_books_dry_false_g88_on_fake_broker(tmp_path, monkeypatch):
    """A synthetic legacy-grade (non-S) fire, submitted through the exact
    function the widened alert_only branch calls, produces a journal row
    tagged dry:false, arm:engine, entry_rule:g88, legacy:True -- never a
    live order (FakeBroker, no network)."""
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = _FakeBroker()
    runner = SimpleNamespace(replay=False)
    # A "B" legacy-grade signal that would be WATCH-only (not S) -- this is
    # exactly the sig shape _emit_signal's alert_only branch now submits.
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0, "level_price": 247.10}

    rec = live_scanner._alpaca_submit_entry(
        broker, runner, "TSLA", sig, "09:41:00",
        size_pct=live_scanner.LEGACY_GRADE_MAX_LOSS / 1000.0,
        entry_rule="g88", extra={"legacy": True, "grade": "B"})

    assert rec is not None, "expected a booked order, not a zero-quantity skip"
    assert len(broker.orders) == 1
    order = broker.orders[0]
    assert order.order_type == OrderType.LIMIT, "g88 must never submit a MARKET order"
    assert order.limit_price == 247.10

    logged = json.loads((tmp_path / "alpaca-paper.jsonl").read_text().strip())
    assert logged["dry"] is False, logged
    assert logged["entry_rule"] == "g88", logged
    assert logged["arm"] == "engine", logged
    assert logged["legacy"] is True, logged
    assert logged["grade"] == "B", logged
    assert logged["level_price"] == 247.10, logged
    print(f"PASS: legacy-grade fire logged dry:false entry_rule:g88 -- {logged}")


def test_engine_legacy_paper_kill_switch_reads_env(monkeypatch):
    """ENGINE_LEGACY_PAPER=0 must read as off -- the rollback path named in
    the plan (Projects/omen-v5-undry-plan.md), no code change needed."""
    monkeypatch.setenv("ENGINE_LEGACY_PAPER", "0")
    import importlib
    reloaded = importlib.reload(live_scanner)
    try:
        assert reloaded.ENGINE_LEGACY_PAPER is False
        print("PASS: ENGINE_LEGACY_PAPER=0 disables the legacy-grade paper arm")
    finally:
        monkeypatch.delenv("ENGINE_LEGACY_PAPER", raising=False)
        importlib.reload(live_scanner)


if __name__ == "__main__":
    import tempfile

    class _MP:
        def __init__(self):
            self._saved = {}

        def setattr(self, obj, name, val):
            setattr(obj, name, val)

        def setenv(self, name, val):
            import os
            self._saved[name] = os.environ.get(name)
            os.environ[name] = val

        def delenv(self, name, raising=True):
            import os
            os.environ.pop(name, None)

    failures = 0
    tests = [
        ("test_alpaca_broker_client_names_paper_endpoint", test_alpaca_broker_client_names_paper_endpoint, {}),
    ]
    with tempfile.TemporaryDirectory() as d:
        tmp_path = Path(d)
        tests.append(("test_legacy_grade_fire_books_dry_false_g88_on_fake_broker",
                      test_legacy_grade_fire_books_dry_false_g88_on_fake_broker,
                      {"tmp_path": tmp_path, "monkeypatch": _MP()}))
        tests.append(("test_engine_legacy_paper_kill_switch_reads_env",
                      test_engine_legacy_paper_kill_switch_reads_env,
                      {"monkeypatch": _MP()}))
        for name, fn, kwargs in tests:
            try:
                fn(**kwargs)
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
