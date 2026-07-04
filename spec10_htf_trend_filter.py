"""
SPEC10 — Multi-Timeframe Trend Alignment

WHAT: Add real 1-hour candle trend bias (not just placeholder "N/A").
The existing htf_bias field in SignalRunner and get_daily_context in
live_scanner already has a 15-minute refresh loop but no data source —
it calls tasty_feed.fetch_htf_bias() which currently returns None.

WHY: Every trade grade currently uses PA-pattern + key-level only.
When a B&R long fires during a bearish 1-hr trend, it should
downgrade at least one letter. This is the #1 missing filter.

FILES TO MODIFY:
  - tastytrade_feed.py — add real fetch_htf_bias()
  - vanquish_bot.py — add HTF-aware grade adjustment
  - spec10_check.py (new) — verification

Step 1: Fetch 1-hr candles from Tastytrade DXLink

Tastytrade DXLink can request multiple timeframes from the same
stream. In dxlink.py, there's already a candle subscription. Add
a method (or extend fetch_recent_bars) to also request 60-min bars
for the same symbol.

tastytrade_feed.TastytradeFeed.fetch_htf_bias(symbol: str) -> str:
  - Uses DXLink to fetch last 3 x 1-hour candles (or last 4, enough
    to determine structure).
  - Checks for HH/HL (uptrend → "bullish"), LL/LH (downtrend →
    "bearish"), or "neutral" (mixed / no clear direction).
  - Cache in _htf_cache dict keyed by (symbol, hour) so it's not
    re-fetched every 1-min poll cycle (existing 15-min refresh from
    live_scanner is fine — use time.time() check there).

If DXLink can't provide 1-hr bars (not supported yet, rate limit),
fallback: compute from recent 1-min candles by aggregating them
into 60-min buckets. Take last 180 minutes of 1-min candles (3
hours of data), group by hour, compute OHLC for each bucket, then
run the same HH/HL check. This is reliable enough for grade
adjustment and doesn't need a separate data stream.

  from itertools import groupby
  from datetime import datetime
  # Group candles by hour, compute OHLC per bucket
  def _aggregate_htf(candles_1min, minutes=180):
      ...

Step 2: Add grade adjustment in PriceActionAnalyzer

vanquish_bot.PriceActionAnalyzer.grade_trade() already receives
htf_bias. Add adjustment:

  def _adjust_for_htf(grade: TradeGrade, htf_bias: str,
                       signal_direction: str) -> TradeGrade:
      if htf_bias is None or htf_bias == "unknown":
          return grade  # fallback: no adjustment
      # Going with the trend → hold grade or bump A→A+
      # Going against trend → downgrade 1 letter
      aligned = (
          (htf_bias == "bullish" and signal_direction == "call") or
          (htf_bias == "bearish" and signal_direction == "put")
      )
      if aligned:
          if grade == TradeGrade.A:
              return TradeGrade.A_PLUS  # trend-aligned A → A+
          return grade
      # Counter-trend
      grade_map = {"A+": TradeGrade.A, "A": TradeGrade.B,
                    "B": TradeGrade.C, "C": TradeGrade.D}
      return grade_map.get(grade.value, grade)

Insert this call after the existing grade logic in grade_trade()
— one line: return _adjust_for_htf(grade, htf_bias, is_long).

Step 3: Remove the "always N/A" note from existing code

In signal_runner.py, and live_scanner.py, remove any code that
hardcodes htf_bias to "N/A" or sets it to None permanently.
The live_scanner already pushes the bias from get_daily_context
to runner.htf_bias — that chain just needed a real data source.

VERIFICATION:
  python spec10_check.py
  - Synthetic 1-min data aggregated into 1-hr candles produces
    correct HH/HL classification
  - A-grade call in bullish 1-hr → A+ (trend aligned)
  - A-grade call in bearish 1-hr → B (counter-trend)
  - D-grade put in bearish 1-hr → still D (floor)
  - htf_bias=None → no adjustment (graceful degradation)

SUCCESS CRITERIA:
  [ ] fetch_htf_bias returns "bullish"/"bearish"/"neutral" for
      each symbol, not None
  [ ] Grade adjustment fires correctly for trend-aligned and
      counter-trend signals
  [ ] All existing spec1/2/3 checks still pass
  [ ] No new DXLink errors during market hours
"""
