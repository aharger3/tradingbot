"""v2-s01: measure Austin's S / one-off(A) / two-off(C) marked signals on 1-min bars.
Match mark -> engine candidate (same sym-day, same side, +-3 min) for level/stop (t04 method).
Features from bars; outcome = t04 honest rig (next-bar open +$0.01, intrabar stop, 2R, flat 11:00, $0.005/sh/side).
Read-only."""
import os,sys,json,gzip,re,random,statistics as st,collections as C,math
ROOT=r"C:\Users\aharg\Desktop\Projects\tradingbot"; os.chdir(ROOT); sys.path.insert(0,"research")
sys.path.insert(0,r"research\agent_runs\t04-his-eye-test")
import marks_pool as mp, build_deck as bd
OUT=r"research\agent_runs\v2-s01-s-trades"
random.seed(11)
B=json.load(gzip.open("research/tape/baseline_2026-09-13.json.gz"))["trades"]
def mins(hm): h,m=hm.split(":")[:2]; return int(h)*60+int(m)
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
                c=ln.split(",");m=mins(c[0][11:16])
                if 570<=m<960: out[m]=(float(c[1]),float(c[2]),float(c[3]),float(c[4]))
    _bc[k]=out; return out
SL=0.01; COM=0.005
def sim(b,sig_m,long,stop,flat_m=660,rr=2.0):
    if not b or sig_m+1 not in b or sig_m+1>=flat_m: return None
    o=b[sig_m+1][0]; fill=o+SL if long else o-SL
    risk=(fill-stop) if long else (stop-fill)
    if risk<=0 or risk<0.0005*fill: return None
    tgt=fill+rr*risk if long else fill-rr*risk; ex=None
    for m in range(sig_m+1,flat_m):
        if m not in b: continue
        O,H,L,Cl=b[m]; first=(m==sig_m+1)
        if long:
            if not first and O<=stop: ex=O-SL;break
            if L<=stop: ex=stop-SL;break
            if H>tgt: ex=tgt;break
        else:
            if not first and O>=stop: ex=O+SL;break
            if H>=stop: ex=stop+SL;break
            if L<tgt: ex=tgt;break
    if ex is None:
        ms=[m for m in b if m>=flat_m]; ex=b[min(ms)][0] if ms else b[max(b)][3]
        ex=ex-SL if long else ex+SL
    return ((ex-fill) if long else (fill-ex)-0)-2*COM if False else (((ex-fill) if long else (fill-ex))-2*COM)/risk
cand=C.defaultdict(list)
for t in B:
    if t["et"]>="10:59": continue
    cand[(t["sym"],t["day"])].append(t)
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
RANK={"S":0,"A":1,"B":2,"C":3}
marks={}; stat=C.Counter(); rawg=C.Counter()
for p in bd.mark_sources():
    for r in bd._rows(p):
        k=mp._judgement_key(r); g=mp.row_grade(r)
        if not k or g is None: continue
        g=str(g).upper()
        if g not in RANK: continue
        rawg[g]+=1
        mm=mark_minute(r)
        if mm is None: stat["no_time_"+g]+=1; continue
        sym,day=k.split("_",1); sd=mark_side(r); best=None
        for t in cand.get((sym,day),[]):
            if sd is not None and (t["dir"]=="call")!=sd: continue
            d=abs(mins(t["et"])-mm)
            if d<=3 and (best is None or d<best[0]): best=(d,t)
        if not best: stat["unmatched_"+g]+=1; continue
        stat["matched_"+g]+=1; t=best[1]; cid=id(t)
        if cid not in marks or RANK[g]<RANK[marks[cid][0]]: marks[cid]=(g,t,mp._relname(p))
print(stat, rawg)
def classify_setup(t):
    lab=(t.get("setup_label") or ""); lv=(t.get("level") or "").lower()
    orb=lv.startswith("or ")
    ocr=("OCR" in lab.upper()) or t["setup"]=="one_candle_rule"
    if t["setup"]=="reentry_84_rule": return "84%"
    if orb and ocr: return "ORB+OCR"
    if orb: return "ORB"
    if ocr and t["setup"]=="one_candle_rule": return "OCR"
    if ocr: return "BR+OCR(" + ("his" if lv in("pdh","pdl","pm high","pm low","prior day high","prior day low") else "lvl") + ")"
    return "BR-other"
def feats(t):
    b=bars(t["sym"],t["day"])
    if not b: return None
    sig=mins(t["et"]); L=t["dir"]=="call"; lvl=t.get("level_px")
    if lvl is None or sig not in b: return None
    lvl=float(lvl); s=1 if L else -1
    rng=[b[m][1]-b[m][2] for m in range(570,sig) if m in b]
    atr=st.mean(rng[-14:]) if len(rng)>=3 else st.mean([b[m][1]-b[m][2] for m in range(570,min(sig+1,575)) if m in b])
    if atr<=0: return None
    # break bar: most recent bar <sig whose close is beyond level and prior close not (or first bar)
    brk=None
    for m in range(sig,569,-1):
        if m not in b: continue
        c=b[m][3]; pm=m-1
        pc=b[pm][3] if pm in b else b[m][0]
        if s*(c-lvl)>0 and s*(pc-lvl)<=0: brk=m;break
    if brk is None: return {"atr":atr,"brk":None}
    # impulse leg: peak excursion beyond level between brk and sig
    ext=[(s*((b[m][1] if L else b[m][2])-lvl),m) for m in range(brk,sig+1) if m in b]
    peak,pk_m=max(ext)
    disp=peak
    strong=sum(1 for m in range(brk,pk_m+1) if m in b and s*(b[m][3]-b[m][0])>=0.6*(b[m][1]-b[m][2])>0)
    bo,bh,bl,bc=b[brk]; brk_body=s*(bc-bo)/atr
    # retest window: after brk to sig inclusive
    lows=[s*((b[m][2] if L else b[m][1])-lvl) for m in range(brk+1,sig+1) if m in b]
    closes_thru=any(s*(b[m][3]-lvl)<0 for m in range(brk+1,sig+1) if m in b)
    mind=min(lows) if lows else float("nan")
    if closes_thru: rt="close-through"
    elif lows and mind<=0: rt="wick-touch"
    elif lows and mind<=0.25*atr: rt="near(<=.25ATR)"
    else: rt="no-touch"
    # retest bar = bar of min distance
    rt_m=None
    if lows:
        rt_m=[m for m in range(brk+1,sig+1) if m in b][lows.index(mind)]
    fb=None
    for m in range(570,sig+1):
        if m not in b: continue
        pc=b[m-1][3] if (m-1) in b else b[m][0]
        if s*(b[m][3]-lvl)>0 and s*(pc-lvl)<=0: fb=m;break
    ct_first=any(s*(b[m][3]-lvl)<0 for m in range(fb+1,sig+1) if m in b) if fb is not None else None
    o,h,l,c=b[sig]; r_=h-l or 1e-9
    body=s*(c-o)/r_; low_w=((min(o,c)-l) if L else (h-max(o,c)))/r_; up_w=((h-max(o,c)) if L else (min(o,c)-l))/r_
    closepos=((c-l) if L else (h-c))/r_
    if body<0: ct="against"
    elif low_w>=0.5 and closepos>=0.6: ct="hammer/pin"
    elif body>=0.6: ct="strong-body"
    elif body<0.25: ct="doji"
    else: ct="normal"
    return {"atr":atr,"brk":brk,"brk_tso":brk-570,"disp_pts":disp,"disp_atr":disp/atr,"disp_pct":100*disp/lvl,"strong_n":strong,
            "brk_body_atr":brk_body,"retest":rt,"retest_dist_atr":mind/atr if lows else None,"bars_brk_to_sig":sig-brk,
            "bars_rt_to_sig":(sig-rt_m) if rt_m else None,"trig":ct,"trig_body":body,"trig_wick":low_w,"trig_range_atr":r_/atr,"closed_thru_since_first_break":ct_first,"n_breaks_first_to_sig":(brk!=fb)}
rows=[]
for cid,(g,t,src) in marks.items():
    f=feats(t); b=bars(t["sym"],t["day"])
    R=sim(b,mins(t["et"]),t["dir"]=="call",float(t["stop"])) if b else None
    R1=sim(b,mins(t["et"]),t["dir"]=="call",float(t["stop"]),flat_m=645) if b else None
    rows.append({"g":g,"sym":t["sym"],"day":t["day"],"et":t["et"],"tso":mins(t["et"])-570,"side":"L" if t["dir"]=="call" else "S",
                 "setup":classify_setup(t),"level":t.get("level"),"lvl":t.get("level_px"),"tags":t.get("tags"),"R":R,"R1045":R1,"src":src,**(f or {})})
json.dump(rows,open(os.path.join(OUT,"s_rows.json"),"w"),default=str,indent=0)
allr=[]
for (sym,day),cs in cand.items():
    b=bars(sym,day)
    if not b: continue
    for t in cs:
        f=feats(t)
        if not f or f.get("brk") is None: continue
        R=sim(b,mins(t["et"]),t["dir"]=="call",float(t["stop"]))
        if R is None: continue
        allr.append([sym,day,mins(t["et"])-570,classify_setup(t),round(f["disp_atr"],3),f["retest"],f["trig"],f["closed_thru_since_first_break"],f["bars_brk_to_sig"],round(R,4),t["status"]])
    if len(_bc)>3000: _bc.clear()
json.dump(allr,open(os.path.join(OUT,"all_cands.json"),"w"))
print("all",len(allr))
print("rows",len(rows),C.Counter(r["g"] for r in rows))
