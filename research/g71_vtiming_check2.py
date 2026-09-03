"""ADVERSARIAL VERIFY part 2: does 'AND traded it' hold on the shipped book, and
is anything emitted AT his candle (offset 0) as opposed to within +/-2?"""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
from t4_engine_recall import run_day  # noqa

DAYS = [("CRM","2025-09-19",10),("SMCI","2025-11-17",36),("TSM","2026-02-02",6),
        ("BABA","2025-02-05",11),("PLTR","2024-03-11",13),("HOOD","2024-11-06",49),
        ("MSFT","2025-03-13",19),("AVGO","2025-10-10",17),("QQQ","2025-09-23",9)]
book = json.load(open(os.path.join(HERE, "bt2y_trades.json")))
bysd = {}
for r in book["trades"]:
    bysd.setdefault((r["sym"], r["day"]), []).append(r)

print("%-5s %-11s %4s | %-30s | %s" % ("sym","day","his","t4 replay fired entry","shipped book that day"))
exact0 = 0
for sym, day, his in DAYS:
    ent, sigs, raw = run_day(sym, day)
    nf = min(ent, key=lambda e: abs(e["bar"] - his))
    at_his = [s for s in sigs if s["bar"] == his]
    exact0 += bool(at_his)
    rows = bysd.get((sym, day), [])
    fired = [r for r in rows if r["status"] == "fired"]
    traded = [r for r in rows if r.get("traded")]
    print("%-5s %-11s %4d | bar%-3d %-16s %-4s %-6s | rows=%2d fired=%d(grades %s) TRADED=%d | sig AT his bar: %s"
          % (sym, day, his, nf["bar"], nf["signal_type"], nf["direction"],
             nf["grade"], len(rows), len(fired),
             ",".join(sorted({r["grade"] for r in fired})) or "-", len(traded),
             ("yes " + ",".join("%s/%s" % (s["grade"], s["status"]) for s in at_his)) if at_his else "NOTHING"))
print("\ndays with any deduped signal EXACTLY at his typed bar: %d of 9" % exact0)
print("days the shipped book TRADED: %d of 9"
      % sum(1 for s, d, _ in DAYS if any(r.get("traded") for r in bysd.get((s, d), []))))
