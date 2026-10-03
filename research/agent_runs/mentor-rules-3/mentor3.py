"""mentor-rules round 3: the two mamba rules (N1 ES/NQ divergence, N2 opening-print) from the night-1003 corpus.
Paper research only. Not investment advice. No orders.

FIT WINDOW ONLY: 2024-09-26 -> 2026-09-25. Window A (real NQ 2019-09-26 -> 2024-09-25) is never loaded: rows dated on
or before 2024-09-25 are dropped as each file is read, and every loaded session is asserted. ES is held to the same rule.

N1  SMT divergence, ES vs NQ, at a key level   (mamba TMybdhN1azw, tMj4_K2eay0, w_Zn6QCkEB0)
N2  Opening-print rejection / reclaim          (mamba TMybdhN1azw, tMj4_K2eay0)

The grid, the primary-variant rule, the std bar, costs and the permutation are in declared.json, committed BEFORE any
variant was evaluated on real data. Fills reuse the round-2 harness (mentor2.py): entry next open + 1 tick adverse,
stop one tick worse than the stop (or the open if it gapped through), 2R target needing 1 tick through, SAME BAR =
STOP WINS, flat at the 11:00 open one tick worse, one trade per day.
"""
import glob, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "mentor-rules-2"))
import mentor2 as m                                           # noqa: E402  (harness: fills, stats, permutation)

SPEC_NQ = m.SPEC_NQ                                           # NQ sized as MNQ: tick 0.25, $2/pt, $1.24 round trip
SPEC_ES = dict(name="ES (sized as MES)", tick=0.25, pv=5.0, comm=1.24)   # MES $5/pt; same $1.24 round trip is an assumption

_orig_min_dist = m.min_dist


def min_dist(spec, e):
    """minimum stop distance. ES like NQ: 2 ticks. (mentor2's version would give ES the stock rule.)"""
    if spec is SPEC_ES:
        return 2 * spec["tick"]
    return _orig_min_dist(spec, e)


m.min_dist = min_dist                                         # build_trades / shuffle_means look it up at call time

LAST_SIG = m.last_bar(1)                                      # 60: signal bar closes by 10:30, entry minute index <= 61
SWEEP_WINDOW = 15                                             # N1: reclaim within 15 one-minute bars of the first sweep
SWING_BARS = 10                                               # swing stop = extreme of the last 10 bars incl. the signal bar
TOL_PCT, DIP_PCT, NEAR_PCT = 0.00005, 0.0005, 0.00125         # N2 distances as a share of the opening print


# ----------------------------------------------------------------------------------------------- loader
def load_fut(prefix, fut=m.FUT, start=m.FIT_START, end=m.FIT_END):
    """Real 1-min futures (prefix 'NQ' or 'ES'), front contract by RTH volume, fit window only. Each day dict has the
    09:30-11:00 bars (arr91), prior-session RTH high/low/close and the overnight high/low (prior session 16:00 ET to
    today 09:29 ET, same contract). A prior-session level exists only when the prior session is the previous NYSE
    session on the same contract (this removes roll days). Returns the list of days with pdh known."""
    parts = []
    for f in sorted(glob.glob(os.path.join(fut, prefix + "*.csv"))):
        d = pd.read_csv(f)
        if d.empty:
            continue
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
        dd = d["ts"].dt.strftime("%Y-%m-%d")
        d = d[(dd >= start) & (dd <= end)]                      # reserved rows are gone before anything else happens
        if d.empty:
            continue
        d["k"] = os.path.basename(f).split("_")[0]
        parts.append(d[["ts", "ts_ns", "open", "high", "low", "close", "volume", "k"]])
    df = pd.concat(parts).set_index("ts").sort_index()
    t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy()
    rth["date"] = rth.index.strftime("%Y-%m-%d")
    assert rth["date"].min() > m.RESERVED_END
    front = rth.groupby(["date", "k"])["volume"].sum().reset_index().sort_values("volume").groupby("date").last()["k"]
    by_k = {k: (g["ts_ns"].to_numpy(), g["high"].to_numpy(), g["low"].to_numpy()) for k, g in df.groupby("k")}
    days, prev = [], None
    for D, k in front.items():
        if D in m.NYSE_HOL:
            continue
        g = rth[(rth.date == D) & (rth.k == k)]
        if len(g) < 200:
            continue
        mins = (g.index.hour * 60 + g.index.minute).to_numpy()
        A = m.arr91(mins, g.open, g.high, g.low, g.close)
        if np.isnan(A["open"][:5]).any():
            continue
        pd_ok = prev is not None and prev[3] == k and prev[4] == m.PREV_OF.get(D)
        A["pdh"], A["pdl"], A["pdc"] = (prev[0], prev[1], prev[2]) if pd_ok else (np.nan, np.nan, np.nan)
        A["onh"] = A["onl"] = np.nan
        if pd_ok:
            ns, hi, lo = by_k[k]
            a = pd.Timestamp(prev[4] + " 16:00", tz="America/New_York").value
            b = pd.Timestamp(D + " 09:30", tz="America/New_York").value
            i0, i1 = np.searchsorted(ns, a, "left"), np.searchsorted(ns, b, "left")
            if i1 - i0 >= 30:
                A["onh"], A["onl"] = float(hi[i0:i1].max()), float(lo[i0:i1].min())
        A["date"], A["sym"] = D, prefix
        prev = (g.high.max(), g.low.min(), g.close.iloc[-1], k, D)
        days.append(A)
    assert all(a["date"] > m.RESERVED_END for a in days), "reserved window A touched"
    return [a for a in days if not np.isnan(a["pdh"])]


def align(nq, es):
    """sessions where NQ and ES both exist with all four levels known. Returns (nq_by_date, es_by_date)."""
    ok = lambda a: not any(np.isnan(a[k]) for k in ("pdh", "pdl", "onh", "onl"))
    n = {a["date"]: a for a in nq if ok(a)}
    e = {a["date"]: a for a in es if ok(a)}
    common = sorted(set(n) & set(e))
    return {d: n[d] for d in common}, {d: e[d] for d in common}


def pair(tr_by_date, ot_by_date):
    """traded-instrument day dicts, each carrying the other instrument's same-date day under key 'x'"""
    out = []
    for d, A in tr_by_date.items():
        B = dict(A)
        B["x"] = ot_by_date[d]
        out.append(B)
    return out


# ----------------------------------------------------------------------------------------------- N1: SMT divergence
LEVEL_KEYS = {"ON": ("onl", "onh"), "PD": ("pdl", "pdh")}


def smt_triggers(T, X, level):
    """All trigger bars (j, side) in 09:30-10:30 for the divergence rule, traded instrument T, other X.
    Bullish: some index has swept its own level L (low < L) since 09:30, the OTHER index has not swept its own level
    (its running low since 09:30 is still >= its L), and the sweeping index has reclaimed: the first sweep was at most
    15 bars ago and this bar closes back above its level and closes green. Bearish mirrors on the highs.
    The sweeping index can be either one. A bar where both sides trigger is a conflict and is returned twice."""
    kl, kh = LEVEL_KEYS[level]
    out = []
    for side in (1, -1):
        key = kl if side > 0 else kh
        ext = "low" if side > 0 else "high"
        run = np.fmin.accumulate if side > 0 else np.fmax.accumulate
        L = {"T": (T, T[key]), "X": (X, X[key])}
        sw, first, run_ext = {}, {}, {}
        for nm, (A, lv) in L.items():
            e = A[ext][:91]
            hit = (e < lv) if side > 0 else (e > lv)
            hit = np.where(np.isnan(e), False, hit)
            first[nm] = int(hit.argmax()) if hit.any() else None
            run_ext[nm] = np.cumsum(hit) > 0                    # swept at or before bar j
        for j in range(0, LAST_SIG + 1):
            if np.isnan(T["open"][j + 1]) or np.isnan(T["close"][j]):
                continue
            s_t, s_x = run_ext["T"][j], run_ext["X"][j]
            if s_t == s_x:                                      # neither or both swept: no divergence
                continue
            nm = "T" if s_t else "X"
            A, lv = L[nm]
            if np.isnan(A["close"][j]) or np.isnan(A["open"][j]):
                continue
            if j - first[nm] > SWEEP_WINDOW:
                continue
            if side > 0:
                ok = A["close"][j] > lv and A["close"][j] > A["open"][j]
            else:
                ok = A["close"][j] < lv and A["close"][j] < A["open"][j]
            if ok:
                out.append((j, side))
    return sorted(out)


def signal_smt(A, level, stop_mode, spec=SPEC_NQ):
    """First trigger of the day -> (entry index, side, stop) on the traded instrument, or None. A bar where both
    sides trigger skips the day. A = traded day dict with the other instrument under 'x'."""
    trig = smt_triggers(A, A["x"], level)
    if not trig:
        return None
    j, side = trig[0]
    if sum(1 for t in trig if t[0] == j) > 1:
        return None
    tick = spec["tick"]
    lo = max(0, j - SWING_BARS + 1)
    if side > 0:
        ext = A["low"][j] if stop_mode == "candle" else np.nanmin(A["low"][lo:j + 1])
        return (j + 1, 1, ext - tick)
    ext = A["high"][j] if stop_mode == "candle" else np.nanmax(A["high"][lo:j + 1])
    return (j + 1, -1, ext + tick)


# ----------------------------------------------------------------------------------------------- N2: opening print
def near_key_level(A):
    OP = A["open"][0]
    lv = [A[k] for k in ("pdh", "pdl", "onh", "onl") if not np.isnan(A[k])]
    return bool(lv) and min(abs(OP - x) for x in lv) <= NEAR_PCT * OP


def signal_op(A, mode, conf, spec=SPEC_NQ):
    """Opening-print rule. OP = the 09:30 bar's open of the traded instrument.
    reject: short when a bar's high reaches OP - tol, the previous close is under OP, and the bar closes under OP and
      red; long mirrors (low reaches OP + tol, previous close over OP, closes over OP and green). tol = 0.005% of OP.
    reclaim: long when a bar closes over OP and green after a previous close at or under it, and the lowest low since
      09:30 was at least 0.05% of OP under OP; short mirrors (close under OP and red after a close at or over it, and
      the highest high since 09:30 at least 0.05% over OP).
    conf='near': only on days when PDH, PDL, ONH or ONL lies within 0.125% of OP. First signal of the day, bars 1..60.
    Stop = extreme of the last 10 bars incl. the signal bar +/- 1 tick. Returns (entry index, side, stop) or None."""
    if conf == "near" and not near_key_level(A):
        return None
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    OP = O[0]
    tick, tol, dip = spec["tick"], TOL_PCT * OP, DIP_PCT * OP
    for j in range(1, LAST_SIG + 1):
        if np.isnan(C[j]) or np.isnan(C[j - 1]) or np.isnan(O[j + 1]) or np.isnan(O[j]):
            continue
        ref = C[j - 1]
        lo = max(0, j - SWING_BARS + 1)
        if mode == "reject":
            if H[j] >= OP - tol and ref < OP and C[j] < OP and C[j] < O[j]:
                return (j + 1, -1, np.nanmax(H[lo:j + 1]) + tick)
            if L[j] <= OP + tol and ref > OP and C[j] > OP and C[j] > O[j]:
                return (j + 1, 1, np.nanmin(L[lo:j + 1]) - tick)
        else:
            if C[j] > OP and C[j] > O[j] and ref <= OP and np.nanmin(L[:j]) <= OP - dip:
                return (j + 1, 1, np.nanmin(L[lo:j + 1]) - tick)
            if C[j] < OP and C[j] < O[j] and ref >= OP and np.nanmax(H[:j]) >= OP + dip:
                return (j + 1, -1, np.nanmax(H[lo:j + 1]) + tick)
    return None


# ----------------------------------------------------------------------------------------------- variants
def n1_variants(spec=SPEC_NQ):
    return {f"smt_{lv}_{st}": (lambda A, lv=lv, st=st: signal_smt(A, lv, st, spec))
            for lv in ("ON", "PD") for st in ("candle", "swing10")}


def n2_variants(spec=SPEC_NQ):
    return {f"op_{md[:3]}_{cf}": (lambda A, md=md, cf=cf: signal_op(A, md, cf, spec))
            for md in ("reject", "reclaim") for cf in ("any", "near")}
