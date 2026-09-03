#!/usr/bin/env python3
"""Live promotion gate checks. Plain asserts, no pytest:  python test_live_tier_s_gate.py

Adapted from the cloud branch's OMEN 8.0 R5 file. R5's thesis -- the live
TRADE/WATCH gate must be expressed in Austin's S/A/C terms, not the retired
A+/A/B/C/D candle ladder -- had already landed on this history in 471e48c9
(2026-08-30), where the gate reads `sig["sac_grade"]` because SAC_TIER now
writes both his S and his A to the engine's top letter `A`, so `grade` alone
can no longer tell them apart.

What did NOT survive the adaptation, and why: the cloud file also asserted
`TRADE_FLOOR == "09:40"`, that a pre-09:40 S cannot promote, and "one trade and
done" (`signals_today == 0`). All three were ratified away here afterwards --
R12 DELETED TRADE_FLOOR on Austin's own words ("Entries can happen any time in
our window"), and GOVERNOR_S_CAP replaced the across-all-symbols first-of-day
rule with a per-symbol cap that is uncapped by default. Those checks are
replaced below by ones pinning the CURRENT rules, so this file cannot quietly
re-impose a floor the trader removed.

Asserted:
 1. The gate is expressed in S/A/C terms -- checked structurally against the
    AST, so a future edit re-introducing the engine ladder fails here.
 2. sac_grade "S", no loss halt, under the governor -> TRADE.
 3. sac_grade "A" or "C" -> WATCH **even at engine grade A+**.
 4. A missing or None sac_grade fails CLOSED (WATCH).
 5. R12: there is no time floor -- an S at 09:31 promotes.
 6. The safeguards that DO bite: the session two-loss halt, the account-wide
    R31 halt, and GOVERNOR_S_CAP when it is set.
 7. The 84% re-entry exemption is unchanged.
 8. `_emit_signal` calls this gate, at this signature.
"""
import ast
import inspect
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import live_scanner as ls
import loss_halt
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
    def __init__(self, consecutive_losses=0):
        self.session = TradingSession()
        self.session.consecutive_losses = consecutive_losses


def sig(sac="S", setup="break_and_retest", grade="B", **extra):
    d = {"signal_type": _Type(setup), "grade": grade,
         "direction": "call", "entry": 100.0, "stop": 99.0}
    if sac is not ...:
        d["sac_grade"] = sac
    d.update(extra)
    return d


def tier(runner, s, grade=None, ts="09:45:00", symbol="TSLA"):
    return ls._tier(runner, s, grade if grade is not None else s.get("grade"), ts, symbol)


def _reset():
    ls._s_trades_today.clear()
    ls._account_streak["n"] = 0


_reset()

# ---------------------------------------------------------------------------
# 1. the rule is expressed in S/A/C terms, structurally
# ---------------------------------------------------------------------------

src = inspect.getsource(ls._tier)
fn = ast.parse(src.lstrip()).body[0]

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
      "(1a) _tier's executable body never reads the engine grade")
check("sac_grade" in consts,
      "(1b) _tier's executable body reads sig['sac_grade']")
check(not ({"A+", "B", "D", "X"} & consts),
      f"(1c) no engine-ladder letters left in _tier's body (found {sorted(consts)})")

# ---------------------------------------------------------------------------
# 2-3. what promotes, and the case R5 was about
# ---------------------------------------------------------------------------

check(tier(_Runner(), sig(sac="S")) == "TRADE",
      "(2) sac_grade S, no halt, under the governor -> TRADE")

_reset()
check(tier(_Runner(), sig(sac="A", grade="A+")) == "WATCH",
      "(3a) sac_grade A does NOT promote even at engine grade A+")
check(tier(_Runner(), sig(sac="C", grade="A+")) == "WATCH",
      "(3b) sac_grade C does NOT promote even at engine grade A+")
check(tier(_Runner(), sig(sac="S", grade="C")) == "TRADE",
      "(3c) sac_grade S DOES promote at engine grade C -- the tier is the gate")
check(tier(_Runner(), sig(sac="S", setup="one_candle_rule")) == "TRADE",
      "(3d) the S gate is setup-agnostic (one_candle_rule promotes too)")

# ---------------------------------------------------------------------------
# 4. fail-closed on a missing / disabled tier
# ---------------------------------------------------------------------------

_reset()
check(tier(_Runner(), sig(sac=..., grade="A+")) == "WATCH",
      "(4a) a sig with NO sac_grade key never promotes (fail-closed)")
check(tier(_Runner(), sig(sac=None, grade="A+")) == "WATCH",
      "(4b) sac_grade None (the ladder disabled) never promotes")
check(tier(_Runner(), sig(sac="S+")) == "WATCH",
      "(4c) 'S+' is a rank inside S, not a ladder letter -- it does not promote")

# ---------------------------------------------------------------------------
# 5. R12: no time floor. The whole session window trades.
# ---------------------------------------------------------------------------

_reset()
check(not hasattr(ls, "TRADE_FLOOR"),
      "(5a) TRADE_FLOOR is gone (R12: 'entries can happen any time in our window')")
check(tier(_Runner(), sig(sac="S"), ts="09:31:00") == "TRADE",
      "(5b) an S at 09:31 promotes -- there is no 09:40 floor any more")

# ---------------------------------------------------------------------------
# 6. the safeguards that DO bite
# ---------------------------------------------------------------------------

_reset()
check(tier(_Runner(consecutive_losses=2), sig(sac="S")) == "WATCH",
      "(6a) two consecutive session losses halt promotion")
check(tier(_Runner(consecutive_losses=1), sig(sac="S")) == "TRADE",
      "(6b) one loss does not halt promotion")

_reset()
ls._account_streak["n"] = loss_halt.HALT_AFTER_CONSECUTIVE_LOSSES
check(tier(_Runner(), sig(sac="S")) == ("WATCH" if loss_halt.LOSS_HALT else "TRADE"),
      "(6c) R31: the account-wide streak halts promotion when loss_halt is on")
_reset()

check(ls.GOVERNOR_S_CAP is None,
      "(6d) GOVERNOR_S_CAP is uncapped by default (his cap number is unresolved)")
_saved_cap, ls.GOVERNOR_S_CAP = ls.GOVERNOR_S_CAP, 1
try:
    ls._s_trades_today["TSLA"] = 1
    check(tier(_Runner(), sig(sac="S"), symbol="TSLA") == "WATCH",
          "(6e) GOVERNOR_S_CAP=1 blocks a second S on the SAME symbol")
    check(tier(_Runner(), sig(sac="S"), symbol="NVDA") == "TRADE",
          "(6f) the cap is PER SYMBOL -- a different symbol still promotes")
finally:
    ls.GOVERNOR_S_CAP = _saved_cap
    _reset()

# ---------------------------------------------------------------------------
# 7. the 84% re-entry exemption, unchanged
# ---------------------------------------------------------------------------

RE = "reentry_84_rule"
check(tier(_Runner(), sig(sac="S", setup=RE)) == "TRADE",
      "(7a) an armed 84% re-entry promotes")
check(tier(_Runner(), sig(sac="A", setup=RE), ts="09:31:00") == "TRADE",
      "(7b) the 84% re-entry is exempt from the ladder letter and the governor")
check(tier(_Runner(consecutive_losses=2), sig(sac="S", setup=RE)) == "WATCH",
      "(7c) the 84% re-entry still stops at two consecutive losses")

# ---------------------------------------------------------------------------
# 8. this gate is the one the live path actually uses
# ---------------------------------------------------------------------------

emit_src = inspect.getsource(ls._emit_signal)
check("_tier(runner, sig, grade, candle.timestamp, symbol)" in emit_src,
      "(8a) _emit_signal calls _tier(runner, sig, grade, candle.timestamp, symbol)")
check('alert_only = tier != "TRADE"' in emit_src,
      "(8b) _emit_signal turns a non-TRADE tier into alert_only")
check(len(inspect.signature(ls._tier).parameters) == 5,
      "(8c) _tier's arity is 5 on this history (runner, sig, grade, ts, symbol)")

print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")
