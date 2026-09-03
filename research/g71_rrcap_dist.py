"""g71 (rrcap): the booked-R distribution of the 2-year book -- does the 2R
target cap winners? Reads research/bt2y_trades.json only; runs no engine."""
import json, collections, statistics
from pathlib import Path

ROOT = Path(__file__).parent.parent
bk = json.loads((ROOT / "research" / "bt2y_trades.json").read_text(encoding="utf-8"))
meta, rows = bk["meta"], bk["trades"]
print("meta:", {k: meta[k] for k in ("generated","first","last","sessions","signals","traded","loss_halt","halted")})

tr = [r for r in rows if r["traded"]]
print("traded rows:", len(tr))
R = [r["r"] for r in tr]
print("mean R %.4f  median %.4f  min %.3f  max %.3f" % (
    statistics.fmean(R), statistics.median(R), min(R), max(R)))

wins = [r for r in tr if r["r"] > 0]
print("win rate %.4f  (%d of %d)" % (len(wins)/len(tr), len(wins), len(tr)))

# how many book EXACTLY 2.000R (the cap), within float noise
def near(x, v, tol=1e-9): return abs(x - v) <= tol
cap = [r for r in tr if near(round(r["r"],3), 2.0, 1e-6)]
over = [r for r in tr if r["r"] > 2.0 + 1e-6]
print("R == 2.000 exactly : %d  (%.2f%% of traded, %.2f%% of winners)" %
      (len(cap), 100*len(cap)/len(tr), 100*len(cap)/len(wins)))
print("R  > 2.000         : %d  (%.2f%% of traded, %.2f%% of winners)" %
      (len(over), 100*len(over)/len(tr), 100*len(over)/len(wins)))
print("max R over 2 :", sorted((r["r"] for r in over), reverse=True)[:15])
print("scaled among >2R:", sum(1 for r in over if r.get("scaled")), "of", len(over))
print("scaled among ==2R:", sum(1 for r in cap if r.get("scaled")), "of", len(cap))
print("scaled in book   :", sum(1 for r in tr if r.get("scaled")))

# exit price == target price?  (the definitional cap test)
at_tgt = [r for r in tr if abs(r["exit"] - r["target"]) < 0.005]
print("exit == target price: %d (%.2f%% of traded)" % (len(at_tgt), 100*len(at_tgt)/len(tr)))

# target is exactly 2x risk?
bad = 0; tot = 0
for r in tr:
    risk = abs(r["entry"] - r["stop"])
    if risk <= 0: continue
    tot += 1
    rr = abs(r["target"] - r["entry"]) / risk
    if abs(rr - 2.0) > 0.02: bad += 1
print("planned R:R != 2.000 : %d of %d rows (%.3f%%)" % (bad, tot, 100*bad/tot))

hist = collections.Counter()
for x in R:
    b = round(x, 3)
    hist[b] += 1
print("top 12 exact R values:", hist.most_common(12))

# winners bucketed
buck = collections.Counter()
for r in wins:
    x = r["r"]
    b = ("<1" if x < 1 else "1-1.5" if x < 1.5 else "1.5-2" if x < 2-1e-6
         else "==2" if x <= 2+1e-6 else "2-3" if x < 3 else "3+")
    buck[b] += 1
print("winner buckets:", dict(buck))
