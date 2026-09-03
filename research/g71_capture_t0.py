"""G7.1 adversarial verify: does CaptureRunner._route not calling super() move
the GOVERNING held-out recall number (research/t0_heldout_recall)?

NOTE the trap this script exists to avoid: `research/t4_engine_recall` is
importable under TWO names -- `t4_engine_recall` (research/ on sys.path, how
regression_gate imports it) and `research.t4_engine_recall` (how
t0_heldout_recall imports it). They are DISTINCT module objects with distinct
CaptureRunner classes. Patching one and measuring the other silently reports
"no change". Both are patched here.
"""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import t4_engine_recall as t4_flat
from research import t4_engine_recall as t4_pkg
from research import t0_heldout_recall as t0
from g71_capture_ab import delegating_route

MODS = [t4_flat, t4_pkg]
assert t4_flat is not t4_pkg, "expected two module objects"


def set_route(fn):
    for m in MODS:
        m.CaptureRunner._route = fn


def snap():
    return {"sweep": t0.score_sweep(), "vetoes": t0.score_vetoes()}


def main():
    stock = t4_pkg.CaptureRunner._route
    a = snap()
    set_route(delegating_route)
    b = snap()
    set_route(stock)
    for arm, d in (("hand-rolled", a), ("delegating ", b)):
        s, v = d["sweep"], d["vetoes"]
        print(f"{arm}  sweep: fired_on_S {s['fired_on_S']}/{s['n_S']} "
              f"= {s['recall_pct']}%  precision {s['precision_pct']}%  "
              f"fired_on_no {s['fired_on_no']}/{s['n_no']}")
        print(f"{arm}  vetoes: S {v['fired_on_his_S']}/{v['his_S']}  "
              f"A {v['fired_on_his_A']}/{v['his_A']}  no {v['fired_on_his_no']}/{v['his_no']}")
    ms_a, ms_b = set(a["sweep"]["missed_S"]), set(b["sweep"]["missed_S"])
    print("S cards firing ONLY on the hand-rolled router:", sorted(ms_b - ms_a))
    print("S cards firing ONLY on the delegating router:", sorted(ms_a - ms_b))
    json.dump({"handrolled": a, "delegating": b},
              open(os.path.join(HERE, "g71_capture_t0.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
