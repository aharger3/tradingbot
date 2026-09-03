"""Is NVDA SEPARABLY the most SPY-correlated single name, and is AAPL
separably the most orthogonal? Paired bootstrap on the correlation
DIFFERENCE over common days (the only way to rank correlations).
Also ranks orthogonality to TSLA."""
from __future__ import annotations
import os, sys, random, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from g71_symbolsV_corr import window_returns, pearson, MIN_DAYS

ARCHIVE = os.path.join(ROOT, "data_archive")
syms = [s for s in sorted(os.listdir(ARCHIVE))]
rets = {}
for s in syms:
    r = window_returns(s)
    if len(r) >= MIN_DAYS:
        rets[s] = r
spy, tsla = rets["SPY"], rets["TSLA"]

def diff_ci(anchor, a, b, n=3000, seed=11):
    days = sorted(set(anchor) & set(a) & set(b))
    A = [anchor[d] for d in days]; X = [a[d] for d in days]; Y = [b[d] for d in days]
    obs = pearson(A, X) - pearson(A, Y)
    rng = random.Random(seed); N = len(days); ds = []
    for _ in range(n):
        idx = [rng.randrange(N) for _ in range(N)]
        aa = [A[i] for i in idx]
        ds.append(pearson(aa, [X[i] for i in idx]) - pearson(aa, [Y[i] for i in idx]))
    ds.sort()
    return obs, ds[int(.025*n)], ds[int(.975*n)], len(days), sum(1 for d in ds if d <= 0)/n

print("Is NVDA's SPY-correlation separable from the next names? (paired bootstrap on r_NVDA - r_X)")
for x in ["AMZN","AVGO","META","HOOD","MSFT","COIN","AMD","TSLA","AAPL"]:
    o, lo, hi, n, p = diff_ci(spy, rets["NVDA"], rets[x])
    sep = "SEPARABLE" if lo > 0 else "not separable"
    print("  NVDA vs %-5s  d=%+.3f [%+.3f,%+.3f] n=%d  P(d<=0)=%.3f  %s" % (x,o,lo,hi,n,p,sep))

print("\nIs AAPL separably the MOST ORTHOGONAL to SPY? (r_X - r_AAPL; negative = X more orthogonal)")
for x in ["SPCX","BABA","INTC","ACHR","NFLX","MSTR","ORCL"]:
    o, lo, hi, n, p = diff_ci(spy, rets[x], rets["AAPL"])
    print("  %-5s vs AAPL  d=%+.3f [%+.3f,%+.3f] n=%d" % (x,o,lo,hi,n))

print("\nOrthogonality to TSLA, full archive, ranked (claim: AAPL 0.17 is the most orthogonal):")
rows=[]
for s in rets:
    if s=="TSLA": continue
    days=sorted(set(tsla)&set(rets[s]))
    if len(days)<MIN_DAYS: continue
    rows.append((s, pearson([tsla[d] for d in days],[rets[s][d] for d in days]), len(days)))
rows.sort(key=lambda t:t[1])
for s,r,n in rows[:8]:
    print("  %-6s %+.3f n=%d" % (s,r,n))
