"""Options-native signal output: strike, expiration, premium-based entry/stop/target.

Workflow:
  1. Stock signal fires → stock_entry, stock_stop, direction
  2. Pick nearest expiration (0DTE if early in day, else next trading day)
  3. Pick nearest ATM strike (round to symbol's increment)
  4. Fetch live option mid from Tastytrade DXLink (real-time)
  5. Estimate stop premium = entry_premium - (stock_risk × delta_estimate)
  6. Contracts = floor(max_loss / ((entry - stop) × 100))
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional, Literal, List


CONTRACT_MULTIPLIER = 100
DEFAULT_MAX_LOSS = 1000.0
DEFAULT_RR = 2.0
DEFAULT_DELTA = 0.5  # ATM ≈ 0.5

# Grade → fraction of max loss to risk (SPEC2). C = alert-only, D = filtered upstream.
GRADE_SIZE_PCT = {"A+": 1.0, "A": 0.8, "B": 0.6, "C": 0.4, "D": 0.0}

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
    quote_source: str  # "tastytrade_dxlink_realtime" or "estimated_delta"
    occ_symbol: str
    bid_ask_spread: float = 0.0
    option_warnings: List[str] = field(default_factory=list)

    def format_discord(self) -> str:
        arrow = "↑" if self.direction == "call" else "↓"
        right = "CALL" if self.direction == "call" else "PUT"
        dte = self._dte_label()
        lines = (
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
        if self.bid_ask_spread > 0:
            lines += f"\nSpread:     ${self.bid_ask_spread:.2f}"
        if self.option_warnings:
            lines += f"\n⚠ {', '.join(self.option_warnings)}"
        return lines

    def _dte_label(self) -> str:
        try:
            exp = datetime.strptime(self.expiration, "%Y-%m-%d").date()
            days = (exp - date.today()).days
            if days == 0:
                return "0DTE"
            return f"{days}DTE"
        except Exception:
            return ""


# OPUS-SPEC #6: Scarface contract selection (2026-07-12)
# Scarface buys the FIRST OTM strike on the nearest WEEKLY (Friday) expiry, not
# nearest-ATM 0DTE. Prior: nearest_strike + nearest_expiration always. Change:
# toggle routes strike/expiry through first_otm_strike/weekly_expiration.
# Default OFF: ATM/0DTE is the measured baseline; flip after a live premium
# comparison (OTM weekly = lower delta, cheaper premium, different sizing).
SCARFACE_CONTRACT = False  # True = first OTM strike + nearest Friday expiration


def nearest_strike(stock_price: float, symbol: str) -> float:
    inc = STRIKE_INCREMENT.get(symbol.upper(), 2.5)
    return round(stock_price / inc) * inc


def first_otm_strike(stock_price: float, symbol: str, direction: str) -> float:
    """OPUS-SPEC #6: first strike strictly beyond spot in the trade direction."""
    inc = STRIKE_INCREMENT.get(symbol.upper(), 2.5)
    base = round(stock_price / inc) * inc
    if direction == "call":
        return base + inc if base <= stock_price else base
    return base - inc if base >= stock_price else base


def weekly_expiration(now: Optional[datetime] = None) -> str:
    """OPUS-SPEC #6: nearest Friday (this week's weekly; today if Friday)."""
    if now is None:
        now = datetime.now(timezone.utc) - timedelta(hours=4)  # approx ET
    d = now.date()
    return (d + timedelta(days=(4 - d.weekday()) % 7)).isoformat()


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
    tasty_feed=None,            # TastytradeFeed instance, optional (preferred)
    max_loss: float = DEFAULT_MAX_LOSS,
    rr: float = DEFAULT_RR,
    delta_estimate: float = DEFAULT_DELTA,
    expiration: Optional[str] = None,
    strike: Optional[float] = None,
) -> OptionsPlan:
    """Build full options trade card.

    Premium sources (priority): Tastytrade (real-time) > delta estimate.
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

    # 2. Strike + expiration (OPUS-SPEC #6: Scarface = first OTM weekly)
    if strike is None:
        strike = (first_otm_strike(stock_entry, symbol, direction) if SCARFACE_CONTRACT
                  else nearest_strike(stock_entry, symbol))
    if expiration is None:
        expiration = weekly_expiration() if SCARFACE_CONTRACT else nearest_expiration()

    # 3. Entry premium: Tastytrade (real-time) > delta estimate
    quote_source = "estimated_delta"
    entry_premium = None
    occ_symbol = ""
    bid_ask_spread = 0.0
    option_warnings = []
    if tasty_feed is not None:
        try:
            snap = tasty_feed.fetch_option_quote(symbol, expiration, strike, direction)
            if snap and snap.get("mid"):
                entry_premium = snap["mid"]
                quote_source = "tastytrade_dxlink_realtime"
                occ_symbol = snap.get("occ_symbol", "")
                if snap.get("strike"):
                    strike = snap["strike"]
                # Spread check
                bid = snap.get("bid", 0) or 0
                ask = snap.get("ask", 0) or 0
                if bid and ask:
                    bid_ask_spread = round(ask - bid, 2)
                    if bid_ask_spread > 0.50:
                        option_warnings.append("wide spread")
        except Exception as e:
            print(f"  tasty quote failed: {e}")

    if entry_premium is None:
        # Fallback: rough ATM 0DTE estimate.
        entry_premium = max(round(stock_entry * 0.005, 2), 0.50)

    # Post-premium filters
    if entry_premium < 0.20:
        option_warnings.append("too cheap")
    if occ_symbol and occ_symbol.startswith(" "):
        option_warnings.append("no liquidity")

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
        bid_ask_spread=bid_ask_spread,
        option_warnings=option_warnings,
    )


if __name__ == "__main__":
    # Test without Tastytrade (estimation only)
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


# ---------------------------------------------------------------------------
# Futures (Omen futures mode) — SPEC15
# ---------------------------------------------------------------------------

@dataclass
class FuturesPlan:
    """Concrete futures trade card for Discord. Price-level stops, no premium."""
    contract: str              # "ES", "NQ", "RTY"
    direction: Literal["long", "short"]
    entry: float
    stop: float
    target: float
    contracts: int
    point_value: float
    max_loss: float
    max_reward: float

    def format_discord(self) -> str:
        arrow = "↑" if self.direction == "long" else "↓"
        return (
            f"**{self.contract} {self.direction.upper()}** {arrow} (futures)\n"
            f"Entry:      {self.entry:g}\n"
            f"Stop:       {self.stop:g}  ({abs(self.entry - self.stop):g} pts)\n"
            f"Target:     {self.target:g}  (2R)\n"
            f"Contracts:  {self.contracts}  → max loss ${self.max_loss:.0f} / max reward ${self.max_reward:.0f}\n"
            f"Point val:  ${self.point_value:.0f}/pt per contract"
        )


def build_futures_plan(
    contract: str,
    direction: Literal["long", "short"],
    entry: float,
    stop: float,
    grade: str = "A",
    max_loss: float = DEFAULT_MAX_LOSS,
    rr: float = DEFAULT_RR,
) -> FuturesPlan:
    """Size a futures trade: contracts = floor(grade-scaled max loss / $risk per contract).

    ES $50/pt, NQ $20/pt, RTY $50/pt. Same A-D grade scaling as options
    (C sizes at 40% but stays alert-only upstream; D never reaches here).
    """
    from futures_feed import POINT_VALUE, TICK_SIZE

    contract = contract.upper()
    point_value = POINT_VALUE[contract]
    tick = TICK_SIZE[contract]

    if direction == "long":
        if stop >= entry:
            raise ValueError(f"Long stop ({stop}) must be below entry ({entry})")
        risk_pts = entry - stop
        target = entry + rr * risk_pts
    else:
        if stop <= entry:
            raise ValueError(f"Short stop ({stop}) must be above entry ({entry})")
        risk_pts = stop - entry
        target = entry - rr * risk_pts

    if risk_pts < tick:
        raise ValueError(f"Stop distance {risk_pts} under one tick ({tick})")

    budget = max_loss * GRADE_SIZE_PCT.get(grade, 0.0)
    per_contract_risk = risk_pts * point_value
    contracts = int(budget // per_contract_risk)

    return FuturesPlan(
        contract=contract,
        direction=direction,
        entry=entry,
        stop=stop,
        target=round(target / tick) * tick,
        contracts=contracts,
        point_value=point_value,
        max_loss=round(per_contract_risk * contracts, 2),
        max_reward=round(per_contract_risk * contracts * rr, 2),
    )
