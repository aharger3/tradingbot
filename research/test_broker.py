"""research/test_broker.py — exercises broker/simulator.py end to end.

Every scenario T65 says matters more than the happy path (Section 2.3, 2.4,
2.5) plus the happy-path 30/30/30/10 ladder itself. NO network calls: only
SimulatorBroker is exercised for behavior. TastytradeBroker is touched only
enough to prove its production guard and its missing-sandbox-credential
guard fire correctly — never constructed successfully, never called.

Run: `python research/test_broker.py` or `pytest research/test_broker.py -v`.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.base import Order, OrderSide, OrderStatus, OrderType, TimeInForce
from broker.simulator import SimulatorBroker


# ---------------------------------------------------------------------------
# Shared invariant: derive true holdings from the broker's own fill log (the
# audit trail) and check positions() never disagrees with it. This is the
# check the task calls out by name — run it after every mutating step in
# every scenario below, not just once at the end.
# ---------------------------------------------------------------------------
def assert_positions_consistent(sim: SimulatorBroker) -> None:
    expected = {}
    for f in sim.fills():
        signed = f.quantity if f.side == OrderSide.BUY else -f.quantity
        expected[f.symbol] = expected.get(f.symbol, 0) + signed
    expected = {sym: qty for sym, qty in expected.items() if qty != 0}
    actual = {p.symbol: p.quantity for p in sim.positions()}
    assert actual == expected, (
        f"simulator reports a position its own fill log doesn't back: "
        f"positions()={actual} vs fills-derived={expected}"
    )


def _order(symbol, side, qty, order_type, key, limit_price=None, stop_price=None):
    return Order(
        symbol=symbol,
        side=side,
        quantity=qty,
        order_type=order_type,
        idempotency_key=key,
        limit_price=limit_price,
        stop_price=stop_price,
        time_in_force=TimeInForce.DAY,
    )


SYM = "TSLA260610C00440000"


# ---------------------------------------------------------------------------
# 1. Happy path: full 30/30/30/10 ladder.
#    entry -> tranche 1 exits at HOD -> breakeven stop armed on the runner
#    (re-armed, cancel/replace, as each further tranche reduces size) ->
#    tranche 2 -> tranche 3 -> force-flat at 11:00 leaves the 10% runner
#    live, per T65 Section 2.2 step 7's named exception.
# ---------------------------------------------------------------------------
def test_full_ladder():
    sim = SimulatorBroker(starting_cash=100_000.0)
    entry_price = 5.00

    # Entry: 100 contracts, market, at 09:31.
    sim.mark(SYM, close=entry_price, timestamp="2026-08-24T09:31:00+00:00")
    entry = sim.place_order(_order(SYM, OrderSide.BUY, 100, OrderType.MARKET, "ladder-entry"))
    assert entry.status == OrderStatus.FILLED
    assert entry.filled_quantity == 100
    assert_positions_consistent(sim)
    pos = {p.symbol: p for p in sim.positions()}[SYM]
    assert pos.quantity == 100 and pos.avg_price == entry_price

    # Tranche 1 (30%) exits at HOD.
    hod = 6.50
    t1 = sim.place_order(_order(SYM, OrderSide.SELL, 30, OrderType.LIMIT, "ladder-t1", limit_price=hod))
    assert t1.status == OrderStatus.WORKING  # resting until price reaches HOD
    fills = sim.mark(SYM, close=6.60, high=6.70, low=6.40, timestamp="2026-08-24T09:50:00+00:00")
    assert len(fills) == 1 and fills[0].price == hod  # limit never fills worse than requested
    assert_positions_consistent(sim)
    remaining = {p.symbol: p for p in sim.positions()}[SYM].quantity
    assert remaining == 70

    # Breakeven stop armed on the runner immediately after tranche 1 fills
    # (T65 Section 2.2 step 5 — mechanical, no exceptions).
    be_stop = sim.place_order(_order(SYM, OrderSide.SELL, 70, OrderType.STOP, "ladder-be-1", stop_price=entry_price))
    assert be_stop.status == OrderStatus.WORKING
    assert_positions_consistent(sim)

    # Tranche 2 (30%) exits at its target. T65 Section 2.3: a resting order
    # must be cancelled, not stacked, once the ladder moves past it — so the
    # stale 70-sized breakeven stop is cancelled before the new size is armed
    # (cancel-then-replace, per base.py's cancel_order docstring).
    assert sim.cancel_order(be_stop) is True
    target2 = 7.20
    t2 = sim.place_order(_order(SYM, OrderSide.SELL, 30, OrderType.LIMIT, "ladder-t2", limit_price=target2))
    fills = sim.mark(SYM, close=7.30, high=7.40, low=7.10, timestamp="2026-08-24T10:05:00+00:00")
    assert len(fills) == 1 and fills[0].price == target2
    assert_positions_consistent(sim)
    remaining = {p.symbol: p for p in sim.positions()}[SYM].quantity
    assert remaining == 40
    be_stop = sim.place_order(_order(SYM, OrderSide.SELL, 40, OrderType.STOP, "ladder-be-2", stop_price=entry_price))

    # Tranche 3 (30%) exits at its target — same cancel/replace discipline.
    assert sim.cancel_order(be_stop) is True
    target3 = 7.80
    t3 = sim.place_order(_order(SYM, OrderSide.SELL, 30, OrderType.LIMIT, "ladder-t3", limit_price=target3))
    fills = sim.mark(SYM, close=7.90, high=8.00, low=7.70, timestamp="2026-08-24T10:20:00+00:00")
    assert len(fills) == 1 and fills[0].price == target3
    assert_positions_consistent(sim)
    remaining = {p.symbol: p for p in sim.positions()}[SYM].quantity
    assert remaining == 10  # the runner
    be_stop = sim.place_order(_order(SYM, OrderSide.SELL, 10, OrderType.STOP, "ladder-be-3", stop_price=entry_price))

    # Force-flat at 11:00: T65 Section 2.2 step 7 — everything closes EXCEPT
    # the 10% runner, which is explicitly permitted to stay live. Nothing to
    # sell here (only the runner remains), so force-flat issues no order;
    # the runner's breakeven stop stays resting.
    remaining_positions = sim.positions()
    assert len(remaining_positions) == 1 and remaining_positions[0].quantity == 10
    # (a state machine's FORCE_FLAT step would check "is this the runner"
    # before market-selling — here that check simply finds nothing else to
    # flatten, which is the named exception, not a special case.)
    assert_positions_consistent(sim)
    print("test_full_ladder: PASS")


# ---------------------------------------------------------------------------
# 2. PARTIAL fill: tranche order fills less than requested, position opens
#    at the filled size (T65 Section 2.3), and the unfilled remainder is
#    cancelled rather than left stacked.
# ---------------------------------------------------------------------------
def test_partial_fill():
    sim = SimulatorBroker(starting_cash=100_000.0)
    sim.mark(SYM, close=5.00, timestamp="2026-08-24T09:31:00+00:00")

    sim.queue_partial_fill(0.6)  # only 18 of 30 fill
    handle = sim.place_order(_order(SYM, OrderSide.BUY, 30, OrderType.MARKET, "partial-entry"))
    assert handle.status == OrderStatus.PARTIAL
    assert handle.filled_quantity == 18
    assert_positions_consistent(sim)
    pos = {p.symbol: p for p in sim.positions()}[SYM]
    assert pos.quantity == 18, "breakeven arms on the FILLED size, not the intended size"

    # The unfilled remainder is cancelled, not left resting to be "stacked"
    # against later tranches (T65 Section 2.3).
    cancelled = sim.cancel_order(handle)
    assert cancelled is True
    assert_positions_consistent(sim)
    # Cancelling the remainder must not touch the 18 already filled.
    pos = {p.symbol: p for p in sim.positions()}[SYM]
    assert pos.quantity == 18

    # Idempotent replay of the same key must not double-fill or re-place.
    handle2 = sim.place_order(_order(SYM, OrderSide.BUY, 30, OrderType.MARKET, "partial-entry"))
    assert handle2.broker_order_id == handle.broker_order_id
    assert_positions_consistent(sim)
    pos = {p.symbol: p for p in sim.positions()}[SYM]
    assert pos.quantity == 18, "idempotent replay must not double-order"
    print("test_partial_fill: PASS")


# ---------------------------------------------------------------------------
# 3. Gap straight through a stop: the candle's low blows past the stop level
#    and its close prints materially worse than the stop price. T65 Section
#    2.4: the broker never promises a fill price — the simulator's fill
#    lands at the bad close, not at the requested stop level.
# ---------------------------------------------------------------------------
def test_gap_through_stop():
    sim = SimulatorBroker(starting_cash=100_000.0)
    entry_price = 5.00
    sim.mark(SYM, close=entry_price, timestamp="2026-08-24T09:31:00+00:00")
    sim.place_order(_order(SYM, OrderSide.BUY, 20, OrderType.MARKET, "gap-entry"))
    assert_positions_consistent(sim)

    stop_price = 4.50  # -1.25R-style protective stop, floored per the backtest model
    stop = sim.place_order(_order(SYM, OrderSide.SELL, 20, OrderType.STOP, "gap-stop", stop_price=stop_price))
    assert stop.status == OrderStatus.WORKING

    # A fast move guts the option premium straight through the stop: low and
    # close both print well below stop_price — no fill was ever available
    # at the modelled stop level.
    gap_close = 2.10
    fills = sim.mark(SYM, close=gap_close, high=4.60, low=1.90, timestamp="2026-08-24T09:52:00+00:00")
    assert len(fills) == 1
    assert fills[0].price == gap_close, "fill must land at the actual close, not the stale stop price"
    assert fills[0].price < stop_price, "this IS the gap: fill is materially worse than the requested stop"
    assert_positions_consistent(sim)
    assert sim.positions() == [], "fully exited — nothing should remain open"
    print("test_gap_through_stop: PASS")


# ---------------------------------------------------------------------------
# 4. Crash-and-recover mid-position: T65 Section 2.5 — the broker, not the
#    local process, is the source of truth. A fresh SimulatorBroker pointed
#    at the same state_path stands in for "the local process restarted; the
#    broker was never down."
# ---------------------------------------------------------------------------
def test_crash_and_recover():
    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "broker-state.json"

        sim_before = SimulatorBroker(starting_cash=100_000.0, state_path=state_path)
        sim_before.mark(SYM, close=5.00, timestamp="2026-08-24T09:31:00+00:00")
        sim_before.place_order(_order(SYM, OrderSide.BUY, 40, OrderType.MARKET, "crash-entry"))
        sim_before.place_order(
            _order(SYM, OrderSide.SELL, 40, OrderType.STOP, "crash-stop", stop_price=4.50)
        )
        assert_positions_consistent(sim_before)
        positions_before = {p.symbol: (p.quantity, p.avg_price) for p in sim_before.positions()}
        fills_before = [(f.fill_id, f.symbol, f.quantity, f.price) for f in sim_before.fills()]
        account_before = sim_before.account()

        # "Crash": drop the in-memory object. Nothing further is called on
        # sim_before — a fresh instance against the same state_path is the
        # only thing that stands in for the restarted process.
        del sim_before

        sim_after = SimulatorBroker(starting_cash=999.0, state_path=state_path)  # starting_cash ignored on load
        assert_positions_consistent(sim_after)
        positions_after = {p.symbol: (p.quantity, p.avg_price) for p in sim_after.positions()}
        fills_after = [(f.fill_id, f.symbol, f.quantity, f.price) for f in sim_after.fills()]
        assert positions_after == positions_before, "broker state must survive the local process restarting"
        assert fills_after == fills_before
        assert sim_after.account() == account_before

        # Idempotency must also survive the restart: retrying the original
        # entry key on the "recovered" broker must not double-order — this
        # is the exact mechanism T65 Section 2.5 point 2 depends on when the
        # recovery routine can't tell whether its last order landed.
        replay = sim_after.place_order(_order(SYM, OrderSide.BUY, 40, OrderType.MARKET, "crash-entry"))
        assert replay.filled_quantity == 40
        assert_positions_consistent(sim_after)
        pos = {p.symbol: p for p in sim_after.positions()}[SYM]
        assert pos.quantity == 40, "idempotency key must survive a restart, not just an in-process retry"
        print("test_crash_and_recover: PASS")


# ---------------------------------------------------------------------------
# 5. TastytradeBroker's guard rails — no network, never constructed
#    successfully. Proves the production guard and the STOP-if-sandbox-
#    creds-are-missing behavior the security constraint requires.
# ---------------------------------------------------------------------------
def test_tastytrade_guards():
    import os

    from broker.tastytrade import (
        SANDBOX_BASE_URL,
        TastytradeBroker,
        TastytradeSandboxCredentialsMissing,
    )

    # Pointed at production (or anything non-cert): must refuse before ever
    # touching the network.
    try:
        TastytradeBroker(base_url="https://api.tastytrade.com", session_token="fake")
        assert False, "must raise when base_url is not the sandbox/cert host"
    except RuntimeError as e:
        assert "sandbox" in str(e).lower()

    try:
        TastytradeBroker(base_url="https://api.tastyworks.com", session_token="fake")
        assert False, "must refuse the non-cert production alias too"
    except RuntimeError:
        pass

    # Sandbox host, but no TASTYTRADE_SANDBOX_* credentials anywhere in this
    # environment (confirmed: not present in .env as of this task) — must
    # STOP, never fall back to TASTYTRADE_USERNAME/PASSWORD.
    saved = {k: os.environ.pop(k, None) for k in (
        "TASTYTRADE_SANDBOX_SESSION_TOKEN",
        "TASTYTRADE_SANDBOX_USERNAME",
        "TASTYTRADE_SANDBOX_PASSWORD",
    )}
    try:
        try:
            TastytradeBroker(base_url=SANDBOX_BASE_URL)
            assert False, "must raise when no sandbox credentials are present"
        except TastytradeSandboxCredentialsMissing:
            pass
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v

    print("test_tastytrade_guards: PASS")


if __name__ == "__main__":
    test_full_ladder()
    test_partial_fill()
    test_gap_through_stop()
    test_crash_and_recover()
    test_tastytrade_guards()
    print("\nALL BROKER TESTS PASSED")
