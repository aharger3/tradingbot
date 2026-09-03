"""ADVERSARIAL part 3: re-run the family on a CAUSAL, DE-DUPLICATED arm set and
test the ruling metric (EV per trade in R), not the runner rate."""
import json, os, sys
import numpy as np
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__))
kept=json.load(open(os.path.join(HERE,"_adv_g114_pop.json"),encoding="utf-8"))["rows"]
n=len(kept)
runner=np.array([1 if r["_mfe_alive"]>=3.0 else 0 for r in kept])
bookr=np.array([r["r"] for r in kept]); t3=np.array([r["_t3.0"] for r in kept])
t2=np.array([r["_t2.0"] for r in kept])

# --- verify level_tf=1D is exactly PDH u PDL -----------------------------
d1=set(i for i,r in enumerate(kept) if r.get("level_tf")=="1D")
pdhl=set(i for i,r in enumerate(kept) if r.get("level") in ("PDH","PDL"))
print("level_tf=1D n=%d ; level in {PDH,PDL} n=%d ; identical: %s"
      % (len(d1),len(pdhl),d1==pdhl))
from collections import Counter
print("level_tf values:", Counter(r.get("level_tf") for r in kept).most_common())

# --- causal, de-duplicated arm family -------------------------------------
LOOKAHEAD_FIELDS={"drange (day range %)","dret (day return %)","rangeb","vol_regime","spy_trend"}
DUP_FIELDS={"level_name","downgrade","n_downgrades","setup_label","gap_abs","side","pool"}  # aliases of level/tag/tripped_n/setup/gap/dir/cls
DEGENERATE={"planned_rr (target R)","level_dist_r"}   # constants: 2.0R and 1.0R for every row
CATEGORICAL=["grade","sgrade","setup","level","level_tf","tier","cls","dir","confluence",
             "stopb","bias","aligned","gapb","dow","slot","entry_tf","bias_tf"]
MIN_N=15
def cat_pairs(r):
    out=[]
    for f in CATEGORICAL:
        v=r.get(f)
        if v not in (None,"","n/a","None"): out.append((f,str(v)))
    et=r.get("et") or "09:30"
    out+= [("hour",et[:2]),("tripped_bucket","tripped=%s"%r.get("tripped")),("seq_bucket","seq%s"%r.get("seq"))]
    for t in (r.get("tags") or ()): out.append(("tag",t))
    return out
def numfeat(r):
    et=r.get("et") or "09:30"
    try: tn=int(r.get("tripped"))
    except (TypeError,ValueError): tn=None
    return {"s (engine score)":r.get("s"),"stop_pct":r.get("stop_pct"),"risk_dollars":r["_risk"],
      "entry_price":r["entry"],"gap":r.get("gap"),
      "minutes_since_open":(int(et[:2])*60+int(et[3:5]))-570,"tripped_n":tn,
      "n_tags":len(r.get("tags") or [])}
masks=defaultdict(lambda: np.zeros(n,dtype=bool))
for i,r in enumerate(kept):
    for k,v in cat_pairs(r): masks[(k,v)][i]=True
nm_={}
for r in kept:
    for k,v in numfeat(r).items(): nm_.setdefault(k,[]).append(np.nan if v is None else float(v))

TRIALS=20000
rng=np.random.default_rng(20260903)
def family(label, name):
    lab=label.astype(float)
    idx=np.argsort(rng.random((TRIALS,n)),axis=1); P=lab[idx]
    arms=[]
    for (f,v),m in sorted(masks.items()):
        k=int(m.sum())
        if k<MIN_N or n-k<MIN_N: continue
        mf=m.astype(float); s=P.dot(mf)
        dp=s/k-(lab.sum()-s)/(n-k)
        o=lab[m].mean()-lab[~m].mean()
        arms.append((f,v,k,o,dp))
    for f,vals in nm_.items():
        val=np.array(vals,dtype=float); good=~np.isnan(val)
        if good.sum()<2*MIN_N: continue
        vg=val[good]; pg=P[:,good]; lg=lab[good]; N=good.sum()
        # numeric arm: correlate value with label -> use mean-diff of VALUE by label
        # for a continuous LABEL (EV) use Pearson-style: mean of label in top/bottom half
        med=np.median(vg); m2=vg>med
        s=pg.dot(m2.astype(float)); k2=m2.sum()
        dp=s/k2-(lg.sum()-s)/(N-k2)
        o=lg[m2].mean()-lg[~m2].mean()
        arms.append((f+" (>median)","",int(k2),o,dp))
    Z=np.column_stack([np.abs((a[4]-a[4].mean())/a[4].std(ddof=1)) for a in arms])
    zo=np.array([abs((a[3]-a[4].mean())/a[4].std(ddof=1)) for a in arms])
    praw=np.array([(np.sum(np.abs(a[4])>=abs(a[3]))+1)/(TRIALS+1) for a in arms])
    mx=Z.max(axis=1)
    pf=np.array([(np.sum(mx>=zo[j])+1)/(TRIALS+1) for j in range(len(arms))])
    print("\n=== FAMILY: %s | %d causal de-duplicated arms | Bonferroni thr %.5f ===" % (name,len(arms),0.05/len(arms)))
    print("%-16s %-22s %5s %9s %8s %9s" % ("field","value","n","effect","p_raw","p_FWER"))
    for j in np.argsort(praw)[:10]:
        f,v,k,o,_=arms[j]
        print("%-16s %-22s %5d %+9.4f %8.4f %9.4f" % (f,v[:22],k,o,praw[j],pf[j]))
    print("  survivors: Bonferroni %d | Westfall-Young FWER<0.05 %d"
          % ((praw<0.05/len(arms)).sum(),(pf<0.05).sum()))
    return arms,praw,pf

family(runner, "runner label (MFE-while-alive >= 3R)")
family(bookr,  "EV per trade in R -- book realised")
family(t3,     "EV per trade in R -- flat 3R target, bar-ordered")

# --- the one arm, stated in the ruling unit --------------------------------
m=np.array([r.get("level_tf")=="1D" for r in kept])
y1=np.array([r["day"]<"2025-09-01" for r in kept])
print("\n=== VETO level_tf=1D (== PDH/PDL), EV per trade in R ===")
def ev(x):
    w=x>0;l=x<0
    return "EV %+.3fR win %4.1f%% avgW %+.3f avgL %+.3f n=%d" % (x.mean(),100*w.mean(),
        x[w].mean() if w.any() else 0, x[l].mean() if l.any() else 0, len(x))
for nm2,arr in [("book realised",bookr),("flat 2R",t2),("flat 3R",t3)]:
    print("  %-14s ALL   %s" % (nm2,ev(arr)))
    print("  %-14s KEEP  %s" % ("",ev(arr[~m])))
    print("  %-14s VETOED%s" % ("",ev(arr[m])))
for tag,sub in [("Y1",y1),("Y2",~y1)]:
    print("  %s  keep book %+.3fR (n=%d) | vetoed %+.3fR (n=%d) | keep 3R %+.3fR"
          % (tag,bookr[sub&~m].mean(),(sub&~m).sum(),bookr[sub&m].mean(),(sub&m).sum(),t3[sub&~m].mean()))
# permutation on the EV gap itself
lab=bookr; idx=np.argsort(rng.random((TRIALS,n)),axis=1); P=lab[idx]
k=m.sum(); s=P.dot(m.astype(float)); dp=s/k-(lab.sum()-s)/(n-k)
o=lab[m].mean()-lab[~m].mean()
print("  permutation on the EV GAP (book R): %+.4fR, p=%.4f" % (o,(np.sum(np.abs(dp)>=abs(o))+1)/(TRIALS+1)))
lab=t3; P=lab[idx]; s=P.dot(m.astype(float)); dp=s/k-(lab.sum()-s)/(n-k)
o=lab[m].mean()-lab[~m].mean()
print("  permutation on the EV GAP (3R tgt): %+.4fR, p=%.4f" % (o,(np.sum(np.abs(dp)>=abs(o))+1)/(TRIALS+1)))
# monthly greens for the prop-eval bar
import collections
def months(arr,mask):
    b=collections.defaultdict(float)
    for i,r in enumerate(kept):
        if mask[i]: b[r["day"][:7]]+=arr[i]
    return sum(1 for v in b.values() if v>0), len(b)
for nm2,arr in [("book",bookr),("3R",t3)]:
    print("  months green %s: ALL %d/%d | KEEP %d/%d" % (nm2,*months(arr,np.ones(n,bool)),*months(arr,~m)))
