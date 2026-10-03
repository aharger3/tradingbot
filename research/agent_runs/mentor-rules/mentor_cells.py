"""mentor-rules: two backtest cells taken from the night-1003 mentor video corpus. Paper research only.

Cell A  bias_orb5_retest : Scarface qhF61rJBOyE. The 1H candle closing at 09:00 ET sets the side; first-5-min
        range break + retest, confirm candle, stop beyond the retest candle, 2R. Control = no bias filter.
Cell B  sweep_reclaim    : J-Dub nCXwyMkUugk / JtqlCOsAJwo / 16pjeegoskc. Undercut of PDL (or poke above PDH)
        that closes back inside within 5 bars; enter next open, stop beyond the sweep extreme, 2R.
Data: real NQ 1m bars on disk, sized as MNQ. IN-SAMPLE ONLY (2025-01-02..2026-09-25); the reserved window
(real NQ 2019-09-26..2024-09-25) is refused by assert. Fills follow frozen orb1m.py: entry next open +1 tick,
stop = min(stop, open) -1 tick, target needs 1 tick through, same bar = stop, flat at 11:00 open -1 tick, $1.24 RT.
"""
import glob, os, json
import numpy as np, pandas as pd

TICK, USD, COMM = 0.25, 2.0, 1.24
FUT = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t01-orb5\fut"
RESERVED_END = "2024-09-25"
IS_START, IS_END = "2025-01-02", "2026-09-25"
SIG_END, CUT = 60, 90  # last signal minute after 09:30 (10:30), flat minute (11:00)


def guard(dates):
    assert all(d > RESERVED_END for d in dates), "reserved OOS window touched"


def arr91(g):
    m = ((g.index.hour * 60 + g.index.minute) - 570).to_numpy()
    ok = (m >= 0) & (m <= 90)
    A = {}
    for k in ("open", "high", "low", "close"):
        a = np.full(91, np.nan)
        a[m[ok]] = g[k].to_numpy()[ok]
        A[k] = a
    return A


def load_days(fut=FUT, start=IS_START, end=IS_END):
    parts = []
    for f in sorted(glob.glob(os.path.join(fut, "NQ*.csv"))):
        d = pd.read_csv(f)
        if d.empty:
            continue
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
        d["k"] = os.path.basename(f).split("_")[0]
        parts.append(d[["ts", "open", "high", "low", "close", "volume", "k"]])
    df = pd.concat(parts).set_index("ts").sort_index()
    t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy()
    rth["date"] = rth.index.strftime("%Y-%m-%d")
    front = rth.groupby(["date", "k"])["volume"].sum().reset_index().sort_values("volume").groupby("date").last()["k"]
    days, prev = [], None
    for D, k in front.items():
        g = rth[(rth.date == D) & (rth.k == k)]
        if len(g) < 200:
            continue
        A = arr91(g)
        if np.isnan(A["open"][:5]).any():
            continue
        c = df[df.k == k]
        hr = c[(c.index >= pd.Timestamp(D + " 08:00", tz="America/New_York")) & (c.index < pd.Timestamp(D + " 09:00", tz="America/New_York"))]
        A["h_open"] = hr.open.iloc[0] if len(hr) else np.nan
        A["h_close"] = hr.close.iloc[-1] if len(hr) else np.nan
        pr = prev if (prev and prev[2] == k) else None
        A["pdh"], A["pdl"] = (pr[0], pr[1]) if pr else (np.nan, np.nan)
        A["date"] = D
        prev = (g.high.max(), g.low.min(), k)
        if start <= D <= end:
            days.append(A)
    guard([a["date"] for a in days])
    return days


def sim(A, side, i, stop, tgt, cut=CUT):
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
    px = O[cut] if not np.isnan(O[cut]) else C[:cut][~np.isnan(C[:cut])][-1]
    return px - TICK * side


def run_trade(A, i, side, dist):
    e = A["open"][i] + TICK * side
    x = sim(A, side, i, e - side * dist, e + side * 2 * dist)
    usd = (x - e) * side * USD - COMM
    return usd / (dist * USD), usd


def signal_bias_orb5(A, use_bias=True):
    """First valid retest of the OR5 break (bias side only if use_bias). Returns (i, side, stop) or None."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    orh, orl = np.nanmax(H[:5]), np.nanmin(L[:5])
    bias = 0
    if use_bias:
        d = A["h_close"] - A["h_open"]
        if np.isnan(d) or d == 0:
            return None
        bias = 1 if d > 0 else -1
    state = None  # (side, level, break_idx)

    def brk(j):
        if C[j] > orh and bias >= 0:
            return (1, orh, j)
        if C[j] < orl and bias <= 0:
            return (-1, orl, j)
        return None

    for j in range(5, SIG_END + 1):
        if np.isnan(C[j]):
            continue
        if state is None:
            state = brk(j)
            continue
        side, lvl, bi = state
        if (C[j] - lvl) * side <= 0:  # close back through: void, re-arm
            state = brk(j)
            continue
        touched = (L[j] <= lvl + TICK) if side > 0 else (H[j] >= lvl - TICK)
        if touched and (C[j] - O[j]) * side > 0 and not np.isnan(O[j + 1]):
            return (j + 1, side, (L[j] - TICK) if side > 0 else (H[j] + TICK))
        if j - bi > 30:
            state = None
    return None


def signal_sweep_reclaim(A, back=5):
    """First PDL undercut / PDH poke that closes back inside within `back` bars. Returns (i, side, stop) or None."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    pdh, pdl = A["pdh"], A["pdl"]
    if np.isnan(pdh) or np.isnan(pdl):
        return None
    st = {1: None, -1: None}  # side -> [armed_at, extreme]
    for j in range(0, SIG_END + 1):
        if np.isnan(C[j]):
            continue
        ref = C[j - 1] if j > 0 and not np.isnan(C[j - 1]) else O[0]
        for side, lvl in ((1, pdl), (-1, pdh)):
            s = st[side]
            if s is None:
                sweep = (L[j] <= lvl - TICK and ref >= lvl) if side > 0 else (H[j] >= lvl + TICK and ref <= lvl)
                if not sweep:
                    continue
                s = st[side] = [j, L[j] if side > 0 else H[j]]
            else:
                s[1] = min(s[1], L[j]) if side > 0 else max(s[1], H[j])
            if j - s[0] > back:
                st[side] = None
                continue
            if (C[j] - lvl) * side > 0 and not np.isnan(O[j + 1]):
                return (j + 1, side, (s[1] - TICK) if side > 0 else (s[1] + TICK))
    return None


def evaluate(days, sigfn, nshuf=1000, seed=7):
    rng = np.random.default_rng(seed)
    trades = []
    for A in days:
        s = sigfn(A)
        if not s:
            continue
        i, side, stop = s
        e = A["open"][i] + TICK * side
        dist = (e - stop) * side
        if dist < 2 * TICK:
            continue
        r, u = run_trade(A, i, side, dist)
        trades.append(dict(date=A["date"], i=int(i), side=int(side), dist=float(dist), R=float(r), usd=float(u)))
    dates = [A["date"] for A in days]
    mid = dates[len(dates) // 2]
    R = np.array([t["R"] for t in trades])
    n = len(R)
    h1 = np.array([t["date"] < mid for t in trades], bool)
    sh = []
    for _ in range(nshuf if n else 0):
        rr = []
        for t in trades:
            while True:
                k = rng.integers(len(days))
                if days[k]["date"] != t["date"] and not np.isnan(days[k]["open"][t["i"]]):
                    break
            rr.append(run_trade(days[k], t["i"], t["side"], t["dist"])[0])
        sh.append(np.mean(rr))
    sh = np.array(sh)
    f = lambda a: float(a.mean()) if len(a) else None
    return dict(sessions=len(days), n=n, win=float((R > 0).mean()) if n else None, meanR=f(R),
                h1_n=int(h1.sum()), h1_meanR=f(R[h1]), h2_n=int((~h1).sum()), h2_meanR=f(R[~h1]),
                p_shuffle=float((sh >= R.mean()).mean()) if n else None, shuf_meanR=f(sh),
                long_share=float(np.mean([t["side"] > 0 for t in trades])) if n else None,
                median_stop_pts=float(np.median([t["dist"] for t in trades])) if n else None, split=mid), trades


CELLS = {
    "A_bias_orb5_retest": lambda A: signal_bias_orb5(A, True),
    "A0_control_no_bias": lambda A: signal_bias_orb5(A, False),
    "B_sweep_reclaim": signal_sweep_reclaim,
}

if __name__ == "__main__":
    days = load_days()
    print("sessions", len(days), days[0]["date"], days[-1]["date"], flush=True)
    out = {}
    for name, fn in CELLS.items():
        res, tr = evaluate(days, fn)
        out[name] = res
        print(name, json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in res.items()}), flush=True)
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json"), "w"), indent=1)
