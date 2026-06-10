"""Options-native signal output: strike, expiration, premium-based entry/stop/target.

Workflow:
  1. Stock signal fires → stock_entry, stock_stop, direction
  2. Pick nearest expiration (0DTE if early in day, else next trading day)
  3. Pick nearest ATM strike (round to symbol's increment)
  4. Fetch live option mid from Alpaca options snapshot (free tier = 15-min delayed)
  5. Estimate stop premium = entry_premium - (stock_risk × delta_estimate)
  6. Contracts = floor(max_loss / ((entry - stop) × 100))
"""

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional, Literal


CONTRACT_MULTIPLIER = 100
DEFAULT_MAX_LOSS = 1000.0
DEFAULT_RR = 2.0
DEFAULT_DELTA = 0.5  # ATM ≈ 0.5

# Per-symbol strike increment (USD)
# Initial-guess only — fetch_option_snapshot queries ±$5 range and picks closest
# actual contract, so this matters mostly for fallback estimation mode.
STRIKE_INCREMENT = {
    "TSLA": 5.0,   # $433
    "NVDA": 2.5,   # $215
    "AAPL": 2.5,   # $308
    "AMD": 5.0,    # $504
    "MSFT": 5.0,   # $415
    "GOOG": 2.5,   # $385
    "META": 5.0,   # $611
    "AMZN": 2.5,   # $265
    "PLTR": 1.0,   # $137
    "SPY": 1.0,    # $750
    "QQQ": 1.0,    # $729
}


@dataclass
class OptionsPlan:
    """Concrete options trade card for Discord."""
    symbol: str
    direction: Literal["call", "put"]
    expiration: str            # "YYYY-MM-DD"
    strike: float
    entry_premium: float
    stop_premium: float
    target_premium: float
    contracts: int
    max_loss: float
    max_reward: float
    # Reference stock levels for context
    stock_entry: float
    stock_stop: float
    stock_target: float
    # Quote quality
    quote_source: str  # "alpaca_mid" or "estimated_delta"
    occ_symbol: str

    def format_discord(self) -> str:
        arrow = "↑" if self.direction == "call" else "↓"
        right = "CALL" if self.direction == "call" else "PUT"
        dte = self._dte_label()
        return (
            f"**{self.symbol} {dte} ${self.strike:g} {right}** {arrow}\n"
            f"Expiration: {self.expiration}\n"
            f"Strike:     ${self.strike:g} (ATM)\n"
            f"Entry:      ${self.entry_premium:.2f}\n"
            f"Stop:       ${self.stop_premium:.2f}  (sell if drops here)\n"
            f"Target:     ${self.target_premium:.2f}  (sell all at 2R)\n"
            f"Contracts:  {self.contracts}  → max loss ${self.max_loss:.0f} / max reward ${self.max_reward:.0f}\n"
            f"Stock ref:  entry ${self.stock_entry:.2f} | stop ${self.stock_stop:.2f} | target ${self.stock_target:.2f}\n"
            f"Quote: {self.quote_source}"
        )

    def _dte_label(self) -> str:
        try:
            exp = datetime.strptime(self.expiration, "%Y-%m-%d").date()
            days = (exp - date.today()).days
            if days == 0:
                return "0DTE"
            return f"{days}DTE"
        except Exception:
            return ""


def nearest_strike(stock_price: float, symbol: str) -> float:
    inc = STRIKE_INCREMENT.get(symbol.upper(), 2.5)
    return round(stock_price / inc) * inc


def nearest_expiration(now: Optional[datetime] = None) -> str:
    """Pick 0DTE if before 14:30 ET, else next trading day.

    Note: NOT all symbols have daily expirations. TSLA & NVDA do.
    For others, you may get a 404 on snapshot — fallback handled in caller.
    """
    if now is None:
        now = datetime.now(timezone.utc) - timedelta(hours=4)  # approx ET
    today = now.date()
    # Before 14:30 ET, use today (0DTE has plenty of value left)
    cutoff = time(14, 30)
    if now.time() < cutoff and today.weekday() < 5:
        return today.isoformat()
    # Otherwise next weekday
    next_day = today + timedelta(days=1)
    while next_day.weekday() >= 5:  # skip weekend
        next_day += timedelta(days=1)
    return next_day.isoformat()


def build_options_plan(
    symbol: str,
    direction: Literal["call", "put"],
    stock_entry: float,
    stock_stop: float,
    alpaca_feed=None,           # AlpacaFeed instance, optional
    tasty_feed=None,            # TastytradeFeed instance, optional (preferred)
    max_loss: float = DEFAULT_MAX_LOSS,
    rr: float = DEFAULT_RR,
    delta_estimate: float = DEFAULT_DELTA,
    expiration: Optional[str] = None,
    strike: Optional[float] = None,
) -> OptionsPlan:
    """Build full options trade card.

    Premium sources (priority): Tastytrade (real-time) > Alpaca (15-min delayed) > delta estimate.
    """
    # 1. Stock-side risk/reward
    if direction == "call":
        if stock_stop >= stock_entry:
            raise ValueError(f"Call stop ({stock_stop}) must be below entry ({stock_entry})")
        stock_risk = stock_entry - stock_stop
        stock_target = stock_entry + rr * stock_risk
    else:
        if stock_stop <= stock_entry:
            raise ValueError(f"Put stop ({stock_stop}) must be above entry ({stock_entry})")
        stock_risk = stock_stop - stock_entry
        stock_target = stock_entry - rr * stock_risk

    # 2. Strike + expiration
    if strike is None:
        strike = nearest_strike(stock_entry, symbol)
    if expiration is None:
        expiration = nearest_expiration()

    # 3. Entry premium: Tastytrade (real-time) > Alpaca (delayed) > delta estimate
    quote_source = "estimated_delta"
    entry_premium = None
    occ_symbol = ""
    if tasty_feed is not None:
        try:
            snap = tasty_feed.fetch_option_quote(symbol, expiration, strike, direction)
            if snap and snap.get("mid"):
                entry_premium = snap["mid"]
                quote_source = "tastytrade_dxlink_realtime"
                occ_symbol = snap.get("occ_symbol", "")
                if snap.get("strike"):
                    strike = snap["strike"]
        except Exception as e:
            print(f"  tasty quote failed: {e}")
    if entry_premium is None and alpaca_feed is not None:
        try:
            snap = alpaca_feed.fetch_option_snapshot(symbol, expiration, strike, direction)
            if snap and snap.get("mid"):
                entry_premium = snap["mid"]
                quote_source = "alpaca_mid_15min_delayed"
                occ_symbol = snap.get("occ_symbol", "")
                if occ_symbol:
                    try:
                        strike = int(occ_symbol[-8:]) / 1000.0
                    except ValueError:
                        pass
        except Exception as e:
            print(f"  alpaca snapshot failed: {e}")

    if entry_premium is None:
        # Fallback: rough ATM 0DTE estimate.
        # ATM premium ≈ stock_price × 0.005 for 0DTE; scale up by delta + IV factor.
        # Use a conservative $1-3 range for $400-stock 0DTE.
        entry_premium = max(round(stock_entry * 0.005, 2), 0.50)

    # 4. Stop + target in PREMIUM terms
    # Stop = entry - (stock_risk × delta × multiplier)
    # Premium moves roughly delta × stock_move (per share, no multiplier)
    premium_risk = round(stock_risk * delta_estimate, 2)
    if premium_risk < 0.05:
        premium_risk = 0.05  # min tick guard

    stop_premium = round(max(entry_premium - premium_risk, 0.05), 2)
    target_premium = round(entry_premium + (rr * premium_risk), 2)

    # 5. Contracts
    per_contract_risk = (entry_premium - stop_premium) * CONTRACT_MULTIPLIER
    contracts = int(max_loss // per_contract_risk) if per_contract_risk > 0 else 0

    return OptionsPlan(
        symbol=symbol.upper(),
        direction=direction,
        expiration=expiration,
        strike=strike,
        entry_premium=entry_premium,
        stop_premium=stop_premium,
        target_premium=target_premium,
        contracts=contracts,
        max_loss=round(per_contract_risk * contracts, 2),
        max_reward=round(per_contract_risk * contracts * rr, 2),
        stock_entry=round(stock_entry, 2),
        stock_stop=round(stock_stop, 2),
        stock_target=round(stock_target, 2),
        quote_source=quote_source,
        occ_symbol=occ_symbol,
    )


if __name__ == "__main__":
    # Test without Alpaca (estimation only)
    plan = build_options_plan(
        symbol="TSLA",
        direction="call",
        stock_entry=440.50,
        stock_stop=439.80,
    )
    print(plan.format_discord())
    print()
    plan_put = build_options_plan(
        symbol="NVDA",
        direction="put",
        stock_entry=850.00,
        stock_stop=852.50,
    )
    print(plan_put.format_discord())
