"""g156 REFUTER #1 (lookahead / leakage lens) -- OMEN 9.0 F7, base f8740f80.

Refutes the F7 claim that `S_CLASSIFIER` v0 buys +$13.51/day on the
one-trade-a-day unit (research/g154_rule_or-break-without-retest.py).

Tests, all on the same honest book (research/bt2y_trades_retest_on.json,
entry = signal bar CLOSE, stops via stop_rule.stop_fill_price, size-gated on
omen_metrics._row_is_sizeable, 1R = $1,000):

  T0  LOOKAHEAD   -- instrument downgrade.no_retest and record the highest bar
                     index it reads. Clean iff max index <= the signal bar.
  T1  REPRODUCE   -- rerun the claim's arithmetic from the book.
  T2  CONCENTRATION -- how many of the 498 day-picks change hands, how much of
                     the whole-book delta is the single best day, bootstrap CI.
  T3  PLACEBO     -- an information-free drop matched day-for-day on COUNT
                     (same number of sizeable stream rows removed on the same
                     days, chosen uniformly at random). If a coin flip clears
                     the same "both halves positive" gate often, the gate is
                     not evidence.
  T4  MULTIPLICITY -- how many of the 25 F5 candidates already print both
                     halves positive.

    python research/g156_refute1_lookahead_leakage.py

Writes research/g156_refute1_lookahead_leakage.json. Ships nothing.
"""
from __future__ import annotations

import glob
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import omen_metrics as om                     # noqa: E402
from research import downgrade as dg          # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT = os.path.join(HERE, "g156_refute1_lookahead_leakage.json")
SPLIT_DAY = "2025-09-01"
OR_LEVELS = ("OR high", "OR low")
TRIALS = 2000
SEED = 20260905
CLAIM_DELTA = 13.51


def drop_or(r):
    return r.get("level") in OR_LEVELS and "no_retest" in r.get("downgrades", [])


def _ekey(r):
    return (r["day"], r["et"], r["sym"])


def stream(rows):
    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    for v in by_day.values():
        v.sort(key=_ekey)
    return by_day


def pick_first(by_day, drop_fn):
    out = {}
    for day, v in by_day.items():
        s = [r for r in v
             if om._row_is_sizeable(r) is not False and not drop_fn(r)]
        if s:
            out[day] = s[0]
    return out


def usd_day(picks, days):
    dset = set(days)
    tot = sum(r["pnl"] for d, r in picks.items() if d in dset)
    return tot / len(days) if days else 0.0


# ------------------------------------------------------------------- T0
def t0_lookahead_audit():
    """Record the highest bar index downgrade.no_retest reads for a signal at
    bar i. Anything above i would be a read past the entry bar."""
    touched = []

    class L(list):
        def __getitem__(self, k):
            if isinstance(k, slice):
                stop = k.stop if k.stop is not None else len(self)
                touched.append(stop - 1)
                return list.__getitem__(self, k)
            touched.append(k if k >= 0 else len(self) + k)
            return list.__getitem__(self, k)

    bars = [{"o": 100.0 + k * 0.01, "h": 100.2 + k * 0.01,
             "l": 99.8 + k * 0.01, "c": 100.1 + k * 0.01} for k in range(60)]
    i = 40
    for is_long in (True, False):
        for lvl in (100.05, 100.3, 100.45):
            dg.no_retest(L(bars), i, lvl, is_long)
    return {"signal_bar_i": i, "max_bar_index_read": max(touched),
            "reads_past_entry_bar": bool(max(touched) > i)}


def main():
    rng = random.Random(SEED)
    blob = json.load(open(BOOK, encoding="utf-8"))
    rows = blob["trades"]
    all_days = sorted({r["day"] for r in rows})
    h1 = [d for d in all_days if d < SPLIT_DAY]
    h2 = [d for d in all_days if d >= SPLIT_DAY]

    by_day = stream(rows)

    # ---- T1 reproduce
    base_picks = {r["day"]: r for r in om.first_of_day_arm(rows, size_gate=True)}
    arm_picks = pick_first(by_day, drop_or)

    base_all, arm_all = usd_day(base_picks, all_days), usd_day(arm_picks, all_days)
    base_h1, arm_h1 = usd_day(base_picks, h1), usd_day(arm_picks, h1)
    base_h2, arm_h2 = usd_day(base_picks, h2), usd_day(arm_picks, h2)
    d_all, d_h1, d_h2 = arm_all - base_all, arm_h1 - base_h1, arm_h2 - base_h2

    # ---- T2 concentration
    changed = []
    for day in all_days:
        b, a = base_picks.get(day), arm_picks.get(day)
        bp = b["pnl"] if b else 0.0
        ap = a["pnl"] if a else 0.0
        if (b is None) != (a is None) or (b is not None and a is not None
                                          and _ekey(b) != _ekey(a)):
            changed.append({"day": day, "delta": round(ap - bp, 2),
                            "base": [b["sym"], b["et"], b["pnl"]] if b else None,
                            "arm": [a["sym"], a["et"], a["pnl"]] if a else None})
    changed.sort(key=lambda x: -abs(x["delta"]))
    tot_delta = sum(c["delta"] for c in changed)
    top1 = changed[0]["delta"] if changed else 0.0
    top3 = sum(c["delta"] for c in changed[:3])

    if changed:
        worst_day = changed[0]["day"]
        jk_days = [d for d in all_days if d != worst_day]
        jk_delta = usd_day(arm_picks, jk_days) - usd_day(base_picks, jk_days)
    else:
        jk_delta = 0.0

    per_day = {}
    for day in all_days:
        b, a = base_picks.get(day), arm_picks.get(day)
        per_day[day] = (a["pnl"] if a else 0.0) - (b["pnl"] if b else 0.0)
    dl = list(all_days)
    n = len(dl)
    boots = []
    for _ in range(TRIALS):
        boots.append(sum(per_day[dl[rng.randrange(n)]] for _ in range(n)) / n)
    boots.sort()
    ci_lo, ci_hi = boots[int(0.025 * TRIALS)], boots[int(0.975 * TRIALS)]
    p_boot_le0 = sum(1 for v in boots if v <= 0) / TRIALS

    # ---- T3 placebo: matched per-day random drop of the same COUNT
    sizeable_by_day = {day: [r for r in v if om._row_is_sizeable(r) is not False]
                       for day, v in by_day.items()}
    n_dropped_by_day = {day: sum(1 for r in sz if drop_or(r))
                        for day, sz in sizeable_by_day.items()}

    hits_all = hits_gate = hits_h1 = hits_h2 = 0
    placebo_deltas = []
    for _ in range(TRIALS):
        picks = {}
        for day, sz in sizeable_by_day.items():
            k = min(n_dropped_by_day[day], len(sz))
            if k <= 0:
                if sz:
                    picks[day] = sz[0]
                continue
            drop_idx = set(rng.sample(range(len(sz)), k))
            surv = [r for j, r in enumerate(sz) if j not in drop_idx]
            if surv:
                picks[day] = surv[0]
        pa = usd_day(picks, all_days) - base_all
        p1 = usd_day(picks, h1) - base_h1
        p2 = usd_day(picks, h2) - base_h2
        placebo_deltas.append(pa)
        if pa >= d_all:
            hits_all += 1
        if p1 > 0 and p2 > 0:
            hits_gate += 1
        if p1 > 0:
            hits_h1 += 1
        if p2 > 0:
            hits_h2 += 1
    placebo_deltas.sort()

    # ---- T4 multiplicity over the F5 candidates
    both_pos = []
    n_with_delta = 0
    for p in sorted(glob.glob(os.path.join(HERE, "g154_rule_*.json"))):
        d = json.load(open(p, encoding="utf-8"))
        a, b = d.get("h1_delta_usd_day"), d.get("h2_delta_usd_day")
        if a is None or b is None:
            continue
        n_with_delta += 1
        if a > 0 and b > 0:
            both_pos.append([os.path.basename(p)[len("g154_rule_"):-5],
                             a, b, d.get("survivor")])

    out = {
        "base_commit": "f8740f80",
        "book": os.path.basename(BOOK),
        "sessions": len(all_days),
        "fill": "signal bar CLOSE entry, stop_rule.stop_fill_price stops, "
                "size-gated on omen_metrics._row_is_sizeable, 1R=$1000",
        "t0_lookahead_audit": t0_lookahead_audit(),
        "t1_reproduce": {
            "baseline_usd_day": round(base_all, 2),
            "arm_usd_day": round(arm_all, 2),
            "delta_usd_day": round(d_all, 2),
            "h1": {"baseline": round(base_h1, 2), "arm": round(arm_h1, 2),
                   "delta": round(d_h1, 2)},
            "h2": {"baseline": round(base_h2, 2), "arm": round(arm_h2, 2),
                   "delta": round(d_h2, 2)},
            "matches_claim": bool(abs(d_all - CLAIM_DELTA) < 0.02),
        },
        "t2_concentration": {
            "days_changed": len(changed),
            "days_total": len(all_days),
            "pct_days_changed": round(len(changed) / len(all_days) * 100, 2),
            "total_delta_usd": round(tot_delta, 2),
            "top1_day_share_pct": round(top1 / tot_delta * 100, 1) if tot_delta else None,
            "top3_day_share_pct": round(top3 / tot_delta * 100, 1) if tot_delta else None,
            "top5_changed_days": changed[:5],
            "delta_usd_day_without_top_day": round(jk_delta, 2),
            "bootstrap_ci95_usd_day": [round(ci_lo, 2), round(ci_hi, 2)],
            "bootstrap_p_delta_le_0": round(p_boot_le0, 4),
        },
        "t3_placebo_matched_count_random_drop": {
            "trials": TRIALS,
            "p_delta_ge_claim": round(hits_all / TRIALS, 4),
            "p_both_halves_positive": round(hits_gate / TRIALS, 4),
            "p_h1_positive": round(hits_h1 / TRIALS, 4),
            "p_h2_positive": round(hits_h2 / TRIALS, 4),
            "placebo_median_delta": round(placebo_deltas[TRIALS // 2], 2),
            "placebo_p95_delta": round(placebo_deltas[int(0.95 * TRIALS)], 2),
        },
        "t4_multiplicity": {
            "candidates_with_both_deltas_reported": n_with_delta,
            "candidates_total_measured_in_f5": 25,
            "both_halves_positive": both_pos,
            "n_both_halves_positive": len(both_pos),
        },
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
