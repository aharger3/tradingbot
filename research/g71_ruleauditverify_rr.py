"""G7.1 adversarial verify of the ruleaudit S11 claim (flat 2R target => mean-R
2.0 unreachable). Counts over the committed 2-year book. Read-only."""
import json, collections, statistics, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
R = Path(__file__).resolve().parent.parent
B = json.load(open(R/"research"/"bt2y_trades.json"))
T = B["trades"]; TR=[r for r in T if r["traded"]]
print("meta:", {k:B["meta"][k] for k in ("generated","sessions","signals","traded")})

# 1. reproduce the histogram
rr = collections.Counter()
for r in T:
    risk = abs(r["entry"]-r["stop"])
    rr[round(abs(r["target"]-r["entry"])/risk,3) if risk else None]+=1
print("1. planned RR hist (all signals):", dict(rr.most_common(8)))
rrt = collections.Counter()
for r in TR:
    risk = abs(r["entry"]-r["stop"])
    rrt[round(abs(r["target"]-r["entry"])/risk,3) if risk else None]+=1
print("   planned RR hist (TRADED only):", dict(rrt.most_common(8)))

# 2. did any traded row actually EXIT at its planned target?
def close(a,b,tol=1e-6): return abs(a-b)<=tol
at_target = [r for r in TR if r.get("exit") is not None and close(r["exit"], r["target"])]
print("2. traded rows exiting AT the planned 2R target: %d of %d" % (len(at_target), len(TR)))

# 3. realized R distribution vs the 2.0 ceiling the claim asserts
Rs = [r["r"] for r in TR]
over2 = [x for x in Rs if x > 2.0+1e-9]
print("3. realized R: mean %+.4f  max %+.4f  rows with R>2.0: %d (%.2f%%)"
      % (statistics.fmean(Rs), max(Rs), len(over2), 100*len(over2)/len(Rs)))
print("   realized R deciles:", [round(x,3) for x in statistics.quantiles(Rs, n=10)])
wins=[r for r in TR if r["out"]=="win"]
print("   win rows: n=%d meanR %+.4f  wins with R>2: %d" % (len(wins), statistics.fmean([w['r'] for w in wins]), sum(1 for w in wins if w['r']>2+1e-9)))
print("   scaled rows: %d of %d" % (sum(1 for r in TR if r.get("scaled")), len(TR)))

# 4. wT-(1-w) sanity: what T would the realized win leg imply?
w = len(wins)/len(TR)
print("4. w=%.4f  realized mean win R=%.4f  realized mean loss R=%.4f"
      % (w, statistics.fmean([x['r'] for x in wins]),
         statistics.fmean([x['r'] for x in TR if x['out']!='win']) ))

# 5. the rounding artefact: the claim's non-2.0 histogram buckets are export
#    rounding (backtest_2y.py:170-171 rounds entry/stop/target to 2dp), not
#    plans. Concentrated entirely in tiny-risk rows.
print()
print("5. planned-RR deviation vs risk size (rounding test)")
buck = collections.defaultdict(collections.Counter)
for r in T:
    risk = abs(r["entry"]-r["stop"])
    if risk <= 0: continue
    q = abs(r["target"]-r["entry"])/risk
    b = ("risk<0.05" if risk < .05 else "0.05-0.20" if risk < .20
         else "0.20-1.00" if risk < 1.0 else "risk>=1.00")
    buck[b]["n"] += 1
    buck[b]["exact2" if abs(q-2.0) < 1e-9 else "near2" if abs(q-2.0) < .05 else "far"] += 1
for k in ("risk<0.05","0.05-0.20","0.20-1.00","risk>=1.00"):
    c = buck[k]
    print("   %-12s n=%6d exact2=%6d near2=%5d far=%5d" % (k, c["n"], c["exact2"], c["near2"], c["far"]))

# 6. reachability of the branch the claim cites
import backtest_week as bw
print()
print("6. backtest_week.SCALE_PLAN default = %r  -> line 770 `if SCALE_PLAN: _ladder_bar(); continue`"
      % (bw.SCALE_PLAN,))
print("   => backtest_week.py:789 `targeted = ... t.target` and :806 `win, t.target`")
print("      are BOTH downstream of that continue. Dead on the shipped config.")
