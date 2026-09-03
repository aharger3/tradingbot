"""G7.1: mechanism for the one held-out S card that flips between routers."""
import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE); sys.path.insert(0,ROOT)
from research import t4_engine_recall as t4
from g71_capture_ab import delegating_route
SYM, DAY = "QQQ", "2025-09-23"
for name in ("hand-rolled", "delegating"):
    if name == "delegating":
        t4.CaptureRunner._route = delegating_route
    ent, sigs, raw = t4.run_day(SYM, DAY)
    fired = [r for r in raw if r["status"] == "fired"]
    print(f"--- {name}: fired={len(fired)} raw={len(raw)}")
    for r in raw:
        if r["status"] in ("fired", "skipped_min_stop_pct"):
            print("   bar", r["bar"], r["timestamp"][11:16], r["signal_type"],
                  r["direction"], r["grade"], r["status"],
                  f"stop_pct={abs(r['entry']-r['stop'])/abs(r['entry'])*100:.4f}%")
