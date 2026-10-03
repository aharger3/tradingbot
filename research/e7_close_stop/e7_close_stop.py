"""E7 (OMEN canon): close-stop vs wick-stop on NQ futures. Paper research only, not investment advice.

Entries are the frozen mantra setup ("v2 baseline (OR5 D1.0 strong)", cut 10:30, 2R) from v3-t-mnq/mnq.py.
Only the stop rule changes. Fit/explore window 2024-09-26 -> 2026-09-25. Window A is never loaded.
Grid declared before the run (prereg-E7.md): disaster cap in {1.0, 1.25, 1.5} R, 3 variants.
Same-bar rule: stop wins (order inside a bar = disaster stop, close past stop, target).
"""
import glob, hashlib, json, os, sys
import numpy as np, pandas as pd

AR = os.environ.get("OMEN_AGENT_RUNS", r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
for sub in ("v2-signal", "v2-t01-orb-1m", "v3-t-mnq"):
    sys.path.insert(0, os.path.join(AR, sub))
sys.path.insert(0, os.path.join(AR, ".."))
import orb1m  # frozen
import mnq    # frozen

TICK, USD, COMM, RISK, MAXN = mnq.TICK, mnq.USD, mnq.COMM, mnq.RISK, mnq.MAXN
FIT_START, FIT_END = "2024-09-26", "2026-09-25"
CAPS = (1.0, 1.25, 1.5)
SETUP, CUTN = "v2 baseline (OR5 D1.0 strong)", "10:30"
CUT = mnq.CUTS[CUTN]
PERM_SEED, PERM_N, SHUF_N = 20261003, 20000, 1000


def frozen_shas():
    out = {}
    for name, p in (("mnq.py", os.path.join(AR, "v3-t-mnq", "mnq.py")), ("orb1m.py", os.path.join(AR, "v2-t01-orb-1m", "orb1m.py"))):
        out[name] = hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    return out


def load_fit(start=FIT_START, end=FIT_END):
    """Real NQ 1-min RTH days inside [start, end]. Rows outside are dropped right after reading."""
    parts = []
    for f in sorted(glob.glob(os.path.join(AR, "t01-orb5", "fut", "NQ*.csv"))):
        d = pd.read_csv(f)
        if d.empty:
            continue
        d.columns = [c.lower() for c in d.columns]
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
        ds = d["ts"].dt.strftime("%Y-%m-%d")
        d = d[(ds >= start) & (ds <= end)].copy()
        if d.empty:
            continue
        d["k"] = os.path.basename(f).split("_")[0]
        parts.append(d[["ts", "open", "high", "low", "close", "volume", "k"]])
    df = pd.concat(parts).set_index("ts").sort_index()
    t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy()
    rth["date"] = rth.index.strftime("%Y-%m-%d")
    front = rth.groupby(["date", "k"])["volume"].sum().reset_index().sort_values("volume").groupby("date").last()["k"]
    days = []
    for D, k in front.items():
        if D in mnq.HOL:
            continue
        A = mnq.arr91(rth[(rth.date == D) & (rth.k == k)])
        if np.isnan(A["open"][:5]).all():
            continue
        A["date"] = D
        days.append(A)
    assert days[0]["date"] >= start and days[-1]["date"] <= end
    return days


def find_entries(days):
    dk, trig, tol, jm = mnq.SETUPS[SETUP]
    out = []
    for k, A in enumerate(days):
        s = mnq.signal(A, CUT, dk, trig, tol, jm)
        if not s:
            continue
        i, side, stop, j = s
        fill = A["open"][i] + TICK * side
        dist = (fill - stop) * side
        if dist < 2 * TICK:
            continue
        out.append(dict(date=A["date"], k=k, i=i, side=side, dist=dist, j=j))
    return out


def simulate(A, side, i, dist, mode, cap=1.25, cut=CUT):
    """Exit price and reason. mode: wick | close | close_next | wide (post-hoc control). Stop wins inside a bar."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    d = side
    fill = O[i] + TICK * d
    stop, tgt, dstop = fill - d * dist, fill + d * 2 * dist, fill - d * cap * dist
    for j in range(i, cut):
        if np.isnan(O[j]):
            continue
        if mode in ("wick", "wide"):
            lvl = stop if mode == "wick" else dstop  # wide = plain hard stop at cap R (post-hoc control, no close rule)
            if (L[j] <= lvl) if d > 0 else (H[j] >= lvl):
                return ((min(lvl, O[j]) - TICK) if d > 0 else (max(lvl, O[j]) + TICK)), "stop"
        else:
            if (L[j] <= dstop) if d > 0 else (H[j] >= dstop):
                return ((min(dstop, O[j]) - TICK) if d > 0 else (max(dstop, O[j]) + TICK)), "disaster"
            if (C[j] <= stop) if d > 0 else (C[j] >= stop):
                if mode == "close_next" and j + 1 < cut and not np.isnan(O[j + 1]):
                    return O[j + 1] - TICK * d, "close_stop"
                return C[j] - TICK * d, "close_stop"
        if (H[j] >= tgt + TICK) if d > 0 else (L[j] <= tgt - TICK):
            return tgt, "target"
    if cut < 91 and not np.isnan(O[cut]):
        px = O[cut]
    else:
        v = C[:cut][~np.isnan(C[:cut])]
        px = v[-1]
    return px - TICK * d, "flat"


def to_R(A, side, i, dist, px):
    """Same sizing and cost as mnq.trade()."""
    fill = A["open"][i] + TICK * side
    n = min(MAXN, int(RISK // (dist * USD + COMM)))
    if n == 0:
        n = 1
    usd = (px - fill) * side * n * USD - n * COMM
    return usd / (n * dist * USD)


def run_variant(days, entries, mode, cap):
    rows = []
    for e in entries:
        A = days[e["k"]]
        px, why = simulate(A, e["side"], e["i"], e["dist"], mode, cap)
        rows.append(dict(date=e["date"], R=to_R(A, e["side"], e["i"], e["dist"], px), why=why))
    return rows


def halves(dates_all, trade_dates):
    mid = dates_all[len(dates_all) // 2]
    return np.array([d < mid for d in trade_dates])


def top5_share(R):
    R = np.asarray(R, float)
    tot = R.sum()
    return float(np.sort(R)[::-1][:5].sum() / tot) if tot > 0 else None


def paired_perm(diff, n=PERM_N, seed=PERM_SEED):
    """One-sided sign-flip permutation p for mean(diff) > 0. One trade per day, so trade = day."""
    diff = np.asarray(diff, float)
    obs = diff.mean()
    if not np.any(diff):
        return 1.0
    rng = np.random.default_rng(seed)
    flips = rng.choice([-1.0, 1.0], size=(n, len(diff)))
    return float(((flips * diff).mean(axis=1) >= obs - 1e-12).mean())


def shuffle_means(days, entries, mode, cap, n=SHUF_N, seed=7):
    """mnq.py style: same trade shape on a random other day, n times. Same seed -> same days for every variant."""
    rng = np.random.default_rng(seed)
    sh = []
    for _ in range(n):
        rr = []
        for e in entries:
            while True:
                k = int(rng.integers(len(days)))
                if k != e["k"] and not np.isnan(days[k]["open"][e["i"]]):
                    break
            A = days[k]
            px, _ = simulate(A, e["side"], e["i"], e["dist"], mode, cap)
            rr.append(to_R(A, e["side"], e["i"], e["dist"], px))
        sh.append(np.mean(rr))
    return np.array(sh)


def summarize(R, dates, all_dates):
    R = np.asarray(R)
    h1 = halves(all_dates, dates)
    return dict(n=int(len(R)), R=float(R.mean()), win=float((R > 0).mean()),
                h1=float(R[h1].mean()), h2=float(R[~h1].mean()), n1=int(h1.sum()), n2=int((~h1).sum()),
                top5=top5_share(R))


def main(out_dir):
    days = load_fit()
    all_dates = [A["date"] for A in days]
    entries = find_entries(days)
    dates = [e["date"] for e in entries]
    print("fit days", len(days), all_dates[0], all_dates[-1], "entries", len(entries), flush=True)
    wick = run_variant(days, entries, "wick", 1.25)
    Rw = np.array([r["R"] for r in wick])
    res = dict(shas=frozen_shas(), fit=[all_dates[0], all_dates[-1]], n_days=len(days),
               wick=summarize(Rw, dates, all_dates), variants={})
    h1 = halves(all_dates, dates)
    shw = shuffle_means(days, entries, "wick", 1.25)
    res["wick"]["shuffle_p"] = float((shw >= Rw.mean()).mean())
    res["wick"]["why"] = pd.Series([r["why"] for r in wick]).value_counts().to_dict()
    cases = [(f"close cap {c}R", "close", c, True) for c in CAPS] + [("SENS close cap 1.25R next-open fill", "close_next", 1.25, False),
        ("POSTHOC plain hard stop at 1.25R", "wide", 1.25, False), ("POSTHOC plain hard stop at 1.5R", "wide", 1.5, False)]
    trade_rows = []
    wick_stopped = np.array([w["why"] == "stop" for w in wick])
    for name, mode, cap, selectable in cases:
        rows = run_variant(days, entries, mode, cap)
        Rc = np.array([r["R"] for r in rows])
        diff = Rc - Rw
        s = summarize(Rc, dates, all_dates)
        sh = shuffle_means(days, entries, mode, cap)
        sv, co = diff > 1e-9, diff < -1e-9
        surv = wick_stopped & np.array([r["why"] not in ("close_stop", "disaster") for r in rows])
        boot = np.random.default_rng(5).choice(diff, (5000, len(diff))).mean(axis=1)
        s.update(selectable=selectable, mode=mode, cap=cap, dR=float(diff.mean()), dR_h1=float(diff[h1].mean()), dR_h2=float(diff[~h1].mean()),
                 paired_p=paired_perm(diff), shuffle_p=float((sh >= Rc.mean()).mean()),
                 saves=int(sv.sum()), costs=int(co.sum()), same=int((~sv & ~co).sum()),
                 save_sumR=float(diff[sv].sum()), cost_sumR=float(diff[co].sum()),
                 wick_stopped=int(wick_stopped.sum()), wick_stopped_survived=int(surv.sum()),
                 surv_mean_R_close=float(Rc[surv].mean()) if surv.any() else None,
                 surv_mean_R_wick=float(Rw[surv].mean()) if surv.any() else None,
                 surv_ends=pd.Series([r["why"] for r, m in zip(rows, surv) if m]).value_counts().to_dict(),
                 why=pd.Series([r["why"] for r in rows]).value_counts().to_dict(),
                 ci=[float(x) for x in np.percentile(boot, [2.5, 97.5])])
        res["variants"][name] = s
        for e, w, r in zip(entries, wick, rows):
            trade_rows.append(dict(variant=name, date=e["date"], side=e["side"], dist=e["dist"], R_wick=w["R"], R_var=r["R"], why_wick=w["why"], why_var=r["why"]))
        print(name, json.dumps(s), flush=True)
    sel = [(n, v) for n, v in res["variants"].items() if v["selectable"]]
    res["selected"] = sorted(sel, key=lambda x: (-round(x[1]["R"], 10), x[1]["cap"]))[0][0]
    os.makedirs(out_dir, exist_ok=True)
    json.dump(res, open(os.path.join(out_dir, "e7-variants.json"), "w"), indent=1, default=float)
    pd.DataFrame(trade_rows).to_csv(os.path.join(out_dir, "e7-trades.csv"), index=False)
    print("WICK", json.dumps(res["wick"]), "\nSELECTED", res["selected"], flush=True)
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "e7-out")
