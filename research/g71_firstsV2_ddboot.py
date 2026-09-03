"""G7.1 verify: (1) fixed-k control matched to P3's trades/day, (2) day-order
bootstrap of max drawdown for P0seq vs P3 vs P4 vs P0shipped."""
import json, random, statistics
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ekey = lambda r: (r["entry_i"], r["et"], r["sym"])
xkey = lambda r: (r["entry_i"] + r["bars"], r["et"], r["sym"])
def walk(c, dec):
    t, free = [], None; w=l=s=0; cum=0.0
    for x in c:
        if dec((len(t),w,l,s,cum)): break
        if free is not None and ekey(x) < free: continue
        t.append(x); free = xkey(x); o=x["out"]
        w += o=="win"; l += o=="loss"; s += o not in ("win","loss"); cum += x["r"]
    return t
b = json.loads((ROOT/"research/bt2y_trades.json").read_text(encoding="utf-8"))
counted=[r for r in b["trades"] if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
shipped=[r for r in b["trades"] if r["traded"]]
by_day=defaultdict(list)
for r in counted: by_day[r["day"]].append(r)
for d in by_day: by_day[d].sort(key=ekey)
days=sorted(by_day)
sh=defaultdict(list)
for r in shipped: sh[r["day"]].append(r)
def dv(t): return {d: sum(x["r"] for x in rs) for d,rs in t.items() if rs}
def mdd(v, order):
    cum=peak=mx=0.0
    for d in order:
        cum+=v.get(d,0.0); peak=max(peak,cum); mx=max(mx,peak-cum)
    return mx
arms={
 "P0 shipped": dv(dict(sh)),
 "P0seq":      dv({d: walk(rs, lambda s: False) for d,rs in by_day.items()}),
 "P3":         dv({d: walk(rs, lambda s: s[4]>0) for d,rs in by_day.items()}),
 "P4":         dv({d: walk(rs, lambda s: s[4]>0 or s[2]>=3) for d,rs in by_day.items()}),
}
for k in (1,2,3):
    def fk(rs,k=k):
        t,free=[],None
        for x in rs:
            if len(t)>=k: break
            if free is not None and ekey(x)<free: continue
            t.append(x); free=xkey(x)
        return t
    arms["fixed-k=%d"%k]=dv({d: fk(rs) for d,rs in by_day.items()})
print("%-12s %6s %6s %7s %8s %7s" % ("arm","t/day","green","green%","totalR","maxDD"))
for k,v in arms.items():
    n=sum(1 for d in v)  # days
    tr = 0
    print("%-12s %6.2f %6d %6.1f%% %8.1f %7.2f" %
          (k, sum(1 for _ in [0])*0 + 0, sum(1 for x in v.values() if x>0),
           100*sum(1 for x in v.values() if x>0)/len(v), sum(v.values()), mdd(v,days)))
print()
rng=random.Random(11)
print("day-order bootstrap of maxDD (2000 reps, resample day ORDER only):")
for k,v in arms.items():
    ds=[]
    for _ in range(2000):
        o=days[:]; rng.shuffle(o); ds.append(mdd(v,o))
    ds.sort()
    print("  %-12s actual %6.2f   boot median %6.2f  p5 %6.2f  p95 %6.2f  pctile_of_actual %.0f%%"
          % (k, mdd(v,days), ds[1000], ds[100], ds[1900],
             100*sum(1 for x in ds if x<=mdd(v,days))/len(ds)))
