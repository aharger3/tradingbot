"""
SPEC11 — Entry Timing Filter: Volume + OR-Close + Opening Range Gate

WHAT: Three entry quality gates that fire AFTER signal detection
but BEFORE the signal enters the route/execution pipeline.

Currently any valid signal (grade A-D, stop check passing) goes
straight to route(). SPEC11 adds three checks:

1. VOLUME FILTER — signal candle must have above-average volume
2. OR-CLOSE GATE — must be within first 30 min of OR close
3. OPENING RANGE RE-ENTRY — if price re-enters OR after
   breaking out, wait for confirmation candle

WHY: Right now B&R signals fire on any retest with any candle.
Most real breakouts that fail happen on low volume or premature
entries during the opening range settling period. These three
gates eliminate the false signals without changing any detection
logic.

FILES TO MODIFY:
  - signal_runner.py — add entry timing checks in detect_signals()
  - spec11_check.py (new) — verification

IMPLEMENTATION:

Add to signal_runner.py inside SignalRunner class:

--- Step 1: Volume Filter ---

SIGNAL_VOLUME_MULTIPLIER = 1.3  # 30% above avg for entry

def _avg_volume(self, lookback: int = 20) -> float:
    \"\"\"Average volume of last N complete candles (exclude current)\"\"\"
    if len(self.candles) < lookback + 1:
        return 0
    recent = self.candles[-(lookback+1):-1]
    return sum(c.volume for c in recent) / len(recent) if recent else 0

def _volume_confirms(self) -> bool:
    \"\"\"Signal candle volume >= 1.3x trailing average.\"\"\"
    current = self.candles[-1]
    avg = self._avg_volume(20)
    if avg == 0:
        return True  # not enough data, pass through
    return current.volume >= avg * SIGNAL_VOLUME_MULTIPLIER

Usage: and self._volume_confirms() added to each signal's final
append check. If volume is too low, the signal is skipped with
reason "low volume (X vs Y avg)".

--- Step 2: OR-Close Proximity ---

The opening range settles during the first ~5 candles (5 min).
Signals that fire within this period OR where the entry price is
still inside the OR range are premature.

Add check: skip any signal where current.close is inside the
OR range unless market has been open >10 minutes.

def _or_zone_timing(self) -> bool:
    \"\"\"True = OK to trade. False = skip.\"\"\"
    if len(self.candles) < 6:
        return False
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(self.candles)
    current = self.candles[-1]
    # If current price is inside OR range, wait for confirmed break
    if or_low < current.close < or_high:
        return False
    # If we've only seen 10 min of data, be patient
    return len(self.candles) >= 10

Connection: any signal where _or_zone_timing() is False gets
skipped with reason "price inside opening range" or "market
recently open, wait for confirmation".

--- Step 3: OR Re-Entry Guard ---

If price BROKE the OR (high or low), then RE-ENTERED the range,
and now fires a signal at the near edge — skip it. A genuine
breakout doesn't re-enter the opening range. This is distinct
from Step 2 (which catches the case where we never left).

def _or_reentry_guard(self) -> bool:
    \"\"\"Skip if price broke OR, re-entered, then tries again.\"\"\"
    if len(self.candles) < 10:
        return True
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(self.candles)
    current = self.candles[-1]

    # Check if any candle after candle #10 broke the OR and then
    # a subsequent candle closed back inside
    post_or = self.candles[10:]  # after OR settled
    broke_out = any(c.close > or_high for c in post_or)
    broke_in = any(c.close < or_low for c in post_or)
    re_entered = False

    if current.close > or_high and broke_out:
        # Bullish signal: check if any previous candle broke, then
        # a later one re-entered
        for i in range(len(post_or)):
            c = post_or[i]
            if c.close > or_high:  # broke
                for j in range(i+1, len(post_or)):
                    if post_or[j].close <= or_high:  # re-entered
                        re_entered = True
                        break
            if re_entered:
                break

    if re_entered:
        return False  # broke out, re-entered, skip
    return True

Usage and grading: Don't skip these — downgrade instead (A→B,
B→D). A re-entry attempt after a failed breakout shows weakness
but isn't worthless. Add a flag to the signal dict.

--- Integration ---

Add all three checks to _route() in signal_runner.py. The route()
method now:

1. Check volume_confirms? If no → skip (log "low volume")
2. Check or_zone_timing? If no → skip (log "too early / inside OR")
3. Check or_reentry + grade? If re-entry detected → downgrade 1 step
4. Then existing min-viable-stop check and grade filter

This keeps detect_signals() clean — it still finds every valid pattern.
The filters remove weak entries, they don't change pattern detection.

VERIFICATION:
  python spec11_check.py
  - Signal with volume < 1.3x avg → skipped
  - Signal inside OR close in first 5 min → skipped
  - Breakout → re-enter OR → signal at upper edge → downgraded
  - Normal signal with volume + confirmed break → passes all gates

SUCCESS CRITERIA:
  [ ] Volume filter skips low-volume breakouts with log message
  [ ] OR-close gate skips premature entries (first 10 min)
  [ ] OR re-entry downgrades (not skips) weak second attempts
  [ ] All existing spec1/2/3/10 checks still pass
  [ ] During live market: should see fewer "fired" signals and
      fewer stops within 2 minutes
"""
