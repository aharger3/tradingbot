"""v2-t08 trade generator: t01 best cell (MNQ OR5, 10:30, strong trigger, disp 1.0 ATR), re-armed after each exit
(up to 3 trades/day) with per-trade path stats for intraday-trail modelling. Paper research only. Same honest fills as
t01: entry next 1m open +1 tick, stop at min(stop,open)-1 tick, target limit needs 1 tick through, same-bar = stop,
flat at cutoff open -1 tick, $1.24 RT per micro."""
import sys, json
import numpy as np
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t01-orb-1m")
from omen_data import load_fut, SPEC
from orb1m import pin, strong, day_arrays, TICK

def signal_from(A, orn, cut, disp_k, trig, start):
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    if np.isnan(H[:orn]).all():
        return None
    orh, orl = np.nanmax(H[:orn]), np.nanmin(L[:orn])
    rngs = H - L
    state = None
    for j in range(max(orn, start), cut - 1):
        if np.isnan(C[j]):
            continue
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
        touched = (L[j] <= lvl + TICK) if side > 0 else (H[j] >= lvl - TICK)
        if touched and disp and j > bi:
            ok = True if trig == "any" else (pin(O[j], H[j], L[j], C[j], side) if trig == "pin" else strong(O[j], H[j], L[j], C[j], side))
            if ok and not np.isnan(O[j + 1]):
                stop = (L[j] - TICK) if side > 0 else (H[j] + TICK)
                return (j + 1, side, stop)
        exc = max(exc, (H[j] - lvl) if side > 0 else (lvl - L[j]))
        state[3] = exc
        if not disp and not np.isnan(atr) and exc >= disp_k * atr:
            state[4] = True
        if j - bi > 30:
            state = None
    return None

def run_path(A, i, side, dist, cut, tmult):
    """returns exit_idx, pnl_pts, mae_pts, giveback_pts (per contract, gross of commission)"""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    e = O[i] + TICK * side
    stop = e - side * dist; tgt = e + side * tmult * dist
    runmax = 0.0; mae = 0.0; gb = 0.0
    for j in range(i, cut):
        if np.isnan(O[j]): continue
        fav = (H[j] - e) if side > 0 else (e - L[j])
        adv = (e - L[j]) if side > 0 else (H[j] - e)
        if (side > 0 and L[j] <= stop) or (side < 0 and H[j] >= stop):
            x = (min(stop, O[j]) - TICK) if side > 0 else (max(stop, O[j]) + TICK)
            p = (x - e) * side
            runmax = max(runmax, fav); mae = max(mae, -p); gb = max(gb, runmax - p)
            return j, p, mae, gb
        if (side > 0 and H[j] >= tgt + TICK) or (side < 0 and L[j] <= tgt - TICK):
            p = tmult * dist
            runmax = max(runmax, p); mae = max(mae, adv); gb = max(gb, runmax + adv)
            return j, p, mae, gb
        runmax = max(runmax, fav); mae = max(mae, adv); gb = max(gb, runmax + adv)
    if cut < 91 and not np.isnan(O[cut]): px = O[cut]
    else:
        v = C[:cut][~np.isnan(C[:cut])]; px = v[-1]
    p = (px - TICK * side - e) * side
    mae = max(mae, -p); gb = max(gb, runmax - p)
    return cut, p, mae, gb

def main():
    sym = "MNQ"; usd, comm = SPEC[sym]["usd_pt"], SPEC[sym]["rt_comm"]
    df = load_fut(sym, "09:30", "11:01")
    days = [(d, day_arrays(g)) for d, g in df.groupby("date")]
    out = {"sessions": [str(d) for d, _ in days], "weekday": [d.weekday() for d, _ in days], "trades": {}}
    for cutname, cut in (("1030", 60), ("1100", 90)):
        tr = []
        for d, A in days:
            start, k = 5, 0
            while k < 3:
                s = signal_from(A, 5, cut, 1.0, "strong", start)
                if not s: break
                i, side, stop = s
                e = A["open"][i] + TICK * side
                dist = (e - stop) * side
                if dist < 2 * TICK:
                    start = i; continue
                x, p, mae, gb = run_path(A, i, side, dist, cut, 2.0)
                perR = dist * usd + comm
                tr.append(dict(date=str(d), k=k, i=int(i), x=int(x), side=int(side), dist=float(dist),
                               usd=float(p * usd - comm), R=float((p * usd - comm) / (dist * usd)),
                               risk=float(perR + TICK * usd), mae=float(mae * usd + comm), gb=float(gb * usd)))
                k += 1; start = x + 1
        out["trades"][cutname] = tr
        f = [t for t in tr if t["k"] == 0]
        print(cutname, "first n", len(f), "avgR", round(np.mean([t["R"] for t in f]), 3),
              "| all n", len(tr), "avgR", round(np.mean([t["R"] for t in tr]), 3),
              "| k>0 n", len(tr) - len(f), "avgR", round(np.mean([t["R"] for t in tr if t["k"] > 0]) if len(tr) > len(f) else 0, 3))
    json.dump(out, open("t08_trades.json", "w"))

if __name__ == "__main__":
    main()
