"""g154 refuter #2 -- displacement-graded-not-boolean: multiplicity + sampling error.

Reproduces research/g154_rule_displacement-graded-not-boolean.py exactly (same
book, same picker, same disp_ratio), then asks two questions it never asked:

  1. SAMPLING ERROR. Paired bootstrap over the 498 SESSIONS (the same resampled
     days score baseline and arm, so the pairing is preserved): what is the 95%
     CI on the T=2.0 arm's $/day delta, overall and per half?
  2. MULTIPLICITY / NULL RATE. The arm's survivor gate is
     (H1 up OR precision up) AND (H2 up OR precision up) AND recall >= baseline.
     Both halves LOSE money here, so the gate reduces to "precision went up and
     recall did not fall". Feed it a PLACEBO: drop a uniformly random 67.12% of
     the judgeable candidates -- same drop rate as T=2.0, same non-droppable
     population (ratio None is kept), same picker, no information at all.
     How often does noise clear the gate?

Fill: unchanged from the claim -- signal-bar CLOSE entry, stop_rule.
stop_fill_price stops, size-gated on signal_runner.min_risk_floor,
1R = $1,000, book research/bt2y_trades_retest_on.json. H1/H2 split 2025-09-01.

    python research/g154_refute2_disp_bootstrap.py

Writes research/g154_refute2_disp_bootstrap.json. Ships nothing.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

_spec = importlib.util.spec_from_file_location(
    "g154mod", os.path.join(HERE, "g154_rule_displacement-graded-not-boolean.py"))
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)

import marks_pool  # noqa: E402

OUT_JSON = os.path.join(HERE, "g154_refute2_disp_bootstrap.json")
N_BOOT = 2000
N_PLACEBO = 1000
SEED = 20260905


def main():
    blob = json.load(open(G.BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    byday = G.by_day_candidates(rows)
    n_days_total = meta.get("sessions") or len({r["day"] for r in rows})

    ratio = {}
    for day, v in byday.items():
        for i, r in enumerate(v):
            ratio[(day, i)] = G.disp_ratio(r)

    pool = marks_pool.canonical_pool()
    s_pairs_100 = G.load_sweep_s_days()

    def pick(keep):
        """keep(day, i, ratio) -> bool. Mirrors G.pick_first_of_day exactly."""
        firsts = []
        for day in sorted(byday):
            pk = None
            for i, r in enumerate(byday[day]):
                if G._row_is_sizeable(r) is False:
                    continue
                if keep is not None and not keep(day, i, ratio[(day, i)]):
                    continue
                pk = r
                break
            if pk is not None:
                firsts.append(pk)
        return firsts

    base = pick(None)
    armT = pick(lambda d, i, f: (f is None) or (f >= G.DEFAULT_T))

    b_h1s, b_h2s = G.split_h1_h2(base)
    a_h1s, a_h2s = G.split_h1_h2(armT)
    b_h1 = G.score(b_h1s)["usd_day"]
    b_h2 = G.score(b_h2s)["usd_day"]
    chk = {
        "baseline_usd_day": G.score(base)["usd_day"],
        "arm_usd_day": G.score(armT)["usd_day"],
        "h1_delta": round(G.score(a_h1s)["usd_day"] - b_h1, 2),
        "h2_delta": round(G.score(a_h2s)["usd_day"] - b_h2, 2),
        "baseline_precision": list(G.precision(base, pool)),
        "arm_precision": list(G.precision(armT, pool)),
        "baseline_recall100": list(G.recall(base, s_pairs_100)),
        "arm_recall100": list(G.recall(armT, s_pairs_100)),
    }

    # ---------------------------------------------- paired session bootstrap
    bpnl = {r["day"]: r["pnl"] for r in base}
    apnl = {r["day"]: r["pnl"] for r in armT}
    days = sorted(set(bpnl) | set(apnl))
    h1days = [d for d in days if d < G.H_SPLIT]
    h2days = [d for d in days if d >= G.H_SPLIT]

    rnd = random.Random(SEED)

    def boot(dayset):
        out = []
        n = len(dayset)
        for _ in range(N_BOOT):
            samp = [dayset[rnd.randrange(n)] for _ in range(n)]
            b = sum(bpnl.get(d, 0.0) for d in samp) / n
            a = sum(apnl.get(d, 0.0) for d in samp) / n
            out.append(a - b)
        out.sort()
        return {
            "mean": round(sum(out) / len(out), 2),
            "lo95": round(out[int(0.025 * len(out))], 2),
            "hi95": round(out[int(0.975 * len(out))], 2),
            "p_arm_better_than_baseline": round(sum(1 for x in out if x > 0) / len(out), 4),
        }

    ci = {"all": boot(days), "H1": boot(h1days), "H2": boot(h2days)}

    # ---------------------------------------------- placebo / null pass rate
    judgeable = [k for k, f in ratio.items() if f is not None]
    drop_rate = sum(1 for k in judgeable if ratio[k] < G.DEFAULT_T) / len(judgeable)

    b_prec = chk["baseline_precision"][0]
    b_rec = chk["baseline_recall100"][0]

    prnd = random.Random(SEED + 1)
    passes = prec_up = joint = 0
    precs, recs, usds = [], [], []
    for _ in range(N_PLACEBO):
        keepset = {k for k in judgeable if prnd.random() >= drop_rate}
        f = pick(lambda d, i, fr: (fr is None) or ((d, i) in keepset))
        p = G.precision(f, pool)[0]
        rc = G.recall(f, s_pairs_100)[0]
        h1 = G.score(G.split_h1_h2(f)[0])["usd_day"]
        h2 = G.score(G.split_h1_h2(f)[1])["usd_day"]
        pi = p > b_prec
        ok = ((h1 > b_h1) or pi) and ((h2 > b_h2) or pi) and (rc >= b_rec)
        passes += bool(ok)
        prec_up += bool(pi)
        joint += bool(p >= 38.3 and rc >= 14.7)
        precs.append(p)
        recs.append(rc)
        usds.append(G.score(f)["usd_day"])
    precs.sort()
    recs.sort()
    usds.sort()

    def pctl(a, q):
        return round(a[min(len(a) - 1, int(q * len(a)))], 2)

    placebo = {
        "n": N_PLACEBO,
        "drop_rate_matched_to_T2.0": round(drop_rate, 4),
        "survivor_gate_pass_rate": round(passes / N_PLACEBO, 4),
        "precision_up_rate": round(prec_up / N_PLACEBO, 4),
        "joint_prec_ge_38.3_and_recall_ge_14.7": round(joint / N_PLACEBO, 4),
        "expected_such_hits_in_25_rules_x_4_thresholds": round(joint / N_PLACEBO * 100, 2),
        "precision_pctl": {"p05": pctl(precs, .05), "p50": pctl(precs, .5),
                           "p95": pctl(precs, .95),
                           "frac_ge_claim_38.3":
                               round(sum(1 for x in precs if x >= 38.3) / N_PLACEBO, 4)},
        "recall100_pctl": {"p05": pctl(recs, .05), "p50": pctl(recs, .5),
                           "p95": pctl(recs, .95),
                           "frac_ge_claim_14.7":
                               round(sum(1 for x in recs if x >= 14.7) / N_PLACEBO, 4)},
        "usd_day_pctl": {"p05": pctl(usds, .05), "p50": pctl(usds, .5),
                         "p95": pctl(usds, .95),
                         "frac_le_claim_-36.03":
                             round(sum(1 for x in usds if x <= -36.03) / N_PLACEBO, 4)},
    }

    # ---------------------------------------------- exact tests on the two wins
    import math

    def fisher_2x2(a, b, c, d):
        """two-sided Fisher exact p for [[a,b],[c,d]]."""
        n = a + b + c + d
        r1, r2, c1 = a + b, c + d, a + c

        def pr(x):
            return (math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1))
        p0 = pr(a)
        lo = max(0, c1 - r2)
        hi = min(r1, c1)
        return round(sum(pr(x) for x in range(lo, hi + 1) if pr(x) <= p0 + 1e-12), 4)

    bp, ap = chk["baseline_precision"], chk["arm_precision"]
    br, ar = chk["baseline_recall100"], chk["arm_recall100"]
    exact = {
        "precision_fisher_p": fisher_2x2(ap[1], ap[2] - ap[1], bp[1], bp[2] - bp[1]),
        "precision_note": "arm %d/%d vs baseline %d/%d -- S numerator identical, "
                          "only non-S graded days were removed"
                          % (ap[1], ap[2], bp[1], bp[2]),
        "recall100_fisher_p": fisher_2x2(ar[1], ar[2] - ar[1], br[1], br[2] - br[1]),
        "recall100_note": "arm %d/%d vs baseline %d/%d S cards" % (ar[1], ar[2], br[1], br[2]),
    }

    claimed = json.load(open(G.OUT_JSON, encoding="utf-8"))
    prec_arms = {t: claimed["arms"][t]["precision"] for t in claimed["arms"]}
    best_prec_T = max(prec_arms, key=lambda t: prec_arms[t]["pct"])

    out = {
        "row": "F6 refuter#2",
        "target": "g154 displacement-graded-not-boolean",
        "book": os.path.basename(G.BOOK_PATH),
        "fill": "signal-bar CLOSE entry, stop_rule.stop_fill_price stops, "
                "size-gated on signal_runner.min_risk_floor, 1R=$1,000",
        "reproduced": chk,
        "paired_session_bootstrap_usd_day_delta": ci,
        "placebo_random_drop": placebo,
        "exact_tests": exact,
        "multiplicity": {
            "thresholds_swept_in_script": claimed["thresholds_swept"],
            "headline_threshold": claimed["default_threshold"],
            "headline_is_argmax_precision_of_the_4": best_prec_T == str(claimed["default_threshold"]),
            "precision_by_threshold": {t: prec_arms[t]["pct"] for t in sorted(prec_arms)},
            "rule_candidates_in_batch": 25,
        },
        "precision_numerator": {
            "baseline_S_over_graded": "%d/%d" % (chk["baseline_precision"][1],
                                                 chk["baseline_precision"][2]),
            "arm_S_over_graded": "%d/%d" % (chk["arm_precision"][1],
                                            chk["arm_precision"][2]),
            "S_numerator_unchanged": chk["baseline_precision"][1] == chk["arm_precision"][1],
        },
        "n_days_total": n_days_total,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
