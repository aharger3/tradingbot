"""research/test_alpaca_wiring.py — OMEN 9.0 W3, resized V5b (2026-09-14).

Unit tests for `live_scanner._alpaca_submit_entry` / `_alpaca_submit_exit`
against a FakeBroker (no network, no real Alpaca SDK import). Asserts:

  1. one submit per fired S, sized to 1R in shares of the underlying --
     V5b (docs/rows/v5-contract.md): both paper arms book shares only, never
     an option contract, so this file no longer has an options-path test.
  2. the notional cap fires when 1R-in-shares would exceed 25% of the paper
     account's own equity (`options_sizer.size_share_qty`) -- the referee's
     hold on V5: an uncapped share order can exceed paper buying power.
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
import live_scanner


class FakeBroker(BrokerInterface):
    """Records every place_order call; `equity` is controllable per-test so
    the notional cap (`options_sizer.size_share_qty`) can be exercised the
    way a real paper account's shrinking buying power would."""

    def __init__(self, equity: float = 1_000_000.0):
        self.equity = equity
        self.orders = []  # list of Order

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


def _fresh_runner(replay: bool):
    r = SimpleNamespace()
    r.replay = replay
    return r


def test_one_submit_per_fired_s_sized_to_1r(tmp_path, monkeypatch):
    """entry_rule="close" (pre-V6 default, still available): MARKET, sized to
    1R. See test_g88_is_the_default_and_submits_a_limit_at_the_level below for
    the paper arm's actual default."""
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker()
    runner = _fresh_runner(replay=False)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0}  # $2/share risk
    rec = live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig,
                                            "09:41:00", size_pct=1.0, entry_rule="close")
    assert rec is not None
    assert len(broker.orders) == 1
    order = broker.orders[0]
    assert order.symbol == "TSLA"  # underlying, never an OCC symbol
    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.MARKET
    # 1R = $1000 / $2 risk-per-share = 500 shares
    assert order.quantity == 500
    logged = json.loads((tmp_path / "alpaca-paper.jsonl").read_text().strip())
    assert logged["event"] == "entry"
    assert logged["arm"] == "engine"
    assert logged["entry_rule"] == "close"


def test_notional_cap_fires_below_25pct_equity(tmp_path, monkeypatch):
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    # 500 shares @ $248 = $124,000 notional; cap it below that with a small
    # paper account so the cap -- not the 1R formula -- decides quantity.
    broker = FakeBroker(equity=10_000.0)  # 25% = $2,500 -> floor(2500/248) = 10
    runner = _fresh_runner(replay=False)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0}
    rec = live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig,
                                            "09:41:00", size_pct=1.0, entry_rule="close")
    assert rec is not None
    order = broker.orders[0]
    assert order.quantity == 10
    assert order.quantity * sig["entry"] <= 0.25 * broker.equity


def test_g88_is_the_default_and_submits_a_limit_at_the_level(tmp_path, monkeypatch):
    """V6 (docs/rows/v5-contract.md addendum, 2026-09-16): the paper arm's
    default flipped to g88 -- a resting LIMIT at the signal's own level,
    never a MARKET order, and the level is `sig["level_price"]` when the
    signal carried one (research/g88_level_limit.py's POST_floor arm)."""
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker()
    runner = _fresh_runner(replay=False)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0, "level_price": 247.10}
    rec = live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig,
                                            "09:41:00", size_pct=1.0)  # no entry_rule -> default
    assert rec is not None
    order = broker.orders[0]
    assert order.order_type == OrderType.LIMIT
    assert order.limit_price == 247.10
    # sizing is unaffected by which order type gets us in -- still 1R off the
    # signal's own entry/stop, not off the limit price.
    assert order.quantity == 500
    assert rec["entry_rule"] == "g88"
    logged = json.loads((tmp_path / "alpaca-paper.jsonl").read_text().strip())
    assert logged["entry_rule"] == "g88"


def test_g88_falls_back_to_stop_when_no_level_price(tmp_path, monkeypatch):
    """Some setups (a few flag entries) never record a distinct level_price;
    the shipped book-builder's own fallback for that case is
    `t.level_price or t.stop` (backtest_2y.py) -- this mirrors it."""
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker()
    runner = _fresh_runner(replay=False)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0}  # no level_price
    rec = live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig,
                                            "09:41:00", size_pct=1.0, entry_rule="g88")
    assert rec is not None
    order = broker.orders[0]
    assert order.order_type == OrderType.LIMIT
    assert order.limit_price == 246.0  # sig["stop"]


def test_stale_g88_entry_cancelled_after_entry_cutoff(tmp_path, monkeypatch):
    """A g88 limit that never touched dies at the entry cutoff -- never
    chased with a market order. Uses the module's real ENTRY_CUTOFF default
    (11:00) via monkeypatched now_et() rather than duplicating the constant."""
    import datetime as dt

    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker()
    runner = _fresh_runner(replay=False)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0, "level_price": 247.10}

    monkeypatch.setattr(live_scanner, "now_et", lambda: dt.datetime(2026, 9, 16, 10, 45))
    entry = live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig,
                                              "09:41:00", size_pct=1.0, entry_rule="g88")
    assert entry is not None
    key = "TSLA|09:41:00"
    assert key in live_scanner._alpaca_open_orders

    # Before the cutoff: still resting, nothing cancelled.
    live_scanner._alpaca_cancel_stale_g88_entries(broker)
    assert key in live_scanner._alpaca_open_orders

    # At/after the cutoff: cancelled and popped.
    monkeypatch.setattr(live_scanner, "now_et", lambda: dt.datetime(2026, 9, 16, 11, 0))
    live_scanner._alpaca_cancel_stale_g88_entries(broker)
    assert key not in live_scanner._alpaca_open_orders
    lines = [json.loads(l) for l in (tmp_path / "alpaca-paper.jsonl").read_text().strip().splitlines()]
    assert lines[-1]["event"] == "entry_cancelled"
    assert lines[-1]["entry_rule"] == "g88"


def test_one_close_per_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker()
    runner = _fresh_runner(replay=False)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0}
    entry = live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig,
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
    exit_logged = json.loads(lines[1])
    assert exit_logged["event"] == "exit"
    # V6: entry_rule carries through from the matching entry (default g88
    # here, since this test doesn't pass one), same pattern as "arm".
    assert exit_logged["entry_rule"] == "g88"


def test_zero_submits_under_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(live_scanner, "_ALPACA_LEDGER", tmp_path / "alpaca-paper.jsonl")
    live_scanner._alpaca_open_orders.clear()
    broker = FakeBroker()
    runner = _fresh_runner(replay=True)
    sig = {"direction": "call", "entry": 248.0, "stop": 246.0}
    try:
        live_scanner._alpaca_submit_entry(broker, runner, "TSLA", sig,
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
