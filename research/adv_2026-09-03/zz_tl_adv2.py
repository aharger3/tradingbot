import pickle, statistics, numpy as np, sys, os, json
ROOT=r"C:\Users\aharg\Desktop\Projects\tradingbot"; sys.path.insert(0,ROOT)
from research.omen_metrics import evaluate_prop_challenge
d=pickle.load(open("zz_tl.pkl","rb")); store=d["store"]; base=d["base"]; meta=d["meta"]
days=[m[0] for m in meta]
CUT="2025-09-01"
for tol in (0.20,0.25,0.30,0.35,0.45):
    lv,ctc=store[tol]
    diffs=[a-b for a,b in zip(lv,ctc)]
    nz=[x for x in diffs if abs(x)>1e-9]
    pos=sum(1 for x in nz if x>0); neg=len(nz)-pos
    # concentration
    s=sorted(nz,key=lambda x:-abs(x))
    tot=sum(diffs)
    top5=sum(s[:5])
    y1=[a-b for a,b,dd in zip(lv,ctc,days) if dd<CUT]
    y2=[a-b for a,b,dd in zip(lv,ctc,days) if dd>=CUT]
    l1=[a for a,dd in zip(lv,days) if dd<CUT]; c1=[a for a,dd in zip(ctc,days) if dd<CUT]
    l2=[a for a,dd in zip(lv,days) if dd>=CUT]; c2=[a for a,dd in zip(ctc,days) if dd>=CUT]
    print("tol %.2f | rows changed %3d (+%d/-%d) | top5 rows = %.1f%% of total delta | Y1 n=%d d=%+.4f (lv %.4f) | Y2 n=%d d=%+.4f (lv %.4f)"%(
        tol,len(nz),pos,neg,100*top5/tot if tot else 0,len(y1),statistics.fmean(y1),statistics.fmean(l1),
        len(y2),statistics.fmean(y2),statistics.fmean(l2)))
print()
# does the sign of the snap matter: nearer vs further
print("prop-eval spot check, $50k, best arm tol=0.45 level vs flat2R")
for risk in (100,250,500,1000):
    for nm,rs in (("flat2R",base),("tol0.45",store[0.45][0])):
        daily=[(dd,r*risk) for dd,r in zip(days,rs)]
        res=evaluate_prop_challenge(daily,account_size=50000.0)
        print("  $%-5d %-8s %s  %-22s %-11s final%%=%.1f dd%%=%.1f"%(risk,nm,"PASS" if res["passed"] else "FAIL",
            res["fail_reason"] or "-",res["fail_day"] or "-",res["final_equity_pct"],res["max_drawdown_seen_pct"]))
