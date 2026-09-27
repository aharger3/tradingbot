"""v3-a2: rule-based S detector. Paper research only. Stocks 1-min (data_archive)."""
import sys, os, json, glob, re, random, itertools, collections as C
import pandas as pd, numpy as np
R=r"C:\Users\aharg\Desktop\Projects\tradingbot\research"; ROOT=os.path.dirname(R)
OUT=os.path.join(R,"agent_runs","v3-a2-s-detector")
sys.path.insert(0,R); sys.path.insert(0,ROOT)
import build_deck as bd, grade_read as gr
ARCH=os.path.join(ROOT,"data_archive")
random.seed(7)
# ---------- marks
def hm(s):
    m=re.search(r"(\d{1,2}):(\d{2})",str(s)); 
    if not m: return None
    h,mi=int(m.group(1)),int(m.group(2))
    if h<9 or h>15: return None
    return h*60+mi-570
marks=[]; agree=[0,0]
for p in bd.mark_sources():
    if not os.path.exists(p): continue
    for r in bd._rows(p):
        try: g=gr.read_grade(r)
        except Exception: g=None
        if not g: continue
        g=str(g).strip().upper()[:1]
        if g not in "SABC": continue
        sym=r.get("symbol"); d=r.get("day") or r.get("date")
        if not sym or not d: continue
        d=str(d)[:10]
        m=None
        for f in ("entry_t","entry_time","et","eng_et","entry_minute"):
            if r.get(f) is not None:
                m=hm(r[f]) if f!="entry_minute" else (hm(r[f]) if ":" in str(r[f]) else None)
                if m is not None: break
        if m is not None and isinstance(r.get("entry_i"),int):
            agree[0]+=1; agree[1]+= abs(r["entry_i"]-m)<=1
        if m is None and isinstance(r.get("entry_i"),int): m=r["entry_i"]
        sd=str(r.get("side") or r.get("direction") or r.get("eng_side") or "").lower()
        side=1 if sd[:1] in ("l","b","u") else (-1 if sd[:1] in ("s","d") else 0)
        if m is None or m<0 or m>390: continue
        marks.append((sym.upper(),d,m,side,g))
# dedupe: best grade per (sym,d,m)
best={}
for sym,d,m,side,g in marks:
    k=(sym,d,m); o=best.get(k)
    if o is None or "SABC".index(g)<"SABC".index(o[1]) or (o[0]==0 and side): best[k]=(side,g)
marks=[(k[0],k[1],k[2],v[0],v[1]) for k,v in best.items()]
print("entry_i vs time agree", agree, "marks w/ time", C.Counter(x[4] for x in marks))
# ---------- bars
_cache={}
def day_bars(sym,d):
    k=(sym,d)
    if k in _cache: return _cache[k]
    f=os.path.join(ARCH,sym,d+".csv")
    if not os.path.exists(f): _cache[k]=None; return None
    df=pd.read_csv(f)
    ts=pd.to_datetime(df["Datetime"].astype(str).str[:19],errors="coerce")
    mm=(ts.dt.hour*60+ts.dt.minute-570).values
    o,h,l,c=[df[x].values.astype(float) for x in ("Open","High","Low","Close")]
    pre=(mm<0)&(mm>=-330)
    rth=(mm>=0)&(mm<390)
    res=dict(m=mm[rth],o=o[rth],h=h[rth],l=l[rth],c=c[rth],
             pmh=h[pre].max() if pre.any() else None, pml=l[pre].min() if pre.any() else None,
             rh=h[rth].max() if rth.any() else None, rl=l[rth].min() if rth.any() else None)
    if len(res["m"])<60: res=None
    _cache[k]=res; return res
def days_of(sym): return sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(ARCH,sym,"*.csv")))
PREV={}
def prevday(sym,d):
    if sym not in PREV: PREV[sym]=days_of(sym)
    L=PREV[sym]; i=L.index(d) if d in L else -1
    return L[i-1] if i>0 else None
# ---------- detector
def detect(sym,d,P):
    """P: D disp ATR, T max minute, trig 'any'|'strong', lv 'orb'|'all', tol ATR touch tolerance."""
    b=day_bars(sym,d)
    if b is None: return []
    m,o,h,l,c=b["m"],b["o"],b["h"],b["l"],b["c"]; n=len(m)
    orw=m<5
    if orw.sum()<4: return []
    lv=[("ORH",1,h[orw].max()),("ORL",-1,l[orw].min())]
    if P["lv"]=="all":
        if b["pmh"] is not None: lv+= [("PMH",1,b["pmh"]),("PML",-1,b["pml"])]
        pd_=prevday(sym,d); pb=day_bars(sym,pd_) if pd_ else None
        if pb is not None: lv+= [("PDH",1,pb["rh"]),("PDL",-1,pb["rl"])]
    rng=h-l; out=[]
    for name,side,L in lv:
        # trade either direction through each level: break up (long) or break down (short)
        for sd in (1,-1):
            brk=None; ext=None
            for i in range(int(orw.sum()),n):
                if m[i]>P["T"]: break
                atr=rng[max(0,i-14):i].mean() if i>0 else rng[0]
                if atr<=0: continue
                beyond=(c[i]-L)*sd>0
                if brk is None:
                    if beyond and (c[i-1]-L)*sd<=0: brk=i; ext=(h[i] if sd==1 else l[i])
                    continue
                if not beyond: brk=None; continue   # closed back through: reset
                disp=((ext-L)*sd)/atr
                touch=((l[i]-L) if sd==1 else (L-h[i]))<=P["tol"]*atr and i>brk
                if touch and disp>=P["D"]:
                    body=abs(c[i]-o[i]); rg=max(rng[i],1e-9)
                    dirok=(c[i]-o[i])*sd>0
                    wick=(min(o[i],c[i])-l[i]) if sd==1 else (h[i]-max(o[i],c[i]))
                    pos=((c[i]-l[i])/rg) if sd==1 else ((h[i]-c[i])/rg)
                    strong=dirok and (body>=0.6*rg or (wick>=0.5*rg and pos>=0.6))
                    if P["trig"]=="any" or strong:
                        stop=(l[i] if sd==1 else h[i])-sd*0.01
                        out.append(dict(sym=sym,d=d,i=i,m=int(m[i]),side=sd,lvl=name,stop=stop,disp=round(disp,2)))
                        break
                ext=max(ext,h[i]) if sd==1 else min(ext,l[i])
    # keep first signal per side per day (one S per direction)
    out.sort(key=lambda x:x["m"]); seen=set(); res=[]
    for x in out:
        if x["side"] in seen: continue
        seen.add(x["side"]); res.append(x)
    return res
def sim(x):
    b=day_bars(x["sym"],x["d"]); m,o,h,l,c=b["m"],b["o"],b["h"],b["l"],b["c"]; sd=x["side"]; e_i=x["i"]+1
    if e_i>=len(m) or m[e_i]>=90: return None
    e=o[e_i]+sd*0.01; risk=(e-x["stop"])*sd
    if risk<=0.02 or risk>0.05*e: return None
    tgt=e+sd*2*risk; xp=None
    for j in range(e_i,len(m)):
        if m[j]>=90: xp=o[j]-sd*0.01; break
        if (sd==1 and l[j]<=x["stop"]) or (sd==-1 and h[j]>=x["stop"]):
            xp=(min(x["stop"],o[j]) if sd==1 else max(x["stop"],o[j]))-sd*0.01; break
        if (sd==1 and h[j]>=tgt+0.01) or (sd==-1 and l[j]<=tgt-0.01): xp=tgt; break
    if xp is None: xp=c[-1]-sd*0.01
    return ((xp-e)*sd-0.01)/risk   # 0.01/sh = $0.005/sh/side commission
# ---------- label eval
def evaluate(P, mk):
    days=C.defaultdict(list)
    for x in mk: days[(x[0],x[1])].append(x)
    tp_f=0; nf=0; nf_any=0; tp_any=0; S_hit=0; S_n=0
    for (sym,d),ms in days.items():
        fires=detect(sym,d,P)
        if day_bars(sym,d) is None: continue
        S=[x for x in ms if x[4]=="S"]; S_n+=len(S)
        for f in fires:
            nf+=1
            hit=[x for x in ms if abs(x[2]-f["m"])<=3 and (x[3]==0 or x[3]==f["side"])]
            if hit:
                nf_any+=1
                if any(x[4]=="S" for x in hit): tp_f+=1; tp_any+=1
        for x in S:
            if any(abs(x[2]-f["m"])<=3 and (x[3]==0 or x[3]==f["side"]) for f in fires): S_hit+=1
    prec=tp_f/nf if nf else 0; rec=S_hit/S_n if S_n else 0
    f1=2*prec*rec/(prec+rec) if prec+rec else 0
    return dict(fires=nf,prec=round(prec,3),S_share_of_marked_hits=round(tp_any/nf_any,3) if nf_any else None,
                recall=round(rec,3),f1=round(f1,3),S_n=S_n,S_hit=S_hit)
if __name__=="__main__":
    avail=[x for x in marks if os.path.exists(os.path.join(ARCH,x[0],x[1]+".csv"))]
    print("marks with bars", C.Counter(x[4] for x in avail))
    ds=sorted(set(x[1] for x in avail if x[4]=="S"))
    SPLIT=ds[int(len(ds)*0.6)]
    tr=[x for x in avail if x[1]<SPLIT]; te=[x for x in avail if x[1]>=SPLIT]
    print("SPLIT",SPLIT,"train",C.Counter(x[4] for x in tr),"test",C.Counter(x[4] for x in te))
    json.dump(dict(marks=avail,split=SPLIT),open(os.path.join(OUT,"marks.json"),"w"))
    grid=[dict(D=D,T=T,trig=tg,lv=lv,tol=tol) for D in (0,0.5,1.0,1.5) for T in (30,45,60,90) for tg in ("any","strong") for lv in ("orb","all") for tol in (0,0.25)]
    rows=[]
    for P in grid:
        e=evaluate(P,tr); rows.append((P,e)); 
    rows.sort(key=lambda r:-r[1]["f1"])
    for P,e in rows[:10]: print("TRAIN",P,e,flush=True)
    json.dump([dict(P=P,train=e) for P,e in rows],open(os.path.join(OUT,"grid_train.json"),"w"))
    bestP=rows[0][0]
    print("TEST best",bestP,evaluate(bestP,te))
    print("TEST S-note rule", evaluate(dict(D=1.0,T=30,trig="strong",lv="orb",tol=0),te))
    json.dump(dict(best=bestP),open(os.path.join(OUT,"best.json"),"w"))
