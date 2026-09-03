"""G7.1: isolate the one mark that changes between the two routers."""
import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE); sys.path.insert(0,ROOT)
import t4_engine_recall as t4
from g71_capture_ab import delegating_route
import signal_runner as sr

SYM, DAY = "SPY", "2026-03-05"
for name in ("hand-rolled", "delegating"):
    if name == "delegating":
        t4.CaptureRunner._route = delegating_route
    ent, sigs, raw = t4.run_day(SYM, DAY)
    print(f"--- {name}: {len(ent)} entries, {len(raw)} raw")
    for r in raw:
        if 54 <= r["bar"] <= 58:
            print("   ", r["bar"], r["signal_type"], r["direction"], r["grade"],
                  r["status"], f"entry={r['entry']:.2f} stop={r['stop']:.2f}",
                  f"stop_pct={abs(r['entry']-r['stop'])/abs(r['entry'])*100:.4f}%")
print("MIN_STOP_PCT =", sr.MIN_STOP_PCT, " NO_REPEAT_ENTRIES =", sr.NO_REPEAT_ENTRIES,
      " ENFORCE_NO_REPEAT =", sr.ENFORCE_NO_REPEAT, " LEVEL_RETIRE_TOUCHES =",
      sr.LEVEL_RETIRE_TOUCHES, " S_GATE =", sr.S_GATE, " RULE_710 =", sr.RULE_710_ENABLED,
      " AUSTIN_TIER_ENABLED =", sr.AUSTIN_TIER_ENABLED, " X_LIFT =", sr.X_LIFT)
