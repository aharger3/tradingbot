"""T0 — every ratified default from the RATIFIED table, pinned.

`research/marks/probe_master_2026-08-29.jsonl` turned 33 of Austin's answers
into configuration truths. This file is the ledger of the ones T0 landed, as
assertions, so none of them can drift back without a red test and a quote to
argue with. Each check carries the fact key and his words.

Items T0 deliberately does NOT assert are listed at the bottom with the track
that owns them -- an unasserted item is an unlanded one, not a silent pass.

Run: python research/test_t0_ratified.py   (exit 0 = green)
"""
from __future__ import annotations
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import signal_runner as sr
import backtest_week as bw
import live_scanner as ls
import stop_rule
from research import downgrade as dg
from omen_bot import SignalType

FAIL = []


def check(cond, rid, msg):
    print(("  ok   " if cond else "  FAIL ") + rid.ljust(5) + msg)
    if not cond:
        FAIL.append(rid + " " + msg)


print("T0 — the ratified table, as configuration")

check(stop_rule.DISASTER_STOP_R == 1.0, "R1",
      'the disaster stop RESTS at -1R  ("-1r is what we want max slippage -1.25")')
check(stop_rule.MAX_LOSS_R == 1.25, "R1",
      "-1.25R is the OUTER BOUND nothing may book past -- a different number")
check(bw.DISASTER_STOP is True, "R2",
      "two stops: level stop on the close, disaster stop on touch (verdict `both`)")
check(bw.STOP_ON_CLOSE is True, "R2",
      "...and the LEVEL stop still needs a close -- wicks stop nothing")

src = open(os.path.join(ROOT, "signal_runner.py"), encoding="utf-8").read()
ocr = src.split("Order block long")[1].split("Flag long")[0]
check('grade = TradeGrade.C' not in ocr, "R3",
      'the OCR B->C demote is gone  ("Ther is no B")')
check("stock_risk < 0.50" not in ocr, "R4",
      'no flat minimum stop on OCR -- size to the stop  (verdict `none`)')

check(SignalType.FAIR_VALUE_GAP in sr.RETIRED_SETUPS
      and SignalType.FLAG in sr.RETIRED_SETUPS
      and sr.TRADE_RETIRED_SETUPS is False
      and sr.FVG_RETEST is False and sr.FLAG_ENABLED is False, "R5",
      'FVG and flag are not traded  ("FVG and flag we don\'t trade")')

check(sr.RULE84_STRICT is False, "R6",
      "the 84% arming gate is OPEN (verdict `open`)")
check(sr.RULE84_ARM_ON == frozenset(SignalType), "R6",
      "...and ANY setup that stops out arms it (verdict `any`)")

check(bw.RISK_DOLLARS == 1000.0, "R32",
      'flat $1,000 planned loss  ("That\'s how much we plan to lose not put up")')

check(not hasattr(ls, "TRADE_FLOOR"), "R12",
      'the 09:40 floor is deleted  ("Entries can happen any time in our window")')
check(ls.MANAGE_END == "16:00" and ls.ENTRY_CUTOFF == "11:00", "R13",
      "11:00 stops new ENTRIES; the live loop keeps managing runners (verdict `manage`)")
check(sr.ON_WATCH is True, "R14", "ON WATCH stays on (verdict `keep`)")

# R15 -- the collapsed-risk skip. With ENABLE_STRUCTURAL_RISK_FLOOR OFF the
# floor reads the POST-fill risk, i.e. the collapsed one, and grades the signal
# X, which _route drops. That IS "skip the trade", his answer, already shipped.
check(sr.ENABLE_STRUCTURAL_RISK_FLOOR is False
      and sr.ENABLE_MIN_RISK_FILL_CLAMP is False, "R15",
      'if risk collapses, SKIP  ("if the trade is too hard to manage it\'s not a '
      'good trade") -- both salvage flags stay off')

check(bw.DEDUPE_MODE == "level", "R16",
      'dedupe by level, not by clock  ("it doesent matter when the trade re sets up")')
import research.t4_engine_recall as t4
check(t4.DEDUPE_BARS == bw.dedupe_window(), "R16",
      "...and the recall harness reads the same window as the book")

check(sr.NO_REPEAT_ENTRIES is False, "R17", "NO_REPEAT_ENTRIES off (verdict `off`)")
check(sr.ENABLE_KILL_B_FLOOR is False and sr.ENABLE_SAC_LADDER is False, "R18",
      "arrival order is KEPT -- and it is a FLOOR, so it cannot cap an S")
check(sr.S_PLUS_PER_DAY == 0, "R20", "S_PLUS_PER_DAY deleted (verdict `delete`)")
check(sr.COUNTER_TREND_CAP is False, "R21",
      'counter-trend is an observation  ("they should not cap or stop thing from '
      'happening... good for stats")')
check(dg.ENABLE_CHASE_DOWNGRADE is True and "chase" in dir(dg), "R22",
      "chase is a downgrade variable, not a tag (verdict `downgrade`)")
check(sr.PIVOT_LEVELS is True, "R26", 'keep pivot levels  ("They can still be a")')
check(sr.LEVEL_BLOCK_CAP is False and sr.MESH_S_VETO is False, "R25",
      'a level in the 2R path is a TARGET  ("maybe we should shoot higher")')
check(sr.LEVEL_RETIRE_TOUCHES == 0, "R27",
      "LEVEL_RETIRE_TOUCHES deleted (verdict `delete`)")

# ---- landed by T23 (the 7.1 stack), not by T0 ----------------------------
import loss_halt
check(loss_halt.LOSS_HALT is True and loss_halt.HALT_AFTER_CONSECUTIVE_LOSSES == 2,
      "R31", "the two-consecutive-loss halt is ON (verdict `both`) -- "
             "backtest_2y.main() and live_scanner._tier(), see loss_halt.py")
check("import loss_halt" in open(os.path.join(ROOT, "live_scanner.py"), encoding="utf-8").read(),
      "R31b", "and it is in the LIVE path too, account-wide -- that is what `both` means")
check(sr.MIN_STOP_PCT > 0, "R30",
      'the tight-RR floor on the UNDERLYING is live  ("I meant stock price not bid ask")')
check(sr.MIN_STOP_PCT == 0.08, "R30b",
      "at 0.08% of entry price -- zero held-out S recall cost (research/t9_spread-and-tight-rr.md)")
# R4's verdict is `none`: no minimum stop distance on the one-candle rule. The
# floor above must never re-litigate it, so OCR is exempt by name in _route.
check("SignalType.ONE_CANDLE_RULE" in
      open(os.path.join(ROOT, "signal_runner.py"), encoding="utf-8").read()
      .split("MIN_STOP_PCT > 0")[1][:400],
      "R4+R30", "and the one-candle rule is EXEMPT from it (R4 verdict `none`)")
check(sr.RETIRED_SETUPS and sr.TRADE_RETIRED_SETUPS is False, "R33",
      "FVG/flag confirmed corpus-absent and kept as retired code "
      "(research/t19_fvg-flag-verdict.md) -- R33 says KEEP, so it was not deleted")

print("""
NOT asserted here, and why -- each is a measurement track, not a config flip:
  R7  index quota            -> T4      R8  symbol balance        -> T15
  R9  level target first     -> T5      R10 runner sizing         -> T5
  R11 BE on movement         -> T11     R19 candles beyond hammer -> T13
  R24 sweep the 0.5%         -> T16     R28 real contracts        -> T7
  R29 strikes / futures      -> T8,T17
LANDED BY T23 and asserted above: R30, R31, R33.
""")
print("%d failed" % len(FAIL))
sys.exit(1 if FAIL else 0)
