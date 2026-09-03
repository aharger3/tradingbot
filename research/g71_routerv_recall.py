"""Adversarial re-measure of track `router`'s recall claim.

Independent path: instead of re-implementing the scorer, call the PUBLISHED
rig function research/t0_heldout_recall.py::score_sweep() twice --
unpatched (hand-rolled CaptureRunner._route as shipped) and with
CaptureRunner._route replaced by a delegating version identical in shape to
backtest_week.BacktestRunner._route. Nothing on disk is edited; marks are
read-only.
"""
import os, sys, json, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import research.t4_engine_recall as t4
import research.t0_heldout_recall as t0
import signal_runner as sr
from signal_runner import TradeGrade

ORIG = t4.CaptureRunner._route

def deleg(self, signals, sig):
    before = len(signals)
    sr.SignalRunner._route(self, signals, sig)
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
    elif "[skip: stop under" in sig.get("reason", ""):
        sig["status"] = "skipped_min_stop_pct"
    else:
        sig["status"] = "skipped_tight_stop"
    self.captured.append(sig)

res = {}
t0_ = time.time(); t4.CaptureRunner._route = ORIG
res["hand_rolled"] = t0.score_sweep(); print("hand %.0fs" % (time.time()-t0_))
t0_ = time.time(); t4.CaptureRunner._route = deleg
res["delegating"] = t0.score_sweep(); print("deleg %.0fs" % (time.time()-t0_))
t4.CaptureRunner._route = ORIG

# MIN_STOP_PCT=0 control on the delegating arm: is the single flip the floor?
sr.MIN_STOP_PCT = 0.0
t4.CaptureRunner._route = deleg
res["delegating_minstop0"] = t0.score_sweep()
t4.CaptureRunner._route = ORIG; sr.MIN_STOP_PCT = 0.08

json.dump(res, open(os.path.join(HERE, "g71_routerv_recall.json"), "w"), indent=2)
for k, v in res.items():
    print(k, v["fired_on_S"], "/", v["n_S"], "=", v["recall_pct"], "| prec",
          v["precision_pct"], "| fp", v["fired_on_no"], "| err", v["unreplayable_days"])
print("missed delta:", sorted(set(res["delegating"]["missed_S"]) - set(res["hand_rolled"]["missed_S"])))
