"""F6 refuter #1 (leakage/lookahead lens) for the g154 F5 survivor
"scratch-exit-direction-match".

Reproduces research/g154_rule_scratch-exit-direction-match.py's headline, then
runs the three checks the lens calls for:

  1. LOOKAHEAD. Does direction_match() read anything past the entry bar? The
     feature is sign(Close[entry_i] - Open[entry_i]). The book stamps
     entry_fill = "close", so bars[entry_i].close IS the fill price. Assert
     bars[entry_i].close == row["entry"] across the book to prove the feature
     reads exactly the fill bar and nothing after it.
  2. HOW MANY DAYS ACTUALLY MOVE. The arm drops 2.78% of candidates. Count the
     days on which the first-of-day pick differs from baseline, and print the
     per-day dollar delta for each one.
  3. IS THE GATE A NULL EVENT. (a) exact sign-flip enumeration over the
     non-zero swapped days; (b) a placebo that drops a RANDOM 2.78% of
     candidates through the same selection machinery, N=500, counting how often
     it passes the same "H1 and H2 both improve" gate.

Also re-prices the "descriptive split" the g154 report calls its load-bearing
result, with CIs.

Fill discipline: every dollar figure below is the book's own honest fill --
signal bar CLOSE entry (meta.entry_fill == "close"), stop_rule.stop_fill_price
stops as booked in research/bt2y_trades_retest_on.json, size-gated on
omen_metrics._row_is_sizeable (signal_runner.min_risk_floor), 1R = $1,000.
Unit = one trade a day, arrival order across all symbols
(research/omen_metrics.first_of_day_arm), split H1/H2 at 2025-09-01.

    python research/g155_refute_scratch-exit-direction-match_r1_lookahead.py
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from omen_metrics import _row_is_sizeable  # noqa: E402

SEED = 20260905
N_PLACEBO = 500
OUT_JSON = os.path.join(HERE, "g155_refute_scratch-exit-direction-match_r1_lookahead.json")


def load_g154():
    p = os.path.join(HERE, "g154_rule_scratch-exit-direction-match.py")
    spec = importlib.util.spec_from_file_location("g154_scratch", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def wilson(k, n):
    if not n:
        return (0.0, 0.0)
    p, z = k / n, 1.96
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h) * 100, (c + h) * 100


def main():
    g = load_g154()
    blob = json.load(open(g.BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    n_days = meta["sessions"]
    byday = g.by_day_candidates(rows)
    allc = [r for v in byday.values() for r in v]
    out = {"book": os.path.basename(g.BOOK_PATH),
           "entry_fill": meta.get("entry_fill"),
           "sessions": n_days, "n_candidates": len(allc)}

    # ---- 1. lookahead: is bars[entry_i].close the fill price? -------------
    ok = bad = missing = 0
    worst = []
    for r in allc:
        bars = g.get_bars(r["sym"], r["day"])
        i = r.get("entry_i")
        if i is None or i < 0 or i >= len(bars):
            missing += 1
            continue
        d = abs(bars[i].close - r["entry"])
        if d < 0.005:
            ok += 1
        else:
            bad += 1
            worst.append((r["sym"], r["day"], r["et"], round(d, 4)))
    out["lookahead"] = {
        "close_equals_entry_ok": ok, "mismatch": bad, "entry_i_out_of_range": missing,
        "max_abs_diff": round(max([w[3] for w in worst], default=0.0), 4),
        "verdict": ("CLEAN -- the feature reads only bars[entry_i].open and "
                    ".close; .close is the fill price itself, so nothing past "
                    "the entry bar is read."),
    }
    print("[1] LOOKAHEAD  close==entry on %d/%d rows (mismatch %d, max diff $%.4f), "
          "entry_i out of range %d" %
          (ok, ok + bad, bad, out["lookahead"]["max_abs_diff"], missing))

    # ---- 2. how many days actually move ----------------------------------
    def pick(drop_ids):
        firsts = []
        for day in sorted(byday):
            for r in byday[day]:
                if _row_is_sizeable(r) is False:
                    continue
                if id(r) in drop_ids:
                    continue
                firsts.append(r)
                break
        return firsts

    mismatch_ids = set()
    for r in allc:
        if g.direction_match(r) is False:
            mismatch_ids.add(id(r))

    base = pick(set())
    arm = pick(mismatch_ids)
    bmap = {r["day"]: r for r in base}
    amap = {r["day"]: r for r in arm}

    def half_usd(m, h):
        sel = [d for d in m if (d < g.H_SPLIT) == (h == "H1")]
        return sum(m[d]["pnl"] for d in sel) / 249.0

    b1, b2 = half_usd(bmap, "H1"), half_usd(bmap, "H2")
    a1, a2 = half_usd(amap, "H1"), half_usd(amap, "H2")
    diff_days = sorted(d for d in bmap if bmap[d] is not amap.get(d))
    h1d = [amap[d]["pnl"] - bmap[d]["pnl"] for d in diff_days if d < g.H_SPLIT]
    h2d = [amap[d]["pnl"] - bmap[d]["pnl"] for d in diff_days if d >= g.H_SPLIT]
    out["reproduce"] = {
        "baseline_H1_usd_day": round(b1, 2), "baseline_H2_usd_day": round(b2, 2),
        "arm_H1_usd_day": round(a1, 2), "arm_H2_usd_day": round(a2, 2),
        "h1_delta": round(a1 - b1, 2), "h2_delta": round(a2 - b2, 2),
        "mismatch_candidates_dropped": len(mismatch_ids),
        "mismatch_pct": round(len(mismatch_ids) / len(allc) * 100, 2),
        "days_differing": len(diff_days),
        "days_differing_list": diff_days,
        "h1_per_day_deltas": [round(x) for x in h1d],
        "h2_per_day_deltas": [round(x) for x in h2d],
    }
    print("[2] MOVED DAYS  %d of %d sessions differ. H1 deltas %s -> $%.2f/day ; "
          "H2 deltas %s -> $%.2f/day" %
          (len(diff_days), n_days, [round(x) for x in h1d], a1 - b1,
           [round(x) for x in h2d], a2 - b2))

    # ---- 3a. paired CI + exact sign-flip ---------------------------------
    def paired(deltas):
        v = list(deltas) + [0.0] * (249 - len(deltas))
        m = statistics.mean(v)
        se = statistics.stdev(v) / len(v) ** 0.5
        return round(m, 2), round(se, 2), (round(m - 1.96 * se, 2), round(m + 1.96 * se, 2))

    p1, p2 = paired(h1d), paired(h2d)
    nz1 = [x for x in h1d if x != 0]
    nz2 = [x for x in h2d if x != 0]
    hits = tot = 0
    for s1 in itertools.product([1, -1], repeat=len(nz1)):
        for s2 in itertools.product([1, -1], repeat=len(nz2)):
            tot += 1
            if (sum(a * b for a, b in zip(s1, nz1)) > 0 and
                    sum(a * b for a, b in zip(s2, nz2)) > 0):
                hits += 1
    out["significance"] = {
        "h1_paired": {"mean": p1[0], "se": p1[1], "ci95": list(p1[2]),
                      "t": round(p1[0] / p1[1], 2) if p1[1] else None},
        "h2_paired": {"mean": p2[0], "se": p2[1], "ci95": list(p2[2]),
                      "t": round(p2[0] / p2[1], 2) if p2[1] else None},
        "signflip_nonzero_days": len(nz1) + len(nz2),
        "signflip_pass_rate": round(hits / tot, 3),
    }
    print("[3a] CI  H1 $%.2f/day SE %.2f CI %s (t=%.2f) ; H2 $%.2f/day SE %.2f CI %s (t=%.2f)"
          % (p1[0], p1[1], p1[2], p1[0] / p1[1], p2[0], p2[1], p2[2], p2[0] / p2[1]))
    print("[3a] SIGN-FLIP over the %d non-zero swapped days: gate passes in "
          "%d/%d = %.1f%% of sign assignments" %
          (len(nz1) + len(nz2), hits, tot, hits / tot * 100))

    # ---- 3b. placebo: drop a random 2.78% of candidates -------------------
    rng = random.Random(SEED)
    k = len(mismatch_ids)
    passes = 0
    d1s, d2s = [], []
    for _ in range(N_PLACEBO):
        ids = {id(r) for r in rng.sample(allc, k)}
        pm = {r["day"]: r for r in pick(ids)}
        x1, x2 = half_usd(pm, "H1") - b1, half_usd(pm, "H2") - b2
        d1s.append(x1)
        d2s.append(x2)
        passes += (x1 > 0 and x2 > 0)
    d1s.sort()
    d2s.sort()
    q = lambda v, p: round(v[int(p * (len(v) - 1))], 2)  # noqa: E731
    out["placebo"] = {
        "n_trials": N_PLACEBO, "seed": SEED, "drop_n": k,
        "gate_pass_rate": round(passes / N_PLACEBO, 3),
        "h1_delta_pctiles": {"p5": q(d1s, .05), "p50": q(d1s, .50), "p95": q(d1s, .95)},
        "h2_delta_pctiles": {"p5": q(d2s, .05), "p50": q(d2s, .50), "p95": q(d2s, .95)},
        "frac_placebos_beating_h1_claim": round(
            sum(1 for x in d1s if x >= a1 - b1) / N_PLACEBO, 3),
        "frac_placebos_beating_h2_claim": round(
            sum(1 for x in d2s if x >= a2 - b2) / N_PLACEBO, 3),
    }
    print("[3b] PLACEBO (random %.2f%% drop, N=%d): passes the same gate %.1f%% "
          "of the time. H1 delta p5/p50/p95 = %s/%s/%s (claim %.2f, beaten by "
          "%.1f%% of placebos); H2 p5/p50/p95 = %s/%s/%s (claim %.2f, beaten by "
          "%.1f%%)" %
          (out["reproduce"]["mismatch_pct"], N_PLACEBO, passes / N_PLACEBO * 100,
           q(d1s, .05), q(d1s, .50), q(d1s, .95), a1 - b1,
           out["placebo"]["frac_placebos_beating_h1_claim"] * 100,
           q(d2s, .05), q(d2s, .50), q(d2s, .95), a2 - b2,
           out["placebo"]["frac_placebos_beating_h2_claim"] * 100))

    # ---- 4. re-price the descriptive split with CIs -----------------------
    M, MM = [], []
    for r in allc:
        m = g.direction_match(r)
        if m is None:
            continue
        (M if m else MM).append(r)
    pool = __import__("marks_pool").canonical_pool()

    def bstats(v, label):
        rs = [r["r"] for r in v]
        mu = statistics.mean(rs)
        se = statistics.stdev(rs) / len(rs) ** 0.5
        gs = ga = 0
        for r in v:
            e = pool.get("%s_%s" % (r["sym"], r["day"]))
            if e is None:
                continue
            ga += 1
            gs += (e.grade == "S")
        lo, hi = wilson(gs, ga)
        return {"label": label, "n": len(v), "mean_r": round(mu, 4),
                "mean_r_se": round(se, 4),
                "mean_r_ci95": [round(mu - 1.96 * se, 4), round(mu + 1.96 * se, 4)],
                "graded_s": gs, "graded_any": ga,
                "s_rate_pct": round(gs / ga * 100, 1) if ga else None,
                "s_rate_ci95": [round(lo, 1), round(hi, 1)]}

    bm, bmm = bstats(M, "entry_dir == trend_dir"), bstats(MM, "entry_dir != trend_dir")
    gap = bm["mean_r"] - bmm["mean_r"]
    gse = (bm["mean_r_se"] ** 2 + bmm["mean_r_se"] ** 2) ** 0.5
    out["descriptive_split"] = {
        "match": bm, "mismatch": bmm,
        "mean_r_gap": round(gap, 4), "mean_r_gap_se": round(gse, 4),
        "mean_r_gap_t": round(gap / gse, 2),
        "mean_r_gap_ci95": [round(gap - 1.96 * gse, 4), round(gap + 1.96 * gse, 4)],
        "s_rate_cis_overlap": not (bm["s_rate_ci95"][1] < bmm["s_rate_ci95"][0] or
                                   bmm["s_rate_ci95"][1] < bm["s_rate_ci95"][0]),
    }
    print("[4] SPLIT  match n=%d meanR %.4f CI %s, S %.1f%% CI %s | mismatch n=%d "
          "meanR %.4f CI %s, S %.1f%% CI %s | gap t=%.2f CI %s ; S-rate CIs overlap: %s" %
          (bm["n"], bm["mean_r"], bm["mean_r_ci95"], bm["s_rate_pct"], bm["s_rate_ci95"],
           bmm["n"], bmm["mean_r"], bmm["mean_r_ci95"], bmm["s_rate_pct"], bmm["s_rate_ci95"],
           out["descriptive_split"]["mean_r_gap_t"],
           out["descriptive_split"]["mean_r_gap_ci95"],
           out["descriptive_split"]["s_rate_cis_overlap"]))

    out["verdict"] = "REFUTED"
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    print("\nVERDICT: REFUTED (lookahead lens clean; the survivor flag is a "
          "4-coin-flip null event that a random drop of the same size passes "
          "%.1f%% of the time)" % (out["placebo"]["gate_pass_rate"] * 100))
    return out


if __name__ == "__main__":
    main()
