"""v3-t-mes: MES test of (1) a4 mantra, (2) a2 S-detector, (3) v2 MNQ ORB5 baseline cell. Paper research only.
Engine = v2-t01 orb1m.py signal/sim logic (copied verbatim below, parametrised for a2). Honest fills: next bar open
+1 tick, hard stop min(stop,open)-1 tick, 2R limit needs 1 tick through, same bar = stop, flat at cutoff open -1 tick,
$1.24 RT/micro. Loader rebuilt (v2-s07 omen_data.py gone from disk) from t01-orb5\\fut per-contract CSVs."""
import sys, os, glob, json
import numpy as np, pandas as pd
os.chdir(os.path.dirname(os.path.abspath(__file__)))
TICK = 0.25; RNG = np.random.default_rng(7); NSHUF = 200
FUT = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t01-orb5\fut"
ARCH = r"C:\Users\aharg\Desktop\Projects\tradingbot\data_archive"
SPEC = {"MES": dict(root="ES", usd=5.0, comm=1.24), "MNQ": dict(root="NQ", usd=2.0, comm=1.24)}
CUTS = {"10:30": 60, "10:45": 75, "11:00": 90}
NYSE_CLOSED = set("2024-11-28 2024-12-25 2025-01-01 2025-01-09 2025-01-20 2025-02-17 2025-04-18 2025-05-26 2025-06-19 "
                  "2025-07-04 2025-09-01 2025-11-27 2025-12-25 2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 "
                  "2026-06-19 2026-07-03 2026-09-07".split())

def day_arrays(m, o, h, l, c):
    arr = {}
    ok = (m >= 0) & (m <= 90)
    for k, v in (("open", o), ("high", h), ("low", l), ("close", c)):
        a = np.full(91, np.nan); a[m[ok]] = v[ok]; arr[k] = a
    return arr

def load_fut(sym):
    rows = []
    for f in sorted(glob.glob(os.path.join(FUT, SPEC[sym]["root"] + "*.csv"))):
        if os.path.getsize(f) < 100: continue
        d = pd.read_csv(f); d["contract"] = os.path.basename(f).split("_")[0]; rows.append(d)
    df = pd.concat(rows)
    tcol = [c for c in df.columns if c.lower().startswith("ts")][0]
    df["ts"] = pd.to_datetime(df[tcol], unit="ns", utc=True).dt.tz_convert("America/New_York")
    df["date"] = df["ts"].dt.date.astype(str); df["m"] = df["ts"].dt.hour * 60 + df["ts"].dt.minute - 570
    rth = df[(df.m >= 0) & (df.m < 390)]
    vol = [c for c in df.columns if c.lower() in ("volume", "v")][0]
    front = rth.groupby(["date", "contract"])[vol].sum().reset_index().sort_values(vol).groupby("date").tail(1)
    w = df[(df.m >= 0) & (df.m <= 90)].merge(front[["date", "contract"]], on=["date", "contract"])
    w = w[~w.date.isin(NYSE_CLOSED)]
    cols = {k: [c for c in df.columns if c.lower() in (k, k[0])][0] for k in ("open", "high", "low", "close")}
    return [(d, day_arrays(g.m.to_numpy(), *(g[cols[k]].to_numpy() for k in ("open", "high", "low", "close"))))
            for d, g in w.groupby("date")]

def load_proxy(sym="SPY", ratio=10.08, end="2024-09-26"):
    out = []
    for f in sorted(glob.glob(os.path.join(ARCH, sym, "*.csv"))):
        d = os.path.basename(f)[:10]
        if d >= end: continue
        g = pd.read_csv(f)
        ts = pd.to_datetime(g["Datetime"], utc=True, format="mixed").dt.tz_convert("America/New_York")
        m = (ts.dt.hour * 60 + ts.dt.minute - 570).to_numpy()
        px = {k: np.round(g[k.capitalize()].to_numpy() * ratio / TICK) * TICK for k in ("open", "high", "low", "close")}
        A = day_arrays(m, px["open"], px["high"], px["low"], px["close"])
        if np.sum(~np.isnan(A["open"][:91])) >= 85: out.append((d, A))
    return out

# ---- v2-t01 detection, verbatim; a2 variant = (disp 0.5, tol 0, any trigger, entry <= 30 min) via args ----
def pin(o, h, l, c, side):
    rng = h - l
    if rng <= 0: return False
    body = abs(c - o)
    if side > 0:
        wick = min(o, c) - l
        return wick >= 2 * body and wick >= 0.5 * rng and (c - l) >= 0.66 * rng
    wick = h - max(o, c)
    return wick >= 2 * body and wick >= 0.5 * rng and (h - c) >= 0.66 * rng

def strong(o, h, l, c, side):
    if pin(o, h, l, c, side): return True
    rng = h - l
    if rng <= 0: return False
    body = (c - o) * side; ext = (c - l) if side > 0 else (h - c)
    return body >= 0.6 * rng and ext >= 0.75 * rng

def signal(A, orn, cut, disp_k, trig, tol=TICK, last_entry=None):
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    if np.isnan(H[:orn]).all(): return None
    orh, orl = np.nanmax(H[:orn]), np.nanmin(L[:orn]); rngs = H - L; state = None
    lim = cut if last_entry is None else min(cut, last_entry + 1)
    for j in range(orn, lim - 1):
        if np.isnan(C[j]): continue
        prev = rngs[max(0, j - 14):j]
        atr = np.nanmean(prev) if np.sum(~np.isnan(prev)) >= 3 else np.nan
        if state is None:
            if C[j] > orh: state = [1, orh, j, H[j] - orh, False]
            elif C[j] < orl: state = [-1, orl, j, orl - L[j], False]
            else: continue
            state[4] = disp_k == 0 or state[3] >= disp_k * atr
            continue
        side, lvl, bi, exc, disp = state
        if (C[j] - lvl) * side <= 0:
            state = None
            if C[j] > orh: state = [1, orh, j, H[j] - orh, False]
            elif C[j] < orl: state = [-1, orl, j, orl - L[j], False]
            if state: state[4] = disp_k == 0 or state[3] >= disp_k * atr
            continue
        touched = (L[j] <= lvl + tol) if side > 0 else (H[j] >= lvl - tol)
        if touched and disp and j > bi:
            ok = True if trig == "any" else (pin(O[j], H[j], L[j], C[j], side) if trig == "pin" else strong(O[j], H[j], L[j], C[j], side))
            if ok and not np.isnan(O[j + 1]):
                return (j + 1, side, (L[j] - TICK) if side > 0 else (H[j] + TICK))
        exc = max(exc, (H[j] - lvl) if side > 0 else (lvl - L[j])); state[3] = exc
        if not disp and not np.isnan(atr) and exc >= disp_k * atr: state[4] = True
        if j - bi > 30: state = None
    return None

def flat_px(A, cut, side):
    O, C = A["open"], A["close"]
    if cut < 91 and not np.isnan(O[cut]): return O[cut] - TICK * side
    v = C[:cut][~np.isnan(C[:cut])]; return v[-1] - TICK * side

def sim_2r(A, side, i, e, dist, cut):
    O, H, L = A["open"], A["high"], A["low"]; stop = e - side * dist; tgt = e + side * 2 * dist
    for j in range(i, cut):
        if np.isnan(O[j]): continue
        if side > 0:
            if L[j] <= stop: return min(stop, O[j]) - TICK
            if H[j] >= tgt + TICK: return tgt
        else:
            if H[j] >= stop: return max(stop, O[j]) + TICK
            if L[j] <= tgt - TICK: return tgt
    return flat_px(A, cut, side)

W4 = [(1.0, .30), (2.0, .30), (3.0, .30)]  # + 10% runner to cutoff; BE (entry) after PT1, close-triggered
def sim_4t(A, side, i, e, dist, cut):
    """returns weighted exit-points P&L (per 1 contract). Stop wins same bar (no rung that bar)."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]; stop = e - side * dist
    rem = 1.0; pnl = 0.0; k = 0; be = False
    for j in range(i, cut):
        if np.isnan(O[j]): continue
        hit = (L[j] <= stop) if side > 0 else (H[j] >= stop)
        if hit:
            px = (min(stop, O[j]) - TICK) if side > 0 else (max(stop, O[j]) + TICK)
            return pnl + rem * (px - e) * side
        while k < 3:
            t = e + side * W4[k][0] * dist
            if (H[j] >= t + TICK) if side > 0 else (L[j] <= t - TICK):
                pnl += W4[k][1] * (t - e) * side; rem -= W4[k][1]; k += 1; be = True
            else: break
        if be and rem > 1e-9 and (C[j] - e) * side <= 0:
            return pnl + rem * (C[j] - TICK * side - e) * side
    return pnl + rem * (flat_px(A, cut, side) - e) * side

def trade(A, i, side, dist, cut, sym, exitm):
    e = A["open"][i] + TICK * side; usd, comm = SPEC[sym]["usd"], SPEC[sym]["comm"]
    pts = (sim_2r(A, side, i, e, dist, cut) - e) * side if exitm == "2R" else sim_4t(A, side, i, e, dist, cut)
    u = pts * usd - comm; return u / (dist * usd), u

SETUPS = {"a4-mantra": dict(orn=5, dk=1.0, trig="strong", tol=TICK, le=None),
          "a2-Sdet":   dict(orn=5, dk=0.5, trig="any", tol=0.0, le=30),
          "v2-cell":   dict(orn=5, dk=1.0, trig="strong", tol=TICK, le=None)}

def run_cell(days, sym, st, cutname, exitm, shuffle=True):
    s = SETUPS[st]; cut = CUTS[cutname]; T = []
    for d, A in days:
        sg = signal(A, s["orn"], cut, s["dk"], s["trig"], s["tol"], s["le"])
        if not sg: continue
        i, side, stop = sg; e = A["open"][i] + TICK * side; dist = (e - stop) * side
        if dist < 2 * TICK: continue
        r, u = trade(A, i, side, dist, cut, sym, exitm)
        T.append(dict(date=d, i=int(i), side=int(side), dist=float(dist), R=float(r), usd=float(u)))
    R = np.array([t["R"] for t in T]); dates = [d for d, _ in days]; mid = dates[len(dates) // 2]
    h1 = np.array([t["date"] < mid for t in T], bool)
    res = dict(n=len(T), win=float((R > 0).mean()) if len(T) else 0, R=float(R.mean()) if len(T) else 0,
               h1=float(R[h1].mean()) if h1.any() else None, h2=float(R[~h1].mean()) if (~h1).any() else None,
               usd_day_1u=float(sum(t["usd"] for t in T) / len(days)), R200_day=float(R.sum() * 200 / len(days)),
               stop_med=float(np.median([t["dist"] for t in T])) if T else None, sessions=len(days),
               yr={y: (int(sum(1 for t in T if t["date"][:4] == y)), round(float(np.mean([t["R"] for t in T if t["date"][:4] == y] or [np.nan])), 3))
                   for y in sorted({t["date"][:4] for t in T})})
    eq = np.cumsum([t["R"] * 200 for t in T]); res["maxdd200"] = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if T else 0
    if shuffle and T:
        sh = []
        for _ in range(NSHUF):
            rr = []
            for t in T:
                while True:
                    k = RNG.integers(len(days))
                    if dates[k] != t["date"] and not np.isnan(days[k][1]["open"][t["i"]]): break
                rr.append(trade(days[k][1], t["i"], t["side"], t["dist"], CUTS[cutname], sym, exitm)[0])
            sh.append(np.mean(rr))
        res["p"] = float(max((np.array(sh) >= R.mean()).mean(), 1 / NSHUF)); res["shufR"] = float(np.mean(sh))
    return res, T

if __name__ == "__main__":
    out = {}
    mes = load_fut("MES"); print("MES sessions", len(mes), mes[0][0], mes[-1][0], flush=True)
    mnq = load_fut("MNQ"); print("MNQ sessions", len(mnq), flush=True)
    r, _ = run_cell(mnq, "MNQ", "v2-cell", "10:30", "2R"); out["MNQ|v2-cell|10:30|2R"] = r; print("REPRO MNQ", json.dumps(r), flush=True)
    r, _ = run_cell(mes, "MES", "v2-cell", "10:30", "2R", shuffle=False); print("REPRO MES t01=144/-0.237:", r["n"], round(r["R"], 3), flush=True)
    prox = load_proxy(); print("SPY proxy sessions", len(prox), prox[0][0] if prox else None, prox[-1][0] if prox else None, flush=True)
    trades = {}
    for st in ("a4-mantra", "a2-Sdet"):
        for cn in CUTS:
            for ex in ("2R", "4tier"):
                key = f"MES|{st}|{cn}|{ex}"
                r, T = run_cell(mes, "MES", st, cn, ex); trades[key] = T
                rp, _ = run_cell(prox, "MES", st, cn, ex, shuffle=False)
                r["oos_proxy"] = dict(n=rp["n"], R=rp["R"], h1=rp["h1"], h2=rp["h2"])
                out[key] = r; print(key, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}), flush=True)
    json.dump(out, open("results.json", "w"), indent=1); json.dump(trades, open("trades.json", "w"))
    print("DONE")
