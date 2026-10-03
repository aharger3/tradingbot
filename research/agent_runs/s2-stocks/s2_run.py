"""S2 main run: his S (and A/C) vs time-matched engine candidates on the same tickers, fit window.
Usage: python s2_run.py OUTDIR CANDS_PICKLE      (pickle from build_cands.py)   -> OUTDIR/results.json
Paper research, not investment advice, no orders."""
import os, sys, json, pickle, collections as C
import numpy as np
import s2_lib as L

SEED, NPERM, NBOOT, WIN = 20261003, 10000, 5000, 5     # +-5 min time match
rng = np.random.default_rng(SEED)


def marked_filter(cands, srows_all):
    """drop every candidate he marked (lab S/A/B/C/none), and anything within 3 min, same sym-day and side, of an s_trades row."""
    near = C.defaultdict(list)
    for x in srows_all:
        near[(x["sym"], x["day"])].append((x["m"], x["side"]))
    keep = []
    for x in cands:
        if x["r"] is None or x["lab"] in ("S", "A", "B", "C", "none"):
            continue
        if any(abs(x["m"] - m) <= 3 and s == x["side"] for m, s in near.get((x["sym"], x["day"]), [])):
            continue
        keep.append(x)
    return keep


def build_index(pool):
    """by (sym, day) -> (minutes, R); by sym -> (minutes, R, days)."""
    d = C.defaultdict(lambda: ([], []))
    t = C.defaultdict(lambda: ([], [], []))
    for x in pool:
        d[(x["sym"], x["day"])][0].append(x["m"]); d[(x["sym"], x["day"])][1].append(x["r"])
        t[x["sym"]][0].append(x["m"]); t[x["sym"]][1].append(x["r"]); t[x["sym"]][2].append(x["day"])
    return ({k: (np.array(a), np.array(b)) for k, (a, b) in d.items()},
            {k: (np.array(a), np.array(b), np.array(c)) for k, (a, b, c) in t.items()})


def slot_null(slots, bysym):
    """per slot: matched null = pool candidates, same sym, |dm|<=WIN, any OTHER day -> (mean R, win rate, count)."""
    mu, wn, cnt = [], [], []
    for s in slots:
        e = bysym.get(s["sym"])
        if e is None:
            mu.append(np.nan); wn.append(np.nan); cnt.append(0); continue
        ok = (np.abs(e[0] - s["m"]) <= WIN) & (e[2] != s["day"])
        mu.append(e[1][ok].mean() if ok.any() else np.nan)
        wn.append((e[1][ok] > 0).mean() if ok.any() else np.nan)
        cnt.append(int(ok.sum()))
    return np.array(mu), np.array(wn), np.array(cnt)


def day_perm(slots, idx, universe, n=NPERM):
    """day-level permutation: each S day is replaced by a random other day (drawn without replacement from the universe
    of days); each of its slots by one random pool candidate on that pseudo-day, same sym, |dm|<=WIN (skipped if none).
    -> mean R per permutation, fill rate."""
    sdays = sorted({s["day"] for s in slots})
    by = C.defaultdict(list)
    for s in slots:
        by[s["day"]].append(s)
    out, fills = np.empty(n), np.empty(n)
    for p in range(n):
        pick = rng.choice(len(universe), size=len(sdays), replace=False)
        tot, k = 0.0, 0
        for sd, ui in zip(sdays, pick):
            for s in by[sd]:
                e = idx.get((s["sym"], universe[ui]))
                if e is None:
                    continue
                ok = np.flatnonzero(np.abs(e[0] - s["m"]) <= WIN)
                if ok.size:
                    tot += e[1][ok[rng.integers(ok.size)]]; k += 1
        out[p] = tot / k if k else np.nan
        fills[p] = k / len(slots)
    return out, fills


def slot_draw_perm(slots, bysym, n=NPERM):
    """each S slot replaced by one random pool candidate (same sym, |dm|<=WIN, other day), independently. 127 S trades sit on
    ~109 days so day clustering is small; the day bootstrap CI covers it. Returns mean R per draw."""
    pools = []
    for s in slots:
        e = bysym.get(s["sym"])
        if e is None:
            continue
        ok = (np.abs(e[0] - s["m"]) <= WIN) & (e[2] != s["day"])
        if ok.any():
            pools.append(e[1][ok])
    return np.array([np.mean([p[rng.integers(len(p))] for p in pools]) for _ in range(n)])


def stats(rs, days, mid):
    rs = np.asarray(rs, float); days = np.asarray(days)
    ds = C.defaultdict(float)
    for r, d in zip(rs, days):
        ds[d] += r
    topd = sorted(ds, key=lambda d: -ds[d])[:5]
    tot = rs.sum()
    h1 = days < mid
    rest = [r for r, d in zip(rs, days) if d not in topd]
    return dict(n=int(len(rs)), mean_R=float(rs.mean()), win=float((rs > 0).mean()), n_days=len(ds),
                h1_n=int(h1.sum()), h1_meanR=float(rs[h1].mean()) if h1.any() else None,
                h2_n=int((~h1).sum()), h2_meanR=float(rs[~h1].mean()) if (~h1).any() else None,
                top5_day_share=float(sum(ds[d] for d in topd) / tot) if tot > 0 else None,
                meanR_ex_top5_days=float(np.mean(rest)) if rest else None)


def boot_ci(vals, days, nb=NBOOT):
    vals = np.asarray(vals, float); days = np.asarray(days)
    ud = np.unique(days); g = {d: vals[days == d] for d in ud}
    m = np.empty(nb)
    for b in range(nb):
        m[b] = np.concatenate([g[d] for d in ud[rng.integers(len(ud), size=len(ud))]]).mean()
    return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def main(outdir, pkl):
    cands = pickle.load(open(pkl, "rb"))
    S_all = [x for x in L.run_sim(L.load_s_rows()) if x["r"] is not None]
    pool_all = marked_filter(cands, S_all)
    pool_jd = [x for x in pool_all if x["lab"] == "unmarked_judged"]
    res = dict(meta=dict(seed=SEED, nperm=NPERM, window_min=WIN, fit=[L.FIT0, L.FIT1], n_candidates_total=len(cands),
                         n_candidates_simmed=sum(x["r"] is not None for x in cands),
                         n_pool_all=len(pool_all), n_pool_judged_days=len(pool_jd)))
    out = {}
    for pname, pool in (("all_days", pool_all), ("judged_days", pool_jd)):
        r = np.array([x["r"] for x in pool])
        out["pool_" + pname] = dict(n=len(r), mean_R=float(r.mean()), win=float((r > 0).mean()))
    for g in ("S", "A", "C"):
        slots = [x for x in S_all if x["g"] == g]
        days = np.array([x["day"] for x in slots]); mid = sorted(days)[len(days) // 2]
        rs = np.array([x["r"] for x in slots])
        o = dict(stats=stats(rs, days, mid), split_date=mid)
        for pname, pool in (("all_days", pool_all), ("judged_days", pool_jd)):
            idx, bysym = build_index(pool)
            mu, wn, cnt = slot_null(slots, bysym)
            okm = ~np.isnan(mu)
            exc = rs[okm] - mu[okm]
            h1 = days[okm] < mid
            universe = sorted({d for (_, d) in idx})
            perm, fills = day_perm(slots, idx, universe)
            obs = float(rs.mean())
            sd = slot_draw_perm(slots, bysym)
            p_slot = float((1 + np.sum(sd >= obs)) / (1 + len(sd)))
            p = float((1 + np.nansum(perm >= obs)) / (1 + np.sum(~np.isnan(perm))))
            o[pname] = dict(slots_with_null=int(okm.sum()), null_mean_R=float(mu[okm].mean()), null_win=float(np.nanmean(wn)),
                            median_null_cands_per_slot=float(np.median(cnt)),
                            S_meanR_on_those_slots=float(rs[okm].mean()),
                            excess_R=float(exc.mean()), excess_ci95_day_boot=boot_ci(exc, days[okm]),
                            excess_h1=float(exc[h1].mean()), excess_h2=float(exc[~h1].mean()),
                            perm_null_mean=float(np.nanmean(perm)), perm_null_sd=float(np.nanstd(perm)),
                            perm_fill_rate=float(fills.mean()), day_perm_p_one_sided=p, slot_draw_p_one_sided=p_slot, slot_draw_null_sd=float(sd.std()), n_days_universe=len(universe))
        out[g] = o
    sS = [x for x in S_all if x["g"] == "S"]; sA = [x for x in S_all if x["g"] == "A"]
    out["S_minus_A_R"] = float(np.mean([x["r"] for x in sS]) - np.mean([x["r"] for x in sA]))
    out["S_by_side"] = {"long": [int(sum(1 for x in sS if x["side"] > 0)), float(np.mean([x["r"] for x in sS if x["side"] > 0]))],
                        "short": [int(sum(1 for x in sS if x["side"] < 0)), float(np.mean([x["r"] for x in sS if x["side"] < 0]))]}
    L.MIN_RISK_FRAC = 0.0                      # sensitivity: S rows with the tight-stop floor switched off (candidates cannot: R explodes)
    nf = [x for x in L.run_sim(L.load_s_rows()) if x["g"] == "S" and x["r"] is not None]
    L.MIN_RISK_FRAC = 0.0005
    out["S_no_floor"] = dict(n=len(nf), meanR=float(np.mean([x["r"] for x in nf])), median_R=float(np.median([x["r"] for x in nf])))
    out["S_how"] = dict(C.Counter(x["how"] for x in sS))
    out["S_top_syms"] = dict(C.Counter(x["sym"] for x in sS).most_common(8))
    out["S_meanR_ci95_day_boot"] = boot_ci([x["r"] for x in sS], [x["day"] for x in sS])
    out["S_sd_R"] = float(np.std([x["r"] for x in sS], ddof=1))
    res["results"] = out
    os.makedirs(outdir, exist_ok=True)
    json.dump(res, open(os.path.join(outdir, "results.json"), "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
