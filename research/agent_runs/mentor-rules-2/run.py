"""Run the declared cells (declared.json) on the fit window. usage: python run.py C D E   (any subset)"""
import hashlib, itertools, json, os, pickle, sys, time
import numpy as np
import mentor2 as m

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "mentor-rules"))
NDRAW = 2000
D_SYMS = ["TSLA", "QQQ", "AMD", "NVDA", "MU", "SPY"]
E_SYMS = ["SPY", "QQQ", "NVDA", "AAPL", "MU", "MSFT", "AMZN", "AMD", "TSLA", "GOOGL", "AVGO", "INTC", "HOOD"]   # GOOG (20 files) and TSM (305) dropped: archive too sparse
CACHE = os.environ.get("MR2_CACHE", os.path.join(HERE, "_cache.pkl"))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load_stocks(syms):
    cache = pickle.load(open(CACHE, "rb")) if os.path.exists(CACHE) else {}
    for s in syms:
        if s not in cache:
            t0 = time.time()
            cache[s] = m.load_stock(s)
            print("  loaded", s, len(cache[s][0]), "sessions", cache[s][1], round(time.time() - t0), "s", flush=True)
    pickle.dump(cache, open(CACHE, "wb"))
    return {s: cache[s] for s in syms}


def run_cell(name, days, sessions, spec, variants, eligible, split, extra=None):
    """variants: {vname: sigfn}. Returns the result dict and the trade rows."""
    t0 = time.time()
    trades, summ = {}, {}
    for v, fn in variants.items():
        tr, sk = m.build_trades(days, fn, spec)
        trades[v] = tr
        summ[v] = m.summarize(tr, split, sk)
        print(f"  {name}/{v}: n={summ[v]['n']} meanR={summ[v]['meanR']} (skip {sk})", flush=True)
    ok = [v for v in eligible if summ[v]["n"] >= 30]
    primary = max(ok, key=lambda v: (summ[v]["meanR"], summ[v]["n"])) if ok else None
    sh = m.shuffle_means({v: t for v, t in trades.items() if t}, sessions, spec, ndraw=NDRAW, seed=7)
    for v in variants:
        summ[v]["shuffle_p"] = m.perm_p(summ[v]["meanR"], sh[v]) if v in sh else None
        summ[v]["shuffle_mean_R"] = float(np.mean(sh[v])) if v in sh else None
        summ[v]["clears_std_bar"] = m.clears_std(summ[v], summ[v]["shuffle_p"])
    fw = None
    if primary:
        mx = np.max(np.vstack([sh[v] for v in ok]), axis=0)
        fw = m.perm_p(summ[primary]["meanR"], mx)
    res = dict(cell=name, spec=spec["name"], sessions=len(sorted({d for s in sessions for d in sessions[s]})),
               split=split, variants=summ, eligible=eligible, primary=primary,
               primary_clears_std_bar=bool(primary and summ[primary]["clears_std_bar"]),
               family_wise_p_primary=fw, ndraw=NDRAW, seconds=round(time.time() - t0))
    if extra:
        res.update(extra(trades, summ, primary))
    rows = [dict(variant=v, **t) for v, ts in trades.items() for t in ts]
    return res, rows


def write(name, res, rows):
    json.dump(res, open(os.path.join(HERE, f"result_{name}.json"), "w"), indent=1)
    if rows:
        import csv
        with open(os.path.join(HERE, f"trades_{name}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)


def cell_C():
    days = m.load_nq()
    print("C: NQ sessions", len(days), days[0]["date"], days[-1]["date"], flush=True)
    m.guard_nq([a["date"] for a in days])
    split = days[len(days) // 2]["date"]
    grid = list(itertools.product([4, 20], ["candle", "push5"]))
    variants = {f"tol{t}_{s}": (lambda A, t=t, s=s: m.signal_rejection(A, t, s)) for t, s in grid}

    def extra(trades, summ, primary):
        out = {}
        try:
            import mentor_cells as r1
            if primary:
                bfire = set()
                for A in days:
                    sg = r1.signal_sweep_reclaim(A)
                    if sg:
                        bfire.add((A["date"], int(sg[1])))
                pt = trades[primary]
                out["overlap_with_cell_B_sweep"] = dict(
                    primary_trades=len(pt), same_day_side_as_B=sum((t["date"], t["side"]) in bfire for t in pt),
                    B_fires_on_these_sessions=len(bfire))
        except Exception as e:                      # descriptive only
            out["overlap_with_cell_B_sweep"] = f"not computed: {e}"
        return out
    res, rows = run_cell("C_rejection", days, {"NQ": {a["date"]: a for a in days}}, m.SPEC_NQ, variants,
                         list(variants), split, extra)
    res["first_last"] = [days[0]["date"], days[-1]["date"]]
    write("C", res, rows)


def cell_D(stocks):
    days = [A for s in D_SYMS for A in stocks[s][0]]
    sessions = {s: {A["date"]: A for A in stocks[s][0]} for s in D_SYMS}
    dates = sorted({d for s in sessions for d in sessions[s]})
    print("D: symbol-days", len(days), dates[0], dates[-1], flush=True)
    split = dates[len(dates) // 2]
    grid = list(itertools.product([0.001, 0.0025], ["extreme", "body"]))
    variants = {f"tol{t}_{c}": (lambda A, t=t, c=c: m.signal_three_bar(A, t, c)) for t, c in grid}
    res, rows = run_cell("D_three_bar", days, sessions, m.SPEC_STK, variants, list(variants), split)
    res["symbols"] = D_SYMS; res["first_last"] = [dates[0], dates[-1]]
    write("D", res, rows)


def cell_E(stocks):
    days = [A for s in E_SYMS for A in stocks[s][0]]
    sessions = {s: {A["date"]: A for A in stocks[s][0]} for s in E_SYMS}
    dates = sorted({d for s in sessions for d in sessions[s]})
    print("E: symbol-days", len(days), dates[0], dates[-1], flush=True)
    split = dates[len(dates) // 2]
    variants, eligible = {}, []
    for tf, st, ef in itertools.product([1, 5], ["candle", "level"], [True, False]):
        v = f"tf{tf}_{st}_{'ema' if ef else 'all'}"
        variants[v] = (lambda A, tf=tf, st=st, ef=ef: m.signal_pdh_retest(A, tf, st, ef))
        if ef:
            eligible.append(v)

    def extra(trades, summ, primary):
        paired = {}
        for tf, st in itertools.product([1, 5], ["candle", "level"]):
            d, p = m.flag_perm_p(trades[f"tf{tf}_{st}_all"])
            ups = [t for t in trades[f"tf{tf}_{st}_all"] if t["up"]]
            dn = [t for t in trades[f"tf{tf}_{st}_all"] if not t["up"]]
            paired[f"tf{tf}_{st}"] = dict(kept_minus_dropped_R=d, p_one_sided=p, kept_n=len(ups), dropped_n=len(dn),
                                          kept_R=float(np.mean([t["R"] for t in ups])) if ups else None,
                                          dropped_R=float(np.mean([t["R"] for t in dn])) if dn else None)
        return dict(ema_filter_paired=paired)
    res, rows = run_cell("E_ema_pdh", days, sessions, m.SPEC_STK, variants, eligible, split, extra)
    res["symbols"] = E_SYMS; res["first_last"] = [dates[0], dates[-1]]
    res["share_of_symbol_days_ema_up"] = float(np.mean([A["up"] for A in days]))
    write("E", res, rows)


if __name__ == "__main__":
    which = sys.argv[1:] or ["C", "D", "E"]
    meta = dict(mentor2_sha256=sha(os.path.join(HERE, "mentor2.py")), declared_sha256=sha(os.path.join(HERE, "declared.json")),
                run_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    print(meta, flush=True)
    if "C" in which:
        cell_C()
    if "D" in which or "E" in which:
        stocks = load_stocks(sorted(set(D_SYMS) | set(E_SYMS)))
        if "D" in which:
            cell_D(stocks)
        if "E" in which:
            cell_E(stocks)
    json.dump(meta, open(os.path.join(HERE, "run_meta.json"), "w"), indent=1)
