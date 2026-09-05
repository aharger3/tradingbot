#!/usr/bin/env python3
"""research/g203_referee_probe.py — OMEN 9.0 wave-2 referee for W3 (61c15363).

Adversarial end-to-end probe of the Alpaca paper-submit wiring. The shipped
test `research/test_alpaca_wiring.py` exercises `_alpaca_submit_entry` /
`_alpaca_submit_exit` DIRECTLY, so it cannot see whether the call sites in
`_emit_signal` are gated correctly. This probe drives the real `_emit_signal`
with a fake broker and counts orders, which is the only way to answer "a
fired S submits exactly one order".

Run:  python research/g203_referee_probe.py
Exit 0 = every referee assertion held.
"""
import pathlib
import sys
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import live_scanner as ls
import options_sizer
from broker.base import Order, OrderHandle, OrderStatus
from omen_bot import TradingSession

FAILS = []


def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


class FakeBroker:
    """Counts place_order calls. resolve_option_contract always succeeds."""

    def __init__(self, explode=False):
        self.orders = []
        self.explode = explode

    def resolve_option_contract(self, underlying, expiration, strike, direction):
        return f"{underlying}_OCC"

    def place_order(self, order: Order) -> OrderHandle:
        self.orders.append(order)
        if self.explode:
            raise RuntimeError("broker down")
        return OrderHandle(broker_order_id=f"fake-{len(self.orders)}",
                           idempotency_key=order.idempotency_key,
                           status=OrderStatus.WORKING, filled_quantity=0)


class _Type:
    def __init__(self, value):
        self.value = value


class _Candle:
    def __init__(self, ts="09:45:00"):
        self.timestamp = ts


class _Runner:
    def __init__(self, replay=False):
        self.session = TradingSession()
        self.futures_mode = False
        self.post_to_discord = False
        self.discord = None
        self.replay = replay


class _FakePlan:
    def __init__(self, max_loss):
        self.max_loss = max_loss
        self.contracts = 3 if max_loss > 0 else 0
        self.stock_target = 0.0
        self.quote_source = "estimated_delta"
        self.symbol = "TSLA"
        self.direction = "call"
        self.strike = 250.0
        self.expiration = "2026-01-16"
        self.occ_symbol = "TSLA260116C00250000"
        self.entry_premium = 2.0
        self.stop_premium = 1.0
        self.target_premium = 4.0

    def format_discord(self):
        return ""


class _FakePaper:
    """Minimal stand-in for PaperBook: open_from_plan only."""

    def open_from_plan(self, plan, ts=None, grade="?", setup="?"):
        return SimpleNamespace(contracts=plan.contracts, symbol=plan.symbol,
                               strike=plan.strike, direction=plan.direction,
                               entry_premium=plan.entry_premium, opened_at=ts)


def sig(sac, grade="A", setup="break_and_retest"):
    return {
        "signal_type": _Type(setup),
        "grade": grade,
        "sac_grade": sac,
        "austin_tier": sac,
        "direction": "call",
        "entry": 100.0,
        "stop": 99.0,
        "reason": "referee probe",
        "stop_level_name": "test level",
        "stop_width_pct": 0.1,
    }


def emit(s, broker, symbol="TSLA", ts="09:45:00", replay=False):
    """Run the real `_emit_signal` with every non-broker side effect stubbed."""
    orig_build = options_sizer.build_options_plan
    orig_log = ls.log_signal
    orig_push = ls.notify_ntfy.push
    options_sizer.build_options_plan = lambda **kw: _FakePlan(kw["max_loss"])
    ls.log_signal = lambda **kw: None
    ls.notify_ntfy.push = lambda *a, **k: True
    ls._last_alert.clear()
    ls._s_trades_today.clear()
    ls._watch_dings["n"] = 0
    ls._session_push["pushed"] = False
    ls._session_push["push_rec"] = None
    ls._session_push["veto_first"] = None
    ls._session_push["trades"] = []
    ls._alpaca_open_orders.clear()
    try:
        return ls._emit_signal(_Runner(replay=replay), None, symbol, _Candle(ts),
                               s, paper=_FakePaper(), broker=broker)
    finally:
        options_sizer.build_options_plan = orig_build
        ls.log_signal = orig_log
        ls.notify_ntfy.push = orig_push


def main():
    # Keep the referee's ledger out of the real journal/.
    ledger = pathlib.Path(__file__).resolve().parent / "g203_referee_ledger.jsonl"
    if ledger.exists():
        ledger.unlink()
    ls._ALPACA_LEDGER = ledger

    print("1. a fired S submits exactly one order")
    b = FakeBroker()
    emit(sig("S"), b)
    check(len(b.orders) == 1, f"S -> 1 order (got {len(b.orders)})")
    check(b.orders and b.orders[0].quantity == 3, "quantity = plan.contracts")
    check(b.orders and b.orders[0].symbol == "TSLA_OCC",
          "symbol resolved off Alpaca's chain, not plan.occ_symbol")

    print("2. a non-S never reaches the broker")
    for sac in ("A", "C"):
        b = FakeBroker()
        emit(sig(sac), b)
        check(len(b.orders) == 0, f"sac_grade {sac} -> 0 orders")

    print("3. broker=None (no --paper-broker) submits nothing and still returns")
    got = emit(sig("S"), None)
    check(got is True, "TRADE tier still returns True with broker=None")

    print("4. a broker exception does not propagate (sim book stands alone)")
    b = FakeBroker(explode=True)
    try:
        emit(sig("S"), b)
        raised = False
    except Exception as e:  # noqa: BLE001
        raised = True
        print(f"       propagated: {type(e).__name__}: {e}")
    check(not raised, "place_order failure swallowed")

    print("5. replay can never submit, even if a broker is handed in")
    b = FakeBroker()
    try:
        emit(sig("S"), b, replay=True)
        raised = False
    except AssertionError:
        raised = True
    check(raised, "runner.replay=True raises before place_order")
    check(len(b.orders) == 0, "zero orders under replay")

    print("6. ADVERSARIAL: an 84% re-entry is TRADE regardless of grade")
    b = FakeBroker()
    emit(sig("C", setup="reentry_84_rule"), b)
    print(f"       reentry with sac_grade=C -> {len(b.orders)} order(s)")
    check(True, "recorded (see report: this is a non-S submission path)")

    print("7. ADVERSARIAL: exit quantity after a partial scale")
    # `_alpaca_submit_exit` sells entry_rec['quantity'] (full size); a CLOSE
    # event after a SCALE carries only the runner leg in ev['contracts'].
    b = FakeBroker()
    r = _Runner()
    ls._alpaca_open_orders.clear()
    ls._alpaca_submit_entry(b, r, "TSLA", sig("S"), _FakePlan(1000.0),
                            "09:45:00", size_pct=1.0)
    ev = {"event": "CLOSE", "symbol": "TSLA", "direction": "call",
          "opened_at": "09:45:00", "outcome": "target", "ts": "10:10:00",
          "contracts": 1, "total_contracts": 3, "scaled": True,
          "scale_contracts": 2}
    x = ls._alpaca_submit_exit(b, r, ev)
    print(f"       CLOSE says runner leg = {ev['contracts']}; "
          f"exit order sends {x['quantity'] if x else None}")
    check(x is not None and x["quantity"] != ev["contracts"],
          "confirmed mismatch: exit ignores ev['contracts'] (latent, ladder OFF by default)")

    if ledger.exists():
        ledger.unlink()
    print(f"\n{'ALL REFEREE CHECKS HELD' if not FAILS else 'FAILURES: ' + str(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
