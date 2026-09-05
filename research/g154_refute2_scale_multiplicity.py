"""REFUTER #2 (multiplicity + sampling error) for the g154 claim
"scale-before-the-level survives: baseline $50/day -> $93/day (cents_005),
H1 delta +9.4, H2 delta +76.5".

Fill named, per CLAUDE.md: entry = the signal bar CLOSE (the book's own
`entry`); level stop via stop_rule.stop_hit_on_close + stop_rule.stop_fill_price;
disaster stop stop_rule.disaster_stop_price at DISASTER_STOP_R = 1.0;
one-trade-a-day unit = omen_metrics.first_of_day_arm(size_gate=True) with the
signal_runner.min_risk_floor size gate; 1R = $1,000. Book
research/bt2y_trades_retest_on.json, 498 sessions, H1/H2 split 2025-09-01.
Both sides run the CLAIM SCRIPT'S OWN single-stage walker, imported unmodified
(G.simulate_exit / G.shifted_target / G.bars_for), so nothing here is a
re-implementation that could disagree for its own reasons.

  A. FINE b GRID -- b in $0.01 .. $0.30 (14 points) plus 0.05xATR14, against
     the same b=0 baseline. "Rest the scale slightly before the level" is a
     claim about a REGION, not a point: $/day should be smooth and single-
     peaked in b. Ragged sign flips are the signature of noise.
  B. PAIRED BOOTSTRAP over the 498 sessions (10k resamples) of the per-day
     dollar delta (cents_005 minus baseline): overall, H1, H2, and the joint
     P(H1 delta > 0 AND H2 delta > 0).
  C1. SELECTION STABILITY -- inside each resample, re-pick the best of the 3
     published arms by full-sample $/day exactly as a reader of the claim
     table would; how often is cents_005 the winner?
  C2. CENTERED NULL -- de-mean each published arm's per-day delta so the true
     effect is exactly zero, then measure how often ANY of the 3 published
     arms clears the claim's survivor gate (H1 delta > 0 AND H2 delta > 0).
     That is the family-wise false-positive rate of the gate itself.
  D. CONCENTRATION -- how few sessions carry the whole delta.
  E. PER-ARM t ON EACH HALF -- delta, standard error and t for every b on the
     grid, on H1 and H2 separately. The survivor gate needs BOTH halves
     positive, so H1 is load-bearing: if no b anywhere in the plausible
     region reaches t > 1.96 on H1, the gate is being cleared by noise.
     Also prints the BOOK's own booked (multi-stage ladder) $/day on the same
     498-session one-trade-a-day unit, to size the gap between the claim's
     single-stage proxy baseline and the money the engine actually books.

    python research/g154_refute2_scale_multiplicity.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

spec = importlib.util.spec_from_file_location(
    "g154scale", os.path.join(HERE, "g154_rule_scale-before-the-level.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

from research import omen_metrics as om            # noqa: E402

H_SPLIT = "2025-09-01"
RISK = G.RISK
FINE_B = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10,
          0.12, 0.15, 0.20, 0.25, 0.30, 0.50]
PUBLISHED = ["cents_002", "cents_005", "atr_005"]
CACHE = os.path.join(HERE, "g154_refute2_scale_grid.json")
OUT_JSON = os.path.join(HERE, "g154_refute2_scale_multiplicity.json")
OUT_MD = os.path.join(HERE, "g154_refute2_scale_multiplicity.md")
N_BOOT = 10000
SEED = 20260905


# ------------------------------------------------------------------ cache

def build_cache():
    blob = json.load(open(G.BOOK, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    n_days = meta.get("sessions") or len({r["day"] for r in rows})
    picks = om.first_of_day_arm(rows, size_gate=True)
    out = []
    for r in sorted(picks, key=lambda x: (x["day"], x["et"], x["sym"])):
        bars = G.bars_for(r["sym"], r["day"])
        rec = {"day": r["day"], "sym": r["sym"], "arms": {}}
        pnl, rm, reason = G.simulate_exit(r, r["target"])
        rec["arms"]["base"] = [round(pnl, 4), reason]
        for b in FINE_B:
            tgt = G.shifted_target(r, b)
            pnl, rm, reason = G.simulate_exit(r, tgt)
            rec["arms"]["c%.2f" % b] = [round(pnl, 4), reason]
        ab, _fb = G.resolve_b("atr", 0.05, r, bars)
        tgt = G.shifted_target(r, ab)
        pnl, rm, reason = G.simulate_exit(r, tgt)
        rec["arms"]["atr_005"] = [round(pnl, 4), reason]
        out.append(rec)
    blob_out = {"sessions": n_days, "rows": out}
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(blob_out, f)
    return blob_out


def load_cache(rebuild=False):
    if not rebuild and os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    return build_cache()


# ------------------------------------------------------------------ stats

def per_day(rows, arm):
    """{day: dollars} for one arm (one pick per day, so this is just the row)."""
    d = {}
    for r in rows:
        d[r["day"]] = r["arms"][arm][0]
    return d


def usd_day(deltas, days):
    if not days:
        return 0.0
    return sum(deltas[d] for d in days) / len(days)


def split_days(days):
    h1 = [d for d in days if d < H_SPLIT]
    h2 = [d for d in days if d >= H_SPLIT]
    return h1, h2


def arm_row(rows, arm):
    base = per_day(rows, "base")
    cand = per_day(rows, arm)
    days = sorted(base)
    delta = {d: cand[d] - base[d] for d in days}
    h1, h2 = split_days(days)
    return {
        "usd_day": round(sum(cand[d] for d in days) / len(days), 2),
        "h1_usd_day": round(sum(cand[d] for d in h1) / len(h1), 2),
        "h2_usd_day": round(sum(cand[d] for d in h2) / len(h2), 2),
        "delta_usd_day": round(usd_day(delta, days), 2),
        "h1_delta": round(usd_day(delta, h1), 2),
        "h2_delta": round(usd_day(delta, h2), 2),
        "n_days_changed": sum(1 for d in days if abs(delta[d]) > 1e-6),
        "delta": delta,
    }


def main():
    rebuild = "--rebuild" in sys.argv
    cache = load_cache(rebuild)
    rows = cache["rows"]
    n_days = cache["sessions"]
    days = sorted(per_day(rows, "base"))
    h1d, h2d = split_days(days)
    base = per_day(rows, "base")
    base_full = round(sum(base.values()) / len(days), 2)
    base_h1 = round(sum(base[d] for d in h1d) / len(h1d), 2)
    base_h2 = round(sum(base[d] for d in h2d) / len(h2d), 2)
    print("sessions %d (H1 %d / H2 %d) -- baseline $%.2f/day (H1 $%.2f, H2 $%.2f)"
          % (n_days, len(h1d), len(h2d), base_full, base_h1, base_h2))

    # ---------------- A. fine b grid ----------------
    grid = {}
    print("\nA. FINE b GRID (b=0 baseline $%.0f/day)" % base_full)
    for b in FINE_B:
        arm = "c%.2f" % b
        a = arm_row(rows, arm)
        a["survivor"] = a["h1_delta"] > 0 and a["h2_delta"] > 0
        grid["$%.2f" % b] = {k: v for k, v in a.items() if k != "delta"}
        print("  b=$%.2f  $%7.2f/day  H1 %+8.2f  H2 %+8.2f  changed %3d/498  survivor=%s"
              % (b, a["usd_day"], a["h1_delta"], a["h2_delta"],
                 a["n_days_changed"], a["survivor"]))
    a_atr = arm_row(rows, "atr_005")
    a_atr["survivor"] = a_atr["h1_delta"] > 0 and a_atr["h2_delta"] > 0
    grid["0.05xATR14"] = {k: v for k, v in a_atr.items() if k != "delta"}
    print("  0.05xATR14 $%7.2f/day  H1 %+8.2f  H2 %+8.2f  changed %3d/498  survivor=%s"
          % (a_atr["usd_day"], a_atr["h1_delta"], a_atr["h2_delta"],
             a_atr["n_days_changed"], a_atr["survivor"]))
    n_grid_surv = sum(1 for v in grid.values() if v["survivor"])
    print("  grid survivors: %d / %d" % (n_grid_surv, len(grid)))

    # ---------------- B. paired bootstrap ----------------
    pub = {"cents_002": arm_row(rows, "c0.02"),
           "cents_005": arm_row(rows, "c0.05"),
           "atr_005": a_atr}
    hero = pub["cents_005"]
    d_all = [hero["delta"][d] for d in days]
    d_h1 = [hero["delta"][d] for d in h1d]
    d_h2 = [hero["delta"][d] for d in h2d]

    rng = random.Random(SEED)

    def boot(vals, n):
        return sum(vals[rng.randrange(n)] for _ in range(n)) / n

    b_all, b_h1, b_h2, joint = [], [], [], 0
    n, n1, n2 = len(d_all), len(d_h1), len(d_h2)
    for _ in range(N_BOOT):
        b_all.append(boot(d_all, n))
        x1 = boot(d_h1, n1)
        x2 = boot(d_h2, n2)
        b_h1.append(x1)
        b_h2.append(x2)
        if x1 > 0 and x2 > 0:
            joint += 1

    def ci(v):
        s = sorted(v)
        return [round(s[int(0.025 * len(s))], 2), round(s[int(0.975 * len(s))], 2)]

    boot_out = {
        "n_resamples": N_BOOT,
        "delta_usd_day": hero["delta_usd_day"],
        "ci95_delta_usd_day": ci(b_all),
        "p_delta_le_0": round(sum(1 for x in b_all if x <= 0) / N_BOOT, 4),
        "h1_delta": hero["h1_delta"], "ci95_h1": ci(b_h1),
        "h2_delta": hero["h2_delta"], "ci95_h2": ci(b_h2),
        "p_h1_le_0": round(sum(1 for x in b_h1 if x <= 0) / N_BOOT, 4),
        "p_h2_le_0": round(sum(1 for x in b_h2 if x <= 0) / N_BOOT, 4),
        "p_both_halves_positive": round(joint / N_BOOT, 4),
    }
    print("\nB. PAIRED BOOTSTRAP (cents_005 minus baseline, %d resamples)" % N_BOOT)
    print("   delta $%+.2f/day  CI95 %s  P(delta<=0)=%.3f"
          % (hero["delta_usd_day"], boot_out["ci95_delta_usd_day"], boot_out["p_delta_le_0"]))
    print("   H1 %+.2f CI95 %s (P<=0 %.3f) | H2 %+.2f CI95 %s (P<=0 %.3f)"
          % (hero["h1_delta"], boot_out["ci95_h1"], boot_out["p_h1_le_0"],
             hero["h2_delta"], boot_out["ci95_h2"], boot_out["p_h2_le_0"]))
    print("   P(both halves positive on a resample) = %.3f"
          % boot_out["p_both_halves_positive"])

    # ---------------- C1. selection stability ----------------
    rng2 = random.Random(SEED + 1)
    idx_all = list(range(n))
    win = defaultdict(int)
    for _ in range(N_BOOT):
        pick = [idx_all[rng2.randrange(n)] for _ in range(n)]
        best, best_v = None, None
        for name in PUBLISHED:
            dd = pub[name]["delta"]
            v = sum(dd[days[i]] for i in pick) / n
            if best_v is None or v > best_v:
                best, best_v = name, v
        win[best] += 1
    stability = {k: round(v / N_BOOT, 4) for k, v in win.items()}
    print("\nC1. SELECTION STABILITY (best-of-3 by $/day, per resample): %s" % stability)

    # ---------------- C2. centered null ----------------
    rng3 = random.Random(SEED + 2)
    centered = {}
    for name in PUBLISHED:
        dd = pub[name]["delta"]
        m = sum(dd.values()) / len(days)
        centered[name] = {d: dd[d] - m for d in days}
    fam_hits = 0
    single_hits = 0
    for _ in range(N_BOOT):
        pick = [idx_all[rng3.randrange(n)] for _ in range(n)]
        pd = [days[i] for i in pick]
        p1 = [d for d in pd if d < H_SPLIT]
        p2 = [d for d in pd if d >= H_SPLIT]
        if not p1 or not p2:
            continue
        any_pass = False
        for name in PUBLISHED:
            c = centered[name]
            v1 = sum(c[d] for d in p1) / len(p1)
            v2 = sum(c[d] for d in p2) / len(p2)
            ok = v1 > 0 and v2 > 0
            if name == "cents_005" and ok:
                single_hits += 1
            if ok:
                any_pass = True
        if any_pass:
            fam_hits += 1
    null_out = {
        "p_single_arm_passes_gate_under_null": round(single_hits / N_BOOT, 4),
        "p_any_of_3_arms_passes_gate_under_null": round(fam_hits / N_BOOT, 4),
    }
    print("\nC2. CENTERED NULL (true effect = 0): one arm clears the H1&H2 gate "
          "%.1f%% of the time; ANY of the 3 clears it %.1f%% of the time"
          % (100 * null_out["p_single_arm_passes_gate_under_null"],
             100 * null_out["p_any_of_3_arms_passes_gate_under_null"]))

    # ---------------- D. concentration ----------------
    order = sorted(days, key=lambda d: -abs(hero["delta"][d]))
    total = sum(hero["delta"].values())
    conc = {}
    for k in (1, 3, 5, 10, 20):
        conc["top%d_share_of_total_delta" % k] = (
            round(sum(hero["delta"][d] for d in order[:k]) / total, 3) if total else None)
    conc["n_days_changed"] = hero["n_days_changed"]
    conc["top5_days"] = [[d, round(hero["delta"][d], 0)] for d in order[:5]]
    print("\nD. CONCENTRATION: %d/498 sessions change at all; top-1 carries %.0f%% of "
          "the total delta, top-3 %.0f%%, top-10 %.0f%%"
          % (conc["n_days_changed"], 100 * conc["top1_share_of_total_delta"],
             100 * conc["top3_share_of_total_delta"], 100 * conc["top10_share_of_total_delta"]))
    print("   top-5 days: %s" % conc["top5_days"])

    # ---------------- E. per-arm t on each half + book-vs-proxy ----------------
    import math

    def stat(v):
        k = len(v)
        m = sum(v) / k
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / (k - 1))
        se = sd / math.sqrt(k)
        return m, se, (m / se if se else 0.0)

    grid_arms = ["c%.2f" % b for b in FINE_B] + ["atr_005"]
    tstats = {}
    print("\nE. PER-ARM t ON EACH HALF (survivor gate needs BOTH halves > 0)")
    print("   arm         H1 delta     SE      t  |  H2 delta     SE      t  | full t")
    for a in grid_arms:
        d = {r["day"]: r["arms"][a][0] - r["arms"]["base"][0] for r in rows}
        v1 = [v for k, v in d.items() if k < H_SPLIT]
        v2 = [v for k, v in d.items() if k >= H_SPLIT]
        m1, s1, t1 = stat(v1)
        m2, s2, t2 = stat(v2)
        m0, s0, t0 = stat(list(d.values()))
        tstats[a] = {"h1_delta": round(m1, 2), "h1_se": round(s1, 2), "h1_t": round(t1, 2),
                     "h2_delta": round(m2, 2), "h2_se": round(s2, 2), "h2_t": round(t2, 2),
                     "full_delta": round(m0, 2), "full_se": round(s0, 2),
                     "full_t": round(t0, 2)}
        print("   %-9s  %+8.2f %6.2f  %+5.2f | %+8.2f %6.2f  %+5.2f | %+5.2f"
              % (a, m1, s1, t1, m2, s2, t2, t0))
    region = [a for a in grid_arms if a.startswith("c") and float(a[1:]) <= 0.20]
    region_h1 = [tstats[a]["h1_delta"] for a in region]
    n_sig = sum(1 for a in region if tstats[a]["h1_t"] > 1.96)
    print("   region b<=$0.20 (%d arms): H1 delta mean %+.2f, min %+.2f, max %+.2f; "
          "%d of %d reach t>1.96 on H1"
          % (len(region), sum(region_h1) / len(region), min(region_h1), max(region_h1),
             n_sig, len(region)))

    blob = json.load(open(G.BOOK, encoding="utf-8"))
    bpicks = om.first_of_day_arm(blob["trades"], size_gate=True)
    bt = sum(p["pnl"] for p in bpicks)
    bh1 = [p for p in bpicks if p["day"] < H_SPLIT]
    bh2 = [p for p in bpicks if p["day"] >= H_SPLIT]
    book_ladder = {
        "usd_day": round(bt / n_days, 2),
        "h1_usd_day": round(sum(p["pnl"] for p in bh1) / len({p["day"] for p in bh1}), 2),
        "h2_usd_day": round(sum(p["pnl"] for p in bh2) / len({p["day"] for p in bh2}), 2),
        "mean_r": round(bt / len(bpicks) / RISK, 3),
    }
    print("   BOOK's own booked multi-stage ladder, same unit: $%.2f/day "
          "(H1 $%.2f, H2 $%.2f), mean R %.3f -- the claim's $50 baseline and $93 "
          "candidate are BOTH single-stage proxies, neither is this."
          % (book_ladder["usd_day"], book_ladder["h1_usd_day"],
             book_ladder["h2_usd_day"], book_ladder["mean_r"]))

    out = {
        "claim": "scale-before-the-level survives: $50/day -> $93/day, H1 +9.4, H2 +76.5",
        "reproduced": {
            "baseline_usd_day": base_full, "baseline_h1": base_h1, "baseline_h2": base_h2,
            "cents_005_usd_day": pub["cents_005"]["usd_day"],
            "cents_005_h1_delta": pub["cents_005"]["h1_delta"],
            "cents_005_h2_delta": pub["cents_005"]["h2_delta"],
        },
        "fill": ("signal-bar CLOSE entry (book `entry`); stop_rule.stop_fill_price / "
                 "stop_hit_on_close; disaster stop at 1.0R intrabar; target touched "
                 "intrabar, filled at open on a gap-through; size-gated "
                 "omen_metrics.first_of_day_arm(size_gate=True); 1R=$1,000"),
        "A_fine_b_grid": grid,
        "B_paired_bootstrap": boot_out,
        "C1_selection_stability": stability,
        "C2_centered_null": null_out,
        "D_concentration": conc,
        "E_per_arm_t": tstats,
        "E_region_h1_significant_arms": {"n_arms": len(region), "n_t_gt_1_96": n_sig,
                                         "h1_delta_mean": round(sum(region_h1) / len(region), 2)},
        "E_book_own_ladder_same_unit": book_ladder,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\nwrote %s" % OUT_JSON)
    return out


if __name__ == "__main__":
    main()
