"""Live scanner: poll TSLA + NVDA every 1 min during 9:30-11:00 ET, post Discord signals.

Usage:
    python3 live_scanner.py                       # production loop
    python3 live_scanner.py --once                # single scan now (testing)
    python3 live_scanner.py --symbols TSLA        # custom watchlist
    python3 live_scanner.py --window 09:30-11:00  # custom hours (ET)
    python3 live_scanner.py --paper               # paper-trade sim (logs to journal/paper-trades.jsonl)
"""

import os
import sys
import time
import argparse
from datetime import datetime, time as dtime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Set, Tuple

from signal_runner import _load_env_file
_load_env_file(Path(__file__).parent / ".env")

from alpaca_feed import AlpacaFeed
from signal_runner import SignalRunner
from tastytrade_feed import TastytradeFeed


DEFAULT_SYMBOLS = [
    "TSLA", "NVDA", "AAPL", "AMD", "META",
    "GOOG", "AMZN", "MSFT", "PLTR", "SPY", "QQQ",
]
DEFAULT_WINDOW = "09:30-11:00"
POLL_INTERVAL_SECONDS = 60


def now_et() -> datetime:
    """Current time in US Eastern. Approximated as UTC-4 (DST). Replace with zoneinfo for accuracy."""
    return datetime.now(timezone.utc) - timedelta(hours=4)


def parse_window(spec: str) -> Tuple[dtime, dtime]:
    """'09:30-11:00' -> (time(9,30), time(11,0))"""
    start_s, end_s = spec.split("-")
    sh, sm = map(int, start_s.split(":"))
    eh, em = map(int, end_s.split(":"))
    return dtime(sh, sm), dtime(eh, em)


def in_window(now: datetime, start: dtime, end: dtime) -> bool:
    t = now.time()
    return start <= t <= end


def scan_once(
    runner: SignalRunner,
    feed: AlpacaFeed,
    symbols: List[str],
    seen_signal_keys: Set[str],
    paper=None,
    tasty_feed: Optional[TastytradeFeed] = None,
) -> int:
    """Scan each symbol once, post novel signals, return count fired."""
    fired = 0
    for symbol in symbols:
        try:
            candles = feed.fetch_recent_bars(symbol, lookback_minutes=60)
        except Exception as e:
            print(f"[{symbol}] fetch failed: {e}")
            continue

        if len(candles) < 5:
            print(f"[{symbol}] only {len(candles)} bars, skipping")
            continue

        # Mark/close any open paper positions against this fresh candle first.
        if paper is not None:
            last = candles[-1]
            for ev in paper.mark(symbol, high=last.high, low=last.low, ts=last.timestamp):
                print(f"   📕 PAPER CLOSE {ev['symbol']} {ev['direction'].upper()} "
                      f"{ev['outcome'].upper()} P&L ${ev['pnl']:.2f}")

        runner.candles = candles
        signals = runner.detect_signals()

        for sig in signals:
            key = f"{symbol}:{sig['signal_type'].value}:{sig['direction']}:{candles[-1].timestamp}"
            if key in seen_signal_keys:
                continue
            seen_signal_keys.add(key)
            sig["reason"] = f"[{symbol}] {sig['reason']}"
            _emit_signal(runner, feed, symbol, candles[-1], sig, paper, tasty_feed)
            fired += 1
    if paper is not None:
        print("   " + paper.summary())
    return fired


def _emit_signal(runner: SignalRunner, feed: AlpacaFeed, symbol: str, candle, sig: dict, paper=None, tasty_feed=None) -> None:
    """Build OptionsPlan (prefer Tastytrade premium, fallback Alpaca/estimate) and post."""
    from options_sizer import build_options_plan
    if sig["entry"] == sig["stop"]:
        return
    try:
        plan = build_options_plan(
            symbol=symbol,
            direction=sig["direction"],
            stock_entry=sig["entry"],
            stock_stop=sig["stop"],
            alpaca_feed=feed,
            tasty_feed=tasty_feed,
        )
    except ValueError as e:
        print(f"  sizing skip: {e}")
        return

    tag = "[PAPER] " if paper is not None else ""
    print(f"🚀 {tag}{sig['signal_type'].value.upper()} {sig['direction'].upper()}  {sig['reason']}")
    print(plan.format_discord())
    if paper is not None:
        pos = paper.open_from_plan(plan, ts=candle.timestamp)
        print(f"   📗 PAPER OPEN {pos.contracts}x {pos.symbol} ${pos.strike:g} "
              f"{pos.direction.upper()} @ ${pos.entry_premium:.2f}")
    if runner.post_to_discord and runner.discord:
        ok = runner.discord.post_signal(sig["signal_type"], candle, sig["reason"], plan)
        print("   ✓ Posted" if ok else "   ✗ Discord post failed")


def main():
    parser = argparse.ArgumentParser(description="Live Vanquish signal scanner")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help=f"Tickers to watch (default {DEFAULT_SYMBOLS})")
    parser.add_argument("--window", default=DEFAULT_WINDOW,
                        help="Trading window in ET HH:MM-HH:MM (default 09:30-11:00)")
    parser.add_argument("--once", action="store_true",
                        help="Run a single scan and exit (testing)")
    parser.add_argument("--no-discord", action="store_true", help="Skip Discord posting")
    parser.add_argument("--paper", action="store_true",
                        help="Paper-trade simulation: log fired signals + mark to stop/target in journal/paper-trades.jsonl")
    args = parser.parse_args()

    start, end = parse_window(args.window)
    feed = AlpacaFeed()
    runner = SignalRunner(post_to_discord=not args.no_discord)
    seen: Set[str] = set()

    # Tastytrade feed for real-time option quotes
    tasty_feed = None
    try:
        tasty_feed = TastytradeFeed()
        tasty_feed.validate_credentials()
    except Exception as e:
        print(f"  Tastytrade init skipped: {e}")

    paper = None
    if args.paper:
        from paper_trader import PaperBook
        paper = PaperBook()
        print(f"📝 Paper mode ON → {paper.ledger_path}")

    print(f"Scanner armed. Symbols: {args.symbols}  Window (ET): {args.window}")

    if args.once:
        print(f"Single scan @ {now_et().strftime('%H:%M:%S')} ET")
        fired = scan_once(runner, feed, args.symbols, seen, paper, tasty_feed=tasty_feed)
        print(f"Done. {fired} signals fired.")
        return

    while True:
        now = now_et()
        if now.weekday() >= 5:  # Sat=5, Sun=6
            print(f"Weekend ({now.strftime('%a')}), sleeping 1h")
            time.sleep(3600)
            continue

        if not in_window(now, start, end):
            # Sleep until next window open
            print(f"{now.strftime('%H:%M:%S')} ET outside window {args.window}, sleeping 60s")
            time.sleep(60)
            continue

        print(f"\n=== {now.strftime('%H:%M:%S')} ET scan ===")
        fired = scan_once(runner, feed, args.symbols, seen, paper, tasty_feed=tasty_feed)
        if fired == 0:
            print("  no new signals")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScanner stopped.")
        sys.exit(0)
