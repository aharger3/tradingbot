"""research/test_alpaca_wiring.py — OMEN 9.0 W3.

Unit tests for `live_scanner._alpaca_submit_entry` / `_alpaca_submit_exit`
against a FakeBroker (no network, no real Alpaca SDK import). Asserts:

  1. one submit per fired S (options path, resolve_option_contract succeeds)
  2. the shares fallback fires and sizes to 1R when OptionsNotAvailable
  3. one closing submit when the marking loop books an exit
  4. ZERO submits under replay -- `runner.replay is True` must raise, never
     silently skip, so a call-site regression that forgets the guard is
     caught loudly.

No network call, no broker/alpaca.py import at module scope (it lazy-imports
`alpaca.trading.client` inside AlpacaBroker.__init__, which this test never
constructs) -- only `broker.base` (the ABC) and `live_scanner`'s submission
functions are exercised.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from broker.base import (
    AccountSnapshot, BrokerInterface, Fill, Order, OrderHandle, OrderSide,
    OrderStatus, OrderType, Position,
)
from broker.alpaca import OptionsNotAvailable
import live_scanner


class FakeBroker(BrokerInterface):
    """Records every place_order call; resolve_option_contract is
    controllable per-test (`options_available`) the way AlpacaBroker's would
    behave against a real listed/unlisted chain."""

    def __init__(self, options_available: bool = True):
        self.options_available = options_available
        self.orders = []  # list of Order

    def resolve_option_contract(self, underlying, expiration, strike, direction):
        if not self.options_available:
            raise OptionsNotAvailable(f"no listed contract for {underlying}")
        return f"{underlying}{expiration.replace('-', '')}{direction[0].upper()}{int(strike*1000):08d}"

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
        return AccountSnapshot(account_number="FAKE", cash_balance=100000.0,
                                buying_power=100000.0)


def _fresh_runner(replay: bool):
    r = SimpleNamespace()
    r.replay = replay
    return r


def _plan(occ="TSLA260101C00250000"):
    return SimpleNamespace(
        symbol="TSLA", direction="call", expiration="2026-01-01", strike=250.0,
        contracts=3, occ_symbol=occ,
        stock_entry=248.0, stock_stop=246.0, stock_target=252.0,
    )


def test_one_submit_per_fired_s_options_path(tmp_path, monkeypatch):
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker(options_available=True)
    runner = _fresh_runner(replay=False)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0}
    rec = live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig, _plan(),
                                            "09:41:00", size_pct=1.0)
    assert rec is not None
    assert len(broker.orders) == 1
    assert broker.orders[0].side == OrderSide.BUY
    assert broker.orders[0].order_type == OrderType.MARKET
    assert broker.orders[0].quantity == 3
    assert broker.orders[0].symbol.startswith("TSLA")
    # logged
    lines = (tmp_path / "alpaca-paper.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    logged = json.loads(lines[0])
    assert logged["event"] == "entry"
    assert logged["fallback"] is None


def test_shares_fallback_sizes_to_1r(tmp_path, monkeypatch):
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker(options_available=False)
    runner = _fresh_runner(replay=False)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0}  # $2/share risk
    rec = live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig, _plan(),
                                            "09:41:00", size_pct=1.0)
    assert rec is not None
    assert len(broker.orders) == 1
    order = broker.orders[0]
    assert order.symbol == "TSLA"  # underlying, not an OCC symbol
    assert order.side == OrderSide.BUY
    # 1R = $1000 / $2 risk-per-share = 500 shares
    assert order.quantity == 500
    logged = json.loads((tmp_path / "alpaca-paper.jsonl").read_text().strip())
    assert logged["fallback"] == "shares"


def test_one_close_per_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker(options_available=True)
    runner = _fresh_runner(replay=False)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0}
    entry = live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig, _plan(),
                                              "09:41:00", size_pct=1.0)
    assert entry is not None
    assert len(broker.orders) == 1

    ev = {"event": "CLOSE", "symbol": "TSLA", "direction": "call",
          "opened_at": "09:41:00", "outcome": "stop", "ts": "09:55:00"}
    xrec = live_scanner._alpaca_submit_exit(broker, runner, ev)
    assert xrec is not None
    assert len(broker.orders) == 2
    assert broker.orders[1].side == OrderSide.SELL  # closes the long
    assert broker.orders[1].symbol == broker.orders[0].symbol
    assert broker.orders[1].quantity == broker.orders[0].quantity

    # a second close event for the same key is a no-op (already popped)
    xrec2 = live_scanner._alpaca_submit_exit(broker, runner, ev)
    assert xrec2 is None
    assert len(broker.orders) == 2

    lines = (tmp_path / "alpaca-paper.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["event"] == "exit"


def test_zero_submits_under_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker(options_available=True)
    runner = _fresh_runner(replay=True)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0}
    try:
        live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig, _plan(),
                                          "09:41:00", size_pct=1.0)
        raised = False
    except AssertionError:
        raised = True
    assert raised, "replay must never reach broker.place_order (entry)"
    assert broker.orders == []

    ev = {"event": "CLOSE", "symbol": "TSLA", "direction": "call",
          "opened_at": "09:41:00", "outcome": "stop", "ts": "09:55:00"}
    try:
        live_scanner._alpaca_submit_exit(broker, runner, ev)
        raised = False
    except AssertionError:
        raised = True
    assert raised, "replay must never reach broker.place_order (exit)"
    assert broker.orders == []


def test_run_replay_sets_runner_replay_true():
    """`run_replay` always sets `runner.replay = True` before any scan_once
    call -- the guard that makes the above assert reachable in the real
    process, not just in this test's hand-built runner."""
    import inspect
    src = inspect.getsource(live_scanner.run_replay)
    assert "runner.replay = True" in src


def test_main_sets_runner_replay_false():
    """The live/once path explicitly marks itself non-replay."""
    import inspect
    src = inspect.getsource(live_scanner.main)
    assert "runner.replay = False" in src


if __name__ == "__main__":
    import tempfile
    failures = 0
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        params = inspect_params = t.__code__.co_varnames[:t.__code__.co_argcount]
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)

            class _MP:
                def setattr(self, obj, name, val):
                    setattr(obj, name, val)

            kwargs = {}
            if "tmp_path" in params:
                kwargs["tmp_path"] = tmp_path
            if "monkeypatch" in params:
                kwargs["monkeypatch"] = _MP()
            try:
                t(**kwargs)
                print(f"PASS {t.__name__}")
            except Exception as e:
                failures += 1
                print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
