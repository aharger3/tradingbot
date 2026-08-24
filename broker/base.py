"""broker/base.py — the narrow broker interface (T65 Sections 2-3).

WHY this file exists: everything above this line — the state machine, the
kill switches, observability (not yet built; this is Phase 1 scope) — is
written once against these five calls and never imports a broker-specific
module directly. A venue swap (sandbox Tastytrade today, a different
broker tomorrow, shares vs. options vs. futures) becomes a config change
(pick a different BrokerInterface implementation), not a rewrite, because
the mess — auth, rate limits, contract lookup, margin checks, native
order types — lives inside each adapter and never leaks through this
surface. Deep module: simple surface, complexity hidden inside.

T65 Section 3 specifies four calls: place/cancel/positions/fills.
`account()` is the fifth, added because sizing (options_sizer.py) has to
read *something* about spendable cash before it can size an order, and
that read belongs on the broker interface rather than scattered into each
adapter's own ad-hoc accessor.

Deliberately NOT on this interface, and why leaving them out is correct
rather than an oversight (T65 Section 3):
- No `modify_order`. A stop move (e.g. breakeven-after-tranche-1) is
  cancel-then-replace everywhere in this system, so it behaves
  identically on a broker with no native "modify" verb, and the
  cancel/replace race (is the old stop still briefly live?) is a known,
  bounded problem instead of a broker-specific one.
- No `get_quote` / market-data calls. That is TastytradeFeed's job.
  Conflating "what is the market doing" with "what did I order" is
  exactly the scope creep a narrow interface exists to prevent.
- No venue-specific order types (OCO, bracket, trailing-stop) in any
  method signature. An adapter may translate a cancel/replace pattern
  into one native bracket order internally if the venue supports it —
  that is an internal optimization that must never change what these
  five calls look like from the caller's side.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class OrderType(str, Enum):
    """MARKET fills at whatever price is available now. LIMIT fills at
    the stated price or better. STOP is a resting order that becomes a
    market order once price trades through the stop level — this is the
    order type that protects an open position at rest. Per T65 Section 5
    switch #3's design note: a stop the local process only "watches" and
    sends when triggered is explicitly not good enough; it must already
    be resting at the broker as a STOP order."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TimeInForce(str, Enum):
    """DAY is the only value Phase 1 needs. The field exists because
    every real broker requires one on every order, not because the state
    machine varies it yet."""

    DAY = "day"
    GTC = "gtc"


class OrderStatus(str, Enum):
    """Maps 1:1 onto the T65 Section 2.1 state-machine states
    (ORDER_WORKING / PARTIAL_FILL / POSITION_OPEN / ORDER_CANCELLED /
    ORDER_REJECTED). Keeping the broker layer's status vocabulary
    identical to the state machine's vocabulary avoids a translation
    layer that could silently drop or reinterpret a status on the way
    from adapter to state machine."""

    WORKING = "working"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Order:
    """One order description — data, not a method-selection decision.

    `idempotency_key` exists specifically for crash recovery (T65
    Section 2.5, Section 3): if the calling process crashes after sending
    an order but before recording the ack, retrying `place_order` with
    the same key must not double-order. Whether the venue supports
    idempotency keys natively, or the adapter has to fake it with a
    pre-flight positions()/open-orders() check, is exactly the kind of
    complexity that belongs inside the adapter, invisible here.
    """

    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    idempotency_key: str
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY


@dataclass(frozen=True)
class OrderHandle:
    """What `place_order` hands back. `broker_order_id` is venue-native
    and opaque to the caller. `idempotency_key` echoes the request so the
    caller can confirm a retried `place_order` returned the *same* handle
    rather than silently creating a second order."""

    broker_order_id: str
    idempotency_key: str
    status: OrderStatus
    filled_quantity: int = 0


@dataclass(frozen=True)
class Position:
    """One symbol's net holding, signed (positive = long, negative =
    short). Returned only by `positions()`, which per T65 Section 3 must
    be the broker's own ground truth, never a cached mirror of what the
    adapter thinks it sent — this is the reconciliation primitive T65
    Section 2.5 builds crash recovery on. The local process converges to
    what this call reports; never the reverse."""

    symbol: str
    quantity: int
    avg_price: float


@dataclass(frozen=True)
class Fill:
    """One execution report. `fills(since=...)` is how the state machine
    learns which tranches filled, at what price, without polling
    `positions()` in a tight loop for something that is really an event
    feed (T65 Section 3)."""

    fill_id: str
    broker_order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime


@dataclass(frozen=True)
class AccountSnapshot:
    """Cash/buying-power context, read before `place_order` decides
    whether a sized order is even affordable. Not a full balances dump —
    only what the state machine actually needs to gate an order, so an
    adapter's richer venue-specific balance payload stays internal to the
    adapter."""

    account_number: str
    cash_balance: float
    buying_power: float


class BrokerInterface(abc.ABC):
    """The narrow surface T65 Section 3 designs the whole execution layer
    against. Every method here is a contract — what must be true of any
    implementation, not how any one venue happens to satisfy it.
    `broker/simulator.py` and `broker/tastytrade.py` are two answers to
    the same five questions; nothing outside `broker/` ever imports a
    concrete class directly, only this interface.
    """

    @abc.abstractmethod
    def place_order(self, order: Order) -> OrderHandle:
        """Submit `order`.

        WHY one call instead of place_market/place_limit/place_stop: the
        state machine decides *what* to order (T65 Section 3) — the
        order's shape is data the caller builds, not a method the caller
        selects per venue. The adapter's only job is placing it.

        Must be idempotent on `order.idempotency_key`: calling this twice
        with the same key (e.g. because the caller crashed and does not
        know whether the first call landed) returns the handle for the
        *original* order, and never places a second one. This is the
        specific mechanism T65 Section 2.5 / Section 3 requires to make
        crash recovery safe.

        Never promises a fill price (T65 Section 2.4) — a MARKET or STOP
        order's eventual fill price is discovered via `fills()`, not
        returned here. A gap through a stop level is exactly the case
        this distinction protects against: nothing in this interface may
        let a caller assume the price it requested is the price it got.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def cancel_order(self, handle: OrderHandle) -> bool:
        """Cancel the order `handle` refers to.

        Returns True if the cancel landed before any (further) fill,
        False otherwise ("not cancelled — probably filled, check
        `fills()`"). WHY a bool and nothing finer: every broker resolves
        the cancel/fill race (did the cancel beat an in-flight fill?)
        differently internally; the state machine only ever needs the
        binary answer, so resolving that race is the adapter's problem,
        not leaked venue-specific detail (T65 Section 3).

        This is also the mechanism behind every stop move in this
        system: moving a stop (e.g. breakeven-after-tranche-1, T65
        Section 2.2 step 5) is cancel-then-replace — call this, then
        `place_order` a new stop. Building the state machine around that
        pattern means it works identically on a broker with no native
        "modify" verb.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def positions(self) -> List[Position]:
        """Return every currently-open position, as the broker itself
        reports it — never a cache of what this process thinks it sent.

        WHY that distinction is load-bearing: this is the reconciliation
        primitive (T65 Section 2.5, Section 3.4). A crash-recovery
        reconcile against a cached mirror proves nothing; it can only
        ever agree with itself. Must never include a symbol at quantity
        zero — a position this process does not actually hold must not
        appear here.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def fills(self, since: Optional[str] = None) -> List[Fill]:
        """Return executions, optionally only those after `since` (a
        fill-id or timestamp cursor).

        WHY `since` exists: a restart needs to ask "what happened while I
        was down" as one call, not re-derive it by diffing two
        `positions()` snapshots — that diff is ambiguous (a position that
        went 30 to 18 could be one partial fill or two independent
        trades) in a way a real fill log never is.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def account(self) -> AccountSnapshot:
        """Return current cash/buying-power.

        WHY it is on this interface rather than folded into
        `positions()`: sizing needs to know what is spendable *before* it
        knows what is open, and conflating the two would force every
        caller to fetch and discard positions just to answer "can I
        afford this order."
        """
        raise NotImplementedError
