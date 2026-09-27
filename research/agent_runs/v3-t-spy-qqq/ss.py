"""v3 t-spy-qqq: mantra v3 (orb1m frozen signal, D1.0 strong) vs a2 detector (D0.5 any, <=10:00) on SPY/QQQ shares.
Paper research. Fills: entry next open +$0.01; stop min(stop,open)-0.01 intrabar; 2R/tier limit needs 1c through; stop wins ties;
flat at cutoff open -0.01. Commission $0 (Robinhood) ; COMM5 column = +$0.005/sh/side. Size: $250 risk, notional cap $100k (25k x4 BP)."""
import sys, json, glob, os
import numpy as np, pandas as pd
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-signal")
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t01-orb-1m")
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
import orb1m
T = 0.01; orb1m.TICK = T
ARC = r"C:\Users\aharg\Desktop\Projects\tradingbot\data_archive"
RISK, CAP, NSH = 250.0, 100000.0, 200
CUTS = {"10:30": 60, "10:45": 75, "11:00": 90}
OOS_END = "2024-09-26"  # before v2 futures sample start = never used in v2

def load(sym):
    days = []; prev = None
    for f in sorted(glob.glob(os.path.join(ARC, sym, "*.csv"))):
        d = os.path.basename(f)[:10]
        g = pd.read_csv(f)
        ts = pd.to_datetime(g["Datetime"], utc=True, format="mixed").dt.tz_convert("America/New_York")
        m = (ts.dt.hour * 60 + ts.dt.minute).to_numpy() - 570
        A = {}
        for k in ("open", "high", "low", "close"):
            a = np.full(91, np.nan); ok = (m >= 0) & (m <= 90); a[m[ok]] = g[k.capitalize()].to_numpy()[ok]; A[k] = a
        pre = (m >= -330) & (m < 0); rth = (m >= 0) & (m < 390)
        if np.isnan(A["open"][:60]).sum() > 10: prev = None; continue
        A["pmh"] = g["High"][pre].max() if pre.any() else np.nan; A["pml"] = g["Low"][pre].min() if pre.any() else np.nan
        A["pdh"], A["pdl"] = prev if prev else (np.nan, np.nan)
        prev = (g["High"][rth].max(), g["Low"][rth].min())
        days.append((d, A))
    return days

def a2sig(A, cut):  # a2 best: D0.5, any trigger, signal within 30 min of open
    s = orb1m.signal(A, 5, min(cut, 31), 0.5, "any"); return s

def ladder(A, i, side, e, dist):
    hi = np.nanmax(A["high"][:i]) if side > 0 else np.nanmin(A["low"][:i])
    r = lambda px: (px - e) * side / dist
    c = []
    p1 = r(hi)
    if p1 >= 0.2: c.append([p1, .3])
    lv = [r(x) for x in (A["pdh"], A["pdl"], A["pmh"], A["pml"]) if not np.isnan(x)]
    lv = sorted(x for x in lv if x > max(p1, 0.2))
    if lv: c.append([lv[0], .3])
    c.append([2.0, .3])
    past = [x for x in lv if x > 2.0]
    c.append([max(4.0, past[0]) if past else 4.0, .1])
    c.sort(); out = []
    for x in c:
        if out and x[0] - out[-1][0] < 0.2: out[-1][1] += x[1]
        else: out.append(list(x))
    w = sum(x[1] for x in out); return [(x[0], x[1] / w) for x in out]

def trade(A, i, side, dist, cut, mode):
    O, H, L = A["open"], A["high"], A["low"]
    e = O[i] + T * side; stop = e - side * dist
    legs = [(2.0, 1.0)] if mode == "2R" else ladder(A, i, side, e, dist)
    rem = 1.0; pnl = 0.0; k = 0; be = False
    for j in range(i, cut):
        if np.isnan(O[j]): continue
        s = e if be else stop
        if (L[j] <= s) if side > 0 else (H[j] >= s):
            px = (min(s, O[j]) - T) if side > 0 else (max(s, O[j]) + T)
            return pnl + rem * (px - e) * side
        while k < len(legs):
            tp = e + side * legs[k][0] * dist
            if (H[j] >= tp + T) if side > 0 else (L[j] <= tp - T):
                pnl += legs[k][1] * (tp - e) * side; rem -= legs[k][1]; k += 1; be = True
            else: break
        if rem <= 1e-9: return pnl
    px = O[cut] if cut < 91 and not np.isnan(O[cut]) else A["close"][:cut][~np.isnan(A["close"][:cut])][-1]
    return pnl + rem * (px - T * side - e) * side

def book(days, strat, cut, mode):
    tr = []
    for d, A in days:
        s = orb1m.signal(A, 5, cut, 1.0, "strong") if strat == "mantra" else a2sig(A, cut)
        if not s: continue
        i, side, stop = s
        e = A["open"][i] + T * side; dist = (e - stop) * side
        if dist < 2 * T or dist > 0.05 * e: continue
        pps = trade(A, i, side, dist, cut, mode)
        sh = min(int(RISK // dist), int(CAP // e))
        tr.append(dict(date=d, i=int(i), side=int(side), dist=float(dist), e=float(e), R=pps / dist,
                       R5=(pps - 0.01) / dist, usd=sh * pps, sh=sh))
    return tr

def shuf(days, tr, cut, mode, rng):
    dates = [d for d, _ in days]; out = []
    for _ in range(NSH):
        rr = []
        for t in tr:
            while True:
                k = rng.integers(len(days))
                if dates[k] != t["date"] and not np.isnan(days[k][1]["open"][t["i"]]): break
            rr.append(trade(days[k][1], t["i"], t["side"], t["dist"], cut, mode) / t["dist"])
        out.append(np.mean(rr) if rr else 0)
    return np.array(out)

def st(tr):
    if not tr: return dict(n=0)
    R = np.array([t["R"] for t in tr]); U = np.array([t["usd"] for t in tr])
    eq = np.cumsum(U); dd = float((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
    return dict(n=len(R), win=float((R > 0).mean()), R=float(R.mean()), R5=float(np.mean([t["R5"] for t in tr])), usd=float(U.sum()), dd=dd)

def main():
    rng = np.random.default_rng(7)
    D = {s: load(s) for s in ("SPY", "QQQ")}
    for s in D: print(s, len(D[s]), D[s][0][0], D[s][-1][0], flush=True)
    rows = []; books = {}
    for sym in ("SPY", "QQQ"):
        days = D[sym]; ins = [x for x in days if x[0] >= OOS_END]; oos = [x for x in days if x[0] < OOS_END]
        mid = ins[len(ins) // 2][0]; omid = oos[len(oos) // 2][0]
        for strat in ("mantra", "a2"):
            for cn, cut in CUTS.items():
                for mode in ("2R", "4tier"):
                    tr = book(days, strat, cut, mode); books[(sym, strat, cn, mode)] = tr
                    I = [t for t in tr if t["date"] >= OOS_END]; O = [t for t in tr if t["date"] < OOS_END]
                    row = dict(sym=sym, strat=strat, cut=cn, mode=mode, all=st(tr), ins=st(I), oos=st(O),
                               ins_h1=st([t for t in I if t["date"] < mid]).get("R"), ins_h2=st([t for t in I if t["date"] >= mid]).get("R"),
                               oos_h1=st([t for t in O if t["date"] < omid]).get("R"), oos_h2=st([t for t in O if t["date"] >= omid]).get("R"),
                               yr={y: st([t for t in tr if t["date"][:4] == y]) for y in ("2024", "2025", "2026")},
                               sess_all=len(days), sess_ins=len(ins), sess_oos=len(oos))
                    if tr:
                        sh = shuf(days, tr, cut, mode, rng); row["p"] = float((sh >= row["all"]["R"]).mean()); row["shufR"] = float(sh.mean())
                        if O:
                            sho = shuf(oos, O, cut, mode, rng); row["p_oos"] = float((sho >= row["oos"]["R"]).mean())
                    rows.append(row); print(json.dumps(row, default=float), flush=True)
    json.dump(rows, open("results.json", "w"), default=float, indent=1)
    json.dump({"|".join(k): v for k, v in books.items()}, open("books.json", "w"), default=float)
    print("DONE")

if __name__ == "__main__":
    main()
