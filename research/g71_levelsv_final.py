"""Final adversarial table: base vs six_target vs six_or_shipped."""
from __future__ import annotations
import json, math, random, statistics as st
from collections import defaultdict

def load(p):
    return [t for t in json.load(open(p, encoding="utf-8"))["trades"] if t["traded"]]
def key(t): return (t["sym"], t["day"], t["et"], t["setup"], t["dir"], t["entry"], t["stop"])

B = load("research/_v/v_base2.json")
arms = {"six_target": load("research/_v/v_six.json"),
        "six_or_shipped": load("research/_v/v_sixorship.json")}

def stat(tr):
    rs=[t["r"] for t in tr]; w=sum(1 for t in tr if t["out"]=="win"); l=sum(1 for t in tr if t["out"]=="loss")
    m=defaultdict(float)
    for t in tr: m[t["ym"]]+=t["r"]
    return len(tr), (w/(w+l)*100 if w+l else 0), st.fmean(rs), sum(rs), sum(1 for v in m.values() if v>0), len(m), m

for nm, tr in [("base", B)] + list(arms.items()):
    n,w,mr,tot,g,mo,_ = stat(tr)
    print("%-16s n=%-5d win=%.1f%% meanR=%+.4f totalR=%+.1f green=%d/%d" % (nm,n,w,mr,tot,g,mo))

bm={key(t):t for t in B}
random.seed(11)
for nm, tr in arms.items():
    am={key(t):t for t in tr}; sh=sorted(set(bm)&set(am))
    d=[am[k]["r"]-bm[k]["r"] for k in sh]
    m=st.fmean(d); se=st.pstdev(d)/math.sqrt(len(d))
    byday=defaultdict(list)
    for k,x in zip(sh,d): byday[k[1]].append(x)
    days=list(byday); N=len(d)
    dt=[sum(v)-m*len(v) for v in byday.values()]
    secl=math.sqrt(sum(x*x for x in dt))/N
    boot=[]
    for _ in range(4000):
        s=0.0;n=0
        for _ in range(len(days)):
            v=byday[random.choice(days)]; s+=sum(v); n+=len(v)
        boot.append(s/n)
    boot.sort()
    print("%-16s shared=%d moved=%d dR=%+.4f naive95=+/-%.4f clustered95=+/-%.4f boot=[%+.4f,%+.4f] P(dR>=0)=%.4f"
          % (nm,len(sh),sum(1 for x in d if abs(x)>1e-9),m,1.96*se,1.96*secl,boot[100],boot[3899],
             sum(1 for x in boot if x>=0)/len(boot)))

_,_,_,_,_,_,mb = stat(B)
for nm, tr in arms.items():
    _,_,_,_,_,_,ma = stat(tr)
    fl=[(ym,mb[ym],ma[ym]) for ym in sorted(set(mb)|set(ma)) if (mb[ym]>0)!=(ma[ym]>0)]
    print("%-16s month flips: %s" % (nm, ["%s %+.2f->%+.2f" % f for f in fl] or "none"))
