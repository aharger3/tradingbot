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

# Force UTF-8 stdout/stderr so emoji in signal output (📝🚀📕📗✓✗) don't crash
# with UnicodeEncodeError when run under Windows/PowerShell (cp1252 pipes).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from signal_runner import _load_env_file
_load_env_file(Path(__file__).parent / ".env")

from signal_runner import SignalRunner
from tastytrade_feed import TastytradeFeed
from signal_tracker import log_signal


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
    tasty_feed: TastytradeFeed,
    symbols: List[str],
    seen_signal_keys: Set[str],
    paper=None,
    max_trades: int = 3,
    max_consecutive_losses: int = 2,
) -> int:
    """Scan each symbol once, post novel signals, return count fired."""
    fired = 0

    # Check daily limits
    if runner.session.day_ended():
        print(f"  Session halted: {runner.session.signals_today}/{max_trades} signals, "
              f"{runner.session.consecutive_losses}/{max_consecutive_losses} consecutive losses")
        return 0

    for symbol in symbols:
        try:
            candles = tasty_feed.fetch_recent_bars(symbol, lookback_minutes=60)
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
                if ev["outcome"] == "stop":
                    runner.session.record_loss()
                else:
                    runner.session.record_win()

        runner.candles = candles
        runner.symbol = symbol  # so detect_signals logs correct ticker
        signals = runner.detect_signals()

        for sig in signals:
            if runner.session.day_ended():
                break
            key = f"{symbol}:{sig['signal_type'].value}:{sig['direction']}:{candles[-1].timestamp}"
            if key in seen_signal_keys:
                continue
            seen_signal_keys.add(key)
            sig["reason"] = f"[{symbol}] {sig['reason']}"
            executed = _emit_signal(runner, tasty_feed, symbol, candles[-1], sig, paper)
            fired += 1
            if executed:  # C-grade alerts don't count toward the daily trade cap
                runner.session.signals_today += 1

    if paper is not None:
        print("   " + paper.summary())
    return fired


def _emit_signal(runner: SignalRunner, tasty_feed: TastytradeFeed, symbol: str, candle, sig: dict, paper=None) -> bool:
    """Build OptionsPlan (Tastytrade real-time premium, fallback delta estimate) and post.

    Returns True if the signal is auto-tradeable (A+/A/B); False for C-grade
    alert-only signals and skips (SPEC2)."""
    from options_sizer import build_options_plan, GRADE_SIZE_PCT, DEFAULT_MAX_LOSS
    if sig["entry"] == sig["stop"]:
        return False
    grade = sig.get("grade", "?")
    size_pct = GRADE_SIZE_PCT.get(grade, 0.6)
    # 84% rule re-entries size base + 50% (course rule, SPEC0 ingestion)
    if getattr(sig["signal_type"], "value", "") == "reentry_84_rule":
        size_pct *= 1.5
    alert_only = grade == "C"
    try:
        plan = build_options_plan(
            symbol=symbol,
            direction=sig["direction"],
            stock_entry=sig["entry"],
            stock_stop=sig["stop"],
            tasty_feed=tasty_feed,
            max_loss=DEFAULT_MAX_LOSS * size_pct,
        )
    except ValueError as e:
        print(f"  sizing skip: {e}")
        return False

    stop_level = sig.get("stop_level_name", "")
    stop_width = sig.get("stop_width_pct", 0.0)
    signal_type_val = sig["signal_type"].value if hasattr(sig["signal_type"], "value") else str(sig["signal_type"])

    tag = "[PAPER] " if paper is not None else ""
    icon = "⚠" if alert_only else "🚀"
    print(f"{icon} {tag}{signal_type_val.upper()} {sig['direction'].upper()}  Grade: {grade}  Stop: {stop_level} ({stop_width}%)")
    if alert_only:
        print("   C GRADE — ALERT ONLY, manual review (not auto-traded)")
    print(f"   {sig['reason']}")
    print(plan.format_discord())

    # Log signal
    log_signal(
        symbol=symbol,
        signal_type=signal_type_val,
        direction=sig["direction"],
        entry=sig["entry"],
        stop=sig["stop"],
        target=plan.stock_target if hasattr(plan, "stock_target") else 0,
        grade=grade,
        reason=sig["reason"],
        stop_width_pct=stop_width,
        quote_source=plan.quote_source if hasattr(plan, "quote_source") else "estimated",
        status="alert" if alert_only else "fired",
    )

    if paper is not None and not alert_only:
        pos = paper.open_from_plan(plan, ts=candle.timestamp)
        print(f"   📗 PAPER OPEN {pos.contracts}x {pos.symbol} ${pos.strike:g} "
              f"{pos.direction.upper()} @ ${pos.entry_premium:.2f}")
    if runner.post_to_discord and runner.discord:
        ok = runner.discord.post_signal(sig["signal_type"], candle, sig["reason"], plan,
                                         grade=grade, stop_level_name=stop_level, stop_width_pct=stop_width)
        print("   ✓ Posted" if ok else "   ✗ Discord post failed")
    return not alert_only


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
    runner = SignalRunner(post_to_discord=not args.no_discord)
    seen: Set[str] = set()
    max_trades = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
    max_losses = int(os.getenv("CONSECUTIVE_LOSS_HALT", "2"))
    runner.session.max_signals_per_day = max_trades

    # Tastytrade is now the sole data feed (candles + real-time option quotes).
    tasty_feed = None
    try:
        tasty_feed = TastytradeFeed()
        tasty_feed.validate_credentials()
    except Exception as e:
        print(f"  Tastytrade init failed: {e}")

    if tasty_feed is None:
        print("No data feed available (Tastytrade init failed). Exiting.")
        sys.exit(1)

    paper = None
    if args.paper:
        from paper_trader import PaperBook
        paper = PaperBook()
        print(f"📝 Paper mode ON → {paper.ledger_path}")

    print(f"Scanner armed. Symbols: {args.symbols}  Window (ET): {args.window}")

    if args.once:
        print(f"Single scan @ {now_et().strftime('%H:%M:%S')} ET")
        fired = scan_once(runner, tasty_feed, args.symbols, seen, paper,
                            max_trades=max_trades, max_consecutive_losses=max_losses)
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
        fired = scan_once(runner, tasty_feed, args.symbols, seen, paper,
                            max_trades=max_trades, max_consecutive_losses=max_losses)
        if fired == 0:
            print("  no new signals")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScanner stopped.")
        sys.exit(0)
