"""k/four-tier-original: re-run the frozen v3-t-mnq cell (v2 baseline, 10:30) with Austin's ORIGINAL
4-tier exit as first coded in research/exit_lab.py @42b27f4f (2026-08-20, OMEN 5.2 T3), BE-floor fix b3c2482c:
  tranche 1 (30% or 50%) at causal-HOD = close of first bar after a new session HOD that fails to make a higher high;
  rest = one runner: stop -> entry (BE floor), trail 1.0xATR14 (or prior-bar low), flat on structure break
  (bar low < prior low), 5-bar consolidation, or the clock. Fills use the frozen harness conventions. Paper only."""
import sys, json
import numpy as np
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v3-t-mnq")
import mnq
from mnq import TICK, USD, COMM, RISK, MAXN

_orig_trade = mnq.trade
CONS = 5

def atr14(A, i):
    if i < 1: return 0.0
    H, L, C = A["high"][1:i + 1], A["low"][1:i + 1], A["close"][:i]
    tr = np.nanmax(np.vstack([H - L, np.abs(H - C), np.abs(L - C)]), axis=0)[-14:]
    tr = tr[~np.isnan(tr)]
    return float(tr.mean()) if len(tr) else 0.0

def split(n, w1, frac):
    if frac: return w1, 1.0 - w1
    if n == 1: return 1, 0
    q1 = max(1, min(n - 1, int(round(w1 * n)))); return q1, n - q1

def orig_exit(A, i, d, fill, stop, dist, cut, n, w1, trail="atr", frac=False):
    """points (price units x contracts) for the original ladder. d=+1 long / -1 short."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    q1, qr = split(n, w1, frac); f = lambda x: x * d   # mirror to long-space
    cur = np.nanmax(H[:i + 1] if d == 1 else -L[:i + 1])
    hod = None; pts = 0.0; t1 = False; start = i
    def clockpx():
        return O[cut] if cut < 91 and not np.isnan(O[cut]) else C[:cut][~np.isnan(C[:cut])][-1]
    for b in range(i, cut):
        if np.isnan(O[b]): continue
        hi, lo = (H[b], L[b]) if d == 1 else (-L[b], -H[b])
        if not t1:
            if lo <= f(stop):   # hard stop, touch, whole position
                return pts + (q1 + qr) * (d * min(f(stop), f(O[b])) - d * TICK - fill) * d, "stop"
            if hod is None and b > i and hi > cur: hod = b
            elif hod is not None and b > hod:
                ph = H[b - 1] if d == 1 else -L[b - 1]
                if hi <= ph:
                    pts += q1 * (C[b] - d * TICK - fill) * d; t1 = True; start = b
                    ext = np.nanmax(H[:b + 1] if d == 1 else -L[:b + 1]); nse = 0
                    if qr == 0: return pts, "t1"
            continue
        # runner
        if lo <= f(stop):
            return pts + qr * (d * min(f(stop), f(O[b])) - d * TICK - fill) * d, "rstop"
        if trail == "atr": ts = ext - atr14(A, b - 1)
        else: ts = H[b - 1] if d == -1 else L[b - 1]; ts = f(ts)
        ts = max(ts, f(fill))
        if f(C[b]) <= ts:
            return pts + qr * (max(f(C[b]) - TICK, f(stop)) * d - fill) * d, "trail"
        if hi > ext: ext = hi; nse = 0
        else: nse += 1
        pl = L[b - 1] if d == 1 else -H[b - 1]
        if lo < pl: return pts + qr * (C[b] - d * TICK - fill) * d, "struct"
        if nse >= CONS: return pts + qr * (C[b] - d * TICK - fill) * d, "cons"
    px = clockpx() - d * TICK
    return pts + ((0 if t1 else q1) + qr) * (px - fill) * d, "clock"

STATS = {}
def trade(A, i, side, dist, cut, j, exitm):
    if not exitm.startswith("orig"): return _orig_trade(A, i, side, dist, cut, j, exitm)
    _, w, tr, fr = exitm.split("_")  # orig_30_atr_int
    d = side; fill = A["open"][i] + TICK * d; stop = fill - d * dist
    n = min(MAXN, int(RISK // (dist * USD + COMM))) or 1
    frac = fr == "frac"; nn = 1 if frac else n
    pts, why = orig_exit(A, i, d, fill, stop, dist, cut, nn, int(w) / 100, tr, frac)
    STATS.setdefault(exitm, {}).setdefault(why, 0); STATS[exitm][why] += 1
    if frac: pts *= n
    usd = pts * USD - n * COMM
    return usd / (n * dist * USD), usd
mnq.trade = trade

def main(nshuf=200):
    real = mnq.load_real(); prox = mnq.load_proxy(); setup = "v2 baseline (OR5 D1.0 strong)"; res = {}
    for ex in ("2R", "4tier", "orig_30_atr_int", "orig_50_atr_int", "orig_30_bar_int", "orig_30_atr_frac"):
        row = {}
        for nm, dd in (("IS", real), ("OOS", prox)):
            mnq.RNG = np.random.default_rng(7); STATS.clear()
            T, sh = mnq.run_cell(dd, setup, "10:30", ex, nshuf=nshuf)
            row[nm] = mnq.summ(T, sh, dd)
            if nm == "IS" and ex.startswith("orig"):
                mnq.RNG = np.random.default_rng(7); STATS.clear(); mnq.run_cell(dd, setup, "10:30", ex, nshuf=0)
                row["exits"] = dict(STATS.get(ex, {}))
        res[ex] = row; print(ex, json.dumps(row), flush=True)
    json.dump(res, open("res.json", "w"), indent=1); print("DONE")

if __name__ == "__main__":
    main()
