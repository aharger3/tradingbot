"""t04 his-eye test: do Austin's S/A/C marks pick better engine signals than unmarked ones?
Honest rig: fill = open of bar after signal bar +$0.01 adverse; engine structural stop, intrabar,
gap-through exits at open -$0.01; 2R limit needs trade-through; flat at 11:00 open (EOD variant too);
commission $0.005/sh/side. R net at 1R=$1000. Read-only on repo data."""
import os,sys,json,gzip,re,random,statistics as st,collections as C,math
ROOT=r"C:\Users\aharg\Desktop\Projects\tradingbot"; os.chdir(ROOT); sys.path.insert(0,"research")
import marks_pool as mp, build_deck as bd
OUT=os.path.join(ROOT,r"research\agent_runs\t04-his-eye-test")
random.seed(7)
B=json.load(gzip.open("research/tape/baseline_2026-09-13.json.gz"))["trades"]
def mins(hm): h,m=hm.split(":")[:2]; return int(h)*60+int(m)
# ---------- bars ----------
_bc={}
def bars(sym,day):
    k=(sym,day)
    if k in _bc: return _bc[k]
    p=os.path.join("data_archive",sym,day+".csv"); out=None
    if os.path.exists(p):
        out={}
        with open(p) as f:
            next(f)
            for ln in f:
                c=ln.split(",");t=c[0][11:16]; m=mins(t)
                if 570<=m<960: out[m]=(float(c[1]),float(c[2]),float(c[3]),float(c[4]))
    if len(_bc)>4000: _bc.clear()
    _bc[k]=out; return out
SL=0.01; COM=0.005
def sim(sym,day,sig_m,long,stop,flat_m=660):
    b=bars(sym,day)
    if not b or sig_m+1 not in b or sig_m+1>=flat_m: return None
    o=b[sig_m+1][0]; fill=o+SL if long else o-SL
    risk=(fill-stop) if long else (stop-fill)
    if risk<=0 or risk<0.0005*fill: return None
    tgt=fill+2*risk if long else fill-2*risk
    ex=None; how=None
    for m in range(sig_m+1,flat_m):
        if m not in b: continue
        O,H,L,Cl=b[m]; first=(m==sig_m+1)
        if long:
            if not first and O<=stop: ex=O-SL;how="gap";break
            if L<=stop: ex=stop-SL;how="stop";break
            if H>tgt and not (first and False): ex=tgt;how="tgt";break
        else:
            if not first and O>=stop: ex=O+SL;how="gap";break
            if H>=stop: ex=stop+SL;how="stop";break
            if L<tgt: ex=tgt;how="tgt";break
    if ex is None:
        ms=[m for m in b if m>=flat_m]
        if ms: ex=b[min(ms)][0]; 
        else: ex=b[max(b)][3]
        ex=ex-SL if long else ex+SL; how="time"
    pps=(ex-fill) if long else (fill-ex)
    return (pps-2*COM)/risk, how, risk/fill
# ---------- engine candidates ----------
cand=C.defaultdict(list)
for t in B:
    if t["et"]>="10:59": continue
    cand[(t["sym"],t["day"])].append(t)
print("cand sym-days",len(cand))
def R_of(t,flat=660):
    if "_r" not in t: t["_r"]={}
    if flat not in t["_r"]:
        t["_r"][flat]=sim(t["sym"],t["day"],mins(t["et"]),t["dir"]=="call",float(t["stop"]),flat)
    return t["_r"][flat]
# ---------- his marks at signal level ----------
TK=["entry_t","entry_time","et","eng_et","entry_et","setup_et","tod","entry_minute"]
def mark_minute(r):
    for f in ("entry_i","eng_entry_i"):
        v=r.get(f)
        if isinstance(v,(int,float)) and 0<=v<390: return 570+int(v)
    for f in TK:
        v=r.get(f)
        if isinstance(v,str):
            m=re.search(r"(\d{1,2}):(\d{2})",v)
            if m: return int(m.group(1))*60+int(m.group(2))
    return None
def mark_side(r):
    for f in ("side","direction","eng_side","dir","setup_dir"):
        v=str(r.get(f) or "").lower()
        if v in("call","long","bull","l","buy","up","bullish","c"): return True
        if v in("put","short","bear","s","sell","down","bearish","p"): return False
    return None
RANK={"S":0,"A":1,"B":2,"C":3,"none":4}
def bucket(g):
    g=str(g).upper()
    if g in("S","A","B","C"): return g
    return "none"
marks={}  # candidate id -> best grade
msrc={}
mstat=C.Counter()
for p in bd.mark_sources():
    for r in bd._rows(p):
        k=mp._judgement_key(r); g=mp.row_grade(r)
        if not k or g is None: continue
        g=bucket(g); mm=mark_minute(r)
        if mm is None: mstat["no_time"]+=1; continue
        sym,day=k.split("_",1); cs=cand.get((sym,day),[])
        sd=mark_side(r)
        best=None
        for t in cs:
            if sd is not None and (t["dir"]=="call")!=sd: continue
            d=abs(mins(t["et"])-mm)
            if d<=3 and (best is None or d<best[0]): best=(d,t)
        if not best: mstat["unmatched"]+=1; continue
        mstat["matched"]+=1
        t=best[1]; cid=id(t)
        msrc.setdefault(cid,set()).add(mp._relname(p))
        if cid not in marks or RANK[g]<RANK[marks[cid][0]]: marks[cid]=(g,t)
print(mstat, C.Counter(v[0] for v in marks.values()))
pool=mp.canonical_pool()
judged_days={(v.symbol,v.date) for v in pool.values()}
# ---------- build signal table ----------
def slot(et):
    m=mins(et)
    return "09:30-44" if m<585 else "09:45-59" if m<600 else "10:00-29" if m<630 else "10:30-59"
ETF={"SPY","QQQ","IWM","DIA"}
def feats(t):
    return {"slot":slot(t["et"]),"dir":t["dir"],"spy_trend":t.get("spy_trend"),"aligned":t.get("aligned"),
            "vol_regime":t.get("vol_regime"),"gap":t.get("gapb"),"range":t.get("rangeb"),"eng_grade":t.get("grade"),
            "setup":t.get("setup"),"etf":"ETF" if t["sym"] in ETF else "stock","year":t["day"][:4],
            "seq":"first" if t.get("seq")==1 else "later","stopb":t.get("stopb"),"bias":t.get("bias")}
rows=[]
for (sym,day),cs in cand.items():
    for t in cs:
        r=R_of(t)
        if r is None: continue
        g=marks.get(id(t),(None,))[0]
        lab=g if g else ("unmarked_judgedday" if (sym,day) in judged_days else "unmarked")
        rows.append({"sym":sym,"day":day,"et":t["et"],"lab":lab,"R":r[0],"how":r[1],"status":t["status"],**feats(t)})
print("rows",len(rows))
# EOD variant for marked + stratified pools
# ---------- stats helpers ----------
def mean(x): return sum(x)/len(x) if x else float("nan")
def summ(rs):
    x=[r["R"] for r in rs]
    return {"n":len(x),"win":round(100*sum(v>0 for v in x)/len(x),1) if x else None,"meanR":round(mean(x),3) if x else None}
def boot_ci(rs,n=2000):
    byd=C.defaultdict(list)
    for r in rs: byd[(r["sym"],r["day"])].append(r["R"])
    ks=list(byd); ms=[]
    for _ in range(n):
        s=[v for k in random.choices(ks,k=len(ks)) for v in byd[k]]; ms.append(mean(s))
    ms.sort(); return (round(ms[int(.025*n)],3),round(ms[int(.975*n)],3))
unm=[r for r in rows if r["lab"]=="unmarked"]
strat=C.defaultdict(list)
for r in unm: strat[(r["sym"],r["slot"],r["dir"])].append(r["R"])
strat2=C.defaultdict(list)
for r in unm: strat2[(r["slot"],r["dir"])].append(r["R"])
def strat_null(rs,n=2000):
    """day-shuffle: each marked signal replaced by a random unmarked engine signal, same symbol+slot+side, other day"""
    pools=[strat.get((r["sym"],r["slot"],r["dir"])) or strat2[(r["slot"],r["dir"])] for r in rs]
    obs=mean([r["R"] for r in rs]); ge=0; nm=[]
    for _ in range(n):
        m=mean([random.choice(p) for p in pools]); nm.append(m); ge+= m>=obs
    return round(mean(nm),3), round((ge+1)/(n+1),4)
def label_perm(rs,a,b,n=5000):
    """cluster (symbol-day) label permutation: mean(a)-mean(b)"""
    rs=[r for r in rs if r["lab"] in a|b]
    byd=C.defaultdict(list)
    for r in rs: byd[(r["sym"],r["day"])].append(r)
    ks=list(byd); labs=[ "a" if any(r["lab"] in a for r in byd[k]) else "b" for k in ks]
    def stat(L):
        xa=[r["R"] for k,l in zip(ks,L) if l=="a" for r in byd[k] if r["lab"] in a|b]
        xb=[r["R"] for k,l in zip(ks,L) if l=="b" for r in byd[k] if r["lab"] in a|b]
        return mean(xa)-mean(xb)
    obs=stat(labs); ge=0
    for _ in range(n):
        L=labs[:]; random.shuffle(L); ge+= stat(L)>=obs
    return round(obs,3), round((ge+1)/(n+1),4)
def trend_perm(rs,n=5000):
    sc={"S":4,"A":3,"B":2.5,"C":2,"none":1}
    rs=[r for r in rs if r["lab"] in sc]
    x=[sc[r["lab"]] for r in rs]; y=[r["R"] for r in rs]
    def cov(x,y):
        mx,my=mean(x),mean(y); return sum((a-mx)*(b-my) for a,b in zip(x,y))
    obs=cov(x,y); ge=0
    for _ in range(n):
        xx=x[:]; random.shuffle(xx); ge+= cov(xx,y)>=obs
    sx=math.sqrt(sum((a-mean(x))**2 for a in x)); sy=math.sqrt(sum((b-mean(y))**2 for b in y))
    return round(obs/(sx*sy),3), round((ge+1)/(n+1),4)
res={}
marked=[r for r in rows if r["lab"] in RANK]
alld=sorted({r["day"] for r in marked}); mid=alld[len(alld)//2]
res["mid_date"]=mid
tab={}
for lab in ["S","A","B","C","none","unmarked_judgedday","unmarked"]:
    rs=[r for r in rows if r["lab"]==lab]
    if not rs: continue
    d=summ(rs); d["ci"]=boot_ci(rs,1000) if lab not in("unmarked",) else None
    d["h1"]=summ([r for r in rs if r["day"]<mid])["meanR"]; d["h2"]=summ([r for r in rs if r["day"]>=mid])["meanR"]
    if lab in RANK: d["null_mean"],d["p_vs_dayshuffle"]=strat_null(rs)
    d["tgt%"]=round(100*sum(r["how"]=="tgt" for r in rs)/len(rs),1)
    tab[lab]=d
# engine-eligible only (status fired/halted = engine would alert)
elig=[r for r in rows if r["status"] in("fired","halted")]
tab["unmarked_engine_eligible"]=summ([r for r in elig if r["lab"]=="unmarked"])
res["ladder"]=tab
res["S_vs_Cnone"]=label_perm(marked,{"S"},{"C","none"})
res["S_vs_A"]=label_perm(marked,{"S"},{"A"})
res["SA_vs_Cnone"]=label_perm(marked,{"S","A"},{"C","none"})
res["trend_rho_p"]=trend_perm(marked)
for h,sel in (("h1",lambda r:r["day"]<mid),("h2",lambda r:r["day"]>=mid)):
    mh=[r for r in marked if sel(r)]
    res["trend_"+h]=trend_perm(mh,2000); res["S_vs_Cnone_"+h]=label_perm(mh,{"S"},{"C","none"},2000)
# ---------- sub-patterns: S (and S+A) vs day-shuffle null within slice ----------
subs=[]
FE=["slot","dir","spy_trend","aligned","vol_regime","gap","range","eng_grade","setup","etf","year","seq","stopb","bias"]
for grp,labs in (("S",{"S"}),("S+A",{"S","A"})):
    base=[r for r in rows if r["lab"] in labs]
    for f in FE:
        for v in sorted({str(r[f]) for r in base}):
            rs=[r for r in base if str(r[f])==v]
            if len(rs)<15: continue
            nmean,p=strat_null(rs,1000)
            h1=[r["R"] for r in rs if r["day"]<mid]; h2=[r["R"] for r in rs if r["day"]>=mid]
            subs.append({"grp":grp,"feat":f,"val":v,"n":len(rs),"meanR":round(mean([r["R"] for r in rs]),3),
                         "null":nmean,"p":p,"h1":round(mean(h1),3) if h1 else None,"h2":round(mean(h2),3) if h2 else None,"nh1":len(h1),"nh2":len(h2)})
# BH
ps=sorted(range(len(subs)),key=lambda i:subs[i]["p"]); m=len(subs); prev=1
for rank,i in reversed(list(enumerate(ps,1))):
    q=min(prev,subs[i]["p"]*m/rank); subs[i]["q"]=round(q,3); prev=q
res["n_slices"]=m
res["subs_top"]=sorted(subs,key=lambda s:s["p"])[:20]
# ---------- day level: canonical pool grade vs first engine-eligible signal of the day ----------
first={}
for r in sorted(rows,key=lambda r:r["et"]):
    k=(r["sym"],r["day"])
    if r["status"] in("fired","halted") and k not in first: first[k]=r
dl={}
for k,r in first.items():
    e=pool.get(k[0]+"_"+k[1]); lab=e.grade if e else "unjudged"
    if e and e.grade=="none": lab="none_X" if set(e.raw_grades)<={"X"} else "none_explicit"
    dl.setdefault(lab,[]).append(dict(r,lab=lab))
res["daylevel"]={lab:{**summ(v),"h1":summ([r for r in v if r["day"]<mid])["meanR"],"h2":summ([r for r in v if r["day"]>=mid])["meanR"]} for lab,v in dl.items()}
dall=[r for v in dl.values() for r in v]
res["day_S_vs_unjudged"]=label_perm(dall,{"S"},{"unjudged"},3000)
res["day_S_vs_notS_judged"]=label_perm(dall,{"S"},{"A","B","C","none_X","none_explicit"},3000)
# ---------- EOD-exit robustness for S/A/C/none ----------
eod={}
for lab in ["S","A","C","none"]:
    ts=[v[1] for v in marks.values() if v[0]==lab]
    x=[R_of(t,955) for t in ts]; x=[a[0] for a in x if a]
    eod[lab]={"n":len(x),"meanR":round(mean(x),3) if x else None}
xs=[]
for r in random.sample([t for cs in cand.values() for t in cs if id(t) not in marks and (t["sym"],t["day"]) not in judged_days],4000):
    a=R_of(r,955)
    if a: xs.append(a[0])
eod["unmarked_sample4000"]={"n":len(xs),"meanR":round(mean(xs),3)}
res["eod_exit"]=eod
# $/day for S signals
sess=len({t["day"] for t in B})
res["S_dollars_per_session"]=round(1000*sum(r["R"] for r in rows if r["lab"]=="S")/sess,1); res["sessions"]=sess
res["mark_match"]=dict(mstat); res["n_marked_signals"]=dict(C.Counter(v[0] for v in marks.values()))

# ---------- hindsight test: does the mark predict price AFTER the 11:00 chart edge he saw? ----------
def post(t):
    """fresh entry at 11:00 open, same side, same per-share risk, 2R/stop intrabar, flat 15:55"""
    b=bars(t["sym"],t["day"])
    if not b or 660 not in b: return None
    long=t["dir"]=="call"; o=b[660][0]; fill=o+SL if long else o-SL
    r0=abs(float(t["entry"])-float(t["stop"]))
    if r0<=0 or r0<0.0005*fill: return None
    stop=fill-r0 if long else fill+r0; tgt=fill+2*r0 if long else fill-2*r0; ex=None
    for m in range(660,955):
        if m not in b: continue
        O,H,L,Cl=b[m]
        if long:
            if m>660 and O<=stop: ex=O-SL;break
            if L<=stop: ex=stop-SL;break
            if H>tgt: ex=tgt;break
        else:
            if m>660 and O>=stop: ex=O+SL;break
            if H>=stop: ex=stop+SL;break
            if L<tgt: ex=tgt;break
    if ex is None:
        ms=[m for m in b if m>=955]; ex=(b[min(ms)][0] if ms else b[max(b)][3]); ex=ex-SL if long else ex+SL
    pps=(ex-fill) if long else (fill-ex)
    return (pps-2*COM)/r0
ph={}
for lab in ["S","A","C","none"]:
    ts=[v[1] for v in marks.values() if v[0]==lab]; x=[post(t) for t in ts]; x=[a for a in x if a is not None]
    ph[lab]={"n":len(x),"meanR":round(mean(x),3) if x else None,"win":round(100*sum(a>0 for a in x)/len(x),1) if x else None}
S_ts=[v[1] for v in marks.values() if v[0]=="S"]
sx=[a for a in (post(t) for t in S_ts) if a is not None]
um=[t for cs in cand.values() for t in cs if id(t) not in marks and (t["sym"],t["day"]) not in judged_days]
ux=[a for a in (post(t) for t in random.sample(um,5000)) if a is not None]
ph["unmarked_sample"]={"n":len(ux),"meanR":round(mean(ux),3)}
# perm: S vs unmarked sample
obs=mean(sx)-mean(ux); allx=sx+ux; ge=0
for _ in range(5000):
    random.shuffle(allx); ge+= (mean(allx[:len(sx)])-mean(allx[len(sx):]))>=obs
ph["S_minus_unmarked"]=round(obs,3); ph["p"]=round((ge+1)/5001,4)
res["post_1100"]=ph
# ---------- visible-future proxy: S edge vs minutes of chart he saw after the signal ----------
vf={}
for lab in ["S","none"]:
    rs=[r for r in rows if r["lab"]==lab]
    for b_,lo,hi in (("<=30 min seen",0,31),("31-60",31,61),(">60",61,999)):
        x=[r["R"] for r in rs if lo<=660-mins(r["et"])<hi]
        vf[lab+" "+b_]={"n":len(x),"meanR":round(mean(x),3) if x else None}
res["visible_future"]=vf
# ---------- per source (S rows) ----------
ps=C.defaultdict(list)
for cid,(g,t) in marks.items():
    r=R_of(t)
    if r is None: continue
    for s_ in msrc.get(cid,()): ps[(s_,g)].append(r[0])
res["per_source"]={f"{k[0]}|{k[1]}":{"n":len(v),"meanR":round(mean(v),3)} for k,v in sorted(ps.items()) if len(v)>=5}
json.dump(res,open(os.path.join(OUT,"eye_test.json"),"w"),indent=1,default=str)
print(json.dumps(res,indent=1,default=str))
