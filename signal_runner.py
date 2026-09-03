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

import omen_bot  # module reference, not just names -- HTF_GRADE_VETO below
                 # must see runtime flips (research scripts patch it on the
                 # module object, `omen_bot.HTF_GRADE_VETO = True`, the same
                 # pattern `bw.LADDER_MODE`/`sr.fill_price` already use
                 # elsewhere in this repo), which `from omen_bot import
                 # HTF_GRADE_VETO` would silently miss (it copies the value at
                 # import time, it does not stay bound to the module).
from omen_bot import (
    Candle, SignalType, TradeGrade, OpeningRangeAnalyzer, TradingSession,
    BreakAndRetestDetector, RuleOf84Detector, PriceActionAnalyzer,
    detect_order_block_setup, find_fvg, detect_flag_setup, detect_break_retest,
)
from discord_bot import DiscordSignalBot
from position_sizer import compute_plan, SizingPlan
from signal_tracker import log_signal
from predicates import is_s_gate


# Order-block tunables (module-level so backtest_sweep.py can vary them).
# 30-day sweeps 2026-07-05: partial_body retests were the leak (wick_only flips
# OB positive). Volume gate re-tested after the grading-anchor fix + PMH/PML:
# it CUT P&L ($1335 vs $2505) — off. B&R-only mode (OB_RETEST_TYPES=()) trades
# 28x @ 50% win if OB ever needs benching.
OB_RETEST_TYPES = ("wick_only",)  # accepted retest strengths
OB_VOLUME_MULT = 0.0  # entry candle volume >= mult x avg(prior 10); 0 = gate off
# 30d A/B 2026-07-05: FVG retests diluted B&R badly (206 trades @33% -$216 vs
# 28 @50% +$1400 raw-level only; 0.1%-min-gap variant still +$277).
# OPUS-SPEC #2: FVG retest zones (2026-07-12)
# fable_rules.yaml line 52: "3-candle gap... is valid retest zone in addition
# to raw level". Prior: FVG blocks accepted any recent gap above/below the
# level — the dilution the 07-05 A/B measured. Change: FVG entry now ALSO
# requires break-leg displacement (_bnr_displacement), i.e. the gap must be
# the one left by the displacement move — the "displacement-anchored detector"
# the old comment said was missing. Default stays False until the anchored
# variant is A/B'd; spec asked for True but the 07-05 evidence stands until
# superseded. Test: signal_runner.py --dry-run.
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
# Austin 2026-08-09: the 84% re-entry arms after a loser from break-and-retest,
# the one candle rule, OR both — not B&R alone. A stopped-out one-candle-rule
# trade now arms it too. FVG and flag losers must NOT arm it (kept out of the
# set). RULE84_ARM_BNR_ONLY is retained as a computed alias so anything reading
# the old boolean name still works; it is now False because the set is wider
# than B&R-only.
RULE84_ARM_ON = frozenset({SignalType.BREAK_AND_RETEST, SignalType.ONE_CANDLE_RULE})
RULE84_ARM_BNR_ONLY = RULE84_ARM_ON == frozenset({SignalType.BREAK_AND_RETEST})

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

# OPUS-SPEC #1: B&R displacement gate (2026-07-12)
# fable_rules.yaml line 50: displacement_gate = "break candle body >= 1.5x avg
# body of prior N candles". omen_bot._has_displacement gates the OCR path only
# (detect_order_block_setup); the B&R entry path never checked displacement.
# Prior: B&R fired on any ordered break/leave/retest/confirm regardless of
# break-leg momentum. Change: [disp]/[nodisp] measurement tag on every B&R card
# + optional cap-at-C gate. Gate defaults OFF: no A/B exists yet, and untested
# gates in this codebase have a losing record (FVG 2026-07-05, flag 2026-07-09).
# Test: signal_runner.py --dry-run exercises both gate states.
# omen-5.0 T11(a): ARMED. Trading-Bot-Rulesets.md clause 5 now defines it
# concretely — "a beyond-level candle in the 5-bar break leg whose body
# (|close - open|) is >= 1.5x the average body of the 10 candles before it...
# The displacement candle must not touch the level being broken" — and says a
# B&R without it can NEVER be S. _bnr_displacement implements exactly that
# paragraph (the no-touch clause was missing and is now in), the gate caps the
# engine grade at C, and compute_austin_tier refuses S outright.
BNR_DISPLACEMENT_GATE = os.getenv("BNR_DISPLACEMENT_GATE", "1").strip().lower() \
    in ("1", "true", "yes", "on")

# Austin trade-notes review 2026-07-06 (91 trades): "middle of a bunch of levels,
# probability goes down significantly"; likes trades where new HOD/LOD can be hit.
LEVEL_BLOCK_CAP = True   # level inside the 2R path caps grade at C (alert-only)
CLEAR_FOR_APLUS = True   # A+/A require entry beyond ALL levels in trade direction
STOP_RANGE_MULT = 0.75   # stop must be >= this x avg 1-min range ("human-proof")
# T5 rename: "X" is the skip grade, "D" is its old letter — both rank 0 so
# either spelling compares correctly.
_GRADE_RANK = {"A+": 4, "A": 3, "B": 2, "C": 1, "X": 0, "D": 0}
# Grade values that mean "skip" (TradeGrade.X, formerly TradeGrade.D)
_SKIP_GRADES = ("X", "D")

# B4 (GRADE_FIX, 2026-07-13) — corrected A+ per B3 audit
# (research/aplus-inversion-audit.md), FLAG-GATED, DEFAULT OFF. Config defaults
# only change at C10; this flag exists purely so the 12mo A/B can measure it.
# Root cause B3 confirmed: RULE84_LESSON=True (line 102) BYPASSES the strong-PA
# gate on 84%-rule re-entries, so the "C -> B" floor in both 84% blocks laundered
# ungated PLAIN-candle reclaims into B, then _grade_for_levels promoted them B -> A
# ("clear of all levels"). Those 22 re-entries ran 22.7%W / -$8,395 = 131% of the
# entire A-tier loss. When GRADE_FIX is ON:
#   (1) the free C -> B floor on 84% re-entries is dropped -> plain reclaims stay C
#       (alert-only, not traded); only genuine strong-PA reclaims (large wick = B)
#       and hammer reclaims (A+) still trade. i.e. cap-at-B unless the reclaim
#       candle itself earns better via PA (B3 fix #1).
#   (2) the clear-road B -> A promotion is blocked for 84% re-entries (B3 fix #3 /
#       H2: that promotion added zero edge, 37% ~ 36.6%, it only relabeled).
GRADE_FIX = os.getenv("GRADE_FIX", "0").strip().lower() in ("1", "true", "yes", "on")

# C5 (HTF_BIAS_GATE, SPEC10, 2026-07-13) — daily-candle trend bias gate,
# FLAG-GATED, DEFAULT OFF. Daily trend proxy = last completed daily close vs
# SMA20 of daily closes (no DXLink MTF needed): bullish if close > SMA20,
# bearish if <. When ON, any signal whose direction fights the daily trend is
# capped to C / alert-only ("only trade the daily trend"). self.daily_bias is
# populated by the caller (live_scanner from yfinance daily candles); None or
# "neutral" => gate is a no-op. Config defaults only change at C10; this flag
# exists purely so the 12mo A/B can measure it. A/B: research/c5_htf_gate_ab.md.
HTF_BIAS_GATE = os.getenv("HTF_BIAS_GATE", "0").strip().lower() in ("1", "true", "yes", "on")

# C9 (RULE84_STRICT / RULE84_OFF, 2026-07-13) — 84%-rule arming variants,
# FLAG-GATED, DEFAULT OFF. Both consulted at the single arm point
# (backtest_week._arm_84 in the backtest; the live re-entry wiring inherits the
# same rule once C10 flips a default). Config defaults only change at C10; these
# exist purely so the 12mo A/B can measure a rulebook-strict 84% detector.
#   RULE84_STRICT: rulebook spec "you need an A+ entry" (bonus_How_To_Read...
#     543s) + same thesis/level/direction. Same-thesis(BNR)/same-level(reclaim of
#     the original entry price)/same-direction are ALREADY enforced by the current
#     arming (RULE84_ARM_ON + the entry_price/entry_direction gate in the 84%
#     blocks); STRICT adds the missing requirement: arm ONLY when the ORIGINAL
#     stopped-out entry graded A+ or A. The current de-martingaled version arms off
#     any counted B&R stop-out regardless of its grade (B3: that laundered grade,
#     C9: it also drags P&L — the B-origin re-entries are the net-negative ones).
#   RULE84_OFF: disable the detector entirely (never arm) = the "84% off" arm.
# A/B: research/c9_rule84_strict_ab.md.
# C10 verdict 2026-07-13: STRICT default ON (strict $79,651 > current $78,190 >
# OFF $75,489 full-pop; tier identical all arms). GRADE_FIX stays OFF — the
# combo run (research/c10_strict_gradefix_charts.json) benches all 4 strict
# re-entries (grades them C) and lands exactly on the OFF arm's $75,489; with
# STRICT removing the 47 B-origin laundered re-entries, A-tier heals anyway
# (58tr 32.8%W -$2,393 -> 44tr 38.6%W +$6,162). n=4/yr caveat: F1 validates.
RULE84_STRICT = os.getenv("RULE84_STRICT", "1").strip().lower() in ("1", "true", "yes", "on")
RULE84_OFF = os.getenv("RULE84_OFF", "0").strip().lower() in ("1", "true", "yes", "on")

# omen-3.6 (S_GATE, 2026-08-06) -- the S gate fit from Austin's S/A/X verdicts,
# FLAG-GATED, DEFAULT OFF. The gate (research/s_gate_spec.md, pre-registered in
# T5 before any backtest) keeps only entries whose entry-bar displacement clears
# the X marks' 50th percentile (0.888). The predicate is predicates.is_s_gate;
# applied here in _route so it covers every candidate entry uniformly. When ON,
# a candidate that fails the gate is capped to C (alert-only), mirroring the
# BNR_DISPLACEMENT_GATE / HTF_BIAS_GATE convention. DEFAULT OFF => shipped
# behaviour byte-identical to today; the harness flips this at runtime for the
# T7 A/B exactly as research/c1_analyze.py flips BNR_DISPLACEMENT_GATE.
S_GATE = False

# omen-3.7 (DETECT_WIDE, T5, 2026-08-08) -- detection widening at the single
# biggest cause of S-blindness, FLAG-GATED, DEFAULT OFF.
#
# Source: research/miss_autopsy.md. Its S column's top row is `no_break_retest`
# -- **27 of the 77 S marks** (35.1%), where detect_break_retest returned falsy
# for every level. research/corpus_miss_autopsy.md (T2.1) independently agrees:
# the same reason tops the 10,263-instance Discord corpus at 4,186 (40.8%).
#
# research/t5_wide_probe.py localises it inside the FSM: on 14 of those 27 the
# sequence stalls at step 3, RETEST -- price broke the level, left it, then
# turned back NEAR it without ever tagging it, and the exact-touch test
# (`c.low <= level`) discards the setup. Widening the window (2 marks) or the
# confirm gap (1 mark) -- the two knobs the autopsy prose guessed at -- barely
# moves it; a retest proximity band reaches 9.
#
# Mechanism (ONE knob): when ON, detect_break_retest's retest step accepts a
# candle within DETECT_WIDE_RETEST_MULT * (avg candle range in the window) of
# the level. Window, max_confirm_gap, the break buffer, the LEAVE step and the
# adverse-wick rule are all unchanged. OFF passes retest_tol_mult=0.0, which is
# today's exact-touch test byte-for-byte => shipped behaviour is identical. The
# harness flips this at runtime exactly as research/c1_analyze.py flips
# BNR_DISPLACEMENT_GATE. Pre-registered recall prediction for T6 is in
# research/detect_wide.md and was written before this code existed.
DETECT_WIDE = False
# 1.0 = "the retest came within one average candle's range of the level". The
# probe's efficient point was 1.3 (13 of 27 vs 9) with a flat curve to 2.5 --
# deliberately NOT taken: 1.3 is fitted to 27 marks, 1.0 is a rule.
DETECT_WIDE_RETEST_MULT = 1.0


# omen-3.8 (RULE_710_ENABLED, T5, 2026-08-09) -- Rules 7 and 10 restated as
# ALWAYS-DEFINED detection conditions, FLAG-GATED, DEFAULT OFF.
#
# Source: research/rule7_rule10.md. Both rules were measured there against the
# 159 marks and both are undefined on a large slice of them, for the SAME
# reason: their start point is a "break candle" (a bar whose body closed across
# the reference level). No break candle => no value. Rule 7 is null on 76/159
# (47.8%), rule 10 on 56/159 (35.2%). A rule the engine cannot evaluate on a bar
# is not a rule, it is a wish, so both conditions below are rewritten to anchor
# on the CURRENT bar -- which always exists -- instead of on a break candle, and
# to saturate rather than return None. Every function here is total: it returns
# a number on every bar, for every level, with no null branch.
#
# Rule 7 (speed of the retest). rule7_retest_bars() counts the bars the level
# spent untouched between price leaving it and now: the away-leg (consecutive
# bars before the retest whose range did not contain the level) plus the lag
# (bars since that retest). Capped at RULE7_WINDOW, and a window with no touch
# at all returns the cap -- "as slow as this window can measure", which fails.
#
# Rule 10 (left-side pivot noise). rule10_left_pivots() uses the same 3-bar
# swing-pivot definition as research/rule7_rule10.py count_left_pivots and
# omen_bot.MarketStructure.update, but over the RULE10_LOOKBACK bars before the
# CURRENT bar rather than before the break; at_level counts the pivots sitting
# within RULE10_LEVEL_TOL of the level -- "is this level already chewed up".
#
# Thresholds are RULES, not fits. rule7_rule10.md's separation tables are
# underpowered on every contrast (|d| below the MDE at this n), so nothing here
# is tuned to those means -- 5 bars is "as soon as possible" read literally, and
# 2 is "at most a couple of old pivots on the level". Same discipline as
# DETECT_WIDE_RETEST_MULT taking 1.0 over the fitted 1.3.
#
# Reference level = sig["stop"], which in every setup below IS the structure
# being retested (stop_level_name spells it: OR high / PDH / Order block low /
# FVG low / Flag low). Applied in _route so it covers every candidate uniformly.
# DEFAULT OFF => shipped behaviour byte-identical to today; when ON, a candidate
# that fails is capped to C (alert-only), mirroring S_GATE / HTF_BIAS_GATE.
# omen-5.0 T11(a): Rule 7's window is now FITTED to Austin's own S marks
# (research/t11_s_quality.md) instead of assumed. The distribution of
# retest-bars at his S marks needs 8 bars to retain 90% of them -- his note
# "lots more candles before retest but I dont mind with the way it wicked and
# tapped from so far away" is visible in that tail. But at 8 bars the rule also
# keeps almost every non-S fire, so arming it would filter nothing and add a
# fitted threshold: RULE_710_ENABLED stays OFF, exactly as this row's spec says
# to do when the fit does not separate. RULE7_MAX_BARS carries the fitted value
# so that the day it is armed it is armed at the measured number, not at 5.
# Rule 10's pivot-count arm is unaffected.
#
# (RULE7_WINDOW below is the SCAN HORIZON -- how far back rule7_retest_bars
# looks before saturating -- not the gate. The gate is RULE7_MAX_BARS.)
RULE_710_ENABLED = False
RULE7_WINDOW = 20
RULE7_MAX_BARS = 8      # fitted 2026-08-11: 90% S retention (was 5, a guess)
RULE10_LOOKBACK = 20
RULE10_MAX_PIVOTS_AT_LEVEL = 2
RULE10_LEVEL_TOL = 0.002        # 0.2% of the level, as in rule7_rule10.py


# omen-3.9 (AUSTIN_TIER, T4, 2026-08-09) -- austin_tier stops being a slot.
#
# From omen-3.7 T5 until now, _route did `sig.setdefault("austin_tier", None)`
# with a comment saying it is always None because no mapping from the engine's
# A+/A/B/C exists. That was the right call then and it is still true now: there
# is no such mapping, and none is invented here. Austin settled the tiers on
# 2026-08-09 as four clauses about the signal itself, so the tier is computed
# from those clauses directly instead of translated from a grade.
#
# The rule is written out in Trading-Bot-Rulesets.md "Austin's Tiers (S / A /
# C / X)"; that section is the spec and this code is its implementation. One
# named helper per clause so T5/T8 can cite a clause instead of re-deriving it:
#   clause 1  setup_is_s_eligible  - B&R / one candle rule / armed 84% re-entry
#   clause 2  bar_extreme_veto     - entry close not at the bar's own extreme
#   clause 3  idea_key             - first S today on this symbol+dir+level
#   clause 4  HTF_OPPOSITION_VETO  - higher timeframe not opposed (a SWITCH)
#
# THIS ROW IS ADDITIVE. austin_tier is a reported field; sig["grade"],
# _SKIP_GRADES and which signals _route accepts are untouched, which is what
# research/regression_gate.py proves.
AUSTIN_TIER_ENABLED = True
# The switch that would restrict _route to S only. READ NOWHERE in this
# version, on purpose: T8 A/Bs it, and arming it is Austin's call.
TRADE_S_ONLY = False
# Clause 4, the one clause Austin has not settled -- so it is a parameter, not
# a constant, and T8 measures both arms.
#   "hard"          an opposed higher timeframe can never be S (today's rule)
#   "fill_override" a signal passing clause 2 may still be S with an opposing HTF
HTF_OPPOSITION_VETO = "hard"
# Clause 2's band: "top 25% of the bar's own range" read literally, not fitted.
BAR_EXTREME_FRAC = 0.25

# ON WATCH -- the third engine state, added 2026-08-23. Off by env if it has to
# be A/B'd: ON_WATCH=0. It is a FILL rule -- see near_session_extreme().
ON_WATCH = os.getenv("ON_WATCH", "1").strip().lower() in ("1", "true", "yes", "on")

# Austin, 2026-08-24: "I don't trade FVG or FLAG. Those are not setups
# anymore." Detection stays on -- the historical numbers stay comparable --
# only routing stops. TRADE_RETIRED_SETUPS=1 is the one-variable-away
# reversal, off by default like every other A/B flag in this file.
RETIRED_SETUPS = frozenset({SignalType.FAIR_VALUE_GAP, SignalType.FLAG})
TRADE_RETIRED_SETUPS = os.getenv("TRADE_RETIRED_SETUPS", "0").strip().lower() \
    in ("1", "true", "yes", "on")

# Clause 1: exactly three setups, nothing else is ever S. FAIR_VALUE_GAP and
# FLAG are deliberately absent.
S_ELIGIBLE_SETUPS = (SignalType.BREAK_AND_RETEST, SignalType.ONE_CANDLE_RULE,
                     SignalType.REENTRY_84_RULE)

# omen-3.9 (ENFORCE_NO_REPEAT, T5, 2026-08-09) -- clause 3 made into a routing
# rule, FLAG-GATED, DEFAULT OFF.
#
# T4 built idea_key(sig) = (symbol, direction, level NAME) and used it inside
# compute_austin_tier's clause 3 ("first S of this idea today") as a reported
# field. This row turns that identity into an actual skip: once an idea has
# been ACCEPTED this session, a later accepted entry on the same idea is
# skipped with [skip: repeat idea] -- the same trade twice is noise Austin does
# not want. The 84% re-entry (SignalType.REENTRY_84_RULE) is the one exemption,
# because it IS by definition the sanctioned second bite at the same idea.
#
# DEFAULT OFF => shipped behaviour byte-identical to today: the per-session
# self._fired_ideas set is maintained on the accept path either way (clause 3
# and the report read it), but nothing is skipped until this is True. The
# harness forces it True in-process for the measurement in
# research/t5_no_repeat_effect.py; arming it is Austin's call. See
# research/t5_no_repeat.md for the suppressed-entry / lost-mark counts.
ENFORCE_NO_REPEAT = False


# omen-4.0 T6 (NO_REPEAT_ENTRIES, 2026-08-09) -- Austin's settled "no repeat
# entries -- take the first one available" rule (Projects/OMEN.md), made into a
# routing rule. Batch 04 showed the engine violating it constantly: TSLA
# 2024-03-27 fired bars 9 (S) and 10 (X) -- adjacent; MSFT 2026-02-11 fired 6
# and 9; NVDA 2024-12-16 fired 7, 14 and 76; TSLA 2024-02-05 fired 8 and 10.
# Every duplicate after the first is an X -- the single largest source of the
# 3% blind equity precision.
#
# Scope is symbol + direction + LEVEL. Once a long off PDH has fired on TSLA,
# no second long off PDH that day. A different level, or the other direction,
# is a different idea and may still fire. The level is its PRICE (rounded to a
# tick), not its name: two names at the same price on the same side is the same
# idea having a second go, and a name would miss that. sig["stop"] IS the
# retested structural level for every setup (B&R -> broken level, OB -> block
# edge, FVG -> gap edge, flag -> flag bound).
#
# The ONLY exemption is an armed 84% re-entry (SignalType.REENTRY_84_RULE):
# by definition the sanctioned second bite at the same idea, so it must stay
# allowed even on a level already taken.
#
# DEFAULT True -- the rule is settled and the engine should enforce it in
# production. A backtest flips it False to measure both arms. See
# research/t6_no_repeat.md. This is keyed and scoped separately from the
# omen-3.9 ENFORCE_NO_REPEAT (name-keyed, default OFF) above: that one tracks
# the same idea by level NAME for tier-clause-3 reporting; this one tracks it
# by level PRICE and actually suppresses the duplicate entry.
NO_REPEAT_ENTRIES = True
# Decimal places to round the level price to (cents = a sensible tick for the
# options names OMEN trades). Mirrors t4_engine_recall's round(sig["stop"], 2).
NO_REPEAT_LEVEL_TICK = 2


# omen-5.0 T3 (SESSION WINDOW / INTRABAR FILL / SESSION-EXTREME VETO / 84% CAPS,
# 2026-08-11) -- four mechanics Austin has written down repeatedly and none of
# which the detector implemented. All four ship ON: this version exists to
# change behaviour, not to add another dormant flag.
#
# (a) The session window lives INSIDE detect_signals now. It used to live only
#     in callers (backtest_week.ENTRY_CUTOFF, live_scanner, t4_engine_recall),
#     so a new caller silently lost it -- that is how 37 of the 80 homework
#     cards were built outside the window and wasted. Austin: "I dont trade
#     past 11 am remember".
SESSION_START = os.getenv("SESSION_START", "09:30:00")
SESSION_END   = os.getenv("SESSION_END", "11:00:00")   # Austin: "I dont trade past 11 am"

# (c) Session HOD/LOD proximity is a VETO, not a demotion (settled 2026-08-11).
#     BAR_EXTREME_FRAC measures where the close sits inside the SIGNAL BAR;
#     this measures how close the fill sits to the SESSION extreme so far --
#     "dont want to be at low of day" / "not right at HOD" (21 notes). Fitted
#     by the A/B in research/t3_session_extreme.md over {0.00, 0.05, 0.10,
#     0.20}; the value below is that measurement's chosen_frac.
#
#     The A/B came back NEGATIVE: 0.00 (veto off) scored the best S-precision
#     (13.11%) of the four, and every armed setting scored at or below it while
#     dropping fires and S-mark coverage (0.05: 12.28%, 7/56 -> 6/56; 0.10:
#     9.09%; 0.20: 11.11%). The spec's own decision rule — highest S-precision
#     that still emits 40% of the control arm's fires — therefore selects 0.00.
#     The mechanic is built and inherited by every subclass through _emit, and
#     arming it is one env var (SESSION_EXTREME_FRAC=0.05). What the marks will
#     not support is arming it by default. See research/t3_session_extreme.md.
SESSION_EXTREME_FRAC = float(os.getenv("SESSION_EXTREME_FRAC", "0.0"))

# (d) 84% rule: 2 attempts on one idea TOTAL (the original entry plus a single
#     re-entry -- "2 is usual"), and the reclaim itself must land before
#     SESSION_END.
RULE84_MAX_ATTEMPTS = int(os.getenv("RULE84_MAX_ATTEMPTS", "2"))

# (b, continued) When the intrabar fill lands ON a level-stop there is no risk
# left to size and the signal dies in the minimum-risk gate. Austin's stated
# rule for exactly that case is that the stop sits on the candle he entered on.
# See intrabar_stop() for the five notes and the 30%-of-B&R measurement.
INTRABAR_STOP_AT_BAR = os.getenv("INTRABAR_STOP_AT_BAR", "1").strip().lower() \
    in ("1", "true", "yes", "on")


# omen-5.0 T10 (PIVOT STRUCTURE AS A LEVEL, 2026-08-11) -- the level type the
# engine has never had.
#
# The engine knows six levels (OR high/low, PDH/PDL, PMH/PML) plus order blocks
# and the session extremes. Austin's eye also trades pivot structure -- swing
# highs and lows built from price itself -- and his notes say so outright:
# "pivot structure break > level break" (AMZN_2025-07-17_34), "no clean break it
# just respect pivot structures" (NVDA_2024-09-06_53), "break/retest of a
# 2-candle structure, not a large pivot" (TSLA_2024-12-03_17), "dont see any
# levels, unless some were forgot to be marked" (SPY_2024-06-11_23).
#
# PIVOT_STRENGTH is bars either side, starting at 2 -- the smallest structure
# his "2-candle structure" note treats as real. A pivot needs PIVOT_STRENGTH
# bars to its RIGHT before it exists, so it is only usable from
# pivot_index + PIVOT_STRENGTH + 1 onward; pivot_levels enforces that with
# as_of, and test_austin_tier asserts it. Getting it wrong is lookahead and
# would make every downstream number a fiction.
PIVOT_LEVELS = os.getenv("PIVOT_LEVELS", "1").strip().lower() in ("1", "true", "yes", "on")
PIVOT_STRENGTH = int(os.getenv("PIVOT_STRENGTH", "2"))
# Only pivots formed inside this many bars of the current one are live
# structure. Same order as RULE10_LOOKBACK (20) and the B&R FSM window: a swing
# from an hour ago is history, not the thing price is retesting now. Without a
# horizon a 90-bar session accumulates ~40 pivots and every B&R level in the
# book gets a duplicate.
PIVOT_LOOKBACK = int(os.getenv("PIVOT_LOOKBACK", "30"))
# A pivot within this fraction of an existing named level is that level, not a
# new one -- same 0.1% dedupe HODLOD_PAIR uses.
PIVOT_DEDUPE_FRAC = float(os.getenv("PIVOT_DEDUPE_FRAC", "0.001"))


# omen-5.0 T11 (S HAS TO EARN ITS WAY, 2026-08-11) -- S stops being the default
# for a detected setup.
#
# compute_austin_tier granted S to any bar where clause 1 held and three
# NEGATIVE filters did not fire. Nothing asked whether the setup was any good.
# B&R fired 74,805 times across the archive while Austin takes 1-3 S a day, and
# that inversion -- not threshold tuning -- is why S-precision is 0-5%. Every
# clause below is a POSITIVE requirement or a hard veto.
#
# (a2) A level that keeps getting hit stops being a level. Austin: "that rule is
#      not a rule without context, you repeat that 3 times and its just not even
#      a break and retest." After LEVEL_RETIRE_TOUCHES completed break-and-
#      retests of the same level in a session, the level is done for the day at
#      EVERY tier -- not a demotion. Distinct from NO_REPEAT_ENTRIES, which only
#      blocks a second entry on an idea that was ACCEPTED.
#
#      Rule 10's rule10_left_pivots at_level count is the structural version of
#      the same phenomenon and stays where it is (the RULE_710 grade arm). It is
#      not reused as the retirement trigger because it counts swing pivots
#      sitting near a price, which retires levels that never produced a signal;
#      Austin's sentence counts the break-and-retests themselves, which is what
#      _level_br_count holds. 0 disables retirement.
LEVEL_RETIRE_TOUCHES = int(os.getenv("LEVEL_RETIRE_TOUCHES", "2"))
# Two fires on the same level inside this many bars are ONE break-and-retest
# having a second go at the entry, not two separate ones -- the same 30-bar
# window backtest_week.DEDUPE_BARS uses to say two fires are one idea. Without
# it, a level that re-fires on consecutive bars retires itself in two minutes,
# which is not what "you repeat that 3 times" means.
LEVEL_RETIRE_COOLDOWN = int(os.getenv("LEVEL_RETIRE_COOLDOWN", "30"))

# (c) In-between mesh is a HARD S-veto (Austin 2026-07-06: "middle of a bunch of
#     levels, probability goes down significantly", made a veto not a demotion on
#     2026-08-11). The computation is _grade_for_levels' own blocking-level test
#     -- a known level sitting inside the entry-to-2R path -- reused, not
#     duplicated, and routed into compute_austin_tier where it had no effect.
#     The mesh set includes the T10 pivot levels; the engine-grade path
#     (LEVEL_BLOCK_CAP) keeps the named-level set it was measured on.
MESH_S_VETO = os.getenv("MESH_S_VETO", "1").strip().lower() in ("1", "true", "yes", "on")

# (e) S+ is a REPORTING RANK inside S, not a new tier letter. All S signals stay
#     S and nothing is discarded -- Austin: "i dont want that discarded, just put
#     it in two separate tiers, not separate grading scale". The top 1-3 per day
#     universe-wide are S+; "the top s trades which usually happen earlier in the
#     day", so the rank is earliest-first, ties broken by engine grade then by
#     confluence.
S_PLUS_PER_DAY = int(os.getenv("S_PLUS_PER_DAY", "3"))


def _retest_tol() -> float:
    """retest_tol_mult to hand detect_break_retest. 0.0 unless DETECT_WIDE."""
    return DETECT_WIDE_RETEST_MULT if DETECT_WIDE else 0.0


def setup_is_s_eligible(sig: dict) -> bool:
    """Clause 1. True only for break-and-retest, the one candle rule (order
    block) and the 84% re-entry — the three setups Austin trades. A
    fair-value-gap entry or a flag breakout is never S no matter how it looks."""
    return sig.get("signal_type") in S_ELIGIBLE_SETUPS


def bar_extreme_veto(sig: dict, candle) -> bool:
    """Clause 2, as a veto: True when the fill is bad enough to block S.

    Vetoes when the entry close sits in the top BAR_EXTREME_FRAC of the signal
    bar's own range (long) or the bottom (short). `candle` is the bar the entry
    is taken on, read AS FORMED at that moment — this is a fill-quality guard
    ("better fills matter" / "don't buy the top"), NOT a wait-for-the-close
    confirmation gate, so it must never be handed a later bar.

    Returns False unconditionally for SignalType.REENTRY_84_RULE: on the 84%
    re-entry the close back through the failed entry IS the signal, so an
    extreme close is the thing being asked for. A zero-range bar cannot say
    where in its range the close sits, so it does not veto."""
    if sig.get("signal_type") is SignalType.REENTRY_84_RULE:
        return False
    entry = sig.get("entry")
    if candle is None or entry is None:
        return False
    rng = candle.high - candle.low
    if rng <= 0:
        return False
    if sig.get("direction") == "call":
        return entry >= candle.high - BAR_EXTREME_FRAC * rng
    return entry <= candle.low + BAR_EXTREME_FRAC * rng


def bar_time(ts) -> str:
    """"HH:MM:SS" from a bar timestamp, whatever shape the caller carries.

    Archive replays hand "09:31:00", live_scanner hands the same, but a JSON
    feed may hand an ISO stamp ("2026-08-11T09:31:00-04:00") and some sources
    hand "09:31". All three have to answer the same question — is this bar
    inside the window Austin trades — so they are normalised here rather than
    at four call sites."""
    if not ts:
        return ""
    s = str(ts)
    if "T" in s:
        s = s.split("T", 1)[1]
    elif " " in s:
        s = s.split(" ", 1)[1]
    s = s[:8]
    if len(s) == 5:          # "09:31" -> "09:31:00"
        s += ":00"
    return s


def in_session(ts) -> bool:
    """T3(a). True when this bar is inside [SESSION_START, SESSION_END) —
    09:30–11:00, Austin's whole trading window. An unparseable stamp passes:
    a detector that silently stopped firing on an unfamiliar timestamp format
    would be worse than one that fires."""
    t = bar_time(ts)
    if len(t) != 8:
        return True
    return SESSION_START <= t < SESSION_END


def fill_price(level: float, candle, is_long: bool,
               session_hi=None, session_lo=None) -> float:
    """Austin 2026-08-11: fill at the close, except when the close sits inside
    BAR_EXTREME_FRAC of the bar's own extreme in the trade direction — then fill
    at the level, which is where he actually enters as the candle is forming.

    "those candles that move fast and close at high of day or low of day, i
    just want to try to not miss out." The level is clamped into the bar's own
    range: he cannot be filled at a price the bar never traded."""
    if candle is None:
        return level
    if level is None:
        return candle.close
    probe = {"entry": candle.close, "direction": "call" if is_long else "put"}
    # Two ways the close is a bad fill: it sits at the BAR's own extreme (T3(b),
    # 2026-08-11), or the bar closed against the SESSION extreme (ON WATCH,
    # 2026-08-23). Either one and the fill goes back to the level, clamped into
    # the bar's range -- he cannot be filled where the bar never traded.
    if not (bar_extreme_veto(probe, candle)
            or (ON_WATCH and near_session_extreme(candle, is_long,
                                                  session_hi, session_lo))):
        return candle.close
    return min(max(level, candle.low), candle.high)


def near_session_extreme(candle, is_long: bool, session_hi, session_lo) -> bool:
    """Did this bar CLOSE jammed against the day's high (long) or low (short)?

    Austin, 2026-08-23, defining ON WATCH after rejecting a price-trigger version:

        you can't make your decision based on the previous candle, but you can
        enter on the candle you want to enter at candle close if it's one of
        those that are **too close to the high for the day**

    The close still decides WHETHER to trade. This decides whether the close is a
    fair FILL. "Too close" is BAR_EXTREME_FRAC of the session's own range -- the
    same 25% that governs the 84% reclaim and stop slippage. One tolerance unit.

    Note this is the OPPOSITE reading to ``session_extreme_veto``, which SKIPS
    signals at the session extreme (SESSION_EXTREME_FRAC, default 0.0 = off).
    Austin does not skip those days. He takes them and refuses to pay the close.
    """
    if session_hi is None or session_lo is None:
        return False
    rng = session_hi - session_lo
    if rng <= 0:
        return False
    band = BAR_EXTREME_FRAC * rng
    return (candle.close >= session_hi - band) if is_long else (candle.close <= session_lo + band)


def pivot_levels(candles, strength: Optional[int] = None,
                 as_of: Optional[int] = None, lookback: Optional[int] = None):
    """T10. Swing highs and lows built from price itself, as levels.

    A pivot high is a bar whose high exceeds the highs of the `strength` bars on
    EITHER side of it; a pivot low mirrors it. Each level is a dict:

        {"index": int,        the bar the pivot formed ON
         "usable_from": int,  index + strength + 1 — the first bar that may see it
         "price": float,
         "kind": "high" | "low",
         "name": "pivot high @HH:MM" / "pivot low @HH:MM"}

    `as_of` is the index of the bar being traded. A pivot needs `strength` bars
    to its RIGHT to exist, so with as_of set, only pivots whose `usable_from` is
    at or before it are returned — that is the no-lookahead guarantee, and it is
    the whole reason this takes an index rather than a slice. `lookback` drops
    pivots older than that many bars before `as_of` (live structure, not the
    session's whole history).

    The name carries the pivot's own time, so idea_key() and
    _targets_session_extreme() keep working unchanged: two pivots at the same
    price from different bars are different ideas, which is what they are."""
    k = PIVOT_STRENGTH if strength is None else strength
    n = len(candles)
    if k < 1 or n < 2 * k + 1:
        return []
    out = []
    for i in range(k, n - k):
        usable = i + k + 1
        if as_of is not None:
            if usable > as_of:          # not yet formed on the bar being traded
                continue
            if lookback is not None and i < as_of - lookback:
                continue
        c = candles[i]
        window = [j for j in range(i - k, i + k + 1) if j != i]
        stamp = bar_time(c.timestamp)[:5]
        if all(c.high > candles[j].high for j in window):
            out.append({"index": i, "usable_from": usable, "price": c.high,
                        "kind": "high", "name": f"pivot high @{stamp}"})
        if all(c.low < candles[j].low for j in window):
            out.append({"index": i, "usable_from": usable, "price": c.low,
                        "kind": "low", "name": f"pivot low @{stamp}"})
    return out


def intrabar_stop(entry: float, stop: float, candle, is_long: bool) -> float:
    """The stop that goes with an intrabar fill.

    T3(b) fills at the LEVEL when the close sits at the bar's extreme. For
    break-and-retest the level IS the stop (BNR_STOP_MODE="level"), so that fill
    lands exactly on the stop and the trade has no risk to size — measured on
    the marked-day population, 223 of 744 B&R signals (30%) collapsed this way
    and were dropped by the minimum-risk gate. Silently losing 30% of the
    detector to a fill rule is not what T3(b) is for.

    Austin's own answer, written five times in the recovered reviews: the stop
    goes on the candle he entered on. "stop loss top of wick of candle you
    entered" (COIN 2026-01-22), "stop a little lower bottom of candle you
    entered on" (INTC 2026-06-10), "stop could be bottom wick of green candle"
    (ORCL 2026-01-16), "needs to be top wick of candle you entered" (AMD
    2026-05-13), "stop loss at the bottom of the wick you entered" (IREN
    2026-06-02). So: only when the fill has landed at or through the level-stop,
    the stop moves to the entry bar's own extreme. Every other setup keeps its
    structural stop untouched — this fires only where the geometry collapsed."""
    if not INTRABAR_STOP_AT_BAR or candle is None:
        return stop
    collapsed = (entry <= stop) if is_long else (entry >= stop)
    if not collapsed:
        return stop
    bar_stop = candle.low if is_long else candle.high
    if (bar_stop < entry) if is_long else (bar_stop > entry):
        return bar_stop
    return stop


def idea_key(sig: dict) -> tuple:
    """Clause 3's identity: (symbol, direction, level_name).

    The level is its NAME (OR high / OR low / PDH / PDL / PMH / PML — whatever
    stop_level_name spells for this setup), never its price: the same level
    broken again at a different tick is the same idea having a second go, and a
    price would make it look like a new one."""
    return (sig.get("symbol"), sig.get("direction"), sig.get("stop_level_name"))


def _targets_session_extreme(sig: dict) -> bool:
    """C's other arm: the signal targets the session HOD/LOD. Those are the
    levels HODLOD_PAIR builds, and stop_level_name is where they surface."""
    return sig.get("stop_level_name") in ("HOD", "LOD")


def _htf_opposes(sig: dict, htf_bias) -> bool:
    """Clause 4's raw condition, before the HTF_OPPOSITION_VETO switch. A
    missing or neutral bias opposes nothing."""
    if htf_bias not in ("bullish", "bearish"):
        return False
    return htf_bias == ("bearish" if sig.get("direction") == "call" else "bullish")


def blocking_levels(sig: dict, levels) -> list:
    """Levels sitting inside the entry-to-2R path — the "in-between mesh".

    Extracted from _grade_for_levels so the engine grade (LEVEL_BLOCK_CAP) and
    Austin's tier (MESH_S_VETO, T11(c)) read ONE computation. The traded level
    itself is ignored (within 10% of risk of the entry); everything else between
    the entry and its 2R target is road he has to get through."""
    entry, stop = sig.get("entry"), sig.get("stop")
    if entry is None or stop is None or not levels:
        return []
    risk = abs(entry - stop)
    if risk == 0:
        return []
    target = entry + 2 * risk if sig.get("direction") == "call" else entry - 2 * risk
    lo, hi = min(entry, target), max(entry, target)
    return [l for l in levels if l is not None and lo < l < hi
            and abs(l - entry) > 0.1 * risk]


def rank_s_plus(signals, per_day: Optional[int] = None) -> list:
    """T11(e). Stamp `s_rank` on a day's S signals: the top `per_day` are "S+",
    the rest stay "S". NOTHING is discarded — this is a reporting rank inside S,
    on one grading scale.

    Order is earliest-first ("the top s trades which usually happen earlier in
    the day"), ties broken by engine grade then by confluence. `signals` is any
    iterable of signal dicts carrying `austin_tier`, a timestamp under
    "timestamp" or "entry_time", `grade` and optionally `confluence`; they are
    grouped by their "day" key so a multi-day set ranks per day, universe-wide,
    which a per-symbol runner cannot do on its own."""
    cap = S_PLUS_PER_DAY if per_day is None else per_day
    by_day = {}
    for s in signals:
        if s.get("austin_tier") != "S":
            continue
        by_day.setdefault(s.get("day"), []).append(s)
    for _day, rows in by_day.items():
        rows.sort(key=lambda s: (str(s.get("timestamp") or s.get("entry_time") or ""),
                                 -_GRADE_RANK.get(s.get("grade"), 0),
                                 0 if s.get("confluence") else 1))
        for i, s in enumerate(rows):
            s["s_rank"] = "S+" if i < cap else "S"
    return signals


def compute_austin_tier(sig: dict, candles, fired_ideas, htf_bias) -> str:
    """Austin's tier for this signal: "S", "A" or "C". Never "X" — X is his
    marking vocabulary for a level not worth tracking, not something the engine
    emits (Trading-Bot-Rulesets.md, "Austin's Tiers").

    `fired_ideas` is the set of idea_key()s that have already produced an S
    today; `candles` ends on the bar the entry is taken on.

    All four clauses -> S. Clause 1 holds and one or two of 2/3/4 fail -> A.
    Clause 1 holds with three failures, or the signal targets the session
    HOD/LOD -> C. Clause 1 fails -> C.
    """
    if not setup_is_s_eligible(sig):
        return "C"
    if _targets_session_extreme(sig):
        return "C"
    # T11(a) — the positive quality clause S never had. Trading-Bot-Rulesets.md
    # clause 5: a break-and-retest whose break leg showed no displacement "can
    # never be S, whatever the other clauses say".
    if (BNR_DISPLACEMENT_GATE
            and sig.get("signal_type") is SignalType.BREAK_AND_RETEST
            and sig.get("displacement") is False):
        return "C"
    # T11(c) — in-between mesh is a HARD veto, not a demotion. A level (named or
    # pivot) sitting between the entry and its 2R target means no clear room.
    if MESH_S_VETO and sig.get("mesh_blocked"):
        return "C"
    is_reentry = sig.get("signal_type") is SignalType.REENTRY_84_RULE
    # clause 2 — fill quality on the entry bar as formed
    fill_ok = not bar_extreme_veto(sig, candles[-1] if candles else None)
    # clause 3 — first S of this idea today; the armed re-entry is allowed to
    # be the second, that is what it is for
    fresh = is_reentry or idea_key(sig) not in (fired_ideas or ())
    # clause 4 — the unsettled one, read through the switch
    if _htf_opposes(sig, htf_bias):
        htf_ok = HTF_OPPOSITION_VETO == "fill_override" and fill_ok
    else:
        htf_ok = True
    fails = sum(1 for ok in (fill_ok, fresh, htf_ok) if not ok)
    if fails == 0:
        return "S"
    return "A" if fails <= 2 else "C"


def rule7_retest_bars(candles, level, window: int = RULE7_WINDOW) -> int:
    """Rule 7 feature: bars the level went untouched between price leaving it
    and the current bar. ALWAYS an int in [0, window] — never None.

    A bar 'touches' the level when the level lies inside its range
    (low <= level <= high). Scanning back from the current bar: the most recent
    touching bar is the retest; the bars since it are the lag; the run of
    non-touching bars immediately before it is the away-leg. No touching bar
    inside the window returns `window` (saturated = slowest measurable), which
    is what replaces rule7_rule10.py's None on the no-break-candle case."""
    n = len(candles)
    if n == 0 or level is None or window <= 0:
        return max(window, 0)
    lo = max(0, n - window)
    touch = lambda c: c.low <= level <= c.high
    retest_i = None
    for k in range(n - 1, lo - 1, -1):
        if touch(candles[k]):
            retest_i = k
            break
    if retest_i is None:
        return window
    away = 0
    k = retest_i - 1
    while k >= lo and not touch(candles[k]):
        away += 1
        k -= 1
    return min(window, (n - 1 - retest_i) + away)


def rule10_left_pivots(candles, level, lookback: int = RULE10_LOOKBACK,
                       tol: float = RULE10_LEVEL_TOL):
    """Rule 10 feature: (count, at_level) 3-bar swing pivots whose centre lies
    in the `lookback` bars before the current bar. ALWAYS a pair of ints —
    (0, 0) when there is not enough history, never None.

    Pivot definition is rule7_rule10.py count_left_pivots': a high above both
    neighbours and/or a low below both; a bar that is both contributes two.
    `at_level` counts the pivot prices within `tol` of the level."""
    n = len(candles)
    i = n - 1
    prices = []
    for p in range(max(1, i - lookback), i):
        if p + 1 >= n:
            break
        h, l = candles[p].high, candles[p].low
        if h > candles[p - 1].high and h > candles[p + 1].high:
            prices.append(h)
        if l < candles[p - 1].low and l < candles[p + 1].low:
            prices.append(l)
    at_level = (sum(1 for pr in prices if abs(pr - level) <= tol * abs(level))
                if level else 0)
    return len(prices), at_level


def rule_710_reject(candles, level) -> Optional[str]:
    """Rules 7 + 10 evaluated on the current bar against `level`. Returns None
    when both pass, else a short reason naming the one that failed. Total by
    construction: both features are defined on every bar, so this never has to
    say 'undefined'. A missing level is the one abstain — nothing to measure
    against — and it passes rather than blocks."""
    if level is None or not candles:
        return None
    bars = rule7_retest_bars(candles, level)
    if bars > RULE7_MAX_BARS:
        return f"rule7 retest {bars}>{RULE7_MAX_BARS} bars"
    _cnt, at_level = rule10_left_pivots(candles, level)
    if at_level > RULE10_MAX_PIVOTS_AT_LEVEL:
        return f"rule10 {at_level} pivots on level"
    return None


def daily_trend_bias(daily_closes, period: int = 20) -> Optional[str]:
    """Daily-candle trend proxy used by HTF_BIAS_GATE. `daily_closes` = list of
    COMPLETED daily closes in chronological order, most recent last, EXCLUDING
    the current (still-forming) session — so there is no look-ahead. Returns
    'bullish' if the last close is above its SMA(period), 'bearish' if below,
    None if fewer than `period` closes are available. Simple + robust by design
    (close-vs-SMA20); do not grow this into a framework."""
    if not daily_closes or len(daily_closes) < period:
        return None
    sma = sum(daily_closes[-period:]) / period
    last = daily_closes[-1]
    if last > sma:
        return "bullish"
    if last < sma:
        return "bearish"
    return "neutral"


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
        # C5 HTF_BIAS_GATE: daily-candle trend ('bullish'/'bearish'/'neutral'),
        # set by the caller via daily_trend_bias(). None => gate no-op.
        self.daily_bias: Optional[str] = None
        # F4 (qqq-alignment-rules.md Rule 4): QQQ's first PD/PM key-level break
        # times for the session — {"up": "HH:MM:SS"|None, "dn": ...} or None
        # when no QQQ data. Set by backtest_12mo; tag-only, no routing.
        self.qqq_breaks: Optional[dict] = None
        # omen-3.9 T4 clause 3 / T5 no-repeat: idea_key()s of every signal this
        # runner has ACCEPTED today. Clause 3 reads it (an idea already accepted
        # cannot be S again today); T5, when ENFORCE_NO_REPEAT is armed, skips a
        # later accepted entry on the same idea outright. Same per-runner "today"
        # scope as self._dir_fired.
        self._fired_ideas = set()
        # omen-4.0 T6 no-repeat-entries: (symbol, direction, rounded level
        # price) of every signal this runner has ACCEPTED today. A later
        # accepted entry on the same symbol+direction+level is suppressed --
        # the armed 84% re-entry excepted (it IS the sanctioned second bite).
        # Same per-runner "today" scope as self._fired_ideas; only consulted
        # when NO_REPEAT_ENTRIES is True (the default), but maintained on the
        # accept path either way so the report can read it.
        self._fired_levels = set()
        # omen-5.0 T3(d): attempts spent on one 84%-rule idea today, keyed by
        # (direction, original entry price rounded to a tick). The original
        # entry is attempt 1, so the armed re-entry is attempt 2 and
        # RULE84_MAX_ATTEMPTS stops there — "2 is usual".
        self._attempts_84 = {}
        # omen-5.0 T11(a2): completed break-and-retests per (symbol, level name)
        # today. The LEVEL_RETIRE_TOUCHES-th one retires the level for the rest
        # of the session, at every tier.
        self._level_br_count = {}
        # T10 pivot prices live on the bar being traded — the mesh S-veto reads
        # them alongside the named level map.
        self._pivot_prices = []
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

    def _bnr_displacement(self, level: float, is_long: bool) -> bool:
        """Displacement in the B&R break leg, exactly as Trading-Bot-Rulesets.md
        clause 5 defines it (T7): a beyond-level candle in the 5-bar leg whose
        body is >= 1.5x the average body of the 10 candles before it (the
        DISPLACEMENT_MULT convention shared with omen_bot._has_displacement and
        the A+ stack), AND which does not touch the level being broken.

        omen-5.0 T11(a) added the no-touch clause. A bar that closes past the
        level but still wicks back into it did not displace off it — it is the
        drift the rulebook says can never be S."""
        lookback = self.candles[-6:-1]
        beyond = ((lambda c: c.close > level and c.low > level) if is_long
                  else (lambda c: c.close < level and c.high < level))
        prior = self.candles[-16:-6] or self.candles[:-6]
        avg_body = (sum(abs(c.close - c.open) for c in prior) / len(prior)) if prior else 0
        return avg_body > 0 and any(
            beyond(c) and abs(c.close - c.open) >= 1.5 * avg_body for c in lookback)

    def _aplus_stack(self, level: float, is_long: bool) -> bool:
        """Austin's A+ spec 2026-07-06: FIRST clean break of the level today,
        displacement in the break leg, strong PA entry candle."""
        current = self.candles[-1]
        earlier = self.candles[:-6]
        beyond = (lambda c: c.close > level) if is_long else (lambda c: c.close < level)
        first_break = not any(beyond(c) for c in earlier)
        return (first_break and self._bnr_displacement(level, is_long)
                and self._strong_pa(current))

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
        # T11(c): one computation, two readers — blocking_levels() is also what
        # the mesh S-veto reads. Ignores the traded level itself.
        blocking = blocking_levels(sig, levels)
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
                if GRADE_FIX and sig.get("signal_type") == SignalType.REENTRY_84_RULE:
                    # B4/H2: 84% re-entries don't earn the clear-road A promotion
                    # (it added no edge, 37% ~ 36.6%; kept these at B not A)
                    pass
                else:
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
                # omen-3.9 T4: "S"/"A"/"C" from compute_austin_tier (was always
                # None while it was a slot); None only if the tier is disabled
                austin_tier=sig.get("austin_tier"),
            )
        except OSError as e:
            print(f"⚠ signal log write failed: {e}")

    def _session_extremes(self) -> tuple:
        """(high, low) of the session SO FAR — every bar from SESSION_START up
        to and including the signal bar. No future bars, ever: this is read on
        the entry bar and the answer must be the one Austin could have seen."""
        bars = [c for c in self.candles if bar_time(c.timestamp) >= SESSION_START] \
            or list(self.candles)
        if not bars:
            return (None, None)
        return (max(c.high for c in bars), min(c.low for c in bars))

    def session_extreme_veto(self, sig: dict) -> bool:
        """T3(c). True when the fill sits within SESSION_EXTREME_FRAC of the
        session extreme it is running into — a long buying the high of day, a
        short selling the low of day. 21 of Austin's notes say some form of
        "dont want to be at low of day" / "not right at HOD", and on 2026-08-11
        he settled that this is a VETO (the signal is not emitted) rather than
        the S->A demotion BAR_EXTREME_FRAC gives.

        SESSION_EXTREME_FRAC <= 0 disables it, which is the A/B's control arm."""
        if SESSION_EXTREME_FRAC <= 0:
            return False
        entry = sig.get("entry")
        if entry is None:
            return False
        hi, lo = self._session_extremes()
        if hi is None or lo is None:
            return False
        band = SESSION_EXTREME_FRAC * (hi - lo)
        if band <= 0:
            return False
        if sig.get("direction") == "call":
            return entry >= hi - band
        return entry <= lo + band

    def _emit(self, signals: List[dict], sig: dict) -> None:
        """Every detection site posts through here, not straight to _route.

        _route is overridden by BacktestRunner and by the research replays; a
        veto placed inside it would be silently absent from exactly the runs
        that measure it. The session-extreme veto therefore sits in front of
        _route where every subclass inherits it."""
        if not TRADE_RETIRED_SETUPS and sig.get("signal_type") in RETIRED_SETUPS:
            sig.setdefault("symbol", self.symbol)
            self._log_record(sig, status="skipped", skip_reason="retired setup")
            return
        if self.session_extreme_veto(sig):
            sig.setdefault("symbol", self.symbol)
            sig["reason"] = sig.get("reason", "") + " [veto: at session extreme]"
            self._log_record(sig, status="skipped", skip_reason="at session extreme")
            return
        # T11(d): remember which of the three S setups fired on this bar and
        # side, before any routing filter can hide one. Confluence is REPORTED,
        # never required — a lone clean setup is still S.
        if sig.get("signal_type") in S_ELIGIBLE_SETUPS:
            self._bar_setups.setdefault(sig.get("direction"), set()).add(
                sig["signal_type"].value)
        self._route(signals, sig)

    def _route(self, signals: List[dict], sig: dict) -> None:
        """Accept viable signals; log D-grade / tight-stop skips for post-session analysis."""
        self._grade_for_levels(sig)
        self._calibration_grade(sig)
        # omen-3.6 S_GATE (default OFF): cap low-displacement candidate entries
        # to C (alert-only). Mirrors BNR_DISPLACEMENT_GATE / HTF_BIAS_GATE. OFF =
        # byte-identical to today. See research/s_gate_spec.md.
        if S_GATE and sig["grade"] in ("A+", "A", "B") and not is_s_gate(self.candles):
            sig["grade"] = TradeGrade.C.value
            sig["reason"] += " [capped C: S_GATE low displacement]"
        # omen-3.8 RULE_710_ENABLED (default OFF): Rules 7 (retest speed) and 10
        # (left-side pivot noise) as always-defined conditions on the retested
        # structure — sig["stop"]. Both are evaluable on every bar, so the
        # "no break candle -> null" case that made these rules unimplementable
        # in research/rule7_rule10.md cannot occur here. OFF = byte-identical to
        # today. See Trading-Bot-Rulesets.md "Rule 7" / "Rule 10".
        if RULE_710_ENABLED and sig["grade"] in ("A+", "A", "B"):
            why = rule_710_reject(self.candles, sig.get("stop"))
            if why:
                sig["grade"] = TradeGrade.C.value
                sig["reason"] += f" [capped C: {why}]"
        # omen-3.9 T4: austin_tier is now COMPUTED (S/A/C) from Austin's four
        # clauses, not a None slot. Reported only — nothing below branches on
        # it, and TRADE_S_ONLY is read nowhere in this version. See
        # Trading-Bot-Rulesets.md "Austin's Tiers (S / A / C / X)".
        # omen-5.0 T11(c): the mesh the tier veto reads is the named level map
        # PLUS the T10 pivot levels — "another known level (including the new
        # pivot levels from T10) sitting between it and its 2R target". The
        # engine-grade path above keeps the named-only set it was measured on.
        mesh_levels = list(getattr(self, "_active_levels", []))
        mesh_levels += [p for p in getattr(self, "_pivot_prices", [])]
        sig["mesh_blocked"] = bool(blocking_levels(sig, mesh_levels))
        if AUSTIN_TIER_ENABLED:
            sig["symbol"] = self.symbol           # idea_key's first element
            sig["austin_tier"] = compute_austin_tier(
                sig, self.candles, self._fired_ideas, self.htf_bias)
            # T11(e): every S carries a rank. S+ is decided per DAY and
            # universe-wide, which one symbol's runner cannot see, so the
            # promotion is rank_s_plus()'s job — the runner ships the floor.
            if sig["austin_tier"] == "S":
                sig.setdefault("s_rank", "S")
        else:
            sig.setdefault("austin_tier", None)
        # T11(a2): a level that has already been broken and retested
        # LEVEL_RETIRE_TOUCHES times today is DONE — every tier, not a demotion.
        # Austin: "you repeat that 3 times and its just not even a break and
        # retest." Counted per symbol + level name, direction-agnostic: the same
        # level failing both ways is the same level being chewed up.
        if LEVEL_RETIRE_TOUCHES > 0 and sig.get("signal_type") in (
                SignalType.BREAK_AND_RETEST, SignalType.ONE_CANDLE_RULE):
            lv_key = (self.symbol, sig.get("stop_level_name"))
            bar = len(self.candles) - 1
            done, last = self._level_br_count.get(lv_key, (0, -10 ** 9))
            if done >= LEVEL_RETIRE_TOUCHES:
                sig["reason"] += " [retired: level broken and retested %d times]" % done
                sig["level_retired"] = True
                self._log_record(sig, status="skipped", skip_reason="level retired")
                return
            if bar - last >= LEVEL_RETIRE_COOLDOWN:
                self._level_br_count[lv_key] = (done + 1, bar)
        if sig["grade"] not in _SKIP_GRADES:
            # omen-3.9 T5: enforce clause 3 as a routing rule. Once an idea
            # (symbol, direction, level NAME) has been accepted this session, a
            # later accepted entry on the same idea is skipped — the 84%
            # re-entry excepted, that IS the sanctioned second bite at the same
            # idea. DEFAULT OFF: _fired_ideas is maintained on the accept path
            # either way (clause 3 and the report read it), so nothing is
            # skipped until ENFORCE_NO_REPEAT is True. See research/t5_no_repeat.md.
            sig.setdefault("symbol", self.symbol)
            if (ENFORCE_NO_REPEAT
                    and sig.get("signal_type") is not SignalType.REENTRY_84_RULE
                    and idea_key(sig) in self._fired_ideas):
                sig["reason"] += " [skip: repeat idea]"
                self._log_record(sig, status="skipped", skip_reason="repeat idea")
                return
            # tight-stop skip only for C — it killed 42 of 303 labeled takes
            # (calibration 2026-07-06); B+ setups size to the stop instead
            if sig["grade"] != "C" or self._min_viable_stop(sig["entry"], sig["stop"], sig["direction"]):
                # omen-4.0 T6: no repeat entries on the same symbol+direction+
                # LEVEL. The armed 84% re-entry is the ONE exemption — it is by
                # definition the sanctioned second bite at the same idea, so it
                # stays allowed on a level already taken. DEFAULT ON
                # (NO_REPEAT_ENTRIES=True). Suppression sits inside the accepted
                # branch on purpose: a tight-stop skip never fired, so it must
                # not claim the level — the first AVAILABLE entry wins. The
                # level is sig["stop"] rounded to NO_REPEAT_LEVEL_TICK (cents).
                # See research/t6_no_repeat.md.
                is_reentry = sig.get("signal_type") is SignalType.REENTRY_84_RULE
                nr_key = (self.symbol, sig["direction"],
                           round(sig["stop"], NO_REPEAT_LEVEL_TICK))
                if (NO_REPEAT_ENTRIES and not is_reentry
                        and nr_key in self._fired_levels):
                    sig["reason"] += " [skip: repeat entry]"
                    self._log_record(sig, status="skipped", skip_reason="repeat entry")
                    return
                self._dir_fired[sig["direction"]] = self._dir_fired.get(sig["direction"], 0) + 1
                # clause 3 bookkeeping: every accepted signal records its idea,
                # so a later entry on the same symbol+direction+level cannot be
                # S (clause 3) and, when ENFORCE_NO_REPEAT is armed, is skipped.
                # Recorded on the ACCEPTED path only — a skipped signal never
                # fired. Same per-runner "today" scope as _dir_fired.
                self._fired_ideas.add(idea_key(sig))
                # T6 no-repeat bookkeeping: the same accept records the level
                # price, so a later accepted entry on the same symbol+
                # direction+level is suppressed (84% re-entry excepted above).
                self._fired_levels.add(nr_key)
                signals.append(sig)
                return
            self._log_record(sig, status="skipped", skip_reason="stop too tight (<0.5% of entry and premium risk <$0.20)")
            return
        self._log_record(sig, status="skipped", skip_reason="X grade (skip)")

    def detect_signals(self) -> List[dict]:
        """Scan candles for signals, grade A-D, filter D.

        Returns list of dicts with: signal_type, reason, entry, stop, direction,
        grade, stop_level_name, stop_width_pct.
        """
        if len(self.candles) < 5:
            return []

        # omen-5.0 T3(a): the 09:30-11:00 window is enforced HERE, not only in
        # callers. Austin: "I dont trade past 11 am remember". The caller-side
        # cutoffs (backtest_week.ENTRY_CUTOFF, live_scanner, t4_engine_recall)
        # stay where they are — they are now redundant, not wrong.
        if not in_session(self.candles[-1].timestamp):
            return []

        signals = []
        self._bar_setups = {}      # T11(d): S-eligible setups seen on THIS bar
        current = self.candles[-1]
        or_high, or_low = OpeningRangeAnalyzer.get_opening_range(self.candles)
        # Session extremes (HOD/LOD) — used by 84% rule RR checks
        hod = max(c.high for c in self.candles)
        lod = min(c.low for c in self.candles)
        # True prior-day levels when live_scanner provided them, else session proxy
        pdh = self.pdh if self.pdh is not None else hod
        pdl = self.pdl if self.pdl is not None else lod

        # Clustered-level bars no longer hard-skip (Austin 2026-08-07,
        # OMEN-CONSOLIDATED.md settled input #2): levels bunched within 0.5%
        # are NOT a no-trade gate — one level broken and retested cleanly is
        # enough to trade. The blanket early-return that abandoned the whole
        # bar was removed; the per-setup B&R / OB / FVG loops below now run
        # against whichever single level the bar actually breaks and retest,
        # and fall through to "no signal" only if none of them fire.

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

        # omen-5.0 T10: pivot structure, fed to break-and-retest exactly as the
        # named levels are. One-sided entries — a pivot high is a long's level
        # and a pivot low is a short's, and each loop skips the side it has no
        # level for. as_of pins them to bars that had already formed BEFORE the
        # bar being traded; a pivot within PIVOT_DEDUPE_FRAC of a named level is
        # that level having a second name, not a new one.
        self._pivot_names = set()
        self._pivot_prices = []
        if PIVOT_LEVELS:
            here = len(self.candles) - 1
            for p in pivot_levels(self.candles, as_of=here, lookback=PIVOT_LOOKBACK):
                if any(abs(p["price"] - l) <= PIVOT_DEDUPE_FRAC * abs(l)
                       for l in self._active_levels if l):
                    continue
                self._pivot_names.add(p["name"])
                self._pivot_prices.append(p["price"])
                if p["kind"] == "high":
                    level_pairs.append((p["name"], None, p["price"], None))
                else:
                    level_pairs.append((None, p["name"], None, p["price"]))

        # ---- CALL SIDE (bullish) ----

        # B&R long: prior breakout of a reference high, retest
        for hi_name, _lo_name, level_hi, level_lo in level_pairs:
            if level_hi is None:  # F3 pair may carry only one qualifying side
                continue
            # Austin 2026-07-09 ORDERED break-and-retest (omen_bot.detect_break_retest):
            # break → LEAVE the level → come back → confirm, IN ORDER. Replaces the
            # presence-in-window booleans that let chop/no-return fire (his review).
            br_out = {}
            br_note = detect_break_retest(self.candles, level_hi, is_long=True, out=br_out,
                                          retest_tol_mult=_retest_tol())
            if br_note and (current.close > level_hi):
                stop = level_hi
                if BNR_STOP_MODE == "retest":
                    stop = br_out["retest_low"]
                elif BNR_STOP_MODE == "buffer":
                    recent = self.candles[-11:-1]
                    avg_rng = (sum(c.high - c.low for c in recent) / len(recent)) if recent else 0.0
                    stop = level_hi - max(0.10, 0.10 * avg_rng)
                # T3(b): close by default, intrabar at the level on an extreme close.
                # ON WATCH overrides it: if the bar never closed through the level
                # we are in on the trigger price, mid-bar, which is the entire
                # point -- a bar that runs to HOD and closes there used to be
                # either skipped or filled at a price that shot the R:R.
                entry = fill_price(level_hi, current, is_long=True,
                                   session_hi=hod, session_lo=lod)
                stop = intrabar_stop(entry, stop, current, is_long=True)
                stock_risk = entry - stop
                grade = PriceActionAnalyzer.grade_trade(current, lookback, level_hi, level_lo,
                                                        is_long=True, htf_bias=self.htf_bias)
                # Austin 2026-07-10: level already broken earlier in the session
                # = dirty/late entry — cap at B (kept for the clean-vs-late A/B).
                if "LATE" in br_note and grade.value in ("A+", "A"):
                    grade = TradeGrade.B
                stack = current.is_bullish and self._aplus_stack(level_hi, is_long=True)
                # Austin's A+ stack outranks candle patterns (30d: pattern grader
                # D-benched 38 of 53 stack setups) — floor B unless HTF opposed.
                # OMEN 8.0 R4: "HTF opposed" can only be the reason a D showed up
                # when HTF_GRADE_VETO is actually live -- with it at its shipped
                # default (off), grade_trade never returns D for opposition, so
                # every D here is pattern-caused regardless of htf_bias, and
                # gating this exclusion on the flag stops it silently
                # withholding a real promotion once HTF_GRADE_VETO is off.
                htf_opposed_long = omen_bot.HTF_GRADE_VETO and self.htf_bias == "bearish"
                if stack and grade.value in ("C",) + _SKIP_GRADES and not htf_opposed_long:
                    grade = TradeGrade.B
                elif (grade == TradeGrade.D and current.is_bullish
                        and not htf_opposed_long):
                    # valid confirmation entry, pattern-D only -> alert tier
                    grade = TradeGrade.C
                if stock_risk < max(0.10, 0.0015 * current.close):  # relative min (flat $0.50 benched sub-$50 stocks)
                    grade = TradeGrade.D  # T3(b): an intrabar fill sitting on the stop has no trade to size
                # OPUS-SPEC #1: displacement check on the B&R break leg —
                # tag always, cap-at-C only when the gate is enabled. Placed
                # after promotions so the A+ stack can't lift it back.
                disp = self._bnr_displacement(level_hi, is_long=True)
                if (BNR_DISPLACEMENT_GATE and not disp
                        and grade.value in ("A+", "A", "B")):
                    grade = TradeGrade.C
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
                self._emit(signals, {
                        "signal_type": SignalType.BREAK_AND_RETEST,
                        "reason": (f"B&R long — prior breakout above {hi_name} ${level_hi:.2f}, "
                                   f"retest with {grade.value} PA"
                                   + (" [late]" if "LATE" in br_note else " [clean]")
                                   + (" [wide]" if "WIDE" in br_note else "")
                                   + (" [hammer]" if hammer else "")
                                   + (" [disp]" if disp else " [nodisp]")  # OPUS-SPEC #1
                                   + self._bnr_tags(current, stock_risk, is_long=True)
                                   + f" S{sc}"),
                        "entry": entry,
                        "stop": stop,
                        "direction": "call",
                        "grade": grade.value,
                        "stop_level_name": hi_name,
                        "stop_width_pct": round(stock_risk / current.close * 100, 2),
                        "aplus_stack": stack,
                        # T10: which KIND of level this B&R is keyed to. Austin's
                        # "pivot-structure break > level break" is recorded as a
                        # rank on the signal, not applied as a silent preference.
                        "level_kind": "pivot" if hi_name in self._pivot_names else "named",
                        "level_rank": 0 if hi_name in self._pivot_names else 1,
                        # T11(a): rulebook clause 5 — no displacement, never S
                        "displacement": disp,
                    })

        # B&R long via FVG: breakout displacement left a gap above the level;
        # price retests the gap, never the raw level (Scarface: FVG = valid zone)
        if FVG_RETEST:
            fvg = find_fvg(self.candles, "bullish")
            for hi_name, _lo, level_hi, level_lo in level_pairs:
                if level_hi is None:      # T10: pivot lows are short-side only
                    continue
                if fvg is None or fvg[0] < level_hi:  # gap must sit above the broken level
                    continue
                prior_breakout = any(c.close > level_hi for c in lookback)
                already_at_level = current.low <= level_hi  # raw-level retest handles it
                # OPUS-SPEC #2: gap must be the displacement leg's gap
                if (prior_breakout and not already_at_level
                        and self._bnr_displacement(level_hi, is_long=True)
                        and current.low <= fvg[1] and current.close > fvg[1]):
                    entry = fill_price(fvg[1], current, is_long=True)  # T3(b)
                    stock_risk = entry - fvg[0]
                    grade = PriceActionAnalyzer.grade_trade(current, lookback, fvg[1], fvg[0],
                                                            is_long=True, htf_bias=self.htf_bias)
                    if stock_risk < 0.50:
                        grade = TradeGrade.D
                    self._emit(signals, {
                            "signal_type": SignalType.FAIR_VALUE_GAP,
                            "reason": f"B&R long — FVG retest ${fvg[0]:.2f}-${fvg[1]:.2f} above {hi_name} ${level_hi:.2f}, {grade.value} PA",
                            "entry": entry,
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
            entry = fill_price(block.high, current, is_long=True)  # T3(b)
            stock_risk = entry - block.low
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
            self._emit(signals, {
                    "signal_type": SignalType.ONE_CANDLE_RULE,
                    "reason": f"Order block long — block ${block.low:.2f}-${block.high:.2f} (at {block.timestamp}), {retest} retest, {grade.value} PA",
                    "entry": entry,
                    "stop": block.low,
                    "direction": "call",
                    "grade": grade.value,
                    "stop_level_name": "Order block low",
                    "stop_width_pct": round(stock_risk / current.close * 100, 2),
                })

        # Flag long (Austin 2026-08-08): pole up -> tight pause -> breakout up.
        # T5: was routed as ONE_CANDLE_RULE, which made per-setup win rates for
        # the flag AND the order block untruthful. Own type now. Dormant
        # (FLAG_ENABLED False), so this is a label fix, not a behaviour change.
        flag, fnote = detect_flag_setup(self.candles, "bullish") if FLAG_ENABLED else (None, "")
        if flag is not None and current.close > flag["flag_lo"] and _volume_ok(self.candles):
            entry = fill_price(flag["flag_hi"], current, is_long=True)  # T3(b)
            stock_risk = entry - flag["flag_lo"]
            grade = PriceActionAnalyzer.grade_trade(current, lookback, flag["flag_hi"], flag["flag_lo"],
                                                    is_long=True, htf_bias=self.htf_bias)
            if stock_risk < 0.50:
                grade = TradeGrade.D
            self._emit(signals, {
                    "signal_type": SignalType.FLAG,
                    "reason": f"Flag long — {fnote}, breakout ${flag['flag_hi']:.2f}, {grade.value} PA",
                    "entry": entry,
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
            # T3(d): 2 attempts on ONE idea total (original + a single re-entry,
            # "2 is usual") and the reclaim must itself land before 11:00.
            key_84 = ("call", round(self.session.entry_price, NO_REPEAT_LEVEL_TICK))
            attempts = self._attempts_84.get(key_84, 1)   # the original entry is attempt 1
            caps_ok = (attempts < RULE84_MAX_ATTEMPTS
                       and bar_time(current.timestamp) < SESSION_END)
            if day_range > 0 and (hod - current.close) / day_range > 0.2 and rr_ok and caps_ok:  # not too close to HOD
                stop_84 = stop_chk
                entry = fill_price(self.session.entry_price, current, is_long=True)  # T3(b)
                stock_risk = entry - stop_84
                self._attempts_84[key_84] = attempts + 1
                grade = PriceActionAnalyzer.grade_trade(current, lookback,
                                                        self.session.entry_price, self.session.entry_price,
                                                        is_long=True, htf_bias=self.htf_bias)
                # NOTE: comment "strong-PA gate already passed" is STALE — under
                # RULE84_LESSON=True the strong-PA gate is bypassed (B3 audit), so
                # this floor grants a free B to plain reclaims. GRADE_FIX drops it.
                if grade == TradeGrade.C and not GRADE_FIX:
                    grade = TradeGrade.B
                self._emit(signals, {
                        "signal_type": SignalType.REENTRY_84_RULE,
                        # [hammer] tag: sources demand strong PA on the reclaim
                        # (audit #32) — measure before gating
                        "reason": (f"84% long — prior entry ${self.session.entry_price:.2f} "
                                   f"reclaimed ({grade.value} PA)"
                                   + f" [attempt {attempts + 1}/{RULE84_MAX_ATTEMPTS}]"
                                   + (" [hammer]" if _confirm_candle(current, long=True) else "")),
                        "entry": entry,
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
            br_note = detect_break_retest(self.candles, level_lo, is_long=False, out=br_out,
                                          retest_tol_mult=_retest_tol())
            if br_note and (current.close < level_lo):
                stop = level_lo
                if BNR_STOP_MODE == "retest":
                    stop = br_out["retest_high"]
                elif BNR_STOP_MODE == "buffer":
                    recent = self.candles[-11:-1]
                    avg_rng = (sum(c.high - c.low for c in recent) / len(recent)) if recent else 0.0
                    stop = level_lo + max(0.10, 0.10 * avg_rng)
                # T3(b): close by default, intrabar at the level on an extreme close
                entry = fill_price(level_lo, current, is_long=False,
                                   session_hi=hod, session_lo=lod)
                stop = intrabar_stop(entry, stop, current, is_long=False)
                stock_risk = stop - entry
                grade = PriceActionAnalyzer.grade_trade(current, lookback, level_hi, level_lo,
                                                        is_long=False, htf_bias=self.htf_bias)
                if "LATE" in br_note and grade.value in ("A+", "A"):
                    grade = TradeGrade.B
                stack = current.is_bearish and self._aplus_stack(level_lo, is_long=False)
                # OMEN 8.0 R4: same fix as the long side above -- gate the "HTF
                # opposed" exclusion on HTF_GRADE_VETO actually being live.
                htf_opposed_short = omen_bot.HTF_GRADE_VETO and self.htf_bias == "bullish"
                if stack and grade.value in ("C",) + _SKIP_GRADES and not htf_opposed_short:
                    grade = TradeGrade.B
                elif (grade == TradeGrade.D and current.is_bearish
                        and not htf_opposed_short):
                    grade = TradeGrade.C
                if stock_risk < max(0.10, 0.0015 * current.close):
                    grade = TradeGrade.D
                # OPUS-SPEC #1: displacement tag + optional gate (see call side)
                disp = self._bnr_displacement(level_lo, is_long=False)
                if (BNR_DISPLACEMENT_GATE and not disp
                        and grade.value in ("A+", "A", "B")):
                    grade = TradeGrade.C
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
                self._emit(signals, {
                        "signal_type": SignalType.BREAK_AND_RETEST,
                        "reason": (f"B&R short — prior breakdown below {lo_name} ${level_lo:.2f}, "
                                   f"retest with {grade.value} PA"
                                   + (" [late]" if "LATE" in br_note else " [clean]")
                                   + (" [wide]" if "WIDE" in br_note else "")
                                   + (" [hammer]" if hammer else "")
                                   + (" [disp]" if disp else " [nodisp]")  # OPUS-SPEC #1
                                   + self._bnr_tags(current, stock_risk, is_long=False)
                                   + f" S{sc}"),
                        "entry": entry,
                        "stop": stop,
                        "direction": "put",
                        "grade": grade.value,
                        "stop_level_name": lo_name,
                        "stop_width_pct": round(stock_risk / current.close * 100, 2),
                        "aplus_stack": stack,
                        # T10: see the call side — pivot-keyed B&R outranks a
                        # named-level one on the same bar, recorded not applied.
                        "level_kind": "pivot" if lo_name in self._pivot_names else "named",
                        "level_rank": 0 if lo_name in self._pivot_names else 1,
                        # T11(a): rulebook clause 5 — no displacement, never S
                        "displacement": disp,
                    })

        # B&R short via FVG (mirror of the long side)
        if FVG_RETEST:
            fvg = find_fvg(self.candles, "bearish")
            for _hi, lo_name, level_hi, level_lo in level_pairs:
                if level_lo is None:      # T10: pivot highs are long-side only
                    continue
                if fvg is None or fvg[1] > level_lo:  # gap must sit below the broken level
                    continue
                prior_breakdown = any(c.close < level_lo for c in lookback)
                already_at_level = current.high >= level_lo
                # OPUS-SPEC #2: gap must be the displacement leg's gap (see call side)
                if (prior_breakdown and not already_at_level
                        and self._bnr_displacement(level_lo, is_long=False)
                        and current.high >= fvg[0] and current.close < fvg[0]):
                    entry = fill_price(fvg[0], current, is_long=False)  # T3(b)
                    stock_risk = fvg[1] - entry
                    grade = PriceActionAnalyzer.grade_trade(current, lookback, fvg[1], fvg[0],
                                                            is_long=False, htf_bias=self.htf_bias)
                    if stock_risk < 0.50:
                        grade = TradeGrade.D
                    self._emit(signals, {
                            "signal_type": SignalType.FAIR_VALUE_GAP,
                            "reason": f"B&R short — FVG retest ${fvg[0]:.2f}-${fvg[1]:.2f} below {lo_name} ${level_lo:.2f}, {grade.value} PA",
                            "entry": entry,
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
            entry = fill_price(block.low, current, is_long=False)  # T3(b)
            stock_risk = block.high - entry
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
            self._emit(signals, {
                    "signal_type": SignalType.ONE_CANDLE_RULE,
                    "reason": f"Order block short — block ${block.low:.2f}-${block.high:.2f} (at {block.timestamp}), {retest} retest, {grade.value} PA",
                    "entry": entry,
                    "stop": block.high,
                    "direction": "put",
                    "grade": grade.value,
                    "stop_level_name": "Order block high",
                    "stop_width_pct": round(stock_risk / current.close * 100, 2),
                })

        # Flag short (Austin 2026-07-08): pole down -> tight pause -> breakdown.
        flag, fnote = detect_flag_setup(self.candles, "bearish") if FLAG_ENABLED else (None, "")
        if flag is not None and current.close < flag["flag_hi"] and _volume_ok(self.candles):
            entry = fill_price(flag["flag_lo"], current, is_long=False)  # T3(b)
            stock_risk = flag["flag_hi"] - entry
            grade = PriceActionAnalyzer.grade_trade(current, lookback, flag["flag_hi"], flag["flag_lo"],
                                                    is_long=False, htf_bias=self.htf_bias)
            if stock_risk < 0.50:
                grade = TradeGrade.D
            self._emit(signals, {
                    "signal_type": SignalType.FLAG,
                    "reason": f"Flag short — {fnote}, breakdown ${flag['flag_lo']:.2f}, {grade.value} PA",
                    "entry": entry,
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
            # T3(d): mirror of the call side — 2 attempts on one idea, reclaim
            # before 11:00.
            key_84 = ("put", round(self.session.entry_price, NO_REPEAT_LEVEL_TICK))
            attempts = self._attempts_84.get(key_84, 1)
            caps_ok = (attempts < RULE84_MAX_ATTEMPTS
                       and bar_time(current.timestamp) < SESSION_END)
            if day_range > 0 and (current.close - lod) / day_range > 0.2 and rr_ok and caps_ok:
                stop_84 = stop_chk
                entry = fill_price(self.session.entry_price, current, is_long=False)  # T3(b)
                stock_risk = stop_84 - entry
                self._attempts_84[key_84] = attempts + 1
                grade = PriceActionAnalyzer.grade_trade(current, lookback,
                                                        self.session.entry_price, self.session.entry_price,
                                                        is_long=False, htf_bias=self.htf_bias)
                # stale comment / free-B floor — see call side; GRADE_FIX drops it
                if grade == TradeGrade.C and not GRADE_FIX:
                    grade = TradeGrade.B
                self._emit(signals, {
                        "signal_type": SignalType.REENTRY_84_RULE,
                        "reason": (f"84% short — prior entry ${self.session.entry_price:.2f} "
                                   f"rejected ({grade.value} PA)"
                                   + f" [attempt {attempts + 1}/{RULE84_MAX_ATTEMPTS}]"
                                   + (" [hammer]" if _confirm_candle(current, long=False) else "")),
                        "entry": entry,
                        "stop": stop_84,
                        "target": self.session.entry_target,
                        "direction": "put",
                        "grade": grade.value,
                        "stop_level_name": "Original stop" if RULE84_LESSON else "Rejection candle high",
                        "stop_width_pct": round(stock_risk / current.close * 100, 2) if current.close else 0,
                    })
                # One re-entry per failed setup (see call side)
                self.session.entry_price = None

        # C5 HTF_BIAS_GATE (default OFF): cap counter-trend signals to C /
        # alert-only so only daily-trend-aligned trades fire. daily_bias None or
        # 'neutral' => no-op. Placed last so no later promotion can lift it back.
        if HTF_BIAS_GATE and self.daily_bias in ("bullish", "bearish"):
            want = "call" if self.daily_bias == "bullish" else "put"
            for sig in signals:
                if sig.get("direction") != want and sig.get("grade") in ("A+", "A", "B"):
                    sig["grade"] = "C"
                    sig["reason"] = sig.get("reason", "") + " [htf-block]"

        # T11(d): two of the three setups on the same symbol, direction and bar
        # is CONFLUENCE — flagged and reported so we can measure whether his S
        # marks cluster there. Never required.
        for sig in signals:
            pair = sorted(self._bar_setups.get(sig.get("direction"), ()))
            if len(pair) >= 2:
                sig["confluence"] = True
                sig["confluence_pair"] = "+".join(pair)
                sig["reason"] += f" [confluence: {sig['confluence_pair']}]"
            else:
                sig.setdefault("confluence", False)

        # T10: "pivot structure break > level break". When both kinds fire on
        # the same bar and side, the named-level one is marked as outranked and
        # the list is ordered pivot-first. Nothing is dropped — the ordering is
        # recorded so T11 can read it, which is what Austin asked for.
        if PIVOT_LEVELS and any(s.get("level_kind") == "pivot" for s in signals):
            pivot_dirs = {s["direction"] for s in signals if s.get("level_kind") == "pivot"}
            for sig in signals:
                if sig.get("level_kind") == "named" and sig["direction"] in pivot_dirs:
                    sig["ranked_below_pivot"] = True
                    sig["reason"] += " [outranked: pivot B&R on this bar]"
            signals.sort(key=lambda s: s.get("level_rank", 1))

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
    parser.add_argument("--dry-run", action="store_true",
                        help="Self-check: run detect_signals on synthetic candles (no Discord, no log)")

    args = parser.parse_args()

    if args.dry_run:
        # OPUS-SPEC self-check: synthetic clean B&R day — flat range, displaced
        # break over the OR high, leave, retest, hammer confirm. Asserts the
        # detector runs clean under every OPUS-SPEC toggle combination.
        # sys.modules[__name__], NOT `import signal_runner`: run as __main__,
        # that import builds a second module copy and the toggles below would
        # land on the dead copy while detect_signals reads __main__ globals.
        import itertools
        _sr = sys.modules[__name__]
        # First 5 bars set OR high = 100.5; flats stay under it; then the FSM
        # sequence in the last 12 bars: break (displaced) -> leave -> retest ->
        # confirm close back above.
        base = [Candle(f"09:{30+i:02d}:00", 100.0, 100.5, 99.9, 100.2, 1000)
                for i in range(5)]
        base += [Candle(f"09:{35+i:02d}:00", 100.1, 100.4, 100.0, 100.2, 1000)
                 for i in range(15)]
        base += [Candle("09:50:00", 100.3, 102.0, 100.2, 101.9, 5000),   # displaced break
                 Candle("09:51:00", 101.9, 102.3, 101.7, 102.1, 2000),   # leave (low > level)
                 Candle("09:52:00", 102.1, 102.2, 101.3, 101.6, 1500),   # drift back
                 Candle("09:53:00", 101.6, 101.7, 100.4, 100.9, 1800),   # retest OR high
                 Candle("09:54:00", 101.0, 101.6, 100.8, 101.5, 1600)]   # confirm close above
        fired_baseline = None
        for gate, fvg in itertools.product((False, True), repeat=2):
            _sr.BNR_DISPLACEMENT_GATE, _sr.FVG_RETEST = gate, fvg
            r = SignalRunner(post_to_discord=False, symbol="DRYRUN", log_signals=False)
            r.candles = base
            sigs = r.detect_signals()
            assert isinstance(sigs, list), "detect_signals must return a list"
            if not gate and not fvg:
                fired_baseline = sigs
            print(f"dry-run gate={gate} fvg={fvg}: {len(sigs)} signal(s) "
                  + ", ".join(f"{s['grade']} {s['signal_type'].value}" for s in sigs))
        assert fired_baseline, "synthetic clean B&R day must fire at least one signal"
        assert any("[disp]" in s["reason"] for s in fired_baseline), \
            "displaced break must carry the [disp] tag"
        _sr.BNR_DISPLACEMENT_GATE, _sr.FVG_RETEST = False, False  # restore defaults
        print("dry-run OK")
        return

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
