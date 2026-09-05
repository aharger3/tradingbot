"""g201 refuter #2 -- multiplicity and sampling error against F9 (g158 MID25).

Lens: how many arms were tried, paired bootstrap over sessions, one-day
dominance, H1-used-to-select-vs-validate. Defaults to REFUTED.

Reproduces g158_mid_candle_arms.py's own pricing path exactly (same book, same
universe, same candidate ordering, same `G.run_trade`, same
`omen_metrics`-style first-of-day arm), then adds four things g158 did not do:

  1. CLOSE_RT  -- the CLOSE control re-priced through the SAME `G.run_trade`
     engine the MID arms use (g158's CLOSE arm reads the book's own recorded
     pnl instead, so its headline compares two different exit replays).
  2. A decomposition of the MID25-minus-CLOSE gap into a SELECTION component
     (the day's pick changes because an unfilled limit is skipped) and a FILL
     component (same candidate, better price).
  3. Paired bootstrap over the 498 sessions on the daily difference, plus
     one-day / top-k dominance and leave-one-day-out.
  4. A matched null family: arms that drop candidates at MID25's own skip rate
     at random and book the CLOSE price, to see what the reshuffle alone pays.

Reads only. No engine file, no mark file, nothing shipped.

    python research/g201_refute2.py
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G   # noqa: E402
import signal_runner as sr                     # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT_JSON = ROOT / "research" / "g201_refute2.json"

RISK = 1000.0
SPLIT_DAY = "2025-09-01"
FRACS = (0.25, 0.50, 0.75)
ARM_NAMES = {0.25: "MID25", 0.50: "MID50", 0.75: "MID75"}
SEED = 20260905
BOOTS = 10000
NULLS = 1000


def half(day):
    return "H1" if day < SPLIT_DAY else "H2"


def resting_price(entry_close, rng, long, frac):
    return entry_close - frac * rng if long else entry_close + frac * rng


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, allrows = book["meta"], book["trades"]
    all_days = sorted({r["day"] for r in allrows})
    n_days = meta["sessions"]
    print("book %s: %d sessions" % (BOOK.name, n_days), flush=True)

    universe = {i: r for i, r in enumerate(allrows)
                if r.get("traded") or r["status"] == "halted"}
    keys = sorted(universe, key=lambda i: (allrows[i]["day"], allrows[i]["et"],
                                           allrows[i]["sym"], i))
    cand_by_day = defaultdict(list)
    for k in keys:
        cand_by_day[allrows[k]["day"]].append(k)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"], i))
    print("  %d candidates over %d days with candidates"
          % (len(keys), len(cand_by_day)), flush=True)

    priced = {f: {} for f in FRACS}
    close_rt = {}
    for n, k in enumerate(keys):
        if n and n % 2000 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r["entry_i"]
        if not bars or i >= len(bars):
            continue
        # CLOSE control through the SAME engine the MID arms use.
        if i < len(bars) - 1:
            res = G.run_trade(r, bars, i, r["entry"], pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is not None:
                close_rt[k] = res
        rng = bars[i].high - bars[i].low
        cutoff = G.cutoff_idx(bars)
        if rng <= 0 or i + 1 >= min(cutoff, len(bars) - 1):
            continue
        long = r["dir"] == "call"
        entry_close = r["entry"]
        for f in FRACS:
            px = resting_price(entry_close, rng, long, f)
            j, fillpx = G.limit_touch(bars, px, long, i + 1, cutoff)
            if j is None or j >= len(bars) - 1:
                continue
            res = G.run_trade(r, bars, j, fillpx, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is not None:
                priced[f][k] = res

    close_rows = {k: universe[k] for k in keys}

    def sizeable(res):
        if "sizeable" in res:
            return res["sizeable"]
        return abs(res["entry"] - res["stop"]) >= sr.min_risk_floor(
            res.get("close", res["entry"]))

    def pick_by_day(rows_by_key):
        """day -> (key, pnl). g158's oneaday_for, but keeping the key."""
        out = {}
        for d in sorted(cand_by_day):
            for k in cand_by_day[d]:
                res = rows_by_key.get(k)
                if res is None:
                    continue
                if sizeable(res):
                    out[d] = (k, res["pnl"])
                    break
        return out

    def daily_vec(picks):
        return [picks.get(d, (None, 0.0))[1] for d in all_days]

    def per_day(vec):
        return sum(vec) / n_days

    picks = {"CLOSE": pick_by_day(close_rows), "CLOSE_RT": pick_by_day(close_rt)}
    for f in FRACS:
        picks[ARM_NAMES[f]] = pick_by_day(priced[f])

    vecs = {a: daily_vec(p) for a, p in picks.items()}
    hdr = {}
    for a in ("CLOSE", "CLOSE_RT", "MID25", "MID50", "MID75"):
        v = vecs[a]
        h1 = [x for x, d in zip(v, all_days) if half(d) == "H1"]
        h2 = [x for x, d in zip(v, all_days) if half(d) == "H2"]
        hdr[a] = {"per_day": round(per_day(v), 1),
                  "H1_per_day": round(sum(h1) / len(h1), 1),
                  "H2_per_day": round(sum(h2) / len(h2), 1),
                  "total": round(sum(v), 0),
                  "days_traded": sum(1 for d in all_days if d in picks[a])}
        print("  %-9s $%6.1f/day  H1 $%6.1f  H2 $%6.1f  (%d days traded)"
              % (a, hdr[a]["per_day"], hdr[a]["H1_per_day"],
                 hdr[a]["H2_per_day"], hdr[a]["days_traded"]), flush=True)

    # ---------------------------------------------------- paired bootstrap
    rng_b = random.Random(SEED)

    def paired_boot(a, b):
        va, vb = vecs[a], vecs[b]
        diff = [x - y for x, y in zip(va, vb)]
        means = sorted(
            sum(diff[i] for i in rng_b.choices(range(n_days), k=n_days)) / n_days
            for _ in range(BOOTS))
        lo, hi = means[int(BOOTS * .025)], means[int(BOOTS * .975)]
        p_le0 = sum(1 for m in means if m <= 0) / BOOTS
        return {"mean_diff_per_day": round(sum(diff) / n_days, 1),
                "ci95": [round(lo, 1), round(hi, 1)],
                "boot_frac_le_zero": round(p_le0, 4)}

    boots = {
        "MID25_vs_CLOSE": paired_boot("MID25", "CLOSE"),
        "MID25_vs_CLOSE_RT": paired_boot("MID25", "CLOSE_RT"),
        "CLOSE_RT_vs_CLOSE": paired_boot("CLOSE_RT", "CLOSE"),
        "MID50_vs_CLOSE_RT": paired_boot("MID50", "CLOSE_RT"),
    }
    for k, v in boots.items():
        print("  boot %-20s %+7.1f/day  CI95 [%+.1f, %+.1f]  P(<=0)=%.3f"
              % (k, v["mean_diff_per_day"], v["ci95"][0], v["ci95"][1],
                 v["boot_frac_le_zero"]), flush=True)

    # ------------------------------------------------------ dominance
    def dominance(a, b):
        diff = [(d, x - y) for d, x, y in zip(all_days, vecs[a], vecs[b])]
        tot = sum(v for _, v in diff)
        s = sorted(diff, key=lambda t: -abs(t[1]))
        top = [(d, round(v, 0)) for d, v in s[:10]]
        share1 = s[0][1] / tot if tot else 0.0
        share5 = sum(v for _, v in s[:5]) / tot if tot else 0.0
        share10 = sum(v for _, v in s[:10]) / tot if tot else 0.0
        best = max(diff, key=lambda t: t[1])
        loo = (tot - best[1]) / (n_days - 1)
        nz = [v for _, v in diff if abs(v) > 1e-9]
        return {"total_gap": round(tot, 0),
                "top10_days": top,
                "top1_share": round(share1, 3),
                "top5_share": round(share5, 3),
                "top10_share": round(share10, 3),
                "days_differing": len(nz),
                "median_gap_on_differing_days": round(
                    statistics.median(nz), 1) if nz else 0.0,
                "drop_best_day_per_day": round(loo, 1),
                "best_day": [best[0], round(best[1], 0)]}

    dom = {"MID25_vs_CLOSE_RT": dominance("MID25", "CLOSE_RT"),
           "MID25_vs_CLOSE": dominance("MID25", "CLOSE")}
    for k, v in dom.items():
        print("  dom %-18s gap $%d  top1 %.1f%%  top5 %.1f%%  differing days %d"
              % (k, v["total_gap"], v["top1_share"] * 100, v["top5_share"] * 100,
                 v["days_differing"]), flush=True)

    # -------------------------------------- selection vs fill decomposition
    sel_rows = {k: close_rt[k] for k in priced[0.25] if k in close_rt}
    sel_picks = pick_by_day(sel_rows)          # MID25 fillability, CLOSE price
    vecs["SELECT_ONLY"] = daily_vec(sel_picks)
    picks["SELECT_ONLY"] = sel_picks

    same = [d for d in all_days
            if d in picks["MID25"] and d in picks["CLOSE_RT"]
            and picks["MID25"][d][0] == picks["CLOSE_RT"][d][0]]
    diff_pick = [d for d in all_days
                 if d in picks["MID25"] and d in picks["CLOSE_RT"]
                 and picks["MID25"][d][0] != picks["CLOSE_RT"][d][0]]
    fill_gap = sum(picks["MID25"][d][1] - picks["CLOSE_RT"][d][1] for d in same)
    selpick_gap = sum(picks["MID25"][d][1] - picks["CLOSE_RT"][d][1]
                      for d in diff_pick)
    only_mid = [d for d in all_days if d in picks["MID25"] and d not in picks["CLOSE_RT"]]
    only_cl = [d for d in all_days if d in picks["CLOSE_RT"] and d not in picks["MID25"]]
    decomp = {
        "same_pick_days": len(same),
        "diff_pick_days": len(diff_pick),
        "mid_only_days": len(only_mid),
        "close_only_days": len(only_cl),
        "fill_component_total": round(fill_gap, 0),
        "fill_component_per_day": round(fill_gap / n_days, 1),
        "selection_component_total": round(selpick_gap, 0),
        "selection_component_per_day": round(selpick_gap / n_days, 1),
        "select_only_arm_per_day": round(per_day(vecs["SELECT_ONLY"]), 1),
    }
    print("  decomp: same-pick %d days ($%.1f/day), different-pick %d days "
          "($%.1f/day)" % (decomp["same_pick_days"],
                           decomp["fill_component_per_day"],
                           decomp["diff_pick_days"],
                           decomp["selection_component_per_day"]), flush=True)

    same_diff = [picks["MID25"][d][1] - picks["CLOSE_RT"][d][1] for d in same]
    rng_c = random.Random(SEED + 1)
    m2 = sorted(sum(rng_c.choices(same_diff, k=len(same_diff))) / n_days
                for _ in range(BOOTS))
    decomp["fill_only_ci95"] = [round(m2[int(BOOTS * .025)], 1),
                                round(m2[int(BOOTS * .975)], 1)]
    decomp["fill_only_frac_le_zero"] = round(
        sum(1 for m in m2 if m <= 0) / BOOTS, 4)

    # ---------------------------------------------- matched random-skip null
    n_priced = len(priced[0.25])
    n_close_rt = len(close_rt)
    skip_p = 1.0 - (n_priced / max(n_close_rt, 1))
    rng_n = random.Random(SEED + 2)
    null_pd = []
    for _ in range(NULLS):
        keep = {k: close_rt[k] for k in close_rt if rng_n.random() >= skip_p}
        null_pd.append(per_day(daily_vec(pick_by_day(keep))))
    null_pd.sort()
    obs = hdr["MID25"]["per_day"]
    null = {
        "skip_rate": round(skip_p, 4),
        "n_draws": NULLS,
        "null_mean_per_day": round(sum(null_pd) / NULLS, 1),
        "null_p05": round(null_pd[int(NULLS * .05)], 1),
        "null_p95": round(null_pd[int(NULLS * .95)], 1),
        "null_max": round(null_pd[-1], 1),
        "frac_null_ge_MID25": round(sum(1 for x in null_pd if x >= obs) / NULLS, 4),
        "frac_null_ge_SELECT_ONLY": round(
            sum(1 for x in null_pd if x >= decomp["select_only_arm_per_day"]) / NULLS, 4),
    }
    print("  null: skip %.1f%%, mean $%.1f/day, p95 $%.1f, max $%.1f; "
          "P(null >= MID25 $%.0f) = %.3f"
          % (skip_p * 100, null["null_mean_per_day"], null["null_p95"],
             null["null_max"], obs, null["frac_null_ge_MID25"]), flush=True)

    # ------------------------------------------------- risk denominator check
    rk = [priced[0.25][k]["risk"] for k in priced[0.25]]
    ck = [close_rt[k]["risk"] for k in close_rt]
    risk_note = {
        "MID25_median_risk": round(statistics.median(rk), 4),
        "CLOSE_RT_median_risk": round(statistics.median(ck), 4),
        "MID25_pct_risk_under_10c": round(
            sum(1 for x in rk if x < 0.10) / len(rk) * 100, 1),
        "CLOSE_RT_pct_risk_under_10c": round(
            sum(1 for x in ck if x < 0.10) / len(ck) * 100, 1),
    }
    print("  risk: MID25 median $%.3f vs CLOSE_RT $%.3f"
          % (risk_note["MID25_median_risk"],
             risk_note["CLOSE_RT_median_risk"]), flush=True)

    # ------------------------------------------- per-half paired bootstrap
    def paired_boot_days(a, b, days, seed):
        idx = [i for i, d in enumerate(all_days) if d in days]
        diff = [vecs[a][i] - vecs[b][i] for i in idx]
        m = len(diff)
        rr = random.Random(seed)
        means = sorted(sum(rr.choices(diff, k=m)) / m for _ in range(BOOTS))
        return {"n_days": m, "mean_diff_per_day": round(sum(diff) / m, 1),
                "ci95": [round(means[int(BOOTS * .025)], 1),
                         round(means[int(BOOTS * .975)], 1)],
                "boot_frac_le_zero": round(
                    sum(1 for x in means if x <= 0) / BOOTS, 4)}

    h1_days = {d for d in all_days if half(d) == "H1"}
    h2_days = {d for d in all_days if half(d) == "H2"}
    halves = {}
    for arm in ("MID25", "MID50", "MID75"):
        halves[arm + "_vs_CLOSE_RT_H1"] = paired_boot_days(
            arm, "CLOSE_RT", h1_days, SEED + 10)
        halves[arm + "_vs_CLOSE_RT_H2"] = paired_boot_days(
            arm, "CLOSE_RT", h2_days, SEED + 11)
    for k, v in halves.items():
        print("  half %-26s %+7.1f/day  CI95 [%+.1f, %+.1f]  P(<=0)=%.3f"
              % (k, v["mean_diff_per_day"], v["ci95"][0], v["ci95"][1],
                 v["boot_frac_le_zero"]), flush=True)

    # H1 picks the fraction, H2 validates it -- the only honest split here.
    h1_best = max(("MID25", "MID50", "MID75"),
                  key=lambda a: hdr[a]["H1_per_day"])
    honest = {"arm_chosen_on_H1": h1_best,
              "H1_per_day": hdr[h1_best]["H1_per_day"],
              "H2_validation": halves[h1_best + "_vs_CLOSE_RT_H2"]}
    print("  H1 picks %s ($%.1f/day on H1); H2 validation %+.1f/day CI [%+.1f, "
          "%+.1f] P(<=0)=%.3f"
          % (h1_best, honest["H1_per_day"],
             honest["H2_validation"]["mean_diff_per_day"],
             honest["H2_validation"]["ci95"][0],
             honest["H2_validation"]["ci95"][1],
             honest["H2_validation"]["boot_frac_le_zero"]), flush=True)

    # -------------------------------- best-of-3 max statistic (multiplicity)
    rr = random.Random(SEED + 20)
    diffs3 = {a: [vecs[a][i] - vecs["CLOSE_RT"][i] for i in range(n_days)]
              for a in ("MID25", "MID50", "MID75")}
    maxes = []
    for _ in range(BOOTS):
        ix = rr.choices(range(n_days), k=n_days)
        maxes.append(max(sum(diffs3[a][i] for i in ix) / n_days
                         for a in diffs3))
    maxes.sort()
    bestof3 = {
        "observed_max": round(max(sum(diffs3[a]) / n_days for a in diffs3), 1),
        "ci95": [round(maxes[int(BOOTS * .025)], 1),
                 round(maxes[int(BOOTS * .975)], 1)],
        "boot_frac_max_le_zero": round(
            sum(1 for x in maxes if x <= 0) / BOOTS, 4),
        "arms_in_family_this_row": 3,
    }
    print("  best-of-3 max %+7.1f/day  CI95 [%+.1f, %+.1f]  P(max<=0)=%.3f"
          % (bestof3["observed_max"], bestof3["ci95"][0], bestof3["ci95"][1],
             bestof3["boot_frac_max_le_zero"]), flush=True)

    # -------------------------------------- positive-gap concentration
    gapv = [(d, vecs["MID25"][i] - vecs["CLOSE_RT"][i])
            for i, d in enumerate(all_days)]
    pos = sorted([g for g in gapv if g[1] > 0], key=lambda t: -t[1])
    tot_gap = sum(v for _, v in gapv)
    conc = {
        "total_gap": round(tot_gap, 0),
        "n_positive_days": len(pos),
        "n_negative_days": sum(1 for _, v in gapv if v < 0),
        "top5_positive_share_of_net_gap": round(
            sum(v for _, v in pos[:5]) / tot_gap, 3) if tot_gap else 0.0,
        "top20_positive_share_of_net_gap": round(
            sum(v for _, v in pos[:20]) / tot_gap, 3) if tot_gap else 0.0,
        "top5_positive_days": [(d, round(v, 0)) for d, v in pos[:5]],
        "net_gap_per_day_dropping_top5_positive": round(
            (tot_gap - sum(v for _, v in pos[:5])) / (n_days - 5), 1),
        "net_gap_per_day_dropping_top20_positive": round(
            (tot_gap - sum(v for _, v in pos[:20])) / (n_days - 20), 1),
    }
    print("  concentration: top5 positive days = %.1f%% of the net gap; drop "
          "them and the gap is %+.1f/day"
          % (conc["top5_positive_share_of_net_gap"] * 100,
             conc["net_gap_per_day_dropping_top5_positive"]), flush=True)

    # ------------------- robustness of the daily gap: sign test + trimmed mean
    gv = sorted(v for _, v in gapv)
    nz2 = [v for v in gv if abs(v) > 1e-9]
    npos = sum(1 for v in nz2 if v > 0)
    # exact two-sided binomial sign test on the differing days
    import math as _m
    n_nz = len(nz2)
    tail = sum(_m.comb(n_nz, i) for i in range(npos, n_nz + 1)) / (2 ** n_nz)
    robust = {
        "differing_days": n_nz,
        "positive_days": npos,
        "negative_days": n_nz - npos,
        "sign_test_p_two_sided": round(min(1.0, 2 * tail), 6),
        "median_daily_gap_all_sessions": round(statistics.median(gv), 1),
        "median_daily_gap_differing": round(statistics.median(nz2), 1),
    }
    for tpct in (0.01, 0.025, 0.05):
        cut = int(n_days * tpct)
        trimmed = gv[cut:n_days - cut]
        robust["trimmed_mean_%.1f%%_each_tail" % (tpct * 100)] = round(
            sum(trimmed) / len(trimmed), 1)
    print("  robust: %d+/%d- differing days, sign p=%.2g, median gap $%.0f, "
          "5%%-trimmed mean $%+.1f/day"
          % (npos, n_nz - npos, robust["sign_test_p_two_sided"],
             robust["median_daily_gap_differing"],
             robust["trimmed_mean_5.0%_each_tail"]), flush=True)

    # -------------------- g90's paired per-trade test, run on g158's own data
    # g90 R2 measured close-minus-mid as a PAIRED per-trade mean-R difference on
    # the signals where both filled. Do exactly that here, per candidate, not on
    # the one-a-day selection unit, so the two reports are compared like for like.
    paired_r = {}
    for f in FRACS:
        both = [k for k in priced[f] if k in close_rt]
        d = [priced[f][k]["r"] - close_rt[k]["r"] for k in both]
        m = len(d)
        rr2 = random.Random(SEED + 30)
        means = sorted(sum(rr2.choices(d, k=m)) / m for _ in range(BOOTS))
        paired_r[ARM_NAMES[f]] = {
            "n_both_filled": m,
            "mean_r_arm": round(sum(priced[f][k]["r"] for k in both) / m, 4),
            "mean_r_close": round(sum(close_rt[k]["r"] for k in both) / m, 4),
            "paired_diff_r": round(sum(d) / m, 4),
            "ci95": [round(means[int(BOOTS * .025)], 4),
                     round(means[int(BOOTS * .975)], 4)],
        }
        print("  paired-R %-6s n=%d  arm %+0.4f vs close %+0.4f  diff %+0.4f "
              "CI [%+0.4f, %+0.4f]"
              % (ARM_NAMES[f], m, paired_r[ARM_NAMES[f]]["mean_r_arm"],
                 paired_r[ARM_NAMES[f]]["mean_r_close"],
                 paired_r[ARM_NAMES[f]]["paired_diff_r"],
                 paired_r[ARM_NAMES[f]]["ci95"][0],
                 paired_r[ARM_NAMES[f]]["ci95"][1]), flush=True)

    out = {"paired_per_trade_r": paired_r,
           "book": BOOK.name, "sessions": n_days, "candidates": len(keys),
           "arms": hdr, "paired_bootstrap": boots, "dominance": dom,
           "half_bootstrap": halves, "h1_select_h2_validate": honest,
           "best_of_3": bestof3, "concentration": conc, "robustness": robust,
           "daily_gap_MID25_minus_CLOSE_RT": {d: round(v, 2)
                                              for d, v in gapv if abs(v) > 1e-9},
           "decomposition": decomp, "random_skip_null": null,
           "risk": risk_note,
           "rows_priced": {"CLOSE_RT": n_close_rt,
                           **{ARM_NAMES[f]: len(priced[f]) for f in FRACS}}}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
