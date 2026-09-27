"""v3-t-mnq: MNQ mantra/a2-detector/v2-baseline x 3 windows x (flat 2R | 4-tier) ; IS = real NQ 1m 2024-09-26..2026-09-25,
OOS = QQQ-proxy (x41.35, snapped) 2024-01-02..2024-09-25 (only pre-v2 data reachable; Polygon key 403 before 2024).
Signal/fill logic imported from frozen v2 orb1m.py (pin/strong/sim), ladder from v2-t04 sc.py rules. Paper research only."""
import sys, json, glob, os, math
import numpy as np, pandas as pd
AR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # research\agent_runs of THIS checkout
REPO = os.path.dirname(os.path.dirname(AR))
sys.path.insert(0, AR + r"\v2-signal"); sys.path.insert(0, AR + r"\v2-t01-orb-1m"); sys.path.insert(0, os.path.join(REPO, "research"))
import orb1m
from orb1m import pin, strong, sim, TICK
USD, COMM, RISK, MAXN = 2.0, 1.24, 200.0, 50
HOL = set("2024-11-28 2024-12-25 2025-01-01 2025-01-09 2025-01-20 2025-02-17 2025-04-18 2025-05-26 2025-06-19 2025-07-04 2025-09-01 2025-11-27 2025-12-25 2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 2026-06-19 2026-07-03 2026-09-07".split())
CUTS = {"10:30": 60, "10:45": 75, "11:00": 90}
W4 = [0.30, 0.30, 0.30, 0.10]
RNG = np.random.default_rng(7)

def arr91(g):
    m = (g.index.hour * 60 + g.index.minute - 570).to_numpy(); ok = (m >= 0) & (m <= 90)
    A = {}
    for k in ("open", "high", "low", "close"):
        a = np.full(91, np.nan); a[m[ok]] = g[k].to_numpy()[ok]; A[k] = a
    return A

def load_real():
    fs = sorted(glob.glob(AR + r"\t01-orb5\fut\NQ*.csv")); parts = []
    for f in fs:
        d = pd.read_csv(f)
        if d.empty: continue
        d.columns = [c.lower() for c in d.columns]
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
        d["k"] = os.path.basename(f).split("_")[0]; parts.append(d[["ts", "open", "high", "low", "close", "volume", "k"]])
    df = pd.concat(parts).set_index("ts").sort_index()
    t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy(); rth["date"] = rth.index.strftime("%Y-%m-%d")
    front = rth.groupby(["date", "k"])["volume"].sum().reset_index().sort_values("volume").groupby("date").last()["k"]
    days = []; prev = None
    for D, k in front.items():
        if D in HOL: continue
        c = df[df.k == k]; g = rth[(rth.date == D) & (rth.k == k)]
        A = arr91(g)
        if np.isnan(A["open"][:5]).all(): continue
        on = c[(c.index > pd.Timestamp(D + " 09:29", tz="America/New_York") - pd.Timedelta(hours=15, minutes=29)) & (c.index < pd.Timestamp(D + " 09:30", tz="America/New_York"))]
        pr = rth[(rth.date == prev) & (rth.k == k)] if prev else None
        A.update(date=D, onh=on.high.max() if len(on) else None, onl=on.low.min() if len(on) else None,
                 pdh=pr.high.max() if pr is not None and len(pr) else None, pdl=pr.low.min() if pr is not None and len(pr) else None)
        days.append(A); prev = D
    return days

def load_proxy(end="2024-09-25"):
    fs = sorted(glob.glob(os.path.join(REPO, "data_archive", "QQQ", "*.csv"))); days = []; prev = None
    for f in fs:
        D = os.path.basename(f)[:10]
        if D > end: break
        d = pd.read_csv(f)
        ts = pd.to_datetime(d["Datetime"], format="mixed", utc=True).dt.tz_convert("America/New_York")
        d = d.set_index(ts); d.columns = [c.lower() for c in d.columns]
        for k in ("open", "high", "low", "close"): d[k] = np.round(d[k] * 41.35 / TICK) * TICK
        t = d.index.hour * 60 + d.index.minute; g = d[(t >= 570) & (t < 960)]; pre = d[t < 570]
        A = arr91(g)
        if np.isnan(A["open"][:5]).all(): continue
        A.update(date=D, onh=pre.high.max() if len(pre) else None, onl=pre.low.min() if len(pre) else None,
                 pdh=prev[0] if prev else None, pdl=prev[1] if prev else None)
        prev = (g.high.max(), g.low.min()); days.append(A)
    return days

def signal(A, cut, dk, trig, tol, jmax):
    """orb1m.signal (OR5) + touch tolerance + last trigger minute jmax. Returns (i, side, stop, j)."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]; orn = 5
    orh, orl = np.nanmax(H[:orn]), np.nanmin(L[:orn]); rngs = H - L; state = None
    for j in range(orn, min(cut - 1, jmax + 1)):
        if np.isnan(C[j]): continue
        prev = rngs[max(0, j - 14):j]; atr = np.nanmean(prev) if np.sum(~np.isnan(prev)) >= 3 else np.nan
        def brk():
            s = [1, orh, j, H[j] - orh, False] if C[j] > orh else ([-1, orl, j, orl - L[j], False] if C[j] < orl else None)
            if s: s[4] = dk == 0 or s[3] >= dk * atr
            return s
        if state is None: state = brk(); continue
        side, lvl, bi, exc, disp = state
        if (C[j] - lvl) * side <= 0: state = brk(); continue
        touched = (L[j] <= lvl + tol) if side > 0 else (H[j] >= lvl - tol)
        if touched and disp and j > bi:
            ok = True if trig == "any" else (pin if trig == "pin" else strong)(O[j], H[j], L[j], C[j], side)
            if ok and not np.isnan(O[j + 1]):
                return (j + 1, side, (L[j] - TICK) if side > 0 else (H[j] + TICK), j)
        exc = max(exc, (H[j] - lvl) if side > 0 else (lvl - L[j])); state[3] = exc
        if not disp and not np.isnan(atr) and exc >= dk * atr: state[4] = True
        if j - bi > 30: state = None
    return None

SETUPS = {"v2 baseline (OR5 D1.0 strong)": (1.0, "strong", TICK, 99),
          "mantra-S (baseline + trigger<=10:00)": (1.0, "strong", TICK, 29),
          "a2 S-detector (D0.5 any tol0 <=10:00)": (0.5, "any", 0.0, 30)}

def rungs(A, fill, d, dist, j):
    R = lambda px: (px - fill) * d / dist
    lv = [A[k] for k in ("pdh", "pdl", "onh", "onl")] + [np.nanmax(A["high"][:5]), np.nanmin(A["low"][:5])]
    named = sorted(R(v) for v in lv if v is not None and not np.isnan(v))
    ext = np.nanmax(A["high"][:j + 1]) if d == 1 else np.nanmin(A["low"][:j + 1]); pt1 = R(ext); c = []
    if pt1 >= 0.20: c.append([pt1, W4[0], "PT1"])
    b = [x for x in named if x > max(pt1, 0.20)]
    if b: c.append([b[0], W4[1], "PT2"])
    p3 = 2.0; near = [x for x in named if abs(x - 2.0) <= 0.25]
    if near: p3 = min(near, key=lambda x: abs(x - 2.0))
    c.append([p3, W4[2], "PT3"]); nx = [x for x in named if x > p3 + 0.20]; c.append([max(4.0, nx[0]) if nx else 4.0, W4[3], "PT4"])
    c.sort(key=lambda x: x[0]); out = []
    for x in c:
        if out and x[0] - out[-1][0] < 0.20: continue
        out.append(x)
    s = sum(x[1] for x in out); return [(x[0], x[1] / s, x[2]) for x in out]

def alloc(rs, n):
    if n >= len(rs):
        raw = [w * n for _, w, _ in rs]; q = [int(x) for x in raw]
        for k in sorted(range(len(rs)), key=lambda k: (-(raw[k] - q[k]), rs[k][0]))[: n - sum(q)]: q[k] += 1
        for k in range(len(q)):
            if q[k] == 0: big = max(range(len(q)), key=lambda z: q[z]); q[big] -= 1; q[k] += 1
        return [(r, q[k]) for k, (r, w, nm) in enumerate(rs) if q[k] > 0]
    pri = ["PT3", "PT1", "PT4", "PT2"]; nm = {x[2]: x[0] for x in rs}
    return sorted([(nm[p], 1) for p in pri if p in nm][:n])

def trade(A, i, side, dist, cut, j, exitm):
    """returns (R_1micro_equiv, usd at $200/R sizing). R = usd/(n*dist*USD)."""
    d = side; fill = A["open"][i] + TICK * d; stop = fill - d * dist
    n = min(MAXN, int(RISK // (dist * USD + COMM)))
    if n == 0: n = 1
    if exitm == "2R":
        x = sim(A, d, i, stop, fill + d * 2 * dist, cut); pts = (x - fill) * d * n
    else:
        legs = [[fill + d * r * dist, q] for r, q in alloc(rungs(A, fill, d, dist, j), n)]
        O, H, L, C = A["open"], A["high"], A["low"], A["close"]; pts = 0.0; be = False
        for b in range(i, cut):
            rem = sum(q for _, q in legs)
            if rem == 0 or np.isnan(O[b]): continue
            lo, hi = (L[b], H[b]) if d == 1 else (-H[b], -L[b])
            if lo <= stop * d:
                pts += rem * ((d * min(stop * d, O[b] * d) - d * TICK) - fill) * d; legs = []; break
            for lg in legs:
                if hi >= lg[0] * d + TICK: pts += lg[1] * (d * max(lg[0] * d, O[b] * d) - fill) * d; lg[1] = 0; be = True
            legs = [x for x in legs if x[1] > 0]; rem = sum(q for _, q in legs)
            if rem and be and C[b] * d <= fill * d:
                pts += rem * (max(C[b] * d - TICK, fill * d - dist) * d - fill) * d; legs = []; break
        rem = sum(q for _, q in legs)
        if rem:
            px = O[cut] if cut < 91 and not np.isnan(O[cut]) else C[:cut][~np.isnan(C[:cut])][-1]
            pts += rem * (px - d * TICK - fill) * d
    usd = pts * USD - n * COMM
    return usd / (n * dist * USD), usd

def run_cell(days, setup, cutn, exitm, nshuf=200):
    dk, trig, tol, jm = SETUPS[setup]; cut = CUTS[cutn]; T = []
    for k, A in enumerate(days):
        s = signal(A, cut, dk, trig, tol, jm)
        if not s: continue
        i, side, stop, j = s; e = A["open"][i] + TICK * side; dist = (e - stop) * side
        if dist < 2 * TICK: continue
        r, u = trade(A, i, side, dist, cut, j, exitm)
        T.append(dict(date=A["date"], k=k, i=i, side=side, dist=dist, j=j, R=r, usd=u))
    sh = []
    if nshuf and T:
        for _ in range(nshuf):
            rr = []
            for t in T:
                while True:
                    k = int(RNG.integers(len(days)))
                    if k != t["k"] and not np.isnan(days[k]["open"][t["i"]]): break
                rr.append(trade(days[k], t["i"], t["side"], t["dist"], cut, t["j"], exitm)[0])
            sh.append(np.mean(rr))
    return T, np.array(sh)

def summ(T, sh, days):
    n = len(T); R = np.array([t["R"] for t in T]); U = np.array([t["usd"] for t in T])
    if n == 0: return dict(n=0)
    dates = [A["date"] for A in days]; mid = dates[len(dates) // 2]; h1 = np.array([t["date"] < mid for t in T])
    eq = np.cumsum(U); dd = float(np.max(np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq))
    yr = {}
    for t in T: yr.setdefault(t["date"][:4], []).append(t["R"])
    return dict(n=n, win=float((R > 0).mean()), R=float(R.mean()), h1=float(R[h1].mean()) if h1.any() else None,
                h2=float(R[~h1].mean()) if (~h1).any() else None, p=float((sh >= R.mean()).mean()) if len(sh) else None,
                usd_day=float(U.sum() / len(days)), dd=dd, yr={y: (len(v), round(float(np.mean(v)), 3)) for y, v in sorted(yr.items())})

def main():
    real = load_real(); prox = load_proxy()
    print("real", len(real), real[0]["date"], real[-1]["date"], "proxy", len(prox), prox[0]["date"], prox[-1]["date"], flush=True)
    # proxy calibration over the real period (does the proxy reproduce the real result?)
    pov = load_proxy(end="2026-09-25"); pov = [A for A in pov if A["date"] >= "2024-09-26"]
    res = {}; trades = {}
    for setup in SETUPS:
        for cutn in CUTS:
            for ex in ("2R", "4tier"):
                key = f"{setup}|{cutn}|{ex}"; row = {}
                for nm, dd in (("IS", real), ("OOS", prox), ("PXcal", pov)):
                    T, sh = run_cell(dd, setup, cutn, ex, nshuf=200 if nm != "PXcal" else 0)
                    row[nm] = summ(T, sh, dd); trades[key + "|" + nm] = T
                res[key] = row; print(key, json.dumps(row), flush=True)
    json.dump(res, open("res.json", "w"), indent=1); json.dump(trades, open("trades.json", "w"), default=float)
    # walk-forward: choose best cell (mean R, n>=20) on all data before year Y; report it in year Y
    allT = {k.rsplit("|", 1)[0]: [] for k in trades}
    for k, T in trades.items():
        if not k.endswith("PXcal"): allT[k.rsplit("|", 1)[0]] += T
    for Y in ("2025", "2026"):
        best = max(allT, key=lambda c: np.mean([t["R"] for t in allT[c] if t["date"] < Y] or [-9]) if sum(t["date"] < Y for t in allT[c]) >= 20 else -9)
        tr = [t["R"] for t in allT[best] if t["date"][:4] == Y]
        print("WF", Y, best, "train R", round(np.mean([t["R"] for t in allT[best] if t["date"] < Y]), 3), "test n", len(tr), "R", round(float(np.mean(tr)), 3) if tr else None, flush=True)
    print("DONE")

if __name__ == "__main__":
    main()
