import json,statistics as st,collections as C,random,sys
rows=json.load(open(sys.argv[1])); random.seed(3)
G=["S","A","C"]
def med(x): x=[v for v in x if v is not None]; return st.median(x) if x else float('nan')
def mean(x): x=[v for v in x if v is not None]; return sum(x)/len(x) if x else float('nan')
by={g:[r for r in rows if r["g"]==g] for g in G}
print("n",{g:len(v) for g,v in by.items()}, "withbrk",{g:sum(1 for r in v if r.get("brk") is not None) for g,v in by.items()})
num=["tso","disp_atr","disp_pts","disp_pct","strong_n","brk_body_atr","retest_dist_atr","bars_brk_to_sig","bars_rt_to_sig","trig_body","trig_wick","trig_range_atr","R","R1045"]
print("feature | S med | A med | C med | AUC S vs A+C")
def auc(a,b):
    a=[v for v in a if v is not None]; b=[v for v in b if v is not None]
    if not a or not b: return float('nan')
    w=sum((x>y)+0.5*(x==y) for x in a for y in b); return w/(len(a)*len(b))
for f in num:
    s=[r.get(f) for r in by["S"]]; o=[r.get(f) for r in by["A"]+by["C"]]
    print(f, *[round(med([r.get(f) for r in by[g]]),3) for g in G], round(auc(s,o),3))
for cat in ["setup","retest","trig","side","level"]:
    print("\n",cat)
    ks=C.Counter(r.get(cat) for r in rows if r["g"] in G)
    for k,_ in ks.most_common():
        cells=[]
        for g in G:
            v=by[g]; n=sum(1 for r in v if r.get(cat)==k); cells.append(f"{n} ({100*n/len(v):.0f}%)")
        Rs=[r["R"] for r in by["S"] if r.get(cat)==k and r["R"] is not None]
        print(k,"|"," | ".join(cells),"| S meanR",round(mean(Rs),2),len(Rs))
print("\nR by grade")
for g in G:
    Rs=[r["R"] for r in by[g] if r["R"] is not None]; R2=[r["R1045"] for r in by[g] if r["R1045"] is not None]
    h1=[r["R"] for r in by[g] if r["R"] is not None and r["day"]<"2025-09-29"]; h2=[r["R"] for r in by[g] if r["R"] is not None and r["day"]>="2025-09-29"]
    print(g,len(Rs),round(mean(Rs),3),"win",round(sum(x>0 for x in Rs)/len(Rs),2),"R1045",round(mean(R2),3),"H1",len(h1),round(mean(h1),3),"H2",len(h2),round(mean(h2),3))
# time buckets
print("\ntime since open buckets (count S/A/C, S R)")
for lo,hi in [(0,5),(5,15),(15,30),(30,60),(60,90)]:
    c=[sum(1 for r in by[g] if lo<=r["tso"]<hi) for g in G]
    Rs=[r["R"] for r in by["S"] if lo<=r["tso"]<hi and r["R"] is not None]
    print(lo,hi,c,round(mean(Rs),2),len(Rs))
# index ETFs
ETF={"SPY","QQQ","IWM","DIA"}
print("\nETF", {g:sum(1 for r in by[g] if r["sym"] in ETF) for g in G}, "S ETF R", round(mean([r["R"] for r in by["S"] if r["sym"] in ETF]),2))
json.dump(by["S"],open(sys.argv[1].replace("s_rows","S_only"),"w"),default=str)
