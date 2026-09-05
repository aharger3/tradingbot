"""broker/alpaca.py — BrokerInterface adapter for Alpaca, PAPER ONLY (L3, OMEN 9.0).

SECURITY CONSTRAINT (spec L3, 2026-09-05): this adapter is authorized against
the Alpaca PAPER trading endpoint only. `alpaca.trading.client.TradingClient`
is constructed with `paper=True` as a literal, hard-coded argument — never a
variable, never read from config or `.env` — so there is no code path in this
file that can be pointed at the live endpoint by changing an environment
variable. `TradingClient(paper=True)` resolves internally to the Alpaca SDK's
paper-trading base URL (its `BaseURL.TRADING_PAPER` constant); this file
never spells out the live-trading host's hostname anywhere in source, which
is exactly what `broker/test_alpaca_paper.py` and the L3 verify gate check
for (a zero-count grep for that hostname's literal text in this file).

Credentials: `ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET` from `.env`, read once
in `__init__`. Never logged, never printed, never included in an exception
message (`_redact` strips them out of anything that might echo a key back).

Reads `broker/base.py`'s five-call BrokerInterface (place/cancel/positions/
fills/account) exactly like `broker/tastytrade.py` does. `place_order`
resolves the option contract via `resolve_option_contract` first; if it can't
resolve one (no listed contract, or options not enabled on this paper
account), it falls back to a share order and stamps `fallback=shares` on the
returned handle's idempotency_key-adjacent log line (`live_scanner.py` logs
it, not this file — this file only raises `OptionsNotAvailable` so the caller
can decide what "fallback" means for its own order-shape).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional

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


class OptionsNotAvailable(Exception):
    """Raised by resolve_option_contract when no contract can be resolved,
    or the paper account has no options trading level. Callers (live_scanner)
    catch this and fall back to a share order sized to 1R."""


def _redact(msg: str) -> str:
    """Strip anything that looks like the loaded API key/secret out of a
    string before it can reach a log line or an exception traceback."""
    key = os.environ.get("ALPACA_PAPER_KEY", "")
    secret = os.environ.get("ALPACA_PAPER_SECRET", "")
    for secretish in (key, secret):
        if secretish and secretish in msg:
            msg = msg.replace(secretish, "***REDACTED***")
    return msg


def _status_map(alpaca_status) -> OrderStatus:
    s = str(getattr(alpaca_status, "value", alpaca_status)).lower()
    if s in ("filled",):
        return OrderStatus.FILLED
    if s in ("partially_filled",):
        return OrderStatus.PARTIAL
    if s in ("canceled", "cancelled", "expired"):
        return OrderStatus.CANCELLED
    if s in ("rejected",):
        return OrderStatus.REJECTED
    return OrderStatus.WORKING


class AlpacaBroker(BrokerInterface):
    """BrokerInterface adapter against Alpaca's PAPER trading API.

    `TradingClient(..., paper=True)` is the ONLY way this class ever
    constructs a client — that argument is a Python literal in this file,
    never threaded through from a caller, so nothing outside this module can
    flip it to live trading.
    """

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        from alpaca.trading.client import TradingClient

        key = api_key or os.environ.get("ALPACA_PAPER_KEY")
        secret = secret_key or os.environ.get("ALPACA_PAPER_SECRET")
        if not key or not secret:
            raise RuntimeError(
                "AlpacaBroker: ALPACA_PAPER_KEY/ALPACA_PAPER_SECRET not set in .env"
            )
        # paper=True is a hard-coded literal -- see module docstring.
        self._client = TradingClient(api_key=key, secret_key=secret, paper=True)

    # ------------------------------------------------------------------
    # option contract resolution
    # ------------------------------------------------------------------
    def resolve_option_contract(
        self,
        underlying: str,
        expiration: str,
        strike: float,
        direction: str,  # "call" | "put"
    ) -> str:
        """Return the OCC-format contract symbol Alpaca lists for these
        terms, or raise OptionsNotAvailable if none is listed (or the
        request itself fails, e.g. options not enabled on this account)."""
        from alpaca.trading.enums import ContractType
        from alpaca.trading.requests import GetOptionContractsRequest

        contract_type = ContractType.CALL if direction == "call" else ContractType.PUT
        req = GetOptionContractsRequest(
            underlying_symbols=[underlying],
            expiration_date=expiration,
            type=contract_type,
            strike_price_gte=str(strike),
            strike_price_lte=str(strike),
            limit=5,
        )
        try:
            resp = self._client.get_option_contracts(req)
        except Exception as e:  # noqa: BLE001 - surface as our own type
            raise OptionsNotAvailable(_redact(str(e))) from e
        contracts = getattr(resp, "option_contracts", None) or []
        if not contracts:
            raise OptionsNotAvailable(
                f"no listed contract for {underlying} {expiration} {strike:g} {direction}"
            )
        return contracts[0].symbol

    # ------------------------------------------------------------------
    # BrokerInterface
    # ------------------------------------------------------------------
    def place_order(self, order: Order) -> OrderHandle:
        from alpaca.trading.enums import OrderSide as AOrderSide
        from alpaca.trading.enums import TimeInForce as ATimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        side = AOrderSide.BUY if order.side == OrderSide.BUY else AOrderSide.SELL
        tif = ATimeInForce.DAY if order.time_in_force.value == "day" else ATimeInForce.GTC

        try:
            if order.order_type == OrderType.LIMIT:
                req = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=side,
                    time_in_force=tif,
                    limit_price=order.limit_price,
                    client_order_id=order.idempotency_key,
                )
            else:
                # MARKET and STOP both submit as market here: this file only
                # ever sends single-leg, day, market entries (spec L3); a stop
                # is managed by cancel/replace from the marking loop, not a
                # resting broker-side STOP order, because Alpaca does not
                # support native option stop orders in all cases and the
                # existing marking loop already owns that responsibility.
                req = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=side,
                    time_in_force=tif,
                    client_order_id=order.idempotency_key,
                )
            resp = self._client.submit_order(req)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(_redact(f"AlpacaBroker.place_order failed: {e}")) from e

        return OrderHandle(
            broker_order_id=str(resp.id),
            idempotency_key=order.idempotency_key,
            status=_status_map(resp.status),
            filled_quantity=int(float(resp.filled_qty or 0)),
        )

    def cancel_order(self, handle: OrderHandle) -> bool:
        try:
            self._client.cancel_order_by_id(handle.broker_order_id)
            return True
        except Exception as e:  # noqa: BLE001
            msg = _redact(str(e)).lower()
            if "already" in msg or "filled" in msg or "404" in msg:
                return False
            raise RuntimeError(_redact(f"AlpacaBroker.cancel_order failed: {e}")) from e

    def positions(self) -> List[Position]:
        out: List[Position] = []
        for p in self._client.get_all_positions():
            qty = float(p.qty)
            if qty == 0:
                continue
            out.append(Position(symbol=p.symbol, quantity=int(qty), avg_price=float(p.avg_entry_price)))
        return out

    def fills(self, since: Optional[str] = None) -> List[Fill]:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=100)
        orders = self._client.get_orders(req)
        out: List[Fill] = []
        for o in orders:
            filled_qty = float(o.filled_qty or 0)
            if filled_qty <= 0:
                continue
            if since is not None and str(o.id) == since:
                continue
            ts = o.filled_at or o.updated_at or datetime.now(timezone.utc)
            out.append(
                Fill(
                    fill_id=str(o.id),
                    broker_order_id=str(o.id),
                    symbol=o.symbol,
                    side=OrderSide.BUY if str(getattr(o.side, "value", o.side)) == "buy" else OrderSide.SELL,
                    quantity=int(filled_qty),
                    price=float(o.filled_avg_price or 0.0),
                    timestamp=ts,
                )
            )
        return out

    def account(self) -> AccountSnapshot:
        acct = self._client.get_account()
        return AccountSnapshot(
            account_number=str(acct.account_number),
            cash_balance=float(acct.cash),
            buying_power=float(acct.buying_power),
        )
