"""burn-target-sweep: re-simulate the EXIT TARGET on the frozen MNQ v2 cell without touching the signal.

EXPLORATORY (hypothesis budget: not a new cell). Paper research only.
Same entries, same stops, same 10:30 flat as the 105 frozen IS trades (v3-t-mnq v2 baseline, OR5 D1.0 strong,
10:30, 2R) and the 46 OOS QQQ-proxy trades. Exit targets: 1.5R, 2R, 2.5R, 3R, 4R and runner (no limit, flat 10:30).
Fill rules are frozen orb1m.sim (limit needs 1 tick through; stop wins same bar, filled at min(stop, open) -1 tick;
flat at cutoff open -1 tick); sizing/commission identical to mnq.trade ($200/R, n = floor(200/(stop$+1.24)), max 50,
$1.24 RT per micro). Asserts the 2R column reproduces mnq.trade exactly.
"""
import sys, json
import numpy as np

AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"
sys.path.insert(0, AR + r"\v3-t-mnq")
TARGETS = [1.5, 2.0, 2.5, 3.0, 4.0, None]  # None = runner to 10:30
TICK, USD, COMM, RISK, MAXN = 0.25, 2.0, 1.24, 200.0, 50
CUT = 60  # 10:30


def label(k):
    return "runner" if k is None else f"{k:g}R"


def sim(A, side, i, stop, tgt, cut):
    """Verbatim orb1m.sim fill rules; tgt=None -> no limit (runner)."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    for j in range(i, cut):
        if np.isnan(O[j]):
            continue
        if side > 0:
            if L[j] <= stop:
                return min(stop, O[j]) - TICK
            if tgt is not None and H[j] >= tgt + TICK:
                return tgt
        else:
            if H[j] >= stop:
                return max(stop, O[j]) + TICK
            if tgt is not None and L[j] <= tgt - TICK:
                return tgt
    if cut < 91 and not np.isnan(O[cut]):
        px = O[cut]
    else:
        v = C[:cut][~np.isnan(C[:cut])]
        px = v[-1]
    return px - TICK * side


def trade_k(A, i, side, dist, k, cut=CUT):
    """mnq.trade(...,'2R') with the 2 replaced by k. Returns (R, usd)."""
    fill = A["open"][i] + TICK * side
    stop = fill - side * dist
    n = min(MAXN, int(RISK // (dist * USD + COMM))) or 1
    x = sim(A, side, i, stop, None if k is None else fill + side * k * dist, cut)
    usd = (x - fill) * side * n * USD - n * COMM
    return usd / (n * dist * USD), usd


def mfe(A, i, side, dist, cut=CUT):
    """(MFE before stop-out or 10:30 [stop wins its own bar], MFE to 10:30 ignoring stop) in R from the fill."""
    O, H, L = A["open"], A["high"], A["low"]
    fill = O[i] + TICK * side; stop = fill - side * dist
    best, best_ns, alive = 0.0, 0.0, True
    for j in range(i, cut):
        if np.isnan(O[j]):
            continue
        fav = ((H[j] - fill) if side > 0 else (fill - L[j])) / dist
        best_ns = max(best_ns, fav)
        if alive:
            hit = L[j] <= stop if side > 0 else H[j] >= stop
            if hit:
                alive = False
            else:
                best = max(best, fav)
    return best, best_ns


def summ(R, U, dates, mid, nsess):
    R, U = np.asarray(R), np.asarray(U); h1 = np.array([d < mid for d in dates])
    eq = np.cumsum(U); dd = float(np.max(np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq))
    return dict(n=len(R), win=float((R > 0).mean()), R=float(R.mean()),
                H1=float(R[h1].mean()), H2=float(R[~h1].mean()), usd_day=float(U.sum() / nsess), dd=dd)


def sweep(days, T, rng, nshuf=200, nperm=10000):
    dates_all = [A["date"] for A in days]; mid = dates_all[len(dates_all) // 2]
    dates = [t["date"] for t in T]; out = {}; Rk = {}
    # day-shuffle draws fixed once, reused for every target (paired across targets)
    draws = []
    for _ in range(nshuf):
        row = []
        for t in T:
            while True:
                k = int(rng.integers(len(days)))
                if k != t["k"] and not np.isnan(days[k]["open"][t["i"]]):
                    break
            row.append(k)
        draws.append(row)
    for k in TARGETS:
        RU = [trade_k(days[t["k"]], t["i"], t["side"], t["dist"], k) for t in T]
        R = [r for r, _ in RU]; U = [u for _, u in RU]; Rk[label(k)] = np.array(R)
        s = summ(R, U, dates, mid, len(days))
        sh = [np.mean([trade_k(days[kk], t["i"], t["side"], t["dist"], k)[0] for kk, t in zip(row, T)]) for row in draws]
        s["p_shuffle"] = float((np.array(sh) >= s["R"]).mean())
        out[label(k)] = s
    # paired sign-flip permutation: target k vs 2R (two-sided)
    base = Rk["2R"]; prng = np.random.default_rng(99)
    for lab, r in Rk.items():
        d = r - base
        if lab == "2R" or not d.any():
            out[lab]["p_vs_2R"] = None; continue
        flips = prng.choice([-1.0, 1.0], size=(nperm, len(d)))
        null = np.abs((flips * d).mean(1))
        out[lab]["diff_vs_2R"] = float(d.mean())
        out[lab]["p_vs_2R"] = float(((null >= abs(d.mean())).sum() + 1) / (nperm + 1))
    M = np.array([mfe(days[t["k"]], t["i"], t["side"], t["dist"]) for t in T])
    q = lambda a: dict(p25=float(np.percentile(a, 25)), median=float(np.median(a)), p75=float(np.percentile(a, 75)),
                       reach={f"{x:g}R": float((a >= x + TICK / 1e9).mean()) for x in (1, 1.5, 2, 2.5, 3, 4)})
    return out, dict(before_stop=q(M[:, 0]), ignore_stop=q(M[:, 1]))


def main():
    import mnq
    rng = np.random.default_rng(21)
    real = mnq.load_real(); prox = mnq.load_proxy()
    res = {}
    for nm, days in (("IS", real), ("OOS", prox)):
        T, _ = mnq.run_cell(days, "v2 baseline (OR5 D1.0 strong)", "10:30", "2R", nshuf=0)
        for t in T:  # frozen-parity check: 2R column == mnq.trade exactly
            r2, _ = trade_k(days[t["k"]], t["i"], t["side"], t["dist"], 2.0)
            assert abs(r2 - t["R"]) < 1e-9, (t["date"], r2, t["R"])
        print(nm, "n", len(T), "R2", round(float(np.mean([t["R"] for t in T])), 4), "sessions", len(days), flush=True)
        sw, mf = sweep(days, T, rng)
        res[nm] = dict(sessions=len(days), sweep=sw, mfe=mf)
        for lab, s in sw.items():
            print(nm, lab, json.dumps({a: (round(b, 3) if isinstance(b, float) else b) for a, b in s.items()}), flush=True)
        print(nm, "MFE", json.dumps(mf), flush=True)
    json.dump(res, open("res.json", "w"), indent=1)
    print("DONE")


if __name__ == "__main__":
    main()
