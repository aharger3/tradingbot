"""Omen Trading Bot - Signal Detection Engine"""

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

    # Engulfing patterns appear in NONE of the 4 Scarface rulebooks — removed
    # from grading (hallucination audit 2026-07-11). Kept only for legacy scripts.
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
        htf_bias: Optional[str] = None,
    ) -> TradeGrade:
        """Grade a potential signal A+ through D (D = skip).

        htf_bias ('bullish'/'bearish'/'neutral'/None) gates the top grades:
        opposed trend = D (counter-trend, course says skip); neutral caps at
        B (A+/A require HTF alignment per fable_rules); None = unknown,
        grade on PA alone (pre-SPEC0 behavior).
        """
        if htf_bias in ("bullish", "bearish"):
            aligned = (htf_bias == "bullish") == is_long
            if not aligned:
                return TradeGrade.D
        base = PriceActionAnalyzer._grade_pa(candle, lookback_candles, or_high, or_low, is_long)
        if htf_bias == "neutral" and base in (TradeGrade.A_PLUS, TradeGrade.A):
            return TradeGrade.B
        return base

    @staticmethod
    def _grade_pa(
        candle: Candle,
        lookback_candles: List[Candle],
        or_high: float,
        or_low: float,
        is_long: bool,
    ) -> TradeGrade:
        # Check if candle is at a key level (OR high for long, OR low for short)
        at_key_level = (candle.low <= or_high if is_long else candle.high >= or_low)

        if is_long:
            if not candle.is_bullish:
                return TradeGrade.D
            # A+: hammer at key level
            if (at_key_level and PriceActionAnalyzer.is_hammer_stick(candle, lookback_candles)):
                return TradeGrade.A_PLUS
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


DISPLACEMENT_MULT = 1.5  # break-leg body vs avg prior body (Scarface: skip slow/hesitant breaks)


def _has_displacement(candles: List[Candle], block_idx: int, break_idx: int, direction: str) -> bool:
    """The leg away from the order block must be a momentum move: largest
    same-direction candle body in the leg >= DISPLACEMENT_MULT x the average
    body of the 10 candles before the block."""
    prior = candles[max(0, block_idx - 10):block_idx]
    if not prior:
        return False
    avg_body = sum(c.body_size for c in prior) / len(prior)
    if avg_body == 0:
        return True
    leg = candles[block_idx + 1:break_idx + 1]
    bodies = [c.body_size for c in leg
              if (c.is_bullish if direction == "bullish" else c.is_bearish)]
    return bool(bodies) and max(bodies) >= DISPLACEMENT_MULT * avg_body


def _is_isolated(candles: List[Candle], block_idx: int) -> bool:
    """Austin 2026-07-06: valid OB candle is "isolated from the volume and
    liquidity and price action that comes before it" — first-glance obvious.
    Reject when >1 of the 4 prior candles overlaps the block's body."""
    block = candles[block_idx]
    b_lo = min(block.open, block.close)
    b_hi = max(block.open, block.close)
    prior = candles[max(0, block_idx - 4):block_idx]
    if not prior:
        return True
    overlap = sum(1 for c in prior if not (c.high < b_lo or c.low > b_hi))
    return overlap <= 1


def detect_order_block_setup(candles: List[Candle], direction: str = "bullish"):
    """Return (block, retest_type, note). block is None when no valid setup."""
    structure = MarketStructure()
    structure.update(candles)
    blocks = structure.get_valid_order_blocks(candles, direction)
    if not blocks:
        return None, None, "No valid order block (or structure broken)"
    block = blocks[0]
    # Displacement gate: locate the block/break indices the same way
    # get_valid_order_blocks did, then require momentum in the leg between them.
    break_idx = (structure.last_hh if direction == "bullish" else structure.last_ll)[2]
    block_idx = next(i for i in range(break_idx - 1, -1, -1)
                     if (candles[i].is_bearish if direction == "bullish" else candles[i].is_bullish))
    if not _is_isolated(candles, block_idx):
        return None, None, "Order block not isolated (consolidation), skipped"
    if not _has_displacement(candles, block_idx, break_idx, direction):
        return None, None, "No displacement - slow/hesitant break, skipped"
    retest = check_retest_type(block, candles[-1], direction)
    if retest == "not_retesting":
        return None, None, "Price not at order block"
    return block, retest, f"Order block retest: {retest}"


def find_fvg(candles: List[Candle], direction: str = "bullish", lookback: int = 15):
    """Most recent Fair Value Gap in the last `lookback` candles, or None.

    Bullish FVG: candle[i].high < candle[i+2].low — the untraded gap left by a
    displacement move. Returns (gap_lo, gap_hi). Gap is invalid once any later
    candle closes through its far side (filled).
    """
    lo_i = max(0, len(candles) - lookback)
    best = None
    for i in range(lo_i, len(candles) - 2):
        a, c = candles[i], candles[i + 2]
        if direction == "bullish" and a.high < c.low:
            zone = (a.high, c.low)
        elif direction == "bearish" and a.low > c.high:
            zone = (c.high, a.low)
        else:
            continue
        # filled = a later close beyond the far edge of the gap
        after = candles[i + 3:]
        if direction == "bullish" and any(x.close < zone[0] for x in after):
            continue
        if direction == "bearish" and any(x.close > zone[1] for x in after):
            continue
        best = zone  # keep scanning: most recent valid gap wins
    return best


# Flag / continuation setup (Austin 2026-07-08): #3 most-traded setup in the
# 181-review dataset (22 hits) and the only pro setup OMEN had no detector for.
# A flag = sharp directional "pole", then a tight low-range pause that holds
# most of the pole, then a breakout the SAME direction. Unlike break-and-retest
# there's no fixed horizontal level — the trigger is the top/bottom of the pause.
# ponytail: percentage thresholds are the calibration knobs; real tape varies by
# symbol/vol regime — tune on the labeled set, don't trust these defaults blind.
POLE_MIN_PCT = 0.006       # pole net move >= 0.6%
POLE_LEN = 5               # candles forming the pole
FLAG_LEN_RANGE = (2, 5)    # pause length to search
FLAG_RANGE_MAX_PCT = 0.005  # pause total range <= 0.5% of price (tight)
FLAG_MAX_RETRACE = 0.5     # pause holds >= half the pole


def detect_flag_setup(candles: List[Candle], direction: str = "bullish"):
    """Return (info, note). info is None when no valid flag breakout on the last
    candle. info = {flag_hi, flag_lo, pole_move} on a fire."""
    bull = direction == "bullish"
    if len(candles) < POLE_LEN + FLAG_LEN_RANGE[0] + 1:
        return None, "not enough candles"
    current = candles[-1]
    for flag_len in range(FLAG_LEN_RANGE[0], FLAG_LEN_RANGE[1] + 1):
        flag = candles[-1 - flag_len:-1]                       # pause, excl. breakout
        pole = candles[-1 - flag_len - POLE_LEN:-1 - flag_len]  # run before pause
        if len(flag) < flag_len or len(pole) < POLE_LEN:
            continue
        pole_start, pole_end = pole[0].open, pole[-1].close
        if pole_start <= 0:
            continue
        pole_move = (pole_end - pole_start) / pole_start
        if (pole_move if bull else -pole_move) < POLE_MIN_PCT:
            continue                                            # pole too weak/wrong way
        flag_hi = max(c.high for c in flag)
        flag_lo = min(c.low for c in flag)
        if (flag_hi - flag_lo) / current.close > FLAG_RANGE_MAX_PCT:
            continue                                            # pause not tight
        pole_size = abs(pole_end - pole_start)
        retrace = (pole_end - flag_lo) if bull else (flag_hi - pole_end)
        if pole_size > 0 and retrace / pole_size > FLAG_MAX_RETRACE:
            continue                                            # pause gave back too much
        broke = (current.close > flag_hi and current.is_bullish) if bull \
            else (current.close < flag_lo and current.is_bearish)
        if broke:
            pct = (pole_move if bull else -pole_move) * 100
            return ({"flag_hi": flag_hi, "flag_lo": flag_lo, "pole_move": pole_move},
                    f"{'Bull' if bull else 'Bear'} flag: {flag_len}-bar pause after {pct:.1f}% pole")
    return None, "no flag"


def detect_break_retest(candles: List[Candle], level: float, is_long: bool,
                        window: int = 12, max_confirm_gap: int = 3,
                        out: Optional[dict] = None):
    """Austin's ORDERED break-and-retest (2026-07-09). Returns a note str if the
    LAST candle is a valid entry, else None.

    The sequence must happen in this order inside the window (presence-in-window
    is NOT enough — that let chop-on-the-level and no-return breaks fire):
      1. BREAK   — a candle closes through the level (crossing from the other side)
      2. LEAVE   — a later candle fully clears the level (long: low > level;
                   short: high < level) — price actually left, didn't chop on it
      3. RETEST  — a still-later candle comes back to touch the level
      4. CONFIRM — the current candle closes back through the level, within
                   max_confirm_gap bars of the retest (immediate retest = gap 0)
    A failed break (falls back through before leaving) resets to step 1.
    PA/grade is judged by the caller; this only enforces the geometry.
    """
    if len(candles) < 4:
        return None
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level:
        return None
    if not is_long and cur.close >= level:
        return None

    # Austin 2026-07-10 (11-04 review): close AT the level / clearing by a hair
    # is not a break or displacement. Buffer = 10% of avg window candle range.
    eps = 0.10 * (sum(c.high - c.low for c in w) / len(w))

    # Austin 2026-07-10 (07-30, 10-09): entry candle with a big wick AGAINST the
    # trade (short w/ long lower wick, long w/ long upper wick) = buyers/sellers
    # already fighting back — not an entry.
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size:
        return None

    state, retest_idx = "seek_break", None
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed:
                state = "seek_leave"
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left:
                state = "seek_retest"
            elif failed:
                state = "seek_break"          # break fizzled, look for a new one
        elif state == "seek_retest":
            back = (c.low <= level) if is_long else (c.high >= level)
            if back:
                retest_idx, state = i, "hold"
        elif state == "hold":                 # retest found; take the latest touch
            back = (c.low <= level) if is_long else (c.high >= level)
            if back:
                retest_idx = i

    if retest_idx is None:
        return None
    if (len(w) - 1) - retest_idx > max_confirm_gap:
        return None                            # retest too stale vs the entry candle

    # Austin 2026-07-10 (07-30, 10-08, 11-06 + brain dump): if the level was
    # already broken earlier in the session (before this window), the level is
    # "dirty" and this is a LATE entry — he wants the FIRST clean break of the
    # day. Tag it (caller downgrades; kept in data for the clean-vs-late A/B).
    prior = candles[:-window]
    late = sum(1 for a, b in zip(prior, prior[1:])
               if (a.close - level) * (b.close - level) < 0)
    tag = f" | LATE({late} prior breaks)" if late else ""
    if out is not None:
        # F2 stop-placement A/B: caller may place the stop at the retest
        # candle's extreme ("stop at the break of the candle that came back
        # for the retest" — yt EIIiEtAEm3s) instead of exactly at the level
        out["retest_low"], out["retest_high"] = w[retest_idx].low, w[retest_idx].high
    return (f"break {'up' if is_long else 'down'} → cleared → retest "
            f"{len(w)-1-retest_idx} bar(s) back → confirm close{tag}")


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
        # 84% rule context: direction + original stop/target of the stopped-out trade
        self.entry_direction: Optional[str] = None
        self.entry_target: Optional[float] = None
        self.entry_stop: Optional[float] = None
        self.entry_time: Optional[str] = None
        self.is_active_trade = False
        self.stop_loss: Optional[float] = None
        self.take_profit_levels: List[float] = []

    def day_ended(self) -> bool:
        """Trading day ends after 2 consecutive losses or max signals.
        (The 11:00 cutoff is enforced by live_scanner's window / backtest
        ENTRY_CUTOFF, not here.)"""
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

    print("=== Omen Bot Signal Detection ===\n")

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
