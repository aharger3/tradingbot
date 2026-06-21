"""Tastytrade API feed for Vanquish signal bot.

Provides real-time option quotes, account data, market metrics, and 1-min
candle bars (all via DXLink — see dxlink.py). Tastytrade is the sole
data/broker integration as of 2026-06-13 (Alpaca removed).

Loads creds from .env.tastytrade (KEY=VALUE format).

Usage:
    from tastytrade_feed import TastytradeFeed
    feed = TastytradeFeed()
    feed.validate_credentials()
    snap = feed.fetch_option_quote("TSLA", "2026-06-12", 350.0, "call")
    balance = feed.get_balance()
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List

import requests

from vanquish_bot import Candle

# Force UTF-8 stdout/stderr so emoji/checkmark output (✓✗) don't crash with
# UnicodeEncodeError when run under Windows/PowerShell (cp1252 pipes).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _load_tastytrade_env(path: Path) -> None:
    """Load .env.tastytrade into os.environ."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_tastytrade_env(Path(__file__).parent / ".env.tastytrade")


API_BASE = "https://api.tastyworks.com"
TOKEN_ENDPOINT = f"{API_BASE}/oauth/token"
USER_AGENT = "vanquish-trading-bot/1.0"


class TastytradeFeed:
    """Tastytrade market data + account info. Throws on auth failure."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        account_number: Optional[str] = None,
    ):
        self.client_id = client_id or os.getenv("CLIENT_ID")
        self.client_secret = client_secret or os.getenv("CLIENT_SECRET")
        self.refresh_token = refresh_token or os.getenv("REFRESH_TOKEN")
        self.account_number = account_number or os.getenv("ACCOUNT_NUMBER")
        self._access_token: Optional[str] = None
        self._access_token_expiry: Optional[datetime] = None
        self._dxlink_token: Optional[dict] = None
        self._dxlink_token_expiry: Optional[datetime] = None
        self._chain_cache: dict = {}

    # ---- Auth ----

    def _get_access_token(self) -> str:
        """Get valid access token, refreshing if expired."""
        if self._access_token and self._access_token_expiry:
            if datetime.now(timezone.utc) < self._access_token_expiry - timedelta(minutes=2):
                return self._access_token

        if not all([self.refresh_token, self.client_id, self.client_secret]):
            raise ValueError(
                "Tastytrade creds missing. Set CLIENT_ID, CLIENT_SECRET, "
                "REFRESH_TOKEN in .env.tastytrade."
            )

        resp = requests.post(
            TOKEN_ENDPOINT,
            json={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            self._access_token = data["access_token"]
            self._access_token_expiry = datetime.now(timezone.utc) + timedelta(
                seconds=data.get("expires_in", 900)
            )
            return self._access_token

        raise RuntimeError(
            f"Tastytrade token refresh failed: HTTP {resp.status_code}"
        )

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, **kwargs) -> requests.Response:
        resp = requests.get(f"{API_BASE}{path}", headers=self._headers(), **kwargs)
        return resp

    # ---- Account ----

    def get_accounts(self) -> list[dict]:
        """List trading accounts."""
        resp = self._get("/customers/me/accounts", timeout=10)
        resp.raise_for_status()
        return resp.json().get("data", {}).get("items", [])

    def get_balance(self) -> dict:
        """Get account balance. Requires account_number."""
        if not self.account_number:
            return {"error": "No account_number set"}
        resp = self._get(f"/accounts/{self.account_number}/balances", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("data", {})
        return {"error": f"HTTP {resp.status_code}"}

    def get_positions(self) -> list[dict]:
        """Get current positions."""
        if not self.account_number:
            return []
        resp = self._get(f"/accounts/{self.account_number}/positions", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("data", {}).get("items", [])
        return []

    # ---- Market Metrics (IV, Greeks) ----

    def get_market_metrics(self, symbol: str) -> Optional[dict]:
        """Get IV, Greeks for a symbol."""
        resp = self._get(f"/market-metrics/{symbol}", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("data", {})
        return None

    # ---- Option Chains ----

    def get_option_chain(self, symbol: str) -> Optional[dict]:
        """Get full nested option chain (expirations → strikes → OCC symbols)."""
        resp = self._get(f"/option-chains/{symbol}/nested", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("data", {})
        return None

    # ---- Streaming Data (via DXLink / api-quote-tokens) ----

    def get_dxlink_token(self) -> Optional[dict]:
        """Get DXLink streaming token + websocket url.

        Uses GET /api-quote-tokens (the OAuth-compatible DXLink endpoint).
        NOTE: the legacy GET /quote-streamer-tokens returns 403 "insufficient
        scopes" for OAuth bearer tokens — that endpoint is the old CometD
        streamer and is not usable with OAuth. /api-quote-tokens is the
        correct DXLink endpoint. Token is valid ~24h, so cache it.

        Returns {"token": str, "url": str} or None.
        """
        if self._dxlink_token and self._dxlink_token_expiry:
            if datetime.now(timezone.utc) < self._dxlink_token_expiry - timedelta(minutes=5):
                return self._dxlink_token

        resp = self._get("/api-quote-tokens", timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json().get("data", {})
        token, url = data.get("token"), data.get("dxlink-url")
        if not token or not url:
            return None
        self._dxlink_token = {"token": token, "url": url}
        # expires-at like "2026-06-11T20:07:16.297+00:00"; fall back to 23h.
        try:
            exp = datetime.fromisoformat(data["expires-at"])
            self._dxlink_token_expiry = exp
        except (KeyError, ValueError):
            self._dxlink_token_expiry = datetime.now(timezone.utc) + timedelta(hours=23)
        return self._dxlink_token

    def _resolve_contract(
        self, symbol: str, expiration: str, strike: float, option_type: str
    ) -> Optional[dict]:
        """Resolve the chain strike record closest to `strike` on `expiration`
        ('YYYY-MM-DD'). Returns {"streamer","occ","strike"} or None.
        """
        chain = self._cached_chain(symbol)
        if not chain:
            return None
        streamer_field = "call-streamer-symbol" if option_type == "call" else "put-streamer-symbol"
        occ_field = "call" if option_type == "call" else "put"
        for underlying in chain.get("items", []):
            for exp in underlying.get("expirations", []):
                if exp.get("expiration-date") != expiration:
                    continue
                best, best_dist = None, None
                for s in exp.get("strikes", []):
                    try:
                        sp = float(s.get("strike-price"))
                    except (TypeError, ValueError):
                        continue
                    dist = abs(sp - strike)
                    if best_dist is None or dist < best_dist:
                        best, best_dist = s, dist
                if best:
                    return {
                        "streamer": best.get(streamer_field),
                        "occ": best.get(occ_field),
                        "strike": float(best.get("strike-price")),
                    }
        return None

    def _cached_chain(self, symbol: str) -> Optional[dict]:
        """Option chain cached per symbol for the process lifetime."""
        symbol = symbol.upper()
        if symbol not in self._chain_cache:
            self._chain_cache[symbol] = self.get_option_chain(symbol)
        return self._chain_cache[symbol]

    def fetch_option_quote(
        self, symbol: str, expiration: str, strike: float, option_type: str
    ) -> Optional[dict]:
        """Fetch real-time bid/ask/mid for one option via DXLink.

        Returns {"bid","ask","mid","strike","occ_symbol","streamer_symbol",
        "source"} or None.
        """
        contract = self._resolve_contract(symbol, expiration, strike, option_type)
        if not contract or not contract.get("streamer"):
            return None
        tok = self.get_dxlink_token()
        if not tok:
            return None
        from dxlink import fetch_quotes
        streamer = contract["streamer"]
        quotes = fetch_quotes(tok["url"], tok["token"], [streamer], timeout=8)
        q = quotes.get(streamer)
        if not q:
            return None
        return {
            **q,
            "strike": contract["strike"],
            "occ_symbol": (contract.get("occ") or "").strip(),
            "streamer_symbol": streamer,
            "source": "tastytrade_dxlink",
        }

    # ---- Validation ----

    def validate_credentials(self) -> bool:
        """Test credentials. Prints status. Returns True if OK."""
        try:
            token = self._get_access_token()
            print(f"  ✓ Access token obtained (starts with: {token[:10]}...)")
            accounts = self.get_accounts()
            print(f"  ✓ Connected. {len(accounts)} account(s).")
            for a in accounts:
                acct = a.get("account", {})
                num = acct.get("account-number", "?")
                nick = acct.get("nickname", "no nickname")
                print(f"    Account: {num} ({nick})")
            if self.account_number:
                bal = self.get_balance()
                if "error" not in bal:
                    cash = bal.get("cash-balance", "N/A")
                    print(f"    Cash balance: ${cash}")
            return True
        except Exception as e:
            print(f"  ✗ Tastytrade: {e}")
            return False

    # ---- Candle History (via DXLink Candle events) ----

    def fetch_recent_bars(self, symbol: str, lookback_minutes: int = 60) -> List[Candle]:
        """Fetch recent 1-min candles via DXLink Candle events.

        *** NEW / UNTESTED-AGAINST-LIVE-API (2026-06-13) ***
        Replaces the old stub (which always returned [] and relied on
        Alpaca as the real bar source — Alpaca is now removed entirely).
        Uses dxlink.fetch_candles() with contract="HISTORY" and a
        `fromTime` lookback window. See dxlink.py for protocol details
        and caveats. The REST endpoint /market-data/history/{symbol}
        previously returned 429s with unclear params, so this goes
        through the same DXLink websocket used for option quotes.

        Returns [] (not an exception) if the dxlink token can't be
        obtained or no candle data comes back — caller logs
        "only 0 bars, skipping" for the symbol in that case.
        """
        tok = self.get_dxlink_token()
        if not tok:
            return []
        from dxlink import fetch_candles
        from_time_ms = int(
            (datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)).timestamp() * 1000
        )
        try:
            raw = fetch_candles(tok["url"], tok["token"], symbol.upper(), from_time_ms, timeout=10)
        except Exception as e:
            print(f"  [{symbol}] dxlink candle fetch failed: {e}")
            return []

        candles: List[Candle] = []
        for c in raw:
            ts = datetime.fromtimestamp(c["time"] / 1000, tz=timezone.utc) - timedelta(hours=4)  # approx ET
            try:
                candles.append(Candle(
                    timestamp=ts.strftime("%H:%M:%S"),
                    open=float(c["open"]),
                    high=float(c["high"]),
                    low=float(c["low"]),
                    close=float(c["close"]),
                    volume=int(c.get("volume") or 0),
                ))
            except (TypeError, ValueError):
                continue
        return candles

    def fetch_bars_for_date(self, symbol: str, date_str: str, timeout: float = 10.0) -> List[Candle]:
        """Fetch 1-min candles for a specific past session (YYYY-MM-DD, ET).

        Unlike fetch_recent_bars (which fetches "last N minutes from now"),
        this sets `fromTime` to midnight ET on `date_str` so the DXLink
        Candle backfill actually covers that date, then keeps only the
        candles whose (approx-ET) date matches `date_str` — discarding any
        earlier/later days included in the backfill/live stream. Used by
        backtest_window.py to replay a specific historical session.

        Returns [] (not an exception) on bad date_str, missing token, or no
        matching candles.
        """
        tok = self.get_dxlink_token()
        if not tok:
            return []
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return []

        from dxlink import fetch_candles
        # Midnight ET on the target date, expressed as UTC epoch ms.
        # (Same UTC-4/ET approximation used elsewhere in this file.)
        from_dt = datetime(target_date.year, target_date.month, target_date.day,
                            tzinfo=timezone.utc) + timedelta(hours=4)
        from_time_ms = int(from_dt.timestamp() * 1000)

        try:
            raw = fetch_candles(tok["url"], tok["token"], symbol.upper(), from_time_ms, timeout=timeout)
        except Exception as e:
            print(f"  [{symbol}] dxlink candle fetch failed: {e}")
            return []

        candles: List[Candle] = []
        for c in raw:
            ts = datetime.fromtimestamp(c["time"] / 1000, tz=timezone.utc) - timedelta(hours=4)  # approx ET
            if ts.date() != target_date:
                continue
            try:
                candles.append(Candle(
                    timestamp=ts.strftime("%H:%M:%S"),
                    open=float(c["open"]),
                    high=float(c["high"]),
                    low=float(c["low"]),
                    close=float(c["close"]),
                    volume=int(c.get("volume") or 0),
                ))
            except (TypeError, ValueError):
                continue
        return candles


if __name__ == "__main__":
    feed = TastytradeFeed()
    ok = feed.validate_credentials()
    if ok:
        print()
        metrics = feed.get_market_metrics("TSLA")
        if metrics:
            print(f"TSLA IV: {float(metrics.get('implied-volatility-index', 0)):.1%}")
        chain = feed.get_option_chain("TSLA")
        if chain:
            items = chain.get("items", {})
            exps = list(items.keys())[:3]
            print(f"TSLA option chain expirations: {exps}")
        pos = feed.get_positions()
        print(f"Open positions: {len(pos)}")
