#!/usr/bin/env python3
"""OMEN 9.0 L5: the live options sizing branch keys off HIS ladder, not the
retired A+/A/B/C/X engine grade.  Plain asserts, no pytest:
    python research/test_s_flat_sizing.py

Before this fix `live_scanner._emit_signal` sized every live card off
`GRADE_SIZE_PCT[sig["grade"]]` -- the legacy engine letter -- and
`signal_runner.SAC_TIER` maps BOTH his "S" and his "A" onto that same engine
letter "A" (0.8). A true S promotion therefore risked 80% of RISK_DOLLARS
($800), never the full $1,000 1R Austin asked for (2026-09-03: "1R is
simpler so why not go with that?"). A and C never reach TRADE (`_tier`
already gates on `sac_grade == "S"`), so this test also pins that their
sizing budget is exactly zero -- they carry no real risk on a live card.

Asserted:
 1. sac_grade "S" sizes the card at max_loss == DEFAULT_MAX_LOSS (RISK_DOLLARS)
    -- exactly 1R -- regardless of what the legacy engine `grade` says (A, B,
    or C all size the same once `sac_grade` is S).
 2. sac_grade "A" or "C" sizes the card at max_loss == 0 -- no live budget --
    even at the old top engine grade "A".
 3. the 84% re-entry exemption is unchanged: it still risks full size (2x),
    regardless of grade or sac_grade, same as before this fix.
 4. `GRADE_SIZE_PCT` is no longer read anywhere in `_emit_signal`'s body (the
    branch was deleted, not just bypassed) -- checked structurally so a
    future edit cannot quietly reintroduce the old ladder here. The constant
    itself still exists in `options_sizer` (kept, per the row) for the
    futures path, which this row does not touch.
"""
import ast
import inspect
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import live_scanner as ls
import options_sizer
from omen_bot import TradingSession

FAILS = []


def check(cond, label):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


class _Type:
    def __init__(self, value):
        self.value = value


class _Candle:
    def __init__(self, ts="09:45:00"):
        self.timestamp = ts


class _Runner:
    def __init__(self):
        self.session = TradingSession()
        self.futures_mode = False
        self.post_to_discord = False
        self.discord = None


class _FakePlan:
    def __init__(self, max_loss):
        self.max_loss = max_loss
        self.contracts = 1 if max_loss > 0 else 0
        self.stock_target = 0.0
        self.quote_source = "estimated_delta"

    def format_discord(self):
        return ""


def sig(sac, grade, setup="break_and_retest"):
    return {
        "signal_type": _Type(setup),
        "grade": grade,
        "sac_grade": sac,
        "austin_tier": sac,
        "direction": "call",
        "entry": 100.0,
        "stop": 99.0,
        "reason": "test",
        "stop_level_name": "test level",
        "stop_width_pct": 0.1,
    }


def _emit_and_capture(s, symbol="TSLA", ts="09:45:00"):
    """Run `_emit_signal` with every side effect stubbed; return the
    `max_loss` it handed to `build_options_plan`."""
    captured = {}

    def fake_build_options_plan(**kw):
        captured["max_loss"] = kw["max_loss"]
        return _FakePlan(kw["max_loss"])

    orig_build = options_sizer.build_options_plan
    orig_log = ls.log_signal
    orig_push = ls.notify_ntfy.push
    options_sizer.build_options_plan = fake_build_options_plan
    ls.log_signal = lambda **kw: None
    ls.notify_ntfy.push = lambda *a, **k: True
    ls._last_alert.clear()
    ls._s_trades_today.clear()
    ls._watch_dings["n"] = 0
    ls._session_push["pushed"] = False
    ls._session_push["push_rec"] = None
    ls._session_push["veto_first"] = None
    ls._session_push["trades"] = []
    try:
        ls._emit_signal(_Runner(), None, symbol, _Candle(ts), s, paper=None)
    finally:
        options_sizer.build_options_plan = orig_build
        ls.log_signal = orig_log
        ls.notify_ntfy.push = orig_push
    return captured["max_loss"]


# ---------------------------------------------------------------------------
# 1. sac_grade S -> exactly RISK_DOLLARS, whatever the engine grade
# ---------------------------------------------------------------------------

for engine_grade in ("A", "B", "C"):
    ml = _emit_and_capture(sig("S", engine_grade), symbol="TSLA")
    check(ml == options_sizer.DEFAULT_MAX_LOSS,
          f"(1) sac_grade S sizes ${options_sizer.DEFAULT_MAX_LOSS:.0f} "
          f"at engine grade {engine_grade} (got ${ml:.0f})")

# ---------------------------------------------------------------------------
# 2. sac_grade A / C -> zero live budget, even at engine grade A
# ---------------------------------------------------------------------------

for sac_grade in ("A", "C"):
    ml = _emit_and_capture(sig(sac_grade, "A"), symbol="NVDA")
    check(ml == 0.0, f"(2) sac_grade {sac_grade} sizes $0 live budget (got ${ml:.0f})")

# ---------------------------------------------------------------------------
# 3. the 84% re-entry exemption -- unchanged, still full-size x2
# ---------------------------------------------------------------------------

ml = _emit_and_capture(sig("A", "C", setup="reentry_84_rule"), symbol="AAPL")
check(ml == 2 * options_sizer.DEFAULT_MAX_LOSS,
      f"(3) an armed 84% re-entry still risks 2x full size regardless of "
      f"grade/sac_grade (got ${ml:.0f}, want ${2 * options_sizer.DEFAULT_MAX_LOSS:.0f})")

# ---------------------------------------------------------------------------
# 4. GRADE_SIZE_PCT is gone from _emit_signal's body (branch deleted, not
#    bypassed); the constant survives in options_sizer for the futures path.
# ---------------------------------------------------------------------------

src = inspect.getsource(ls._emit_signal)
fn = ast.parse(src.lstrip()).body[0]
names = set()
for stmt in fn.body:
    for node in ast.walk(stmt):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
check("GRADE_SIZE_PCT" not in names,
      "(4a) _emit_signal's executable body never reads GRADE_SIZE_PCT "
      "(comments may still name it)")
check(hasattr(options_sizer, "GRADE_SIZE_PCT"),
      "(4b) GRADE_SIZE_PCT still exists in options_sizer (kept, per the row)")

print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    if __name__ == "__main__":
        sys.exit(1)
print("all checks passed")
