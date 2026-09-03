"""What the recall harness itself emits within +/-2 bars of his minute, on the
9 FIRED days -- compared against what research/g71_timing.md section 4 prints."""
import os, sys, json
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE); sys.path.insert(0,ROOT)
from research.t4_engine_recall import run_day
days=[("CRM","2025-09-19",10),("SMCI","2025-11-17",36),("TSM","2026-02-02",6),
      ("BABA","2025-02-05",11),("PLTR","2024-03-11",13),("HOOD","2024-11-06",49),
      ("MSFT","2025-03-13",19),("AVGO","2025-10-10",17),("QQQ","2025-09-23",9)]
tot=nx=0
for s,d,his in days:
    ent,sig,raw=run_day(s,d)
    near=[r for r in raw if abs(r["bar"]-his)<=2]
    print("%-5s %s his=%2d | %s"%(s,d,his," · ".join(
        "%d:%s:%s:%s"%(r["bar"],r["grade"],r["status"],r["signal_type"][:3]) for r in near)))
    tot+=len(near); nx+=sum(1 for r in near if r["grade"]=="X")
print("\nraw near-signals total=%d  graded X=%d"%(tot,nx))
