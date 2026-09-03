"""Paired significance on the CAP curve's interior, and the marginal-Sharpe
condition the `weeks` report states incorrectly."""
import json, math
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT/"research/_g71_weeks_verify.json").read_text())
N = {r["policy"].split()[0]: r for r in d["capn_curve"]+d["policies"]+d["week_policies"]}
def gv(r): return [1 if v>0 else 0 for _w,v,_c in r["weekly_series"]]
def mc(a,b):
    ga,gb=gv(N[a]),gv(N[b])
    b01=sum(1 for x,y in zip(ga,gb) if x==0 and y==1); b10=sum(1 for x,y in zip(ga,gb) if x==1 and y==0)
    n=b01+b10
    if n==0: return (0,0,1.0)
    k=min(b01,b10); p=2*sum(math.comb(n,i) for i in range(k+1))/2**n
    return (b10,b01,round(min(1.0,p),4))
for a,b in [("CAP-3","CAP-4"),("CAP-3","CAP-5"),("CAP-3","CAP-24"),("CAP-1","CAP-3"),
            ("CAP-1","CAP-24"),("CAP-2","CAP-3"),("P0","CAP-3"),("P0","CAP-24"),("P0","P0u")]:
    x=mc(a,b); print("%-8s vs %-8s  %s only=%2d  %s only=%2d  p=%s  (%.1f%% -> %.1f%%)"
        % (a,b,a,x[0],b,x[1],x[2],N[a]["green_week_pct"],N[b]["green_week_pct"]))

print()
# The report's escape clause: "unless the trades you drop have negative edge".
# The correct condition for adding a marginal trade to RAISE weekly Sharpe
# S = M/sqrt(V) is EXACTLY  2(m/M) + (m/M)^2 > v/V, where (m,v) are the marginal
# trade's mean and variance and (M,V) the running totals. Positive edge (m>0)
# is NOT sufficient. Evaluate it slot by slot.
import statistics, sys
from collections import defaultdict
sys.path.insert(0,str(ROOT/"research"))
from g71_firsts_policy import ekey,xkey
b2=json.loads((ROOT/"research/bt2y_trades.json").read_text())
cnt=[r for r in b2["trades"] if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
bd=defaultdict(list)
for r in cnt: bd[r["day"]].append(r)
for k in bd: bd[k].sort(key=ekey)
slot=defaultdict(list)
for dd,rows in bd.items():
    free=None;i=0
    for c in rows:
        if free is not None and ekey(c)<free: continue
        slot[i].append(c["r"]); free=xkey(c); i+=1
W=105.0
M=V=0.0
print("%5s %9s %9s %9s %9s %9s" % ("slot","m/wk","v/wk","wkSharpe","dSharpe","raises?"))
for k in sorted(slot):
    v=slot[k]; m=sum(v)/W; vv=statistics.pvariance(v)*len(v)/W
    S0=M/math.sqrt(V) if V else 0.0
    M+=m; V+=vv; S1=M/math.sqrt(V)
    print("%5d %9.4f %9.4f %9.4f %9.4f %9s" % (k+1,m,vv,S1,S1-S0,"YES" if S1>S0 else "NO"))
