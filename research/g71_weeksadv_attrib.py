"""Attribution: which of W1's advertised costs come from the WEEKLY STOP and
which come from dropping concurrency (P0 -> P0seq)?  Plus: is 102/105 more
than W1's own per-trade edge implies?"""
import json, math, random, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
book = json.loads((ROOT/"research/bt2y_trades.json").read_text(encoding="utf-8"))
trades = book["trades"]; RISK = book["meta"]["risk_dollars"]
counted = [r for r in trades if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
shipped = [r for r in trades if r["traded"]]
ek=lambda r:(r["entry_i"],r["et"],r["sym"]); xk=lambda r:(r["entry_i"]+r["bars"],r["et"],r["sym"])
def wkof(d):
    y,w,_=date.fromisoformat(d).isocalendar(); return "%04d-W%02d"%(y,w)
by_day=defaultdict(list)
for r in counted: by_day[r["day"]].append(r)
for d in by_day: by_day[d].sort(key=ek)
days=sorted(by_day); weeks=sorted({wkof(d) for d in days}); months=sorted({d[:7] for d in days})
wkd=defaultdict(list)
for d in days: wkd[wkof(d)].append(d)
def run(stop):
    out=[]
    for w in weeks:
        cum=0.0; stop_now=False
        for d in wkd[w]:
            if stop_now: break
            free=None
            for c in by_day[d]:
                if stop(cum): stop_now=True; break
                if free is not None and ek(c)<free: continue
                free=xk(c); out.append(c); cum+=c["r"]
    return out
def mo(rows):
    m=defaultdict(float)
    for r in rows: m[r["day"][:7]]+=r["r"]
    return m
NEV=lambda c:False; W1=lambda c:c>0
seq=run(NEV); w1=run(W1)
ms=mo(shipped); mq=mo(seq); mw=mo(w1)
red=lambda m:[k for k in months if m.get(k,0.0)<=0]
print("months not green -- P0:",red(ms)," P0seq:",red(mq)," W1:",red(mw))
for lbl,rows in (("P0",shipped),("P0seq",seq),("W1",w1)):
    n=len(rows); print("%-6s n=%4d meanR=%.4f sdR=%.4f totalR=%.2f"%(lbl,n,statistics.fmean([r['r'] for r in rows]),statistics.pstdev([r['r'] for r in rows]),sum(r['r'] for r in rows)))
# Is 102/105 above what W1's own trade stream implies iid?  Permute W1's OWN
# realised R values across its own week slots, keeping counts, 2000 draws.
rng=random.Random(7)
wr=defaultdict(list)
for r in w1: wr[wkof(r["day"])].append(r["r"])
pool=[r["r"] for r in w1]; counts=[len(wr.get(w,[])) for w in weeks]
d=[]
for _ in range(2000):
    s=pool[:]; rng.shuffle(s); i=0; g=0
    for c in counts:
        if c and sum(s[i:i+c])>0: g+=1
        i+=c
    d.append(g)
d.sort(); print("W1 green weeks if its OWN trades were shuffled across its own weeks: median %d [p05 %d p95 %d]  observed 102"%(d[1000],d[100],d[1900]))
