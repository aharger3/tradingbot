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

from omen_bot import (
    Candle, SignalType, TradeGrade, OpeningRangeAnalyzer, TradingSession,
    BreakAndRetestDetector, RuleOf84Detector, PriceActionAnalyzer,
    detect_order_block_setup, find_fvg, detect_flag_setup, detect_break_retest
)
from discord_bot import DiscordSignalBot
from position_sizer import compute_plan, SizingPlan
from signal_tracker import log_signal


# Order-block tunables (module-level so backtest_sweep.py can vary them).
# 30-day sweeps 2026-07-05: partial_body retests were the leak (wick_only flips
# OB positive). Volume gate re-tested after the grading-anchor fix + PMH/PML:
# it CUT P&L ($1335 vs $2505) — off. B&R-only mode (OB_RETEST_TYPES=()) trades
# 28x @ 50% win if OB ever needs benching.
OB_RETEST_TYPES = ("wick_only",)  # accepted retest strengths
OB_VOLUME_MULT = 0.0  # entry candle volume >= mult x avg(prior 10); 0 = gate off
# 30d A/B 2026-07-05: FVG retests diluted B&R badly (206 trades @33% -$216 vs
# 28 @50% +$1400 raw-level only; 0.1%-min-gap variant still +$277). Off until a
# displacement-anchored FVG detector exists.
FVG_RETEST = False  # B&R may retest the displacement FVG instead of the raw level
# Flag detector BENCHED 2026-07-09: my 2026-07-08 speculative add fired 465x for
# -$57.6k over 12mo (28% win) = the whole system loss. Austin never visually
# validated it. Re-enable only after an ordered rebuild + his chart review.
FLAG_ENABLED = False


def _confirm_candle(c: Candle, long: bool) -> bool:
    """Scarface entry candle: hammer (long) / inverted hammer (short).
    12mo split 2026-07-11: hammer entries 42.4%W +$18k vs 33.8%W +$3k without;
    monotonic improvement at every S tier (S>=4+hammer = 70%W n=10)."""
    rng = c.high - c.low
    if rng <= 0:
        return False
    if long:
        return c.lower_wick >= c.body_size and c.close >= c.low + 0.5 * rng
    return c.upper_wick >= c.body_size and c.close <= c.high - 0.5 * rng


def _volume_ok(candles: List[Candle]) -> bool:
    if OB_VOLUME_MULT <= 0 or len(candles) < 2:
        return True
    prior = candles[-11:-1]
    avg = sum(c.volume for c in prior) / len(prior)
    return avg <= 0 or candles[-1].volume >= OB_VOLUME_MULT * avg


STRONG_PA_MULT = 1.5  # reclaim body vs avg body of prior 10 candles (84% rule gate)

# Chase distance (hallucination audit #48, 2026-07-11): entry close >= this far
# beyond the broken level = extended ("don't buy the top"). 12mo re-run: chase
# 28.0%W -$14.5k vs no-chase 37.3%W. TAG-ONLY by decision: the S>=4+hammer tier
# already screens these out (encoding as S-1 measured $24k vs $25k baseline).
# Same verdict for [vwap-] (25%W -$12k full-pop, tier-neutral) and [pdwick]
# (community chop claim REFUTED: 36.7%W inside zone vs 35.5% outside).
CHASE_PCT = 0.005

# 84% variants (A/B 2026-07-06). Lesson 6 canonical: re-enter on reclaim CLOSE,
# no pattern needed, ORIGINAL stop + targets, arm only off solid B&R setups.
# Austin's chat def: strong-PA reclaim, stop under reclaim candle.
RULE84_LESSON = True   # True = lesson-faithful (no PA gate, original stop)
RULE84_ARM_BNR_ONLY = True  # arm only when the failed trade was a break & retest

# F2 stop-placement A/B (fable-spec-2026-07-12, audit #6). Ours was exactly AT
# the level -> zone-wiggle stop-outs. Source: "10-15 cents buffer below level"
# (mm 5.0) / "stop at the break of the candle that came back for the retest"
# (yt EIIiEtAEm3s).
#   "level"  = current behavior, stop exactly at broken level
#   "retest" = Variant A: stop at retest-candle low (long) / high (short)
#   "buffer" = Variant B: stop level -/+ max($0.10, 10% of avg 1-min range)
BNR_STOP_MODE = "level"  # F2 A/B 2026-07-11: retest & buffer BOTH lose (see
                         # research/f2f1_runs/session-notes.md) — keep at-level

# F3: HOD/LOD intraday break-retest pair (fable-spec-2026-07-12, audit #10).
# Mastermind 5.0: "Wait for HOD break and retest or LOD break and retest.
# Nothing in between — all noise." Level = session extreme set BEFORE the FSM
# window and >=30 min old (avoids OR duplication); skipped when within 0.1%
# of an existing level. stop_level_name "HOD"/"LOD" for split reporting.
HODLOD_PAIR = False  # F3 12mo 2026-07-11: 19 tr/yr standalone, 33.3%W −$228,
                     # tier drag 43.4→42.5 — no edge as specced. OFF.

# Austin trade-notes review 2026-07-06 (91 trades): "middle of a bunch of levels,
# probability goes down significantly"; likes trades where new HOD/LOD can be hit.
LEVEL_BLOCK_CAP = True   # level inside the 2R path caps grade at C (alert-only)
CLEAR_FOR_APLUS = True   # A+/A require entry beyond ALL levels in trade direction
STOP_RANGE_MULT = 0.75   # stop must be >= this x avg 1-min range ("human-proof")
_GRADE_RANK = {"A+": 4, "A": 3, "B": 2, "C": 1, "D": 0}


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
        # Prior day's daily-candle open/close — for the [pdwick] chop tag
        self.pd_open: Optional[float] = None
        self.pd_close: Optional[float] = None
        # Premarket high/low (Scarface: PMH/PML are breakable structure like PDH/PDL)
        self.pmh: Optional[float] = None
        self.pml: Optional[float] = None
        self.htf_bias: Optional[str] = None
        # F4 (qqq-alignment-rules.md Rule 4): QQQ's first PD/PM key-level break
        # times for the session — {"up": "HH:MM:SS"|None, "dn": ...} or None
        # when no QQQ data. Set by backtest_12mo; tag-only, no routing.
        self.qqq_breaks: Optional[dict] = None
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
        # Human-proof gate (Austin: tight stops "lose the $1,000 in a second"):
        # stop can't sit inside one typical candle's range.
        recent = self.candles[-11:-1]
        if recent:
            avg_range = sum(c.high - c.low for c in recent) / len(recent)
            if stock_risk < STOP_RANGE_MULT * avg_range:
                return False
        risk_pct = stock_risk / entry
        premium_risk = stock_risk * 0.5  # ATM delta ≈ 0.5 estimate
        return risk_pct >= 0.005 or premium_risk >= 0.20

    def _aplus_stack(self, level: float, is_long: bool) -> bool:
        """Austin's A+ spec 2026-07-06: FIRST clean break of the level today,
        displacement in the break leg, strong PA entry candle."""
        current = self.candles[-1]
        lookback = self.candles[-6:-1]
        earlier = self.candles[:-6]
        beyond = (lambda c: c.close > level) if is_long else (lambda c: c.close < level)
        first_break = not any(beyond(c) for c in earlier)
        prior = self.candles[-16:-6] or self.candles[:-6]
        avg_body = (sum(abs(c.close - c.open) for c in prior) / len(prior)) if prior else 0
        displacement = avg_body > 0 and any(
            beyond(c) and abs(c.close - c.open) >= 1.5 * avg_body for c in lookback)
        return first_break and displacement and self._strong_pa(current)

    def _grade_for_levels(self, sig: dict) -> None:
        """Demote signals fighting the level map (Austin notes 2026-07-06).

        Level inside the 2R path -> cap at C (trade must have open road to a
        new HOD/LOD). A+/A additionally require entry beyond every level in
        the trade direction (breakout conditions, not mid-range chop).
        """
        levels = getattr(self, "_active_levels", [])
        if not levels:
            return
        grade = sig["grade"]
        entry, stop = sig["entry"], sig["stop"]
        risk = abs(entry - stop)
        if risk == 0:
            return
        target = entry + 2 * risk if sig["direction"] == "call" else entry - 2 * risk
        lo, hi = min(entry, target), max(entry, target)
        # ignore the traded level itself (within 10% of risk of entry)
        blocking = [l for l in levels if lo < l < hi and abs(l - entry) > 0.1 * risk]
        if LEVEL_BLOCK_CAP and blocking and _GRADE_RANK.get(grade, 0) > _GRADE_RANK["C"]:
            sig["grade"] = TradeGrade.C.value
            sig["reason"] += f" [capped C: level ${blocking[0]:.2f} blocks 2R path]"
            return
        if CLEAR_FOR_APLUS and grade in ("A+", "A", "B"):
            clear = (all(l <= entry for l in levels) if sig["direction"] == "call"
                     else all(l >= entry for l in levels))
            if not clear and grade != "B":
                sig["grade"] = TradeGrade.B.value
                sig["reason"] += " [A->B: entry not beyond all levels]"
            elif clear and grade == "B":
                # Open road to new HOD/LOD = Austin's A context (30d: 67% win)
                sig["grade"] = TradeGrade.A.value
                sig["reason"] += " [B->A: breakout conditions, clear of all levels]"
            if clear and sig.get("aplus_stack"):
                # First break of level today + displacement + strong PA + open road
                sig["grade"] = TradeGrade.A_PLUS.value
                sig["reason"] += " [A+: first break, displacement, strong PA, clear road]"
            elif sig["grade"] == "A+":
                # A+ reserved for the full stack (pattern-A+ hallucinated per Austin)
                sig["grade"] = TradeGrade.A.value

    def _calibration_grade(self, sig: dict) -> None:
        """Calibration vs 133 labeled trades (Scarface replay + Austin charts,
        2026-07-06): he takes the FIRST signal per direction, with the day
        trend, inside the first 90 min (94.5% of his traded direction-days,
        1.2 alerts/day). Re-triggers and counter-trend spray are what he skips.
        """
        d = sig["direction"]
        if not hasattr(self, "_dir_fired"):
            self._dir_fired = {"call": 0, "put": 0}
        # ponytail: day trend from candles[0].open — live lookback may start
        # after 9:30; good enough inside the 90-min window we trade
        with_trend = (self.candles[-1].close >= self.candles[0].open) == (d == "call")
        t = self.candles[-1].timestamp[:5]
        mins = int(t[:2]) * 60 + int(t[3:5]) - 570
        if not with_trend and _GRADE_RANK.get(sig["grade"], 0) > _GRADE_RANK["C"]:
            sig["grade"] = TradeGrade.C.value
            sig["reason"] += " [capped C: counter day trend]"
        elif (with_trend and self._dir_fired[d] == 0 and 0 <= mins <= 90
              and sig["grade"] == "C" and "capped C" not in sig["reason"]):
            sig["grade"] = TradeGrade.B.value
            sig["reason"] += " [floor B: first with-trend signal of the day]"

    def _qqq_aligned(self, ts: str, is_long: bool) -> Optional[bool]:
        """F4 Rule 4 (qqq-alignment-rules.md): QQQ broke a PD/PM key level in
        the trade direction before entry time. None = no QQQ data (live scanner
        not plumbed yet — S contribution simply absent there)."""
        if self.qqq_breaks is None:
            return None
        up, dn = self.qqq_breaks.get("up"), self.qqq_breaks.get("dn")
        return (up is not None and up <= ts) if is_long else (dn is not None and dn <= ts)

    def _bnr_tags(self, current: Candle, stock_risk: float, is_long: bool) -> str:
        """Measurement tag on B&R cards — no routing effect.

        [vwap±] and [pdwick] REMOVED 2026-07-11 evening (Austin: not something
        he or Scarface trades / pdwick refuted by data — 36.7%W inside zone vs
        35.5% outside). [chase] stays: it's his own 'don't buy the top' rule,
        28.0%W −$14.5k/yr when tagged."""
        tags = ""
        if current.close > 0 and stock_risk / current.close >= CHASE_PCT:
            tags += " [chase]"
        # F4 Rule 4 measurement tag: "QQQ/SPY market structure aligned (QQQ
        # broke key level in same direction)". NOT the refuted OR-break proxy —
        # levels here are QQQ's PDH/PDL/PMH/PML.
        aligned = self._qqq_aligned(current.timestamp, is_long)
        if aligned is not None:
            tags += " [qqqA]" if aligned else " [qqqX]"
        return tags

    def _strong_pa(self, current: Candle) -> bool:
        """84% reclaim gate: candle body >= STRONG_PA_MULT x avg body of prior 10."""
        prior = self.candles[-11:-1]
        if not prior:
            return False
        avg = sum(abs(c.close - c.open) for c in prior) / len(prior)
        return avg > 0 and abs(current.close - current.open) >= STRONG_PA_MULT * avg

    @staticmethod
    def _closes_strong(c: Candle, is_long: bool) -> bool:
        """Strong PA independent of neighbors: body dominates range, close near
        the extreme (relative-body test fails near the open when 5-point
        opening bars inflate the average — Scarface replay 06-12 TSLA)."""
        rng = c.high - c.low
        if rng <= 0:
            return False
        body = abs(c.close - c.open)
        if body < 0.5 * rng:
            return False
        return ((c.high - c.close) if is_long else (c.close - c.low)) <= 0.25 * rng

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
        self._grade_for_levels(sig)
        self._calibration_grade(sig)
        if sig["grade"] != TradeGrade.D.value:
            # tight-stop skip only for C — it killed 42 of 303 labeled takes
            # (calibration 2026-07-06); B+ setups size to the stop instead
            if sig["grade"] != "C" or self._min_viable_stop(sig["entry"], sig["stop"], sig["direction"]):
                self._dir_fired[sig["direction"]] = self._dir_fired.get(sig["direction"], 0) + 1
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

        # Level map for chop grading (only real levels, no session proxies)
        self._active_levels = [l for l in (self.pdh, self.pdl, self.pmh,
                                           self.pml, or_high, or_low) if l is not None]

        lookback = self.candles[-6:-1] if len(self.candles) >= 6 else self.candles[:-1]

        # B&R reference levels: OR always; true PDH/PDL when available (SPEC0:
        # both traders treat prior-day levels as the PRIMARY reference)
        level_pairs = [("OR high", "OR low", or_high, or_low)]
        if self.pdh is not None and self.pdl is not None:
            level_pairs.append(("PDH", "PDL", self.pdh, self.pdl))
        if self.pmh is not None and self.pml is not None:
            level_pairs.append(("PMH", "PML", self.pmh, self.pml))
        # F3: rolling session-extreme pair. Extreme must predate the B&R FSM
        # window (12 bars) and be >=30 min old; dedupe vs existing levels.
        if HODLOD_PAIR and len(self.candles) >= 43:
            pre = self.candles[:-12]
            n = len(self.candles)
            hi_val = max(c.high for c in pre)
            hi_age = n - 1 - max(j for j, c in enumerate(pre) if c.high == hi_val)
            lo_val = min(c.low for c in pre)
            lo_age = n - 1 - max(j for j, c in enumerate(pre) if c.low == lo_val)
            dup = lambda v: any(abs(v - l) / l < 0.001 for l in self._active_levels)
            hod_lv = hi_val if hi_age >= 30 and not dup(hi_val) else None
            lod_lv = lo_val if lo_age >= 30 and not dup(lo_val) else None
            if hod_lv is not None or lod_lv is not None:
                level_pairs.append(("HOD", "LOD", hod_lv, lod_lv))

        # ---- CALL SIDE (bullish) ----

        # B&R long: prior breakout of a reference high, retest
        for hi_name, _lo_name, level_hi, level_lo in level_pairs:
            if level_hi is None:  # F3 pair may carry only one qualifying side
                continue
            # Austin 2026-07-09 ORDERED break-and-retest (omen_bot.detect_break_retest):
            # break → LEAVE the level → come back → confirm, IN ORDER. Replaces the
            # presence-in-window booleans that let chop/no-return fire (his review).
            br_out = {}
            br_note = detect_break_retest(self.candles, level_hi, is_long=True, out=br_out)
            if br_note and current.close > level_hi:
                stop = level_hi
                if BNR_STOP_MODE == "retest":
                    stop = br_out["retest_low"]
                elif BNR_STOP_MODE == "buffer":
                    recent = self.candles[-11:-1]
                    avg_rng = (sum(c.high - c.low for c in recent) / len(recent)) if recent else 0.0
                    stop = level_hi - max(0.10, 0.10 * avg_rng)
                stock_risk = current.close - stop
                grade = PriceActionAnalyzer.grade_trade(current, lookback, level_hi, level_lo,
                                                        is_long=True, htf_bias=self.htf_bias)
                # Austin 2026-07-10: level already broken earlier in the session
                # = dirty/late entry — cap at B (kept for the clean-vs-late A/B).
                if "LATE" in br_note and grade.value in ("A+", "A"):
                    grade = TradeGrade.B
                stack = current.is_bullish and self._aplus_stack(level_hi, is_long=True)
                # Austin's A+ stack outranks candle patterns (30d: pattern grader
                # D-benched 38 of 53 stack setups) — floor B unless HTF opposed
                if stack and grade.value in ("C", "D") and self.htf_bias != "bearish":
                    grade = TradeGrade.B
                elif (grade == TradeGrade.D and current.is_bullish
                        and self.htf_bias != "bearish"):
                    # valid confirmation entry, pattern-D only -> alert tier
                    grade = TradeGrade.C
                if stock_risk < max(0.10, 0.0015 * current.close):  # relative min (flat $0.50 benched sub-$50 stocks)
                    grade = TradeGrade.D
                # PM-level B&R negative BOTH backtest years (24mo 2026-07-10:
                # −$5k y1 / −$6k y2, 30-31%W) — alert-only. After promotions so
                # the A+ stack can't lift it back.
                if hi_name == "PMH" and grade.value in ("A+", "A", "B"):
                    grade = TradeGrade.C
                # Selection score (24mo split 2026-07-10): clean+2, A-grade+2,
                # structural stop >=0.3% +2, non-PM +1. S>=4 = top-quality tier.
                hammer = _confirm_candle(current, long=True)
                sc = ((2 if "LATE" not in br_note else 0)
                      + (2 if grade.value in ("A+", "A") else 0)
                      + (2 if stock_risk / current.close >= 0.003 else 0)
                      + (0 if hi_name == "PMH" else 1)
                      + (2 if hammer else 0)
                      # F4 Rule 4 S-input (2026-07-11): QQQ-aligned +1. Tier
                      # 12mo: 90 tr 44.4%W $30k/yr vs 83/43.4%/$25k without.
                      + (1 if self._qqq_aligned(current.timestamp, True) else 0))
                self._route(signals, {
                        "signal_type": SignalType.BREAK_AND_RETEST,
                        "reason": (f"B&R long — prior breakout above {hi_name} ${level_hi:.2f}, "
                                   f"retest with {grade.value} PA"
                                   + (" [late]" if "LATE" in br_note else " [clean]")
                                   + (" [hammer]" if hammer else "")
                                   + self._bnr_tags(current, stock_risk, is_long=True)
                                   + f" S{sc}"),
                        "entry": current.close,
                        "stop": stop,
                        "direction": "call",
                        "grade": grade.value,
                        "stop_level_name": hi_name,
                        "stop_width_pct": round(stock_risk / current.close * 100, 2),
                        "aplus_stack": stack,
                    })

        # B&R long via FVG: breakout displacement left a gap above the level;
        # price retests the gap, never the raw level (Scarface: FVG = valid zone)
        if FVG_RETEST:
            fvg = find_fvg(self.candles, "bullish")
            for hi_name, _lo, level_hi, level_lo in level_pairs:
                if fvg is None or fvg[0] < level_hi:  # gap must sit above the broken level
                    continue
                prior_breakout = any(c.close > level_hi for c in lookback)
                already_at_level = current.low <= level_hi  # raw-level retest handles it
                if (prior_breakout and not already_at_level
                        and current.low <= fvg[1] and current.close > fvg[1]):
                    stock_risk = current.close - fvg[0]
                    grade = PriceActionAnalyzer.grade_trade(current, lookback, fvg[1], fvg[0],
                                                            is_long=True, htf_bias=self.htf_bias)
                    if stock_risk < 0.50:
                        grade = TradeGrade.D
                    self._route(signals, {
                            "signal_type": SignalType.BREAK_AND_RETEST,
                            "reason": f"B&R long — FVG retest ${fvg[0]:.2f}-${fvg[1]:.2f} above {hi_name} ${level_hi:.2f}, {grade.value} PA",
                            "entry": current.close,
                            "stop": fvg[0],
                            "direction": "call",
                            "grade": grade.value,
                            "stop_level_name": "FVG low",
                            "stop_width_pct": round(stock_risk / current.close * 100, 2),
                        })
                    break  # one FVG signal max per bar

        # Order block long: last red candle before the structural HH (SPEC3)
        block, retest, note = detect_order_block_setup(self.candles, "bullish")
        if (block is not None and retest in OB_RETEST_TYPES
                and current.close > block.high and _volume_ok(self.candles)):
            stock_risk = current.close - block.low
            # Grade PA at the block's own level, not the OR (a block far from the
            # OR could otherwise never grade above C)
            grade = PriceActionAnalyzer.grade_trade(current, lookback, block.high, block.low,
                                                    is_long=True, htf_bias=self.htf_bias)
            if stock_risk < 0.50:
                grade = TradeGrade.D
            # Austin 2026-07-10 review + 12mo split: OCR only earns its keep at
            # A-grade with a TIGHT stop (10tr 40%W +$2k); B-grade 19%W −$13k and
            # wide stops 0-for-11 −$10k. Demote the rest to alert-only.
            if grade.value == "B":
                grade = TradeGrade.C
            if stock_risk / current.close > 0.004:  # stop wider than 0.4% = 2R unreachable
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

        # Flag long (Austin 2026-07-08): pole up -> tight pause -> breakout up.
        # Routed as ONE_CANDLE_RULE like order block; "Flag long" reason tags it.
        # ponytail: dedicated SignalType.FLAG if per-setup analytics needed later.
        flag, fnote = detect_flag_setup(self.candles, "bullish") if FLAG_ENABLED else (None, "")
        if flag is not None and current.close > flag["flag_lo"] and _volume_ok(self.candles):
            stock_risk = current.close - flag["flag_lo"]
            grade = PriceActionAnalyzer.grade_trade(current, lookback, flag["flag_hi"], flag["flag_lo"],
                                                    is_long=True, htf_bias=self.htf_bias)
            if stock_risk < 0.50:
                grade = TradeGrade.D
            self._route(signals, {
                    "signal_type": SignalType.ONE_CANDLE_RULE,
                    "reason": f"Flag long — {fnote}, breakout ${flag['flag_hi']:.2f}, {grade.value} PA",
                    "entry": current.close,
                    "stop": flag["flag_lo"],
                    "direction": "call",
                    "grade": grade.value,
                    "stop_level_name": "Flag low",
                    "stop_width_pct": round(stock_risk / current.close * 100, 2),
                })

        # 84% Rule long (Austin 2026-07-05): stopped-out CALL, price reclaims the
        # failed entry with STRONG PA -> re-enter toward the ORIGINAL target;
        # stop under the reclaim candle ("we just had our stop wrong the first time")
        if (self.session.entry_price is not None
                and self.session.entry_direction in (None, "call")
                and current.close >= self.session.entry_price
                and current.is_bullish
                and (RULE84_LESSON or self._strong_pa(current))):
            # Skip if close near high of day (risk/reward gone)
            day_range = hod - lod
            # 2026-07-10: remaining reward must still be >=1.5x risk at re-entry
            stop_chk = (self.session.entry_stop if RULE84_LESSON
                        and self.session.entry_stop is not None else current.low)
            tgt = self.session.entry_target
            rr_ok = (tgt is not None and stop_chk < current.close
                     and (tgt - current.close) >= 1.5 * (current.close - stop_chk))
            if day_range > 0 and (hod - current.close) / day_range > 0.2 and rr_ok:  # not too close to HOD
                stop_84 = stop_chk
                stock_risk = current.close - stop_84
                grade = PriceActionAnalyzer.grade_trade(current, lookback,
                                                        self.session.entry_price, self.session.entry_price,
                                                        is_long=True, htf_bias=self.htf_bias)
                if grade == TradeGrade.C:  # strong-PA gate already passed; C = alert-only would bench every 84
                    grade = TradeGrade.B
                self._route(signals, {
                        "signal_type": SignalType.REENTRY_84_RULE,
                        # [hammer] tag: sources demand strong PA on the reclaim
                        # (audit #32) — measure before gating
                        "reason": (f"84% long — prior entry ${self.session.entry_price:.2f} "
                                   f"reclaimed ({grade.value} PA)"
                                   + (" [hammer]" if _confirm_candle(current, long=True) else "")),
                        "entry": current.close,
                        "stop": stop_84,
                        "target": self.session.entry_target,
                        "direction": "call",
                        "grade": grade.value,
                        "stop_level_name": "Original stop" if RULE84_LESSON else "Reclaim candle low",
                        "stop_width_pct": round(stock_risk / current.close * 100, 2) if current.close else 0,
                    })
                # Scarface: 84% rule = ONE re-entry per failed setup. Disarm so it
                # doesn't re-fire on every reclaim bar (SPEC17 backtest: 51x/week spam).
                self.session.entry_price = None

        # ---- PUT SIDE (bearish) ----

        # B&R short: prior breakdown of a reference low, retest
        for _hi_name, lo_name, level_hi, level_lo in level_pairs:
            if level_lo is None:  # F3 pair may carry only one qualifying side
                continue
            # Mirror of the long side — ordered break/leave/retest/confirm.
            br_out = {}
            br_note = detect_break_retest(self.candles, level_lo, is_long=False, out=br_out)
            if br_note and current.close < level_lo:
                stop = level_lo
                if BNR_STOP_MODE == "retest":
                    stop = br_out["retest_high"]
                elif BNR_STOP_MODE == "buffer":
                    recent = self.candles[-11:-1]
                    avg_rng = (sum(c.high - c.low for c in recent) / len(recent)) if recent else 0.0
                    stop = level_lo + max(0.10, 0.10 * avg_rng)
                stock_risk = stop - current.close
                grade = PriceActionAnalyzer.grade_trade(current, lookback, level_hi, level_lo,
                                                        is_long=False, htf_bias=self.htf_bias)
                if "LATE" in br_note and grade.value in ("A+", "A"):
                    grade = TradeGrade.B
                stack = current.is_bearish and self._aplus_stack(level_lo, is_long=False)
                if stack and grade.value in ("C", "D") and self.htf_bias != "bullish":
                    grade = TradeGrade.B
                elif (grade == TradeGrade.D and current.is_bearish
                        and self.htf_bias != "bullish"):
                    grade = TradeGrade.C
                if stock_risk < max(0.10, 0.0015 * current.close):
                    grade = TradeGrade.D
                # PM-level B&R: alert-only (see call side, 24mo both-years split)
                if lo_name == "PML" and grade.value in ("A+", "A", "B"):
                    grade = TradeGrade.C
                # Selection score — mirror of call side.
                hammer = _confirm_candle(current, long=False)
                sc = ((2 if "LATE" not in br_note else 0)
                      + (2 if grade.value in ("A+", "A") else 0)
                      + (2 if stock_risk / current.close >= 0.003 else 0)
                      + (0 if lo_name == "PML" else 1)
                      + (2 if hammer else 0)
                      # F4 Rule 4 S-input — mirror of call side
                      + (1 if self._qqq_aligned(current.timestamp, False) else 0))
                self._route(signals, {
                        "signal_type": SignalType.BREAK_AND_RETEST,
                        "reason": (f"B&R short — prior breakdown below {lo_name} ${level_lo:.2f}, "
                                   f"retest with {grade.value} PA"
                                   + (" [late]" if "LATE" in br_note else " [clean]")
                                   + (" [hammer]" if hammer else "")
                                   + self._bnr_tags(current, stock_risk, is_long=False)
                                   + f" S{sc}"),
                        "entry": current.close,
                        "stop": stop,
                        "direction": "put",
                        "grade": grade.value,
                        "stop_level_name": lo_name,
                        "stop_width_pct": round(stock_risk / current.close * 100, 2),
                        "aplus_stack": stack,
                    })

        # B&R short via FVG (mirror of the long side)
        if FVG_RETEST:
            fvg = find_fvg(self.candles, "bearish")
            for _hi, lo_name, level_hi, level_lo in level_pairs:
                if fvg is None or fvg[1] > level_lo:  # gap must sit below the broken level
                    continue
                prior_breakdown = any(c.close < level_lo for c in lookback)
                already_at_level = current.high >= level_lo
                if (prior_breakdown and not already_at_level
                        and current.high >= fvg[0] and current.close < fvg[0]):
                    stock_risk = fvg[1] - current.close
                    grade = PriceActionAnalyzer.grade_trade(current, lookback, fvg[1], fvg[0],
                                                            is_long=False, htf_bias=self.htf_bias)
                    if stock_risk < 0.50:
                        grade = TradeGrade.D
                    self._route(signals, {
                            "signal_type": SignalType.BREAK_AND_RETEST,
                            "reason": f"B&R short — FVG retest ${fvg[0]:.2f}-${fvg[1]:.2f} below {lo_name} ${level_lo:.2f}, {grade.value} PA",
                            "entry": current.close,
                            "stop": fvg[1],
                            "direction": "put",
                            "grade": grade.value,
                            "stop_level_name": "FVG high",
                            "stop_width_pct": round(stock_risk / current.close * 100, 2),
                        })
                    break

        # Order block short: last green candle before the structural LL (SPEC3)
        block, retest, note = detect_order_block_setup(self.candles, "bearish")
        if (block is not None and retest in OB_RETEST_TYPES
                and current.close < block.low and _volume_ok(self.candles)):
            stock_risk = block.high - current.close
            # Grade at the block's own level (see call side)
            grade = PriceActionAnalyzer.grade_trade(current, lookback, block.high, block.low,
                                                    is_long=False, htf_bias=self.htf_bias)
            if stock_risk < 0.50:
                grade = TradeGrade.D
            # Mirror of call side: A-grade + tight stop only (2026-07-10 split).
            if grade.value == "B":
                grade = TradeGrade.C
            if stock_risk / current.close > 0.004:
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

        # Flag short (Austin 2026-07-08): pole down -> tight pause -> breakdown.
        flag, fnote = detect_flag_setup(self.candles, "bearish") if FLAG_ENABLED else (None, "")
        if flag is not None and current.close < flag["flag_hi"] and _volume_ok(self.candles):
            stock_risk = flag["flag_hi"] - current.close
            grade = PriceActionAnalyzer.grade_trade(current, lookback, flag["flag_hi"], flag["flag_lo"],
                                                    is_long=False, htf_bias=self.htf_bias)
            if stock_risk < 0.50:
                grade = TradeGrade.D
            self._route(signals, {
                    "signal_type": SignalType.ONE_CANDLE_RULE,
                    "reason": f"Flag short — {fnote}, breakdown ${flag['flag_lo']:.2f}, {grade.value} PA",
                    "entry": current.close,
                    "stop": flag["flag_hi"],
                    "direction": "put",
                    "grade": grade.value,
                    "stop_level_name": "Flag high",
                    "stop_width_pct": round(stock_risk / current.close * 100, 2),
                })

        # 84% Rule short (mirror of long: stopped-out PUT, strong-PA rejection back
        # below the failed entry, original target, stop above the rejection candle)
        if (self.session.entry_price is not None
                and self.session.entry_direction in (None, "put")
                and current.close <= self.session.entry_price
                and current.is_bearish
                and (RULE84_LESSON or self._strong_pa(current))):
            day_range = hod - lod
            # 2026-07-10: remaining reward must still be >=1.5x risk at re-entry
            # (12mo: avg re-entry had 1.4R left, some 0.6R — geometry gone)
            stop_chk = (self.session.entry_stop if RULE84_LESSON
                        and self.session.entry_stop is not None else current.high)
            tgt = self.session.entry_target
            rr_ok = (tgt is not None and stop_chk > current.close
                     and (current.close - tgt) >= 1.5 * (stop_chk - current.close))
            if day_range > 0 and (current.close - lod) / day_range > 0.2 and rr_ok:
                stop_84 = stop_chk
                stock_risk = stop_84 - current.close
                grade = PriceActionAnalyzer.grade_trade(current, lookback,
                                                        self.session.entry_price, self.session.entry_price,
                                                        is_long=False, htf_bias=self.htf_bias)
                if grade == TradeGrade.C:  # see call side
                    grade = TradeGrade.B
                self._route(signals, {
                        "signal_type": SignalType.REENTRY_84_RULE,
                        "reason": (f"84% short — prior entry ${self.session.entry_price:.2f} "
                                   f"rejected ({grade.value} PA)"
                                   + (" [hammer]" if _confirm_candle(current, long=False) else "")),
                        "entry": current.close,
                        "stop": stop_84,
                        "target": self.session.entry_target,
                        "direction": "put",
                        "grade": grade.value,
                        "stop_level_name": "Original stop" if RULE84_LESSON else "Rejection candle high",
                        "stop_width_pct": round(stock_risk / current.close * 100, 2) if current.close else 0,
                    })
                # One re-entry per failed setup (see call side)
                self.session.entry_price = None

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
