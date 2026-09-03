import csv,json,os,statistics
from collections import defaultdict
exec(open(r"C:\Users\aharg\AppData\Local\Temp\claude\C--Users-aharg-Desktop-Projects-tradingbot\e36136ab-fd7a-4f0c-97a8-86b0ad6d542a\scratchpad\adv.py").read().split('blob=json.load')[0])

blob=json.load(open(BOOK,encoding="utf-8"))
rows=blob["trades"]; sessions=blob["meta"]["sessions"]
traded=[r for r in rows if r["status"]=="fired" and r.get("traded")]

# resim all arms keyed by row index so we can intersect
recs={n:{} for n,_ in VARIANTS}
for idx,row in enumerate(traded):
    b=bars_for(row["sym"],row["day"])
    if not b: continue
    for n,fn in VARIANTS:
        rec,_=resim(row,b,fn)
        if rec is not None: recs[n][idx]=rec

names=[n for n,_ in VARIANTS if recs[n]]
common=set(recs[names[0]])
for n in names: common &= set(recs[n])
print("=== A. COMMON-POPULATION (rows every non-empty arm can trade): n=%d ==="%len(common))
print("%-22s %8s %8s %7s %8s %8s %8s"%("variant","ev_r_own","ev_r_com","win%","avg_win","stop%","yrR_com"))
base=None
for n in names:
    own=sb(list(recs[n].values()))
    c=sb([recs[n][i] for i in sorted(common)])
    st=100*sum(1 for i in common if recs[n][i]["out"]=="stop")/len(common)
    print("%-22s %8.4f %8.4f %7.1f %8.4f %8.1f %8.1f"%(n,own["ev_r"],c["ev_r"],100*c["win"],c["aw"],st,c["tot"]/sessions*252))

print()
print("=== B. -1R HARD CAP SUBSIDY (real close-based loss vs the -1.0 cap) ===")
print("%-22s %10s %10s %10s %10s"%("variant","ev_r_cap","ev_r_true","subsidy","worst_R"))
for n in names:
    t=list(recs[n].values())
    a=sb(t,"r"); bq=sb(t,"r_uncapped")
    worst=min(x["r_uncapped"] for x in t)
    print("%-22s %10.4f %10.4f %10.4f %10.2f"%(n,a["ev_r"],bq["ev_r"],a["ev_r"]-bq["ev_r"],worst))

print()
print("=== C. YEAR SPLIT (in-sample stability) ===")
def yr(d): return "Y1" if d < "2025-09-01" else "Y2"
print("%-22s %10s %10s %8s %8s"%("variant","ev_r_Y1","ev_r_Y2","n_Y1","n_Y2"))
for n in names:
    t=list(recs[n].values())
    y1=[x for x in t if yr(x["day"])=="Y1"]; y2=[x for x in t if yr(x["day"])=="Y2"]
    a=sb(y1); b2=sb(y2)
    print("%-22s %10.4f %10.4f %8d %8d"%(n,a["ev_r"],b2["ev_r"],a["n"],b2["n"]))

print()
print("=== D. WHO GETS DROPPED by fixed_pct_0.25 vs shipped_level ===")
dr25=[traded[i] for i in range(len(traded)) if i not in recs["fixed_pct_0.25"]]
drsh=[traded[i] for i in range(len(traded)) if i not in recs["shipped_level"]]
print("fixed_pct_0.25 drops %d rows; entry price max=%.2f  (0.25%% < $0.10 <=> px < $40)"%(len(dr25),max(r["entry"] for r in dr25)))
print("shipped_level  drops %d rows; entry price median=%.2f"%(len(drsh),statistics.median([r["entry"] for r in drsh])))
# shipped on the fixed25-kept set only
kept25=set(recs["fixed_pct_0.25"])
both=kept25 & set(recs["shipped_level"])
print("shipped_level restricted to rows fixed_pct_0.25 keeps (n=%d): ev_r=%.4f"%(len(both),sb([recs["shipped_level"][i] for i in both])["ev_r"]))
print("fixed_pct_0.25 on that same set              (n=%d): ev_r=%.4f"%(len(both),sb([recs["fixed_pct_0.25"][i] for i in both])["ev_r"]))

print()
print("=== E. NOTIONAL / LEVERAGE at $1,000 risk per trade ===")
print("%-22s %12s %12s %12s"%("variant","med_risk_$/sh","med_notional","pct>4x $50k"))
for n in names:
    t=list(recs[n].values())
    notion=[x["entry"]*(1000.0/x["risk"]) for x in t]
    print("%-22s %12.3f %12.0f %11.1f%%"%(n,statistics.median(x["risk"] for x in t),
          statistics.median(notion),100*sum(1 for v in notion if v>200000)/len(notion)))

print()
print("=== F. HOLDING TIME / EOD scratch share ===")
print("%-22s %8s %8s %8s"%("variant","med_bars","scratch%","tgt%"))
for n in names:
    t=list(recs[n].values())
    print("%-22s %8.0f %8.1f %8.1f"%(n,statistics.median(x["bars_held"] for x in t),
        100*sum(1 for x in t if x["out"]=="scratch")/len(t),
        100*sum(1 for x in t if x["out"]=="target")/len(t)))
