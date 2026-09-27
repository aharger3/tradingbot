"""t01 ORB-5 backtest -- 24-combo grid, honest fills, split-half + day-shuffle.

Data: real ES/NQ 1-min (research/agent_runs/t01-orb5/fut, front month by RTH volume)
      and SPY/QQQ 1-min (data_archive) scaled to ES/NQ points as MES/MNQ proxies.
Fills: entry = next 1m bar open + 1 tick; stop = hard, exits at min(stop, bar open) - 1 tick;
       target = limit, fills only if bar trades 1 tick through; stop wins a same-bar tie;
       time exit = 11:00 bar open - 1 tick (1/2/3R) or last RTH close - 1 tick (10R arm);
       commission $1.24 per micro round trip.
Grid: mode {raw, retest, za} x stop {S1 OR-opposite, S2 tight} x target {1,2,3,10R/EOD} = 24.
Paper research only. No orders.
"""
import sys, os, json, glob, math, random
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\aharg\Desktop\Projects\tradingbot"
ARCH = os.path.join(ROOT, "data_archive")
FUT = os.path.join(HERE, "fut")
TICK = 0.25
SPEC = {"MES": dict(pt=5.0, etf="SPY", root="ES"), "MNQ": dict(pt=2.0, etf="QQQ", root="NQ")}
COMM = 1.24
N_SHUF = int(os.environ.get("N_SHUF", "200"))
TIME_IDX = 90   # 11:00 bar
CUT_IDX = 60    # last entry bar = 10:30 open

def grid_of(df):
    """df with columns minute(0..389), O,H,L,C -> (390,4) float array, NaN where missing, ffilled inside."""
    a = np.full((390, 4), np.nan)
    m = df["m"].values
    ok = (m >= 0) & (m < 390)
    a[m[ok]] = df[["O", "H", "L", "C"]].values[ok]
    last = int(m[ok].max()) if ok.any() else -1
    for i in range(1, last + 1):
        if np.isnan(a[i, 0]):
            c = a[i - 1, 3]
            a[i] = [c, c, c, c]
    return a, last

def load_etf(sym):
    out = {}
    for f in sorted(glob.glob(os.path.join(ARCH, sym, "*.csv"))):
        d = pd.read_csv(f)
        t = d["Datetime"].str.slice(11, 16)
        hh = t.str.slice(0, 2).astype(int); mm = t.str.slice(3, 5).astype(int)
        d["m"] = (hh * 60 + mm) - (9 * 60 + 30)
        d = d[(d["m"] >= 0) & (d["m"] < 390)].rename(columns={"Open": "O", "High": "H", "Low": "L", "Close": "C"})
        if len(d) < 200 or d["m"].min() != 0:
            continue
        a, last = grid_of(d)
        out[os.path.basename(f)[:10]] = (a, last)
    return out

def load_fut(root):
    frames = []
    for f in sorted(glob.glob(os.path.join(FUT, root + "*.csv"))):
        d = pd.read_csv(f)
        if d.empty:
            continue
        d["tk"] = os.path.basename(f)
        frames.append(d)
    if not frames:
        return {}
    d = pd.concat(frames)
    ts = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
    d["day"] = ts.dt.strftime("%Y-%m-%d")
    d["m"] = ts.dt.hour * 60 + ts.dt.minute - (9 * 60 + 30)
    d = d[(d["m"] >= 0) & (d["m"] < 390)].rename(columns={"open": "O", "high": "H", "low": "L", "close": "C"})
    out = {}
    for day, g in d.groupby("day"):
        vol = g.groupby("tk")["volume"].sum()
        g = g[g["tk"] == vol.idxmax()]
        if len(g) < 200 or g["m"].min() != 0:
            continue
        out[day] = grid_of(g.sort_values("m"))
    return out

def atr14(days, bars):
    res, trs, prev = {}, [], None
    for d in days:
        a, last = bars[d]
        h, l, c = np.nanmax(a[:last + 1, 1]), np.nanmin(a[:last + 1, 2]), a[last, 3]
        if len(trs) >= 14:
            res[d] = float(np.mean(trs[-14:]))
        tr = h - l if prev is None else max(h - l, abs(h - prev), abs(l - prev))
        trs.append(tr); prev = c
    return res

# ---------------------------------------------------------------- signals
def signal(a, mode, stopv, atr):
    O, H, L, C = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    orh, orl = H[:5].max(), L[:5].min()
    if mode == "za":
        side = 1 if C[4] > O[0] else (-1 if C[4] < O[0] else 0)
        if side == 0:
            return None
        e = 5
        entry = O[e] + side * TICK
        if stopv == "S1":
            stop = orl if side == 1 else orh
        else:
            if atr is None:
                return None
            stop = entry - side * 0.10 * atr
        return e, side, entry, stop
    i = 5
    while i < CUT_IDX:
        side = 1 if C[i] > orh else (-1 if C[i] < orl else 0)
        if side == 0 or not (orl <= C[i - 1] <= orh):  # break = first close beyond from inside the OR
            i += 1; continue
        lvl = orh if side == 1 else orl
        if mode == "raw":
            e = i + 1
            entry = O[e] + side * TICK
            stop = (orl if side == 1 else orh) if stopv == "S1" else (L[i] - TICK if side == 1 else H[i] + TICK)
            return e, side, entry, stop
        # retest: touch within 10 bars, no close back through, confirm close beyond level with body in direction
        touched, ext = False, None
        j = i + 1
        while j <= min(i + 10, CUT_IDX - 1):
            if (side == 1 and C[j] <= lvl) or (side == -1 and C[j] >= lvl):
                break  # invalid -- close back through
            if (side == 1 and L[j] <= lvl + TICK) or (side == -1 and H[j] >= lvl - TICK):
                touched = True
            if touched:
                ext = L[j] if side == 1 and (ext is None or L[j] < ext) else ext
                ext = H[j] if side == -1 and (ext is None or H[j] > ext) else ext
                if (C[j] - O[j]) * side > 0:
                    e = j + 1
                    entry = O[e] + side * TICK
                    stop = (orl if side == 1 else orh) if stopv == "S1" else lvl - side * TICK  # broken level
                    return e, side, entry, stop
            j += 1
        i = max(j, i + 1)
    return None

def simulate(a, last, e, side, entry, stop, tgt_r):
    risk = (entry - stop) * side
    if not np.isfinite(risk) or risk <= 0 or e > last:
        return None
    O, H, L, C = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    if tgt_r >= 10:
        end, tgt = last, entry + side * 10 * risk
    else:
        end, tgt = min(TIME_IDX, last), entry + side * tgt_r * risk
    sl = slice(e, end + (1 if tgt_r >= 10 else 0))
    if side == 1:
        sh = np.nonzero(L[sl] <= stop)[0]; th = np.nonzero(H[sl] >= tgt + TICK)[0]
    else:
        sh = np.nonzero(H[sl] >= stop)[0]; th = np.nonzero(L[sl] <= tgt - TICK)[0]
    ks = sh[0] if len(sh) else 10**9
    kt = th[0] if len(th) else 10**9
    if ks == 10**9 and kt == 10**9:
        exitp = (C[last] if tgt_r >= 10 else O[end]) - side * TICK
        why = "time"
    elif ks <= kt:
        k = e + ks
        exitp = (min(stop, O[k]) if side == 1 else max(stop, O[k])) - side * TICK
        why = "stop"
    else:
        k = e + kt
        exitp = max(tgt, O[k]) if side == 1 else min(tgt, O[k])
        why = "tgt"
    return (exitp - entry) * side, risk, why

MODES = ["raw", "retest", "za"]; STOPS = ["S1", "S2"]; TGTS = [1, 2, 3, 10]

def run(bars, pt, days, atrs):
    """-> {combo: list of trades (day, e, side, pts, risk_pts, why, entry, stopfrac)}"""
    res = {}
    for mo in MODES:
        for sv in STOPS:
            sigs = {}
            for d in days:
                a, last = bars[d]
                s = signal(a, mo, sv, atrs.get(d))
                if s: sigs[d] = s
            for t in TGTS:
                tr = []
                for d, (e, side, entry, stop) in sigs.items():
                    a, last = bars[d]
                    r = simulate(a, last, e, side, entry, stop, t)
                    if r is None: continue
                    pts, risk, why = r
                    tr.append(dict(day=d, e=e, side=side, pts=pts, risk=risk, why=why,
                                   usd=pts * pt - COMM, r=(pts * pt - COMM) / (risk * pt),
                                   frac=risk / entry))
                res[f"{mo}|{sv}|{t}R"] = tr
    return res

def stats(tr, days, pt):
    n = len(tr); S = len(days)
    if n == 0:
        return dict(n=0)
    usd = np.array([x["usd"] for x in tr]); r = np.array([x["r"] for x in tr])
    eq = np.cumsum(usd); dd = float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
    mid = days[S // 2]
    h1 = [x for x in tr if x["day"] < mid]; h2 = [x for x in tr if x["day"] >= mid]
    months = {}
    for x in tr: months[x["day"][:7]] = months.get(x["day"][:7], 0) + x["usd"]
    allm = sorted({d[:7] for d in days})
    return dict(n=n, win=float((usd > 0).mean()), avgR=float(r.mean()), usd_day=float(usd.sum() / S),
                maxdd=dd, stop_pts_med=float(np.median([x["risk"] for x in tr])),
                h1R=float(np.mean([x["r"] for x in h1])) if h1 else None,
                h2R=float(np.mean([x["r"] for x in h2])) if h2 else None,
                h1_usd_day=float(sum(x["usd"] for x in h1) / (S // 2)),
                h2_usd_day=float(sum(x["usd"] for x in h2) / (S - S // 2)),
                green=sum(1 for m in allm if months.get(m, 0) > 0), months=len(allm), mid=mid)

def shuffle_p(tr, bars, days, pt, tgt_r, rng):
    """Day shuffle: same entry minute, side, stop% and target, replayed on a random other session."""
    if not tr: return None, None
    real = np.mean([x["r"] for x in tr])
    means = []
    for _ in range(N_SHUF):
        rs = []
        for x in tr:
            d = days[rng.randrange(len(days))]
            if d == x["day"]: d = days[(days.index(d) + 1) % len(days)]
            a, last = bars[d]
            if x["e"] > last: continue
            entry = a[x["e"], 0] + x["side"] * TICK
            stop = entry - x["side"] * x["frac"] * entry
            s = simulate(a, last, x["e"], x["side"], entry, stop, tgt_r)
            if s is None: continue
            pts, risk, _ = s
            rs.append((pts * pt - COMM) / (risk * pt))
        means.append(np.mean(rs))
    means = np.array(means)
    return float(((means >= real).sum() + 1) / (N_SHUF + 1)), float(means.mean())

def main():
    src = sys.argv[1]  # "fut" or "proxy"
    out = {}
    rng = random.Random(7)
    for inst, sp in SPEC.items():
        fut = load_fut(sp["root"])
        spy_days = {os.path.basename(f)[:10] for f in glob.glob(os.path.join(ARCH, "SPY", "*.csv"))}
        last_spy = max(spy_days)
        # exchange sessions only (drops CME holiday half-sessions such as MLK day)
        fut = {d: v for d, v in fut.items() if d in spy_days or (d > last_spy and pd.Timestamp(d).weekday() < 5)}
        if src == "fut":
            bars = fut
        else:
            etf = load_etf(sp["etf"])
            fdays = sorted(fut)
            ratios = {d: fut[d][0][0, 0] / etf[d][0][0, 0] for d in fdays if d in etf}
            rd = sorted(ratios)
            bars = {}
            for d, (a, last) in etf.items():
                # nearest futures/ETF ratio (same day if present)
                k = min(rd, key=lambda x: abs(pd.Timestamp(x) - pd.Timestamp(d)).days) if rd else None
                ratio = ratios[k] if k else (10.16 if inst == "MES" else 41.35)
                bars[d] = (a * ratio, last)
        days = sorted(bars)
        atrs = atr14(days, bars)
        days = [d for d in days if d in atrs]  # need ATR history -> same sample for every combo
        res = run(bars, sp["pt"], days, atrs)
        for combo, tr in res.items():
            st = stats(tr, days, sp["pt"])
            tgt = int(combo.split("|")[2][:-1])
            p, shufR = shuffle_p(tr, bars, days, sp["pt"], tgt, rng)
            st.update(p_shuffle=p, shuffle_meanR=shufR, first=days[0], last=days[-1], sessions=len(days))
            out[f"{inst}|{combo}"] = st
            print(inst, combo, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in st.items()}), flush=True)
        # keep trades for the gate
        json.dump({k: v for k, v in res.items()}, open(os.path.join(HERE, f"trades_{src}_{inst}.json"), "w"))
    json.dump(out, open(os.path.join(HERE, f"grid_{src}.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
