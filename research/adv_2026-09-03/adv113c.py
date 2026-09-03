import json, os, sys, statistics, random
ROOT = r"C:\Users\aharg\Desktop\Projects\tradingbot"
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT,"research"))
import omen_metrics as om
SP=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(SP,"adv113_rows.json"))); days=d["days"]; n=len(days)
KEYS=["one_target","30/30/30/10","20/20/20/40P","20/20/20+40run"]
for rd in (200.0,100.0):
    print("=== start-date robustness @ $%d/trade ===" % rd)
    npass={k:0 for k in KEYS}; tot=0
    for off in range(0, n-120, 20):
        tot+=1
        line="  %-11s"%days[off]
        for k in KEYS:
            ev=om.evaluate_prop_challenge([(days[i], d[k][i]*rd) for i in range(off,n)], account_size=50000.0)
            if ev["passed"]: npass[k]+=1
            line+="  %-14s"%("PASS d%d"%ev["days_traded"] if ev["passed"] else "FAIL "+(ev["fail_reason"] or "")[:9])
        print(line)
    print("  PASS rate over %d start dates: %s\n" % (tot, ", ".join("%s %d/%d"%(k,npass[k],tot) for k in KEYS)))
random.seed(11)
for a,b in (("30/30/30/10","one_target"),("25/25/25/25","one_target"),("20/20/20+40run","50/50")):
    diff=[x-y for x,y in zip(d[a],d[b])]; obs=statistics.fmean(diff)
    p=sum(1 for _ in range(20000) if abs(statistics.fmean([x if random.random()<.5 else -x for x in diff]))>=abs(obs))/20000
    print("paired perm %-16s vs %-12s diff=%+.4fR p=%.4f" % (a,b,obs,p))
