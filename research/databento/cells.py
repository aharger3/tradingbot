"""B1 pre-registered cells, matching life-plan 07-money/omen/prereg-next-cells.md EXACTLY. Paper research only.

Registered here: Cell 1 (frozen MNQ mantra) and Cell 2 arm P (Cell 1 trade kept only when the OR level is within
1 ATR of PDH/PDL). Cell 2 arm Z (Zarattini NQ 09:25, flat 15:59) lives in oos_z.py (branch research/zarattini-oos).
Nothing else is registered: no news filter, no 0.5 ATR stop, no Zarattini flat 11:00, no Bonferroni x5.
Each arm is judged alone at p < .05 (prereg "each arm alone"). Window A (2019-09-26..2024-09-25) is reserved:
run() refuses any window touching it unless locked=True (Austin's "locked" tap).
"""
import os, sys
import numpy as np

AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"
WINDOW_A = ("2019-09-26", "2024-09-25")
RNG = np.random.default_rng(7)


def _mnq():
    sys.path.insert(0, AR + r"\v3-t-mnq")
    import mnq
    return mnq


def _atr(A, j):
    rng = A["high"] - A["low"]; prev = rng[max(0, j - 14):j]
    return np.nanmean(prev) if np.sum(~np.isnan(prev)) >= 3 else np.nan


def _lvl(A, side):
    return np.nanmax(A["high"][:5]) if side > 0 else np.nanmin(A["low"][:5])


def mnq_cell(days, keep=None):
    """frozen v2 baseline signal (wick stop, mnq.py unchanged); keep(A, sig) filters."""
    mnq = _mnq(); dk, trig, tol, jm = mnq.SETUPS["v2 baseline (OR5 D1.0 strong)"]; cut = mnq.CUTS["10:30"]; T = []
    for k, A in enumerate(days):
        s = mnq.signal(A, cut, dk, trig, tol, jm)
        if not s: continue
        i, side, stop, j = s
        if keep and not keep(A, dict(i=i, side=side, j=j, lvl=_lvl(A, side), atr=_atr(A, j))): continue
        e = A["open"][i] + mnq.TICK * side; dist = (e - stop) * side
        if not dist >= 2 * mnq.TICK: continue
        r, u = mnq.trade(A, i, side, dist, cut, j, "2R")
        T.append(dict(date=A["date"], k=k, i=i, side=side, dist=dist, j=j, R=r, usd=u))
    return T


def mnq_shuffle(T, days, nshuf):
    """same as mnq.run_cell: each kept trade replayed on a random other session (same minute, side, stop dist)."""
    mnq = _mnq(); cut = mnq.CUTS["10:30"]; sh = []
    for _ in range(nshuf if T else 0):
        rr = []
        for t in T:
            while True:
                k = int(RNG.integers(len(days)))
                if k != t["k"] and not np.isnan(days[k]["open"][t["i"]]): break
            rr.append(mnq.trade(days[k], t["i"], t["side"], t["dist"], cut, t["j"], "2R")[0])
        sh.append(np.mean(rr))
    return np.array(sh)


def pdh_pdl(A, s):
    return any(x is not None and not np.isnan(x) and abs(s["lvl"] - x) <= s["atr"] for x in (A["pdh"], A["pdl"]))


CELLS = {
    "1 frozen MNQ mantra": dict(keep=None),
    "2P mantra + PDH/PDL within 1 ATR": dict(keep=pdh_pdl),
}


def stats(T, sh, span):
    R = np.array([t["R"] for t in T]); n = len(R)
    if n == 0: return dict(n=0)
    d = [t["date"] for t in T]; mid = span[2]; h1 = np.array([x < mid for x in d])
    p = float((sh >= R.mean()).mean()) if len(sh) else None
    return dict(n=n, R=float(R.mean()), h1=float(R[h1].mean()) if h1.any() else None,
                h2=float(R[~h1].mean()) if (~h1).any() else None, p=p)


def touches_window_a(window):
    return window[0] <= WINDOW_A[1] and window[1] >= WINDOW_A[0]


def run(name, days, window, nshuf=200, locked=False):
    """days: mnq.load_real() already filtered to window. window=(lo, hi). Unregistered names raise KeyError."""
    if name not in CELLS: raise KeyError(f"{name!r} is not a pre-registered cell: {list(CELLS)}")
    if touches_window_a(window) and not locked:
        raise PermissionError("window A is reserved: needs Austin's 'locked' (pass locked=True)")
    dates = [A["date"] for A in days]; span = (window[0], window[1], dates[len(dates) // 2])
    T = mnq_cell(days, **CELLS[name]); sh = mnq_shuffle(T, days, nshuf)
    return T, stats(T, sh, span)


def gate(s):
    """prereg floor + bar, each arm alone: n>=30, R>=+0.15, both halves>0, p<.05 (no multiplicity correction)."""
    ok = s.get("n", 0) >= 30 and s["R"] >= 0.15 and (s["h1"] or -1) > 0 and (s["h2"] or -1) > 0 and s["p"] is not None and s["p"] < 0.05
    return "SHIP-ELIGIBLE" if ok else "NO-SHIP"
