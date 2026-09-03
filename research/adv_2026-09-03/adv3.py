import csv,json,os,statistics
from collections import defaultdict
exec(open(r"C:\Users\aharg\AppData\Local\Temp\claude\C--Users-aharg-Desktop-Projects-tradingbot\e36136ab-fd7a-4f0c-97a8-86b0ad6d542a\scratchpad\adv.py").read().split('blob=json.load')[0])

def resim2(row,bars,fn,mode):
    """mode: 'claim'  = stop on close, fill capped at -1R (the sweep)
             'honest' = stop on close, fill AT the close (no cap)
             'touch'  = stop on intrabar touch, fill at stop -> exactly -1R
    In every mode target fires on touch; a bar doing both goes to STOP."""
    i=row["entry_i"]
    if i>=len(bars): return None
    e=row["entry"]; lng=row["dir"]=="call"; tgt=row["target"]
    stop,reason=fn(row,bars,i,e,lng)
    if stop is None: return None
    risk=abs(e-stop)
    if risk<=1e-9: return None
    if lng and stop>=e: return None
    if (not lng) and stop<=e: return None
    if risk<floor_(e): return None
    for j in range(i+1,len(bars)):
        _,o,h,l,c=bars[j]
        th=(h>=tgt) if lng else (l<=tgt)
        if mode=="touch":
            sh=(l<=stop) if lng else (h>=stop)
        else:
            sh=(c<=stop) if lng else (c>=stop)
        if sh:
            if mode=="honest":
                return dict(day=row["day"],r=((c-e)/risk if lng else (e-c)/risk),out="stop")
            return dict(day=row["day"],r=-1.0,out="stop")
        if th:
            r=((tgt-e)/risk) if lng else ((e-tgt)/risk)
            return dict(day=row["day"],r=r,out="target")
    c=bars[-1][4]
    return dict(day=row["day"],r=((c-e)/risk if lng else (e-c)/risk),out="scratch")

blob=json.load(open(BOOK,encoding="utf-8"))
traded=[r for r in blob["trades"] if r["status"]=="fired" and r.get("traded")]
sessions=blob["meta"]["sessions"]

MODES=["claim","honest","touch"]
out={m:{n:[] for n,_ in VARIANTS} for m in MODES}
for row in traded:
    b=bars_for(row["sym"],row["day"])
    if not b: continue
    for n,fn in VARIANTS:
        for m in MODES:
            r=resim2(row,b,fn,m)
            if r: out[m][n].append(r)

print("=== THE THREE STOP WORLDS, same rows, same targets ===")
print("  claim  = trigger on CLOSE, loss forced to exactly -1R   (what the sweep did)")
print("  honest = trigger on CLOSE, fill AT that close           (what a close-stop costs)")
print("  touch  = trigger on TOUCH, fill AT the stop = -1R exact (what a resting stop gets)")
print()
print("%-22s %6s | %8s %8s %8s | %7s %7s %7s"%("variant","n","claim","honest","touch","cl_win%","ho_win%","to_win%"))
for n,_ in VARIANTS:
    if not out["claim"][n]:
        print("%-22s %6s | %8s"%(n,0,"ALL DROPPED")); continue
    s={m:sb(out[m][n]) for m in MODES}
    print("%-22s %6d | %8.4f %8.4f %8.4f | %7.1f %7.1f %7.1f"%(
        n,s["claim"]["n"],s["claim"]["ev_r"],s["honest"]["ev_r"],s["touch"]["ev_r"],
        100*s["claim"]["win"],100*s["honest"]["win"],100*s["touch"]["win"]))

print()
print("=== rank order by world ===")
for m in MODES:
    rk=sorted([(sb(out[m][n])["ev_r"],n) for n,_ in VARIANTS if out[m][n]],reverse=True)
    print(" %-7s %s"%(m,"  ".join("%s=%.3f"%(n,v) for v,n in rk[:5])))

print()
print("=== wins the close-stop keeps that a resting stop would have taken ===")
print("  (target credited on a bar/path whose LOW/HIGH had already gone through the stop)")
for n in ("shipped_level","fixed_pct_0.25","atr_0.5x","entry_candle_extreme"):
    fn=dict(VARIANTS)[n]
    ghost=0; tot=0
    for row in traded:
        b=bars_for(row["sym"],row["day"])
        if not b: continue
        rc=resim2(row,b,fn,"claim")
        rt=resim2(row,b,fn,"touch")
        if rc is None: continue
        tot+=1
        if rc["out"]=="target" and rt and rt["out"]=="stop": ghost+=1
    print("  %-22s %d of %d target-wins-or-trades  (%.1f%% of all trades)"%(n,ghost,tot,100*ghost/tot))
