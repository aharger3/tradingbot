import json, os, sys
ROOT=r"C:\Users\aharg\Desktop\Projects\tradingbot"
sys.path.insert(0,ROOT); sys.path.insert(0,os.path.join(ROOT,"research"))
import omen_metrics as om
SP=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(SP,"adv113_rows.json"))); days=d["days"]; n=len(days)
KEYS=["shipped","one_target","50/50","50/20/20/10","30/30/30/10","25/25/25/25","20/20/20/40P","20/20/20+40run"]
sizes=[75,100,125,150,175,200,250,300]
starts=list(range(0,n-120,20))
print("PASS rate across %d rolling start dates (12-mo-plus window, $50k eval)" % len(starts))
print("%-18s %s" % ("arm"," ".join("$%-6d"%s for s in sizes)))
for k in KEYS:
    row=""
    for s in sizes:
        c=sum(1 for off in starts if om.evaluate_prop_challenge([(days[i],d[k][i]*s) for i in range(off,n)],account_size=50000.0)["passed"])
        row+=" %-7s"%("%d/%d"%(c,len(starts)))
    print("%-18s %s"%(k,row))
# restrict to starts that leave >=252 sessions (a real 12-month attempt)
print("\nsame, but only start dates with >=252 sessions remaining AND capped at 252 sessions (his 12-month bar)")
starts2=[o for o in range(0,n-252,20)]
print("%-18s %s" % ("arm"," ".join("$%-6d"%s for s in sizes)))
for k in KEYS:
    row=""
    for s in sizes:
        c=sum(1 for off in starts2 if om.evaluate_prop_challenge([(days[i],d[k][i]*s) for i in range(off,off+252)],account_size=50000.0)["passed"])
        row+=" %-7s"%("%d/%d"%(c,len(starts2)))
    print("%-18s %s"%(k,row))
