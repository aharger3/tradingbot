"""mentor-rules round 2: three more rule cells from the night-1003 mentor video corpus. Paper research only.

FIT WINDOW ONLY: 2024-09-26 -> 2026-09-25. Window A (real NQ 2019-09-26 -> 2024-09-25) is reserved and never loaded:
NQ rows dated on or before 2024-09-25 are dropped right after each file is read, and every session is asserted.
Stock rows before the fit window are read ONLY to build the prior-session levels and the daily EMAs (no trade is ever
taken outside the fit window).

Cell C  rejection      NQ     PDH/PDL rejection (pop and fade / level bounce), J-Dub I9f1J6DYjdI + 6 more videos
Cell D  three_bar      stocks 3-bar entry model at PDH/PDL on 5m candles, J-Dub nCXwyMkUugk + _McZebfqzds
Cell E  ema_pdh        stocks daily 9/21 EMA uptrend filter on PDH break + retest, FIzcNCL7zfE/Kc7947yZBgM/ZiU4HVCpo10/_McZebfqzds

The grid, the primary-variant rule, the std bar, the cost model and the permutation are in declared.json, written and
committed BEFORE any variant was evaluated on real data. Fills follow the frozen orb1m.py convention (entry next open
+1 tick adverse, stop exit one tick worse than the stop (or the open if it gapped through), target needs 1 tick through,
SAME BAR = STOP WINS, flat at the 11:00 open one tick worse) with the instrument's own tick and costs.
"""
import glob, json, os
import numpy as np
import pandas as pd

FIT_START, FIT_END = "2024-09-26", "2026-09-25"
RESERVED_END = "2024-09-25"
WARM_START = "2024-01-02"           # stocks only: prior-session levels and EMA warm-up, never traded
SIG_LAST = 61                       # latest entry minute index (10:31); signal bar closes at or before 10:30
CUT = 90                            # flat at the 11:00 open

AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"
FUT = AR + r"\t01-orb5\fut"
ARCHIVE = r"C:\Users\aharg\Desktop\Projects\tradingbot\data_archive"

NYSE_HOL = set("2024-11-28 2024-12-25 2025-01-01 2025-01-09 2025-01-20 2025-02-17 2025-04-18 2025-05-26 2025-06-19 "
               "2025-07-04 2025-09-01 2025-11-27 2025-12-25 2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 "
               "2026-06-19 2026-07-03 2026-09-07".split())


def _calendar(start="2024-09-25", end=FIT_END):
    days = pd.bdate_range(start, end).strftime("%Y-%m-%d")
    return [d for d in days if d not in NYSE_HOL]


CAL = _calendar()                                   # NYSE sessions, fit window plus the day before it
PREV_OF = dict(zip(CAL[1:], CAL[:-1]))              # a prior-session level is used only if it is the PREVIOUS NYSE session

SPEC_NQ = dict(name="NQ (sized as MNQ)", tick=0.25, pv=2.0, comm=1.24)
SPEC_STK = dict(name="stocks/ETFs (shares)", tick=0.01, pv=1.0, comm=0.01)   # $0.01 slip/side, $0.005/sh/side


def min_dist(spec, e):
    """minimum stop distance in price units; a smaller stop is skipped (the day is dropped, no second try)"""
    if spec is SPEC_NQ:
        return 2 * spec["tick"]
    return max(0.03, 0.0005 * e)


def guard_nq(dates):
    assert all(d > RESERVED_END for d in dates), "reserved window A touched"


# ----------------------------------------------------------------------------------------------- bars
def arr91(minutes, o, h, l, c):
    """minute-of-session arrays 0..90 (09:30 .. 11:00 ET) from rows already filtered to RTH minutes"""
    m = np.asarray(minutes) - 570
    ok = (m >= 0) & (m <= 90)
    A = {}
    for k, v in (("open", o), ("high", h), ("low", l), ("close", c)):
        a = np.full(91, np.nan)
        a[m[ok]] = np.asarray(v, float)[ok]
        A[k] = a
    return A


def agg(A, tf):
    """tf-minute candles aligned at 09:30 over minutes 0..89. Candle b covers [b*tf, (b+1)*tf - 1] and is complete
    (known) at minute (b+1)*tf, so the earliest entry is the open of that minute."""
    if tf == 1:
        return A["open"][:90], A["high"][:90], A["low"][:90], A["close"][:90]
    nb = 90 // tf
    O = np.full(nb, np.nan); H = O.copy(); L = O.copy(); C = O.copy()
    for b in range(nb):
        sl = slice(b * tf, (b + 1) * tf)
        oo, hh, ll, cc = A["open"][sl], A["high"][sl], A["low"][sl], A["close"][sl]
        ok = ~np.isnan(oo)
        if not ok.any():
            continue
        O[b] = oo[ok][0]; C[b] = cc[ok][-1]; H[b] = hh[ok].max(); L[b] = ll[ok].min()
    return O, H, L, C


def last_bar(tf):
    """highest candle index b whose completion minute (b+1)*tf is a legal entry minute"""
    return SIG_LAST // tf - 1


# ----------------------------------------------------------------------------------------------- fills
def sim(A, side, i, stop, tgt, spec, cut=CUT):
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    tick = spec["tick"]
    eps = 1e-9                                   # cent prices are not exact in floating point
    if side > 0:
        sh = L[i:cut] <= stop + eps
        th = H[i:cut] >= tgt + tick - eps
    else:
        sh = H[i:cut] >= stop - eps
        th = L[i:cut] <= tgt - tick + eps
    si = int(sh.argmax()) if sh.any() else None
    ti = int(th.argmax()) if th.any() else None
    if si is not None and (ti is None or si <= ti):          # same bar: stop wins
        o = O[i + si]
        return (min(stop, o) - tick) if side > 0 else (max(stop, o) + tick)
    if ti is not None:
        return tgt
    px = O[cut] if not np.isnan(O[cut]) else C[:cut][~np.isnan(C[:cut])][-1]
    return px - tick * side


def run_trade(A, i, side, dist, spec):
    e = A["open"][i] + spec["tick"] * side
    x = sim(A, side, i, e - side * dist, e + side * 2 * dist, spec)
    usd = (x - e) * side * spec["pv"] - spec["comm"]
    return usd / (dist * spec["pv"]), usd


# ----------------------------------------------------------------------------------------------- loaders
def load_nq(fut=FUT, start=FIT_START, end=FIT_END):
    """real NQ 1-min, front month by RTH volume, fit window only. Each day dict has prior-session RTH high/low/close
    from the SAME contract (NaN when the prior session is missing or on another contract)."""
    parts = []
    for f in sorted(glob.glob(os.path.join(fut, "NQ*.csv"))):
        d = pd.read_csv(f)
        if d.empty:
            continue
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
        dd = d["ts"].dt.strftime("%Y-%m-%d")
        d = d[(dd >= start) & (dd <= end)]                # reserved rows are gone before anything else happens
        if d.empty:
            continue
        d["k"] = os.path.basename(f).split("_")[0]
        parts.append(d[["ts", "open", "high", "low", "close", "volume", "k"]])
    df = pd.concat(parts).set_index("ts").sort_index()
    t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy()
    rth["date"] = rth.index.strftime("%Y-%m-%d")
    assert rth["date"].min() > RESERVED_END
    front = rth.groupby(["date", "k"])["volume"].sum().reset_index().sort_values("volume").groupby("date").last()["k"]
    days, prev = [], None
    for D, k in front.items():
        if D in NYSE_HOL:                              # NQ trades a thin holiday session; the stock market is shut
            continue
        g = rth[(rth.date == D) & (rth.k == k)]
        if len(g) < 200:
            continue
        mins = (g.index.hour * 60 + g.index.minute).to_numpy()
        A = arr91(mins, g.open, g.high, g.low, g.close)
        if np.isnan(A["open"][:5]).any():
            continue
        pr = prev if (prev and prev[3] == k and prev[4] == PREV_OF.get(D)) else None
        A["pdh"], A["pdl"], A["pdc"] = (pr[0], pr[1], pr[2]) if pr else (np.nan, np.nan, np.nan)
        A["date"], A["sym"] = D, "NQ"
        prev = (g.high.max(), g.low.min(), g.close.iloc[-1], k, D)
        days.append(A)
    guard_nq([a["date"] for a in days])
    return [a for a in days if not np.isnan(a["pdh"])]


def load_stock(sym, archive=ARCHIVE, warm=WARM_START, end=FIT_END):
    """one symbol, 1-min RTH bars. Returns fit-window day dicts with prior-session levels and the daily EMA9/EMA21
    known at the prior close (built from sessions since `warm`). Sessions with < 300 RTH bars are dropped; a day
    whose open is > 35% from the prior close (split artefact) is dropped, and so is a day whose prior archive session is
    not the previous NYSE session (a hole in the archive). Both are counted. Returns (days, counts)."""
    p = os.path.join(archive, sym)
    rows, skipped_split, skipped_gap = [], 0, 0
    for f in sorted(os.listdir(p)):
        D = f[:10]
        if not f.endswith(".csv") or D < warm or D > end:
            continue
        d = pd.read_csv(os.path.join(p, f), usecols=["Datetime", "Open", "High", "Low", "Close"])
        if d.empty:
            continue
        s = d["Datetime"].astype(str)
        mins = (s.str.slice(11, 13).astype(int) * 60 + s.str.slice(14, 16).astype(int)).to_numpy()
        ok = (mins >= 570) & (mins < 960)
        if ok.sum() < 300:
            continue
        d = d[ok]; mins = mins[ok]
        A = arr91(mins, d.Open, d.High, d.Low, d.Close)
        if np.isnan(A["open"][:5]).any():
            continue
        A["date"], A["sym"] = D, sym
        A["_dh"], A["_dl"], A["_dc"] = float(d.High.max()), float(d.Low.min()), float(d.Close.iloc[-1])
        rows.append(A)
    closes = pd.Series([a["_dc"] for a in rows])
    e9 = closes.ewm(span=9, adjust=False).mean().to_numpy()
    e21 = closes.ewm(span=21, adjust=False).mean().to_numpy()
    out = []
    for n in range(1, len(rows)):
        A = rows[n]
        if not (FIT_START <= A["date"] <= end):
            continue
        pv = rows[n - 1]
        if pv["date"] != PREV_OF.get(A["date"]):         # a missing archive day: the prior-session levels would be stale
            skipped_gap += 1
            continue
        if not (0.65 <= A["open"][0] / pv["_dc"] <= 1.5):
            skipped_split += 1
            continue
        A["pdh"], A["pdl"], A["pdc"] = pv["_dh"], pv["_dl"], pv["_dc"]
        A["ema9"], A["ema21"] = float(e9[n - 1]), float(e21[n - 1])
        A["up"] = bool(A["pdc"] > A["ema9"] and A["pdc"] > A["ema21"])
        out.append(A)
    return out, dict(split_skips=skipped_split, gap_skips=skipped_gap)


# ----------------------------------------------------------------------------------------------- signals
def signal_rejection(A, tol_ticks, stop_mode):
    """Cell C. First 1-min rejection of the prior-day high (short) or low (long) in 09:30-10:30.
    Short: the bar's high reaches PDH - tol (or beyond), the previous close was under PDH, the bar closes under PDH
    and closes red. Long mirrors at PDL (low reaches PDL + tol, previous close above, closes above and green).
    Entry is the next minute's open. Stop = rejection bar extreme +/- 1 tick ('candle') or the extreme of the last
    5 bars including it ('push5'). Returns (i, side, stop) or None."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    pdh, pdl = A["pdh"], A["pdl"]
    if np.isnan(pdh) or np.isnan(pdl):
        return None
    tol = tol_ticks * SPEC_NQ["tick"]
    tick = SPEC_NQ["tick"]
    for j in range(0, last_bar(1) + 1):
        if np.isnan(C[j]) or np.isnan(O[j + 1]):
            continue
        if j > 0 and not np.isnan(C[j - 1]):
            ref = C[j - 1]
        else:
            ref = A["pdc"] if not np.isnan(A["pdc"]) else O[0]
        lo = max(0, j - 4)
        if H[j] >= pdh - tol and ref < pdh and C[j] < pdh and C[j] < O[j]:
            ext = H[j] if stop_mode == "candle" else np.nanmax(H[lo:j + 1])
            return (j + 1, -1, ext + tick)
        if L[j] <= pdl + tol and ref > pdl and C[j] > pdl and C[j] > O[j]:
            ext = L[j] if stop_mode == "candle" else np.nanmin(L[lo:j + 1])
            return (j + 1, 1, ext - tick)
    return None


def signal_three_bar(A, tol_pct, confirm, tf=5):
    """Cell D. Three consecutive tf-minute candles k (lead), r (reaction), m (confirm) at the prior-day high / low.
    Bearish at PDH: lead is green and its HIGH is within tol_pct of PDH (either side); reaction is red; confirm closes
    under the lead's low ('extreme') or under the lead's open = body bottom ('body'). Bullish at PDL mirrors (red lead,
    green reaction, confirm closes over the lead's high or open). Entry = open of the minute after the confirm candle
    closes; stop = extreme of the three candles +/- 1 tick. First signal of the day, either side."""
    pdh, pdl = A["pdh"], A["pdl"]
    if np.isnan(pdh) or np.isnan(pdl):
        return None
    tick = SPEC_STK["tick"]
    O, H, L, C = agg(A, tf)
    for m in range(2, last_bar(tf) + 1):
        k, r = m - 2, m - 1
        if np.isnan([O[k], O[r], O[m]]).any():
            continue
        i = (m + 1) * tf
        if np.isnan(A["open"][i]):
            continue
        if pdh * (1 - tol_pct) <= H[k] <= pdh * (1 + tol_pct) and C[k] > O[k] and C[r] < O[r]:
            lvl = L[k] if confirm == "extreme" else O[k]
            if C[m] < lvl:
                return (i, -1, max(H[k], H[r], H[m]) + tick)
        if pdl * (1 - tol_pct) <= L[k] <= pdl * (1 + tol_pct) and C[k] < O[k] and C[r] > O[r]:
            lvl = H[k] if confirm == "extreme" else O[k]
            if C[m] > lvl:
                return (i, 1, min(L[k], L[r], L[m]) - tick)
    return None


def signal_pdh_retest(A, tf, stop_mode, ema_filter):
    """Cell E. Long only. Break = a tf candle closes over PDH after the previous close (prior-day close for the first
    candle) was at or under it. Retest = a later candle (within 30 minutes of the break) whose low is within 1 tick of
    PDH or lower, closes green and closes over PDH. A close back at or under PDH voids the break (a new break may arm).
    Entry = open of the minute after the retest candle closes. Stop = retest candle low - 1 tick ('candle') or
    PDH - 1 tick ('level'). ema_filter: only when the prior close was above both the daily EMA9 and EMA21."""
    if ema_filter and not A["up"]:
        return None
    pdh = A["pdh"]
    if np.isnan(pdh):
        return None
    tick = SPEC_STK["tick"]
    O, H, L, C = agg(A, tf)
    b0 = None
    for b in range(0, last_bar(tf) + 1):
        if np.isnan(C[b]):
            continue
        ref = C[b - 1] if b > 0 and not np.isnan(C[b - 1]) else A["pdc"]
        if b0 is None:
            if C[b] > pdh and ref <= pdh:
                b0 = b
            continue
        if C[b] <= pdh:
            b0 = None
            continue
        if L[b] <= pdh + tick and C[b] > O[b]:
            i = (b + 1) * tf
            if np.isnan(A["open"][i]):
                continue
            return (i, 1, (L[b] - tick) if stop_mode == "candle" else (pdh - tick))
        if (b - b0) * tf >= 30:
            b0 = None
    return None


# ----------------------------------------------------------------------------------------------- evaluation
def build_trades(days, sigfn, spec):
    out, skipped = [], 0
    for A in days:
        s = sigfn(A)
        if not s:
            continue
        i, side, stop = s
        e = A["open"][i] + spec["tick"] * side
        dist = (e - stop) * side
        if dist < min_dist(spec, e):
            skipped += 1
            continue
        r, u = run_trade(A, i, side, dist, spec)
        out.append(dict(sym=A["sym"], date=A["date"], i=int(i), side=int(side), dist=float(dist),
                        pct=float(dist / e), R=float(r), usd=float(u), up=bool(A.get("up", True))))
    return out, skipped


def summarize(trades, split, skipped=0):
    R = np.array([t["R"] for t in trades])
    n = len(R)
    f = lambda a: float(a.mean()) if len(a) else None
    h1 = np.array([t["date"] < split for t in trades], bool)
    by_day = {}
    for t in trades:
        by_day[t["date"]] = by_day.get(t["date"], 0.0) + t["R"]
    top5 = None
    if n and R.sum() > 0:
        top5 = float(sum(sorted(by_day.values(), reverse=True)[:5]) / R.sum())
    return dict(n=n, skipped_min_dist=skipped, win=float((R > 0).mean()) if n else None, meanR=f(R),
                h1_n=int(h1.sum()), h1_meanR=f(R[h1]), h2_n=int((~h1).sum()), h2_meanR=f(R[~h1]),
                long_share=float(np.mean([t["side"] > 0 for t in trades])) if n else None,
                median_stop_pct=float(np.median([t["pct"] for t in trades])) if n else None,
                top5_days_share=top5, trade_days=len(by_day))


def clears_std(s, p):
    """the canon std bar: n >= 30, mean R >= +0.15, both halves > 0, shuffle p < .05"""
    return bool(s["n"] >= 30 and s["meanR"] is not None and s["meanR"] >= 0.15
                and (s["h1_meanR"] or 0) > 0 and (s["h2_meanR"] or 0) > 0 and p is not None and p < 0.05)


def shuffle_means(variants, sessions, spec, ndraw=2000, seed=7):
    """Day-level permutation. Each draw maps every session date to a different random date (the same map for every
    symbol and every variant, so same-day trades stay clustered); each trade is replayed on its own symbol's session
    on the mapped date with the same entry minute, side and stop as a share of price. If that symbol has no usable
    session on the mapped date, a random other date of that symbol is used. Returns {variant: array of mean R}."""
    rng = np.random.default_rng(seed)
    dates = sorted({d for sym in sessions for d in sessions[sym]})
    n = len(dates)
    didx = {d: k for k, d in enumerate(dates)}
    sym_dates = {s: sorted(sessions[s]) for s in sessions}
    out = {v: np.empty(ndraw) for v in variants}
    ar = np.arange(n)
    for t in range(ndraw):
        m = rng.integers(0, n - 1, size=n)
        m = m + (m >= ar)
        for v, trs in variants.items():
            rs = []
            for tr in trs:
                A2 = sessions[tr["sym"]].get(dates[m[didx[tr["date"]]]])
                if A2 is None or np.isnan(A2["open"][tr["i"]]):
                    sd = sym_dates[tr["sym"]]
                    while True:
                        d2 = sd[rng.integers(len(sd))]
                        A2 = sessions[tr["sym"]][d2]
                        if d2 != tr["date"] and not np.isnan(A2["open"][tr["i"]]):
                            break
                e2 = A2["open"][tr["i"]] + spec["tick"] * tr["side"]
                dist2 = max(tr["pct"] * e2, min_dist(spec, e2))
                rs.append(run_trade(A2, tr["i"], tr["side"], dist2, spec)[0])
            out[v][t] = np.mean(rs) if rs else np.nan
    return out


def perm_p(real, draws):
    """share of shuffles at or above the real mean, with the +1 correction"""
    return float((1 + np.sum(draws >= real)) / (1 + len(draws)))


def flag_perm_p(trades, ndraw=5000, seed=11):
    """kept (EMA up) minus dropped mean R, flags permuted across the control's trades. Returns (diff, p one-sided)."""
    R = np.array([t["R"] for t in trades]); up = np.array([t["up"] for t in trades], bool)
    if up.sum() == 0 or (~up).sum() == 0:
        return None, None
    obs = R[up].mean() - R[~up].mean()
    rng = np.random.default_rng(seed)
    ge = 0
    for _ in range(ndraw):
        f = rng.permutation(up)
        ge += (R[f].mean() - R[~f].mean()) >= obs
    return float(obs), float((1 + ge) / (1 + ndraw))
