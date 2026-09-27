"""v3-t-nq-es: NQ/ES full-size. Setups: M = a4 mantra (== v2 t01 cell: OR5, disp>=1 ATR, wick retest<=30 bars,
no close-through, strong trigger); D = a2 S-detector (OR5, disp>=0.5 ATR, wick touch tol 0, any trigger, signal <=10:00).
Cutoffs 10:30/10:45/11:00 (last entry + flat). Exits: flat 2R vs 4-tier 30/30/30/10 + BE (t04 rules; named levels =
ORH/ORL/PDH/PDL, no ONH/ONL). Honest: entry next open +1 tick, stop min(stop,open)-1 tick, limits need 1 tick through,
stop wins ties, flat cutoff open -1 tick, $4.50 RT/contract. Size: n=floor($1000/(dist*usd+comm)), skip 0.
OOS proxy: QQQ/SPY 1-min Jan-Sep 2024 x fixed ratio (never used in v2; proxy wick noise ~8%)."""
import sys, json, math, glob, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t01-orb-1m")
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
from omen_data import load_fut, SPEC
import orb1m
from orb1m import signal as msig, pin, strong, TICK

RISK = 1000.0
CUTS = {"10:30": 60, "10:45": 75, "11:00": 90}
W4 = [0.30, 0.30, 0.30, 0.10]
NSH = 200


def dsig(A, cut):
    """a2 detector: OR5, disp>=0.5ATR, wick touch (tol 0), close beyond, any trigger, entry <= 10:00 (min 30)."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    if np.isnan(H[:5]).all(): return None
    orh, orl = np.nanmax(H[:5]), np.nanmin(L[:5]); rngs = H - L; st = None
    last = min(cut, 31) - 1
    for j in range(5, last):
        if np.isnan(C[j]): continue
        prev = rngs[max(0, j - 14):j]; atr = np.nanmean(prev) if np.sum(~np.isnan(prev)) >= 3 else np.nan
        def arm():
            if C[j] > orh: return [1, orh, j, H[j] - orh]
            if C[j] < orl: return [-1, orl, j, orl - L[j]]
            return None
        if st is None: st = arm(); continue
        side, lvl, bi, exc = st
        if (C[j] - lvl) * side <= 0: st = arm(); continue
        touched = (L[j] <= lvl) if side > 0 else (H[j] >= lvl)
        if touched and j > bi and not np.isnan(atr) and exc >= 0.5 * atr and not np.isnan(O[j + 1]):
            return (j + 1, side, (L[j] - TICK) if side > 0 else (H[j] + TICK))
        st[3] = max(exc, (H[j] - lvl) if side > 0 else (lvl - L[j]))
    return None


def ffill(A):
    B = {k: v.copy() for k, v in A.items()}
    for j in range(len(B["open"])):
        if np.isnan(B["open"][j]):
            p = B["close"][j - 1] if j else np.nan
            for k in B: B[k][j] = p
    return B


def ladder(A, i, d, fill, dist, lv):
    R = lambda px: (px - fill) * d / dist
    named = sorted(R(v) for v in lv if v is not None and not np.isnan(v))
    ext = np.nanmax(A["high"][:i]) if d == 1 else np.nanmin(A["low"][:i])
    pt1 = R(ext); c = []
    if pt1 >= 0.20: c.append([pt1, W4[0], "PT1"])
    bey = [x for x in named if x > max(pt1, 0.20)]
    if bey: c.append([bey[0], W4[1], "PT2"])
    p3 = 2.0; near = [x for x in named if abs(x - 2.0) <= 0.25]
    if near: p3 = min(near, key=lambda x: abs(x - 2.0))
    c.append([p3, W4[2], "PT3"]); nx = [x for x in named if x > p3 + 0.20]
    c.append([max(4.0, nx[0]) if nx else 4.0, W4[3], "PT4"])
    c.sort(key=lambda x: x[0]); out = []
    for x in c:
        if out and x[0] - out[-1][0] < 0.20: continue
        out.append(x)
    s = sum(x[1] for x in out); return [(x[0], x[1] / s, x[2]) for x in out]


def alloc(rs, n):
    if n >= len(rs):
        raw = [w * n for _, w, _ in rs]; q = [int(x) for x in raw]
        for k in sorted(range(len(rs)), key=lambda k: -(raw[k] - q[k]))[: n - sum(q)]: q[k] += 1
        for k in range(len(q)):
            if q[k] == 0:
                b = max(range(len(q)), key=lambda z: q[z]); q[b] -= 1; q[k] += 1
        return [(r, q[k]) for k, (r, w, nm) in enumerate(rs) if q[k] > 0], False
    pri = ["PT3", "PT1", "PT4", "PT2"]; names = {nm: r for r, w, nm in rs}
    return sorted([(names[p], 1) for p in pri if p in names][:n]), True


def trade(A, i, d, stop_or_dist, cut, usd, comm, mode, lv, by_dist=False):
    """Returns (R, usd, n, collapsed) or None. A must be ffilled."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    fill = O[i] + d * TICK
    dist = stop_or_dist if by_dist else (fill - stop_or_dist) * d
    if dist < 2 * TICK: return None
    n = int(RISK // (dist * usd + comm))
    if n == 0: return None
    hard = fill - d * dist
    legs, coll = ([(2.0, n)], False) if mode == "2R" else alloc(ladder(A, i, d, fill, dist, lv), n)
    op = [[fill + d * r * dist, q] for r, q in legs]; pnl = 0.0; be = False
    for b in range(i, 91):
        rem = sum(q for _, q in op)
        if rem == 0: break
        if b >= cut:
            pnl += rem * (O[b] - d * TICK - fill) * d; op = []; break
        hi, lo = (H[b], L[b]) if d == 1 else (-L[b], -H[b])
        if lo <= hard * d:
            px = d * min(hard * d, O[b] * d) - d * TICK; pnl += rem * (px - fill) * d; op = []; break
        for leg in op:
            if hi >= leg[0] * d + TICK:
                px = d * max(leg[0] * d, O[b] * d); pnl += leg[1] * (px - fill) * d; leg[1] = 0; be = mode != "2R"
        op = [x for x in op if x[1] > 0]; rem = sum(q for _, q in op)
        if rem and be and C[b] * d <= fill * d:
            px = max(C[b] * d - TICK, fill * d - dist) * d; pnl += rem * (px - fill) * d; op = []; break
    if op: pnl += sum(q for _, q in op) * (C[90] - fill) * d
    u = pnl * usd - n * comm
    return u / (n * dist * usd), u, n, coll


def maxdd(x):
    eq = np.cumsum(x); return float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max()) if len(x) else 0.0


def load_days(sym):
    df = load_fut(sym, "09:30", "16:00")
    days = []; pd_hl = (None, None)
    for d, g in df.groupby("date"):
        A = orb1m.day_arrays(g[(g.ts.dt.hour * 60 + g.ts.dt.minute) <= 660])
        days.append((str(d), A, ffill(A), pd_hl)); pd_hl = (g.high.max(), g.low.min())
    return days


def load_proxy(etf, ratio, start, end):
    days = []; pd_hl = (None, None)
    for f in sorted(glob.glob(rf"C:\Users\aharg\Desktop\Projects\tradingbot\data_archive\{etf}\*.csv")):
        ds = os.path.basename(f)[:10]
        if not (start <= ds <= end): continue
        g = pd.read_csv(f); g["ts"] = pd.to_datetime(g["Datetime"].astype(str).str[:19], errors="coerce")
        g = g.dropna(subset=["ts"]); m = g.ts.dt.hour * 60 + g.ts.dt.minute
        g = g[(m >= 570) & (m < 960)].rename(columns=str.lower)
        if len(g) < 300: continue
        for k in ("open", "high", "low", "close"): g[k] = (g[k] * ratio / TICK).round() * TICK
        A = orb1m.day_arrays(g[(g.ts.dt.hour * 60 + g.ts.dt.minute) <= 660])
        days.append((ds, A, ffill(A), pd_hl)); pd_hl = (g.high.max(), g.low.min())
    return days


def run_cell(days, setup, cut, mode, usd, comm, rng, shuffle=True):
    tr = []
    for ds, A, F, (pdh, pdl) in days:
        s = msig(A, 5, cut, 1.0, "strong") if setup == "M" else dsig(A, cut)
        if not s: continue
        i, d, stop = s
        lv = [np.nanmax(A["high"][:5]), np.nanmin(A["low"][:5]), pdh, pdl]
        r = trade(F, i, d, stop, cut, usd, comm, mode, lv)
        if r: tr.append(dict(date=ds, i=i, d=d, dist=(F["open"][i] + d * TICK - stop) * d, lv=lv, R=r[0], usd=r[1], n=r[2], coll=r[3]))
    dates = [x[0] for x in days]; mid = dates[len(dates) // 2]
    R = np.array([t["R"] for t in tr]); U = np.array([t["usd"] for t in tr])
    h1 = np.array([t["date"] < mid for t in tr], bool)
    res = dict(n=len(tr), win=float((R > 0).mean()) if len(tr) else 0, R=float(R.mean()) if len(tr) else 0,
               t=float(R.mean() / R.std(ddof=1) * math.sqrt(len(R))) if len(R) > 2 else 0,
               usd_day=float(U.sum() / len(days)), maxdd=maxdd(U), sessions=len(days),
               h1=float(R[h1].mean()) if h1.any() else None, h2=float(R[~h1].mean()) if (~h1).any() else None,
               n_med=float(np.median([t["n"] for t in tr])) if tr else None,
               stop_med=float(np.median([t["dist"] for t in tr])) if tr else None,
               coll=float(np.mean([t["coll"] for t in tr])) if tr else None)
    yr = {}
    for t in tr: yr.setdefault(t["date"][:4], []).append(t["R"])
    res["years"] = {y: (len(v), round(float(np.mean(v)), 3)) for y, v in sorted(yr.items())}
    if shuffle and tr:
        sh = []
        for _ in range(NSH):
            rr = []
            for t in tr:
                while True:
                    k = rng.integers(len(days))
                    if dates[k] != t["date"] and not np.isnan(days[k][1]["open"][t["i"]]): break
                F = days[k][2]; x = trade(F, t["i"], t["d"], t["dist"], cut, usd, comm, mode, [None], by_dist=True)
                if x: rr.append(x[0])
            sh.append(np.mean(rr) if rr else 0)
        res["p"] = float(max((np.array(sh) >= R.mean()).mean(), 1 / NSH)); res["shufR"] = float(np.mean(sh))
    return res, tr


def main():
    rng = np.random.default_rng(7); out = {}; trades = {}
    data = {s: load_days(s) for s in ("NQ", "ES")}
    prox = {"NQ": load_proxy("QQQ", 41.35, "2024-01-01", "2024-09-25"), "ES": load_proxy("SPY", 10.16, "2024-01-01", "2024-09-25")}
    for s in data: print(s, len(data[s]), data[s][0][0], data[s][-1][0], "proxy", len(prox[s]), prox[s][0][0] if prox[s] else None, flush=True)
    # engine check: MNQ micro sizing reproduce t01 cell (+0.309R, n=105)
    res, _ = run_cell(data["NQ"], "M", 60, "2R", 2.0, 1.24, rng, shuffle=False); out["CHECK|MNQ|M|10:30|2R|IS"] = res
    print("CHECK MNQ", json.dumps(res), flush=True)
    for sym in ("NQ", "ES"):
        usd, comm = SPEC[sym]["usd_pt"], SPEC[sym]["rt_comm"]
        for setup in ("M", "D"):
            for cn, cut in CUTS.items():
                for mode in ("2R", "4T"):
                    for per, dd in (("IS", data[sym]), ("OOSp", prox[sym])):
                        key = f"{sym}|{setup}|{cn}|{mode}|{per}"
                        res, tr = run_cell(dd, setup, cut, mode, usd, comm, rng, shuffle=True)
                        out[key] = res; trades[key] = [(t["date"], t["usd"]) for t in tr]
                        print(key, json.dumps(res), flush=True)
    json.dump(out, open("grid.json", "w"), indent=1); json.dump(trades, open("trades.json", "w"))
    print("DONE")


if __name__ == "__main__":
    main()
