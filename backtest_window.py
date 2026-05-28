#!/usr/bin/env python3
"""Backtest a specific time window on a given date."""

import sys
from datetime import datetime, time as dtime, timezone, timedelta
from pathlib import Path

from alpaca_feed import AlpacaFeed
from signal_runner import SignalRunner

DEFAULT_SYMBOLS = [
    "TSLA", "NVDA", "AAPL", "AMD", "META",
    "GOOG", "AMZN", "MSFT", "PLTR", "SPY", "QQQ",
]

def backtest_window(symbols, date_str="2026-05-27", start_et="09:30", end_et="11:00"):
    """Backtest signals from a specific window on a date.

    date_str: "YYYY-MM-DD"
    start_et, end_et: "HH:MM"
    """
    feed = AlpacaFeed()
    runner = SignalRunner(post_to_discord=False)

    # Parse times
    sh, sm = map(int, start_et.split(":"))
    eh, em = map(int, end_et.split(":"))
    start_time = dtime(sh, sm)
    end_time = dtime(eh, em)

    print(f"Backtesting {date_str} {start_et}-{end_et} ET on symbols: {symbols}")
    print()

    total_signals = 0
    for symbol in symbols:
        try:
            # Fetch all bars for the day
            candles = feed.fetch_recent_bars(symbol, lookback_minutes=1440)  # 1 day
        except Exception as e:
            print(f"[{symbol}] fetch failed: {e}")
            continue

        if len(candles) < 5:
            print(f"[{symbol}] only {len(candles)} bars")
            continue

        # Filter to window
        window_candles = []
        for c in candles:
            try:
                # c.timestamp is time string like "14:25:00"
                ct = datetime.strptime(c.timestamp, "%H:%M:%S").time()
            except ValueError:
                # Try full ISO format
                try:
                    ct = datetime.fromisoformat(c.timestamp).time()
                except:
                    continue
            if start_time <= ct <= end_time:
                window_candles.append(c)
        if len(window_candles) < 2:
            print(f"[{symbol}] only {len(window_candles)} bars in window")
            continue

        print(f"[{symbol}] {len(window_candles)} bars in window")

        runner.candles = window_candles
        signals = runner.detect_signals()

        if signals:
            total_signals += len(signals)
            for sig in signals:
                arrow = "↑" if sig["direction"] == "call" else "↓"
                print(f"  🚀 {sig['signal_type'].value.upper()} {sig['direction'].upper()} {arrow}  {sig['reason']}")

                # Also show sizing
                from options_sizer import build_options_plan
                try:
                    plan = build_options_plan(
                        symbol=symbol,
                        direction=sig["direction"],
                        stock_entry=sig["entry"],
                        stock_stop=sig["stop"],
                        alpaca_feed=feed,
                    )
                    print(f"      {plan.strike:g} {plan.direction.upper()} | entry ${plan.entry_premium:.2f} | stop ${plan.stop_premium:.2f} | target ${plan.target_premium:.2f} | {plan.contracts} contracts")
                except Exception as e:
                    print(f"      sizing error: {e}")
        print()

    print(f"Total signals in window: {total_signals}")

if __name__ == "__main__":
    import sys
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).date().isoformat()
    start_et = sys.argv[2] if len(sys.argv) > 2 else "09:30"
    end_et = sys.argv[3] if len(sys.argv) > 3 else "11:00"
    backtest_window(DEFAULT_SYMBOLS, date_str=date_str, start_et=start_et, end_et=end_et)
