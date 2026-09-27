"""v2-t01: ORB break + displacement + wick retest (no close through) + strong trigger candle, 1-min ES/NQ bars
sized as MES/MNQ, fixed 1:2. Paper research only. Honest fills: entry next bar open +1 tick, stop at
min(stop,open)-1 tick, target limit needs 1 tick through, same-bar = stop, flat at cutoff open -1 tick,
$1.24 RT commission per micro."""
import sys, json
import numpy as np, pandas as pd
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
from omen_data import load_fut, SPEC

TICK = 0.25
RNG = np.random.default_rng(7)
NSHUF = 200
CUTS = {"10:30": 60, "10:45": 75, "11:00": 90}  # minutes after 09:30


def pin(o, h, l, c, side):
    rng = h - l
    if rng <= 0:
        return False
    body = abs(c - o)
    if side > 0:
        wick = min(o, c) - l
        return wick >= 2 * body and wick >= 0.5 * rng and (c - l) >= 0.66 * rng
    wick = h - max(o, c)
    return wick >= 2 * body and wick >= 0.5 * rng and (h - c) >= 0.66 * rng


def strong(o, h, l, c, side):
    if pin(o, h, l, c, side):
        return True
    rng = h - l
    if rng <= 0:
        return False
    body = (c - o) * side
    ext = (c - l) if side > 0 else (h - c)
    return body >= 0.6 * rng and ext >= 0.75 * rng


def day_arrays(g):
    m = ((g["ts"].dt.hour * 60 + g["ts"].dt.minute) - 570).to_numpy()
    full = np.full(91, np.nan)
    arr = {}
    for k in ("open", "high", "low", "close"):
        a = full.copy()
        ok = (m >= 0) & (m <= 90)
        a[m[ok]] = g[k].to_numpy()[ok]
        arr[k] = a
    return arr


def sim(A, side, i, stop, tgt, cut):
    """Enter at open of minute i (already slipped entry price passed in by caller). Returns exit px or None."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    for j in range(i, cut):
        if np.isnan(O[j]):
            continue
        if side > 0:
            if L[j] <= stop:
                return min(stop, O[j]) - TICK
            if H[j] >= tgt + TICK:
                return tgt
        else:
            if H[j] >= stop:
                return max(stop, O[j]) + TICK
            if L[j] <= tgt - TICK:
                return tgt
    # flat at cutoff bar open (or last available close)
    if cut < 91 and not np.isnan(O[cut]):
        px = O[cut]
    else:
        v = C[:cut][~np.isnan(C[:cut])]
        px = v[-1]
    return px - TICK * side


def signal(A, orn, cut, disp_k, trig):
    """First valid setup of the day. Returns (entry_minute, side, stop) or None."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    if np.isnan(H[:orn]).all():
        return None
    orh, orl = np.nanmax(H[:orn]), np.nanmin(L[:orn])
    rngs = H - L
    state = None  # (side, level, break_idx, maxexc, displaced)
    for j in range(orn, cut - 1):
        if np.isnan(C[j]):
            continue
        prev = rngs[max(0, j - 14):j]
        atr = np.nanmean(prev) if np.sum(~np.isnan(prev)) >= 3 else np.nan
        if state is None:
            if C[j] > orh:
                state = [1, orh, j, H[j] - orh, False]
            elif C[j] < orl:
                state = [-1, orl, j, orl - L[j], False]
            else:
                continue
            state[4] = disp_k == 0 or state[3] >= disp_k * atr
            continue
        side, lvl, bi, exc, disp = state
        # close through -> setup void; re-arm (a new break may form on either side)
        if (C[j] - lvl) * side <= 0:
            state = None
            if C[j] > orh:
                state = [1, orh, j, H[j] - orh, False]
            elif C[j] < orl:
                state = [-1, orl, j, orl - L[j], False]
            if state:
                state[4] = disp_k == 0 or state[3] >= disp_k * atr
            continue
        touched = (L[j] <= lvl + TICK) if side > 0 else (H[j] >= lvl - TICK)
        if touched and disp and j > bi:
            ok = True if trig == "any" else (pin(O[j], H[j], L[j], C[j], side) if trig == "pin" else strong(O[j], H[j], L[j], C[j], side))
            if ok and not np.isnan(O[j + 1]):
                stop = (L[j] - TICK) if side > 0 else (H[j] + TICK)
                return (j + 1, side, stop)
        # update displacement (excursion beyond level) with this bar
        exc = max(exc, (H[j] - lvl) if side > 0 else (lvl - L[j]))
        state[3] = exc
        if not disp and not np.isnan(atr) and exc >= disp_k * atr:
            state[4] = True
        if j - bi > 30:  # retest must come within 30 bars of the break
            state = None
    return None


def run_trade(A, i, side, dist, cut, usd, comm):
    e = A["open"][i] + TICK * side
    stop = e - side * dist
    tgt = e + side * 2 * dist
    x = sim(A, side, i, stop, tgt, cut)
    pnl_pts = (x - e) * side
    usd_pnl = pnl_pts * usd - comm
    return usd_pnl / (dist * usd), usd_pnl


def maxdd(x):
    eq = np.cumsum(x)
    return float(np.max(np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq)) if len(x) else 0.0


def main():
    out = {}
    variants = []
    for sym in ("MES", "MNQ"):
        for cut in ("10:30", "10:45", "11:00"):
            for trig in ("pin", "strong"):
                variants.append((sym, 5, cut, 1.0, trig))
        variants.append((sym, 15, "11:00", 1.0, "strong"))
        variants.append((sym, 5, "11:00", 0.0, "strong"))  # control: no displacement filter
        variants.append((sym, 5, "11:00", 1.0, "any"))     # control: no trigger-candle filter
    assert len(variants) <= 18
    days_cache = {}
    for sym in ("MES", "MNQ"):
        df = load_fut(sym, "09:30", "11:01")
        days_cache[sym] = [(d, day_arrays(g)) for d, g in df.groupby("date")]
    for (sym, orn, cutname, dk, trig) in variants:
        days = days_cache[sym]
        usd, comm = SPEC[sym]["usd_pt"], SPEC[sym]["rt_comm"]
        cut = CUTS[cutname]
        trades = []
        for d, A in days:
            s = signal(A, orn, cut, dk, trig)
            if not s:
                continue
            i, side, stop = s
            e = A["open"][i] + TICK * side
            dist = (e - stop) * side
            if dist < 2 * TICK:
                continue
            r, u = run_trade(A, i, side, dist, cut, usd, comm)
            trades.append(dict(date=str(d), i=int(i), side=int(side), dist=float(dist), R=float(r), usd=float(u)))
        n = len(trades)
        R = np.array([t["R"] for t in trades]); U = np.array([t["usd"] for t in trades])
        dates = [str(d) for d, _ in days]
        mid = dates[len(dates) // 2]
        h1 = np.array([t["date"] < mid for t in trades], bool)
        # day shuffle: same minute, side, stop distance, replayed on a random other session
        sh = []
        for _ in range(NSHUF):
            rr = []
            for t in trades:
                while True:
                    k = RNG.integers(len(days))
                    if dates[k] != t["date"] and not np.isnan(days[k][1]["open"][t["i"]]):
                        break
                rr.append(run_trade(days[k][1], t["i"], t["side"], t["dist"], cut, usd, comm)[0])
            sh.append(np.mean(rr) if rr else 0)
        sh = np.array(sh)
        key = f"{sym}|OR{orn}|{cutname}|D{dk:g}|{trig}"
        res = dict(n=n, win=float((R > 0).mean()) if n else 0, avgR=float(R.mean()) if n else 0,
                   usd_day=float(U.sum() / len(days)), maxdd=maxdd(U), sessions=len(days),
                   h1n=int(h1.sum()), h2n=int((~h1).sum()),
                   h1R=float(R[h1].mean()) if h1.any() else None, h2R=float(R[~h1].mean()) if (~h1).any() else None,
                   h1_usd_day=float(U[h1].sum() / (len(days) // 2)), h2_usd_day=float(U[~h1].sum() / (len(days) - len(days) // 2)),
                   p_shuffle=float((sh >= (R.mean() if n else 0)).mean()), shuf_meanR=float(sh.mean()),
                   stop_pts_med=float(np.median([t["dist"] for t in trades])) if n else None,
                   long_share=float(np.mean([t["side"] > 0 for t in trades])) if n else None, mid=mid)
        out[key] = res
        print(key, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items()}), flush=True)
        json.dump(trades, open(f"trades_{key.replace('|','_').replace(':','')}.json", "w"))
    json.dump(out, open("grid.json", "w"), indent=1)
    print("DONE")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # synthetic: OR 100-101 for 5 bars, break to 103, retest pin at 101, then run to target
        n = 91
        O = np.full(n, 100.5); H = np.full(n, 101.0); L = np.full(n, 100.0); C = np.full(n, 100.5)
        O[5], H[5], L[5], C[5] = 100.9, 103.0, 100.9, 102.9   # break + displacement
        O[6], H[6], L[6], C[6] = 102.9, 103.0, 102.0, 102.5
        O[7], H[7], L[7], C[7] = 102.0, 102.1, 101.0, 102.05  # pin touching 101 (wick), close well above
        for j in range(8, n):
            O[j], H[j], L[j], C[j] = 102.0 + (j - 8) * 0.5, 102.5 + (j - 8) * 0.5, 101.9 + (j - 8) * 0.5, 102.4 + (j - 8) * 0.5
        A = dict(open=O, high=H, low=L, close=C)
        s = signal(A, 5, 90, 1.0, "pin"); print("sig", s)
        assert s == (8, 1, 100.75), s
        r, u = run_trade(A, 8, 1, 102.25 - 100.75, 90, 5.0, 1.24); print("R", r, u)
        assert abs(r - (2 - 1.24 / 7.5)) < 1e-9
        # close-through voids
        C2 = C.copy(); C2[6] = 100.9
        A2 = dict(open=O, high=H, low=L, close=C2); print("void", signal(A2, 5, 90, 1.0, "pin"))
        # gap through stop
        A3 = {k: v.copy() for k, v in A.items()}; A3["open"][9] = 99.0; A3["low"][9] = 98.9
        print("gapstop R", run_trade(A3, 8, 1, 1.5, 90, 5.0, 1.24))
        print("TESTS OK")
    else:
        main()
