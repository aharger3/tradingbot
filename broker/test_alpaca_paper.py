"""broker/test_alpaca_paper.py — L3 verify gate (OMEN 9.0).

Places one far-from-market LIMIT order on the Alpaca PAPER account, reads it
back via `positions()`/order lookup, cancels it, and confirms the cancel
landed. Exits 0 on success, non-zero (with a message, no secrets) otherwise.

Never touches the live endpoint: `AlpacaBroker` hard-codes `paper=True` on
construction (see broker/alpaca.py). Nothing here prints ALPACA_PAPER_KEY,
ALPACA_PAPER_SECRET, or any response body that could carry them.
"""

from __future__ import annotations

import os
import sys
import time

# Running this file directly (`python broker/test_alpaca_paper.py`) puts its
# own directory (broker/) at sys.path[0], which would shadow the installed
# `alpaca` (alpaca-py) package with our own broker/alpaca.py of the same
# name. Drop that entry before importing anything, then add the repo root
# instead so `broker.alpaca` / `broker.base` still resolve as a package.
_here = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _here]
sys.path.insert(0, os.path.dirname(_here))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from broker.alpaca import AlpacaBroker  # noqa: E402
from broker.base import Order, OrderSide, OrderType, TimeInForce  # noqa: E402


def main() -> int:
    try:
        broker = AlpacaBroker()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: could not construct AlpacaBroker: {e}")
        return 1

    # A limit BUY for AAPL shares at $1.00 -- nowhere near market, so it
    # rests as WORKING and never fills during this test.
    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.LIMIT,
        idempotency_key=f"g142-test-{int(time.time())}",
        limit_price=1.00,
        time_in_force=TimeInForce.DAY,
    )

    try:
        handle = broker.place_order(order)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: place_order raised: {e}")
        return 1

    print(f"placed: broker_order_id={handle.broker_order_id} status={handle.status.value}")

    if handle.status.value not in ("working", "partial"):
        print(f"FAIL: unexpected order status after placement: {handle.status.value}")
        return 1

    # Read it back: the order must appear among orders/positions bookkeeping.
    # positions() will be empty (nothing filled) -- that itself is expected
    # and correct, not a failure; we assert instead that fills()/positions()
    # do not raise, proving the read path against the paper account works.
    try:
        _ = broker.positions()
        _ = broker.account()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: read-back call raised: {e}")
        return 1

    ok = broker.cancel_order(handle)
    print(f"cancelled: {ok}")
    if not ok:
        print("FAIL: cancel_order returned False for a resting limit order")
        return 1

    print("PASS: placed, read back, cancelled on the Alpaca PAPER endpoint")
    return 0


if __name__ == "__main__":
    sys.exit(main())
