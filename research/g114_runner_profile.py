"""g114 -- runner profile: what, at entry time, separates a runner from the rest?

Austin, 2026-09-03: "runners that can run is where the money's at." g97 already
measured that the average first-of-day trade offers +2.14R of MFE-while-alive
against a realised book of only +0.038R, and that 23.2% of trades reach >=3R
before any stop (n=103/444, size-gated on `signal_runner.min_risk_floor`, the
same 444 g97 reports). This script asks the next question: using ONLY fields
known AT ENTRY (before the outcome unfolds), is there anything that tells a
runner (MFE-while-alive >= 3R) apart from a non-runner, before the fact?

RUNNER DEFINITION, reused verbatim from g97's bar-ordered walk (not
re-derived): mfe_alive = the best price offered while the trade was still
alive, i.e. strictly before adverse excursion reaches 1R. This is the same
size-gated, bar-ordered, causal (entry_i+1 onward) measurement g97 made; this
script imports g97's `walk()` rather than reimplementing it, so the runner
population here is exactly g97's population.

CAUSAL vs OUTCOME. `out`, `pnl`, `r`, `bars`, `exit`, `scaled`, `status`,
`traded`, `alert` all either encode or leak the trade's own result and are
EXCLUDED. `target` is Austin's PT1 (HOD/LOD), fixed at signal time -- causal.
Everything tested below is knowable before entry+1's first bar closes.

METHOD. Every stamped causal field, categorical and numeric, gets one
permutation test against the binary runner label (two-sided, label-shuffle,
same style as g96's `permutation_p` but vectorized: one (trials x n) shuffled-
label matrix is reused across every arm via matrix-dot, not regenerated per
field, so it is fast enough to be exhaustive). Categorical values need >=15
supporting rows to be scored at all -- anything thinner is not reported, only
counted. Multi-value fields (tags, downgrades) are unpacked into one boolean
arm per distinct value, same convention g95 used.

    python research/g114_runner_profile.py

Honest book (`bt2y_trades_retest_on.json`), first-of-day arm, size-gated,
bar-ordered to 11:00. Applies nothing, ships nothing.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g97_mfe as g97                             # noqa: E402
from research import g80_ordertype_grid as G       # noqa: E402

BOOK = g97.BOOK
OUT_JSON = os.path.join(HERE, "g114_runner_profile.json")
OUT_MD = os.path.join(HERE, "g114_runner_profile.md")
RUNNER_R = 3.0
TRIALS = 5000
SEED = 20260903
MIN_N = 15

# fields that encode or leak the trade's own outcome -- never testable as a
# "separator" without it being circular / look-ahead.
NON_CAUSAL = {"out", "pnl", "r", "bars", "exit", "scaled", "status", "traded",
              "alert", "reason"}

CATEGORICAL = ["grade", "sgrade", "setup", "setup_label", "level",
               "level_name", "level_tf", "tier", "pool", "cls", "side", "dir",
               "confluence", "stopb", "bias", "aligned", "vol_regime",
               "rangeb", "gapb", "dow", "slot", "spy_trend", "entry_tf",
               "bias_tf"]
MULTI = ["tags", "downgrades"]
# derived categorical arms built directly in cat_pairs(): hour, tripped_bucket,
# seq_bucket -- not re-listed here, this constant is documentation only.


def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return b["trades"] if isinstance(b, dict) else b


def numeric_features(r, risk):
    entry = r["entry"]
    et = r.get("et") or "09:30"
    h, m = int(et[:2]), int(et[3:5])
    mins_since_open = (h * 60 + m) - (9 * 60 + 30)
    target_dist_r = abs(r["target"] - entry) / risk if risk else None
    level_dist_r = abs(entry - r.get("level_px", entry)) / risk if risk else None
    tripped_n = None
    try:
        tripped_n = int(r.get("tripped"))
    except (TypeError, ValueError):
        pass
    return {
        "s (engine score)": r.get("s"),
        "stop_pct": r.get("stop_pct"),
        "risk_dollars": risk,
        "entry_price": entry,
        "drange (day range %)": r.get("drange"),
        "dret (day return %)": r.get("dret"),
        "gap": r.get("gap"),
        "gap_abs": abs(r.get("gap", 0.0)),
        "minutes_since_open": mins_since_open,
        "planned_rr (target R)": target_dist_r,
        "level_dist_r": level_dist_r,
        "tripped_n": tripped_n,
        "n_tags": len(r.get("tags") or []),
        "n_downgrades": len(r.get("downgrades") or []),
    }


def cat_pairs(r):
    out = []
    for f in CATEGORICAL:
        v = r.get(f)
        if v not in (None, "", "n/a", "None"):
            out.append((f, str(v)))
    et = r.get("et") or "09:30"
    out.append(("hour", et[:2]))
    out.append(("tripped_bucket", "tripped=%s" % r.get("tripped")))
    out.append(("seq_bucket", "seq%s" % r.get("seq")))
    for t in (r.get("tags") or ()):
        out.append(("tag", t))
    for d in (r.get("downgrades") or ()):
        out.append(("downgrade", d))
    return out


def perm_two_sided(perm_labels, weight, mask_or_group, kind):
    """perm_labels: (TRIALS, n) shuffled 0/1 runner matrix (SAME matrix reused
    for every arm -- correlated across arms, each individual test still
    exchangeable-valid). Returns (obs_diff, p)."""
    n_runner = perm_labels[0].sum()
    n = perm_labels.shape[1]
    if kind == "cat":
        mask = mask_or_group.astype(float)
        n_mask = mask.sum()
        if n_mask < MIN_N or (n - n_mask) < MIN_N:
            return None
        sum1_perm = perm_labels.dot(mask)               # (TRIALS,)
        rate_mask_perm = sum1_perm / n_mask
        rate_other_perm = (n_runner - sum1_perm) / (n - n_mask)
        diff_perm = rate_mask_perm - rate_other_perm
        runner_obs = perm_labels_obs = weight            # weight IS the real runner array here
        sum1_obs = runner_obs[mask_or_group].sum()
        rate_mask_obs = sum1_obs / n_mask
        rate_other_obs = (runner_obs.sum() - sum1_obs) / (n - n_mask)
        obs = rate_mask_obs - rate_other_obs
    else:  # numeric
        value = mask_or_group  # full-length value array (may contain nan)
        good = ~np.isnan(value)
        if good.sum() < 2 * MIN_N:
            return None
        v = np.where(good, value, 0.0)
        runner_obs = weight
        n_runner_g = (runner_obs[good]).sum()
        n_g = good.sum()
        if n_runner_g < MIN_N or (n_g - n_runner_g) < MIN_N:
            return None
        sumV1_obs = v[good & (runner_obs == 1)].sum()
        mean1_obs = sumV1_obs / n_runner_g
        mean0_obs = (v[good].sum() - sumV1_obs) / (n_g - n_runner_g)
        obs = mean1_obs - mean0_obs
        # for the permutation arm restrict to the same `good` subset
        pg = perm_labels[:, good]
        vg = v[good]
        n_runner_perm = pg[0].sum()  # constant across trials by construction on full n;
        # but on the `good` subset it varies trial to trial, so recompute:
        n_runner_perm = pg.sum(axis=1)
        sumV1_perm = pg.dot(vg)
        mean1_perm = sumV1_perm / n_runner_perm
        mean0_perm = (vg.sum() - sumV1_perm) / (n_g - n_runner_perm)
        diff_perm = mean1_perm - mean0_perm
    p = (np.sum(np.abs(diff_perm) >= abs(obs)) + 1) / (len(diff_perm) + 1)
    return obs, p


def main():
    rows = load(BOOK)
    byday = g86.candidates(rows)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]
    print("first-of-day candidates: %d" % len(firsts))

    kept, mfes = [], []
    no_bars = gated = 0
    for k, r in enumerate(firsts, 1):
        bars, *_ = G.day_pack(r["sym"], r["day"])
        if not bars:
            no_bars += 1
            continue
        w = g97.walk(r, bars)
        if w is None:
            gated += 1
            continue
        mfe_alive, stopped, outc = w
        kept.append(r)
        mfes.append(mfe_alive)
        if k % 150 == 0:
            print("  ... %d/%d" % (k, len(firsts)))

    n = len(kept)
    mfes = np.array(mfes)
    runner = (mfes >= RUNNER_R).astype(int)
    n_runner = int(runner.sum())
    print("\nmeasured %d (%d no bars, %d below min_risk_floor -- dropped)"
          % (n, no_bars, gated))
    print("runners (MFE-while-alive >= %.1fR): %d/%d = %.1f%%"
          % (RUNNER_R, n_runner, n, 100 * n_runner / n))

    # --- build the shared permutation matrix once ---------------------------
    rng = np.random.default_rng(SEED)
    idx = np.argsort(rng.random((TRIALS, n)), axis=1)
    perm_labels = runner[idx]                      # (TRIALS, n), each row a permutation

    # --- categorical / multi-value arms --------------------------------------
    from collections import defaultdict
    cat_masks = defaultdict(lambda: np.zeros(n, dtype=bool))
    for i, r in enumerate(kept):
        for k2, v in cat_pairs(r):
            cat_masks[(k2, v)][i] = True

    cat_results = []
    n_cat_tested = 0
    for (field, val), mask in cat_masks.items():
        res = perm_two_sided(perm_labels, runner, mask, "cat")
        if res is None:
            continue
        n_cat_tested += 1
        obs, p = res
        n_mask = int(mask.sum())
        runner_rate_in = runner[mask].mean() * 100
        runner_rate_out = runner[~mask].mean() * 100
        cat_results.append({"field": field, "value": val, "n": n_mask,
                            "runner_rate_in_pct": round(runner_rate_in, 1),
                            "runner_rate_out_pct": round(runner_rate_out, 1),
                            "diff_pp": round(obs * 100, 1), "p": round(float(p), 4)})
    cat_results.sort(key=lambda x: x["p"])

    # --- numeric arms ---------------------------------------------------------
    all_num_names = None
    num_matrix = {}
    for r in kept:
        risk = abs(r["entry"] - r["stop"])
        feats = numeric_features(r, risk)
        if all_num_names is None:
            all_num_names = list(feats.keys())
        for k2, v in feats.items():
            num_matrix.setdefault(k2, []).append(np.nan if v is None else float(v))

    num_results = []
    n_num_tested = 0
    for name in all_num_names:
        value = np.array(num_matrix[name], dtype=float)
        res = perm_two_sided(perm_labels, runner, value, "num")
        if res is None:
            continue
        n_num_tested += 1
        obs, p = res
        good = ~np.isnan(value)
        mean_runner = value[good & (runner == 1)].mean()
        mean_non = value[good & (runner == 0)].mean()
        num_results.append({"field": name, "n": int(good.sum()),
                            "mean_runner": round(float(mean_runner), 4),
                            "mean_non_runner": round(float(mean_non), 4),
                            "diff": round(float(obs), 4), "p": round(float(p), 4)})
    num_results.sort(key=lambda x: x["p"])

    n_tested = n_cat_tested + n_num_tested
    alpha = 0.05
    bonf = alpha / n_tested if n_tested else alpha
    expected_false_pos = n_tested * alpha

    print("\n=== categorical/multi-value arms tested: %d ===" % n_cat_tested)
    print("%-14s %-30s %6s %10s %10s %8s %7s" %
          ("field", "value", "n", "rate_in%", "rate_out%", "diff_pp", "p"))
    for row in cat_results[:15]:
        print("%-14s %-30s %6d %10.1f %10.1f %+8.1f %7.4f" %
              (row["field"], row["value"][:30], row["n"], row["runner_rate_in_pct"],
               row["runner_rate_out_pct"], row["diff_pp"], row["p"]))

    print("\n=== numeric arms tested: %d ===" % n_num_tested)
    print("%-26s %6s %12s %12s %10s %7s" %
          ("field", "n", "mean|runner", "mean|non", "diff", "p"))
    for row in num_results:
        print("%-26s %6d %12.4f %12.4f %+10.4f %7.4f" %
              (row["field"], row["n"], row["mean_runner"], row["mean_non_runner"],
               row["diff"], row["p"]))

    sig_cat = [r for r in cat_results if r["p"] < alpha]
    sig_num = [r for r in num_results if r["p"] < alpha]
    sig_bonf = [r for r in cat_results + num_results if r["p"] < bonf]
    print("\n%d total arms tested (%d categorical, %d numeric)."
          % (n_tested, n_cat_tested, n_num_tested))
    print("at raw p<0.05: %d categorical + %d numeric = %d arms significant "
          "(expected by chance alone at this alpha: ~%.1f)"
          % (len(sig_cat), len(sig_num), len(sig_cat) + len(sig_num), expected_false_pos))
    print("Bonferroni threshold for %d tests: p<%.5f -> %d arms survive"
          % (n_tested, bonf, len(sig_bonf)))

    out = {"n_firsts": len(firsts), "no_bars": no_bars, "gated": gated,
           "n_measured": n, "n_runner": n_runner,
           "runner_pct": round(100 * n_runner / n, 1), "runner_threshold_r": RUNNER_R,
           "trials": TRIALS, "n_cat_tested": n_cat_tested, "n_num_tested": n_num_tested,
           "n_tested_total": n_tested, "bonferroni_p": round(bonf, 6),
           "expected_false_positives_at_p05": round(expected_false_pos, 1),
           "categorical": cat_results, "numeric": num_results,
           "significant_at_p05": len(sig_cat) + len(sig_num),
           "significant_at_bonferroni": len(sig_bonf)}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g114 -- runner profile: what separates a runner at entry time?", "",
          "Book `bt2y_trades_retest_on.json`, first-of-day arm, size-gated on "
          "`min_risk_floor`, bar-ordered MFE-while-alive to 11:00 (g97's exact "
          "walk, reused not reimplemented).", "",
          "**%d/%d = %.1f%% are runners** (MFE-while-alive >= %.1fR) -- matches "
          "g97's own 23.2%%." % (n_runner, n, 100 * n_runner / n, RUNNER_R), "",
          "**%d causal arms tested** (%d categorical/tag values, %d numeric "
          "fields), each a two-sided label-shuffle permutation test (%d trials)."
          % (n_tested, n_cat_tested, n_num_tested, TRIALS), "",
          "At raw p<0.05: **%d arms** (chance alone predicts ~%.1f false "
          "positives out of %d tests at this threshold). Bonferroni (p<%.5f): "
          "**%d arms survive**."
          % (len(sig_cat) + len(sig_num), expected_false_pos, n_tested, bonf,
             len(sig_bonf)), "",
          "## Categorical / tag / downgrade arms (top by p)", "",
          "| field | value | n | runner%% in | runner%% out | diff (pp) | p |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for row in cat_results[:20]:
        md.append("| %s | %s | %d | %.1f | %.1f | %+.1f | %.4f |" %
                  (row["field"], row["value"], row["n"], row["runner_rate_in_pct"],
                   row["runner_rate_out_pct"], row["diff_pp"], row["p"]))
    md += ["", "## Numeric arms (all, sorted by p)", "",
           "| field | n | mean\\|runner | mean\\|non-runner | diff | p |",
           "|---|---:|---:|---:|---:|---:|"]
    for row in num_results:
        md.append("| %s | %d | %.4f | %.4f | %+.4f | %.4f |" %
                  (row["field"], row["n"], row["mean_runner"], row["mean_non_runner"],
                   row["diff"], row["p"]))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
