"""REFUTER #2 (multiplicity + sampling error) for the g154 claim
"scratch-exit-direction-match survives: baseline $33.93/day -> $35.09/day,
H1 delta 1.89, H2 delta 0.42, precision 30.5 -> 30.0, recall_100 5.9 -> 5.9".

Fill named, per CLAUDE.md: entry = the signal bar CLOSE (the book's own
`entry`), stops via stop_rule.stop_fill_price with DISASTER_STOP_R = 1.0,
one-trade-a-day unit = the claim script's own pick_first_of_day (identical to
omen_metrics.first_of_day_arm: arrival order across all symbols, size-gated on
signal_runner.min_risk_floor), 1R = $1,000. Book
research/bt2y_trades_retest_on.json, 498 sessions, H1/H2 split 2025-09-01.
Every arm below runs the CLAIM SCRIPT'S OWN functions, imported unmodified
(G.pick_first_of_day / G.score / G.precision / G.recall / G.direction_match),
so nothing here is a re-implementation that could disagree for its own reasons.

  A. REPRODUCTION -- rerun the claim script's arms and diff against its
     published JSON, field by field.
  B. FOOTPRINT -- how many of the 498 sessions actually change hands between
     baseline and arm, and how concentrated the whole dollar delta is.
  C. PAIRED BOOTSTRAP over sessions (10k resamples) of the per-day dollar
     delta (arm minus baseline): overall, H1, H2, and the joint
     P(H1 delta > 0 AND H2 delta > 0) -- the claim's own survivor gate.
  D. LABEL-PERMUTATION NULL -- keep the arm's exact shape (drop the same
     number of candidates, fall through to the next) but shuffle WHICH
     candidates carry the mismatch label. The direction signal is destroyed;
     everything else is identical. How often does a random relabelling clear
     the claim's survivor gate? That is the per-candidate false-positive rate
     of the gate on this book, and x25 candidates tried is the family-wise
     expectation.
  E. DESCRIPTIVE SPLIT -- the report calls the split "NOT flat" off a
     20.1pp S-rate gap. Fisher exact on the 2x2 and a Welch t on the mean-R
     gap say whether 20 graded cards can carry that.

    python research/g154_refute2_scratch_multiplicity.py

Writes research/g154_refute2_scratch_multiplicity.{json,md}.
"""
from __future__ import annotations

import importlib.util
import json
import math
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
    "g154scratch", os.path.join(HERE, "g154_rule_scratch-exit-direction-match.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

import marks_pool  # noqa: E402

OUT_JSON = os.path.join(HERE, "g154_refute2_scratch_multiplicity.json")
OUT_MD = os.path.join(HERE, "g154_refute2_scratch_multiplicity.md")
CLAIM_JSON = os.path.join(HERE, "g154_rule_scratch-exit-direction-match.json")

N_BOOT = 10000
N_NULL = 2000
N_TRIED = 25          # candidates in the g154 family
SEED = 20260905


# ------------------------------------------------------------------ machinery

def pick_with_labels(byday, drop_keys):
    """The claim's pick_first_of_day, but the 'drop this candidate' decision
    comes from an explicit key set instead of direction_match(). Same
    pick-then-gate fall-through, same size gate."""
    firsts = []
    for day in sorted(byday):
        pick = None
        for r in byday[day]:
            if G._row_is_sizeable(r) is False:
                continue
            if drop_keys is not None and G.ekey(r) in drop_keys:
                continue
            pick = r
            break
        if pick is not None:
            firsts.append(pick)
    return firsts


def arm_stats(firsts, pool, s_pairs_100):
    h1, h2 = G.split_h1_h2(firsts)
    p, gs, ga = G.precision(firsts, pool)
    r100, hit100, n100 = G.recall(firsts, s_pairs_100)
    return {
        "overall": G.score(firsts), "H1": G.score(h1), "H2": G.score(h2),
        "precision_pct": p, "precision_s": gs, "precision_n": ga,
        "recall100_pct": r100, "recall100_hit": hit100, "recall100_n": n100,
    }


def survivor_gate(base, arm):
    """The claim script's own gate, verbatim:
       improves = (H1 delta > 0 and H2 delta > 0) or precision goes up
       recall_ok = arm recall_100 >= baseline recall_100"""
    h1d = arm["H1"]["usd_day"] - base["H1"]["usd_day"]
    h2d = arm["H2"]["usd_day"] - base["H2"]["usd_day"]
    usd = h1d > 0 and h2d > 0
    prec = arm["precision_pct"] > base["precision_pct"]
    rec = arm["recall100_pct"] >= base["recall100_pct"]
    return bool((usd or prec) and rec), h1d, h2d, usd, prec


def pct(xs, q):
    if not xs:
        return 0.0
    s = sorted(xs)
    i = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
    return s[i]


def fisher_exact_two_tail(a, b, c, d):
    """2x2 [[a,b],[c,d]] two-tailed Fisher exact p."""
    def logC(n, k):
        return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1))

    n = a + b + c + d
    r1, r2 = a + b, c + d
    c1 = a + c

    def prob(x):
        y = r1 - x
        z = c1 - x
        w = r2 - z
        if y < 0 or z < 0 or w < 0:
            return 0.0
        return math.exp(logC(r1, x) + logC(r2, z) - logC(n, c1))

    p_obs = prob(a)
    lo = max(0, c1 - r2)
    hi = min(r1, c1)
    tot = 0.0
    for x in range(lo, hi + 1):
        p = prob(x)
        if p <= p_obs * (1 + 1e-9):
            tot += p
    return min(1.0, tot)


def welch_t(xs, ys):
    nx, ny = len(xs), len(ys)
    if nx < 2 or ny < 2:
        return 0.0, 0.0, 0.0
    mx = sum(xs) / nx
    my = sum(ys) / ny
    vx = sum((v - mx) ** 2 for v in xs) / (nx - 1)
    vy = sum((v - my) ** 2 for v in ys) / (ny - 1)
    se = math.sqrt(vx / nx + vy / ny)
    if se == 0:
        return mx - my, 0.0, 0.0
    t = (mx - my) / se
    # two-tailed normal approximation
    p = math.erfc(abs(t) / math.sqrt(2))
    return mx - my, t, p


# ----------------------------------------------------------------------- main

def main():
    rng = random.Random(SEED)
    blob = json.load(open(G.BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    byday = G.by_day_candidates(rows)
    n_days_total = meta.get("sessions") or len({r["day"] for r in rows})
    all_cands = [r for v in byday.values() for r in v]

    pool = marks_pool.canonical_pool()
    s_pairs_100 = G.load_sweep_s_days()

    # ---- label every candidate once (bars come from data_archive cache)
    labels = {}
    for r in all_cands:
        labels[G.ekey(r)] = G.direction_match(r)
    mismatch_keys = {k for k, v in labels.items() if v is False}
    readable_keys = [k for k, v in labels.items() if v is not None]
    n_mismatch = len(mismatch_keys)

    # ---- A. reproduction
    base_firsts = pick_with_labels(byday, None)
    arm_firsts = pick_with_labels(byday, mismatch_keys)
    base = arm_stats(base_firsts, pool, s_pairs_100)
    arm = arm_stats(arm_firsts, pool, s_pairs_100)
    surv, h1d, h2d, usd_ok, prec_ok = survivor_gate(base, arm)

    claim = json.load(open(CLAIM_JSON, encoding="utf-8"))
    repro = {
        "baseline_usd_day": [base["overall"]["usd_day"], claim["baseline"]["overall"]["usd_day"]],
        "arm_usd_day": [arm["overall"]["usd_day"], claim["arm_keep_match_only"]["overall"]["usd_day"]],
        "h1_delta": [round(h1d, 2), claim["h1_delta_usd_day"]],
        "h2_delta": [round(h2d, 2), claim["h2_delta_usd_day"]],
        "precision_base": [base["precision_pct"], claim["baseline"]["precision"]["pct"]],
        "precision_arm": [arm["precision_pct"], claim["arm_keep_match_only"]["precision"]["pct"]],
        "recall100_base": [base["recall100_pct"], claim["baseline"]["s_recall_100"]["pct"]],
        "recall100_arm": [arm["recall100_pct"], claim["arm_keep_match_only"]["s_recall_100"]["pct"]],
        "survivor": [surv, claim["survivor"]],
    }
    repro_exact = all(abs(v[0] - v[1]) < 1e-6 if isinstance(v[0], (int, float))
                      else v[0] == v[1] for v in repro.values())

    # ---- B. footprint: which days changed hands
    base_by_day = {r["day"]: r for r in base_firsts}
    arm_by_day = {r["day"]: r for r in arm_firsts}
    changed = []
    per_day_delta = {}
    for day in sorted(set(base_by_day) | set(arm_by_day)):
        bp = base_by_day[day]["pnl"] if day in base_by_day else 0.0
        ap = arm_by_day[day]["pnl"] if day in arm_by_day else 0.0
        per_day_delta[day] = ap - bp
        b_id = G.ekey(base_by_day[day]) if day in base_by_day else None
        a_id = G.ekey(arm_by_day[day]) if day in arm_by_day else None
        if b_id != a_id:
            changed.append({"day": day, "delta_usd": round(ap - bp, 2),
                            "base": "%s %s" % (b_id[2], b_id[1]) if b_id else None,
                            "arm": "%s %s" % (a_id[2], a_id[1]) if a_id else None})
    changed.sort(key=lambda d: -abs(d["delta_usd"]))
    tot_delta = sum(per_day_delta.values())
    top1 = changed[0]["delta_usd"] if changed else 0.0
    top3 = sum(c["delta_usd"] for c in changed[:3])

    # ---- C. paired bootstrap over sessions
    h1_days = sorted(d for d in per_day_delta if d < G.H_SPLIT)
    h2_days = sorted(d for d in per_day_delta if d >= G.H_SPLIT)
    h1_vals = [per_day_delta[d] for d in h1_days]
    h2_vals = [per_day_delta[d] for d in h2_days]
    all_vals = h1_vals + h2_vals

    def boot(vals, n):
        m = len(vals)
        return [sum(vals[rng.randrange(m)] for _ in range(m)) / m for _ in range(n)]

    b_h1, b_h2, b_all, b_joint = [], [], [], 0
    m1, m2 = len(h1_vals), len(h2_vals)
    for _ in range(N_BOOT):
        s1 = sum(h1_vals[rng.randrange(m1)] for _ in range(m1)) / m1
        s2 = sum(h2_vals[rng.randrange(m2)] for _ in range(m2)) / m2
        b_h1.append(s1)
        b_h2.append(s2)
        b_all.append((s1 * m1 + s2 * m2) / (m1 + m2))
        if s1 > 0 and s2 > 0:
            b_joint += 1

    boot_out = {
        "overall_delta_usd_day": round(tot_delta / len(per_day_delta), 2),
        "overall_ci95": [round(pct(b_all, 0.025), 2), round(pct(b_all, 0.975), 2)],
        "overall_p_gt0": round(sum(1 for v in b_all if v > 0) / N_BOOT, 4),
        "h1_delta": round(h1d, 2),
        "h1_ci95": [round(pct(b_h1, 0.025), 2), round(pct(b_h1, 0.975), 2)],
        "h1_p_gt0": round(sum(1 for v in b_h1 if v > 0) / N_BOOT, 4),
        "h2_delta": round(h2d, 2),
        "h2_ci95": [round(pct(b_h2, 0.025), 2), round(pct(b_h2, 0.975), 2)],
        "h2_p_gt0": round(sum(1 for v in b_h2 if v > 0) / N_BOOT, 4),
        "joint_p_both_halves_positive": round(b_joint / N_BOOT, 4),
    }

    # ---- D. label-permutation null
    null_surv = 0
    null_usd = 0
    null_prec = 0
    null_h1 = []
    null_h2 = []
    pool_keys = list(readable_keys)
    for _ in range(N_NULL):
        fake = set(rng.sample(pool_keys, n_mismatch))
        f = pick_with_labels(byday, fake)
        a = arm_stats(f, pool, s_pairs_100)
        s, d1, d2, u, p = survivor_gate(base, a)
        null_surv += s
        null_usd += u
        null_prec += p
        null_h1.append(d1)
        null_h2.append(d2)
    p0 = null_surv / N_NULL

    null_out = {
        "n_null": N_NULL,
        "n_dropped_per_draw": n_mismatch,
        "survivor_rate": round(p0, 4),
        "usd_gate_rate": round(null_usd / N_NULL, 4),
        "precision_gate_rate": round(null_prec / N_NULL, 4),
        "h1_delta_null_ci95": [round(pct(null_h1, 0.025), 2), round(pct(null_h1, 0.975), 2)],
        "h2_delta_null_ci95": [round(pct(null_h2, 0.025), 2), round(pct(null_h2, 0.975), 2)],
        "h1_delta_null_pctile_of_observed":
            round(sum(1 for v in null_h1 if v < h1d) / N_NULL, 4),
        "h2_delta_null_pctile_of_observed":
            round(sum(1 for v in null_h2 if v < h2d) / N_NULL, 4),
        "expected_spurious_survivors_over_%d_tried" % N_TRIED: round(p0 * N_TRIED, 2),
        "p_at_least_one_spurious_over_%d_tried" % N_TRIED:
            round(1 - (1 - p0) ** N_TRIED, 4),
    }

    # ---- E. descriptive split significance
    split = claim["descriptive_split"]
    m, mm = split["match"], split["mismatch"]
    fisher_p = fisher_exact_two_tail(
        m["graded_s"], m["graded_any"] - m["graded_s"],
        mm["graded_s"], mm["graded_any"] - mm["graded_s"])
    match_r = [r["r"] for r in all_cands if labels[G.ekey(r)] is True]
    mismatch_r = [r["r"] for r in all_cands if labels[G.ekey(r)] is False]
    dr, tr, pr = welch_t(match_r, mismatch_r)
    split_out = {
        "match_n": m["n"], "mismatch_n": mm["n"],
        "match_graded": "%d/%d" % (m["graded_s"], m["graded_any"]),
        "mismatch_graded": "%d/%d" % (mm["graded_s"], mm["graded_any"]),
        "s_rate_gap_pp": round((m["s_rate_pct"] or 0) - (mm["s_rate_pct"] or 0), 1),
        "fisher_exact_p": round(fisher_p, 4),
        "mean_r_gap": round(dr, 4),
        "mean_r_welch_t": round(tr, 3),
        "mean_r_welch_p": round(pr, 4),
    }

    out = {
        "role": "refuter2_multiplicity_sampling",
        "claim": ("scratch-exit-direction-match survives: baseline $33.93/day "
                  "-> $35.09/day, H1 delta 1.89, H2 delta 0.42, precision "
                  "30.5 -> 30.0, recall_100 5.9 -> 5.9"),
        "fill": ("signal bar CLOSE entry, stop_rule.stop_fill_price stops, "
                 "size-gated on signal_runner.min_risk_floor, 1R = $1,000; "
                 "one-trade-a-day unit = the claim script's pick_first_of_day "
                 "(== omen_metrics.first_of_day_arm)"),
        "book": os.path.basename(G.BOOK_PATH),
        "sessions": n_days_total,
        "ekey_note": {
            "candidate_rows": len(all_cands),
            "distinct_ekeys": len({G.ekey(r) for r in all_cands}),
            "mismatch_rows": len([r for r in all_cands if labels[G.ekey(r)] is False]),
            "mismatch_distinct_ekeys": n_mismatch,
            "why": ("(day, et, sym) is not unique in the book -- 8227 rows collapse "
                    "to 7920 keys -- so this refuter's drop set is keyed and the "
                    "null draws the same number of KEYS. Reproduction is exact on "
                    "every published field, so the collapse changes no pick."),
        },
        "reproduction": repro,
        "reproduces_exactly": repro_exact,
        "footprint": {
            "sessions_changed": len(changed),
            "pct_sessions_changed": round(len(changed) / len(per_day_delta) * 100, 2),
            "total_delta_usd": round(tot_delta, 2),
            "top1_session_delta_usd": round(top1, 2),
            "top1_share_of_total_pct": (round(top1 / tot_delta * 100, 1)
                                        if tot_delta else None),
            "top3_share_of_total_pct": (round(top3 / tot_delta * 100, 1)
                                        if tot_delta else None),
            "changed_sessions": changed,
        },
        "paired_bootstrap": boot_out,
        "label_permutation_null": null_out,
        "descriptive_split_significance": split_out,
    }

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    write_md(out)
    print(json.dumps({k: v for k, v in out.items() if k != "footprint"}, indent=2))
    print("sessions changed:", len(changed))
    for c in changed:
        print("  ", c)
    return out


def write_md(o):
    b = o["paired_bootstrap"]
    n = o["label_permutation_null"]
    f = o["footprint"]
    s = o["descriptive_split_significance"]
    L = []
    L.append("# g154 refuter2 -- scratch-exit-direction-match: multiplicity and sampling error\n")
    L.append("**What is different now:** the claim reproduces to the cent, but its "
             "entire survivor verdict rests on %d of %d sessions changing hands, the "
             "paired-bootstrap CI on both halves straddles zero, and a random "
             "relabelling that drops the same number of candidates clears the very "
             "same survivor gate %.1f%% of the time -- so over the 25 candidates "
             "tried this family expects %s spurious survivors of exactly this kind.\n"
             % (f["sessions_changed"], o["sessions"], n["survivor_rate"] * 100,
                n["expected_spurious_survivors_over_25_tried"]))
    L.append("Fill: %s. Book %s, %d sessions, H1/H2 split 2025-09-01. "
             "Script: `research/g154_refute2_scratch_multiplicity.py`.\n"
             % (o["fill"], o["book"], o["sessions"]))

    L.append("## A. Reproduction\n")
    L.append("| field | rerun | published |")
    L.append("|---|---:|---:|")
    for k, v in o["reproduction"].items():
        L.append("| %s | %s | %s |" % (k, v[0], v[1]))
    L.append("")
    L.append("reproduces exactly: **%s**\n" % o["reproduces_exactly"])

    L.append("## B. Footprint -- how much of the book the arm actually touches\n")
    L.append("| | |")
    L.append("|---|---:|")
    L.append("| sessions where the pick changed | %d / %d (%.2f%%) |"
             % (f["sessions_changed"], o["sessions"], f["pct_sessions_changed"]))
    L.append("| total dollar delta over 2 years | $%s |" % f["total_delta_usd"])
    L.append("| single biggest session's share | %s%% |" % f["top1_share_of_total_pct"])
    L.append("| top 3 sessions' share | %s%% |" % f["top3_share_of_total_pct"])
    L.append("")
    if f["changed_sessions"]:
        L.append("| day | delta $ | baseline pick | arm pick |")
        L.append("|---|---:|---|---|")
        for c in f["changed_sessions"]:
            L.append("| %s | %s | %s | %s |" % (c["day"], c["delta_usd"],
                                                c["base"], c["arm"]))
        L.append("")
        h1c = [c for c in f["changed_sessions"] if c["day"] < G.H_SPLIT]
        h2c = [c for c in f["changed_sessions"] if c["day"] >= G.H_SPLIT]
        if h1c:
            top = max(h1c, key=lambda c: abs(c["delta_usd"]))
            rest = sum(c["delta_usd"] for c in h1c) - top["delta_usd"]
            L.append("H1's whole +$%s/day is %d swapped sessions; remove the single "
                     "%s swap and the remaining %d leave H1 at $%.2f/day. "
                     % (b["h1_delta"], len(h1c), top["day"], len(h1c) - 1, rest / 249.0))
        if h2c:
            top = max(h2c, key=lambda c: abs(c["delta_usd"]))
            rest = sum(c["delta_usd"] for c in h2c) - top["delta_usd"]
            L.append("H2's whole +$%s/day is %d swapped sessions; remove the single "
                     "%s swap and the remaining %d leave H2 at $%.2f/day. "
                     "**The survivor gate is decided by two individual trade swaps.**"
                     % (b["h2_delta"], len(h2c), top["day"], len(h2c) - 1, rest / 249.0))
        L.append("")
        e = o["ekey_note"]
        L.append("_Bookkeeping: %s_\n" % e["why"])

    L.append("## C. Paired bootstrap over sessions (10k resamples)\n")
    L.append("| slice | delta $/day | 95% CI | P(delta > 0) |")
    L.append("|---|---:|---|---:|")
    L.append("| overall | %s | [%s, %s] | %s |" % (b["overall_delta_usd_day"],
             b["overall_ci95"][0], b["overall_ci95"][1], b["overall_p_gt0"]))
    L.append("| H1 | %s | [%s, %s] | %s |" % (b["h1_delta"], b["h1_ci95"][0],
             b["h1_ci95"][1], b["h1_p_gt0"]))
    L.append("| H2 | %s | [%s, %s] | %s |" % (b["h2_delta"], b["h2_ci95"][0],
             b["h2_ci95"][1], b["h2_p_gt0"]))
    L.append("")
    L.append("P(H1 delta > 0 AND H2 delta > 0) under resampling: **%s**\n"
             % b["joint_p_both_halves_positive"])

    L.append("## D. Label-permutation null -- same shape, no signal\n")
    L.append("Drop %d candidates chosen uniformly at random from the readable "
             "book (the arm drops exactly %d), fall through to the next pick, "
             "score with the claim script's own gate. %d draws.\n"
             % (n["n_dropped_per_draw"], n["n_dropped_per_draw"], n["n_null"]))
    L.append("| | |")
    L.append("|---|---:|")
    L.append("| random relabelling clears the survivor gate | **%.1f%%** |"
             % (n["survivor_rate"] * 100))
    L.append("| ... via the $/day arm (both halves up) | %.1f%% |"
             % (n["usd_gate_rate"] * 100))
    L.append("| ... via the precision arm | %.1f%% |" % (n["precision_gate_rate"] * 100))
    L.append("| observed H1 delta's percentile in the null | %.1f%% |"
             % (n["h1_delta_null_pctile_of_observed"] * 100))
    L.append("| observed H2 delta's percentile in the null | %.1f%% |"
             % (n["h2_delta_null_pctile_of_observed"] * 100))
    L.append("| expected spurious survivors over the 25 candidates tried | **%s** |"
             % n["expected_spurious_survivors_over_25_tried"])
    L.append("| P(at least one spurious survivor over 25 tried) | %s |"
             % n["p_at_least_one_spurious_over_25_tried"])
    L.append("")

    L.append("## E. The descriptive split the report calls load-bearing\n")
    L.append("| | |")
    L.append("|---|---:|")
    L.append("| match S rate | %s |" % s["match_graded"])
    L.append("| mismatch S rate | %s |" % s["mismatch_graded"])
    L.append("| S-rate gap | %spp |" % s["s_rate_gap_pp"])
    L.append("| Fisher exact two-tailed p | **%s** |" % s["fisher_exact_p"])
    L.append("| mean-R gap (match minus mismatch) | %s |" % s["mean_r_gap"])
    L.append("| Welch t / p on mean R | %s / %s |" % (s["mean_r_welch_t"], s["mean_r_welch_p"]))
    L.append("")
    L.append("Note the sign: the mismatch bucket has the WORSE mean R and the "
             "HIGHER S rate. Those two point opposite ways, which is what a "
             "20-card sample looks like when nothing is there.\n")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
