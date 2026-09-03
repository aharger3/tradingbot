"""g71 router track: does the governing recall metric MOVE when the capture
router is replaced by the live one? Runs t0_heldout_recall and regression_gate
under both arms in-process."""
from __future__ import annotations
import os, sys, json, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import signal_runner as sr, t4_engine_recall as t4
import t0_heldout_recall as t0
import regression_gate as rg

ORIG = t4.CaptureRunner._route
def delegating(self, signals, sig):
    before = len(signals)
    sr.SignalRunner._route(self, signals, sig)
    sig["status"] = "fired" if len(signals) > before else "skipped"
    self.captured.append(sig)

def run_arm(name):
    sweep = t0.score_sweep()
    vet = t0.score_vetoes()
    marks = rg.load_marks()
    anysig, sgrade, fired_all, by_tier = rg.current_sets(marks)
    return {"arm": name,
            "sweep_recall_pct": sweep["recall_pct"],
            "sweep_fired_on_S": sweep["fired_on_S"],
            "sweep_fired_on_no": sweep["fired_on_no"],
            "sweep_precision_pct": sweep["precision_pct"],
            "sweep_missed_S": sweep["missed_S"],
            "vetoes": {k: v for k, v in sorted(vet.items()) if k != "detail"},
            "gate_any_signal": len(anysig), "gate_s_grade": len(sgrade),
            "gate_fired_all": len(fired_all),
            "gate_s_keys": sorted(sgrade)}

t4.CaptureRunner._route = ORIG
A = run_arm("A_capture_hand_rolled")
t4.CaptureRunner._route = delegating
B = run_arm("B_delegates_to_live_route")
t4.CaptureRunner._route = ORIG

for r in (A, B):
    print(json.dumps({k: v for k, v in r.items() if k not in ("gate_s_keys",)}, default=str))
print("\nS-recall key set identical:", A["gate_s_keys"] == B["gate_s_keys"])
print("dropped by delegating:", sorted(set(A["gate_s_keys"]) - set(B["gate_s_keys"])))
print("added by delegating:", sorted(set(B["gate_s_keys"]) - set(A["gate_s_keys"])))
