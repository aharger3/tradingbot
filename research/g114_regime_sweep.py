"""g114_regime_sweep.py -- regime slices of the honest book, headlined in EV/R.

Austin 2026-09-03: EV per trade in R is the headline everywhere; $/day is a
supporting row. This sweep asks: which regimes carry the edge and which
destroy it, across vol_regime, gap bucket, day-range bucket, SPY trend, day
of week, month, and first-half vs second-half of the 2-year book? g95 found
day-of-week was the single best predictor among 81 stamped features, which
smells like noise -- every split here runs through a label-permutation test
(10,000 draws) so "best of N regimes" doesn't get reported as a real edge by
construction.

Algebra note: win_rate*avg_win_R - loss_rate*avg_loss_R (Austin's ev_r
formula, ev_r_scoreboard in omen_metrics.py) is exactly mean(R) over the
group -- sum_win and sum_loss_abs telescope to sum(all R) once you divide
by the same n. That means the win/loss decomposition drops out of the
omnibus statistic and this file can permutation-test the plain group means
directly (an ordinary one-way ANOVA SS-between, vectorized in numpy) while
still reporting EV/R by name in every printed table, since it IS that
number.

Two arms, both size-gated on signal_runner.min_risk_floor via
omen_metrics.ev_r_scoreboard / _row_is_sizeable:

  PRIMARY  -- the shippable one-trade-a-day arm (omen_metrics.first_of_day_arm),
              n~444. This is the arm every other g11x sweep headlines against.
  POWER    -- every fired-and-traded row in the book, n~4000. NOT a shippable
              policy (multiple trades/day) -- reported only because 444 split
              12 ways starves every cell. A regime claim that only shows up
              in POWER and not PRIMARY is a power artifact, not a plan.

LOOKAHEAD FLAG: vol_regime, spy_trend, rangeb and dret are computed in
backtest_2y.py from the CURRENT day's own close/high/low (spy_context() uses
closes[i] including today; drange/dret use dhi/dlo/dclose across the full
session). An entry at 09:46 cannot know its own day's high, low, or close --
these are POST-HOC LABELS for describing what already happened, not levers a
live day-open filter could use. gapb is causal (prior close + this day's
OPEN, both known pre-entry). dow/month/half are calendar, always causal.
Flagged dimensions are still scored (the question "which regimes carry the
edge" is legitimate as description) but marked UNSHIPPABLE in the table.

    python research/g114_regime_sweep.py
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from omen_metrics import first_of_day_arm, _row_is_sizeable, BOOK_PATH, MIN_RISK_FLOOR_SOURCE

N_PERM = 10000
SEED = 42


def month_of_year(row):
    return row["ym"][5:7]  # "01".."12", both years folded together


def load_book():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    return blob["meta"], blob["trades"]


def sizeable_rs(rows):
    """(r, row) for every row that clears the size gate -- the fixed R
    population the permutation tests shuffle LABELS over (values never
    change; only which group each value is assigned to does)."""
    out = []
    for r in rows:
        if _row_is_sizeable(r) is False:
            continue
        rr = r.get("r")
        if rr is None:
            continue
        out.append((rr, r))
    return out


# ---------------------------------------------------------------------------
# vectorized permutation machinery (numpy) -- ev_r == mean(R), see module
# docstring, so the omnibus statistic is the ordinary ANOVA SS-between.
# ---------------------------------------------------------------------------

def omnibus_p(rs, labels_idx, n_groups, n_perm=N_PERM, seed=SEED):
    n = len(rs)
    overall = rs.mean()

    def ss_between(lab):
        ss = 0.0
        for g in range(n_groups):
            mask = (lab == g)
            cnt = mask.sum()
            if cnt == 0:
                continue
            mean_g = rs[mask].mean()
            ss += cnt * (mean_g - overall) ** 2
        return ss

    observed = ss_between(labels_idx)

    rng = np.random.default_rng(seed)
    perm_idx = np.argsort(rng.random((n_perm, n)), axis=1)
    shuffled = labels_idx[perm_idx]  # (n_perm, n)

    ss_null = np.zeros(n_perm)
    for g in range(n_groups):
        mask = (shuffled == g)               # (n_perm, n)
        cnt = mask.sum(axis=1)                # (n_perm,)
        safe_cnt = np.where(cnt == 0, 1, cnt)
        sums = (mask * rs[None, :]).sum(axis=1)
        means = sums / safe_cnt
        ss_null += np.where(cnt > 0, cnt * (means - overall) ** 2, 0.0)

    p = (np.sum(ss_null >= observed) + 1) / (n_perm + 1)
    return observed, p


def level_vs_rest_p(rs, is_in_level, n_perm=N_PERM, seed=SEED):
    n = len(rs)
    mask0 = np.asarray(is_in_level, dtype=bool)
    n_in = mask0.sum()
    n_out = n - n_in
    if n_in == 0 or n_out == 0:
        return None, None, None
    total_sum = rs.sum()
    sum_in = rs[mask0].sum()
    mean_in = sum_in / n_in
    mean_out = (total_sum - sum_in) / n_out
    observed = abs(mean_in - mean_out)

    rng = np.random.default_rng(seed)
    perm_idx = np.argsort(rng.random((n_perm, n)), axis=1)
    shuffled_mask = mask0[perm_idx]  # (n_perm, n)
    cnt_in = shuffled_mask.sum(axis=1)
    cnt_out = n - cnt_in
    sums_in = (shuffled_mask * rs[None, :]).sum(axis=1)
    sums_out = total_sum - sums_in
    means_in = sums_in / np.where(cnt_in == 0, 1, cnt_in)
    means_out = sums_out / np.where(cnt_out == 0, 1, cnt_out)
    stat = np.abs(means_in - means_out)
    p = (np.sum(stat >= observed) + 1) / (n_perm + 1)
    return float(mean_in), float(mean_out), float(p)


# ---------------------------------------------------------------------------
# per-dimension sweep
# ---------------------------------------------------------------------------

DIMENSIONS = [
    # (name, key_fn, causal?, note)
    ("vol_regime", lambda r: r.get("vol_regime", "n/a"), False,
     "SPY same-day close/SMA -- day not over yet at entry"),
    ("gapb", lambda r: r.get("gapb", "n/a"), True,
     "prior close + today's open, both pre-entry"),
    ("rangeb", lambda r: r.get("rangeb", "n/a"), False,
     "full-session high/low -- includes bars after entry"),
    ("spy_trend", lambda r: r.get("spy_trend", "n/a"), False,
     "SPY same-day close vs 20d SMA -- day not over yet at entry"),
    ("dow", lambda r: r.get("dow", "n/a"), True, "calendar"),
    ("month_of_year", month_of_year, True, "calendar, years folded together"),
    ("yr", lambda r: r.get("yr", "n/a"), True,
     "calendar; 2024/2026 are partial years (Sep-Dec / Jan-Sep)"),
]


def half_label_fn(sorted_days):
    """chronological first-half vs second-half of the book's own session
    calendar, by day RANK not calendar year (the book spans Sep'24-Sep'26,
    so calendar-year buckets are lopsided partial years)."""
    mid = len(sorted_days) // 2
    cut = sorted_days[mid]
    return lambda r: "first_half" if r["day"] < cut else "second_half"


def run_arm(name, rows, all_days_sorted):
    pairs = sizeable_rs(rows)
    rs = np.array([p[0] for p in pairs], dtype=float)
    recs = [p[1] for p in pairs]
    n = len(rs)
    overall_ev = float(rs.mean()) if n else None
    print("\n" + "=" * 78)
    print("%s -- n=%d sizeable trades (of %d input), overall EV/R = %s" %
          (name, n, len(rows), ("%.4f" % overall_ev) if overall_ev is not None else "n/a"))
    print("=" * 78)

    dims = list(DIMENSIONS)
    dims.append(("half", half_label_fn(all_days_sorted), True,
                  "chronological halves of the 498-session book"))

    n_arms_tested = 0
    flagged_unshippable = []
    survivors = []

    for dim_name, key_fn, causal, note in dims:
        labels = [key_fn(r) for r in recs]
        levels = sorted(set(labels))
        n_groups = len(levels)
        if n_groups < 2:
            print("\n[%s] only %d level present -- skipped" % (dim_name, n_groups))
            continue
        level_idx = {lv: i for i, lv in enumerate(levels)}
        labels_idx = np.array([level_idx[l] for l in labels], dtype=int)

        observed_ss, p_omni = omnibus_p(rs, labels_idx, n_groups)
        n_arms_tested += 1
        tag = "" if causal else "  [UNSHIPPABLE: lookahead -- %s]" % note
        if not causal:
            flagged_unshippable.append(dim_name)
        print("\n--- %s%s ---" % (dim_name, tag))
        print("  omnibus permutation: SS_between=%.5f  p=%.4f  (%d groups, %d perms)" %
              (observed_ss, p_omni, n_groups, N_PERM))

        by_level = defaultdict(list)
        for r, l in zip(rs, labels):
            by_level[l].append(r)

        print("  %-16s %6s %9s %9s %9s %9s" %
              ("level", "n", "ev_r", "win%", "avg_win", "avg_loss"))
        for lv in levels:
            grp = np.array(by_level[lv])
            wins = grp[grp > 0]
            losses = grp[grp < 0]
            ev = float(grp.mean())
            wr = len(wins) / len(grp) if len(grp) else 0.0
            aw = float(wins.mean()) if len(wins) else 0.0
            al = float(-losses.mean()) if len(losses) else 0.0
            is_in = [l == lv for l in labels]
            _, _, p_lvl = level_vs_rest_p(rs, is_in)
            n_arms_tested += 1
            star = " *" if (p_lvl is not None and p_lvl < 0.05) else ""
            print("  %-16s %6d %9.4f %8.1f%% %9.4f %9.4f   p_vs_rest=%.4f%s" %
                  (lv, len(grp), ev, wr * 100, aw, al, p_lvl if p_lvl is not None else float("nan"), star))
            if star:
                survivors.append((dim_name, lv, len(grp), ev, p_lvl, causal))

    return n_arms_tested, flagged_unshippable, survivors


def main():
    print("min_risk_floor source: %s" % MIN_RISK_FLOOR_SOURCE)
    meta, rows = load_book()
    sessions = meta.get("sessions") or len({r["day"] for r in rows})
    all_days_sorted = sorted({r["day"] for r in rows})
    print("book: %s sessions, %d symbols, %d rows" %
          (sessions, len(meta.get("symbols", [])), len(rows)))

    firsts = first_of_day_arm(rows)
    traded_all = [r for r in rows if r.get("status") == "fired" and r.get("traded")]

    total_arms = 0
    total_unshippable_dims = set()
    all_survivors = []

    for arm_name, arm_rows in (
        ("PRIMARY: first-of-day (shippable, one trade/day)", firsts),
        ("POWER-ONLY: all fired-and-traded rows (NOT a shippable policy -- multi-trade/day)", traded_all),
    ):
        n_tested, unshippable, survivors = run_arm(arm_name, arm_rows, all_days_sorted)
        total_arms += n_tested
        total_unshippable_dims.update(unshippable)
        all_survivors.extend((arm_name, *s) for s in survivors)

    print("\n" + "#" * 78)
    print("SWEEP SUMMARY")
    print("#" * 78)
    print("arms tested (omnibus + per-level, both book arms): %d" % total_arms)
    print("dimensions flagged UNSHIPPABLE (lookahead): %s" %
          ", ".join(sorted(total_unshippable_dims)))
    if all_survivors:
        print("\nlevels surviving p<0.05 vs rest (level-permutation, NOT corrected for")
        print("testing %d arms -- expect ~%.1f false positives at alpha=0.05 by chance alone):" %
              (total_arms, 0.05 * total_arms))
        for arm_name, dim, lv, ng, ev, p, causal in all_survivors:
            print("  [%s] %s=%s  n=%d ev_r=%.4f p=%.4f  %s" %
                  (arm_name.split(":")[0], dim, lv, ng, ev, p,
                   "causal" if causal else "LOOKAHEAD-UNSHIPPABLE"))
    else:
        print("\nNo level survived p<0.05 vs rest, on either arm, at any dimension.")
        print("Read straight: no regime slice of this book carries a signal that")
        print("clears a look-alike-random relabeling. g95's day-of-week finding was")
        print("the multiple-comparisons artifact it looked like.")


if __name__ == "__main__":
    main()
