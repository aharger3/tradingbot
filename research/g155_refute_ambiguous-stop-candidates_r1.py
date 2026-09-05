import json,os,sys,random
from collections import defaultdict
HERE=os.path.abspath('research'); ROOT=os.path.dirname(HERE)
sys.path.insert(0,ROOT); sys.path.insert(0,HERE)
import importlib.util
spec=importlib.util.spec_from_file_location("g154amb", os.path.join(HERE,"g154_rule_ambiguous-stop-candidates.py"))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import marks_pool

blob=json.load(open(m.BOOK_PATH,encoding="utf-8"))
meta,rows=blob["meta"],blob["trades"]
byday=m.by_day_candidates(rows)
n_days_total=meta["sessions"]
pool=marks_pool.canonical_pool()
s100=m.load_sweep_s_days()

# sizeable-filtered ordered candidate list per day (the only rows selection sees)
elig={}
for d,v in byday.items():
    elig[d]=[r for r in v if m._row_is_sizeable(r) is not False]
elig={d:v for d,v in elig.items() if v}
print("days with >=1 sizeable candidate:",len(elig))

flag={}
for d,v in elig.items():
    for r in v:
        flag[id(r)]=m.is_ambiguous(r)[0]
allrows=[r for v in elig.values() for r in v]
n_amb=sum(flag[id(r)] for r in allrows)
print("eligible candidates=%d ambiguous=%d rate=%.4f"%(len(allrows),n_amb,n_amb/len(allrows)))

def pick(flagmap):
    out=[]
    for d in sorted(elig):
        for r in elig[d]:
            if flagmap.get(id(r),False): continue
            out.append(r); break
    return out

def prec(firsts):
    gs=ga=0
    for r in firsts:
        e=pool.get("%s_%s"%(r["sym"],r["day"]))
        if e is None: continue
        ga+=1
        if e.grade=="S": gs+=1
    return (gs/ga*100 if ga else 0.0), gs, ga

def usd(firsts, lo=None, hi=None):
    f=[r for r in firsts if (lo is None or r["day"]>=lo) and (hi is None or r["day"]<hi)]
    if not f: return 0.0
    return sum(r["pnl"] for r in f)/len({r["day"] for r in f})

def rec100(firsts):
    byd=defaultdict(set)
    for r in firsts: byd[r["day"]].add(r["sym"])
    return sum(1 for s,d in s100 if s in byd.get(d,()))

base=pick({})
arm=pick(flag)
changed=sum(1 for a,b in zip(base,arm) if a is not b)
print("BASE prec=%.1f%% (%d/%d) usd/day=%.2f H1=%.2f H2=%.2f rec100=%d"%(*prec(base),usd(base),usd(base,hi=m.H_SPLIT),usd(base,lo=m.H_SPLIT),rec100(base)))
print("ARM  prec=%.1f%% (%d/%d) usd/day=%.2f H1=%.2f H2=%.2f rec100=%d"%(*prec(arm),usd(arm),usd(arm,hi=m.H_SPLIT),usd(arm,lo=m.H_SPLIT),rec100(arm)))
print("days whose PICK changed: %d of %d (%.1f%%)"%(changed,len(base),changed/len(base)*100))

bp,bgs,bga=prec(base); ap,ags,aga=prec(arm)
print("precision moved by %d graded-S day and %d graded day"%(ags-bgs,aga-bga))

# ---- PLACEBO: shuffle the ambiguous labels across eligible candidates ----
rng=random.Random(20260905)
N=3000
nsurv=nprec=0; dprec=[]; dusd=[]
ids=[id(r) for r in allrows]
labels=[flag[i] for i in ids]
b_prec=bp; b_h1=usd(base,hi=m.H_SPLIT); b_h2=usd(base,lo=m.H_SPLIT); b_r=rec100(base)
for _ in range(N):
    rng.shuffle(labels)
    fm=dict(zip(ids,labels))
    f=pick(fm)
    p,_g,_a=prec(f)
    h1=usd(f,hi=m.H_SPLIT); h2=usd(f,lo=m.H_SPLIT); rc=rec100(f)
    dprec.append(p-b_prec); dusd.append(usd(f)-usd(base))
    pi=p>b_prec
    if pi: nprec+=1
    if ((h1>b_h1 and h2>b_h2) or pi) and rc>=b_r: nsurv+=1
dprec.sort()
print("PLACEBO n=%d: P(precision improves)=%.3f  P(survivor gate passes)=%.3f"%(N,nprec/N,nsurv/N))
print("PLACEBO precision-delta pctiles 5/50/95: %.2f / %.2f / %.2f ; observed %.2f -> pct rank %.3f"%(
    dprec[int(.05*N)],dprec[N//2],dprec[int(.95*N)],ap-bp,
    sum(1 for x in dprec if x< (ap-bp))/N))

# ---- bootstrap CI on $/day delta, paired by day ----
days=sorted(elig)
bpnl={r["day"]:r["pnl"] for r in base}
apnl={r["day"]:r["pnl"] for r in arm}
diff=[apnl.get(d,0.0)-bpnl.get(d,0.0) for d in days]
boot=[]
for _ in range(5000):
    s=[diff[rng.randrange(len(diff))] for _ in range(len(diff))]
    boot.append(sum(s)/len(s))
boot.sort()
print("BOOTSTRAP $/day delta mean=%.2f  95%% CI [%.2f, %.2f]"%(sum(diff)/len(diff),boot[125],boot[4875]))
