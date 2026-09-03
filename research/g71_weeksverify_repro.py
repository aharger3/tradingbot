"""ADVERSARIAL VERIFY of research/g71_weeks.md's weekly claims.

Independent re-implementation: does NOT import g71_firsts_policy. Rebuilds the
day policies, the ISO-week green counts, and McNemar from research/bt2y_trades.json.
"""
import json, math, statistics
from collections import defaultdict, Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
book = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
meta, trades = book["meta"], book["trades"]
print("BOOK", {k: meta[k] for k in ("generated","first","last","sessions","signals","traded","halted","loss_halt")})

counted = [r for r in trades if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
shipped = [r for r in trades if r["traded"]]
print("counted", len(counted), "shipped", len(shipped))

def ek(r): return (r["entry_i"], r["et"], r["sym"])
def xk(r): return (r["entry_i"]+r["bars"], r["et"], r["sym"])
def wk(d):
    y,w,_ = date.fromisoformat(d).isocalendar(); return "%04d-W%02d"%(y,w)

by_day = defaultdict(list)
for r in counted: by_day[r["day"]].append(r)
for d in by_day: by_day[d].sort(key=ek)
all_days = sorted(by_day)
all_weeks = sorted({wk(d) for d in all_days})
print("days", len(all_days), "weeks", len(all_weeks), "months", len({d[:7] for d in all_days}))

def walk(c, stop):
    out=[]; free=None; w=l=s=0; cum=0.0
    for r in c:
        if stop((len(out),w,l,s,cum)): break
        if free is not None and ek(r)<free: continue
        out.append(r); free=xk(r)
        o=r["out"]
        if o=="win": w+=1
        elif o=="loss": l+=1
        else: s+=1
        cum+=r["r"]
    return out

P={"P1": lambda s: s[0]>=1,
   "P2": lambda s: s[1]>=1 or s[2]>=2,
   "P3": lambda s: s[4]>0,
   "P4": lambda s: s[4]>0 or s[2]>=3,
   "P0seq": lambda s: False}

def weekvec(rows_by_day):
    v=defaultdict(float)
    for d,rs in rows_by_day.items():
        v[wk(d)] += sum(r["r"] for r in rs)
    return [v.get(w,0.0) for w in all_weeks]

def grp(rows):
    g=defaultdict(list)
    for r in rows: g[r["day"]].append(r)
    return g

s_by_day = {}
for d,rs in by_day.items():
    ss=[r for r in rs if r["sgrade"]=="S"]
    if ss: s_by_day[d]=ss

arms={}
arms["P0"]=weekvec(grp(shipped))
arms["P0u"]=weekvec(by_day)
for k,f in P.items():
    arms[k]=weekvec({d: walk(rs,f) for d,rs in by_day.items()})
arms["P5"]=weekvec({d: walk(rs,P["P2"]) for d,rs in s_by_day.items()})

ntr={}
ntr["P0"]=len(shipped); ntr["P0u"]=len(counted)
for k,f in P.items(): ntr[k]=sum(len(walk(rs,f)) for rs in by_day.values())
ntr["P5"]=sum(len(walk(rs,P["P2"])) for rs in s_by_day.values())

def g(v): return [1 if x>0 else 0 for x in v]
def mcnemar(a,b):
    ga,gb=g(a),g(b)
    b10=sum(1 for x,y in zip(ga,gb) if x==1 and y==0)
    b01=sum(1 for x,y in zip(ga,gb) if x==0 and y==1)
    n=b10+b01
    if n==0: return b10,b01,1.0
    k=min(b10,b01)
    p=2*sum(math.comb(n,i) for i in range(k+1))/2**n
    return b10,b01,min(1.0,p)

print("\n%-6s %6s %7s %8s %9s"%("arm","trades","green","%grn","totalR"))
for k in ("P0","P0u","P0seq","P1","P2","P3","P4","P5"):
    v=arms[k]; gr=sum(1 for x in v if x>0)
    print("%-6s %6d %4d/%-3d %7.2f%% %9.2f"%(k,ntr[k],gr,len(v),gr/len(v)*100,sum(v)))

print("\nMcNemar vs P0 (a_only=P0 wins, b_only=arm wins)")
ps={}
for k in ("P1","P2","P3","P4","P5","P0seq","P0u"):
    a,b,p=mcnemar(arms["P0"],arms[k]); ps[k]=p
    print("  P0 vs %-6s a_only=%2d b_only=%2d p=%.5f"%(k,a,b,p))

# multiplicity: the report ran 13 tests
allp=sorted([0.0,0.00342,0.01294,0.01612,0.11847,0.15159,0.28628,0.50344,0.60724,0.72656,0.79053,1.0,1.0])
m=len(allp); print("\nHolm over the report's %d tests:"%m)
mx=0
for i,p in enumerate(allp):
    adj=min(1.0,max(mx,p*(m-i))); mx=adj
    print("   raw %.5f -> Holm %.4f %s"%(p,adj,"SIG" if adj<0.05 else "n.s."))

# fragility of P1's discordant weeks
v0,v1=arms["P0"],arms["P1"]
disc=[(w,a,b) for w,a,b in zip(all_weeks,v0,v1) if (a>0)!=(b>0)]
p0w=[x for x in disc if x[1]>0]
print("\nP0-wins weeks: P1 weekly R distribution (how close to green):")
mm=sorted(x[2] for x in p0w)
print("  n=%d min=%.2f q1=%.2f med=%.2f q3=%.2f max=%.2f ; within -1R of green: %d"%(
   len(mm),mm[0],mm[len(mm)//4],mm[len(mm)//2],mm[3*len(mm)//4],mm[-1],sum(1 for x in mm if x>-1)))
p1w=[x for x in disc if x[2]>0]
mm2=sorted(x[1] for x in p1w)
print("  P1-wins weeks: P0 weekly R min=%.2f med=%.2f max=%.2f"%(mm2[0],mm2[len(mm2)//2],mm2[-1]))

# per-trade edge: is P1 worse per trade, or just smaller n?
def rows(t): return [r for rs in t.values() for r in rs]
r1=rows({d: walk(rs,P["P1"]) for d,rs in by_day.items()})
print("\nper-trade edge  P0 mean=%.4f sd=%.4f n=%d | P1 mean=%.4f sd=%.4f n=%d"%(
  statistics.fmean(r["r"] for r in shipped), statistics.pstdev([r["r"] for r in shipped]), len(shipped),
  statistics.fmean(r["r"] for r in r1), statistics.pstdev([r["r"] for r in r1]), len(r1)))
print("P1 picks by status:", Counter(r["status"] for r in r1))
print("P1 picks NOT in shipped book (halted rows):", sum(1 for r in r1 if r["status"]=="halted"))

# iid model prediction of green-week share at each arm's own n
mu=statistics.fmean(r["r"] for r in shipped); sg=statistics.pstdev([r["r"] for r in shipped])
def phi(x): return 0.5*(1+math.erf(x/math.sqrt(2)))
print("\nPhi(sqrt(n_wk)*mu/sd) using P0's OWN per-trade mu/sd, at each arm's trades/week:")
for k in ("P1","P2","P3","P4","P0seq","P0"):
    n=ntr[k]/len(all_weeks)
    print("  %-6s t/wk=%5.2f predicted %%green=%5.1f%%  observed=%5.1f%%"%(
      k,n,phi(math.sqrt(n)*mu/sg)*100, sum(1 for x in arms[k] if x>0)/len(arms[k])*100))

# ---- extra: the concurrency-isolated baseline, and a paired week bootstrap
import random as _rnd
print("\nP0seq vs P1 (both sequential, count is the only difference):")
a,b,p = mcnemar(arms["P0seq"], arms["P1"]); print("  a_only=%d b_only=%d p=%.5f"%(a,b,p))
gv0=g(arms["P0"]); gv1=g(arms["P1"])
R=_rnd.Random(7); diffs=[]
for _ in range(5000):
    idx=[R.randrange(len(gv0)) for _ in range(len(gv0))]
    diffs.append(sum(gv0[i] for i in idx)-sum(gv1[i] for i in idx))
diffs.sort()
print("paired week bootstrap of (P0 green - P1 green), 5000 draws: med=%d  95%%CI [%d, %d]  P(<=0)=%.4f"
      %(diffs[2500],diffs[125],diffs[4875],sum(1 for d in diffs if d<=0)/len(diffs)))
