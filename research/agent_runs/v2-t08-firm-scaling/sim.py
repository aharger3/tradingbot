"""v2-t08 prop-firm scaling sweep on the t01 best cell. Paper research only.
Vectorised over (contract ladder x path). Paths = every Mon-Thu start date (wrapping) + 1000 day-bootstrap shuffles."""
import json, itertools, math, sys
import numpy as np
rng = np.random.default_rng(8)
D = json.load(open("t08_trades.json"))
wd = np.array(D["weekday"]); ses = D["sessions"]
keep = [i for i in range(len(ses)) if wd[i] <= 3]          # Mon-Thu only (his availability)
sidx = {ses[i]: n for n, i in enumerate(keep)}
ND = len(keep); MID = ND // 2
FIRMS = {  # eval rules (s08, 50K)
 "Lucid Flex":   dict(dd=2000, lock=100, cons=0.50, mind=1, dll=None, target=3000, cost=146, monthly=0, act=0, cap=2000),
 "Topstep":      dict(dd=2000, lock=0,   cons=0.50, mind=2, dll=1000, target=3000, cost=0, monthly=49, act=149, cap=2000),
 "Tradeify Flex":dict(dd=2000, lock=100, cons=0.40, mind=3, dll=None, target=3000, cost=165, monthly=0, act=0, cap=3000),
}
CSET = [2, 3, 4, 6, 8, 10, 12]
LADDERS = list(itertools.product(CSET, CSET, CSET))       # contracts at profit <1K / 1-2K / >=2K
TIERS = (1000, 2000)

def day_arrays(cut, maxT, demean=False, half=None):
    tr = [t for t in D["trades"][cut] if t["date"] in sidx and t["k"] < maxT]
    if half == 1: tr = [t for t in tr if sidx[t["date"]] < MID]
    if half == 2: tr = [t for t in tr if sidx[t["date"]] >= MID]
    mR = np.mean([t["R"] for t in tr])
    U = np.zeros((ND, maxT)); RK = np.full((ND, maxT), np.inf); MAE = np.zeros((ND, maxT)); MFE = np.zeros((ND, maxT)); GB = np.zeros((ND, maxT))
    V = np.zeros((ND, maxT), bool)
    for t in tr:
        d, k = sidx[t["date"]], t["k"]
        u = t["usd"] - (mR * (t["risk"] - 0.5) if demean else 0)
        U[d, k] = u; RK[d, k] = t["risk"]; MAE[d, k] = max(t["mae"], -u); GB[d, k] = t["gb"]; V[d, k] = True
        MFE[d, k] = u if t["R"] > 1.8 else max(u, t["gb"] + u)
    return U, RK, MAE, MFE, GB, V, len(tr), mR

def paths(H, days_pool):
    pool = np.array(days_pool)
    st = np.array([[pool[(s + t) % len(pool)] for t in range(H)] for s in range(len(pool))])
    sh = rng.choice(pool, size=(1000, H), replace=True)
    return st, sh

def run(firm, arr, P, ladders, intraday=False, dstop=None):
    f = FIRMS[firm]; U, RK, MAE, MFE, GB, V, _, _ = arr
    L = np.array(ladders, float)                          # (K,3)
    K, NP, H = len(L), P.shape[0], P.shape[1]
    bal = np.zeros((K, NP)); floor = np.full((K, NP), -f["dd"]); peak = np.zeros((K, NP))
    alive = np.ones((K, NP), bool); passed = np.zeros((K, NP), bool); dpass = np.full((K, NP), -1)
    best = np.zeros((K, NP)); ndays = np.zeros((K, NP))
    for t in range(H):
        d = P[:, t]; act = alive & ~passed
        if not act.any(): break
        day = np.zeros((K, NP)); won = np.zeros((K, NP), bool); traded = np.zeros((K, NP), bool)
        for k in range(U.shape[1]):
            v = V[d, k][None, :] & act & ~won
            if dstop is not None: v &= day > -dstop
            if f["dll"] is not None: v &= day > -f["dll"]
            prof = bal
            c = np.where(prof < TIERS[0], L[:, 0:1], np.where(prof < TIERS[1], L[:, 1:2], L[:, 2:3]))
            cush = bal - floor
            n = np.minimum(c, np.floor((cush - 50) / RK[d, k][None, :]))
            n = np.where(v & (n >= 1), n, 0)
            if intraday:
                lockd = floor >= f["lock"]
                ddn = np.maximum(peak - bal + n * MAE[d, k][None, :], n * GB[d, k][None, :])
                br = (n > 0) & np.where(lockd, bal - n * MAE[d, k][None, :] < floor, ddn >= f["dd"])
                alive &= ~br
                peak = np.maximum(peak, bal + n * MFE[d, k][None, :])
            pnl = n * U[d, k][None, :]
            bal = bal + pnl; day = day + pnl; traded |= n > 0; won |= (n > 0) & (pnl > 0)
            if intraday:
                floor = np.where(act, np.minimum(np.maximum(floor, peak - f["dd"]), f["lock"]), floor)
        # EOD
        alive &= ~(act & (bal < floor)) if not intraday else True
        if not intraday:
            floor = np.where(act & alive, np.minimum(np.maximum(floor, bal - f["dd"]), f["lock"]), floor)
            peak = np.maximum(peak, bal)
        ndays += act & traded
        best = np.where(act, np.maximum(best, day), best)
        ok = act & alive & (bal >= f["target"]) & (best <= f["cons"] * bal) & (ndays >= f["mind"])
        dpass = np.where(ok, t + 1, dpass); passed |= ok
    return passed, dpass, alive

def summ(passed, dpass):
    pr = passed.mean(1)
    med = np.array([np.median(r[r > 0]) if (r > 0).any() else np.nan for r in dpass])
    return pr, med

if __name__ == "__main__":
    H = 200
    res = {}
    POL = [("1030", 1, None), ("1100", 1, None), ("1100", 3, 400)]
    st, sh = paths(H, list(range(ND)))
    for cut, maxT, ds in POL:
        arr = day_arrays(cut, maxT)
        print(f"policy cut={cut} maxT={maxT} dstop={ds} trades(MonThu)={arr[6]} meanR={arr[7]:.3f}", flush=True)
        for firm in FIRMS:
            out = {}
            for nm, P in (("start", st), ("shuf", sh)):
                p, dp, _ = run(firm, arr, P, LADDERS, dstop=ds); out[nm] = summ(p, dp)
            score = np.minimum(out["start"][0], out["shuf"][0])
            top = np.argsort(-score)[:3]
            for j in top:
                print(f"  {firm:13s} ladder={LADDERS[j]} pass start={out['start'][0][j]:.3f} shuf={out['shuf'][0][j]:.3f} med_days={out['start'][1][j]:.0f}/{out['shuf'][1][j]:.0f}", flush=True)
            res[(cut, maxT, ds, firm)] = (out, top)
    import pickle; pickle.dump(res, open("sweep.pkl", "wb"))
