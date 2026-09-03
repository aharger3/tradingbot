"""G71/samplesize -- how many graded cards the recall gate actually needs.

Pure-stdlib (no scipy on this box): exact binomial tails via math.comb, normal
quantiles via bisection on math.erf.

Four questions, all at alpha = 0.05 two-sided:

  Q1  n to DISTINGUISH 52.9% from the 90% gate  -- one-sample exact binomial
      test of H0: recall = 0.90 when the truth is 0.529. Reported as (a) the
      smallest n at which the point estimate 0.529 already rejects 0.90, and
      (b) the n that gives 80% / 90% POWER, which is the honest number.
  Q2  n to DETECT A 10-POINT CHANGE, unpaired -- two independent proportions
      0.529 vs 0.629, per arm.
  Q3  n to DETECT A 10-POINT CHANGE, PAIRED (McNemar) -- the design this repo
      actually runs: the same cards replayed under two engine configs. Sample
      size falls out of the DISCORDANT pair rate, so it is tabulated over it.
  Q4  the precision curve -- Wilson 95% CI half-width on a 52.9% recall as n
      grows, i.e. how wide the number we steer by is at n=34.

Every n_S is also converted to GRADED CARDS at two S base rates:
  0.340 -- the 100-card blind sweep (34 of 100 came back S)
  0.253 -- the whole judged corpus (287 S of 1,133 Austin-graded symbol-days,
           research/g71_samplesize_corpus_audit.py)

Usage: python research/g71_samplesize_power.py --out research/g71_samplesize_power.json
"""
from __future__ import annotations
import argparse, json, math, os

ALPHA = 0.05
BASE_RATES = {"blind_sweep_0.340": 0.34, "corpus_0.253": 0.2533}


def z(p):
    """Inverse standard normal CDF by bisection on erf."""
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


Z_A2 = z(1 - ALPHA / 2)          # 1.95996


def binom_pmf(k, n, p):
    if p <= 0:
        return 1.0 if k == 0 else 0.0
    if p >= 1:
        return 1.0 if k == n else 0.0
    return math.comb(n, k) * p ** k * (1 - p) ** (n - k)


def binom_cdf(k, n, p):
    return sum(binom_pmf(i, n, p) for i in range(0, k + 1))


def exact_lower_crit(n, p0, alpha=ALPHA):
    """Largest k with P(X <= k | p0) <= alpha/2 -- the low-tail rejection region
    of a two-sided exact binomial test of H0: p = p0."""
    k = -1
    for i in range(0, n + 1):
        if binom_cdf(i, n, p0) <= alpha / 2:
            k = i
        else:
            break
    return k


def power_one_sample(n, p0, p1, alpha=ALPHA):
    """Prob of rejecting H0: p=p0 (low tail) when truth is p1, exact binomial."""
    k = exact_lower_crit(n, p0, alpha)
    if k < 0:
        return 0.0
    return binom_cdf(k, n, p1)


def wilson(k, n, alpha=ALPHA):
    if n == 0:
        return (0.0, 1.0)
    zz = Z_A2
    ph = k / n
    d = 1 + zz * zz / n
    c = (ph + zz * zz / (2 * n)) / d
    h = zz * math.sqrt(ph * (1 - ph) / n + zz * zz / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def n_two_prop(p1, p2, power=0.80, alpha=ALPHA):
    """Per-arm n, independent two-proportion, two-sided (pooled-variance form)."""
    zb = z(power)
    pbar = (p1 + p2) / 2
    num = (Z_A2 * math.sqrt(2 * pbar * (1 - pbar))
           + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return math.ceil(num / (p1 - p2) ** 2)


def n_mcnemar(psi, delta, power=0.80, alpha=ALPHA):
    """Paired n. psi = P(discordant pair); delta = p1 - p2 (the recall change)."""
    if psi <= abs(delta):
        return None
    p10 = (psi + delta) / 2
    p01 = (psi - delta) / 2
    zb = z(power)
    num = (Z_A2 * math.sqrt(psi) + zb * math.sqrt(psi - delta ** 2)) ** 2
    return math.ceil(num / delta ** 2), round(p10, 4), round(p01, 4)


def pw_two(n, p1, p2):
    """Power of a two-sided two-proportion z-test with n per arm."""
    pbar = (p1 + p2) / 2
    se0 = math.sqrt(2 * pbar * (1 - pbar) / n)
    se1 = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n)
    zc = Z_A2 * se0
    d = abs(p1 - p2)
    return 1 - 0.5 * (1 + math.erf(((zc - d) / se1) / math.sqrt(2)))


def pw_mcnemar(n, psi, delta):
    if psi <= abs(delta):
        return 0.0
    num = math.sqrt(n) * delta - Z_A2 * math.sqrt(psi)
    den = math.sqrt(psi - delta ** 2)
    return 0.5 * (1 + math.erf((num / den) / math.sqrt(2)))


def cards(n_s):
    return {k: math.ceil(n_s / v) for k, v in BASE_RATES.items()}


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--out", default=os.path.join(here, "g71_samplesize_power.json"))
    a = ap.parse_args()
    OBS, GATE = 0.529, 0.90
    out = {}

    # ---- Q1 ---------------------------------------------------------------
    n_point = None
    for n in range(2, 600):
        k = round(OBS * n)
        if binom_cdf(k, n, GATE) <= ALPHA / 2:
            n_point = n
            break
    n_pow = {}
    for pw in (0.80, 0.90, 0.95):
        for n in range(2, 600):
            if power_one_sample(n, GATE, OBS) >= pw:
                n_pow[str(pw)] = {"n_S": n, "graded_cards": cards(n)}
                break
    out["Q1_distinguish_52.9_from_90"] = {
        "H0": GATE, "truth": OBS, "alpha": ALPHA,
        "test": "exact binomial, two-sided",
        "n_S_where_point_estimate_rejects": {
            "n_S": n_point, "graded_cards": cards(n_point)},
        "n_S_for_power": n_pow,
        "at_n_S_34": {
            "observed_k": 18, "recall": round(18 / 34, 4),
            "wilson95": [round(x, 4) for x in wilson(18, 34)],
            "p_value_vs_0.90": binom_cdf(18, 34, GATE) * 2,
            "power_to_reject_0.90": round(power_one_sample(34, GATE, OBS), 4),
        },
    }

    # ---- Q2 ---------------------------------------------------------------
    q2 = {}
    for pw in (0.80, 0.90):
        n = n_two_prop(0.529, 0.629, pw)
        q2[str(pw)] = {"n_S_per_arm": n, "graded_cards_per_arm": cards(n),
                       "total_graded_cards_both_arms":
                           {k: 2 * v for k, v in cards(n).items()}}
    q2["by_delta_power80_n_S_per_arm"] = {
        "%dpt" % round(d * 100): n_two_prop(0.529, 0.529 + d, 0.80)
        for d in (0.05, 0.10, 0.15, 0.20, 0.25, 0.371)}
    out["Q2_detect_10pt_change_unpaired"] = q2

    # ---- Q3 ---------------------------------------------------------------
    q3 = {}
    for psi in (0.12, 0.15, 0.20, 0.30, 0.40, 0.50):
        r = n_mcnemar(psi, 0.10, 0.80)
        if r:
            n, p10, p01 = r
            q3["discordance_%.2f" % psi] = {"n_S": n, "p10": p10, "p01": p01,
                                            "graded_cards": cards(n)}
    out["Q3_detect_10pt_change_paired_mcnemar"] = {
        "note": "same cards, two engine configs; n falls as discordance falls",
        "power": 0.80, "delta": 0.10, "by_discordance": q3}

    # ---- Q4 ---------------------------------------------------------------
    curve = []
    for n in (17, 25, 34, 50, 75, 100, 150, 200, 278, 287, 400, 500):
        lo, hi = wilson(round(OBS * n), n)
        curve.append({
            "n_S": n,
            "graded_cards_corpus_rate": math.ceil(n / BASE_RATES["corpus_0.253"]),
            "wilson95_lo": round(lo, 3), "wilson95_hi": round(hi, 3),
            "ci_halfwidth_pts": round((hi - lo) / 2 * 100, 1),
            "power_vs_gate_0.90": round(power_one_sample(n, GATE, OBS), 3),
            "power_10pt_unpaired": round(pw_two(n, 0.529, 0.629), 3),
            "power_10pt_paired_psi0.30": round(pw_mcnemar(n, 0.30, 0.10), 3),
        })
    out["Q4_curve"] = curve

    print(json.dumps(out, indent=2))
    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=2)
    print("wrote " + a.out)


if __name__ == "__main__":
    main()
