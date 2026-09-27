import numpy as np, math
from sim import *
H = 200
st, sh = paths(H, list(range(ND)))
arr = day_arrays("1030", 1)
BEST = {"Lucid Flex": [(10, 8, 4), (12, 10, 6), (4, 4, 4), (6, 6, 6)], "Topstep": [(10, 8, 4), (12, 10, 6), (4, 4, 4), (6, 6, 6)],
        "Tradeify Flex": [(8, 8, 6), (8, 8, 8), (4, 4, 4), (6, 6, 6)]}
def funded(firm, lad, P, days=120):
    f = FIRMS[firm]; U, RK, MAE, MFE, GB, V, _, _ = arr
    NP = P.shape[0]; bal = np.zeros(NP); floor = np.full(NP, -f["dd"]); alive = np.ones(NP, bool)
    wins = np.zeros(NP); paid = np.zeros(NP); dpay = np.full(NP, -1)
    for t in range(days):
        d = P[:, t % P.shape[1]]; act = alive & (paid == 0)
        c = np.where(bal < 1000, lad[0], np.where(bal < 2000, lad[1], lad[2]))
        n = np.minimum(c, np.floor((bal - floor - 50) / RK[d, 0])); n = np.where(V[d, 0] & act & (n >= 1), n, 0)
        pnl = n * U[d, 0]; bal = bal + pnl
        alive &= ~(act & (bal < floor)); floor = np.where(act & alive, np.minimum(np.maximum(floor, bal - f["dd"]), f["lock"]), floor)
        wins += act & (pnl >= 150)
        ok = act & alive & (wins >= 5) & (bal > 0)
        paid = np.where(ok, np.minimum(0.5 * bal, f["cap"]) * 0.9, paid); dpay = np.where(ok, t + 1, dpay)
    return paid
rows = []
for firm, lads in BEST.items():
    for lad in lads:
        r = {}
        for nm, P in (("start", st), ("shuf", sh)):
            p, dp, al = run(firm, arr, P, [lad]); p, dp, al = p[0], dp[0], al[0]
            r[nm] = (p.mean(), (~al).mean(), np.median(dp[p]) if p.any() else np.nan, np.percentile(dp[p], 75) if p.any() else np.nan)
        pi, _, _ = run(firm, arr, sh, [lad], intraday=True); r["intra"] = pi[0].mean()
        a0 = arr
        for tag, kw in (("null", dict(demean=True)), ("H1", dict(half=1)), ("H2", dict(half=2))):
            globals()["arr"] = a0
            ax = day_arrays("1030", 1, **kw)
            pool = list(range(MID)) if tag == "H1" else list(range(MID, ND)) if tag == "H2" else list(range(ND))
            s2 = rng.choice(np.array(pool), size=(1000, H), replace=True)
            px, _, _ = run(firm, ax, s2, [lad]); r[tag] = px[0].mean()
        pay = funded(firm, lad, sh); ppay = (pay > 0).mean(); epay = pay[pay > 0].mean() if ppay else 0
        f = FIRMS[firm]; med = r["shuf"][2]
        cost = f["cost"] + f["monthly"] * math.ceil(med / 17.3) + f["act"] * r["shuf"][0]
        ev = r["shuf"][0] * ppay * epay - cost
        rows.append((firm, lad, r, ppay, epay, cost, ev))
        print(f"| {firm} | {lad} | {r['start'][0]:.0%} | {r['shuf'][0]:.0%} | {r['shuf'][1]:.0%} | {r['shuf'][2]:.0f} ({r['shuf'][3]:.0f}) | {r['intra']:.0%} | {r['H1']:.0%} / {r['H2']:.0%} | {r['null']:.0%} | {ppay:.0%} | ${epay:,.0f} | ${cost:,.0f} | ${ev:+,.0f} |", flush=True)
