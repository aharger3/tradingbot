"""CLI signal detector - read candles, detect signals, post to Discord"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import List, Optional


def _load_env_file(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE per line, no quoting/expansion."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(Path(__file__).parent / ".env")

from vanquish_bot import (
    Candle, SignalType, OpeningRangeAnalyzer, TradingSession,
    BreakAndRetestDetector, OneCandleRuleDetector, RuleOf84Detector, PriceActionAnalyzer
)
from discord_bot import DiscordSignalBot
from position_sizer import compute_plan, SizingPlan


class SignalRunner:
    """Monitor candles, detect signals, alert Discord"""

    def __init__(self, webhook_url: Optional[str] = None, post_to_discord: bool = True):
        self.session = TradingSession()
        self.candles: List[Candle] = []
        self.discord = None
        self.post_to_discord = post_to_discord

        if post_to_discord:
            try:
                self.discord = DiscordSignalBot(webhook_url)
            except ValueError as e:
                print(f"Warning: {e}")
                self.post_to_discord = False

    def load_candles_from_json(self, json_str: str) -> bool:
        """Parse candles from JSON array"""
        try:
            data = json.loads(json_str)
            self.candles = []
            for item in data:
                candle = Candle(
                    timestamp=item["timestamp"],
                    open=float(item["open"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                    volume=int(item["volume"])
                )
                self.candles.append(candle)
            return True
        except Exception as e:
            print(f"Failed to parse JSON: {e}")
            return False

    def load_candles_from_csv(self, csv_str: str) -> bool:
        """Parse candles from CSV (timestamp,open,high,low,close,volume)"""
        try:
            lines = csv_str.strip().split("\n")
            self.candles = []
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                parts = line.split(",")
                candle = Candle(
                    timestamp=parts[0].strip(),
                    open=float(parts[1]),
                    high=float(parts[2]),
                    low=float(parts[3]),
                    close=float(parts[4]),
                    volume=int(parts[5])
                )
                self.candles.append(candle)
            return True
        except Exception as e:
            print(f"Failed to parse CSV: {e}")
            return False

    def detect_signals(self) -> List[dict]:
        """Scan candles for all three signal types, both call and put side.

        Returns list of dicts with: signal_type, reason, entry, stop, direction.
        Entry = current close. Stop = setup-specific level.
        Direction = 'call' (bullish) or 'put' (bearish).
        """
        if len(self.candles) < 5:
            return []

        signals = []
        current = self.candles[-1]
        or_high, or_low = OpeningRangeAnalyzer.get_opening_range(self.candles)

        # ---- CALL SIDE (bullish) ----

        # B&R long: retest of OR high with strong PA. Stop = low of retest candle.
        if current.low <= or_high and current.close > or_high:
            if PriceActionAnalyzer.is_strong_price_action(current):
                signals.append({
                    "signal_type": SignalType.BREAK_AND_RETEST,
                    "reason": "Retest of OR high with strong price action",
                    "entry": current.close,
                    "stop": current.low,
                    "direction": "call",
                })

        # OneCandle long: retest of red support candle.
        for i in range(max(0, len(self.candles) - 10), len(self.candles) - 1):
            ref = self.candles[i]
            if ref.is_bearish and current.low <= ref.low and current.close > ref.low:
                if PriceActionAnalyzer.is_strong_price_action(current):
                    signals.append({
                        "signal_type": SignalType.ONE_CANDLE_RULE,
                        "reason": f"Retest of red support ({ref.timestamp}) with strong PA",
                        "entry": current.close,
                        "stop": ref.low,
                        "direction": "call",
                    })
                    break

        # 84% long re-entry: reclaim recent low with large lower wick.
        if len(self.candles) > 5:
            recent_low = min(c.low for c in self.candles[-6:-1])
            if current.low <= recent_low * 1.01 and current.is_bullish:
                if PriceActionAnalyzer.has_large_lower_wick(current):
                    signals.append({
                        "signal_type": SignalType.REENTRY_84_RULE,
                        "reason": f"Reclaim ${recent_low:.2f} with large lower wick",
                        "entry": current.close,
                        "stop": recent_low,
                        "direction": "call",
                    })

        # ---- PUT SIDE (bearish) ----

        # B&R short: retest of OR low with strong bearish PA. Stop = high of retest candle.
        if current.high >= or_low and current.close < or_low:
            if PriceActionAnalyzer.is_strong_bearish_price_action(current):
                signals.append({
                    "signal_type": SignalType.BREAK_AND_RETEST,
                    "reason": "Retest of OR low (rejected) with bearish PA",
                    "entry": current.close,
                    "stop": current.high,
                    "direction": "put",
                })

        # OneCandle short: retest of green resistance candle.
        for i in range(max(0, len(self.candles) - 10), len(self.candles) - 1):
            ref = self.candles[i]
            if ref.is_bullish and current.high >= ref.high and current.close < ref.high:
                if PriceActionAnalyzer.is_strong_bearish_price_action(current):
                    signals.append({
                        "signal_type": SignalType.ONE_CANDLE_RULE,
                        "reason": f"Retest of green resistance ({ref.timestamp}) with bearish PA",
                        "entry": current.close,
                        "stop": ref.high,
                        "direction": "put",
                    })
                    break

        # 84% short re-entry: rejection at recent high with large upper wick.
        if len(self.candles) > 5:
            recent_high = max(c.high for c in self.candles[-6:-1])
            if current.high >= recent_high * 0.99 and current.is_bearish:
                if PriceActionAnalyzer.has_large_upper_wick(current):
                    signals.append({
                        "signal_type": SignalType.REENTRY_84_RULE,
                        "reason": f"Rejection at ${recent_high:.2f} with large upper wick",
                        "entry": current.close,
                        "stop": recent_high,
                        "direction": "put",
                    })

        return signals

    def process_candles(self, candles_data: str, format_type: str = "json") -> None:
        """Load and process candles, detect signals"""
        if format_type == "json":
            if not self.load_candles_from_json(candles_data):
                return
        elif format_type == "csv":
            if not self.load_candles_from_csv(candles_data):
                return
        else:
            print(f"Unknown format: {format_type}")
            return

        print(f"Loaded {len(self.candles)} candles")

        signals = self.detect_signals()

        if signals:
            print(f"\n{'='*70}")
            print(f"SIGNALS DETECTED: {len(signals)}")
            print(f"{'='*70}\n")
            for sig in signals:
                signal_type = sig["signal_type"]
                # Skip signals where stop equals entry (zero-risk = bad data)
                if sig["entry"] == sig["stop"]:
                    print(f"⚠ {signal_type.value.upper()}: skipped (entry == stop, no risk to size)\n")
                    continue
                try:
                    plan = compute_plan(
                        stock_entry=sig["entry"],
                        stock_stop=sig["stop"],
                        direction=sig["direction"],
                    )
                except ValueError as e:
                    print(f"⚠ {signal_type.value.upper()}: sizing failed — {e}\n")
                    continue

                print(f"🚀 {signal_type.value.upper()}")
                print(f"   Reason: {sig['reason']}")
                print(f"   Time: {self.candles[-1].timestamp}")
                print(plan.format_discord())
                print()

                if self.post_to_discord and self.discord:
                    success = self.discord.post_signal(signal_type, self.candles[-1], sig["reason"], plan)
                    if success:
                        print("   ✓ Posted to Discord")
                    else:
                        print("   ✗ Discord post failed")
        else:
            print("No signals detected")


def main():
    parser = argparse.ArgumentParser(description="Trading signal detector with Discord integration")
    parser.add_argument("--file", help="Read candles from JSON/CSV file")
    parser.add_argument("--format", choices=["json", "csv"], default="json", help="Input format")
    parser.add_argument("--no-discord", action="store_true", help="Skip Discord posting")
    parser.add_argument("--webhook", help="Discord webhook URL (or set DISCORD_WEBHOOK_URL env var)")

    args = parser.parse_args()

    runner = SignalRunner(webhook_url=args.webhook, post_to_discord=not args.no_discord)

    if args.file:
        print(f"Reading from {args.file}...")
        try:
            with open(args.file, "r") as f:
                data = f.read()
            runner.process_candles(data, format_type=args.format)
        except FileNotFoundError:
            print(f"File not found: {args.file}")
            sys.exit(1)
    else:
        print("Reading from stdin (paste JSON/CSV, then Ctrl+D)...")
        data = sys.stdin.read()
        runner.process_candles(data, format_type=args.format)


if __name__ == "__main__":
    main()
