"""SPEC17 - Backtest OMEN signals over the last trading week.

Walk-forward: replay each session bar-by-bar through SignalRunner.detect_signals,
capture every signal (fired + D-grade/tight-stop skips), simulate outcomes
(2R target vs stop), and write backtest_report.md.

Data: yfinance 1-min bars (free tier covers ~7 days back). P&L assumes fixed
$1000 risk per trade: win = +$2000 (2R), loss = -$1000, scratch = R-multiple x $1000.

Usage: python backtest_week.py [YYYY-MM-DD ...]   (default: last week's sessions)
"""

import math
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
try:                          # yfinance is a settled dead end for OMEN; only the
    import yfinance as yf     # live-fetch path below still touches it, never the
except ModuleNotFoundError:   # data_archive replay the research rows run on.
    yf = None

from omen_bot import Candle, SignalType, TradeGrade
from signal_runner import SignalRunner
from stop_rule import (stop_hit_on_close, stop_hit_on_wick, stop_fill_price,
                       disaster_stop_price, disaster_stop_hit, DISASTER_STOP_R,
                       MAX_LOSS_R)
# The ONE entry fill, the twin of stop_rule above. This module never computes an
# entry price of its own: `sig["entry"]` already came through `entry_fill` inside
# `signal_runner.fill_price`, and the three forward-looking modes -- which the
# engine cannot resolve, because it only ever sees `candles[:i + 1]` -- are
# re-priced through the SAME function at the trade-creation site below.
import entry_fill
from entry_fill import ENTRY_FILL

# The exit ladder (MASTER SPEC, lane: exits). `build_rungs` is the one pure
# function that turns entry/stop/direction + a causal level pool into 1-4
# profit rungs -- see levels_ladder.py's module docstring for the frozen
# contract. Imported unconditionally (cheap, no I/O) so SCALE_PLAN=four_rung
# can be selected at runtime without a reimport.
import levels_ladder as ladder

# Days the entry order never filled. One row per missed setup, appended by
# `simulate_day`, read by `backtest_2y` and by anything comparing order types.
# EMPTY on the shipped default -- a market order at the close always fills. It
# exists because the alternative is what the first resting-limit arm did:
# silently drop the days it could not get into, which makes a limit look like a
# free option instead of a rule that misses trades.
ENTRY_FILL_MISSES: List[dict] = []

# Austin's watchlist 2026-07-11: all stocks with ~200k+ daily options volume
# (his rule — high options volume = cleaner moves, easier fills). SPY/QQQ stay
# as trend reference, rarely traded.
# Watchlist tiers live in universe.py -- the single source of truth. Re-exported
# here because six modules import them from backtest_week (OMEN 6 ticket 14).
from universe import (CORE_SYMBOLS, EXPERIMENTAL_SYMBOLS,  # noqa: F401
                      BACKTEST_SYMBOLS as SYMBOLS, MIN_SAMPLE_N)
RISK_DOLLARS = 1000.0

# ---- D2: S-score-scaled position sizing (flag-gated, default OFF) ----
# Scale per-trade risk by the selection score printed in the signal reason
# (" S<n>"): S=4 -> 1.0x, S=5 -> 1.25x, S>=6 -> 1.5x, on the $1k base.
# P&L is linear in risk dollars (pnl = R-multiple * risk_dollars), so a
# higher-conviction trade risks — and returns — proportionally more; only
# S>=5 scales up, S<=4 and unscored trades stay at base $1k. Sizing changes
# no signal detection or outcomes, just the dollar multiplier on each trade.
# Env: OMEN_SSCORE_SIZING=1. Default OFF (flat $1k), no existing default moved.
SSCORE_SIZING = os.environ.get("OMEN_SSCORE_SIZING", "0") == "1"


def sscore_mult(reason: str) -> float:
    """Per-trade risk multiplier from the S-score in `reason` (D2, flag-gated).
    Flat 1.0x when the flag is OFF or no S-score is present."""
    if not SSCORE_SIZING:
        return 1.0
    m = re.search(r" S(\d+)", reason or "")
    if not m:
        return 1.0
    s = int(m.group(1))
    if s >= 6:
        return 1.5
    if s == 5:
        return 1.25
    return 1.0
# ---- R16: dedupe by LEVEL, not by clock ------------------------------------
# Austin, probe_master_2026-08-29, fact_dedupe -> `level`:
#   "it doesent matter when the trade re sets up as long as it happens during
#    the window"
# The KEY was already the level (the broken level's name for a break-and-retest,
# the block price otherwise). What he deleted is the CLOCK around it: a level
# that broke, retested, failed and set up again 12 minutes later was thrown away
# as a duplicate of the first. It is a second trade.
#
# What survives is the only thing the clock was really needed for: the detector
# re-fires on every bar while the setup is still standing there, and those are
# one idea, not twenty. DEDUPE_MODE="level" suppresses a repeat only while the
# same level is firing on CONSECUTIVE bars; one quiet bar and the next fire is a
# new trade. DEDUPE_MODE="clock" restores the 30-minute window for the A/B.
DEDUPE_MODE = os.getenv("DEDUPE_MODE", "level").strip().lower()
DEDUPE_BARS = 30  # clock arm only: same setup re-firing within 30 min = one idea
DEDUPE_CONTIG = 2  # level arm: suppress only a contiguous run of re-fires

# G7.2 (suppress): ONLY A FIRE MAY OPEN OR EXTEND THE SUPPRESSION WINDOW.
# Until 2026-08-29 the `seen` map below was written by EVERY captured signal,
# including the ones SignalRunner._route had just REJECTED -- D-grade, tight
# stop, repeat idea, repeat entry, retired level. A reject on bar i therefore
# silenced the real, tradeable fire on bar i+1 at the same level, and a run of
# rejects rolled that window forward indefinitely. The dedupe exists to collapse
# "the detector re-fires while the setup is still standing there" into one
# TRADE; a signal that never became a trade has nothing to collapse.
# signal_runner._route already gets this right for its own no-repeat registry --
# "a tight-stop skip never fired, so it must not claim the level -- the first
# AVAILABLE entry wins" -- and this makes the backtest agree with it.
# DEDUPE_FIRES_ONLY=0 restores the old behaviour for the A/B.
# Priced in research/g72_suppress_report.md by research/g72_suppress_price.py.
DEDUPE_FIRES_ONLY = os.getenv("DEDUPE_FIRES_ONLY", "1").strip().lower() not in (
    "0", "false", "no", "off")


def dedupe_window() -> int:
    """Bars of suppression after a fire. Read at call time so an A/B can flip
    DEDUPE_MODE on the module without re-importing."""
    return DEDUPE_BARS if DEDUPE_MODE == "clock" else DEDUPE_CONTIG


REPORT_PATH = Path(__file__).parent / "backtest_report.md"

# ---- Rule 6: Position Management (Scarface: scale 50% at HOD/breakeven) ----
# Austin 2026-07-10: "Mgmt: scale HOD / breakeven at post-entry red OB."
# When price hits entry + 1R (calls) / entry - 1R (puts), close 50% at breakeven,
# move runner stop to entry, let runner ride to 2R. Improves R:R by locking partial
# profit and reducing max-loss frequency (runner is free after breakeven).
RULE6_ENABLED = False     # toggle for backtest comparison; 12mo A/B 2026-07-12
                          # (backtest_rule6_comparison.md): stays OFF per synthesis
RULE6_SCALE_PCT = 0.5      # fraction of position closed at breakeven
RULE6_BE_MULT = 1.0        # breakeven level = entry +- 1R x this multiplier

# ---- F1: Liquidity-ladder exits (fable-spec-2026-07-12, audit #7) ----
# Source: "exit some at high of day every single time", then next draw of
# liquidity (PDH/PDL, psych whole numbers); "2:1 is the MINIMUM aggregate
# expectation, not the exit mechanism". Blind 2R was our invention.
#   None = blind 2R (current behavior)
#   "hod_then_runner"    = 50% off at first HOD/LOD touch after entry (session
#          extremes as-of entry bar, no lookahead); stop unchanged until scale;
#          runner to first key level beyond the scale point (PDH/PDL/PMH/PML/
#          next whole dollar; fallback = original 2R target); runner keeps
#          original stop. (Was called ladder mode "A".)
#   "hod_then_runner_be" = hod_then_runner + stop -> breakeven after the first
#          scale. (Was called ladder mode "B".)
# W% note: scaled trades are labeled win/loss by SIGN of total P&L; EOD runners
# stay "scratch" (same as blind-2R). 84% arming: only FULL stop-outs (unscaled)
# arm a re-entry — a scaled trade already paid, "stop was wrong" doesn't apply.
# omen-5.0 T4(d): SCALE_PLAN defaults to "hod_then_runner_be" — Austin's real
# management, stated 2026-08-11 and in his notes before it: scale out at 1R and
# let a runner go, "you always take something off at HOD; true 2R only when
# target coincides with HOD". The F1 A/B recorded here measured that plan (once
# called ladder mode B) at a 58% win rate against blind-2R's larger dollar
# figure; his gate is a 55% win rate, so it is the book that answers the
# question he is actually asking. Blind 2R stays reachable (OMEN_SCALE_PLAN=none)
# so the old number is reproducible — the comment on the F1 line above says it
# outright: "Blind 2R was our invention."
#
# P5 (2026-08-26): renamed from LADDER_MODE. Its "A"/"B" values read as trade
# grades in every table and conversation — Austin: "what's ladder B — B is not
# a grade anymore." It never was a grade; it is this exit plan. OMEN_LADDER_MODE
# is kept working below as a deprecated alias (values "A"/"B"/"none" map onto
# the new words) so committed research docs that say "reproduce with
# OMEN_LADDER_MODE=B" don't go stale. Remove the alias once no research/*.md
# still cites the old env var.
_LEGACY_LADDER_MAP = {"a": "hod_then_runner", "b": "hod_then_runner_be"}
_SCALE_ENV = os.environ.get("OMEN_SCALE_PLAN")
if _SCALE_ENV is None:
    _legacy_env = os.environ.get("OMEN_LADDER_MODE", "B").strip()
    _SCALE_ENV = _LEGACY_LADDER_MAP.get(_legacy_env.lower(), _legacy_env)
else:
    _SCALE_ENV = _SCALE_ENV.strip()
SCALE_PLAN = None if _SCALE_ENV.lower() in ("", "none", "0", "off") else _SCALE_ENV
# OMEN_SCALE_PLAN="four_rung" selects the new engine below (`_ladder_bar_4`),
# a sibling of `_ladder_bar` -- see "THE EXIT LADDER" flags immediately below.

# ---- THE EXIT LADDER (MASTER SPEC, lane: exits, g99/ga1) ------------------
# Austin, on the anatomy cards: "way too tight, if we know our mean RR is 2.5
# we shouldnt be targeting .41" / "2r level is trumped by HTF levels and
# whole psych number if one is close." g99_rung_recon.py measured why: the
# TWO-rung F1 ladder's `runner_tgt` (backtest_week.py:1032-1043, unchanged
# above) is computed from levels beyond `scale_level` and never compared to
# the 2R `target` a few lines up -- so it lands INSIDE 2R on 303/444 (68.2%)
# of first-of-day trades, median 1.30R. LADDER_RUNNER_GUARD (below) is the
# two-line fix, measured alone; OMEN_SCALE_PLAN=four_rung is the full
# four-rung replacement (levels_ladder.build_rungs), a new sibling engine
# that leaves `_ladder_bar` and every existing SCALE_PLAN value untouched.
#
# Every flag here defaults to today's shipped behaviour -- with SCALE_PLAN
# != "four_rung" and LADDER_RUNNER_GUARD=0, not one line of an existing path
# executes differently (byte-identical; research/test_exit_ladder.py's
# `test_shipped_default_byte_identical` is the proof).
LADDER_RUNNER_GUARD = os.getenv("LADDER_RUNNER_GUARD", "0").strip().lower() not in (
    "0", "false", "off", "")


def _parse_ladder_weights(s: str) -> Tuple[float, float, float, float]:
    """"30/30/30/10" (percentages, the usual spelling) or "0.3/0.3/0.3/0.1"
    (already fractions) -> a 4-tuple summing to 1.0. Detected by magnitude:
    a sum > 1.5 is read as percentages."""
    parts = [float(x) for x in s.split("/")]
    if len(parts) != 4:
        raise SystemExit("LADDER_WEIGHTS must be 4 slash-separated numbers "
                         "(e.g. \"30/30/30/10\"), got %r" % s)
    total = sum(parts)
    if total <= 0:
        raise SystemExit("LADDER_WEIGHTS must sum to a positive number, got %r" % s)
    scaled = [p / 100.0 for p in parts] if total > 1.5 else parts
    return tuple(scaled)


def _parse_psych_tol(s: str) -> Tuple[str, float]:
    """"0.25r" / "0.10c" / "0.05pct" (or "%") -> (unit, value)."""
    s = s.strip().lower()
    for suffix, unit in (("pct", "pct"), ("%", "pct"), ("r", "r"), ("c", "c")):
        if s.endswith(suffix):
            try:
                return unit, float(s[: -len(suffix)])
            except ValueError:
                break
    raise SystemExit("LADDER_PSYCH_TOL must end in r/c/pct (e.g. \"0.25r\"), got %r" % s)


def _parse_rung_gap(s: str) -> float:
    """"0.20r" (or a bare number) -> the fraction of risk, as a float."""
    s = s.strip().lower()
    return float(s[:-1]) if s.endswith("r") else float(s)


LADDER_WEIGHTS = _parse_ladder_weights(os.getenv("LADDER_WEIGHTS", "30/30/30/10"))
LADDER_PSYCH_TOL = _parse_psych_tol(os.getenv("LADDER_PSYCH_TOL", "0.25r"))
LADDER_PSYCH_STEP = float(os.getenv("LADDER_PSYCH_STEP", "1.00"))
LADDER_PT4_MODE = os.getenv("LADDER_PT4_MODE", "max").strip().lower()
LADDER_PT4_R = float(os.getenv("LADDER_PT4_R", "4.0"))
LADDER_MIN_RUNG_GAP = _parse_rung_gap(os.getenv("LADDER_MIN_RUNG_GAP", "0.20r"))
LADDER_TRAIL = os.getenv("LADDER_TRAIL", "be").strip().lower()
if LADDER_TRAIL not in ("be", "prev_rung"):
    raise SystemExit("LADDER_TRAIL must be 'be' or 'prev_rung', got %r" % LADDER_TRAIL)

# LADDER_TREND_TEST (spec section 4): a MEASURED OPTION ONLY, off by default.
# "daily" reads the already-threaded `bias` (signal_runner.daily_trend_bias,
# causal: SMA20 of PRIOR sessions' daily closes) against the trade direction.
# "qqq" reads `runner.qqq_breaks` (live_scanner.compute_qqq_breaks) and
# requires the break to be strictly EARLIER than the entry bar's own
# timestamp -- the causal half of the comparison. Per his sentence ("if day
# is not trending, we want those HOD exits more money quicker"): trending ->
# 30/30/30/10, not trending -> 50/20/20/10, REGARDLESS of LADDER_WEIGHTS --
# these two vectors are the arm definition, not a knob.
LADDER_TREND_TEST = os.getenv("LADDER_TREND_TEST", "off").strip().lower()
if LADDER_TREND_TEST not in ("off", "daily", "qqq"):
    raise SystemExit("LADDER_TREND_TEST must be 'off'/'daily'/'qqq', got %r" % LADDER_TREND_TEST)
_TREND_WEIGHTS_ON = (0.30, 0.30, 0.30, 0.10)
_TREND_WEIGHTS_OFF = (0.50, 0.20, 0.20, 0.10)
# Reachability bookkeeping (P7/G1 pattern) -- research/ga1_ladder_replay.py
# reads this to enforce the spec's 15%/85% reachability gate on the arm.
LADDER_TREND_FUNNEL: Counter = Counter()

# LADDER_HTF_PIVOTS: the spec's last build-order item -- 1h/4h pivots.
# `research/htf_levels.py` (htf_level_beyond / htf_candles / htf_pivots)
# landed from a parallel session while this pass was in flight, but it reads
# its own bars off the Polygon archive by symbol/day, not this module's
# `candles` list (which `fetch_week`/`backtest_12mo` source from
# yfinance/Polygon depending on caller) -- wiring it in here risks a second,
# silently different data source per level. NOT wired in this pass, which is
# scoped to backtest_week.py; see this build's `blockers`. The flag is
# defined for book-stamp/env parity and defaults OFF (today's book is
# unaffected either way); turning it ON degrades to "no HTF pivots added"
# with one warning rather than pretending to have wired it.
LADDER_HTF_PIVOTS = os.getenv("LADDER_HTF_PIVOTS", "0").strip().lower() not in (
    "0", "false", "off", "")
_htf_pivots_warned = False


def _warn_htf_pivots_once() -> None:
    global _htf_pivots_warned
    if not _htf_pivots_warned:
        print("[backtest_week] LADDER_HTF_PIVOTS=1 requested but is not wired "
             "into backtest_week.py yet (research/htf_levels.py exists but "
             "reads its own archive bars, not this module's `candles`) -- "
             "proceeding WITHOUT 1h/4h pivots (named_levels still carries "
             "PDH/PDL/PMH/PML/OR/1m pivots).", file=sys.stderr)
        _htf_pivots_warned = True


def _named_level_pool(candles: List[Candle], i: int,
                      pdh: Optional[float], pdl: Optional[float],
                      pmh: Optional[float], pml: Optional[float]) -> dict:
    """The causal level pool `build_rungs` draws PT2/PT3-substitute/PT4-structure
    candidates from -- PDH/PDL, PMH/PML, OR high/low, and same-timeframe
    pivots (`signal_runner.pivot_levels`, always called with `as_of=i` so a
    pivot needing bars past the entry bar is never returned). 1h/4h pivots
    join this pool only under LADDER_HTF_PIVOTS (see above)."""
    levels = {}
    if pdh is not None:
        levels["PDH"] = pdh
    if pdl is not None:
        levels["PDL"] = pdl
    if pmh is not None:
        levels["PMH"] = pmh
    if pml is not None:
        levels["PML"] = pml
    # Opening range (first 5 bars) -- causal for every i >= 5, which is where
    # the day loop in simulate_day starts.
    levels["ORH"] = max(cd.high for cd in candles[:5])
    levels["ORL"] = min(cd.low for cd in candles[:5])
    from signal_runner import pivot_levels as _pivot_levels
    for pv in _pivot_levels(candles[: i + 1], as_of=i):
        levels[pv["name"]] = pv["price"]
    if LADDER_HTF_PIVOTS:
        _warn_htf_pivots_once()
    return levels


def _ladder_weights(direction: str, bias: Optional[str], qqq: Optional[dict],
                    entry_ts: str) -> Tuple[float, float, float, float]:
    """LADDER_TREND_TEST arm selection (spec section 4). "off" (default)
    always returns LADDER_WEIGHTS; "daily"/"qqq" pick between the two fixed
    vectors above by whether the day reads as trending, and count which
    vector each row selected so the reachability gate (>=15%, <=85%) can be
    checked without a second pass."""
    if LADDER_TREND_TEST == "off":
        return LADDER_WEIGHTS
    if LADDER_TREND_TEST == "daily":
        if bias is None:
            LADDER_TREND_FUNNEL["bias_none"] += 1
            trending = False
        else:
            trending = (bias == "bullish" and direction == "call") or \
                      (bias == "bearish" and direction == "put")
    else:  # "qqq"
        ts = (qqq or {}).get("up" if direction == "call" else "dn")
        trending = bool(ts) and ts < entry_ts
    LADDER_TREND_FUNNEL["trending" if trending else "chop"] += 1
    return _TREND_WEIGHTS_ON if trending else _TREND_WEIGHTS_OFF


def _psych_tol_r(risk: float, entry: float) -> float:
    """LADDER_PSYCH_TOL converted to a fraction of risk, for the runner
    guard's own precedence check (legacy two-rung plans only)."""
    unit, value = LADDER_PSYCH_TOL
    if unit == "r":
        return value
    if unit == "c":
        return value / risk if risk else 0.0
    return (value / 100.0 * entry) / risk if risk else 0.0


# ---- R11 / T11: "enough movement" raises the stop to break-even ----------
# Austin, probe_master_2026-08-29, fact_be_trigger, verdict `move`: "if we dont
# hit price target 1, we dont raise the stop to BE, but we need to run stats on
# with enough movement raising to BE" -- and separately, on the base case:
# "can still focus on first PT move to BE".
#
# BE_TRIGGER="pt1" (default) is exactly today's F1 ladder behaviour: the stop
# only moves to entry when the scale rung (causal HOD/LOD, "PT1") is touched --
# see the `hod_then_runner_be` accelerator below. BE_TRIGGER="mfe" arms the
# SAME stop-to-entry move on a plain favourable-excursion threshold
# (BE_MOVE_R * original risk, tested against the bar's high/low -- MFE is a
# wick concept, the stop that moves because of it is still close-triggered)
# instead of waiting for the scale rung. Whichever fires first wins; once
# `runner_stop` is set neither path re-arms it.
BE_TRIGGER = os.getenv("BE_TRIGGER", "pt1").strip().lower()
BE_MOVE_R = float(os.getenv("BE_MOVE_R", "0"))

# omen-5.0 T4(a): the stop TRIGGERS on the candle CLOSE, not on a wick through
# the level. Austin has written this five times in one grading batch — "stop out
# happens when candle CLOSES below the level", "stop outs only happen when candle
# closes by the way", "your entry never closed below the stop so no need 84
# percent rule". The exit PRICE stays t.stop: his stop order still fills at the
# level, only the trigger moves. STOP_ON_CLOSE=0 reproduces the old wick
# behaviour for the A/B in research/t4_stop_on_close.md. Default ON.
STOP_ON_CLOSE = os.getenv("STOP_ON_CLOSE", "1") not in ("0", "false")

# omen-5.1 T2: the same-bar tie. A resting limit target fills on an intrabar
# TOUCH; a stop needs a CLOSE beyond the level. One bar can do both, and from a
# 1-minute bar you cannot know which came first — assuming the target tagged
# first is the most optimistic assumption in the whole backtest. Default ON:
# a bar that touches the target AND closes beyond the stop books the LOSS, at
# the trade's ORIGINAL stop, at every rung of ladder B. The 1R scale-out takes
# no partial credit. PESSIMISTIC_FILL=0 reproduces the old behaviour exactly so
# both arms backtest (research/t51_fill.md, research/t51_ev_honest.md).
PESSIMISTIC_FILL = os.getenv("PESSIMISTIC_FILL", "1") not in ("0", "false")

# ---- R1 / R2: the disaster stop (Austin, probe_master_2026-08-29) ----------
# `fact_two_stops` verdict `both`; `fact_stop_floor_is_fiction` verdict `hard`,
# note: "-1r is what we want max slippage -1.25".
#
# A resting order at entry -/+ DISASTER_STOP_R x original risk, filled on an
# intrabar TOUCH, underneath the close-triggered LEVEL stop. -1.25R
# (stop_rule.MAX_LOSS_R) is NOT a second stop: it stays the outer bound the
# close-fill is clamped to, for the bars that gap straight past the resting
# order.
#
# Tested BEFORE the level stop on every bar: a bar that touched -1R and then
# closed further away was already out at -1R, so booking its close instead
# would credit the trade with a loss it never took.
#
# Ships ON at his ratified number. DISASTER_STOP=0 restores the clamp-only book
# every figure before 2026-08-29 was measured on; DISASTER_STOP_R sweeps where
# the order rests (T1's arms).
DISASTER_STOP = os.getenv("DISASTER_STOP", "1") not in ("0", "false", "off")
DISASTER_R = float(os.getenv("DISASTER_STOP_R", str(DISASTER_STOP_R)))

# ---- G8.2: the four stop arms, for research/g82_stop_ab.py -----------------
# Austin, on the close-only stop rule: it stands "if you have the metrics."
# Nobody had run the plain A/B, so STOP_ARM names each arm as ONE word and every
# arm is expressed here rather than by stacking three half-related env flags.
#
#   ""              the book as shipped. Untouched: close trigger + the resting
#                   -1R disaster stop on touch + the -1.25R floor. Default, and
#                   byte-identical to every figure published before today.
#   "close_floor"   close trigger, fill at that close, floored at -1.25R, and
#                   NO disaster stop. This is the rule CLAUDE.md actually states,
#                   on its own, which the shipped book does not run.
#   "close_nofloor" the same with the floor removed.
#   "touch"         a resting stop order: triggers the moment price TOUCHES the
#                   level, fills THERE -- or at the bar's open when the bar
#                   gapped straight through it. No floor.
#   "touch_floor"   the same, floored at -1.25R, so the floor is doing gap
#                   protection and nothing else.
#
# Every named arm turns the disaster stop OFF, because each one states its own
# complete stop semantics; leaving a second stop underneath would measure the
# two together and that is exactly the confusion this A/B exists to end.
STOP_ARM = os.getenv("STOP_ARM", "").strip().lower()
_ARMS = ("", "close_floor", "close_nofloor", "touch", "touch_floor")
if STOP_ARM not in _ARMS:
    raise SystemExit("STOP_ARM must be one of %r, got %r" % (_ARMS, STOP_ARM))
STOP_ARM_TOUCH = STOP_ARM.startswith("touch")
STOP_ARM_FLOOR = STOP_ARM in ("close_floor", "touch_floor")

# ---- G8.2: the two profit-leg arms ----------------------------------------
# Austin believes a profit target fills the moment price TOUCHES it (a resting
# limit order) and suspects the code may instead require a candle to CLOSE
# through it. It does not -- every profit leg here is an intrabar touch and
# always has been (`_target_hit` below, and the three call sites it replaced).
# TARGET_ON_CLOSE=1 builds the arm he was worried about so the belief is
# measured instead of asserted. Default 0 = touch = shipped, byte-identical.
#
# It governs all three profit legs together -- the blind-2R target, the ladder's
# PT1 scale rung, and the runner target -- because they are the same kind of
# order and splitting them would answer a question nobody asked.
TARGET_ON_CLOSE = os.getenv("TARGET_ON_CLOSE", "0").strip().lower() in (
    "1", "true", "yes", "on")

# ---- P8/G2: ENTRY_SCRATCH — Austin's failed-entry scratch, one bar late ----
# Austin, 2026-08-11: "an entry taken intrabar that then closes back beyond the
# level is not a loss — scratch out at close, no 84 percent, this rule and
# previous applys to BR and OCR as well."
#
# The T4(b) implementation of that sentence tested the ENTRY bar's own close
# against sig["stop"], at the trade-creation site below. It was UNREACHABLE by
# construction and never fired in two years. Every detector requires the entry
# bar to CLOSE through the retested level (detect_break_retest step 4;
# `current.close > block.high` for the order block; `close >= entry_price` for
# the 84% reclaim), and every stop sits at or beyond that level on the losing
# side — so the entry bar's close is on the good side of BOTH lines, always.
# research/p8_scratch.md carries the measured distribution.
#
# The cause is that this engine is bar-CLOSE driven. It cannot take an entry
# "intrabar" in the sense Austin means: it decides at the close of bar i, and
# fill_price() only back-dates the PRICE to the level. A bar that trades through
# the level and closes back is never entered at all — detect_break_retest's
# `no_confirm_close` return IS that scratch, taken before the fill instead of
# after it. So the earliest bar on which "closes back beyond the level" can be
# true here is entry_idx + 1, and that is the bar this flag tests.
#
#   ENTRY_SCRATCH=level  the bar AFTER entry closes back through the RETESTED
#                        LEVEL (sig["level_price"]) -> scratch at that close,
#                        clamped no worse than the trade's own stop (his stop
#                        order still fills at the level), and _arm_84 is never
#                        called. Tested BEFORE the stop, so the scratch wins the
#                        bar.
#   ENTRY_SCRATCH=stop   the same one-bar shift read against sig["stop"] — the
#                        dead branch's own line. Measured for the report, NOT
#                        recommended: with BNR_STOP_MODE="level" the stop IS the
#                        level, so it re-labels ordinary close-based stop-outs as
#                        scratches and contradicts the settled rule that "stop
#                        out happens when candle CLOSES below the level".
#   ENTRY_SCRATCH=0      OFF — the shipped default, byte-identical to the book.
ENTRY_SCRATCH = os.getenv("ENTRY_SCRATCH", "0").strip().lower()
if ENTRY_SCRATCH in ("", "0", "off", "false", "none"):
    ENTRY_SCRATCH = ""

# P8/G2 bookkeeping, the way ARM84_FUNNEL is bookkeeping: one row per created
# trade saying where the entry bar's close — and the NEXT bar's close — sit
# relative to the retested level and to the stop, in units of the entry bar's
# own range. Collected only under SCRATCH_PROBE=1 (research/p8_scratch.py drives
# it); untouched and empty otherwise, so the canonical replay is unaffected.
SCRATCH_PROBE_ON = os.getenv("SCRATCH_PROBE", "0").strip().lower() \
    in ("1", "true", "yes", "on")
SCRATCH_PROBE: List[dict] = []

# ---- R2 (Austin, 2026-09-03 ruling) — the gave-it-back EXIT --------------
# "A trade that ran and came back through its entry candle is dead. Exit at
# that close; do not wait for the stop." Objective, causal, needs no new
# data -- no fitted threshold, no MFE precondition: the boundary is the
# ENTRY CANDLE's own range (`t.entry_candle_lo` / `_hi`, captured once at
# trade creation from the fill bar), not `t.level_price` (the retested
# level, read only by ENTRY_SCRATCH above) and not `t.stop`.
#
# Distinct from `omen_bot.detect_break_retest`'s pre-entry gave-it-back
# veto (a candidate never taken at all): this is an IN-TRADE exit, checked
# on every bar of an open position, not only the bar after entry.
#
# Bar-ordered and causal, checked in `_ladder_bar` / `_ladder_bar_4` / the
# binary path AFTER the disaster stop and the level stop -- so a bar that
# satisfies both this and the stop goes to the STOP, matching the
# "conservative: stop wins ties" convention already in this file. The fill
# is `_stop_fill_px` (which itself is nothing but `stop_rule.stop_fill_price`)
# -- never a locally invented price.
#
# Default OFF, byte-identical to the shipped book when off.
# research/g112_gave_it_back_exit.py measures it.
GAVE_IT_BACK_EXIT = os.getenv("GAVE_IT_BACK_EXIT", "0").strip().lower() not in (
    "0", "false", "off", "")

# Pure bookkeeping, the way ARM84_FUNNEL is bookkeeping: one tick per trade
# whose exit `_gave_it_back` decided. Reading or ignoring it changes nothing;
# research/g113_gave_it_back_exit.py resets it and reads it back.
GAVE_IT_BACK_FUNNEL: Counter = Counter()


@dataclass
class SimTrade:
    symbol: str
    day: str
    signal_type: str
    direction: str  # call/put
    grade: str
    status: str     # fired / skipped_d / skipped_tight_stop
    entry_time: str
    entry: float
    stop: float
    target: float
    outcome: str = "open"  # win / loss / scratch
    exit_price: float = 0.0
    reason: str = ""
    entry_idx: int = 0
    exit_idx: int = 0
    # Rule 6: breakeven scaling fields
    be_level: float = 0.0     # stock price where 50% is scaled out (0 = disabled)
    be_taken: bool = False     # whether breakeven scale already fired
    runner_stop: float = 0.0   # raised stop for runner after BE taken
    # F1 ladder fields
    scale_level: float = 0.0   # HOD/LOD as-of entry bar (50% scale trigger)
    runner_target: float = 0.0 # first key level beyond scale point
    scaled: bool = False       # ladder 50% scale fired
    # P8/G2: the RETESTED level this setup is keyed to, as a price. Equal to
    # `stop` for a default B&R (BNR_STOP_MODE="level"), NOT equal for the order
    # block (stop = the far side of the block) or when intrabar_stop() collapsed
    # the stop onto the entry bar's own extreme. Read only by ENTRY_SCRATCH.
    level_price: float = 0.0
    # R2 (Austin, 2026-09-03 ruling): the ENTRY CANDLE's own extreme, captured
    # once at trade creation from the fill bar -- low for a long, high for a
    # short. NOT `level_price` (the retested level) and NOT `stop`: read only
    # by `_gave_it_back` below, flag-gated GAVE_IT_BACK_EXIT.
    entry_candle_lo: float = 0.0
    entry_candle_hi: float = 0.0
    # G7.1/labels. The two identity fields signal_runner stamps on every sig
    # and this dataclass used to drop on the floor (research/g71_labeller.md).
    # `setup_type` is SignalType.BR_OCR_CONFLUENCE whenever
    # downgrade.has_confluence held on the entry bar
    # (signal_runner._label_confluence), Austin's third setup class alongside
    # break-and-retest and one-candle-rule. `stop_level_name` is the level the
    # setup actually broke, spelled ("PDH" / "OR high" / "Order block low").
    # Carrying them changes no fill, no grade and no P&L: backtest_2y was
    # already re-deriving a worse version of both from the reason prose with a
    # regex that cannot see an order block or the 84% rule.
    setup_type: str = ""
    stop_level_name: str = ""
    # THE EXIT LADDER (spec 5.3): SCALE_PLAN=four_rung only. `rungs` is the
    # frozen `levels_ladder.Rung` list this trade was built with (empty on
    # every other plan -- the `pnl` branch below reads this to decide which
    # P&L model applies, so an empty tuple is a real behavioural switch, not
    # just bookkeeping). `fills` accumulates (weight, price) in BAR ORDER as
    # rungs fire, a stop books the remainder, or the EOD flush closes it out;
    # sum(weight for weight, _ in fills) == 1.0 once the trade is done.
    rungs: tuple = ()
    fills: list = field(default_factory=list)

    @property
    def counted(self) -> bool:
        # C is alert-only in live_scanner (SPEC2) — excluded from traded P&L
        return self.status == "fired" and self.grade != "C"

    @property
    def is_alert(self) -> bool:
        return self.status == "fired" and self.grade == "C"

    @property
    def pnl(self) -> float:
        """Dollar P&L at RISK_DOLLARS risk per trade.

        Rule 6 (when enabled): if BE scale was taken, the scaled portion
        locks partial profit and the runner rides to breakeven stop/target.
        Without Rule 6, binary P&L as before (win = +2R, loss = -1R).

        84% 2x sizing REMOVED 2026-07-10: re-entries keep the ORIGINAL stop
        but only the REMAINING distance to target (avg 1.4R, some 0.6R)
        -- doubling size on degraded geometry was a martingale
        (12mo: -$8.7k at 2x, all losses -$2k)."""
        risk = abs(self.entry - self.stop)
        if risk == 0:
            return 0.0

        # D2: S-score-scaled risk (flag-gated; 1.0x = flat $1k when OFF).
        risk_dollars = RISK_DOLLARS * sscore_mult(self.reason)

        # THE EXIT LADDER (spec 5.3): SCALE_PLAN=four_rung. Weighted R across
        # every (weight, price) fill, at the trade's ORIGINAL entry/risk --
        # never a raised runner_stop, same convention `_stop_fill_px` uses.
        if self.rungs:
            sign = 1 if self.direction == "call" else -1
            return round(sum(w * sign * (px - self.entry) / risk
                             for w, px in self.fills) * risk_dollars, 2)

        # F1 ladder: 50% filled at scale_level + 50% at exit_price
        if self.scaled:
            sign = 1 if self.direction == "call" else -1
            scale_r = sign * (self.scale_level - self.entry) / risk
            run_r = sign * (self.exit_price - self.entry) / risk
            return round((0.5 * scale_r + 0.5 * run_r) * risk_dollars, 2)

        # Rule 6: BE scale taken -> two-stage P&L
        if self.be_taken:
            be_r = 1.0  # always 1R at breakeven
            be_pnl = be_r * risk_dollars * RULE6_SCALE_PCT
            if self.outcome == "win":
                run_r = 2.0
                run_pnl = run_r * risk_dollars * (1 - RULE6_SCALE_PCT)
            else:
                run_pnl = 0.0
            return round(be_pnl + run_pnl, 2)

        # Original binary P&L (no Rule 6)
        move = (self.exit_price - self.entry) if self.direction == "call" else (self.entry - self.exit_price)
        return round(move / risk * risk_dollars * 1.0, 2)


def _wick_hit(c: Candle, level: float, long: bool) -> bool:
    """Pre-omen-5.0 stop trigger: any wick through the level stops the trade out.
    Reachable only with STOP_ON_CLOSE=0, so the old numbers stay reproducible."""
    return stop_hit_on_wick(c.high, c.low, level, long)


def _stop_hit(c: Candle, level: float, long: bool) -> bool:
    """T4(a). Did this bar stop the trade out? On the CLOSE by default.

    Candle-shaped wrapper over `stop_rule`, which the live path also imports —
    one rule, one function (G11). Reads the module-global STOP_ON_CLOSE on every
    call so research/t4_stop_on_close.py can still flip `bw.STOP_ON_CLOSE`.
    """
    if STOP_ARM_TOUCH:
        return _wick_hit(c, level, long)
    if STOP_ARM:                    # the two close arms, disaster stop removed
        return stop_hit_on_close(c.close, level, long)
    if STOP_ON_CLOSE:
        return stop_hit_on_close(c.close, level, long)
    return _wick_hit(c, level, long)


def _target_hit(c: Candle, level: float, long: bool) -> bool:
    """G8.2. Did this bar take a profit leg at ``level``?

    A resting limit order fills on an intrabar TOUCH -- that is what this
    returns by default, and what all three profit legs (the blind-2R target, the
    ladder's PT1 scale rung, the runner target) have always done inline. The
    function exists so the claim is checkable in one place instead of three, and
    so TARGET_ON_CLOSE=1 can build the close-through arm Austin suspected was
    already shipped. `stop_rule`'s own module docstring says the same thing:
    "Targets are not stops... Only the STOP trigger moved to the close."
    """
    if TARGET_ON_CLOSE:
        return c.close >= level if long else c.close <= level
    return c.high >= level if long else c.low <= level


def _stop_fill_px(t: "SimTrade", c: Candle, long: bool,
                  level: Optional[float] = None) -> float:
    """T11. The price a close-triggered stop BOOKS on bar ``c``.

    The trigger is `_stop_hit` above; this is the other half of the same rule.
    You are out at market once the bar closes beyond the stop, so the fill is
    that close, floored at -1.25R of the trade's ORIGINAL risk
    (`stop_rule.stop_fill_price`, shared with `research/exit_lab` and the live
    `paper_trader`).

    Until 2026-08-28 all three exit sites here filled at `t.stop` instead, which
    is -1.000R by construction. `research/x2_stop_floor_audit.md` measured the
    consequence on the shipped book: 458 of 474 stop-outs (96.6%) were triggered
    by a candle that had ALREADY closed past 1R -- median -1.35R, worst -4.36R --
    and every one was booked as exactly -1.000R, which is why the -1.25R floor
    never bound on any of 45,193 rows. Austin, 2026-08-28: "fix stop out 1.25 max
    slippage this needs to be fixed now."

    ``entry`` and ``abs(entry - stop)`` are always the trade's ORIGINAL pair,
    never the moved runner stop -- the floor is -1.25R of the whole trade, not
    -1.25R measured off whichever stop happened to fire. Under STOP_ON_CLOSE=0
    (the retired wick trigger, kept only so t4_stop_on_close's A/B reproduces)
    there is no close to fill at, so the old `t.stop` fill stands.

    G8.2: ``level`` is the stop that actually fired -- the original one, or the
    runner's raised one. Only the named STOP_ARM arms read it, and they must:
    a resting order fills where it RESTS, and a resting order at break-even
    that filled at `t.stop` would book -1R for a trade that lost nothing. The
    shipped path ignores it and is unchanged.
    """
    risk = abs(t.entry - t.stop)
    if STOP_ARM:
        floor = MAX_LOSS_R if STOP_ARM_FLOOR else float("inf")
        if STOP_ARM_TOUCH:
            lv = t.stop if level is None else level
            # A resting order fills at its own price -- unless the bar OPENED
            # through it, in which case the fill is that open. This is the only
            # way a touch arm can lose more than it planned, so it is also the
            # only thing the -1.25R floor is protecting against here.
            raw = min(lv, c.open) if long else max(lv, c.open)
        else:
            raw = c.close
        return stop_fill_price(raw, t.entry, risk, long, floor)
    if not STOP_ON_CLOSE:
        return t.stop
    return stop_fill_price(c.close, t.entry, risk, long)


def _disaster_hit(t: "SimTrade", c: Candle, long: bool):
    """R1/R2. The resting -1R order's fill price on bar ``c``, or None.

    ``None`` when the flag is off or the bar never reached it. The fill IS the
    resting price -- a stop order that is touched fills there -- so a disaster
    stop-out books exactly -DISASTER_R, comfortably inside MAX_LOSS_R. Risk is
    the trade's ORIGINAL entry-to-stop, never a moved runner stop.

    G8.2: every named STOP_ARM removes it. Each arm states its own complete stop
    semantics, and leaving this one underneath would measure two stops at once --
    which is exactly what the shipped book does, and exactly why the close-only
    rule has never actually been measured (research/g82_stop_ab.md)."""
    if STOP_ARM or not DISASTER_STOP:
        return None
    risk = abs(t.entry - t.stop)
    if risk <= 0:
        return None
    px = disaster_stop_price(t.entry, risk, long, DISASTER_R)
    return px if disaster_stop_hit(c.high, c.low, px, long) else None


# P7/G1: the arm-gate funnel, counted in-process. Pure bookkeeping — reading or
# ignoring it changes nothing. research/p7_84_rule.py resets it and prints it.
ARM84_FUNNEL: Counter = Counter()


def _sgrade_84(t: "SimTrade", runner: "BacktestRunner") -> Optional[str]:
    """Austin's S/A/C grade for the ORIGINAL stopped-out trade, or None.

    Same call backtest_2y.py already makes per row — downgrade.score on the day's
    bars at the entry index, with the stop as the level proxy — so the arm gate and
    the report's `sgrade` column are the same number. score() is causal (nothing
    reads past `i`), so grading off runner.candles, a prefix of the session that
    always reaches past the entry bar, is identical to grading off the full day."""
    from research import downgrade as dg
    bars = getattr(runner, "candles", None) or []
    if t.entry_idx >= len(bars):
        return None
    d = [{"o": x.open, "h": x.high, "l": x.low, "c": x.close, "v": x.volume} for x in bars]
    rec = dg.score(d, t.entry_idx, t.stop, t.direction == "call", runner.htf_bias)
    return (rec or {}).get("grade")


def _arm_84(t: "SimTrade", runner: "BacktestRunner", c: Optional[Candle] = None) -> None:
    """Arm one 84%-rule re-entry off a full stop-out (same gate as blind-2R path).

    omen-5.0 T4(c): only a close-based FULL stop-out arms it. A scratch does not
    ("scratch out at close, no 84 percent"), and neither does a stop-out landing
    at or after 11:00 — Austin does not trade past 11, so there is no re-entry to
    take. `c` is the stop-out bar; omitted means the caller has no bar to time.

    P7/G1: the three gates are evaluated instead of short-circuited so each stage
    can be counted. The final condition is unchanged — counted AND arming setup
    AND grade gate AND before 11:00 — so with every flag at its default this arms
    exactly the same stop-outs it always did."""
    from signal_runner import (RULE84_ARM_ON, RULE84_STRICT, RULE84_OFF,
                               RULE84_ARM_SGRADE, RULE84_ARM_NOGATE, SESSION_END, bar_time)
    if RULE84_OFF:  # C9: detector fully disabled
        return
    if t.outcome != "loss":       # scratches never arm the 84% rule
        return
    ARM84_FUNNEL["stopouts"] += 1
    if t.counted:
        ARM84_FUNNEL["stopouts_counted"] += 1
    # Austin 2026-08-09: arm when the stopped trade's setup is in RULE84_ARM_ON
    # (B&R or the one candle rule). FVG / flag losers do NOT arm it.
    setup_ok = SignalType(t.signal_type) in RULE84_ARM_ON
    # The grade gate, in whichever of its four readings is active.
    #   RULE84_ARM_NOGATE (T-84, 2026-08-28): Austin — "84 percent rule can fire
    #     on S A or C, but we only will trade S of course." No grade gate at the
    #     arm point at all; takes priority over the other two readings for the
    #     same reason RULE84_STRICT already ignores RULE84_ARM_SGRADE — one arm
    #     point, not stacked gates.
    #   RULE84_ARM_SGRADE (P7/G1): Austin's ladder — the original must be S.
    #   RULE84_STRICT (C9, shipped): rulebook "you need an A+ entry", read against
    #     the legacy ladder — arm only off an A+/A original.
    #   none of the three: arm off any counted stop-out on an arming setup.
    if RULE84_ARM_NOGATE:
        grade_ok = True
    elif RULE84_ARM_SGRADE:
        grade_ok = _sgrade_84(t, runner) == "S"
    elif RULE84_STRICT:
        grade_ok = t.grade in ("A+", "A")
    else:
        grade_ok = True
    in_session = c is None or bar_time(c.timestamp) < SESSION_END
    if t.counted and setup_ok:
        ARM84_FUNNEL["arming_setup"] += 1
        if grade_ok:
            ARM84_FUNNEL["grade_gate"] += 1
            if in_session:
                ARM84_FUNNEL["armed"] += 1
    if t.counted and setup_ok and grade_ok and in_session:
        runner.session.entry_price = t.entry
        runner.session.entry_direction = t.direction
        runner.session.entry_target = t.target
        runner.session.entry_stop = t.stop


def _entry_scratch(t: "SimTrade", c: Candle) -> Optional[float]:
    """P8/G2. The exit price if `c` scratches this entry, else None.

    `c` is the bar AFTER entry; the caller owns that check. Reads ENTRY_SCRATCH
    at call time (default "" = OFF, so this always returns None as shipped) so a
    test can arm one mode without re-importing the module."""
    if not ENTRY_SCRATCH:
        return None
    lv = t.level_price if ENTRY_SCRATCH == "level" else t.stop
    long = t.direction == "call"
    if (c.close < lv) if long else (c.close > lv):
        # "scratch out at close" — but his stop order still fills at the level,
        # so the scratch is never worse than the stop-out it replaced.
        return max(c.close, t.stop) if long else min(c.close, t.stop)
    return None


def _gave_it_back(t: "SimTrade", c: Candle, long: bool) -> bool:
    """R2 (Austin, 2026-09-03 ruling). Did bar ``c`` close back through the
    ENTRY CANDLE's own range -- below its low for a long, above its high for
    a short? ``False`` whenever the flag is off, so this is a no-op on the
    shipped book. No MFE precondition: "ran and came back" is the rule's
    plain-language framing, not a fitted threshold to encode -- the check
    itself is unconditional on every open bar, same as the stop it sits
    beside."""
    if not GAVE_IT_BACK_EXIT:
        return False
    lv = t.entry_candle_lo if long else t.entry_candle_hi
    hit = (c.close < lv) if long else (c.close > lv)
    if hit:
        GAVE_IT_BACK_FUNNEL["fired"] += 1
        if t.counted:
            GAVE_IT_BACK_FUNNEL["fired_counted"] += 1
    return hit


def _probe_row(t: "SimTrade", c: Candle, nxt: Optional[Candle], level: float) -> dict:
    """P8/G2 measurement, no behaviour. Where the entry bar's close and the next
    bar's close sit relative to the retested level and the stop.

    Offsets are SIGNED so that positive = on the trade's side of the line (a long
    closing above it), and scaled by the ENTRY bar's own range so a $400 stock and
    a $9 stock are on one axis. `d0_*` < 0 is exactly the condition the dead T4(b)
    branch tested; `d1_*` < 0 is the same condition one bar later."""
    rng = c.high - c.low
    sgn = 1.0 if t.direction == "call" else -1.0

    def off(px, line):
        if rng <= 0 or px is None or line is None:
            return None
        return round(sgn * (px - line) / rng, 4)

    return {"sym": t.symbol, "day": t.day, "et": t.entry_time[:5],
            "setup": t.signal_type, "dir": t.direction, "grade": t.grade,
            "traded": bool(t.counted), "rng": round(rng, 4),
            "level_eq_stop": abs(level - t.stop) < 1e-9,
            # fill_price() returned the LEVEL, not the close — the engine's only
            # model of "taken intrabar" (bar_extreme_veto or ON WATCH tripped).
            "intrabar_fill": abs(t.entry - c.close) > 1e-9,
            "d0_stop": off(c.close, t.stop), "d0_level": off(c.close, level),
            "d1_stop": off(nxt.close if nxt else None, t.stop),
            "d1_level": off(nxt.close if nxt else None, level),
            "out": t.outcome, "r": 0.0, "hold": 0}


def _ladder_bar(t: "SimTrade", c: Candle, i: int, open_trades: list,
                runner: "BacktestRunner") -> None:
    """F1 ladder position management for one bar. Conservative: stop wins ties."""
    long = t.direction == "call"
    if not t.scaled:
        # T4(a): the close is the trigger; the fill is still t.stop.
        # omen-5.1 T2: the stop is tested BEFORE the 1R scale rung, so a bar that
        # tags the scale level and closes beyond the stop already books the full
        # loss with no partial credit — pessimistic here without a flag.
        #
        # R11/T11-BE: before the scale rung fires, the working stop is either
        # still the ORIGINAL stop (BE_TRIGGER="pt1", the shipped default) or --
        # under BE_TRIGGER="mfe" -- already raised to entry once a prior bar's
        # favourable excursion cleared BE_MOVE_R. `runner_stop` is the one flag
        # for "the stop has moved", set by either path below.
        stop_lv = t.runner_stop if t.runner_stop else t.stop
        # R1/R2: once the stop has moved to breakeven the resting BE order sits
        # between price and -1R, so the disaster stop cannot be touched first
        # (same reasoning as the scaled branch below).
        dz = _disaster_hit(t, c, long) if stop_lv == t.stop else None
        if dz is not None:
            t.outcome, t.exit_price, t.exit_idx = "loss", dz, i
            open_trades.remove(t)
            _arm_84(t, runner, c)
            return
        if _stop_hit(c, stop_lv, long):
            t.exit_price, t.exit_idx = _stop_fill_px(t, c, long, stop_lv), i
            # A stop-out at the ORIGINAL stop is a real loss by construction
            # (fill is at/beyond it). A stop-out at a BE-raised stop can book a
            # small win, a scratch, or -- past the -1.25R floor's own worse-side
            # -- still a real loss if the bar gapped hard; let the trade's own
            # pnl (entry vs. exit_price) say which, same convention the scaled
            # branch below already uses.
            p_sign = (t.exit_price - t.entry) if long else (t.entry - t.exit_price)
            t.outcome = "loss" if p_sign < 0 else ("win" if p_sign > 0 else "scratch")
            open_trades.remove(t)
            if stop_lv == t.stop:
                # full stop-out at ORIGINAL risk arms 84%; a BE-raised stop that
                # gives back to (near) breakeven already had its risk cut --
                # "stop was wrong" doesn't apply, same call the F1 ladder makes
                # for every scaled trade.
                _arm_84(t, runner, c)
            return
        # R2 (Austin, 2026-09-03 ruling): the gave-it-back exit, checked AFTER
        # the disaster/level stop above (so a bar that satisfies both goes to
        # the STOP) and before the scale rung, so a give-back on this bar
        # cannot be masked by a target that also tagged. No 84% arm -- like
        # ENTRY_SCRATCH, this is a discretionary exit, not a "stop was wrong."
        if _gave_it_back(t, c, long):
            t.exit_price, t.exit_idx = _stop_fill_px(t, c, long, stop_lv), i
            p_sign = (t.exit_price - t.entry) if long else (t.entry - t.exit_price)
            t.outcome = "loss" if p_sign < 0 else ("win" if p_sign > 0 else "scratch")
            open_trades.remove(t)
            return
        if _target_hit(c, t.scale_level, long):
            t.scaled = True
            if SCALE_PLAN == "hod_then_runner_be":
                t.runner_stop = t.entry  # accelerator: BE after first scale
            return
        # R11/T11-BE: "enough movement" arm, independent of the PT1 scale rung.
        # Checked last (after this bar's disaster/stop/scale tests, which all
        # read the PRE-arm stop) so the arm takes effect starting next bar --
        # no look-ahead within the bar that crosses the threshold.
        if BE_TRIGGER == "mfe" and not t.runner_stop and BE_MOVE_R > 0:
            risk = abs(t.entry - t.stop)
            if risk > 0:
                mfe_r = (c.high - t.entry) / risk if long else (t.entry - c.low) / risk
                if mfe_r >= BE_MOVE_R:
                    t.runner_stop = t.entry
        return
    stop_lv = t.runner_stop if t.runner_stop else t.stop
    hit_target = _target_hit(c, t.runner_target, long)
    # R1/R2: the disaster stop survives the scale-out, but only while the
    # runner is still working the ORIGINAL stop. Under SCALE_PLAN
    # "hod_then_runner_be" the first rung raises the stop to break-even, and a
    # resting BE order sits between price and -1R -- price cannot reach the
    # disaster stop without crossing it first. A cap on the trade's total loss,
    # not a trailing rung.
    dz = _disaster_hit(t, c, long) if stop_lv == t.stop else None
    if dz is not None:
        t.exit_price, t.exit_idx = dz, i
    elif _stop_hit(c, stop_lv, long):     # T4(a): close-based on the runner too
        # T11: the fill is this bar's CLOSE, floored at -1.25R of the ORIGINAL
        # risk -- so a runner whose stop had been raised to break-even can still
        # book a real loss, which is the whole point of the floor.
        fill = _stop_fill_px(t, c, long, stop_lv)
        if PESSIMISTIC_FILL and hit_target:
            # omen-5.1 T2 survives on top of it: a bar that tagged the runner
            # target and STILL closed beyond the stop books no BETTER than the
            # trade's ORIGINAL stop, never the breakeven stop mode B moved it
            # to. `t.stop` is -1.000R, comfortably inside the floor, so taking
            # the worse of the two can never breach it.
            fill = min(fill, t.stop) if long else max(fill, t.stop)
        t.exit_price = fill
        t.exit_idx = i
    # R2: same veto, checked after the (disaster/level) stop above so the
    # stop still wins a shared bar, and before the runner target so a
    # give-back on this bar is never masked by a target that also tagged.
    elif _gave_it_back(t, c, long):
        t.exit_price, t.exit_idx = _stop_fill_px(t, c, long, stop_lv), i
    elif hit_target:
        t.exit_price, t.exit_idx = t.runner_target, i
    else:
        return
    p = t.pnl
    t.outcome = "win" if p > 0 else ("loss" if p < 0 else "scratch")
    open_trades.remove(t)


def _ladder_bar_4(t: "SimTrade", c: Candle, i: int, open_trades: list,
                  runner: "BacktestRunner") -> None:
    """THE EXIT LADDER (spec 5.4). Per-bar management for a SCALE_PLAN=
    four_rung trade. A new sibling of `_ladder_bar` above -- that function is
    NOT modified, so every other SCALE_PLAN value is untouched by this one.

    Same two non-negotiables as everywhere else in this file: the stop wins
    any bar that touches both a rung and the stop (no partial credit), and
    every fill routes through `_stop_fill_px` / `_disaster_hit`, never a
    locally invented price."""
    long = t.direction == "call"
    # 1. the working stop -- original until the first rung fills, then
    #    breakeven or the last-filled rung's price per LADDER_TRAIL.
    stop_lv = t.runner_stop if t.runner_stop else t.stop

    def _weight_filled() -> float:
        return sum(w for w, _ in t.fills)

    def _close(exit_price: float, by_sign: bool) -> None:
        t.exit_price, t.exit_idx = exit_price, i
        if by_sign:
            p = t.pnl
            t.outcome = "win" if p > 0 else ("loss" if p < 0 else "scratch")
        open_trades.remove(t)

    # 2. disaster stop -- resting -1R order, on TOUCH, only while the stop is
    #    still the ORIGINAL one (same guard `_ladder_bar` uses: once raised,
    #    a resting order between price and -1R must be crossed first).
    dz = _disaster_hit(t, c, long) if stop_lv == t.stop else None
    if dz is not None:
        had_fills = bool(t.fills)
        remaining = round(1.0 - _weight_filled(), 9)
        if remaining > 1e-9:
            t.fills.append((remaining, dz))
        _close(dz, by_sign=True)
        if not had_fills:
            _arm_84(t, runner, c)
        return

    # 3. which of the still-open rungs did this bar touch -- a PREFIX of the
    #    unfilled rungs, since they are strictly monotonic in the trade's
    #    direction: reaching a farther rung's price means reaching every
    #    nearer one too.
    unfilled = t.rungs[len(t.fills):]
    touched = []
    for r in unfilled:
        if _target_hit(c, r.price, long):
            touched.append(r)
        else:
            break

    # 4. THE STOP WINS THE BAR. A bar that closes beyond the stop books the
    #    remaining weight at the stop's fill -- no rung on THIS bar fills,
    #    even if `touched` is non-empty (omen-5.1 T2's same-bar tie).
    if _stop_hit(c, stop_lv, long):
        fill = _stop_fill_px(t, c, long, stop_lv)
        if PESSIMISTIC_FILL and touched:
            fill = min(fill, t.stop) if long else max(fill, t.stop)
        had_fills = bool(t.fills)
        remaining = round(1.0 - _weight_filled(), 9)
        if remaining > 1e-9:
            t.fills.append((remaining, fill))
        _close(fill, by_sign=True)
        if stop_lv == t.stop and not had_fills:
            _arm_84(t, runner, c)
        return

    # 4.5. R2 (Austin, 2026-09-03 ruling): the gave-it-back exit -- checked
    # after the (disaster/level) stop above, so the stop still wins a shared
    # bar, and before any rung fills below, so a give-back on this bar can
    # never be masked by a rung that also touched. Books the remaining
    # unfilled weight at the close, same as the disaster stop and the level
    # stop above. No 84% arm -- a discretionary exit, not a "stop was wrong."
    if _gave_it_back(t, c, long):
        fill = _stop_fill_px(t, c, long, stop_lv)
        remaining = round(1.0 - _weight_filled(), 9)
        if remaining > 1e-9:
            t.fills.append((remaining, fill))
        _close(fill, by_sign=True)
        return

    # 5. fill every touched rung, in order, each at its own price; the stop
    #    trails after the FIRST fill of the trade's life, per LADDER_TRAIL.
    if touched:
        for r in touched:
            t.fills.append((r.weight, r.price))
        t.runner_stop = t.entry if LADDER_TRAIL == "be" else touched[-1].price

    # 6. every rung filled -> the trade is done.
    if len(t.fills) == len(t.rungs):
        _close(t.fills[-1][1], by_sign=True)
        return

    # 7. R11/T11-BE's "enough movement" arm, independent of any rung -- same
    #    as `_ladder_bar`'s own copy, checked last so it takes effect
    #    starting next bar (no look-ahead within the bar that crosses it).
    if BE_TRIGGER == "mfe" and not t.runner_stop and BE_MOVE_R > 0:
        risk = abs(t.entry - t.stop)
        if risk > 0:
            mfe_r = (c.high - t.entry) / risk if long else (t.entry - c.low) / risk
            if mfe_r >= BE_MOVE_R:
                t.runner_stop = t.entry
    # else: still open, unfilled weight carries to the next bar (or the EOD
    # flush in simulate_day, which appends it at the session's last close).


class BacktestRunner(SignalRunner):
    """Capture ALL signals including D-grade and tight-stop skips."""

    def __init__(self, symbol: str):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.captured: List[dict] = []

    def _route(self, signals: List[dict], sig: dict) -> None:
        """Capture ALL signals, but let the BASE decide which of them fire.

        omen-5.0 (2026-08-12): this used to reimplement routing -- grade, D-skip,
        tight-stop skip -- and never called super(). Every gate the base grew
        after it was written was therefore INERT in every backtest ever run:
        austin_tier (omen-3.9 T4), ENFORCE_NO_REPEAT / NO_REPEAT_ENTRIES
        (omen-3.9 T5, omen-4.0 T6), and all of omen-5.0 T11 -- the mesh S-veto,
        level retirement, S_GATE and RULE_710. The subclass exists to CAPTURE
        what the base rejects, not to route differently, so it now delegates and
        labels the outcome afterwards."""
        before = len(signals)
        super()._route(signals, sig)
        if len(signals) > before:
            sig["status"] = "fired"
        elif sig["grade"] == TradeGrade.D.value:
            sig["status"] = "skipped_d"
        elif sig.get("level_retired"):
            sig["status"] = "skipped_level_retired"
        elif "[skip: repeat entry]" in sig.get("reason", ""):
            sig["status"] = "skipped_repeat_entry"
        elif "[skip: repeat idea]" in sig.get("reason", ""):
            sig["status"] = "skipped_repeat_idea"
        else:
            sig["status"] = "skipped_tight_stop"
        self.captured.append(sig)


# ---- data ----

def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_week(symbol: str, days: int = 8) -> dict:
    """Return {date_iso: [Candle...]} of RTH 1-min candles, plus hourly closes.

    yfinance caps 1m data at 8 days/request and ~30 days of history, so longer
    ranges are fetched in 7-day chunks and concatenated.
    """
    if days <= 8:
        m1 = _flatten(yf.download(symbol, period=f"{days}d", interval="1m",
                                  prepost=True, progress=False, auto_adjust=False))
    else:
        chunks = []
        end = date.today() + timedelta(days=1)
        start = date.today() - timedelta(days=min(days, 29))
        cur = start
        while cur < end:
            nxt = min(cur + timedelta(days=7), end)
            try:
                df = _flatten(yf.download(symbol, start=cur.isoformat(), end=nxt.isoformat(),
                                          interval="1m", prepost=True, progress=False,
                                          auto_adjust=False))
                if len(df):
                    chunks.append(df)
            except Exception as e:
                print(f"  [{symbol}] chunk {cur} failed: {e}")
            cur = nxt
        m1 = pd.concat(chunks) if chunks else pd.DataFrame()
    h1 = _flatten(yf.download(symbol, period="3mo", interval="1h",
                              prepost=False, progress=False, auto_adjust=False))
    days = defaultdict(list)
    premkt = {}  # day -> [pm_high, pm_low] from 04:00-09:29 extended-hours bars
    rth_open = datetime.strptime("09:30", "%H:%M").time()
    rth_close = datetime.strptime("16:00", "%H:%M").time()
    for ts, row in m1.iterrows():
        if pd.isna(row["Open"]):
            continue
        t, d = ts.time(), ts.date().isoformat()
        if t < rth_open:
            hi, lo = float(row["High"]), float(row["Low"])
            if d in premkt:
                premkt[d][0] = max(premkt[d][0], hi)
                premkt[d][1] = min(premkt[d][1], lo)
            else:
                premkt[d] = [hi, lo]
            continue
        if t >= rth_close:
            continue
        days[d].append(Candle(
            timestamp=ts.strftime("%H:%M:%S"),
            open=float(row["Open"]), high=float(row["High"]),
            low=float(row["Low"]), close=float(row["Close"]),
            volume=int(row["Volume"] or 0),
        ))
    hourly = [(ts, float(row["Close"])) for ts, row in h1.iterrows() if not pd.isna(row["Close"])]
    return {"days": dict(days), "hourly": hourly,
            "premkt": {d: tuple(v) for d, v in premkt.items()}}


def htf_bias_for(hourly, day_iso: str) -> Optional[str]:
    """Close vs SMA20 of hourly closes before the session open (mirrors fetch_htf_bias)."""
    closes = [c for ts, c in hourly if ts.date().isoformat() < day_iso]
    if len(closes) < 20:
        return None
    sma20 = sum(closes[-20:]) / 20
    last = closes[-1]
    if last > sma20 * 1.001:
        return "bullish"
    if last < sma20 * 0.999:
        return "bearish"
    return "neutral"


# ---- simulation ----

ENTRY_CUTOFF = "11:00:00"  # Scarface trades 9:30-11 only (volume/volatility); None = all day


def simulate_day(symbol: str, day_iso: str, candles: List[Candle],
                 pdh: Optional[float], pdl: Optional[float], bias: Optional[str],
                 pmh: Optional[float] = None, pml: Optional[float] = None,
                 pdo: Optional[float] = None, pdc: Optional[float] = None,
                 qqq: Optional[dict] = None,
                 min_risk_dollars: Optional[float] = None) -> List[SimTrade]:
    runner = BacktestRunner(symbol)
    runner.pdh, runner.pdl, runner.htf_bias = pdh, pdl, bias
    runner.pmh, runner.pml = pmh, pml
    runner.pd_open, runner.pd_close = pdo, pdc  # [pdwick] tag inputs
    runner.qqq_breaks = qqq  # F4 [qqqA]/[qqqX] tag input
    # T4/R7: symbol's own prior-20-session range x MIN_RISK_ATR_MULT, in
    # dollars. None (the default) leaves min_risk_floor() reading its
    # 0.0015 x close fallback -- see signal_runner.ENABLE_ATR_SCALED_MIN_RISK.
    runner.min_risk_dollars = min_risk_dollars

    trades: List[SimTrade] = []
    open_trades: List[SimTrade] = []
    probe: List[tuple] = []   # P8/G2, only under SCRATCH_PROBE=1
    seen = {}  # dedupe key -> last bar index it appeared
    misses = ENTRY_FILL_MISSES

    for i in range(5, len(candles)):
        c = candles[i]

        # 1. update open sim positions against this bar
        for t in list(open_trades):
            # A position cannot be managed before it is filled. NO-OP on the
            # shipped fill (`entry_idx` is the signal bar and the trade is only
            # appended after this loop has run for that bar, so the first
            # managed bar is always entry_idx + 1). It matters only under the
            # forward ENTRY_FILL modes, where the fill lands one or two bars
            # after the signal and those bars must not be allowed to stop out a
            # trade that does not exist yet.
            if i <= t.entry_idx:
                continue
            # P8/G2 ENTRY_SCRATCH, default OFF. Austin's failed-entry scratch on
            # the FIRST bar after entry — the earliest bar on which "taken
            # intrabar, then closes back beyond the level" can be true on a
            # close-driven engine. Tested ahead of the stop so the scratch wins
            # the bar, exits at that close but never worse than the trade's own
            # stop, and never reaches _arm_84 ("no 84 percent").
            if i == t.entry_idx + 1:
                px = _entry_scratch(t, c)
                if px is not None:
                    t.outcome, t.exit_price, t.exit_idx = "scratch", px, i
                    open_trades.remove(t)
                    continue
            if SCALE_PLAN == "four_rung":
                _ladder_bar_4(t, c, i, open_trades, runner)
                continue
            if SCALE_PLAN:
                _ladder_bar(t, c, i, open_trades, runner)
                continue
            # Rule 6: check breakeven scale BEFORE stop/target
            if RULE6_ENABLED and not t.be_taken and t.be_level > 0:
                if (t.direction == "call" and c.high >= t.be_level) or                    (t.direction == "put" and c.low <= t.be_level):
                    t.be_taken = True
                    t.runner_stop = t.entry  # raise stop to breakeven
                    # BE scale recorded; runner continues below
            # Check stop (using runner_stop if BE taken). T4(a): a wick through
            # the level is not a stop-out — the CANDLE HAS TO CLOSE beyond it.
            # The target is unchanged: a target order fills intrabar.
            lv = t.runner_stop if t.be_taken else t.stop
            # R1/R2: the resting -1R disaster stop, on TOUCH, tested first.
            # Only while the stop is still the original one: once it has been
            # raised to break-even the trade cannot lose 1R, and price has to
            # cross the BE order on its way down to -1R anyway.
            dz = None if t.be_taken else _disaster_hit(t, c, t.direction == "call")
            stopped = _stop_hit(c, lv, t.direction == "call")
            targeted = _target_hit(c, t.target, t.direction == "call")
            if dz is not None:
                t.outcome, t.exit_price, t.exit_idx = "loss", dz, i
                open_trades.remove(t)
                _arm_84(t, runner, c)
                continue
            if stopped:  # both in one bar -> conservative: loss
                # T11: fill at the triggering close, floored at -1.25R.
                t.outcome, t.exit_price, t.exit_idx = (
                    "loss", _stop_fill_px(t, c, t.direction == "call", lv), i)
                open_trades.remove(t)
                # Lesson 6 canonical: arm only off solid B&R stop-outs (Scarface:
                # "can't be a one-minute order block with nothing else"). Shared
                # with the ladder path via _arm_84 so C9's RULE84_STRICT/RULE84_OFF
                # gate applies here too (binary-2R path = default config).
                _arm_84(t, runner, c)
            # R2 (Austin, 2026-09-03 ruling): the gave-it-back exit, checked
            # after the disaster/level stop above (stop wins a shared bar)
            # and before the target, so a give-back is never masked by a
            # target that also tagged this bar. No 84% arm (ENTRY_SCRATCH's
            # same convention): a discretionary exit, not "stop was wrong."
            elif _gave_it_back(t, c, t.direction == "call"):
                t.exit_price, t.exit_idx = _stop_fill_px(t, c, t.direction == "call", lv), i
                p_sign = ((t.exit_price - t.entry) if t.direction == "call"
                          else (t.entry - t.exit_price))
                t.outcome = "loss" if p_sign < 0 else ("win" if p_sign > 0 else "scratch")
                open_trades.remove(t)
            elif targeted:
                t.outcome, t.exit_price, t.exit_idx = "win", t.target, i
                open_trades.remove(t)

        # 2. detect signals as of this bar. R13 (Austin, probe_master_2026-08-29,
        # fact_session_end -> `manage`): 11:00 stops new ENTRIES, runners keep
        # running. That is already what this `continue` does and has always
        # done -- step 1 above marks every open position on every bar of the
        # session and only step 2 is skipped -- so no backtest figure moves with
        # R13. The live path is where the runner really was being cut by the
        # clock (live_scanner.MANAGE_END).
        if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
            continue
        runner.candles = candles[:i + 1]
        before = len(runner.captured)
        runner.detect_signals()

        for sig in runner.captured[before:]:
            # Dedupe by trade IDEA. For B&R that's the broken level (name is
            # unique per day) — keying on stop price breaks under F2 variable
            # stops (retest/buffer stops shift by the bar -> 760 tr became 1811).
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            # G7.2: a REJECT neither opens nor extends the window. See
            # DEDUPE_FIRES_ONLY at the top of this file.
            claims = sig.get("status") == "fired" or not DEDUPE_FIRES_ONLY
            if key in seen and i - seen[key] < dedupe_window():   # R16
                if claims:
                    seen[key] = i  # still firing: extend suppression
                continue
            if claims:
                seen[key] = i
            # ---- ONE ENTRY FILL (entry_fill.py). See the import block. ----
            # On the shipped default (`close`) and on `published` there is
            # nothing to do here: `sig["entry"]` IS `entry_fill`'s answer
            # already, computed inside `signal_runner.fill_price` on the signal
            # bar. The three forward modes are statements about bars the engine
            # is structurally forbidden to see, so they are priced here, once,
            # through the same function -- same setups, same stops, same exits,
            # only the way IN changes (research/g80_ordertype_grid.md).
            #
            # A no-fill is a NO TRADE and it is COUNTED, not skipped: a resting
            # limit that never traded is a day he did not get into, and pretending
            # those days away is how a limit arm gets to look like a free option.
            fill_i, fill_c = i, c
            if entry_fill.needs_future_bars():
                long_ = sig["direction"] == "call"
                fill = entry_fill.entry_fill_price(
                    sig.get("level_price", sig["stop"]) or sig["stop"], c, long_,
                    future_bars=candles[i + 1:])
                if not fill.filled:
                    misses.append({"sym": symbol, "day": day_iso,
                                   "et": c.timestamp[:5], "mode": ENTRY_FILL,
                                   "setup": sig["signal_type"].value,
                                   "reason": fill.reason})
                    continue
                sig["entry"] = fill.price
                fill_i = i + fill.bar_offset
                fill_c = candles[fill_i]
                # The fill landed at or through the stop: there is no trade left
                # in it (a limit resting ON a break-and-retest's level IS the
                # stop). Counted as a miss rather than booked at zero risk.
                if (sig["entry"] <= sig["stop"]) if long_ else (sig["entry"] >= sig["stop"]):
                    misses.append({"sym": symbol, "day": day_iso,
                                   "et": c.timestamp[:5], "mode": ENTRY_FILL,
                                   "setup": sig["signal_type"].value,
                                   "reason": "filled at %.2f, at or through the "
                                             "stop %.2f — no risk left in it"
                                             % (sig["entry"], sig["stop"])})
                    continue
            risk = abs(sig["entry"] - sig["stop"])
            # 84% signals carry the ORIGINAL trade's target; everything else 2R
            target = sig.get("target") or (
                sig["entry"] + 2 * risk if sig["direction"] == "call" else sig["entry"] - 2 * risk)
            # Rule 6: breakeven scaling level at entry +- 1R
            if RULE6_ENABLED and risk > 0:
                if sig["direction"] == "call":
                    be_level = sig["entry"] + RULE6_BE_MULT * risk
                else:
                    be_level = sig["entry"] - RULE6_BE_MULT * risk
            else:
                be_level = 0.0
            # F1 ladder: scale trigger = session extreme as-of entry bar (no
            # lookahead); runner target = first key level beyond the scale point
            scale_level = runner_tgt = 0.0
            rungs: tuple = ()
            if SCALE_PLAN == "four_rung" and risk > 0:
                # THE EXIT LADDER (spec 1/2): every rung is a price, causal at
                # the entry bar, built by the one pure function in
                # levels_ladder.py. `bias`/`qqq` are simulate_day's own params
                # -- already causal, already threaded through for exactly this.
                session_extreme = (max(cd.high for cd in candles[:i + 1])
                                   if sig["direction"] == "call"
                                   else min(cd.low for cd in candles[:i + 1]))
                named_levels = _named_level_pool(candles, i, pdh, pdl, pmh, pml)
                rungs = tuple(ladder.build_rungs(
                    sig["entry"], sig["stop"], sig["direction"],
                    session_extreme=session_extreme, named_levels=named_levels,
                    weights=_ladder_weights(sig["direction"], bias, qqq, fill_c.timestamp),
                    psych_step=LADDER_PSYCH_STEP, psych_tol=LADDER_PSYCH_TOL,
                    pt4_mode=LADDER_PT4_MODE, pt4_r=LADDER_PT4_R,
                    min_gap_r=LADDER_MIN_RUNG_GAP))
            elif SCALE_PLAN and risk > 0:
                if sig["direction"] == "call":
                    scale_level = max(cd.high for cd in candles[:i + 1])
                    cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]
                    cands.append(math.floor(scale_level) + 1.0)  # next psych whole $
                    runner_tgt = min(cands)
                else:
                    scale_level = min(cd.low for cd in candles[:i + 1])
                    cands = [x for x in (pdl, pml) if x is not None and x < scale_level]
                    cands.append(math.ceil(scale_level) - 1.0)
                    runner_tgt = max(cands)
                # THE RUNNER GUARD (spec section 3, LADDER_RUNNER_GUARD, default
                # OFF). `runner_tgt` above and `target` (2R, a few lines up) are
                # computed independently and NEVER compared -- measured on
                # 444 first-of-day trades, `runner_tgt` lands inside the 2R
                # target on 303 (68.2%), median 1.30R. A near runner is only
                # legitimate when the precedence rule (section 2's tolerance,
                # reused here) put it there deliberately; otherwise it is the
                # whole-dollar fallback geometry bug and 2R wins.
                if LADDER_RUNNER_GUARD:
                    floor_px = target  # entry +/- 2*risk, computed above
                    tol_r = _psych_tol_r(risk, sig["entry"])
                    cur_r = ((runner_tgt - sig["entry"]) / risk if sig["direction"] == "call"
                            else (sig["entry"] - runner_tgt) / risk)
                    if cur_r < 2.0 - tol_r:
                        runner_tgt = floor_px

            # G7.1/labels: setup_type is a SignalType enum when
            # _label_confluence ran (every live/backtest sig does); absent on a
            # hand-built sig from an older research replay -- fall back to the
            # base signal_type rather than an empty string.
            _setup_type = sig.get("setup_type", sig["signal_type"])
            t = SimTrade(symbol=symbol, day=day_iso,
                         signal_type=sig["signal_type"].value,
                         direction=sig["direction"], grade=sig["grade"],
                         status=sig["status"], entry_time=fill_c.timestamp,
                         entry=sig["entry"], stop=sig["stop"], target=target,
                         reason=sig["reason"], entry_idx=fill_i,
                         exit_idx=len(candles) - 1,
                         be_level=be_level, scale_level=scale_level,
                         runner_target=runner_tgt, rungs=rungs,
                         setup_type=getattr(_setup_type, "value", _setup_type),
                         stop_level_name=sig.get("stop_level_name") or "",
                         entry_candle_lo=fill_c.low, entry_candle_hi=fill_c.high)
            trades.append(t)
            if risk > 0:
                # T4(b) was HERE and tested this bar's own close against
                # sig["stop"]. It could not fire: the detector already required
                # this bar to close through the retested level, and the stop sits
                # at or beyond that level on the losing side. See ENTRY_SCRATCH
                # above and research/p8_scratch.md — the test that replaced it
                # lives in the open-position loop, one bar later.
                t.level_price = sig.get("level_price")
                if t.level_price is None:
                    t.level_price = sig["stop"]
                if SCRATCH_PROBE_ON:
                    nxt = candles[i + 1] if i + 1 < len(candles) else None
                    probe.append((_probe_row(t, c, nxt, t.level_price), t))
                open_trades.append(t)

    # EOD: whatever is open scratches at last close. THE EXIT LADDER (spec
    # 5.4 step 8): a four_rung trade still holding unfilled weight books that
    # remainder at the session's last close FIRST, so its `pnl` (weighted
    # across every fill) is correct -- still labeled "scratch", same as every
    # other EOD flush here, never win/loss by construction.
    for t in open_trades:
        if t.rungs:
            remaining = round(1.0 - sum(w for w, _ in t.fills), 9)
            if remaining > 1e-9:
                t.fills.append((remaining, candles[-1].close))
        t.outcome, t.exit_price = "scratch", candles[-1].close
    for row, t in probe:   # P8/G2: outcomes are only known once the day is done
        row["out"] = t.outcome
        row["r"] = round(t.pnl / RISK_DOLLARS, 3)
        row["hold"] = max(0, t.exit_idx - t.entry_idx)
        SCRATCH_PROBE.append(row)
    return trades


# ---- report ----

def _stats(trades: List[SimTrade]) -> tuple:
    """(n, wins, losses, scratches, win_rate_pct, pnl)"""
    n = len(trades)
    wins = sum(1 for t in trades if t.outcome == "win")
    losses = sum(1 for t in trades if t.outcome == "loss")
    scr = n - wins - losses
    decided = wins + losses
    wr = round(wins / decided * 100, 1) if decided else 0.0
    pnl = round(sum(t.pnl for t in trades), 2)
    return n, wins, losses, scr, wr, pnl


def write_report(all_trades: List[SimTrade], days: List[str], notes: List[str]) -> str:
    fired = [t for t in all_trades if t.counted]
    alerts = [t for t in all_trades if t.is_alert]
    d_skips = [t for t in all_trades if t.status == "skipped_d"]
    tight = [t for t in all_trades if t.status == "skipped_tight_stop"]

    lines = [f"# Backtest Report: Week of {days[0]} to {days[-1]}" if days
             else "# Backtest Report", ""]
    lines += ["## Assumptions",
              "- Data: yfinance 1-min RTH bars; walk-forward replay through SignalRunner.detect_signals",
              f"- $1000 risk per trade, 2R target -> win +$2000, loss -$1000, scratch = R x $1000 at EOD close",
              "- Stop+target same bar counted as loss (conservative)",
              f"- Repeat fires of same setup deduped by {DEDUPE_MODE} ({dedupe_window()} bars)",
              ""]

    n, w, l, s, wr, pnl = _stats(fired)
    lines += ["## Summary",
              f"- Traded signals (A+/A/B, viable stop): **{n}** | {w}W {l}L {s} scratch | win rate {wr}% (of decided)",
              f"- Simulated P&L (traded all A+/A/B): **{'+' if pnl >= 0 else ''}${pnl}**",
              f"- C-grade alerts (alert-only per SPEC2): {len(alerts)} | D filtered: {len(d_skips)} | tight-stop skips: {len(tight)}",
              ""]

    lines += ["### By Grade", "| Grade | Signals | W | L | Scratch | Win rate | P&L |",
              "|-------|---------|---|---|---------|----------|-----|"]
    for g in ["A+", "A", "B"]:
        gt = [t for t in fired if t.grade == g]
        if gt:
            n, w, l, s, wr, pnl = _stats(gt)
            lines.append(f"| {g} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
    if alerts:
        n, w, l, s, wr, pnl = _stats(alerts)
        lines.append(f"| C (alert only) | {n} | {w} | {l} | {s} | {wr}% | (${pnl} if traded) |")
    if d_skips:
        n, w, l, s, wr, pnl = _stats(d_skips)
        lines.append(f"| D (filtered) | {n} | {w} | {l} | {s} | {wr}% | (${pnl} if traded) |")
    lines.append("")

    lines += ["### By Setup", "| Setup | Signals | W | L | Scratch | Win rate | P&L |",
              "|-------|---------|---|---|---------|----------|-----|"]
    for st in sorted({t.signal_type for t in fired}):
        stt = [t for t in fired if t.signal_type == st]
        n, w, l, s, wr, pnl = _stats(stt)
        lines.append(f"| {st} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
    lines.append("")

    lines += ["### By Symbol", "| Symbol | Signals | W | L | Scratch | Win rate | P&L |",
              "|--------|---------|---|---|---------|----------|-----|"]
    for sym in sorted({t.symbol for t in fired}):
        st_ = [t for t in fired if t.symbol == sym]
        n, w, l, s, wr, pnl = _stats(st_)
        tag = " _(low n)_" if n < MIN_SAMPLE_N else ""
        lines.append(f"| {sym}{tag} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
    lines.append(f"_(low n): under {MIN_SAMPLE_N} trades -- too few for this row to mean much "
                 "(research/p12_sample_floor.md). Still counted in every total above._")
    lines.append("")

    # Per entry-hour (2026-07-11): YouTube stat says 75% of Scarface trades
    # cluster ~10:00 AM — test our own hour-by-hour win rate. Entry cutoff is
    # 11:00, so every fired trade falls in one of these three 30-min buckets.
    def _hour_bucket(ts: str) -> Optional[str]:
        hhmm = ts[:5]  # "HH:MM"
        if "09:30" <= hhmm < "10:00":
            return "09:30-10:00"
        if "10:00" <= hhmm < "10:30":
            return "10:00-10:30"
        if "10:30" <= hhmm < "11:00":
            return "10:30-11:00"
        return None
    lines += ["### By Entry Hour", "| Hour | Signals | W | L | Scratch | Win rate | P&L |",
              "|------|---------|---|---|---------|----------|-----|"]
    for bucket in ["09:30-10:00", "10:00-10:30", "10:30-11:00"]:
        bt = [t for t in fired if _hour_bucket(t.entry_time) == bucket]
        if bt:
            n, w, l, s, wr, pnl = _stats(bt)
            lines.append(f"| {bucket} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
    lines.append("")

    # Austin 2026-07-10: clean first-break vs late/dirty-level B&R A/B
    br = [t for t in fired if t.signal_type == "break_and_retest"]
    clean = [t for t in br if "[clean]" in t.reason]
    late = [t for t in br if "[late]" in t.reason]
    if clean or late:
        lines += ["### B&R: clean first break vs late (level broken earlier)",
                  "| Bucket | Signals | W | L | Scratch | Win rate | P&L |",
                  "|--------|---------|---|---|---------|----------|-----|"]
        for name, ts in (("clean", clean), ("late", late)):
            if ts:
                n, w, l, s, wr, pnl = _stats(ts)
                lines.append(f"| {name} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
        lines.append("")

    # Rule 6: Breakeven Scale Analysis (when RULE6_ENABLED, show BE-scale stats)
    scaled = [t for t in fired if t.be_taken]
    if scaled:
        be_hit = len(scaled)
        be_then_win = sum(1 for t in scaled if t.outcome == "win")
        be_then_loss = sum(1 for t in scaled if t.outcome == "loss")
        be_then_scr = sum(1 for t in scaled if t.outcome == "scratch")
        be_pnl = sum(t.pnl for t in scaled)
        no_be = [t for t in fired if not t.be_taken]
        no_be_decided = [t for t in no_be if t.outcome in ("win", "loss")]
        no_be_wr = round(sum(1 for t in no_be if t.outcome == "win") / max(len(no_be_decided), 1) * 100, 1)
        be_decided = [t for t in scaled if t.outcome in ("win", "loss")]
        be_wr = round(be_then_win / max(be_then_win + be_then_loss, 1) * 100, 1)
        lines += ["### Rule 6: Breakeven Scale Analysis",
                  f"| Metric | Value |",
                  f"|--------|-------|",
                  f"| Trades that hit BE scale | {be_hit}/{len(fired)} ({round(be_hit/max(len(fired),1)*100)}%) |",
                  f"| BE scaled -> win | {be_then_win} |",
                  f"| BE scaled -> loss (stopped at breakeven) | {be_then_loss} |",
                  f"| BE scaled -> scratch | {be_then_scr} |",
                  f"| P&L from BE-scaled trades | ${be_pnl} |",
                  f"| Win rate (BE scaled) | {be_wr}% |",
                  f"| Win rate (no BE scale) | {no_be_wr}% |",
                  f"| Scaling improved returns | {'YES' if be_wr >= no_be_wr else 'NO'} |",
                  ""]

    lines += ["## By Day", "| Day | Signals | Wins | Losses | Scratch | P&L |",
              "|-----|---------|------|--------|---------|-----|"]
    for d in days:
        dt = [t for t in fired if t.day == d]
        n, w, l, s, wr, pnl = _stats(dt)
        lines.append(f"| {d} | {n} | {w} | {l} | {s} | ${pnl} |")
    lines.append("")

    r84 = [t for t in all_trades if t.signal_type == "reentry_84_rule"]
    n, w, l, s, wr, pnl = _stats([t for t in r84 if t.counted])
    lines += ["## 84% Rule Analysis",
              f"- Total triggers (incl. filtered): {len(r84)}",
              f"- Fired re-entry signals: {n}",
              f"- Win rate on re-entry: {wr}% | P&L ${pnl}",
              ""]

    lines += ["## Signal Log", "| Day | Time | Sym | Setup | Dir | Grade | Status | Entry | Stop | Outcome | P&L |",
              "|-----|------|-----|-------|-----|-------|--------|-------|------|---------|-----|"]
    for t in sorted(all_trades, key=lambda t: (t.day, t.entry_time)):
        lines.append(f"| {t.day} | {t.entry_time} | {t.symbol} | {t.signal_type} | {t.direction} "
                     f"| {t.grade} | {t.status} | {t.entry:.2f} | {t.stop:.2f} | {t.outcome} "
                     f"| {'$' + format(t.pnl, '.0f') if t.counted else '-'} |")
    lines.append("")

    lines += ["## Findings & Recommendations"] + [f"- {n_}" for n_ in notes] + [""]
    text = "\n".join(lines)
    REPORT_PATH.write_text(text, encoding="utf-8")
    return text


def build_notes(all_trades: List[SimTrade]) -> List[str]:
    notes = []
    fired = [t for t in all_trades if t.counted]

    def wr(ts):
        d = [t for t in ts if t.outcome in ("win", "loss")]
        return (sum(1 for t in d if t.outcome == "win") / len(d) * 100) if d else None

    top = wr([t for t in fired if t.grade in ("A+", "A")])
    low = wr([t for t in fired if t.grade in ("B", "C")])
    if top is not None and low is not None:
        verdict = "KEEP grading" if top >= low else "grading NOT predictive this week - review PA grade criteria"
        notes.append(f"A+/A win rate {top:.0f}% vs B/C {low:.0f}% -> {verdict}")

    d_wr = wr([t for t in all_trades if t.status == "skipped_d"])
    if d_wr is not None:
        notes.append(f"D-grade filter: filtered signals would have won {d_wr:.0f}% -> "
                     + ("filter justified (<50%)" if d_wr < 50 else "filter may be cutting winners, re-examine"))

    r84 = [t for t in all_trades if t.signal_type == "reentry_84_rule"]
    if r84:
        r = wr([t for t in r84 if t.counted])
        rtxt = f"{r:.0f}%" if r is not None else "n/a"
        notes.append(f"84% rule (Lesson 6 canonical 2026-07-06: solid B&R stop-out arms one "
                     f"re-entry on the reclaim close, ORIGINAL stop + target): "
                     f"{len(r84)} triggers, fired win rate {rtxt}.")
    notes.append("84% live wiring: armed per-symbol off paper stop-outs in live_scanner "
                 "(2026-07-05). Requires --paper mode; signal-only runs have no stop-out feedback.")

    by_setup = defaultdict(list)
    for t in fired:
        by_setup[t.signal_type].append(t)
    ranked = [(st, wr(ts)) for st, ts in by_setup.items() if wr(ts) is not None]
    if ranked:
        ranked.sort(key=lambda x: x[1], reverse=True)
        notes.append(f"Best setup: {ranked[0][0]} ({ranked[0][1]:.0f}%) | worst: {ranked[-1][0]} ({ranked[-1][1]:.0f}%)")

    alerts = [t for t in all_trades if t.is_alert]
    a_wr = wr(alerts)
    if a_wr is not None:
        notes.append(f"C-grade alerts ({len(alerts)}, alert-only per SPEC2) would have won {a_wr:.0f}% - "
                     + ("similar to traded grades; alert-only demotion costs little." if a_wr < 45
                        else "outperforming; consider trading C at reduced size."))

    scr = sum(1 for t in fired if t.outcome == "scratch")
    if fired and scr / len(fired) > 0.4:
        notes.append(f"{scr}/{len(fired)} trades never resolved by EOD - 2R target may be too far for 1-min setups; test 1.5R")
    return notes


def _load_news_days() -> set:
    """Load news_days.json -> set of date strings (empty on missing/error)."""
    import json
    try:
        nd = json.loads((Path(__file__).parent / "news_days.json").read_text())
        return set(nd.get("news_days", []))
    except (OSError, ValueError):
        return set()


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Backtest OMEN signals over the last trading week.")
    ap.add_argument("dates", nargs="*",
                    help="explicit dates YYYY-MM-DD (default: last week)")
    ap.add_argument("--days", type=int, default=None,
                    help="lookback days (e.g. --days 30; max 29)")
    ap.add_argument("--entry-cutoff", default=None, metavar="HH:MM",
                    help="override entry cutoff time (default 11:00)")
    ap.add_argument("--skip-news", action="store_true",
                    help="exclude dates listed in news_days.json")
    args = ap.parse_args()

    # Override ENTRY_CUTOFF before the day loop (module-level global read by
    # simulate_day). Spec: module-level assignment before the loop is fine.
    global ENTRY_CUTOFF
    if args.entry_cutoff:
        ENTRY_CUTOFF = f"{args.entry_cutoff}:00"

    news_days = _load_news_days() if args.skip_news else set()

    fetch_days = 8
    if args.days is not None:
        fetch_days = min(args.days, 29)
        target_days = None
        week_start = (date.today() - timedelta(days=fetch_days)).isoformat()
        week_end = (date.today() - timedelta(days=1)).isoformat()
    elif args.dates:
        target_days = args.dates
        week_start = week_end = None  # explicit dates only
    else:
        target_days = None  # last complete trading week (Mon..Fri of most recent Friday)
        today = date.today()
        last_friday = today - timedelta(days=(today.weekday() - 4) % 7 or 7)
        week_start = (last_friday - timedelta(days=4)).isoformat()
        week_end = last_friday.isoformat()

    all_trades: List[SimTrade] = []
    chart_records: List[dict] = []
    seen_days = set()

    for sym in SYMBOLS:
        try:
            data = fetch_week(sym, days=fetch_days)
        except Exception as e:
            print(f"[{sym}] fetch failed: {e}")
            continue
        day_keys = sorted(data["days"].keys())
        use = [d for d in day_keys
               if (target_days is None and week_start <= d <= week_end)
               or (target_days and d in target_days)]
        if news_days:
            use = [d for d in use if d not in news_days]
        prev_day = None
        for d in day_keys:  # iterate all so prev_day PDH/PDL is right
            candles = data["days"][d]
            if d in use and len(candles) >= 30:
                if prev_day:
                    pc = data["days"][prev_day]
                    pdh, pdl = max(c.high for c in pc), min(c.low for c in pc)
                    pdo, pdc = pc[0].open, pc[-1].close
                else:
                    pdh = pdl = pdo = pdc = None
                bias = htf_bias_for(data["hourly"], d)
                pmh, pml = data.get("premkt", {}).get(d, (None, None))
                trades = simulate_day(sym, d, candles, pdh, pdl, bias, pmh, pml, pdo, pdc)
                all_trades.extend(trades)
                orh = max(c.high for c in candles[:5])
                orl = min(c.low for c in candles[:5])
                levels = {k: v for k, v in [("PDH", pdh), ("PDL", pdl), ("PMH", pmh),
                                            ("PML", pml), ("ORH", orh), ("ORL", orl)]
                          if v is not None}
                for t in trades:
                    if t.counted or t.is_alert:
                        lo, hi = max(0, t.entry_idx - 25), min(len(candles), t.exit_idx + 11)
                        chart_records.append({
                            "symbol": t.symbol, "day": t.day, "setup": t.signal_type,
                            "direction": t.direction, "grade": t.grade,
                            "alert_only": t.is_alert, "outcome": t.outcome,
                            "entry": t.entry, "stop": t.stop, "target": t.target,
                            "exit_price": t.exit_price, "pnl": t.pnl,
                            "entry_i": t.entry_idx - lo, "exit_i": t.exit_idx - lo,
                            "reason": t.reason, "levels": levels,
                            "candles": [{"t": c.timestamp[:5], "o": c.open, "h": c.high,
                                         "l": c.low, "c": c.close} for c in candles[lo:hi]],
                        })
                seen_days.add(d)
                print(f"[{sym}] {d}: {len(candles)} bars, {len(trades)} signals "
                      f"({sum(1 for t in trades if t.counted)} fired)")
            prev_day = d

    days = sorted(seen_days)
    notes = build_notes(all_trades)
    write_report(all_trades, days, notes)
    import json
    charts_path = REPORT_PATH.with_name("backtest_charts.json")
    charts_path.write_text(json.dumps(chart_records), encoding="utf-8")
    print(f"Charts data -> {charts_path} ({len(chart_records)} trades)")
    print(f"\nReport -> {REPORT_PATH}")
    for n_ in notes:
        print(f"  * {n_}")


if __name__ == "__main__":
    main()
