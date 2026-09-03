"""G7.1 adversarial verify of track `capture`: is QQQ_2025-09-23 dropped by
MIN_STOP_PCT, or by some other gate the delegating router also grew?

Ablates one base-router gate at a time on the single card that separates the
two arms. Reads bars from data_archive; writes nothing; touches no engine file.
"""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import signal_runner as sr
import t4_engine_recall as t4
from g71_capture_route_ab import DelegatingCaptureRunner

SYM, DAY = "QQQ", "2025-09-23"

def card():
    p = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
    for l in open(p, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            if r["symbol"] == SYM and r["date"] == DAY:
                return r
    return None

def show(tag):
    ent, sigs, raw = t4.run_day(SYM, DAY)
    print(f"\n-- {tag}: entries={len(ent)} deduped_sigs={len(sigs)} raw={len(raw)}")
    for e in ent:
        w = abs(e["entry"] - e["stop"]) / abs(e["entry"]) * 100
        print(f"   FIRE bar={e['bar']} {e['timestamp']} {e['signal_type']} "
              f"{e['direction']} grade={e['grade']} entry={e['entry']} "
              f"stop={e['stop']} width={w:.4f}% of price")
    return len(ent)

c = card()
print("card:", c["card_id"], "answers.s =", c["answers"]["s"], "et =", c.get("et"),
      "lane =", c.get("lane"))
print("MIN_STOP_PCT =", sr.MIN_STOP_PCT, " NO_REPEAT_ENTRIES =", sr.NO_REPEAT_ENTRIES,
      " ENFORCE_NO_REPEAT =", sr.ENFORCE_NO_REPEAT,
      " LEVEL_RETIRE_TOUCHES =", sr.LEVEL_RETIRE_TOUCHES,
      " X_LIFT =", sr.X_LIFT, " S_GATE =", sr.S_GATE,
      " AUSTIN_TIER_ENABLED =", sr.AUSTIN_TIER_ENABLED)

incumbent = t4.CaptureRunner
n_a = show("A incumbent CaptureRunner")

t4.CaptureRunner = DelegatingCaptureRunner
try:
    n_b = show("B delegating, shipped flags")

    old = sr.MIN_STOP_PCT; sr.MIN_STOP_PCT = 0.0
    n_b_nomin = show("B delegating, MIN_STOP_PCT=0")
    sr.MIN_STOP_PCT = old

    old_nr = sr.NO_REPEAT_ENTRIES; sr.NO_REPEAT_ENTRIES = False
    n_b_nonr = show("B delegating, NO_REPEAT_ENTRIES=False")
    sr.NO_REPEAT_ENTRIES = old_nr

    old_lr = sr.LEVEL_RETIRE_TOUCHES; sr.LEVEL_RETIRE_TOUCHES = 0
    n_b_nolr = show("B delegating, LEVEL_RETIRE_TOUCHES=0")
    sr.LEVEL_RETIRE_TOUCHES = old_lr
finally:
    t4.CaptureRunner = incumbent

print("\nVERDICT on this card:")
print("  A fires:", n_a, " B fires:", n_b,
      " B|MIN_STOP_PCT=0:", n_b_nomin,
      " B|NO_REPEAT off:", n_b_nonr,
      " B|LEVEL_RETIRE off:", n_b_nolr)
