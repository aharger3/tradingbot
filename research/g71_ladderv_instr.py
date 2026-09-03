"""Adversarial instrumentation: stamp the RAW _grade_trade verdict onto every
emitted signal so the book records what `_grade_pa` actually said BEFORE the
untagged emission-site rewrites (LATE cap, A+ stack floor sr:2768/:3052,
D->C bump, min-risk D, displacement gate).  Read-only w.r.t. shared files;
writes only its own --out.  Tag is additive, so routing is unchanged."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import signal_runner as sr

_orig_gt = sr.SignalRunner._grade_trade
_orig_emit = sr.SignalRunner._emit

def gt(self, *a, **k):
    g = _orig_gt(self, *a, **k)
    self._pa_raw_stash = getattr(g, "value", g)
    self._pa_raw_seq = getattr(self, "_pa_raw_seq", 0) + 1
    return g

def emit(self, signals, sig):
    seq = getattr(self, "_pa_raw_seq", 0)
    used = getattr(self, "_pa_raw_used", -1)
    raw = getattr(self, "_pa_raw_stash", None) if seq != used else None
    self._pa_raw_used = seq
    sig["reason"] = (sig.get("reason") or "") + " {{pa=%s|stk=%s}}" % (
        raw, 1 if sig.get("aplus_stack") else 0)
    return _orig_emit(self, signals, sig)

sr.SignalRunner._grade_trade = gt
sr.SignalRunner._emit = emit

out = os.path.join("research", "g71_ladderv_instr_book.json")
assert not out.endswith("bt2y_trades.json")
import backtest_2y
sys.argv = ["backtest_2y.py", "--days", "730", "--out", out]
backtest_2y.main()
