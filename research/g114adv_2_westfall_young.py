"""ADVERSARIAL: rebuild g114's 85 arms, then apply the CORRECT multiplicity
correction (Westfall-Young max-statistic on the same shuffle matrix), split by
year, and re-express every arm in EV per trade in R (Austin's ruling metric)."""
import json, os, sys
import numpy as np
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
POP = json.load(open(os.path.join(HERE, "_adv_g114_pop.json"), encoding="utf-8"))
kept = POP["rows"]; n = len(kept)
runner = np.array([1 if r["_mfe_alive"] >= 3.0 else 0 for r in kept])
print("n=%d runners=%d (%.1f%%)" % (n, runner.sum(), 100*runner.mean()))

CATEGORICAL = ["grade","sgrade","setup","setup_label","level","level_name","level_tf",
 "tier","pool","cls","side","dir","confluence","stopb","bias","aligned","vol_regime",
 "rangeb","gapb","dow","slot","spy_trend","entry_tf","bias_tf"]
MIN_N = 15

def cat_pairs(r):
    out=[]
    for f in CATEGORICAL:
        v=r.get(f)
        if v not in (None,"","n/a","None"): out.append((f,str(v)))
    et=r.get("et") or "09:30"
    out.append(("hour",et[:2])); out.append(("tripped_bucket","tripped=%s"%r.get("tripped")))
    out.append(("seq_bucket","seq%s"%r.get("seq")))
    for t in (r.get("tags") or ()): out.append(("tag",t))
    for d in (r.get("downgrades") or ()): out.append(("downgrade",d))
    return out

def numfeat(r):
    entry=r["entry"]; risk=r["_risk"]; et=r.get("et") or "09:30"
    mins=(int(et[:2])*60+int(et[3:5]))-(9*60+30)
    try: tn=int(r.get("tripped"))
    except (TypeError,ValueError): tn=None
    return {"s (engine score)":r.get("s"),"stop_pct":r.get("stop_pct"),
      "risk_dollars":risk,"entry_price":entry,"drange (day range %)":r.get("drange"),
      "dret (day return %)":r.get("dret"),"gap":r.get("gap"),"gap_abs":abs(r.get("gap",0.0)),
      "minutes_since_open":mins,"planned_rr (target R)":abs(r["target"]-entry)/risk,
      "level_dist_r":abs(entry-r.get("level_px",entry))/risk,"tripped_n":tn,
      "n_tags":len(r.get("tags") or []),"n_downgrades":len(r.get("downgrades") or [])}

cat_masks=defaultdict(lambda: np.zeros(n,dtype=bool))
for i,r in enumerate(kept):
    for k,v in cat_pairs(r): cat_masks[(k,v)][i]=True
numm={}
for r in kept:
    for k,v in numfeat(r).items(): numm.setdefault(k,[]).append(np.nan if v is None else float(v))

TRIALS=20000
rng=np.random.default_rng(20260903)
idx=np.argsort(rng.random((TRIALS,n)),axis=1)
P=runner[idx].astype(float)   # (TRIALS,n)
nR=runner.sum()

arms=[]  # (label, obs, perm_vector)
for (f,v),mask in sorted(cat_masks.items()):
    nm=int(mask.sum())
    if nm<MIN_N or (n-nm)<MIN_N: continue
    m=mask.astype(float)
    s1=P.dot(m); dperm=s1/nm-(nR-s1)/(n-nm)
    o1=runner[mask].sum(); obs=o1/nm-(nR-o1)/(n-nm)
    arms.append(("cat",f,v,nm,obs,dperm,mask))
for name,vals in numm.items():
    val=np.array(vals,dtype=float); good=~np.isnan(val)
    if good.sum()<2*MIN_N: continue
    vg=val[good]; pg=P[:,good]; ng=good.sum()
    nrp=pg.sum(axis=1); s=pg.dot(vg)
    dperm=s/nrp-(vg.sum()-s)/(ng-nrp)
    rg=runner[good]; s0=vg[rg==1].sum()
    obs=s0/rg.sum()-(vg.sum()-s0)/(ng-rg.sum())
    arms.append(("num",name,"",int(ng),obs,dperm,good))

print("arms rebuilt: %d (%d cat, %d num)" % (len(arms),
      sum(1 for a in arms if a[0]=="cat"), sum(1 for a in arms if a[0]=="num")))

# raw p + standardized statistic for Westfall-Young maxT
Z=np.zeros((TRIALS,len(arms))); zobs=np.zeros(len(arms)); praw=np.zeros(len(arms))
for j,(kind,f,v,nm,obs,dperm,_) in enumerate(arms):
    mu=dperm.mean(); sd=dperm.std(ddof=1)
    Z[:,j]=np.abs((dperm-mu)/sd); zobs[j]=abs((obs-mu)/sd)
    praw[j]=(np.sum(np.abs(dperm)>=abs(obs))+1)/(TRIALS+1)
maxZ=Z.max(axis=1)
pfwer=np.array([(np.sum(maxZ>=zobs[j])+1)/(TRIALS+1) for j in range(len(arms))])
bonf=0.05/len(arms)

order=np.argsort(praw)
print("\n%-14s %-26s %5s %9s %8s %9s" % ("field","value","n","diff","p_raw","p_FWER"))
for j in order[:14]:
    kind,f,v,nm,obs,_,_=arms[j]
    print("%-14s %-26s %5d %+9.4f %8.4f %9.4f" % (f,v[:26],nm,obs,praw[j],pfwer[j]))
print("\nBonferroni thr %.5f -> %d survive | Westfall-Young FWER<0.05 -> %d survive"
      % (bonf,(praw<bonf).sum(),(pfwer<0.05).sum()))
np.save(os.path.join(HERE,"_adv_zobs.npy"),zobs)
json.dump({"arms":[[a[1],a[2],a[3],float(a[4])] for a in arms],
  "p_raw":praw.tolist(),"p_fwer":pfwer.tolist(),"bonf":bonf},
  open(os.path.join(HERE,"_adv_g114_tests.json"),"w"),indent=1)
