"""G71 adversarial verify: is the 'direction at his minute' stable?

For each of the 34 S cards, list every signal within +/-5 minutes of the
minute Austin wrote, and report whether call and put BOTH appear. If they do,
the aligned/opposed label the trend track published is an artifact of the
tie-break, not of his setup.
"""
import os, sys, json
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
from research.t4_engine_recall import run_day
from research.g71_trend import read_sweep

S, refused, minute = read_sweep()
rows = []
for k in sorted(S):
    sym, day = k
    et = minute[k]
    m = int(et[:2]) * 60 + int(et[3:])
    try:
        entries, sigs, _ = run_day(sym, day)
    except Exception as e:
        rows.append({"card": "%s_%s" % k, "err": str(type(e).__name__)}); continue
    sigs = sigs or []
    def mm(s):
        return int(s["timestamp"][:2]) * 60 + int(s["timestamp"][3:5])
    near = [s for s in sigs if abs(mm(s) - m) <= 5]
    win = [s for s in sigs if abs(mm(s) - m) <= 15]
    pick = min(sigs, key=lambda s: abs(mm(s) - m)) if sigs else None
    rows.append({"card": "%s_%s" % k, "min": et,
                 "n_all": len(sigs),
                 "pick_dir": pick["direction"] if pick else None,
                 "pick_et": pick["timestamp"][:5] if pick else None,
                 "pick_gap": abs(mm(pick) - m) if pick else None,
                 "n5": len(near), "dirs5": sorted({s["direction"] for s in near}),
                 "n15": len(win), "dirs15": sorted({s["direction"] for s in win}),
                 "grades_all": dict(Counter(s["grade"] for s in sigs)),
                 "status_all": dict(Counter(s.get("status") for s in sigs))})
amb5 = sum(1 for r in rows if len(r.get("dirs5") or []) > 1)
amb15 = sum(1 for r in rows if len(r.get("dirs15") or []) > 1)
gap = Counter(r.get("pick_gap") for r in rows)
print("cards", len(rows))
print("both directions within +/-5m :", amb5)
print("both directions within +/-15m:", amb15)
print("pick_gap distribution (min):", dict(sorted(gap.items(), key=lambda kv: (kv[0] is None, kv[0]))))
print("cards whose nearest signal is >5m from his minute:",
      sum(1 for r in rows if (r.get("pick_gap") or 0) > 5))
print("signals per day: min %d med %d max %d" % (
    min(r["n_all"] for r in rows),
    sorted(r["n_all"] for r in rows)[len(rows)//2],
    max(r["n_all"] for r in rows)))
allg = Counter()
for r in rows: allg.update(r["grades_all"])
print("grades over ALL signals on the 34 S days:", dict(allg))
alls = Counter()
for r in rows: alls.update(r["status_all"])
print("status over ALL signals on the 34 S days:", dict(alls))
json.dump(rows, open(os.path.join(HERE, "g71_verify_trend_dirsens.json"), "w"), indent=1)
for r in rows:
    print(" %-20s min=%s pick=%s/%s gap=%s n5=%d dirs5=%s n15=%d dirs15=%s n_all=%d"
          % (r["card"], r.get("min"), r.get("pick_et"), r.get("pick_dir"),
             r.get("pick_gap"), r.get("n5", 0), ",".join(r.get("dirs5") or []),
             r.get("n15", 0), ",".join(r.get("dirs15") or []), r.get("n_all", 0)))
