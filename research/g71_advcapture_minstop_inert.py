"""G7.1 adversarial verify: is MIN_STOP_PCT INERT in the rig that produced the
'costs zero held-out S recall (18/34 before and after)' claim at
signal_runner.py:2582? Score the 34 blind S cards four ways."""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import signal_runner as sr
import t4_engine_recall as t4
from g71_capture_route_ab import DelegatingCaptureRunner

SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
cards = [json.loads(l) for l in open(SWEEP, encoding="utf-8") if l.strip()]
cards = [r for r in cards if r["answers"].get("s")]
S = [r for r in cards if r["answers"]["s"] == ["s"]]
NO = [r for r in cards if r["answers"]["s"] != ["s"]]

def score(tag):
    fired = {}
    for sym, day in sorted({(r["symbol"], r["date"]) for r in cards}):
        try:
            ent, _s, _r = t4.run_day(sym, day)
        except Exception:
            ent = None
        fired[(sym, day)] = bool(ent)
    tp = [r["card_id"] for r in S if fired[(r["symbol"], r["date"])]]
    fp = [r["card_id"] for r in NO if fired[(r["symbol"], r["date"])]]
    print(f"{tag:<46} S recall {len(tp)}/{len(S)} = {len(tp)/len(S)*100:.1f}%"
          f"   false fires {len(fp)}/{len(NO)}")
    return set(tp)

inc = t4.CaptureRunner
a1 = score("A incumbent, MIN_STOP_PCT=0.08 (shipped)")
sr.MIN_STOP_PCT = 0.0
a2 = score("A incumbent, MIN_STOP_PCT=0")
sr.MIN_STOP_PCT = 0.15
a3 = score("A incumbent, MIN_STOP_PCT=0.15")
sr.MIN_STOP_PCT = 0.08

t4.CaptureRunner = DelegatingCaptureRunner
try:
    b1 = score("B delegating, MIN_STOP_PCT=0.08 (shipped)")
    sr.MIN_STOP_PCT = 0.0
    b2 = score("B delegating, MIN_STOP_PCT=0")
    sr.MIN_STOP_PCT = 0.15
    b3 = score("B delegating, MIN_STOP_PCT=0.15")
    sr.MIN_STOP_PCT = 0.08
finally:
    t4.CaptureRunner = inc

print("\nA arm moves with the threshold:", "NO -- inert" if a1 == a2 == a3 else "yes")
print("B arm 0.08 vs 0   diff:", sorted(b2 - b1) or "none")
print("B arm 0.15 vs 0   diff:", sorted(b2 - b3) or "none")
