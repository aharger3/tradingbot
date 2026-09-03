#!/usr/bin/env python3
"""OMEN 8.0 R5 checks. Plain asserts, no pytest:  python3 test_live_tier_s_gate.py

`live_scanner._tier` decides whether a live signal is TRADE (sized, paper-booked,
counted against the daily governor) or WATCH (a Discord ding and nothing else).
Until omen-8.0 R5 its classification clause read `grade not in ("A+", "A")` --
`PriceActionAnalyzer.grade_trade`'s A+/A/B/C/D candle-shape ladder, the RETIRED
scheme. Austin's settled trading set is `S only` (Projects/omen-blockers.md,
"Already settled -- do not re-ask", 2026-08-24) on the S/A/C tier
`signal_runner.compute_austin_tier` computes. The two are different
classifications of different things and `signal_runner` says outright that no
mapping between them exists.

This file asserts the live promotion rule IS expressed in S/A/C terms:

 1. `_tier` takes no `grade` argument and its body never reads one -- checked
    structurally against the AST, so a future edit that re-introduces the ladder
    fails here rather than silently shipping.
 2. austin_tier "S", post-floor, first of the day, no loss halt -> TRADE.
 3. austin_tier "A" or "C" -> WATCH **even when the engine grade is "A+"**.
    This is the case whose behaviour actually changed: under the old gate an
    A+/A ladder grade promoted regardless of Austin's tier, and over the
    committed two-year archive 25 of the old gate's 34 non-re-entry promotions
    were tier A or C (research/g94_live_tier.md).
 4. A missing or None austin_tier fails CLOSED (WATCH), so a signal from any
    other producer -- or `AUSTIN_TIER_ENABLED = False` -- can never promote.
 5. The operational safeguards carried across the migration still bite:
    TRADE_FLOOR (09:40), first-of-day (`signals_today == 0`), and the two-loss
    session halt.
 6. The 84% re-entry exemption is unchanged: it promotes while
    consecutive_losses < 2 regardless of tier, time of day or the daily
    governor, and stops promoting at two losses.
 7. `_emit_signal` actually calls `_tier` with the new three-argument
    signature, so this gate is the one the live path uses.
"""
import ast
import inspect
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import live_scanner as ls
from omen_bot import TradingSession

FAILS = []


def check(cond, label):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


class _Type:
    """Stand-in for SignalType: `_tier` only ever reads `.value`."""

    def __init__(self, value):
        self.value = value


class _Runner:
    def __init__(self, signals_today=0, consecutive_losses=0):
        self.session = TradingSession()
        self.session.signals_today = signals_today
        self.session.consecutive_losses = consecutive_losses


def sig(tier="S", setup="break_and_retest", grade="B", **extra):
    d = {"signal_type": _Type(setup), "grade": grade,
         "direction": "call", "entry": 100.0, "stop": 99.0}
    if tier is not ...:
        d["austin_tier"] = tier
    d.update(extra)
    return d


AFTER = "09:45:00"    # past TRADE_FLOOR
BEFORE = "09:35:00"   # inside the 09:30-09:40 chop the floor exists to skip


# ---------------------------------------------------------------------------
# 1. the rule is expressed in S/A/C terms, structurally
# ---------------------------------------------------------------------------

src = inspect.getsource(ls._tier)
tree = ast.parse(src.lstrip())
fn = tree.body[0]

params = [a.arg for a in fn.args.args]
check("grade" not in params,
      f"(1a) _tier takes no `grade` parameter (signature: {params})")

body = list(fn.body)
if body and isinstance(body[0], ast.Expr) and isinstance(
        getattr(body[0], "value", None), ast.Constant) and isinstance(
        body[0].value.value, str):
    body = body[1:]          # drop the docstring; prose may name the old ladder

names, consts = set(), set()
for stmt in body:
    for node in ast.walk(stmt):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            consts.add(node.value)

check("grade" not in names and "grade" not in consts,
      "(1b) _tier's executable body never reads the engine grade")
check("austin_tier" in consts,
      "(1c) _tier's executable body reads sig['austin_tier']")
check(not ({"A+", "B", "D", "X"} & consts),
      f"(1d) no A+/A/B/C/D ladder letters left in _tier's body (found {sorted(consts)})")


# ---------------------------------------------------------------------------
# 2-3. what promotes, and the case that actually changed
# ---------------------------------------------------------------------------

check(ls._tier(_Runner(), sig(tier="S"), AFTER) == "TRADE",
      "(2) austin_tier S, post-floor, first of day, no losses -> TRADE")

check(ls._tier(_Runner(), sig(tier="A", grade="A+"), AFTER) == "WATCH",
      "(3a) austin_tier A does NOT promote even at engine grade A+")
check(ls._tier(_Runner(), sig(tier="C", grade="A+"), AFTER) == "WATCH",
      "(3b) austin_tier C does NOT promote even at engine grade A+")
check(ls._tier(_Runner(), sig(tier="A", grade="A"), AFTER) == "WATCH",
      "(3c) austin_tier A does NOT promote at engine grade A")
check(ls._tier(_Runner(), sig(tier="S", grade="C"), AFTER) == "TRADE",
      "(3d) austin_tier S DOES promote at engine grade C -- the tier is the gate")
check(ls._tier(_Runner(), sig(tier="S", grade="B"), AFTER) == "TRADE",
      "(3e) austin_tier S DOES promote at engine grade B")
check(ls._tier(_Runner(), sig(tier="S", setup="one_candle_rule"), AFTER) == "TRADE",
      "(3f) the S gate is setup-agnostic (one_candle_rule promotes too)")


# ---------------------------------------------------------------------------
# 4. fail-closed on a missing / disabled tier
# ---------------------------------------------------------------------------

check(ls._tier(_Runner(), sig(tier=..., grade="A+"), AFTER) == "WATCH",
      "(4a) a sig with NO austin_tier key never promotes (fail-closed)")
check(ls._tier(_Runner(), sig(tier=None, grade="A+"), AFTER) == "WATCH",
      "(4b) austin_tier None (AUSTIN_TIER_ENABLED off) never promotes")
check(ls._tier(_Runner(), sig(tier="S+"), AFTER) == "WATCH",
      "(4c) 'S+' is a rank inside S, not a tier value -- it does not promote "
      "(rank_s_plus writes s_rank, never austin_tier)")


# ---------------------------------------------------------------------------
# 5. the operational safeguards carried across, unchanged
# ---------------------------------------------------------------------------

check(ls.TRADE_FLOOR == "09:40", "(5a) TRADE_FLOOR is still 09:40")
check(ls._tier(_Runner(), sig(tier="S"), BEFORE) == "WATCH",
      "(5b) an S before TRADE_FLOOR does not promote")
check(ls._tier(_Runner(), sig(tier="S"), "09:40:00") == "TRADE",
      "(5c) the floor is inclusive: 09:40 exactly promotes")
check(ls._tier(_Runner(signals_today=1), sig(tier="S"), AFTER) == "WATCH",
      "(5d) one trade and done: a second S the same day does not promote")
check(ls._tier(_Runner(consecutive_losses=2), sig(tier="S"), AFTER) == "WATCH",
      "(5e) two consecutive losses halt promotion")
check(ls._tier(_Runner(consecutive_losses=1), sig(tier="S"), AFTER) == "TRADE",
      "(5f) one loss does not halt promotion")


# ---------------------------------------------------------------------------
# 6. the 84% re-entry exemption, deliberately unchanged by R5
# ---------------------------------------------------------------------------

RE = "reentry_84_rule"
check(ls._tier(_Runner(), sig(tier="S", setup=RE), AFTER) == "TRADE",
      "(6a) an armed 84% re-entry promotes")
check(ls._tier(_Runner(signals_today=2), sig(tier="A", setup=RE), BEFORE) == "TRADE",
      "(6b) the 84% re-entry is exempt from the tier, the floor and the daily "
      "governor -- it is the sanctioned second bite at an idea already taken")
check(ls._tier(_Runner(consecutive_losses=2), sig(tier="S", setup=RE), AFTER) == "WATCH",
      "(6c) the 84% re-entry still stops at two consecutive losses")


# ---------------------------------------------------------------------------
# 7. this gate is the one the live path actually uses
# ---------------------------------------------------------------------------

emit_src = inspect.getsource(ls._emit_signal)
check("_tier(runner, sig, candle.timestamp)" in emit_src,
      "(7a) _emit_signal calls _tier(runner, sig, candle.timestamp)")
check("alert_only = tier != \"TRADE\"" in emit_src,
      "(7b) _emit_signal turns a non-TRADE tier into alert_only")
check(len(inspect.signature(ls._tier).parameters) == 3,
      "(7c) _tier's arity is 3 -- the grade argument is gone from the call site too")

print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")
