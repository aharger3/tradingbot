"""burn-robinhood-qqq: the MNQ v2 OR5 10:30 strong signal traded as QQQ SHARES (Robinhood-style). Paper research only.

IS  (2024-09-27 -> QQQ archive end): B1030 list from v3-options-0dte/signals.json (MNQ entries mapped to QQQ, same minute).
    Stop = MNQ stop points x QQQ/NQ ratio of THAT day (median QQQ/NQ close over the 5 OR bars, known before entry),
    vs the fixed /41.32 mapping opt0.py used.
OOS (2024-01-02 -> 2024-09-26): no NQ bars on disk before 2024-09-26, so the SAME orb1m.signal rule is run natively
    on QQQ 1-min (tick $0.01). Also run on IS for an apples-to-apples native column.
Fills: entry next-bar open +1c, stop = min(stop, open) -1c (same bar: stop wins), 2R limit needs 1c through,
flat at 10:30 open -1c. $0 commission. Size = floor($250 / stop), capped at $100K notional (4x of $25K).
"""
import sys, os, json, glob, math
import numpy as np, pandas as pd

MAIN = r"C:\Users\aharg\Desktop\Projects\tradingbot"
AR = os.path.join(MAIN, "research", "agent_runs")
HERE = os.path.dirname(os.path.abspath(__file__))
ARCH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "data_archive")  # worktree's tracked archive
TK = 0.01; CUT = 60; RISK = 250.0; BP = 25_000 * 4; FIXED = 41.32
IS0, MID, OOS0, OOS1 = "2024-09-27", "2025-09-26", "2024-01-02", "2024-09-26"
NSHUF = 1000


def load(d):
    f = os.path.join(ARCH, "QQQ", d + ".csv")
    if not os.path.exists(f): return None
    df = pd.read_csv(f); ts = pd.to_datetime(df["Datetime"].astype(str).str[:19], errors="coerce")
    mm = (ts.dt.hour * 60 + ts.dt.minute - 570).values; ok = (mm >= 0) & (mm < 390)
    A = {}
    for k, c in (("open", "Open"), ("high", "High"), ("low", "Low"), ("close", "Close")):
        a = np.full(391, np.nan); a[mm[ok]] = df[c].values[ok]; A[k] = a
    return A if np.sum(~np.isnan(A["close"][:90])) > 60 else None


def sim(A, side, i, dist, cut=CUT):
    """-> (entry, exit, kind). Honest share fills, stop wins same-bar ties."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    e = O[i] + TK * side; stop = e - side * dist; tgt = e + side * 2 * dist
    for j in range(i, cut):
        if np.isnan(O[j]): continue
        if (L[j] <= stop) if side > 0 else (H[j] >= stop):
            return e, (min(stop, O[j]) if side > 0 else max(stop, O[j])) - TK * side, "stop"
        if (H[j] >= tgt + TK) if side > 0 else (L[j] <= tgt - TK):
            return e, tgt, "tgt"
    px = O[cut] if cut < len(O) and not np.isnan(O[cut]) else C[:cut][~np.isnan(C[:cut])][-1]
    return e, px - TK * side, "flat"


def size(e, dist, risk=RISK, bp=BP):
    return int(min(math.floor(risk / dist), math.floor(bp / e)))


def trade(A, d, side, i, dist):
    if not dist >= 2 * TK: return None
    e, x, kind = sim(A, side, i, dist)
    sh = size(e, dist); pts = (x - e) * side
    return dict(d=d, i=i, side=side, dist=dist, R=pts / dist, usd=sh * pts, sh=sh, bp=sh * e, kind=kind)


def maxdd(u):
    eq = np.cumsum(u); return float(np.max(np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq)) if len(u) else 0.0


def perm_p(T, days, rng):
    """day shuffle: same minute/side/stop replayed on a random other session of the same window."""
    if not T: return None
    act = np.mean([t["R"] for t in T]); sh = []
    for _ in range(NSHUF):
        rr = []
        for t in T:
            while True:
                d2 = days[rng.integers(len(days))]
                if d2 != t["d"] and not np.isnan(DAYS[d2]["open"][t["i"]]): break
            r = trade(DAYS[d2], d2, t["side"], t["i"], t["dist"]); rr.append(r["R"] if r else 0.0)
        sh.append(np.mean(rr))
    return float((np.array(sh) >= act).mean())


def stats(T, days, rng, mid=None):
    R = np.array([t["R"] for t in T]); U = np.array([t["usd"] for t in T]); dd = np.array([t["d"] for t in T])
    mid = mid or (sorted(days)[len(days) // 2])
    h1 = dd < mid
    return dict(n=len(T), R=round(R.mean(), 3), win=round((R > 0).mean(), 3),
                H1=f"{R[h1].mean():+.3f} (n={h1.sum()})", H2=f"{R[~h1].mean():+.3f} (n={(~h1).sum()})",
                usd_day=round(U.sum() / len(days), 1), usd_tot=round(U.sum()), maxdd=round(maxdd(U)),
                maxbp=round(max(t["bp"] for t in T)), capped=int(sum(t["sh"] < math.floor(RISK / t["dist"]) for t in T)),
                p=perm_p(T, days, rng), sessions=len(days))


DAYS = {}


def main():
    sys.path.insert(0, os.path.join(AR, "v2-s07-data")); sys.path.insert(0, os.path.join(AR, "v2-t01-orb-1m"))
    from omen_data import load_fut
    import orb1m
    rng = np.random.default_rng(7)
    for f in sorted(glob.glob(os.path.join(ARCH, "QQQ", "*.csv"))):
        d = os.path.basename(f)[:-4]; A = load(d)
        if A is not None: DAYS[d] = A
    qend = max(DAYS)
    IS = [d for d in DAYS if IS0 <= d <= qend]; OOS = [d for d in DAYS if OOS0 <= d <= OOS1]
    nq = {str(d): orb1m.day_arrays(g) for d, g in load_fut("MNQ", "09:30", "11:01").groupby("date")}
    mnq = {t["date"]: t for t in json.load(open(os.path.join(AR, "v2-t01-orb-1m", "trades_MNQ_OR5_1030_D1_strong.json")))}
    B = [s for s in json.load(open(os.path.join(AR, "v3-options-0dte", "signals.json"))) if s["v"] == "B1030"]
    Td, Tf, Tm, ratios = [], [], [], []
    for s in B:
        d = s["d"]
        if d not in DAYS or d not in nq or d not in mnq: continue
        A = DAYS[d]; N = nq[d]; t = mnq[d]; assert t["i"] == s["i"] and t["side"] == s["side"]
        r = np.nanmedian(A["close"][:5] / N["close"][:5]); ratios.append(r)
        a = trade(A, d, s["side"], s["i"], t["dist"] * r); b = trade(A, d, s["side"], s["i"], t["dist"] / FIXED)
        if a and b:
            Td.append(a); Tf.append(b)
            ct = math.floor(RISK / (t["dist"] * 2.0)); Tm.append(dict(d=d, R=t["R"], usd=ct * t["usd"]))
    # native QQQ rule (the only honest OOS: no NQ bars before 2024-09-26)
    orb1m.TICK = TK
    def native(days):
        T = []
        for d in days:
            A = DAYS[d]; s = orb1m.signal({k: v[:91] for k, v in A.items()}, 5, CUT, 1.0, "strong")
            if s:
                i, side, stop = s; x = trade(A, d, side, i, (A["open"][i] + TK * side - stop) * side)
                if x: T.append(x)
        return T
    To, Tn = native(OOS), native(IS)
    res = {"IS B1030 daily-ratio": stats(Td, IS, rng, MID), "IS B1030 fixed/41.32": stats(Tf, IS, rng, MID),
           "IS QQQ-native": stats(Tn, IS, rng, MID), "OOS QQQ-native": stats(To, OOS, rng)}
    Rm = np.array([t["R"] for t in Tm]); Um = np.array([t["usd"] for t in Tm])
    res["MNQ same dates ($250 risk, $1.24 RT/ct)"] = dict(n=len(Tm), R=round(Rm.mean(), 3), usd_day=round(Um.sum() / len(IS), 1), maxdd=round(maxdd(Um)))
    rd = np.array([t["R"] for t in Td]); rf = np.array([t["R"] for t in Tf])
    res["ratio"] = dict(med=round(float(np.median(1 / np.array(ratios))), 2), lo=round(float(np.min(1 / np.array(ratios))), 2),
                        hi=round(float(np.max(1 / np.array(ratios))), 2), n_B1030=len(B), priced=len(Td),
                        dR_daily_minus_fixed=round(float(rd.mean() - rf.mean()), 4), trades_R_changed=int(np.sum(np.abs(rd - rf) > 1e-6)),
                        outcome_flips=int(sum(a["kind"] != b["kind"] for a, b in zip(Td, Tf))),
                        corr_qqq_mnq=round(float(np.corrcoef(rd, Rm)[0, 1]), 3), same_kind_as_mnq_pct=None,
                        mean_abs_R_gap_vs_mnq=round(float(np.mean(np.abs(rd - Rm))), 3))
    json.dump(dict(res=res, trades_daily=Td, trades_oos=To), open(os.path.join(HERE, "rh.json"), "w"), default=float, indent=1)
    for k, v in res.items(): print(k, json.dumps(v, default=float))


def selftest():
    n = 91; O = np.full(n, 100.0); H = O + 0.05; L = O - 0.05; C = O.copy()
    A = dict(open=O.copy(), high=H.copy(), low=L.copy(), close=C.copy())
    # long, dist 0.50: target 101.02 needs 101.03 print
    A["high"][12] = 101.02; assert sim(A, 1, 10, 0.5)[2] == "flat"
    A["high"][12] = 101.03; e, x, k = sim(A, 1, 10, 0.5); assert (round(e, 2), x, k) == (100.01, 100.01 + 1.0, "tgt"), (e, x, k)
    # same bar touches stop and target -> stop
    B = {k: v.copy() for k, v in A.items()}; B["low"][12] = 99.0; e, x, k = sim(B, 1, 10, 0.5); assert k == "stop" and abs(x - (99.51 - 0.01)) < 1e-9
    # gap through stop fills at open -1c
    G = {k: v.copy() for k, v in A.items()}; G["open"][11] = 99.0; G["low"][11] = 98.9; e, x, k = sim(G, 1, 10, 0.5); assert abs(x - 98.99) < 1e-9
    # short flat at cutoff open +1c
    e, x, k = sim(dict(open=O, high=H, low=L, close=C), -1, 10, 0.5); assert k == "flat" and abs(x - 100.01) < 1e-9
    assert size(500.0, 0.10) == 200 and size(500.0, 2.0) == 125  # notional cap binds at 0.10 stop
    print("TESTS OK")


if __name__ == "__main__":
    selftest() if (len(sys.argv) > 1 and sys.argv[1] == "test") else main()
