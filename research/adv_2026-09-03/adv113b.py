import json, os, sys, statistics, random
ROOT = r"C:\Users\aharg\Desktop\Projects\tradingbot"
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT,"research"))
import omen_metrics as om
SP = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(SP,"adv113_rows.json")))
days = d["days"]; n=len(days)
arms = [k for k in d if k!="days"]

print("=== min R per arm (R1: max loss -1R hard) ===")
for k in arms:
    v=d[k]; print("  %-18s min=%+.4f  n_below_-1.0=%d  n_below_-1.0001=%d" % (k, min(v), sum(1 for x in v if x < -1.0), sum(1 for x in v if x < -1.0001)))

print("\n=== are the '4-rung' arms actually distinct? per-row identity ===")
for a,b in (("30/30/30/10","25/25/25/25"),("25/25/25/25","20/20/20/40P"),("30/30/30/10","20/20/20/40P"),("50/20/20/10","25/25/25/25")):
    same = sum(1 for x,y in zip(d[a],d[b]) if abs(x-y)<1e-9)
    print("  %-14s vs %-14s identical on %d/%d rows (%.1f%%)" % (a,b,same,n,same/n*100))

print("\n=== monthly R, best arm vs one_target ===")
per={}
for i,dd in enumerate(days):
    per.setdefault(dd[:7],[0.0,0.0,0])
    per[dd[:7]][0]+=d["20/20/20+40run"][i]; per[dd[:7]][1]+=d["one_target"][i]; per[dd[:7]][2]+=1
cum=0
for m in sorted(per):
    cum+=per[m][0]
    print("  %s n=%2d runner %+7.2fR (cum %+7.2f)  one_target %+7.2fR" % (m,per[m][2],per[m][0],cum,per[m][1]))

print("\n=== paired permutation: runner vs one_target, 20k shuffles ===")
diff=[a-b for a,b in zip(d["20/20/20+40run"],d["one_target"])]
obs=statistics.fmean(diff); random.seed(7)
cnt=sum(1 for _ in range(20000) if abs(statistics.fmean([x if random.random()<.5 else -x for x in diff]))>=abs(obs))
print("  mean paired diff = %+.4fR, p = %.4f" % (obs, cnt/20000))
diff2=[a-b for a,b in zip(d["20/20/20+40run"],d["30/30/30/10"])]
obs2=statistics.fmean(diff2)
cnt2=sum(1 for _ in range(20000) if abs(statistics.fmean([x if random.random()<.5 else -x for x in diff2]))>=abs(obs2))
print("  runner vs 30/30/30/10: %+.4fR, p = %.4f" % (obs2, cnt2/20000))

print("\n=== prop eval START-DATE robustness ($100/trade, $50k eval) ===")
print("  start        %s" % "  ".join("%-14s"%a for a in ["one_target","30/30/30/10","20/20/20/40P","20/20/20+40run"]))
for off in (0,50,100,150,200,222,250,300):
    if off>=n-60: continue
    line="  %-11s" % days[off]
    for k in ["one_target","30/30/30/10","20/20/20/40P","20/20/20+40run"]:
        daily=[(days[i], d[k][i]*100.0) for i in range(off,n)]
        ev=om.evaluate_prop_challenge(daily, account_size=50000.0)
        line += "  %-14s" % ("PASS d%d"%ev["days_traded"] if ev["passed"] else ("FAIL "+(ev["fail_reason"] or "")[:9]))
    print(line)

print("\n=== what the prop grid really is: R-thresholds ===")
for k in arms:
    v=d[k]; peak=cum=worst=0.0
    for x in v:
        cum+=x; peak=max(peak,cum); worst=min(worst,cum-peak)
    print("  %-18s totalR=%+7.2f  maxDD_R=%.2f  -> DD budget at $100=20.0R, $200=10.0R" % (k,sum(v),worst))
