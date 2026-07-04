"""Vanquish Trading Bot - Signal Detection Engine"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class SignalType(Enum):
    BREAK_AND_RETEST = "break_and_retest"
    ONE_CANDLE_RULE = "one_candle_rule"
    REENTRY_84_RULE = "reentry_84_rule"
    NONE = "none"


class TradeGrade(Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass
class Candle:
    """Single 1-minute candle OHLCV data"""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


class PriceActionAnalyzer:
    """Detect price action patterns (hammers, strong wicks, etc)"""

    @staticmethod
    def is_hammer_stick(candle: Candle, lookback_candles: List[Candle]) -> bool:
        """
        Hammer: small body, large lower wick, sellers rejected, buyers reclaimed.
        Bullish hammer: close near high, large lower wick relative to body.
        """
        if not candle.is_bullish:
            return False

        body = candle.body_size
        lower_wick = candle.lower_wick

        # Hammer: lower wick 2x+ body size, close near high
        return lower_wick > body * 2 and (candle.high - candle.close) < body * 0.5

    @staticmethod
    def has_large_lower_wick(candle: Candle) -> bool:
        """Strong price action: large lower wick indicating rejection + buyers stepping in"""
        body = candle.body_size
        lower_wick = candle.lower_wick

        # Large wick: at least 1.5x body size
        return lower_wick > body * 1.5

    @staticmethod
    def is_strong_price_action(candle: Candle) -> bool:
        """Bullish candle with large lower wick OR hammer stick"""
        return candle.is_bullish and (
            PriceActionAnalyzer.has_large_lower_wick(candle) or
            PriceActionAnalyzer.is_hammer_stick(candle, [])
        )

    @staticmethod
    def is_inverted_hammer(candle: Candle) -> bool:
        """Bearish inverted hammer: large upper wick, close near low, buyers rejected."""
        if not candle.is_bearish:
            return False
        body = candle.body_size
        return candle.upper_wick > body * 2 and (candle.close - candle.low) < body * 0.5

    @staticmethod
    def has_large_upper_wick(candle: Candle) -> bool:
        """Sellers rejecting upper level — bearish strong price action."""
        body = candle.body_size
        return candle.upper_wick > body * 1.5

    @staticmethod
    def is_strong_bearish_price_action(candle: Candle) -> bool:
        """Bearish candle with large upper wick OR inverted hammer."""
        return candle.is_bearish and (
            PriceActionAnalyzer.has_large_upper_wick(candle) or
            PriceActionAnalyzer.is_inverted_hammer(candle)
        )

    @staticmethod
    def is_bullish_engulfing(candle: Candle, prev: Candle) -> bool:
        """Bullish engulfing: green body fully contains prior red body."""
        return (candle.is_bullish and prev.is_bearish
                and candle.open <= prev.close and candle.close >= prev.open)

    @staticmethod
    def is_bearish_engulfing(candle: Candle, prev: Candle) -> bool:
        """Bearish engulfing: red body fully contains prior green body."""
        return (candle.is_bearish and prev.is_bullish
                and candle.open >= prev.close and candle.close <= prev.open)

    @staticmethod
    def grade_trade(
        candle: Candle,
        lookback_candles: List[Candle],
        or_high: float,
        or_low: float,
        is_long: bool,
    ) -> TradeGrade:
        """Grade a potential signal A+ through D (D = skip)."""
        # Check if candle is at a key level (OR high for long, OR low for short)
        at_key_level = (candle.low <= or_high if is_long else candle.high >= or_low)

        if is_long:
            if not candle.is_bullish:
                return TradeGrade.D
            # A+: hammer at key level
            if (at_key_level and PriceActionAnalyzer.is_hammer_stick(candle, lookback_candles)):
                return TradeGrade.A_PLUS
            # A: bullish engulfing at key level
            if lookback_candles and PriceActionAnalyzer.is_bullish_engulfing(candle, lookback_candles[-1]) and at_key_level:
                return TradeGrade.A
            # B: strong PA at key level
            if at_key_level and PriceActionAnalyzer.has_large_lower_wick(candle):
                return TradeGrade.B
            # C: any bullish retest
            if candle.low <= or_high:
                return TradeGrade.C
            return TradeGrade.D
        else:
            if not candle.is_bearish:
                return TradeGrade.D
            # A+: inverted hammer at key level
            if (at_key_level and PriceActionAnalyzer.is_inverted_hammer(candle)):
                return TradeGrade.A_PLUS
            # A: bearish engulfing at key level
            if lookback_candles and PriceActionAnalyzer.is_bearish_engulfing(candle, lookback_candles[-1]) and at_key_level:
                return TradeGrade.A
            # B: strong bearish PA at key level
            if at_key_level and PriceActionAnalyzer.has_large_upper_wick(candle):
                return TradeGrade.B
            # C: any bearish retest
            if candle.high >= or_low:
                return TradeGrade.C
            return TradeGrade.D


class MarketStructure:
    """Track swing highs/lows across the session; locate structural order blocks.

    Order block = the LAST opposite-close candle before the leg that broke
    structure (made a higher high for bullish, lower low for bearish) — not
    any random red/green candle in a lookback window (SPEC3).
    """

    def __init__(self):
        self.swing_highs: List[tuple] = []  # (price, timestamp, index)
        self.swing_lows: List[tuple] = []
        self.last_hh: Optional[tuple] = None  # most recent swing high that broke a prior swing high
        self.last_ll: Optional[tuple] = None  # most recent swing low that broke a prior swing low

    def update(self, candles: List[Candle]) -> None:
        self.swing_highs, self.swing_lows = [], []
        self.last_hh, self.last_ll = None, None
        for i in range(1, len(candles) - 1):
            c = candles[i]
            if c.high > candles[i - 1].high and c.high > candles[i + 1].high:
                self.swing_highs.append((c.high, c.timestamp, i))
            if c.low < candles[i - 1].low and c.low < candles[i + 1].low:
                self.swing_lows.append((c.low, c.timestamp, i))
        for prev, cur in zip(self.swing_highs, self.swing_highs[1:]):
            if cur[0] > prev[0]:
                self.last_hh = cur
        for prev, cur in zip(self.swing_lows, self.swing_lows[1:]):
            if cur[0] < prev[0]:
                self.last_ll = cur

    def get_valid_order_blocks(self, candles: List[Candle], direction: str = "bullish") -> List[Candle]:
        """Most-recent-first order blocks whose structure is still intact."""
        blocks = []
        if direction == "bullish" and self.last_hh is not None:
            hh_idx = self.last_hh[2]
            for i in range(hh_idx - 1, -1, -1):
                if candles[i].is_bearish:
                    block = candles[i]
                    # Structure intact: nothing after the block closed below its low
                    if all(c.close >= block.low for c in candles[i + 1:]):
                        blocks.append(block)
                    break
        elif direction == "bearish" and self.last_ll is not None:
            ll_idx = self.last_ll[2]
            for i in range(ll_idx - 1, -1, -1):
                if candles[i].is_bullish:
                    block = candles[i]
                    if all(c.close <= block.high for c in candles[i + 1:]):
                        blocks.append(block)
                    break
        return blocks

    def is_structure_intact(self, candles: List[Candle], direction: str = "bullish") -> bool:
        return bool(self.get_valid_order_blocks(candles, direction))


def check_retest_type(block: Candle, candle: Candle, direction: str = "bullish") -> str:
    """Classify how the current candle retests the order block zone.

    wick_only is the strongest entry; full_body = weakest momentum (SPEC3).
    Returns: 'wick_only', 'partial_body', 'full_body', 'not_retesting'.
    """
    body_lo = min(candle.open, candle.close)
    body_hi = max(candle.open, candle.close)
    if direction == "bullish":
        if candle.low > block.high:
            return "not_retesting"
        if body_lo > block.high:
            return "wick_only"
        if body_hi > block.high:
            return "partial_body"
        return "full_body"
    else:
        if candle.high < block.low:
            return "not_retesting"
        if body_hi < block.low:
            return "wick_only"
        if body_lo < block.low:
            return "partial_body"
        return "full_body"


def detect_order_block_setup(candles: List[Candle], direction: str = "bullish"):
    """Return (block, retest_type, note). block is None when no valid setup."""
    structure = MarketStructure()
    structure.update(candles)
    blocks = structure.get_valid_order_blocks(candles, direction)
    if not blocks:
        return None, None, "No valid order block (or structure broken)"
    block = blocks[0]
    retest = check_retest_type(block, candles[-1], direction)
    if retest == "not_retesting":
        return None, None, "Price not at order block"
    return block, retest, f"Order block retest: {retest}"


class BreakAndRetestDetector:
    """Break and Retest Strategy: break level → retest with A+ confirmation"""

    @staticmethod
    def detect_breakout(
        candles: List[Candle],
        support_level: float,
        resistance_level: float,
        is_long: bool
    ) -> Optional[Candle]:
        """
        Detect if stock broke through level without touching it on return.
        is_long=True: looking for break above resistance_level
        is_long=False: looking for break below support_level
        """
        if len(candles) < 2:
            return None

        current = candles[-1]
        previous = candles[-2]

        if is_long:
            # Break above resistance: close above level, not touching on way down
            if current.close > resistance_level and previous.close <= resistance_level:
                return current
        else:
            # Break below support: close below level, not touching on way up
            if current.close < support_level and previous.close >= support_level:
                return current

        return None

    @staticmethod
    def detect_retest_entry(
        candles: List[Candle],
        breakout_candle: Candle,
        support_level: float,
        resistance_level: float,
        is_long: bool
    ) -> tuple[bool, Optional[str]]:
        """
        After breakout, detect retest with A+ confirmation (hammer or strong price action).
        Returns (is_valid_entry, reason)
        """
        if len(candles) < 3:
            return False, "Not enough candles to confirm retest"

        current = candles[-1]

        if is_long:
            # Retest: low touches resistance, close above it
            if current.low <= resistance_level and current.close > resistance_level:
                if PriceActionAnalyzer.is_strong_price_action(current):
                    return True, "A+ retest entry: strong price action at resistance"
                elif PriceActionAnalyzer.has_large_lower_wick(current):
                    return True, "A+ retest entry: large lower wick at resistance"
        else:
            # Retest: high touches support, close below it
            if current.high >= support_level and current.close < support_level:
                if PriceActionAnalyzer.is_strong_price_action(current):
                    return True, "A+ retest entry: strong price action at support"
                elif PriceActionAnalyzer.has_large_lower_wick(current):
                    return True, "A+ retest entry: large lower wick at support"

        return False, "Retest failed: weak price action"


class OneCandleRuleDetector:
    """One Candle Rule: use candle as support/resistance, break and retest"""

    @staticmethod
    def detect_entry(
        candles: List[Candle],
        reference_candle: Candle,
        is_long: bool
    ) -> tuple[bool, Optional[str]]:
        """
        Break away from reference candle, retest with strong price action.
        is_long=True: reference candle is red support
        is_long=False: reference candle is green resistance
        """
        if len(candles) < 2:
            return False, "Not enough candles"

        current = candles[-1]
        support_level = reference_candle.low
        resistance_level = reference_candle.high

        if is_long:
            # Retest red candle support with strong price action
            if current.low <= support_level and current.close > support_level:
                if PriceActionAnalyzer.is_strong_price_action(current):
                    return True, "One Candle Rule: strong retest at support"
        else:
            # Retest green candle resistance with strong price action
            if current.high >= resistance_level and current.close < resistance_level:
                if PriceActionAnalyzer.is_strong_price_action(current):
                    return True, "One Candle Rule: strong retest at resistance"

        return False, "One Candle Rule: weak retest"


class RuleOf84Detector:
    """84% Rule: re-entry at exact level after initial stop loss"""

    @staticmethod
    def detect_reentry(
        current_candle: Candle,
        entry_price: float,
        is_long: bool
    ) -> tuple[bool, Optional[str]]:
        """
        Detect if price reclaimed exact entry level (candle close).
        Returns (is_valid_reentry, reason)
        """
        if is_long:
            # Candle close at or above entry price
            if current_candle.close >= entry_price:
                return True, "84% Rule: price reclaimed entry level"
        else:
            # Candle close at or below entry price
            if current_candle.close <= entry_price:
                return True, "84% Rule: price reclaimed entry level"

        return False, "84% Rule: entry level not reclaimed"


class OpeningRangeAnalyzer:
    """Track 5-minute opening range (first 5 x 1-min candles)"""

    @staticmethod
    def get_opening_range(candles: List[Candle]) -> tuple[float, float]:
        """Get high/low of first 5 candles of day"""
        opening_candles = candles[:5]
        high = max(c.high for c in opening_candles)
        low = min(c.low for c in opening_candles)
        return high, low

    @staticmethod
    def is_outside_opening_range(
        current_price: float,
        opening_range_high: float,
        opening_range_low: float
    ) -> bool:
        """Check if price is outside opening range"""
        return current_price > opening_range_high or current_price < opening_range_low


class TradingSession:
    """Track daily trading state"""

    def __init__(self):
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.signals_today = 0
        self.max_signals_per_day = 3
        self.entry_price: Optional[float] = None
        self.entry_time: Optional[str] = None
        self.is_active_trade = False
        self.stop_loss: Optional[float] = None
        self.take_profit_levels: List[float] = []

    def day_ended(self) -> bool:
        """Trading day ends after max losses, max signals, or 11 AM"""
        return (self.consecutive_losses >= 2
                or self.signals_today >= self.max_signals_per_day)

    def record_loss(self):
        self.consecutive_losses += 1
        self.consecutive_wins = 0

    def record_win(self):
        self.consecutive_wins += 1
        self.consecutive_losses = 0

    def start_trade(self, entry_price: float, entry_time: str, stop_loss: float):
        self.is_active_trade = True
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.stop_loss = stop_loss

    def close_trade(self):
        self.is_active_trade = False


# Example usage & test
if __name__ == "__main__":
    # Sample candles for testing
    sample_candles = [
        Candle("09:30:00", 100.0, 101.5, 99.8, 101.0, 1000),
        Candle("09:31:00", 101.0, 102.0, 100.5, 101.5, 1200),
        Candle("09:32:00", 101.5, 102.5, 101.0, 102.0, 1100),
        Candle("09:33:00", 102.0, 103.0, 101.5, 102.5, 1300),
        Candle("09:34:00", 102.5, 103.5, 102.0, 103.0, 1400),
        # Consolidation
        Candle("09:35:00", 103.0, 103.2, 102.5, 102.8, 800),
        # Retest with hammer
        Candle("09:36:00", 102.8, 103.1, 101.8, 103.0, 1500),
    ]

    print("=== Vanquish Bot Signal Detection ===\n")

    # Check last candle for strong price action
    last = sample_candles[-1]
    print(f"Last candle: O={last.open}, H={last.high}, L={last.low}, C={last.close}")
    print(f"  Body: {last.body_size:.2f}, Lower wick: {last.lower_wick:.2f}")
    print(f"  Strong price action: {PriceActionAnalyzer.is_strong_price_action(last)}")
    print(f"  Is hammer: {PriceActionAnalyzer.is_hammer_stick(last, [])}\n")

    # Check opening range
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(sample_candles)
    print(f"Opening Range (first 5 candles): {or_low:.2f} - {or_high:.2f}")
    print(f"Current price {last.close:.2f} outside OR: {OpeningRangeAnalyzer.is_outside_opening_range(last.close, or_high, or_low)}\n")

    # Test session tracking
    session = TradingSession()
    session.record_loss()
    session.record_loss()
    print(f"Day ended after 2 losses: {session.day_ended()}")
