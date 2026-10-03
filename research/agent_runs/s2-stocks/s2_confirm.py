"""S2 forward confirm (arm F). Pre-registered in prereg-S2.md. Paper research, not investment advice, no orders.
Usage: python s2_confirm.py TAPS_CSV CANDS_CSV OUTDIR [--allow-look]
  TAPS_CSV : sym,day,sig_t(HH:MM),side(L|S),stop,label(S|notS),sig_close_ts,tap_ts   (ISO timestamps with tz)
  CANDS_CSV: sym,day,sig_t(HH:MM),side(L|S),stop      (every engine candidate in the forward window, signal 09:35-10:58)
Imports sim, slot_null, slot_draw_perm, day_perm, stats, boot_ci, build_index from s2_run/s2_lib unchanged (WIN=5, SEED=20261003, no fallback).
Refuses to compute excess/p until >=100 simulable S taps (or --allow-look, only after the date rule in prereg-S2.md fires)."""
import os, sys, csv, json, collections as C
from datetime import datetime
import numpy as np
import s2_lib as L
import s2_run as R

MIN_N, EXC_BAR, P_BAR, TOP5_BAR, LATE_S, FILL_BAR = 100, 0.25, 0.05, 0.40, 120, 0.25


def _rows(fp):
    with open(fp, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _cand(r):
    return dict(sym=r["sym"], day=r["day"], m=L.mins(r["sig_t"]), side=1 if r["side"].upper().startswith("L") else -1, stop=float(r["stop"]))


def tap_ok(r):
    """tap counts only if it arrives 0..120 s after the signal bar closes. Returns latency seconds or None."""
    lat = (datetime.fromisoformat(r["tap_ts"]) - datetime.fromisoformat(r["sig_close_ts"])).total_seconds()
    return lat if 0 <= lat <= LATE_S else None


def main(taps_fp, cands_fp, outdir, allow_look=False):
    R.rng = np.random.default_rng(R.SEED)                       # fixed stream for slot_draw_perm / day_perm / boot_ci
    taps = _rows(taps_fp)
    good = [t for t in taps if tap_ok(t) is not None]
    s_taps = [_cand(t) for t in good if t["label"] == "S"]
    for x in L.run_sim(s_taps): pass
    s_taps = [x for x in s_taps if x["r"] is not None]
    res = dict(meta=dict(seed=R.SEED, nperm=R.NPERM, win=R.WIN, taps_total=len(taps), taps_in_time=len(good),
                         response_in_time=len(good) / len(taps) if taps else None, s_taps_simulable=len(s_taps)))
    if len(s_taps) < MIN_N and not allow_look:
        res["status"] = "NOT_YET: %d of %d simulable S taps; no look" % (len(s_taps), MIN_N)
        print(json.dumps(res, indent=1)); return res
    skey = {(x["sym"], x["day"], x["m"], x["side"]) for x in s_taps}
    pool = [x for x in L.run_sim([_cand(r) for r in _rows(cands_fp)]) if x["r"] is not None
            and (x["sym"], x["day"], x["m"], x["side"]) not in skey]
    idx, bysym = R.build_index(pool)
    days = np.array([x["day"] for x in s_taps]); rs = np.array([x["r"] for x in s_taps])
    dates = sorted(days); mid = dates[len(dates) // 2]            # H2 includes the median date
    mu, wn, cnt = R.slot_null(s_taps, bysym)
    ok = ~np.isnan(mu); exc = rs[ok] - mu[ok]; h1 = days[ok] < mid
    ci = R.boot_ci(exc, days[ok])
    sd = R.slot_draw_perm(s_taps, bysym); obs = float(rs.mean())
    p_slot = float((1 + np.sum(sd >= obs)) / (1 + len(sd)))
    universe = sorted({d for (_, d) in idx})
    perm, fills = R.day_perm(s_taps, idx, universe)
    p_day = float((1 + np.nansum(perm >= obs)) / (1 + np.sum(~np.isnan(perm))))
    st = R.stats(rs, days, mid)
    h1e = float(exc[h1].mean()) if h1.any() else None; h2e = float(exc[~h1].mean()) if (~h1).any() else None
    day_counts = fills.mean() >= FILL_BAR
    bar = dict(n_ge_100=len(s_taps) >= MIN_N, excess_ge_025=bool(exc.mean() >= EXC_BAR),
               slot_draw_p_lt_005=p_slot < P_BAR, boot_ci_lower_gt_0=ci[0] > 0,
               both_halves_positive=bool(h1e is not None and h2e is not None and h1e > 0 and h2e > 0),
               top5_le_40=bool(st["top5_day_share"] is not None and st["top5_day_share"] <= TOP5_BAR))
    res["result"] = dict(stats=st, slots_with_null=int(ok.sum()), null_mean_R=float(mu[ok].mean()), excess_R=float(exc.mean()),
                         excess_ci95_day_boot=ci, excess_h1=h1e, excess_h2=h2e, slot_draw_p_one_sided=p_slot,
                         day_perm_p_one_sided_reported_only=p_day, day_perm_fill_rate=float(fills.mean()),
                         day_perm_counts_as_significance=bool(day_counts))
    res["pass_bar"] = bar; res["PASS"] = all(bar.values())
    os.makedirs(outdir, exist_ok=True)
    json.dump(res, open(os.path.join(outdir, "s2_confirm.json"), "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float)); return res


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], allow_look="--allow-look" in sys.argv)
