import csv,json,os,statistics,random,sys
from collections import defaultdict
exec(open(r"C:\Users\aharg\AppData\Local\Temp\claude\C--Users-aharg-Desktop-Projects-tradingbot\e36136ab-fd7a-4f0c-97a8-86b0ad6d542a\scratchpad\adv.py").read().split('blob=json.load')[0])
exec(open(r"C:\Users\aharg\AppData\Local\Temp\claude\C--Users-aharg-Desktop-Projects-tradingbot\e36136ab-fd7a-4f0c-97a8-86b0ad6d542a\scratchpad\adv3.py").read().split('blob=json.load')[0].split('exec(')[0].replace('import csv,json,os,statistics','') if False else "")
sys.path.insert(0,ROOT)
from research.omen_metrics import evaluate_prop_challenge, first_of_day_arm

def resim2(row,bars,fn,mode):
    i=row["entry_i"]
    if i>=len(bars): return None
    e=row["entry"]; lng=row["dir"]=="call"; tgt=row["target"]
    stop,_=fn(row,bars,i,e,lng)
    if stop is None: return None
    risk=abs(e-stop)
    if risk<=1e-9: return None
    if lng and stop>=e: return None
    if (not lng) and stop<=e: return None
    if risk<floor_(e): return None
    for j in range(i+1,len(bars)):
        _,o,h,l,c=bars[j]
        th=(h>=tgt) if lng else (l<=tgt)
        sh=((l<=stop) if lng else (h>=stop)) if mode=="touch" else ((c<=stop) if lng else (c>=stop))
        if sh:
            if mode=="honest": return dict(day=row["day"],r=((c-e)/risk if lng else (e-c)/risk),out="stop")
            return dict(day=row["day"],r=-1.0,out="stop")
        if th: return dict(day=row["day"],r=(((tgt-e)/risk) if lng else ((e-tgt)/risk)),out="target")
    c=bars[-1][4]
    return dict(day=row["day"],r=((c-e)/risk if lng else (e-c)/risk),out="scratch")

blob=json.load(open(BOOK,encoding="utf-8"))
allrows=blob["trades"]; sessions=blob["meta"]["sessions"]
traded=[r for r in allrows if r["status"]=="fired" and r.get("traded")]
firsts=first_of_day_arm(allrows)
FN=dict(VARIANTS)
KEY=["shipped_level","prior_candle_extreme","fixed_pct_0.25","entry_candle_extreme","atr_0.5x","fixed_pct_0.50","fixed_pct_1.00","atr_1.5x"]

# paired bootstrap: fixed_pct_0.25 vs shipped_level on rows BOTH can trade, per world
print("=== G. PAIRED TEST, fixed_pct_0.25 vs shipped_level, rows BOTH trade ===")
random.seed(20260903)
for mode in ("claim","honest","touch"):
    pa=[];pb=[]
    for row in traded:
        b=bars_for(row["sym"],row["day"])
        if not b: continue
        x=resim2(row,b,FN["fixed_pct_0.25"],mode); y=resim2(row,b,FN["shipped_level"],mode)
        if x and y: pa.append(x["r"]); pb.append(y["r"])
    d=[a-bq for a,bq in zip(pa,pb)]
    m=statistics.fmean(d); n=len(d)
    boots=[]
    for _ in range(2000):
        s=[d[random.randrange(n)] for _ in range(n)]
        boots.append(statistics.fmean(s))
    boots.sort()
    print("  %-7s n_pairs=%d  d_mean=%+.4fR  95%%CI [%+.4f, %+.4f]  %s"%(
        mode,n,m,boots[50],boots[1949],"SIGNIF" if boots[50]>0 or boots[1949]<0 else "not distinguishable from 0"))

print()
print("=== H. YEAR SPLIT in the honest and touch worlds ===")
def yr(d): return "Y1" if d<"2025-09-01" else "Y2"
print("%-22s | %8s %8s | %8s %8s"%("variant","honestY1","honestY2","touchY1","touchY2"))
for n in KEY:
    r={}
    for mode in ("honest","touch"):
        t=[]
        for row in traded:
            b=bars_for(row["sym"],row["day"])
            if not b: continue
            x=resim2(row,b,FN[n],mode)
            if x: t.append(x)
        r[mode]=(sb([x for x in t if yr(x["day"])=="Y1"])["ev_r"], sb([x for x in t if yr(x["day"])=="Y2"])["ev_r"])
    print("%-22s | %+8.4f %+8.4f | %+8.4f %+8.4f"%(n,r["honest"][0],r["honest"][1],r["touch"][0],r["touch"][1]))

print()
print("=== I. PROP EVAL on first-of-day, redone in all three worlds ===")
print("%-22s %6s %-8s %-8s %-8s %-8s"%("variant","risk$","claim","honest","touch",""))
for n in KEY:
    per={}
    for mode in ("claim","honest","touch"):
        t=[]
        for row in firsts:
            b=bars_for(row["sym"],row["day"])
            if not b: continue
            x=resim2(row,b,FN[n],mode)
            if x: t.append(x)
        per[mode]=t
    for risk in (100,250,500):
        cells=[]
        for mode in ("claim","honest","touch"):
            daily=[(x["day"],x["r"]*risk) for x in per[mode]]
            res=evaluate_prop_challenge(daily,account_size=50000.0)
            cells.append(("PASS" if res["passed"] else "F:"+ (res["fail_reason"] or "")[:6]))
        print("%-22s %6d %-8s %-8s %-8s  (n=%d)"%(n,risk,cells[0],cells[1],cells[2],len(per["honest"])))
