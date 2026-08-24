"""broker/simulator.py — BrokerInterface backed by in-process arithmetic.

WHY this file exists (T65 Section 4.1): "paper trading" is not a separate
mode with separate logic that has to be kept in sync with the real path —
it is the *same* state machine, pointed at SimulatorBroker instead of
TastytradeBroker. This is what Phase 1 actually runs against, per T65's
phased build order (Section 1): every bug found here is free, because
nothing here touches a network.

No network calls anywhere in this module. That is not an optimization —
it is the point: the whole state machine (entry, tranche exits, breakeven
stop, force-flat, partial fills, gaps, crash recovery) has to be provable
with zero financial risk and zero dependency on a broker being reachable.

Two things this simulator does that are NOT part of BrokerInterface, and
are intentionally not: `mark()` feeds the simulator a price tick so
resting LIMIT/STOP orders can be checked and filled, and `queue_partial_fill()`
lets a test force the next fill to be less than the full requested size.
Real market data and fill-quality are broker/venue concerns the shared
interface (broker/base.py) deliberately keeps out (T65 Section 3) — a
simulator standing in for a venue is allowed to need a data feed of its
own; the state machine talking to it through BrokerInterface never sees
these two extra methods and never needs to.

Fill-price policy that matters for T65 Section 2.4 (gaps through a stop):
a LIMIT order fills at its own limit price (a limit never fills worse than
requested). A STOP order fills at the tick's `close`, not at its
`stop_price` — this mirrors the OMEN rule that stops trigger on candle
close, not on price touching a level, and it is exactly what makes a gap
observable in this simulator: if a candle's low blows through the stop
level and closes far past it, the simulated fill is that bad close, not
the requested stop price. The interface never promises a fill price; this
is the concrete mechanism that keeps that promise honest even in the
simulator.

Durability (T65 Section 2.5's "the broker, not the local process, is the
source of truth"): if constructed with `state_path`, every mutating call
persists the full order/fill/position book to that file before returning.
A fresh SimulatorBroker pointed at the same `state_path` reconstructs
identical state — standing in for "the local process crashed and
restarted, and the broker was never down." Section 2.5 crash recovery is
about the *local* process converging back to the broker's truth; this is
how a simulator can exercise that without a real venue behind it.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from broker.base import (
    AccountSnapshot,
    BrokerInterface,
    Fill,
    Order,
    OrderHandle,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SimulatorBroker(BrokerInterface):
    """In-process, no-network implementation of BrokerInterface.

    Args:
        account_number: cosmetic; echoed back by `account()`.
        starting_cash: opening cash balance.
        contract_multiplier: dollars per point per unit of `quantity`
            (100 for standard equity options — the instrument OMEN
            trades, per CLAUDE.md: "the instrument is options, not
            shares").
        state_path: if given, the full book is persisted to this JSON
            file after every mutating call and reloaded from it on
            construction — see module docstring on crash recovery.
    """

    def __init__(
        self,
        account_number: str = "SIM-0001",
        starting_cash: float = 100_000.0,
        contract_multiplier: int = 100,
        state_path: Optional[Path] = None,
    ):
        self.account_number = account_number
        self.contract_multiplier = contract_multiplier
        self.state_path = Path(state_path) if state_path else None

        self._cash_balance = starting_cash
        self._orders: Dict[str, dict] = {}          # broker_order_id -> order dict
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> broker_order_id
        self._fills: List[dict] = []                 # insertion-ordered fill dicts
        self._positions: Dict[str, dict] = {}         # symbol -> {quantity, avg_price}
        self._last_price: Dict[str, float] = {}
        self._next_order_id = 1
        self._next_fill_id = 1
        self._queued_partial_ratio: Optional[float] = None  # test-only, one-shot

        if self.state_path and self.state_path.exists():
            self._load()

    # ---- test-only hooks (not part of BrokerInterface) ----

    def mark(
        self,
        symbol: str,
        close: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> List[Fill]:
        """Feed one price tick (a completed candle's close, with optional
        high/low). Checks every resting LIMIT/STOP order on `symbol` and
        fills whatever the tick crosses. Returns the Fills this tick
        produced (empty if none). This is the simulator's stand-in for a
        market-data feed — deliberately not on BrokerInterface (T65
        Section 3: market data is not the broker's job)."""
        high = self._last_price.get(symbol, close) if high is None else high
        high = max(high, close)
        low = close if low is None else low
        low = min(low, close)
        self._last_price[symbol] = close
        ts = timestamp or _now_iso()

        produced: List[Fill] = []
        for order_id in list(self._orders.keys()):
            order = self._orders[order_id]
            if order["symbol"] != symbol:
                continue
            if order["status"] not in (OrderStatus.WORKING.value, OrderStatus.PARTIAL.value):
                continue
            remaining = order["quantity"] - order["filled_quantity"]
            if remaining <= 0:
                continue

            fill_price = self._resting_fill_price(order, close, high, low)
            if fill_price is None:
                continue
            produced.append(self._execute_fill(order, remaining, fill_price, ts))

        self._persist()
        return produced

    def queue_partial_fill(self, ratio: float) -> None:
        """The next `place_order` call fills only `ratio` of the
        requested quantity (0 < ratio < 1); the remainder stays resting
        as PARTIAL, exactly like a real tranche order that only got some
        size done before price moved away. One-shot: consumed by the next
        `place_order` call only. Test-only — never on BrokerInterface."""
        if not (0.0 < ratio < 1.0):
            raise ValueError(f"partial-fill ratio must be in (0, 1), got {ratio}")
        self._queued_partial_ratio = ratio

    # ---- BrokerInterface ----

    def place_order(self, order: Order) -> OrderHandle:
        existing_id = self._idempotency_index.get(order.idempotency_key)
        if existing_id is not None:
            # Idempotent replay: same key, same order, return the original
            # handle rather than placing a second one (T65 Section 2.5/3).
            return self._handle_for(self._orders[existing_id])

        order_id = f"SIM-O-{self._next_order_id:06d}"
        self._next_order_id += 1
        record = {
            "broker_order_id": order_id,
            "idempotency_key": order.idempotency_key,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": order.quantity,
            "order_type": order.order_type.value,
            "limit_price": order.limit_price,
            "stop_price": order.stop_price,
            "time_in_force": order.time_in_force.value,
            "status": OrderStatus.WORKING.value,
            "filled_quantity": 0,
            "created_at": _now_iso(),
        }
        self._orders[order_id] = record
        self._idempotency_index[order.idempotency_key] = order_id

        fill_ratio = self._queued_partial_ratio
        self._queued_partial_ratio = None  # one-shot, consumed regardless of order type

        if order.order_type == OrderType.MARKET:
            price = self._last_price.get(order.symbol)
            if price is None:
                raise ValueError(
                    f"SimulatorBroker has no known price for {order.symbol!r} — "
                    f"call mark() before placing a MARKET order (the simulator "
                    f"has no market-data feed of its own, by design)."
                )
            qty = order.quantity if fill_ratio is None else max(1, int(order.quantity * fill_ratio))
            qty = min(qty, order.quantity)
            self._execute_fill(record, qty, price, _now_iso())
        elif fill_ratio is not None:
            # A resting LIMIT/STOP order can also be forced to partially
            # fill immediately at its own limit/stop price, for tests that
            # want a partial fill on a non-market order.
            price = order.limit_price if order.order_type == OrderType.LIMIT else order.stop_price
            if price is not None:
                qty = max(1, int(order.quantity * fill_ratio))
                self._execute_fill(record, min(qty, order.quantity), price, _now_iso())

        self._persist()
        return self._handle_for(record)

    def cancel_order(self, handle: OrderHandle) -> bool:
        record = self._orders.get(handle.broker_order_id)
        if record is None:
            return False
        if record["status"] in (OrderStatus.WORKING.value, OrderStatus.PARTIAL.value):
            record["status"] = OrderStatus.CANCELLED.value
            self._persist()
            return True
        return False  # already FILLED/CANCELLED/REJECTED — nothing to cancel

    def positions(self) -> List[Position]:
        # Ground truth is self._positions; zero-quantity entries are never
        # stored (see _execute_fill), so nothing here needs filtering.
        return [
            Position(symbol=sym, quantity=p["quantity"], avg_price=p["avg_price"])
            for sym, p in self._positions.items()
        ]

    def fills(self, since: Optional[str] = None) -> List[Fill]:
        rows = self._fills
        if since is not None:
            cutoff = self._fill_sort_key(since)
            rows = [f for f in rows if self._fill_sort_key(f["fill_id"]) > cutoff]
        return [self._fill_from_dict(f) for f in rows]

    def account(self) -> AccountSnapshot:
        return AccountSnapshot(
            account_number=self.account_number,
            cash_balance=round(self._cash_balance, 2),
            buying_power=round(self._cash_balance, 2),
        )

    # ---- internals ----

    @staticmethod
    def _fill_sort_key(fill_id: str) -> int:
        # "SIM-F-000042" -> 42; monotonic, so lexical cursor comparisons
        # would also work, but this is unambiguous.
        return int(fill_id.rsplit("-", 1)[-1])

    def _resting_fill_price(self, order: dict, close: float, high: float, low: float) -> Optional[float]:
        side = order["side"]
        otype = order["order_type"]
        if otype == OrderType.LIMIT.value:
            limit_price = order["limit_price"]
            if side == OrderSide.SELL.value and high >= limit_price:
                return limit_price  # a limit never fills worse than requested
            if side == OrderSide.BUY.value and low <= limit_price:
                return limit_price
            return None
        if otype == OrderType.STOP.value:
            stop_price = order["stop_price"]
            # Sell-stop (protective stop under a long): triggers if the
            # candle traded through the stop. Fill at `close`, not
            # `stop_price` — this is what makes a gap-through-the-stop
            # observable (T65 Section 2.4): a bad close prints a fill
            # materially worse than the requested stop level.
            if side == OrderSide.SELL.value and low <= stop_price:
                return close
            if side == OrderSide.BUY.value and high >= stop_price:
                return close
            return None
        return None  # MARKET orders never rest

    def _execute_fill(self, order: dict, quantity: int, price: float, timestamp: str) -> Fill:
        fill_id = f"SIM-F-{self._next_fill_id:06d}"
        self._next_fill_id += 1
        order["filled_quantity"] += quantity
        remaining = order["quantity"] - order["filled_quantity"]
        order["status"] = OrderStatus.FILLED.value if remaining <= 0 else OrderStatus.PARTIAL.value

        fill_row = {
            "fill_id": fill_id,
            "broker_order_id": order["broker_order_id"],
            "symbol": order["symbol"],
            "side": order["side"],
            "quantity": quantity,
            "price": price,
            "timestamp": timestamp,
        }
        self._fills.append(fill_row)
        self._apply_to_position(order["symbol"], order["side"], quantity, price)
        self._apply_to_cash(order["side"], quantity, price)
        return self._fill_from_dict(fill_row)

    def _apply_to_position(self, symbol: str, side: str, quantity: int, price: float) -> None:
        signed = quantity if side == OrderSide.BUY.value else -quantity
        pos = self._positions.get(symbol, {"quantity": 0, "avg_price": 0.0})
        old_qty, old_avg = pos["quantity"], pos["avg_price"]
        new_qty = old_qty + signed

        if old_qty == 0 or (old_qty > 0) == (signed > 0):
            # Opening or adding to a position in the same direction:
            # weighted-average the price.
            total_cost = old_avg * abs(old_qty) + price * abs(signed)
            new_avg = total_cost / abs(new_qty) if new_qty != 0 else 0.0
        else:
            # Reducing (or flipping through) the position: avg price of
            # what remains is unchanged unless it flips sides entirely.
            new_avg = old_avg if (new_qty == 0 or (new_qty > 0) == (old_qty > 0)) else price

        if new_qty == 0:
            # THE ONE INVARIANT test_broker.py checks directly: a flat
            # position is never reported by positions() at all, not as a
            # zero-quantity row.
            self._positions.pop(symbol, None)
        else:
            self._positions[symbol] = {"quantity": new_qty, "avg_price": round(new_avg, 4)}

    def _apply_to_cash(self, side: str, quantity: int, price: float) -> None:
        notional = price * quantity * self.contract_multiplier
        self._cash_balance += -notional if side == OrderSide.BUY.value else notional

    def _handle_for(self, record: dict) -> OrderHandle:
        return OrderHandle(
            broker_order_id=record["broker_order_id"],
            idempotency_key=record["idempotency_key"],
            status=OrderStatus(record["status"]),
            filled_quantity=record["filled_quantity"],
        )

    def _fill_from_dict(self, row: dict) -> Fill:
        return Fill(
            fill_id=row["fill_id"],
            broker_order_id=row["broker_order_id"],
            symbol=row["symbol"],
            side=OrderSide(row["side"]),
            quantity=row["quantity"],
            price=row["price"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    # ---- persistence (T65 Section 2.5: broker is the source of truth) ----

    def _persist(self) -> None:
        if not self.state_path:
            return
        snapshot = {
            "account_number": self.account_number,
            "contract_multiplier": self.contract_multiplier,
            "cash_balance": self._cash_balance,
            "orders": self._orders,
            "idempotency_index": self._idempotency_index,
            "fills": self._fills,
            "positions": self._positions,
            "last_price": self._last_price,
            "next_order_id": self._next_order_id,
            "next_fill_id": self._next_fill_id,
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: a crash mid-write must never leave a truncated,
        # unparseable state file behind for the next restart to trip over.
        fd, tmp_name = tempfile.mkstemp(dir=str(self.state_path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2)
            os.replace(tmp_name, self.state_path)
        except BaseException:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise

    def _load(self) -> None:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.account_number = data.get("account_number", self.account_number)
        self.contract_multiplier = data.get("contract_multiplier", self.contract_multiplier)
        self._cash_balance = data.get("cash_balance", self._cash_balance)
        self._orders = data.get("orders", {})
        self._idempotency_index = data.get("idempotency_index", {})
        self._fills = data.get("fills", [])
        self._positions = data.get("positions", {})
        self._last_price = data.get("last_price", {})
        self._next_order_id = data.get("next_order_id", 1)
        self._next_fill_id = data.get("next_fill_id", 1)
