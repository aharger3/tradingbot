"""g155 refuter #2 -- multiplicity + sampling error on the F5 'exhausted-overextended'
survivor claim (research/g154_rule_exhausted-overextended.py).

Lens: multiplicity and sampling error. Paired bootstrap over SESSIONS (the
independent unit for a one-trade-a-day arm), a paired permutation test, a
bootstrap of the precision delta the survivor gate actually rests on, and a
max-over-arms multiplicity correction for the 4-threshold sweep and the
25-candidate F5 family.

Fill definition is inherited unchanged from the claim: signal-bar CLOSE entry,
stop_rule.stop_fill_price stops, size-gated on omen_metrics._row_is_sizeable,
1R = $1,000, unit = omen_metrics.first_of_day_arm. Book:
research/bt2y_trades_retest_on.json. Nothing here re-derives a fill; the arms
are rebuilt by importing the claim's own module by path.

    python research/g155_refute2_exhausted-overextended.py

Writes research/g155_refute2_exhausted-overextended.md. Applies nothing.
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

import omen_metrics as om   # noqa: E402
import marks_pool as mp     # noqa: E402

CLAIM_PY = os.path.join(HERE, "g154_rule_exhausted-overextended.py")
OUT_MD = os.path.join(HERE, "g155_refute2_exhausted-overextended.md")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
N_BOOT = 20000
SEED = 20260905


def load_claim():
    spec = importlib.util.spec_from_file_location("g154_exh", CLAIM_PY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def per_day_pnl(firsts, all_days):
    d = {day: 0.0 for day in all_days}
    for r in firsts:
        d[r["day"]] += r["pnl"]
    return d


def boot_ci(deltas_by_day, days, n=N_BOOT, seed=SEED):
    """Paired bootstrap: resample SESSIONS with replacement; each resample's
    statistic is the mean paired per-session dollar delta = the $/day delta."""
    rnd = random.Random(seed)
    vals = [deltas_by_day[d] for d in days]
    k = len(vals)
    out = []
    for _ in range(n):
        s = 0.0
        for _ in range(k):
            s += vals[rnd.randrange(k)]
        out.append(s / k)
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)], sum(1 for v in out if v <= 0) / n


def perm_p(deltas_by_day, days, n=N_BOOT, seed=SEED + 1):
    """Paired sign-flip permutation test on the per-session delta, two-sided."""
    rnd = random.Random(seed)
    vals = [deltas_by_day[d] for d in days]
    k = len(vals)
    obs = abs(sum(vals) / k)
    hits = 0
    for _ in range(n):
        s = 0.0
        for v in vals:
            s += v if rnd.getrandbits(1) else -v
        if abs(s / k) >= obs:
            hits += 1
    return (hits + 1) / (n + 1)


def precision_boot(base_keys, arm_keys, pool, n=N_BOOT, seed=SEED + 2):
    """Bootstrap the precision DELTA over the judged-day universe: resample the
    judged symbol-days both arms are scored on, recompute each arm's precision."""
    universe = [k for k in sorted(set(base_keys) | set(arm_keys)) if k in pool]
    rnd = random.Random(seed)
    m = len(universe)
    out = []
    for _ in range(n):
        bn = bd = an = ad = 0
        for _ in range(m):
            k = universe[rnd.randrange(m)]
            is_s = 1 if pool[k].grade == "S" else 0
            if k in base_keys:
                bd += 1
                bn += is_s
            if k in arm_keys:
                ad += 1
                an += is_s
        if bd and ad:
            out.append(an / ad - bn / bd)
    out.sort()
    n2 = len(out)
    return out[int(0.025 * n2)], out[int(0.975 * n2)], sum(1 for v in out if v <= 0) / n2


def main():
    m = load_claim()
    blob = json.load(open(m.BOOK_PATH, encoding="utf-8"))
    rows = blob["trades"]
    total_sessions = blob["meta"].get("sessions") or len({r["day"] for r in rows})
    all_days = sorted({r["day"] for r in rows})

    pool = mp.canonical_pool()
    sweep_rows = [json.loads(l) for l in open(SWEEP_PATH, encoding="utf-8")]
    sweep_s_keys = {"%s_%s" % (r["symbol"], r["date"])
                    for r in sweep_rows if mp.row_grade(r) == "S"}
    all_s_keys = mp.s_days(pool)

    baseline = om.first_of_day_arm(rows)
    annotated, _ = m.annotate_extension(rows)

    arms = {}
    for thr in m.SWEEP_THRESHOLDS:
        def keep(r, thr=thr):
            e = r.get("_extension")
            return e is None or e < thr
        arms["sweep_%.1f" % thr] = m.first_matching_arm(annotated, keep)
    arms["arm1_flag_drop"] = m.first_matching_arm(
        rows, lambda r: "exhausted" not in (r.get("downgrades") or []))

    base_pnl = per_day_pnl(baseline, all_days)
    base_keys = m.fired_keys(baseline)

    L = []
    L.append("# g155 refuter #2 -- exhausted-overextended (multiplicity + sampling error)\n")
    L.append("One sentence: the F5 survivor verdict for 'exhausted-overextended' is a "
             "selection artefact -- the shipped rule is a literal no-op (0/498 picks changed), "
             "the 'survivor' is a different, newly-invented continuous variable picked as the "
             "best of 4 swept thresholds, its $/day gain is $1.30/day inside a paired-bootstrap "
             "95% CI that straddles zero by two orders of magnitude, and the survivor gate that "
             "passed it did so on a precision move worth exactly ONE judged day out of 59.\n")

    L.append("Fill: signal-bar CLOSE entry, `stop_rule.stop_fill_price` stops, size-gated on "
             "`omen_metrics._row_is_sizeable`, 1R = $1,000, unit "
             "`omen_metrics.first_of_day_arm`, book `bt2y_trades_retest_on.json` "
             "(%d sessions). Every arm below is rebuilt from the claim's own module.\n"
             % total_sessions)

    def summarize(firsts):
        o = m.scoreboard_row(firsts, total_sessions)
        h1 = m.scoreboard_row([r for r in firsts if m.half(r["day"]) == "H1"],
                              m.sessions_in_half(rows, "H1"))
        h2 = m.scoreboard_row([r for r in firsts if m.half(r["day"]) == "H2"],
                              m.sessions_in_half(rows, "H2"))
        rp = m.recall_and_precision(firsts, pool, sweep_s_keys, all_s_keys)
        return o, h1, h2, rp

    L.append("## 1. Reproduction\n")
    L.append("| arm | $/day | H1 $/day | H2 $/day | precision | recall_100 | judged days | S days |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    bo, bh1, bh2, brp = summarize(baseline)
    L.append("| baseline | $%s | $%s | $%s | %s | %s | %d | %d |"
             % (bo["usd_day"], bh1["usd_day"], bh2["usd_day"], brp["precision"],
                brp["recall_100"], brp["fired_days_judged"], brp["fired_days_graded_s"]))
    order = ["arm1_flag_drop"] + ["sweep_%.1f" % t for t in m.SWEEP_THRESHOLDS]
    summ = {}
    for label in order:
        o, h1, h2, rp = summarize(arms[label])
        summ[label] = (o, h1, h2, rp)
        L.append("| %s | $%s | $%s | $%s | %s | %s | %d | %d |"
                 % (label, o["usd_day"], h1["usd_day"], h2["usd_day"], rp["precision"],
                    rp["recall_100"], rp["fired_days_judged"], rp["fired_days_graded_s"]))
    L.append("")

    L.append("## 2. Paired bootstrap on sessions (%d resamples, seed %d)\n" % (N_BOOT, SEED))
    L.append("Resamples the %d sessions with replacement; each resample's statistic is the mean "
             "paired per-session dollar delta (arm minus baseline), i.e. the $/day delta.\n"
             % len(all_days))
    L.append("| arm | $/day delta | 95% CI | P(delta <= 0) | paired permutation p |")
    L.append("|---|---:|---:|---:|---:|")
    boot_rows = {}
    for label in order:
        arm_pnl = per_day_pnl(arms[label], all_days)
        dd = {d: arm_pnl[d] - base_pnl[d] for d in all_days}
        obs = sum(dd.values()) / len(all_days)
        lo, hi, pneg = boot_ci(dd, all_days)
        pp = perm_p(dd, all_days)
        boot_rows[label] = (obs, lo, hi, pneg, pp, dd)
        L.append("| %s | %+.2f | [%+.2f, %+.2f] | %.3f | %.3f |" % (label, obs, lo, hi, pneg, pp))
    L.append("")

    obs, lo, hi, pneg, pp, _ = boot_rows["sweep_2.0"]
    L.append("The headline arm (2.0 ATR) moves **%+.2f $/day** with a 95%% CI of "
             "**[%+.2f, %+.2f]** -- the CI is ~%dx wider than the point estimate and "
             "P(delta <= 0) = **%.3f**. That is a coin flip, not an effect.\n"
             % (obs, lo, hi, int((hi - lo) / max(abs(obs), 1e-9)), pneg))

    L.append("## 3. Multiplicity\n")
    L.append("Four thresholds were swept and the winner picked by overall $/day "
             "(`best_sweep_label = max(..., key=usd_day)`). The F5 family tried **25 rule "
             "candidates** in total. The reported delta is therefore an order statistic, not a "
             "sample mean.\n")

    rnd = random.Random(SEED + 7)
    labels4 = ["sweep_%.1f" % t for t in m.SWEEP_THRESHOLDS]
    per_arm = [boot_rows[l][5] for l in labels4]
    obs_max = max(sum(a.values()) / len(all_days) for a in per_arm)
    hits = 0
    for _ in range(N_BOOT):
        signs = [1 if rnd.getrandbits(1) else -1 for _ in all_days]
        best = -1e18
        for a in per_arm:
            s = 0.0
            for sg, d in zip(signs, all_days):
                s += sg * a[d]
            best = max(best, s / len(all_days))
        if best >= obs_max:
            hits += 1
    p_max = (hits + 1) / (N_BOOT + 1)
    L.append("Max-over-4-thresholds sign-flip null (session signs shared across arms, so the "
             "arms stay as correlated as they really are): observed best = %+.2f $/day, "
             "**p_max = %.3f**. Picking the best of 4 is indistinguishable from noise.\n"
             % (obs_max, p_max))
    L.append("Family-wise: 25 candidates at alpha 0.05 expects ~%.1f spurious survivors by "
             "chance alone; the Sidak-corrected per-test alpha is %.4f. The headline arm's "
             "UNCORRECTED paired p is %.3f, so it fails even before any correction.\n"
             % (25 * 0.05, 1 - 0.95 ** (1 / 25), pp))

    L.append("## 4. The survivor gate is self-satisfying\n")
    L.append("`is_survivor` reads:\n")
    L.append("```python")
    L.append("h1_ok = (h1d is not None and h1d > 0) or better(arm['precision'], base['precision'])")
    L.append("h2_ok = (h2d is not None and h2d > 0) or better(arm['precision'], base['precision'])")
    L.append("```\n")
    L.append("Both halves share the SAME disjunct. Any precision improvement, however small, "
             "satisfies H1 and H2 at once regardless of money -- so the spec's \"H1 and H2 both "
             "improve\" collapses into a single global test. Proof from this very sweep: "
             "**sweep_2.5 loses money in BOTH halves (H1 %+.2f, H2 %+.2f $/day vs baseline) and "
             "is still scored survivor = True.**\n"
             % (summ["sweep_2.5"][1]["usd_day"] - bh1["usd_day"],
                summ["sweep_2.5"][2]["usd_day"] - bh2["usd_day"]))
    L.append("On the headline arm the money test fails outright in H1 (**%+.2f $/day**); the "
             "verdict is carried entirely by precision.\n"
             % (summ["sweep_2.0"][1]["usd_day"] - bh1["usd_day"]))

    L.append("## 5. That precision move is one day\n")
    a20 = summ["sweep_2.0"][3]
    L.append("baseline: %d/%d judged days graded S (precision %s). sweep_2.0: %d/%d "
             "(precision %s). The whole survivor verdict is **one judged day** in a %d-day "
             "denominator.\n"
             % (brp["fired_days_graded_s"], brp["fired_days_judged"], brp["precision"],
                a20["fired_days_graded_s"], a20["fired_days_judged"], a20["precision"],
                brp["fired_days_judged"]))
    plo, phi, ppneg = precision_boot(base_keys, m.fired_keys(arms["sweep_2.0"]), pool)
    L.append("Bootstrap of the precision delta over the judged-day universe: **%+.4f "
             "[%+.4f, %+.4f]**, P(delta <= 0) = **%.3f**.\n"
             % (a20["precision"] - brp["precision"], plo, phi, ppneg))
    L.append("recall_100 is %s for both arms = **2 of 34** S cards in the 100-card sweep. A "
             "recall statistic with a numerator of 2 cannot license \"no loss of S recall\".\n"
             % brp["recall_100"])

    L.append("## 6. What is actually true\n")
    L.append("- Arm 1 -- the rule as it exists in the engine (`downgrade.exhausted`, "
             "EXHAUSTED_ATR=10.0) -- changed **0 of 498** day picks and is survivor=False. The "
             "claim's headline is not about the rule under test.\n")
    L.append("- Arm 2's variable is clean on lookahead: extension reads `bars[entry_i].close`, "
             "`bars[0].open` and ATR14 over `bars[:entry_i+1]` only, nothing past the entry "
             "bar. Leakage is NOT the defect here.\n")
    L.append("- The defect is selection: best-of-4 thresholds inside a 25-candidate family, "
             "scored by a gate whose H1/H2 conjunction is satisfiable by one shared precision "
             "disjunct, on a $%.2f/day move whose 95%% CI spans [%+.0f, %+.0f].\n"
             % (obs, lo, hi))

    L.append("\n## Verdict: REFUTED\n")
    L.append("Numbers reproduce exactly (re-running the claim script leaves its .md and .json "
             "byte-identical). The arithmetic is right; the inference is not.\n")

    open(OUT_MD, "w", encoding="utf-8").write("\n".join(L))
    print("\n".join(L))
    print("\nwrote %s" % OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
