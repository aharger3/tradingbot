import json, os, sys, statistics, importlib
import numpy as np
ROOT=r"C:\Users\aharg\Desktop\Projects\tradingbot"
sys.path.insert(0,ROOT)
from research.omen_metrics import ev_r_scoreboard, min_risk_floor
G=importlib.import_module("research.g80_ordertype_grid")
g86=importlib.import_module("research.g86_honest_ceiling")
blob=json.load(open(os.path.join(ROOT,"research","bt2y_trades_retest_on.json"),encoding="utf-8"))
allrows=blob["trades"]; sessions=blob["meta"].get("sessions")
byday=g86.candidates(allrows); firsts=[byday[d][0] for d in sorted(byday) if byday[d]]
WIN_END="11:00:00"; OR_BARS=15
prep=[]
for r in firsts:
    entry,stop=r["entry"],r["stop"]; risk=abs(entry-stop)
    if risk<min_risk_floor(entry): continue
    i=r.get("entry_i"); bars,pdh,pdl,pmh,pml=G.day_pack(r["sym"],r["day"])
    if not bars or i is None or i>=len(bars): continue
    long=r["dir"]=="call"; sign=1.0 if long else -1.0
    orh=orl=None
    if i>=OR_BARS and len(bars)>OR_BARS:
        orh=max(c.high for c in bars[:OR_BARS]); orl=min(c.low for c in bars[:OR_BARS])
    named={"PDH":pdh,"PMH":pmh,"ORH":orh} if long else {"PDL":pdl,"PML":pml,"ORL":orl}
    prep.append(dict(sym=r["sym"],day=r["day"],i=i,entry=entry,risk=risk,long=long,sign=sign,
                     named=named,flat=entry+sign*2.0*risk,bars=bars))
print("n=",len(prep))
def snapf(px,entry,risk,long,named,tol_r,step=1.00):
    tol=tol_r*risk; subs=[]; k0=round(px/step)
    for dk in (-1,0,1):
        wd=(k0+dk)*step
        if abs(wd-px)<=tol: subs.append(("whole$",wd,abs(wd-px)))
    for nm,v in named.items():
        if v is not None and abs(v-px)<=tol: subs.append((nm,v,abs(v-px)))
    if not subs: return px,None
    best=min(s[2] for s in subs); tied=[s for s in subs if abs(s[2]-best)<1e-9]
    tied.sort(key=lambda s:(0 if s[0]!="whole$" else 1, abs(s[1]-entry)))
    return tied[0][1],tied[0][0]
def walk_t(p,tgt):
    bars=p["bars"];entry=p["entry"];risk=p["risk"];long=p["long"];last=entry
    for b in bars[p["i"]+1:]:
        if b.timestamp>WIN_END: break
        last=b.close
        adv=((entry-b.low) if long else (b.high-entry))/risk
        if adv>=1.0: return -1.0,"stop",False
        px=b.high if long else b.low
        if (px>=tgt) if long else (px<=tgt):
            return ((tgt-entry)/risk if long else (entry-tgt)/risk),"target",abs(px-tgt)<1e-9
    return ((last-entry) if long else (entry-last))/risk,"eod",False
def walk(p,t): return walk_t(p,t)[0]
def pci(d,n=10000,seed=20260903):
    d=np.asarray(d,float); rng=np.random.default_rng(seed)
    m=rng.integers(0,len(d),size=(n,len(d))); mm=d[m].mean(axis=1); mm.sort()
    return float(d.mean()),float(mm[int(.025*n)]),float(mm[int(.975*n)-1])
# tie diagnostic
for dd in (2.0000,2.0040):
    nt=ntie=0; rs=[]
    for p in prep:
        r,w,t=walk_t(p,p["entry"]+p["sign"]*dd*p["risk"]); rs.append(r)
        if w=="target": nt+=1; ntie+=t
    print("flat %.4fR: targets=%d exact-tie(high==tgt)=%d ev_r=%.4f"%(dd,nt,ntie,statistics.fmean(rs)))
print("flat-2R target price is an exact cent in %d/%d rows"%(
    sum(1 for p in prep if abs(round(p["flat"]*100)-p["flat"]*100)<1e-6),len(prep)))
base=[walk(p,p["flat"]) for p in prep]
print("\n=== CORRECTED control: same avg distance but ROUNDED TO THE CENT ===")
print("%-5s %8s %8s %10s %-20s %10s %-20s"%("tol","ev_LVL","ev_CTLc","d_vs_ctlc","95%CI","d_vs_flat2R","95%CI"))
TOLS=[round(0.05*k,2) for k in range(11)]
store={}
for tol in TOLS:
    lv=[];dist=[]
    for p in prep:
        t,s=snapf(p["flat"],p["entry"],p["risk"],p["long"],p["named"],tol)
        lv.append(walk(p,t)); dist.append(p["sign"]*(t-p["entry"])/p["risk"])
    ad=statistics.fmean(dist)
    ctc=[walk(p,round((p["entry"]+p["sign"]*ad*p["risk"])*100)/100) for p in prep]
    o1,l1,h1=pci([a-b for a,b in zip(lv,ctc)]); o2,l2,h2=pci([a-b for a,b in zip(lv,base)])
    store[tol]=(lv,ctc)
    print("%-5.2f %8.4f %8.4f %+10.4f [%+.4f,%+.4f] %+10.4f [%+.4f,%+.4f]"%(
        tol,statistics.fmean(lv),statistics.fmean(ctc),o1,l1,h1,o2,l2,h2))
import pickle; pickle.dump({"store":store,"base":base,
  "meta":[(p["day"],p["sym"]) for p in prep]},open("zz_tl.pkl","wb"))
