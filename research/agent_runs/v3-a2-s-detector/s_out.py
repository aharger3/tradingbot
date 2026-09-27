import sys, os, json, random, collections as C, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s_det as S
random.seed(11)
cfg=json.load(open(os.path.join(S.OUT,"marks.json"))); SPLIT=cfg["split"]
P=json.load(open(os.path.join(S.OUT,"best.json")))["best"]
syms=sorted(d for d in os.listdir(S.ARCH) if d!="options" and os.path.isdir(os.path.join(S.ARCH,d)))
rows=[]; nulls=[]  # nulls: per fire list of candidate random R
for sym in syms:
    for d in S.days_of(sym):
        fs=S.detect(sym,d,P)
        for f in fs:
            r=S.sim(f)
            if r is None: continue
            b=S.day_bars(sym,d)
            alt=[]
            for i in range(5,len(b["m"])):
                if b["m"][i]>P["T"]: break
                g=dict(f); g["i"]=i; g["stop"]=(b["l"][i] if f["side"]==1 else b["h"][i])-f["side"]*0.01
                rr=S.sim(g)
                if rr is not None: alt.append(rr)
            rows.append(dict(sym=sym,d=d,m=f["m"],side=f["side"],R=r)); nulls.append(alt)
        S._cache.clear()
json.dump(rows,open(os.path.join(S.OUT,"fires_all.json"),"w"))
def st(xs):
    xs=np.array(xs); 
    if len(xs)==0: return "n=0"
    return f"n={len(xs)} mean={xs.mean():+.3f} win={np.mean(xs>0):.1%} t={xs.mean()/xs.std(ddof=1)*len(xs)**.5:.2f}"
R=np.array([x["R"] for x in rows]); dd=np.array([x["d"] for x in rows])
idx=[i for i,x in enumerate(rows) if nulls[i]]
def shuffle_p(sel):
    sel=[i for i in sel if nulls[i]]
    obs=np.mean([rows[i]["R"] for i in sel]); ge=0; ms=[]
    for _ in range(500):
        mm=np.mean([random.choice(nulls[i]) for i in sel]); ms.append(mm); ge+= mm>=obs
    return f"null mean={np.mean(ms):+.3f} p={(ge+1)/501:.3f}"
periods={"ALL":dd>="0","pre-v2 2024-01..08":dd<"2024-09-01","label-fit (<%s)"%SPLIT:dd<SPLIT,"held-out (>=%s)"%SPLIT:dd>=SPLIT}
for k,msk in periods.items():
    sel=list(np.where(msk)[0]); print(k, st(R[msk]), shuffle_p(sel))
    ds=sorted(set(dd[msk])); 
    if ds:
        h=ds[len(ds)//2]; print("   H1",st(R[msk&(dd<h)]),"H2",st(R[msk&(dd>=h)]),"half split",h)
etf=np.array([x["sym"] in ("SPY","QQQ","IWM") for x in rows])
for k,msk in (("SPY/QQQ/IWM",etf),("SPY/QQQ/IWM held-out",etf&(dd>=SPLIT)),("single stocks",~etf)):
    print(k, st(R[msk]))
print("syms",len(syms),"fire days", len(set((x["sym"],x["d"]) for x in rows)))
