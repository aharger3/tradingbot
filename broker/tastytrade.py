"""broker/tastytrade.py — BrokerInterface adapter for Tastytrade, SANDBOX ONLY.

SECURITY CONSTRAINT (Austin, 2026-08-24): this adapter is authorized against
the sandbox / certification environment only. It never reads
TASTYTRADE_USERNAME, TASTYTRADE_PASSWORD, or TASTYTRADE_REMEMBER_TOKEN — those
are the production credentials `tastytrade_feed.py` uses, and this file must
never touch them, log them, or fall back to them. Sandbox credentials are a
*separate* Tastytrade account (register at https://developer.tastytrade.com/
sandbox/) and are read only from TASTYTRADE_SANDBOX_* environment variables.
As of this writing those variables are not present anywhere in this repo's
.env — no sandbox account has been provisioned yet. That is why nothing in
this file is exercised (imported-and-instantiated, yes; ever actually called
over the network) by research/test_broker.py or by any other code path this
task touches. Provisioning a sandbox account and validating the request/
response shapes below against a live sandbox call is follow-up work, not done
here (see module-level NOTE comments for exactly which shapes are unverified).

WHY sandbox-vs-production is a hard-coded module constant plus a guard, not a
config flag: T65 Section 1 separates "the adapter is correct" from "the
strategy is proven," on purpose, specifically so a working broker adapter
never becomes the thing that tempts turning on real money early. A guard that
can be silently pointed at production by passing a different string defeats
that separation; `_assert_sandbox_host` runs in `__init__` regardless of what
`base_url` is passed, so there is no code path that constructs a
TastytradeBroker against a production host.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

import requests

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

# ---------------------------------------------------------------------------
# The sandbox/cert base URL, and only the sandbox/cert base URL.
# Confirmed 2026-08-24 against Tastytrade's public developer docs
# (developer.tastytrade.com/sandbox/) — NOT verified by an actual
# authenticated call in this task (no sandbox credentials exist yet, and
# Austin's constraint forbids exercising this file with production creds
# as a substitute).
# ---------------------------------------------------------------------------
SANDBOX_BASE_URL = "https://api.cert.tastyworks.com"

# Known production hosts — `tastytrade_feed.py` uses api.tastytrade.com;
# Tastytrade's docs also reference api.tastyworks.com (no "cert." prefix) as
# a production alias. Both are explicitly refused here.
_PRODUCTION_HOSTS = {"api.tastytrade.com", "api.tastyworks.com"}

USER_AGENT = "omen-trading-bot-broker/1.0 (sandbox-only)"


def _assert_sandbox_host(base_url: str) -> None:
    """Raises if `base_url` is not the sandbox/cert host. Called from
    __init__ unconditionally — this is the guard T65 Section 1 requires:
    nothing constructs a working adapter pointed at production."""
    host = (urlparse(base_url).hostname or "").lower()
    if host in _PRODUCTION_HOSTS or "cert" not in host:
        raise RuntimeError(
            f"TastytradeBroker refuses base_url={base_url!r}: only the "
            f"sandbox/cert host ({SANDBOX_BASE_URL}) is authorized. Austin's "
            f"instruction (2026-08-24): sandbox/certification ONLY, never "
            f"production. This is not configurable around."
        )


class TastytradeSandboxCredentialsMissing(RuntimeError):
    """Raised when no TASTYTRADE_SANDBOX_* credential is available.

    Deliberately a distinct exception type, not a generic RuntimeError: per
    Austin's instruction, the correct behavior when sandbox credentials do
    not exist is to STOP and say so — never to fall back to
    TASTYTRADE_USERNAME/PASSWORD/REMEMBER_TOKEN. Catching this specific type
    should never be "paper over it with production creds"; the only correct
    handler is "go provision a sandbox account."
    """


class TastytradeBroker(BrokerInterface):
    """Tastytrade sandbox adapter. See module docstring: unauthenticated and
    unexercised over the network as of this task — no sandbox credentials
    exist in this repo.

    Auth: either a pre-obtained sandbox session token
    (TASTYTRADE_SANDBOX_SESSION_TOKEN — the safer option, since it avoids
    holding a sandbox password in this process at all) or sandbox
    username/password (TASTYTRADE_SANDBOX_USERNAME /
    TASTYTRADE_SANDBOX_PASSWORD), read only from those exact env var names.
    Never reads TASTYTRADE_USERNAME, TASTYTRADE_PASSWORD, or
    TASTYTRADE_REMEMBER_TOKEN under any circumstance.
    """

    def __init__(
        self,
        base_url: str = SANDBOX_BASE_URL,
        account_number: Optional[str] = None,
        session_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        _assert_sandbox_host(base_url)
        self.base_url = base_url

        self.session_token = session_token or os.getenv("TASTYTRADE_SANDBOX_SESSION_TOKEN")
        self.username = username or os.getenv("TASTYTRADE_SANDBOX_USERNAME")
        self.password = password or os.getenv("TASTYTRADE_SANDBOX_PASSWORD")
        self.account_number = account_number or os.getenv("TASTYTRADE_SANDBOX_ACCOUNT_NUMBER")

        if not self.session_token and not (self.username and self.password):
            raise TastytradeSandboxCredentialsMissing(
                "No sandbox credentials found. Expected TASTYTRADE_SANDBOX_"
                "SESSION_TOKEN, or TASTYTRADE_SANDBOX_USERNAME + "
                "TASTYTRADE_SANDBOX_PASSWORD, in the environment. Per "
                "Austin's instruction: the sandbox needs its own credentials "
                "that do not currently exist in this repo's .env — do NOT "
                "fall back to TASTYTRADE_USERNAME/PASSWORD (those are "
                "production). Register a sandbox user at "
                "https://developer.tastytrade.com/sandbox/ and set the "
                "TASTYTRADE_SANDBOX_* variables before constructing this "
                "class."
            )

        self._access_token: Optional[str] = self.session_token

    # ---- auth ----

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        # NOTE (unverified — see module docstring): POST /sessions with
        # {"login", "password"} is the same shape tastytrade_feed.py uses
        # against production; assumed identical in sandbox per Tastytrade's
        # docs, not confirmed by a live call.
        resp = requests.post(
            f"{self.base_url}/sessions",
            json={"login": self.username, "password": self.password, "remember-me": False},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        if resp.status_code != 201:
            raise RuntimeError(f"Tastytrade sandbox session auth failed: HTTP {resp.status_code} {resp.text[:200]}")
        data = resp.json().get("data", {})
        self._access_token = data.get("session-token")
        if not self.account_number:
            accts = self._get("/customers/me/accounts").json().get("data", {}).get("items", [])
            if accts:
                self.account_number = accts[0].get("account", {}).get("account-number")
        return self._access_token or ""

    def _headers(self) -> dict:
        return {
            "Authorization": f"Token {self._get_access_token()}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, **kwargs) -> requests.Response:
        resp = requests.get(f"{self.base_url}{path}", headers=self._headers(), timeout=10, **kwargs)
        resp.raise_for_status()
        return resp

    def _require_account(self) -> str:
        if not self.account_number:
            self._get_access_token()  # populates account_number as a side effect
        if not self.account_number:
            raise RuntimeError("TastytradeBroker has no account_number and could not discover one.")
        return self.account_number

    # ---- BrokerInterface ----

    def place_order(self, order: Order) -> OrderHandle:
        # NOTE (unverified — see module docstring): this order-body shape
        # (time-in-force / order-type / price / price-effect / legs with
        # instrument-type+symbol+quantity+action) matches Tastytrade's
        # publicly documented JSON:API order schema, not confirmed live.
        acct = self._require_account()
        action = self._infer_action(order)
        leg = {
            "instrument-type": "Equity Option",
            "symbol": order.symbol,
            "quantity": order.quantity,
            "action": action,
        }
        body = {
            "time-in-force": "Day" if order.time_in_force.value == "day" else "GTC",
            "order-type": {"market": "Market", "limit": "Limit", "stop": "Stop"}[order.order_type.value],
            "legs": [leg],
        }
        if order.order_type == OrderType.LIMIT and order.limit_price is not None:
            body["price"] = order.limit_price
            body["price-effect"] = "Debit" if order.side == OrderSide.BUY else "Credit"
        if order.order_type == OrderType.STOP and order.stop_price is not None:
            body["stop-trigger"] = order.stop_price

        resp = requests.post(
            f"{self.base_url}/accounts/{acct}/orders",
            json=body,
            headers={**self._headers(), "X-Idempotency-Key": order.idempotency_key},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            return OrderHandle(
                broker_order_id="",
                idempotency_key=order.idempotency_key,
                status=OrderStatus.REJECTED,
                filled_quantity=0,
            )
        data = resp.json().get("data", {}).get("order", {})
        return OrderHandle(
            broker_order_id=str(data.get("id", "")),
            idempotency_key=order.idempotency_key,
            status=self._map_status(data.get("status", "")),
            filled_quantity=int(data.get("size", 0)) - int(data.get("remaining-quantity", data.get("size", 0))),
        )

    def cancel_order(self, handle: OrderHandle) -> bool:
        acct = self._require_account()
        resp = requests.delete(
            f"{self.base_url}/accounts/{acct}/orders/{handle.broker_order_id}",
            headers=self._headers(),
            timeout=10,
        )
        return resp.status_code in (200, 204)

    def positions(self) -> List[Position]:
        acct = self._require_account()
        items = self._get(f"/accounts/{acct}/positions").json().get("data", {}).get("items", [])
        out = []
        for item in items:
            qty = float(item.get("quantity", 0) or 0)
            if qty == 0:
                continue  # never report a position not actually held
            direction = item.get("quantity-direction", "Long")
            signed_qty = qty if direction == "Long" else -qty
            out.append(
                Position(
                    symbol=item.get("symbol", ""),
                    quantity=int(signed_qty),
                    avg_price=float(item.get("average-open-price", 0) or 0),
                )
            )
        return out

    def fills(self, since: Optional[str] = None) -> List[Fill]:
        # NOTE (unverified — see module docstring): /accounts/{acct}/transactions
        # filtered to transaction-type=Trade is Tastytrade's documented fill
        # history endpoint; the `start-at` query param name and its exact
        # ISO-8601 format are assumed from public docs, not confirmed live.
        acct = self._require_account()
        params = {"transaction-types[]": "Trade"}
        if since is not None:
            params["start-at"] = since
        items = self._get(f"/accounts/{acct}/transactions", params=params).json().get("data", {}).get("items", [])
        out = []
        for item in items:
            action = item.get("action", "")
            side = OrderSide.BUY if "Buy" in action else OrderSide.SELL
            out.append(
                Fill(
                    fill_id=str(item.get("id", "")),
                    broker_order_id=str(item.get("order-id", "")),
                    symbol=item.get("symbol", ""),
                    side=side,
                    quantity=int(abs(float(item.get("quantity", 0) or 0))),
                    price=float(item.get("price", 0) or 0),
                    timestamp=self._parse_ts(item.get("executed-at")),
                )
            )
        return out

    def account(self) -> AccountSnapshot:
        acct = self._require_account()
        data = self._get(f"/accounts/{acct}/balances").json().get("data", {})
        return AccountSnapshot(
            account_number=acct,
            cash_balance=float(data.get("cash-balance", 0) or 0),
            # NOTE (unverified): field name assumed from tastytrade_feed.py's
            # sibling usage; Tastytrade exposes several buying-power fields
            # (equity vs. derivative) and which one gates an options order
            # has not been confirmed against a live sandbox response.
            buying_power=float(data.get("derivative-buying-power", data.get("cash-balance", 0)) or 0),
        )

    # ---- internals ----

    @staticmethod
    def _infer_action(order: Order) -> str:
        # NOTE: a fully correct Buy-to-Open vs Buy-to-Close (etc.)
        # determination requires checking the current position for this
        # symbol first (positions() is available but this keeps place_order
        # to one extra call at most, and is unexercised/unverified in this
        # task regardless). BUY is assumed opening, SELL is assumed closing
        # — the common case for OMEN's long-options-only ladder. A short
        # position (Sell to Open) is out of scope for Phase 1.
        return "Buy to Open" if order.side == OrderSide.BUY else "Sell to Close"

    @staticmethod
    def _map_status(raw: str) -> OrderStatus:
        table = {
            "Received": OrderStatus.WORKING,
            "Routed": OrderStatus.WORKING,
            "Live": OrderStatus.WORKING,
            "Partially Filled": OrderStatus.PARTIAL,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "Rejected": OrderStatus.REJECTED,
        }
        return table.get(raw, OrderStatus.WORKING)

    @staticmethod
    def _parse_ts(raw: Optional[str]) -> datetime:
        if not raw:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
