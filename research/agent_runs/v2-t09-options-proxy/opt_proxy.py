"""v2-t09: options proxy. Re-runs v2-t01 ORB-1m signals (ES/NQ 1-min, honest futures fills) and maps each trade to a
0DTE SPY/QQQ long call/put priced with Black-Scholes (r=0, no dividends). Paper research only, no orders.
Option fills: BS value at the futures entry/exit price and minute, +/- half-spread + 1 tick slippage per side,
$0.65/contract/side commission. Option R = P&L / planned risk, where planned risk = loss if the stop were hit at
the entry minute (BS at stop price, same T) incl. exit costs."""
import sys, json, math
import numpy as np
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t01-orb-1m")
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
from orb1m import signal, day_arrays, CUTS, TICK
from omen_data import load_fut, SPEC

RNG = np.random.default_rng(9)
NSHUF = 200
ETF = {"MES": ("SPY", 10.08, 0.01, 0.01), "MNQ": ("QQQ", 41.32, 0.02, 0.01)}  # name, fut/etf ratio, half-spread, slip
COMM = 0.65 / 100  # per share per side
YR_MIN = 390 * 252


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(S, K, T, iv, cp):
    if T <= 0:
        return max(0.0, (S - K) * cp)
    v = iv * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * v * v) / v
    d2 = d1 - v
    return cp * (S * ncdf(cp * d1) - K * ncdf(cp * d2))


def delta(S, K, T, iv, cp):
    v = iv * math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * v * v) / v
    return ncdf(d1) if cp > 0 else ncdf(d1) - 1


def sim_t(A, side, i, stop, tgt, cut):
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    for j in range(i, cut):
        if np.isnan(O[j]):
            continue
        if side > 0:
            if L[j] <= stop: return min(stop, O[j]) - TICK, j
            if H[j] >= tgt + TICK: return tgt, j
        else:
            if H[j] >= stop: return max(stop, O[j]) + TICK, j
            if L[j] <= tgt - TICK: return tgt, j
    if cut < 91 and not np.isnan(O[cut]):
        return O[cut] - TICK * side, cut
    v = np.where(~np.isnan(C[:cut]))[0]
    return C[v[-1]] - TICK * side, v[-1]


def rv_iv(A, i):
    c = A["close"][:i]; c = c[~np.isnan(c)]
    if len(c) < 6: return 0.15
    return float(np.clip(np.std(np.diff(np.log(c))) * math.sqrt(YR_MIN), 0.08, 0.60))


def one(sym, A, i, side, dist, cut, ivmode, otm):
    name, ratio, hs, slip = ETF[sym]
    usd, comm = SPEC[sym]["usd_pt"], SPEC[sym]["rt_comm"]
    e = A["open"][i] + TICK * side
    stop, tgt = e - side * dist, e + side * 2 * dist
    x, jx = sim_t(A, side, i, stop, tgt, cut)
    fR = ((x - e) * side * usd - comm) / (dist * usd)
    S0, Sx, Ss = e / ratio, x / ratio, stop / ratio
    iv = rv_iv(A, i) if ivmode == "rv" else ivmode * (1.3 if name == "QQQ" else 1.0)
    K = round(S0) + side * otm
    T0 = (390 - i) / YR_MIN
    Tx = (390 - jx) / YR_MIN
    cost = hs + slip
    p_in = bs(S0, K, T0, iv, side) + cost + COMM
    p_out = max(0.0, bs(Sx, K, Tx, iv, side) - cost) - COMM
    p_stop = max(0.0, bs(Ss, K, T0, iv, side) - cost) - COMM
    risk = p_in - p_stop
    return fR, (p_out - p_in) / risk, bs(S0, K, T0, iv, side), abs(delta(S0, K, T0, iv, side)), risk * 100


def main():
    days = {}
    for sym in ("MES", "MNQ"):
        df = load_fut(sym, "09:30", "11:01")
        days[sym] = [(str(d), day_arrays(g)) for d, g in df.groupby("date")]
    cells = [("MNQ", "10:30", "strong"), ("MNQ", "11:00", "strong"), ("MES", "10:30", "strong")]
    modes = [("rv", 0), (0.10, 0), (0.15, 0), (0.25, 0), ("rv", 1)]
    out = {}
    for sym, cutn, trig in cells:
        D = days[sym]; cut = CUTS[cutn]
        mid = D[len(D) // 2][0]
        sigs = []
        for d, A in D:
            s = signal(A, 5, cut, 1.0, trig)
            if not s: continue
            i, side, stop = s
            e = A["open"][i] + TICK * side
            dist = (e - stop) * side
            if dist < 2 * TICK: continue
            sigs.append((d, A, i, side, dist))
        for ivm, otm in modes:
            rows = [one(sym, A, i, side, dist, cut, ivm, otm) + (d,) for d, A, i, side, dist in sigs]
            F = np.array([r[0] for r in rows]); O = np.array([r[1] for r in rows])
            h1 = np.array([r[5] < mid for r in rows])
            # day shuffle: same minute/side/stop distance on a random other session
            sh = []
            for _ in range(NSHUF):
                acc = []
                for d, A, i, side, dist in sigs:
                    while True:
                        d2, A2 = D[RNG.integers(len(D))]
                        if d2 != d and not np.isnan(A2["open"][i]): break
                    acc.append(one(sym, A2, i, side, dist, cut, ivm, otm)[1])
                sh.append(np.mean(acc))
            p = max(1 / NSHUF, float(np.mean(np.array(sh) >= O.mean())))
            win, los = O[O > 0], O[O <= 0]
            key = f"{ETF[sym][0]}|{cutn}|{trig}|iv={ivm}|otm={otm}"
            out[key] = dict(n=len(O), futR=float(F.mean()), optR=float(O.mean()), win=float((O > 0).mean()),
                            futwin=float((F > 0).mean()), avgwinR=float(win.mean()) if len(win) else 0,
                            avglossR=float(los.mean()) if len(los) else 0, minR=float(O.min()), maxR=float(O.max()),
                            h1=float(O[h1].mean()), n1=int(h1.sum()), h2=float(O[~h1].mean()), n2=int((~h1).sum()),
                            p=p, shufmean=float(np.mean(sh)), prem=float(np.median([r[2] for r in rows])),
                            delta=float(np.median([r[3] for r in rows])), risk1=float(np.median([r[4] for r in rows])),
                            corr=float(np.corrcoef(F, O)[0, 1]))
            print(key, {k: round(v, 3) if isinstance(v, float) else v for k, v in out[key].items()}, flush=True)
    json.dump(out, open("opt_proxy.json", "w"), indent=1)


if __name__ == "__main__":
    # self-check: BS sanity
    assert abs(bs(100, 100, 1, 0.2, 1) - 7.9656) < 1e-3
    assert abs(bs(100, 100, 1, 0.2, -1) - 7.9656) < 1e-3
    main()
