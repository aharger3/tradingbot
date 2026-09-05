"""g156 refuter #2 -- multiplicity and sampling error on the S classifier v0 headline.

Lens: multiplicity (how many arms were tried before this one was picked) and
sampling error (paired bootstrap over the 498 sessions).

Claim under test (research/g156_s_classifier_v0.md, row F7):
  baseline $33.93/day -> v0 $47.44/day (+$13.51), H1 +$8.56, H2 +$18.46,
  precision flat 30.5%, bar-backed S recall 49.0% -> 48.7%.

Reproduces the arm exactly from research/g154_rule_or-break-without-retest.py's
own functions, then adds:
  1. construct check -- baseline picks identical to omen_metrics.first_of_day_arm
  2. how many of 498 sessions actually change hands, and delta concentration
  3. paired bootstrap over sessions on the daily delta (whole book, H1, H2)
  4. placebo -- random drop of the same number of stream rows, same positional
     exposure; how often does a null drop clear (a) delta >= +13.51 whole-book
     and (b) BOTH halves positive, the exact criterion F7's forward selection used
  5. multiplicity -- expected best-of-25 under that null

Fill: entry = signal bar CLOSE, stops via stop_rule.stop_fill_price, size-gated
on signal_runner.min_risk_floor, 1R = $1,000, book research/bt2y_trades_retest_on.json.

    python research/g156_refute2_multiplicity.py
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import omen_metrics as om  # noqa: E402

g154 = __import__("g154_rule_or-break-without-retest".replace("-", "_")) if False else None

# import the arm module by path (its filename has hyphens)
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "g154arm", os.path.join(HERE, "g154_rule_or-break-without-retest.py"))
g154 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g154)

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
SPLIT = "2025-09-01"
N_BOOT = 20000
N_PLACEBO = 2000
SEED = 20260905


def daily(picks, all_days):
    d = {day: 0.0 for day in all_days}
    for r in picks:
        d[r["day"]] += r["pnl"]
    return d


def usd_day(dmap, days):
    return sum(dmap[d] for d in days) / len(days)


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    rows = blob["trades"]
    all_days = sorted({r["day"] for r in rows})
    h1 = [d for d in all_days if d < SPLIT]
    h2 = [d for d in all_days if d >= SPLIT]

    base_picks_ref = om.first_of_day_arm(rows, size_gate=True)
    base_picks = g154.candidate_arm(rows, lambda r: False)
    arm_picks = g154.candidate_arm(rows, g154.drop_or_specific)

    ref_key = {(r["day"], r["et"], r["sym"]) for r in base_picks_ref}
    loc_key = {(r["day"], r["et"], r["sym"]) for r in base_picks}
    construct_ok = ref_key == loc_key

    bd = daily(base_picks, all_days)
    ad = daily(arm_picks, all_days)
    delta = {d: ad[d] - bd[d] for d in all_days}

    changed = [d for d in all_days if abs(delta[d]) > 1e-9]
    dsorted = sorted(changed, key=lambda d: -abs(delta[d]))
    tot_delta = sum(delta.values())

    print("== reproduce ==")
    print("construct check (local baseline == omen_metrics.first_of_day_arm):", construct_ok)
    print("baseline $/day %.2f   arm $/day %.2f   delta %.2f"
          % (usd_day(bd, all_days), usd_day(ad, all_days),
             usd_day(ad, all_days) - usd_day(bd, all_days)))
    print("H1 delta %.2f   H2 delta %.2f"
          % (usd_day(ad, h1) - usd_day(bd, h1), usd_day(ad, h2) - usd_day(bd, h2)))

    print("\n== how much of the book actually moves ==")
    print("sessions changed: %d of %d (%.2f%%)"
          % (len(changed), len(all_days), 100.0 * len(changed) / len(all_days)))
    print("total delta $%.0f" % tot_delta)
    for k in (1, 3, 5):
        top = sum(delta[d] for d in dsorted[:k])
        print("  top %d session(s) carry $%.0f = %.1f%% of total delta"
              % (k, top, 100.0 * top / tot_delta if tot_delta else 0.0))
    for d in dsorted[:6]:
        print("   %s  %+9.0f" % (d, delta[d]))

    # ---- paired bootstrap over sessions
    rnd = random.Random(SEED)
    dv_all = [delta[d] for d in all_days]
    dv_h1 = [delta[d] for d in h1]
    dv_h2 = [delta[d] for d in h2]

    def boot(vals, n=N_BOOT):
        k = len(vals)
        out = []
        for _ in range(n):
            out.append(sum(vals[rnd.randrange(k)] for _ in range(k)) / k)
        out.sort()
        return out

    print("\n== paired bootstrap over sessions (%d resamples) ==" % N_BOOT)
    both_pos = 0
    b_all = boot(dv_all)
    b_h1 = boot(dv_h1)
    b_h2 = boot(dv_h2)
    for name, b in (("whole book", b_all), ("H1", b_h1), ("H2", b_h2)):
        lo = b[int(0.025 * len(b))]
        hi = b[int(0.975 * len(b))]
        p_le0 = sum(1 for v in b if v <= 0) / len(b)
        print("  %-11s mean %+7.2f  95%% CI [%+8.2f, %+8.2f]  P(delta<=0) = %.3f"
              % (name, statistics.fmean(b), lo, hi, p_le0))
    # joint: resample sessions once, evaluate both halves
    for _ in range(N_BOOT):
        a = sum(dv_h1[rnd.randrange(len(dv_h1))] for _ in range(len(dv_h1)))
        b = sum(dv_h2[rnd.randrange(len(dv_h2))] for _ in range(len(dv_h2)))
        if a > 0 and b > 0:
            both_pos += 1
    print("  P(BOTH halves positive | resampled sessions) = %.3f" % (both_pos / N_BOOT))

    # ---- placebo: random drop of the same size from the same stream
    stream = g154._candidate_stream(rows)
    sizeable_by_day = {}
    for day, v in stream.items():
        sizeable_by_day[day] = [r for r in v if om._row_is_sizeable(r) is not False]
    n_drop = sum(1 for day, v in sizeable_by_day.items()
                 for r in v if g154.drop_or_specific(r))
    n_size = sum(len(v) for v in sizeable_by_day.values())
    rate = n_drop / n_size
    print("\n== placebo: random drop at the arm's own rate ==")
    print("arm drops %d of %d sizeable stream rows (%.3f%%)" % (n_drop, n_size, 100 * rate))

    obs_all = usd_day(ad, all_days) - usd_day(bd, all_days)
    obs_h1 = usd_day(ad, h1) - usd_day(bd, h1)
    obs_h2 = usd_day(ad, h2) - usd_day(bd, h2)

    rnd2 = random.Random(SEED + 1)
    flat = [(day, i) for day, v in sizeable_by_day.items() for i in range(len(v))]
    ge_obs = 0
    both_pos_pl = 0
    pl_deltas = []
    for _ in range(N_PLACEBO):
        dropped = set(rnd2.sample(flat, n_drop))
        pd_ = {}
        for day, v in sizeable_by_day.items():
            pick = None
            for i, r in enumerate(v):
                if (day, i) in dropped:
                    continue
                pick = r
                break
            pd_[day] = pick["pnl"] if pick is not None else 0.0
        da = sum(pd_[d] - bd[d] for d in all_days) / len(all_days)
        d1 = sum(pd_[d] - bd[d] for d in h1) / len(h1)
        d2 = sum(pd_[d] - bd[d] for d in h2) / len(h2)
        pl_deltas.append(da)
        if da >= obs_all:
            ge_obs += 1
        if d1 > 0 and d2 > 0:
            both_pos_pl += 1
    pl_deltas.sort()
    print("placebo (%d draws): P(delta >= observed %+0.2f) = %.3f"
          % (N_PLACEBO, obs_all, ge_obs / N_PLACEBO))
    print("placebo P(BOTH halves positive -- F7's own selection gate) = %.3f"
          % (both_pos_pl / N_PLACEBO))
    print("placebo delta distribution: p5 %+.2f  median %+.2f  p95 %+.2f  max %+.2f"
          % (pl_deltas[int(0.05 * N_PLACEBO)], pl_deltas[N_PLACEBO // 2],
             pl_deltas[int(0.95 * N_PLACEBO)], pl_deltas[-1]))

    # ---- multiplicity: best-of-25 under the placebo null
    k = 25
    best_of = []
    for i in range(0, N_PLACEBO - k, k):
        best_of.append(max(pl_deltas[j] for j in range(0, 0)) if False else None)
    # proper best-of-25: draw 25 placebo deltas at random, take the max, repeat
    rnd3 = random.Random(SEED + 2)
    maxes = []
    for _ in range(4000):
        maxes.append(max(pl_deltas[rnd3.randrange(N_PLACEBO)] for _ in range(k)))
    maxes.sort()
    p_bestof25_ge = sum(1 for v in maxes if v >= obs_all) / len(maxes)
    print("\n== multiplicity: 25 rules were measured before this one was picked ==")
    print("best-of-25 null delta: median %+.2f  p95 %+.2f" %
          (maxes[len(maxes) // 2], maxes[int(0.95 * len(maxes))]))
    print("P(best of 25 null arms >= observed %+0.2f) = %.3f" % (obs_all, p_bestof25_ge))

    out = {
        "reproduces": construct_ok,
        "observed": {"all": round(obs_all, 2), "h1": round(obs_h1, 2),
                     "h2": round(obs_h2, 2)},
        "sessions_changed": len(changed),
        "sessions": len(all_days),
        "top1_share_of_delta": round(
            100.0 * delta[dsorted[0]] / tot_delta, 1) if changed else None,
        "bootstrap": {
            "all_ci": [round(b_all[int(0.025 * N_BOOT)], 2),
                       round(b_all[int(0.975 * N_BOOT)], 2)],
            "all_p_le0": round(sum(1 for v in b_all if v <= 0) / N_BOOT, 3),
            "h1_p_le0": round(sum(1 for v in b_h1 if v <= 0) / N_BOOT, 3),
            "h2_p_le0": round(sum(1 for v in b_h2 if v <= 0) / N_BOOT, 3),
            "p_both_halves_positive": round(both_pos / N_BOOT, 3),
        },
        "placebo": {
            "n_drop": n_drop, "n_sizeable": n_size, "rate_pct": round(100 * rate, 3),
            "p_ge_observed": round(ge_obs / N_PLACEBO, 3),
            "p_both_halves_positive": round(both_pos_pl / N_PLACEBO, 3),
        },
        "multiplicity": {"k": k, "p_best_of_25_ge_observed": round(p_bestof25_ge, 3)},
    }
    json.dump(out, open(os.path.join(HERE, "g156_refute2_multiplicity.json"), "w"),
              indent=1)
    print("\nwrote research/g156_refute2_multiplicity.json")


if __name__ == "__main__":
    main()
