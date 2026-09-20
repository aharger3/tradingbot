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
    AccountSnapshot, BrokerInterface, Fill, Order, OrderHandle, OrderSide,
    OrderStatus, OrderType, Position,
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


def test_flatten_legacy_cancels_stale_order_and_flattens_filled_position(tmp_path, monkeypatch):
    """omen-v5-undry follow-up (2026-09-19): the flagged risk was 'a legacy
    limit that fills has no exit -- it sits as an open paper position
    forever'. Seeds one still-resting legacy g88 order and one already-
    filled one (an open position with no other exit path), then asserts
    `flatten_legacy()` cancels the first, market-flattens the second against
    the broker's own positions() (never a local guess), and writes exactly
    one journal row per action. FakeBroker throughout -- no real order."""
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    live_scanner._legacy_positions.clear()

    class _SessionEndBroker(BrokerInterface):
        """order-1 is still resting (cancel succeeds, order-side.py contract);
        order-2 already filled (cancel returns False, 'probably filled'),
        leaving an open MSFT position this function must flatten."""

        def __init__(self):
            self.orders = []
            self.cancelled = []

        def place_order(self, order: Order) -> OrderHandle:
            self.orders.append(order)
            return OrderHandle(broker_order_id=f"close-{len(self.orders)}",
                                idempotency_key=order.idempotency_key,
                                status=OrderStatus.FILLED, filled_quantity=order.quantity)

        def cancel_order(self, handle: OrderHandle) -> bool:
            self.cancelled.append(handle.broker_order_id)
            return handle.broker_order_id == "order-1"  # order-2: already filled

        def positions(self):
            return [Position(symbol="MSFT", quantity=10, avg_price=300.0)]

        def fills(self, since=None):
            if not self.orders:
                return []
            last = self.orders[-1]
            import datetime as _dt
            return [Fill(fill_id="f1", broker_order_id=f"close-{len(self.orders)}",
                         symbol=last.symbol, side=last.side, quantity=last.quantity,
                         price=305.0, timestamp=_dt.datetime.now())]

        def account(self) -> AccountSnapshot:
            return AccountSnapshot(account_number="FAKE", cash_balance=100_000.0,
                                    buying_power=100_000.0, equity=100_000.0)

    broker = _SessionEndBroker()

    # Seed directly -- mirrors what _alpaca_submit_entry(..., extra={"legacy":
    # True, ...}) would have written into _legacy_positions, without a full
    # sig/plan round-trip.
    live_scanner._legacy_positions["TSLA|09:41:00"] = {
        "symbol": "TSLA", "order_symbol": "TSLA", "direction": "call",
        "ts": "09:41:00", "broker_order_id": "order-1",
        "idempotency_key": "TSLA-09:41:00-call-entry", "entry_rule": "g88",
        "level_price": 247.10, "stop": 246.0, "max_loss": 100.0, "legacy": True,
    }
    live_scanner._legacy_positions["MSFT|09:45:00"] = {
        "symbol": "MSFT", "order_symbol": "MSFT", "direction": "call",
        "ts": "09:45:00", "broker_order_id": "order-2",
        "idempotency_key": "MSFT-09:45:00-call-entry", "entry_rule": "g88",
        "level_price": 300.0, "stop": 298.0, "max_loss": 100.0, "legacy": True,
    }

    results = live_scanner.flatten_legacy(broker)

    assert live_scanner._legacy_positions == {}, "flatten_legacy must clear every record it handled"
    assert broker.cancelled == ["order-1", "order-2"]
    assert len(broker.orders) == 1, "only the filled (MSFT) leg needs a real flatten order"
    assert broker.orders[0].symbol == "MSFT"
    assert broker.orders[0].order_type == OrderType.MARKET
    assert broker.orders[0].side == OrderSide.SELL  # long 10 MSFT -> sell to flatten
    assert broker.orders[0].quantity == 10

    actions = {r["symbol"]: r["action"] for r in results}
    assert actions == {"TSLA": "cancel", "MSFT": "flatten"}
    assert all(r["legacy"] is True for r in results)

    lines = [json.loads(l) for l in (tmp_path / "alpaca-paper.jsonl").read_text().strip().splitlines()]
    assert len(lines) == 2, "one journal row per action"
    cancel_row = next(l for l in lines if l["symbol"] == "TSLA")
    flatten_row = next(l for l in lines if l["symbol"] == "MSFT")
    assert cancel_row["action"] == "cancel" and cancel_row["legacy"] is True
    assert flatten_row["action"] == "flatten" and flatten_row["legacy"] is True
    assert flatten_row["fill_price"] == 305.0
    assert flatten_row["pnl"] == (305.0 - 300.0) * 10  # $50
    assert flatten_row["r_multiple"] == 50.0 / 100.0
    print(f"PASS: flatten_legacy cancelled 1 stale order + flattened 1 filled position -- {actions}")


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
    # Each test that touches the ledger gets its own tmp dir so one test's
    # journal rows never leak into another's line-count assertions.
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        tests.append(("test_legacy_grade_fire_books_dry_false_g88_on_fake_broker",
                      test_legacy_grade_fire_books_dry_false_g88_on_fake_broker,
                      {"tmp_path": Path(d1), "monkeypatch": _MP()}))
        tests.append(("test_flatten_legacy_cancels_stale_order_and_flattens_filled_position",
                      test_flatten_legacy_cancels_stale_order_and_flattens_filled_position,
                      {"tmp_path": Path(d2), "monkeypatch": _MP()}))
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
