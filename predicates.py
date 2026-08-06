"""
Predicate functions for trading strategy rules.
Each function returns True if the condition is met, False otherwise.

Source of truth = rules/*.md (Austin's dictated paragraphs, 2026-07-31).
Fixed 2026-08-01 (5/8 tests were failing): see rules/PREDICATE-NOTES.md.
Refined 2026-08-01 (Austin review notes): displacement need not be the candle
immediately after the break, but the displacement candle must not touch the
level / order block / pivot being broken. Extra confluence if all three align.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
from statistics import median

@dataclass
class Candle:
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
    def range_size(self) -> float:
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


def is_break_and_retest(
    candles: List[Candle],
    level: float,
    direction: str,  # "call" for bullish, "put" for bearish
    lookback: int = 12,
    max_confirm_gap: int = 3
) -> bool:
    """
    Detect a break and retest (ordered: break -> displacement away -> retest -> entry).

    Austin (rules/break-and-retest.md): strong candle close through the level, a
    subsequent candle displaces away from it (not necessarily the very next one —
    Austin 2026-08-01: "doesn't have to be the next candle exactly that gives the
    displacement", but it must not be touching the level / order block / pivot;
    extra confluence if all three align), then a candle wicks back to the reference
    and closes back through it. That close is the entry.

    Args:
        candles: List of candles, most recent last. The last candle is the entry candle.
        level: The price level / pivot / order-block edge being broken and retested.
        direction: "call" for a bullish break, "put" for a bearish break.
        lookback: How many candles back the pattern may start.
        max_confirm_gap: Max candles allowed between the retest and the entry.
                         Austin: "if it takes too many candles probability decreases."

    Returns:
        True if a valid break and retest is found, False otherwise.
    """
    if len(candles) < 4:
        return False

    # +1 candle: the break candle needs its own predecessor in scope to prove price
    # actually crossed the level rather than merely opening on the far side of it.
    window = candles[-(lookback + 1):]
    if len(window) < 4:
        return False

    entry = window[-1]

    # Austin 2026-07-10: closing AT the level / clearing it by a hair is not a break.
    eps = 0.10 * (sum(c.range_size for c in window) / len(window))

    # The entry candle must itself confirm: close through the level in the trade's
    # direction, with no big wick against the trade (Austin 2026-07-10: an entry
    # candle with a large adverse wick is not an entry).
    if direction == "call":
        if not entry.is_bullish or entry.close <= level + eps:
            return False
        if entry.upper_wick > 1.5 * entry.body_size:
            return False
    else:  # put
        if not entry.is_bearish or entry.close >= level - eps:
            return False
        if entry.lower_wick > 1.5 * entry.body_size:
            return False

    # Ordered walk. The entry candle is the confirmation, so it is never counted as
    # the retest — the retest must be a strictly earlier candle.
    state = "seek_break"
    retest_idx = None

    for i in range(1, len(window) - 1):
        c, p = window[i], window[i - 1]

        if state == "seek_break":
            # BREAK: a candle closes through the level, coming from the other side.
            crossed = (p.close <= level and c.close > level + eps) if direction == "call" \
                else (p.close >= level and c.close < level - eps)
            if crossed:
                state = "seek_leave"

        elif state == "seek_leave":
            # DISPLACEMENT: a candle fully clears the level (no overlap back into it).
            # Austin 2026-08-01: need not be the candle right after the break — neutral
            # candles keep this state open. The displacement candle itself must NOT touch
            # the level (low > level+eps for calls), and a close back through resets.
            left = (c.low > level + eps) if direction == "call" else (c.high < level - eps)
            failed = (c.close <= level + eps) if direction == "call" else (c.close >= level - eps)
            if left:
                state = "seek_retest"
            elif failed:
                state = "seek_break"  # break fizzled, look for a fresh one

        elif state in ("seek_retest", "hold"):
            # RETEST: price wicks back and touches the broken reference.
            back = (c.low <= level) if direction == "call" else (c.high >= level)
            if back:
                retest_idx, state = i, "hold"  # keep the latest touch

    if retest_idx is None:
        return False

    # Austin: the retest should happen fast. A stale retest is a different trade.
    if (len(window) - 1) - retest_idx > max_confirm_gap:
        return False

    return True


def is_order_block(
    candles: List[Candle],
    direction: str,  # "call" for bullish OB, "put" for bearish OB
    lookback: int = 20
) -> Tuple[bool, Optional[Candle]]:
    """
    Identify the live order block and check price is still respecting it.

    Austin (rules/order-block.md): the last red candle before a bullish move (or the
    last green candle before a bearish move) whose body and wick define the zone price
    must hold. It is also where the stop goes.

    Args:
        candles: List of candles, most recent last.
        direction: "call" for a bullish OB, "put" for a bearish OB.
        lookback: How many candles back to search for the block.

    Returns:
        (is_respected, ob_candle). ob_candle is None when no block was found.
    """
    if len(candles) < 3:
        return False, None

    window = candles[-lookback:] if len(candles) > lookback else candles

    # Walk backwards — the most recent order block is the live one.
    ob = None
    for i in range(len(window) - 2, -1, -1):
        c, nxt = window[i], window[i + 1]
        # The move out of the block must be real displacement, not a doji drift.
        displaced = nxt.range_size > 0 and nxt.body_size > nxt.range_size * 0.6
        if not displaced:
            continue
        if direction == "call" and c.is_bearish and nxt.is_bullish:
            ob = c
            break
        if direction == "put" and c.is_bullish and nxt.is_bearish:
            ob = c
            break

    if ob is None:
        return False, None

    # Respected = price has not closed through the far side of the block.
    # Austin: a shallow tap and reject is high probability; all the way through is not.
    last = candles[-1]
    if direction == "call":
        return last.close > ob.low, ob
    return last.close < ob.high, ob


def is_84_reentry_opportunity(
    candles: List[Candle],
    original_entry_price: float,
    original_direction: str,  # "call" or "put"
    original_stop: float,
    lookback: int = 10
) -> bool:
    """
    Check for an 84% rule re-entry.

    Austin (rules/reentry-84.md): this is a RE-entry, never a standalone entry. The
    original stop has to have been hit first, and then price has to reclaim the
    original entry price with strength.

    Args:
        candles: List of candles, most recent last.
        original_entry_price: Entry price of the stopped-out trade.
        original_direction: "call" or "put" of the original trade.
        original_stop: Stop loss of the original trade.
        lookback: How many candles back to look for the stop-out and the reclaim.

    Returns:
        True if a re-entry opportunity is detected.
    """
    if len(candles) < 3:
        return False

    window = candles[-lookback:] if len(candles) > lookback else candles

    # 1. The original stop must actually have been hit. No stop-out, no 84% rule.
    #    Take the most recent stop-out; the reclaim has to come after it.
    stop_idx = None
    for i, c in enumerate(window):
        hit = (c.low <= original_stop) if original_direction == "call" \
            else (c.high >= original_stop)
        if hit:
            stop_idx = i
    if stop_idx is None:
        return False

    # 2. Reclaim of the original entry, with strength. Austin: price reclaims the
    #    level and in the final 10 seconds looks like a strong close through it —
    #    approximated on closed bars as a body of at least half the candle's range.
    for i in range(stop_idx + 1, len(window)):
        c = window[i]
        strong = c.range_size > 0 and c.body_size >= c.range_size * 0.5
        if not strong:
            continue
        if original_direction == "call" and c.close >= original_entry_price and c.is_bullish:
            return True
        if original_direction == "put" and c.close <= original_entry_price and c.is_bearish:
            return True

    return False


def is_chop_market(
    candles: List[Candle],
    threshold: int = 10,
    body_threshold: float = 0.3
) -> bool:
    """
    Detect chop: consecutive small-body candles.

    Austin (rules/x-reject.md): "10 or 11 chop candles is the threshold. Chop candles
    = a lot of consolidation, sitting between one or two levels, or liquidity sweeps."

    Args:
        candles: List of candles, most recent last.
        threshold: How many consecutive small-body candles count as chop.
        body_threshold: Body as a fraction of range below which a candle is "small".

    Returns:
        True if chop detected.
    """
    if len(candles) < threshold:
        return False

    count = 0
    for c in reversed(candles[-threshold:]):
        if c.range_size > 0 and c.body_size / c.range_size < body_threshold:
            count += 1
        else:
            count = 0  # a zero-range bar breaks the run rather than extending it
        if count >= threshold:
            return True
    return False


def is_x_signal(
    candles: List[Candle],
    level: float,
    direction: str,
    lookback: int = 20
) -> bool:
    """
    Reject signal. True means the setup is invalid and should not be traded.

    Austin (rules/x-reject.md): chop kills it, noise before the break kills it, and
    trading inside all the levels with no clean break and retest kills it.
    """
    # 1. Chop / consolidation.
    if is_chop_market(candles, threshold=10):
        return True

    # 2. Noise beforehand — price flip-flopping direction into the break.
    if len(candles) > lookback:
        prior = candles[-(lookback + 1):-1]
        flips, last_dir = 0, None
        for c in prior:
            d = 1 if c.is_bullish else (-1 if c.is_bearish else 0)
            if d == 0:
                continue
            if last_dir is not None and d != last_dir:
                flips += 1
            last_dir = d
        if flips > 5:
            return True

    # 3. No clean break and retest of the reference in either direction.
    # ponytail: only fires once a level is actually supplied; callers that pass a
    # placeholder level get the chop/noise gates only.
    if level is not None and not is_break_and_retest(candles, level, direction):
        return True

    return False


# S_GATE displacement threshold (omen-3.6 / T6). Source: research/s_gate_spec.md
# "PRE-REGISTERED GATE" -- the X marks' 50th-percentile displacement. A
# candidate passes the gate when its entry bar is at least as displaced as the
# median reject (Austin's 'x' verdicts). Do not retune this after T7 sees the
# backtest; that is the whole point of the pre-registration.
S_GATE_DISPLACEMENT = 0.888


def is_s_gate(candles: List[Candle]) -> bool:
    """S-gate predicate (omen-3.6). Source: research/s_gate_spec.md.

    Accepts a candidate entry when its displacement clears the pre-registered
    threshold. `displacement` is defined exactly as in research/mark_features.md
    and research/mark_features.py:

        displacement = (entry bar range) / (median range of the prior 20 bars)

    where the entry bar is `candles[-1]`, the prior bars are `candles[-21:-1]`
    (up to 20 bars strictly before the entry, matching
    `bars[max(0, entry_i-20):entry_i]`), and zero-range bars are excluded from
    the median. When fewer than 20 prior bars exist, all available prior bars are
    used (mirroring the `max(0, ...)` clamp).

    Literal threshold: displacement >= 0.888 (the X marks' 50th percentile).
    Returns False when displacement is undefined (no usable prior bars, zero
    median range, or zero entry-bar range) -- the candidate does not pass.

    Args:
        candles: List of candles, most recent last. The last candle is the
            entry candle. Works on any object exposing `.high` / `.low`.

    Returns:
        True if the candidate clears the displacement threshold, False otherwise.
    """
    if len(candles) < 2:
        return False
    entry = candles[-1]
    rng = entry.high - entry.low
    if rng <= 0:
        return False
    prior = candles[-21:-1]
    prior_ranges = [c.high - c.low for c in prior if (c.high - c.low) > 0]
    if not prior_ranges:
        return False
    med_rng = median(prior_ranges)
    if not med_rng or med_rng <= 0:
        return False
    return (rng / med_rng) >= S_GATE_DISPLACEMENT
