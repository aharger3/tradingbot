"""CLI signal detector - read candles, detect signals, post to Discord"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import List, Optional

# Force UTF-8 stdout/stderr so emoji in signal output (⚠🚀✓✗) don't crash
# with UnicodeEncodeError when run under Windows/PowerShell (cp1252 pipes).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


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
    Candle, SignalType, TradeGrade, OpeningRangeAnalyzer, TradingSession,
    BreakAndRetestDetector, RuleOf84Detector, PriceActionAnalyzer,
    detect_order_block_setup
)
from discord_bot import DiscordSignalBot
from position_sizer import compute_plan, SizingPlan
from signal_tracker import log_signal


class SignalRunner:
    """Monitor candles, detect signals, alert Discord"""

    def __init__(self, webhook_url: Optional[str] = None, post_to_discord: bool = True,
                 symbol: str = "UNKNOWN", log_signals: bool = True):
        self.session = TradingSession()
        self.candles: List[Candle] = []
        # True prior-day levels + HTF trend, set by live_scanner per symbol
        # (SPEC0 gaps). None = unavailable → session-proxy / PA-only grading.
        self.pdh: Optional[float] = None
        self.pdl: Optional[float] = None
        self.htf_bias: Optional[str] = None
        self.discord = None
        self.post_to_discord = post_to_discord
        self.symbol = symbol
        self.log_signals = log_signals

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

    def _min_viable_stop(self, entry: float, stop: float, direction: str) -> bool:
        """Skip only when BOTH stock risk < 0.5% of entry AND estimated premium
        risk < $0.20 (spec: either one being wide enough makes it tradeable)."""
        if entry == stop:
            return False
        stock_risk = abs(entry - stop)
        risk_pct = stock_risk / entry
        premium_risk = stock_risk * 0.5  # ATM delta ≈ 0.5 estimate
        return risk_pct >= 0.005 or premium_risk >= 0.20

    def _is_consolidation(self, or_high: float, or_low: float, pdh: float, pdl: float) -> bool:
        """All key levels within 0.5% = consolidation, skip all signals."""
        levels = [pdh, pdl, or_high, or_low]
        avg = sum(levels) / len(levels)
        return all(abs(l - avg) / avg < 0.005 for l in levels)

    def _log_record(self, sig: dict, status: str = "fired", skip_reason: Optional[str] = None) -> None:
        if not self.log_signals:
            return
        risk = abs(sig["entry"] - sig["stop"])
        target = sig["entry"] + 2 * risk if sig["direction"] == "call" else sig["entry"] - 2 * risk
        try:
            log_signal(
                symbol=self.symbol,
                signal_type=sig["signal_type"].value,
                direction=sig["direction"],
                entry=sig["entry"],
                stop=sig["stop"],
                target=target,
                grade=sig["grade"],
                reason=sig["reason"],
                stop_width_pct=sig.get("stop_width_pct"),
                status=status,
                skip_reason=skip_reason,
            )
        except OSError as e:
            print(f"⚠ signal log write failed: {e}")

    def _route(self, signals: List[dict], sig: dict) -> None:
        """Accept viable signals; log D-grade / tight-stop skips for post-session analysis."""
        if sig["grade"] != TradeGrade.D.value:
            if self._min_viable_stop(sig["entry"], sig["stop"], sig["direction"]):
                signals.append(sig)
                return
            self._log_record(sig, status="skipped", skip_reason="stop too tight (<0.5% of entry and premium risk <$0.20)")
            return
        self._log_record(sig, status="skipped", skip_reason="D grade")

    def detect_signals(self) -> List[dict]:
        """Scan candles for signals, grade A-D, filter D.

        Returns list of dicts with: signal_type, reason, entry, stop, direction,
        grade, stop_level_name, stop_width_pct.
        """
        if len(self.candles) < 5:
            return []

        signals = []
        current = self.candles[-1]
        or_high, or_low = OpeningRangeAnalyzer.get_opening_range(self.candles)
        # Session extremes (HOD/LOD) — used by 84% rule RR checks
        hod = max(c.high for c in self.candles)
        lod = min(c.low for c in self.candles)
        # True prior-day levels when live_scanner provided them, else session proxy
        pdh = self.pdh if self.pdh is not None else hod
        pdl = self.pdl if self.pdl is not None else lod

        # Consolidation check → skip all
        if self._is_consolidation(or_high, or_low, pdh, pdl):
            return []

        lookback = self.candles[-6:-1] if len(self.candles) >= 6 else self.candles[:-1]

        # B&R reference levels: OR always; true PDH/PDL when available (SPEC0:
        # both traders treat prior-day levels as the PRIMARY reference)
        level_pairs = [("OR high", "OR low", or_high, or_low)]
        if self.pdh is not None and self.pdl is not None:
            level_pairs.append(("PDH", "PDL", self.pdh, self.pdl))

        # ---- CALL SIDE (bullish) ----

        # B&R long: prior breakout of a reference high, retest
        for hi_name, _lo_name, level_hi, level_lo in level_pairs:
            prior_breakout = any(c.close > level_hi for c in lookback)
            if prior_breakout and current.low <= level_hi and current.close > level_hi:
                stock_risk = current.close - level_hi
                grade = PriceActionAnalyzer.grade_trade(current, lookback, level_hi, level_lo,
                                                        is_long=True, htf_bias=self.htf_bias)
                if stock_risk < 0.50:
                    grade = TradeGrade.D
                self._route(signals, {
                        "signal_type": SignalType.BREAK_AND_RETEST,
                        "reason": f"B&R long — prior breakout above {hi_name} ${level_hi:.2f}, retest with {grade.value} PA",
                        "entry": current.close,
                        "stop": level_hi,
                        "direction": "call",
                        "grade": grade.value,
                        "stop_level_name": hi_name,
                        "stop_width_pct": round(stock_risk / current.close * 100, 2),
                    })

        # Order block long: last red candle before the structural HH (SPEC3)
        block, retest, note = detect_order_block_setup(self.candles, "bullish")
        if block is not None and retest in ("wick_only", "partial_body") and current.close > block.high:
            stock_risk = current.close - block.low
            grade = PriceActionAnalyzer.grade_trade(current, lookback, or_high, or_low,
                                                    is_long=True, htf_bias=self.htf_bias)
            if stock_risk < 0.50:
                grade = TradeGrade.D
            self._route(signals, {
                    "signal_type": SignalType.ONE_CANDLE_RULE,
                    "reason": f"Order block long — block ${block.low:.2f}-${block.high:.2f} (at {block.timestamp}), {retest} retest, {grade.value} PA",
                    "entry": current.close,
                    "stop": block.low,
                    "direction": "call",
                    "grade": grade.value,
                    "stop_level_name": "Order block low",
                    "stop_width_pct": round(stock_risk / current.close * 100, 2),
                })

        # 84% Rule long: prior stop-out at this level, reclaim
        if (self.session.entry_price is not None
                and current.close >= self.session.entry_price
                and current.is_bullish):
            # Skip if close near high of day (risk/reward gone)
            day_range = hod - lod
            if day_range > 0 and (hod - current.close) / day_range > 0.2:  # not too close to HOD
                # Spec: stop at the exact reclaim level (prior entry), not day low
                stock_risk = current.close - self.session.entry_price
                grade = PriceActionAnalyzer.grade_trade(current, lookback, or_high, or_low,
                                                        is_long=True, htf_bias=self.htf_bias)
                self._route(signals, {
                        "signal_type": SignalType.REENTRY_84_RULE,
                        "reason": f"84% long — prior entry ${self.session.entry_price:.2f} reclaimed with {grade.value} PA",
                        "entry": current.close,
                        "stop": self.session.entry_price,
                        "direction": "call",
                        "grade": grade.value,
                        "stop_level_name": "Reclaim level (prior entry)",
                        "stop_width_pct": round(stock_risk / current.close * 100, 2),
                    })

        # ---- PUT SIDE (bearish) ----

        # B&R short: prior breakdown of a reference low, retest
        for _hi_name, lo_name, level_hi, level_lo in level_pairs:
            prior_breakdown = any(c.close < level_lo for c in lookback)
            if prior_breakdown and current.high >= level_lo and current.close < level_lo:
                stock_risk = level_lo - current.close
                grade = PriceActionAnalyzer.grade_trade(current, lookback, level_hi, level_lo,
                                                        is_long=False, htf_bias=self.htf_bias)
                if stock_risk < 0.50:
                    grade = TradeGrade.D
                self._route(signals, {
                        "signal_type": SignalType.BREAK_AND_RETEST,
                        "reason": f"B&R short — prior breakdown below {lo_name} ${level_lo:.2f}, retest with {grade.value} PA",
                        "entry": current.close,
                        "stop": level_lo,
                        "direction": "put",
                        "grade": grade.value,
                        "stop_level_name": lo_name,
                        "stop_width_pct": round(stock_risk / current.close * 100, 2),
                    })

        # Order block short: last green candle before the structural LL (SPEC3)
        block, retest, note = detect_order_block_setup(self.candles, "bearish")
        if block is not None and retest in ("wick_only", "partial_body") and current.close < block.low:
            stock_risk = block.high - current.close
            grade = PriceActionAnalyzer.grade_trade(current, lookback, or_high, or_low,
                                                    is_long=False, htf_bias=self.htf_bias)
            if stock_risk < 0.50:
                grade = TradeGrade.D
            self._route(signals, {
                    "signal_type": SignalType.ONE_CANDLE_RULE,
                    "reason": f"Order block short — block ${block.low:.2f}-${block.high:.2f} (at {block.timestamp}), {retest} retest, {grade.value} PA",
                    "entry": current.close,
                    "stop": block.high,
                    "direction": "put",
                    "grade": grade.value,
                    "stop_level_name": "Order block high",
                    "stop_width_pct": round(stock_risk / current.close * 100, 2),
                })

        # 84% Rule short
        if (self.session.entry_price is not None
                and current.close <= self.session.entry_price
                and current.is_bearish):
            day_range = hod - lod
            if day_range > 0 and (current.close - lod) / day_range > 0.2:
                # Spec: stop at the exact rejection level (prior entry), not day high
                stock_risk = self.session.entry_price - current.close
                grade = PriceActionAnalyzer.grade_trade(current, lookback, or_high, or_low,
                                                        is_long=False, htf_bias=self.htf_bias)
                self._route(signals, {
                        "signal_type": SignalType.REENTRY_84_RULE,
                        "reason": f"84% short — prior entry ${self.session.entry_price:.2f} rejected with {grade.value} PA",
                        "entry": current.close,
                        "stop": self.session.entry_price,
                        "direction": "put",
                        "grade": grade.value,
                        "stop_level_name": "Rejection level (prior entry)",
                        "stop_width_pct": round(stock_risk / current.close * 100, 2),
                    })

        for sig in signals:
            self._log_record(sig)

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
                print(f"   Grade: {sig.get('grade', '?')}")
                print(f"   Stop level: {sig.get('stop_level_name', 'N/A')} (width {sig.get('stop_width_pct', '?')}%)")
                print(f"   Reason: {sig['reason']}")
                print(f"   Time: {self.candles[-1].timestamp}")
                print(plan.format_discord())
                print()

                self.session.signals_today += 1

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
    parser.add_argument("--symbol", default="UNKNOWN", help="Ticker symbol for signal log records")
    parser.add_argument("--no-log", action="store_true", help="Skip writing to journal/signal_log_*.jsonl")

    args = parser.parse_args()

    runner = SignalRunner(webhook_url=args.webhook, post_to_discord=not args.no_discord,
                          symbol=args.symbol, log_signals=not args.no_log)

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
