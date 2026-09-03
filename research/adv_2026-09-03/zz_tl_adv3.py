import pickle, statistics, sys
ROOT=r"C:\Users\aharg\Desktop\Projects\tradingbot"; sys.path.insert(0,ROOT)
from research.omen_metrics import evaluate_prop_challenge
d=pickle.load(open("zz_tl.pkl","rb")); store=d["store"]; base=d["base"]; days=[m[0] for m in d["meta"]]
CUT="2025-09-01"
def run(rs,dys,risk,lbl):
    daily=[(a,r*risk) for a,r in zip(dys,rs)]
    res=evaluate_prop_challenge(daily,account_size=50000.0)
    print("  %-28s %s %-26s %-11s final%%=%6.1f dd%%=%5.1f days=%d bestday=%.0f%% of profit"%(
        lbl,"PASS" if res["passed"] else "FAIL",res["fail_reason"] or "-",res["fail_day"] or "-",
        res["final_equity_pct"],res["max_drawdown_seen_pct"],res["days_traded"],
        100*(res.get("best_day_pct_of_profit") or 0)))
print("12-MONTH WINDOWS at $100/trade (Austin's bar: pass ONE eval within 12 months)")
for nm,rs in (("flat2R",base),("tol0.45",store[0.45][0]),("tol0.35",store[0.35][0]),("tol0.30",store[0.30][0])):
    run(rs,days,100,nm+" FULL 2y")
    y1=[(r,a) for r,a in zip(rs,days) if a<CUT]; y2=[(r,a) for r,a in zip(rs,days) if a>=CUT]
    run([x[0] for x in y1],[x[1] for x in y1],100,nm+" YEAR1 only")
    run([x[0] for x in y2],[x[1] for x in y2],100,nm+" YEAR2 only")
print("\nrisk sweep, tol=0.45, FULL 2y (finding the sizing that actually passes)")
for risk in (50,75,100,125,150,175,200,225):
    run(store[0.45][0],days,risk,"tol0.45 $%d"%risk)
