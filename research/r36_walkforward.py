"""R36 -- walk-forward audit of the g88 POST_floor break-and-retest baseline.

Baseline (u03-backtest-ledger.md): research/tape/g88_post_floor_trades.json.gz,
498 trades, one per session, 2024-09-03 to 2026-09-02, $256/day gross,
$161/day net of slippage, 27.5% win rate.

This script:
  1. Loads the 498-trade book (already causal / no-lookahead per the ledger).
  2. Splits it chronologically: train = first 298 days, test = LAST 200 days
     (unseen, never touched by the fit) -- guarantees the >=200-trade floor.
  3. Grid-searches <=5 binary/threshold selection params on TRAIN ONLY,
     maximizing train avg R per trade (min 60 train trades to keep a fit
     meaningful), where params are all things a trader could set in advance
     (grade floor, score floor, weekday, vol regime, trend alignment) --
     nothing here touches entry/stop/exit logic, only which of the already
     -fired signals get taken.
  4. Applies the frozen, fitted filter UNCHANGED to the test period and
     reports n, win rate, avg R, $/day-equivalent (avg R * 1000), and the
     delta vs both the train fit and the full-sample baseline.

Run: python research/r36_walkforward.py
"""
from __future__ import annotations

import gzip
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "research" / "tape" / "g88_post_floor_trades.json.gz"
OUT_MD = ROOT / "research" / "r36_walkforward.md"

GRADE_RANK = {"S": 4, "A": 3, "B": 2, "C": 1, "D": 0}

# The 5 tuned params. Each is a (name, candidate values) pair.
PARAM_SPACE = [
    ("sgrade_min", ["ANY", "D", "C", "B", "A", "S"]),
    ("score_min", [0, 1, 2, 3, 4]),
    ("exclude_fri", [False, True]),
    ("vol_regime", ["ANY", "normal_or_wild", "wild_only"]),
    ("aligned", ["ANY", "not_against"]),
]

MIN_TRAIN_TRADES = 60


def load_trades():
    with gzip.open(BOOK, "rt", encoding="utf-8") as f:
        d = json.load(f)
    rows = d["trades"]
    rows.sort(key=lambda r: (r["day"], r["et"]))
    return d["meta"], rows


def passes(row, params):
    sgrade_min, score_min, exclude_fri, vol_regime, aligned = params
    if sgrade_min != "ANY" and GRADE_RANK.get(row.get("sgrade", "D"), 0) < GRADE_RANK[sgrade_min]:
        return False
    if row.get("s", 0) < score_min:
        return False
    if exclude_fri and row.get("dow") == "Fri":
        return False
    vr = row.get("vol_regime", "")
    if vol_regime == "wild_only" and vr != "wild":
        return False
    if vol_regime == "normal_or_wild" and vr not in ("normal", "wild"):
        return False
    if aligned == "not_against" and row.get("aligned") == "against":
        return False
    return True


def stats(rows):
    n = len(rows)
    if n == 0:
        return dict(n=0, win_rate=0.0, avg_r=0.0, total_r=0.0, dollars_per_day=0.0)
    wins = sum(1 for r in rows if r["r"] > 0)
    total_r = sum(r["r"] for r in rows)
    avg_r = total_r / n
    return dict(n=n, win_rate=100.0 * wins / n, avg_r=avg_r, total_r=total_r,
                dollars_per_day=avg_r * 1000.0)


def main():
    meta, rows = load_trades()
    n_total = len(rows)
    n_test = 200
    n_train = n_total - n_test
    train, test = rows[:n_train], rows[n_train:]
    assert len(test) >= 200, "unseen period must be >=200 trades"

    base_train = stats(train)
    base_test = stats(test)
    base_all = stats(rows)

    best = None
    combos = 0
    for combo in itertools.product(*[vals for _, vals in PARAM_SPACE]):
        combos += 1
        sub = [r for r in train if passes(r, combo)]
        if len(sub) < MIN_TRAIN_TRADES:
            continue
        s = stats(sub)
        if best is None or s["avg_r"] > best[1]["avg_r"]:
            best = (combo, s)

    best_combo, best_train_stats = best
    test_filtered = [r for r in test if passes(r, best_combo)]
    test_stats = stats(test_filtered)

    param_names = [p[0] for p in PARAM_SPACE]
    combo_str = ", ".join(f"{n}={v}" for n, v in zip(param_names, best_combo))

    lines = []
    lines.append("# R36 walk-forward audit -- g88 POST_floor break-and-retest baseline")
    lines.append("")
    lines.append(f"Book: `{BOOK.relative_to(ROOT)}` -- {n_total} trades, "
                  f"{meta.get('first', rows[0]['day'])} to {meta.get('last', rows[-1]['day'])}, one per session.")
    lines.append("")
    lines.append(f"Grid: {len(param_names)} params, {combos} combos "
                  f"(min {MIN_TRAIN_TRADES} train trades to qualify).")
    lines.append("")
    lines.append("## Split")
    lines.append(f"- Train (fit window): first {len(train)} trades, "
                  f"{train[0]['day']} to {train[-1]['day']}")
    lines.append(f"- Test (unseen, never touched by the fit): last {len(test)} trades, "
                  f"{test[0]['day']} to {test[-1]['day']}")
    lines.append("")
    lines.append("## Baseline (no filter, this book)")
    lines.append(f"- Full sample: n={base_all['n']}, win {base_all['win_rate']:.1f}%, "
                  f"avg R {base_all['avg_r']:.3f}, ${base_all['dollars_per_day']:.0f}/day-equiv")
    lines.append(f"- Train slice: n={base_train['n']}, win {base_train['win_rate']:.1f}%, "
                  f"avg R {base_train['avg_r']:.3f}, ${base_train['dollars_per_day']:.0f}/day-equiv")
    lines.append(f"- Test slice:  n={base_test['n']}, win {base_test['win_rate']:.1f}%, "
                  f"avg R {base_test['avg_r']:.3f}, ${base_test['dollars_per_day']:.0f}/day-equiv")
    lines.append("")
    lines.append("## Fitted filter (chosen on TRAIN ONLY, maximizing train avg R)")
    lines.append(f"- Params ({len(param_names)}): {combo_str}")
    lines.append(f"- Train (in-sample) result: n={best_train_stats['n']}, "
                  f"win {best_train_stats['win_rate']:.1f}%, avg R {best_train_stats['avg_r']:.3f}, "
                  f"${best_train_stats['dollars_per_day']:.0f}/day-equiv")
    lines.append("")
    lines.append("## Applied unchanged to the unseen test period")
    lines.append(f"- n={test_stats['n']}, win {test_stats['win_rate']:.1f}%, "
                  f"avg R {test_stats['avg_r']:.3f}, ${test_stats['dollars_per_day']:.0f}/day-equiv")
    lines.append("")
    delta_avg_r = test_stats["avg_r"] - base_test["avg_r"]
    delta_vs_train = test_stats["avg_r"] - best_train_stats["avg_r"]
    lines.append("## Verdict")
    lines.append(f"- Delta vs unfiltered test (same period, same baseline strategy): "
                  f"{delta_avg_r:+.3f}R/trade ({test_stats['dollars_per_day'] - base_test['dollars_per_day']:+.0f}$/day-equiv)")
    lines.append(f"- Delta vs the train fit itself (in-sample -> out-of-sample decay): "
                  f"{delta_vs_train:+.3f}R/trade")
    if test_stats["n"] < 30 or delta_avg_r <= 0:
        verdict = "CURVE-FIT: the filter tuned on train does not survive on unseen data (or n too thin)."
    elif delta_vs_train < -0.15:
        verdict = "PARTIAL: filter beats no-filter out-of-sample but decays a lot vs its own fit window -- treat as noisy."
    else:
        verdict = "HOLDS (weak claim): filter beats no-filter on unseen data with limited in-sample decay -- still n<200 in most cells, not a green light."
    lines.append(f"- {verdict}")
    lines.append("")
    lines.append("## Context vs the ledger's headline number")
    lines.append("`07-money/omen/u03-backtest-ledger.md`: g88 POST_floor, full 498-trade sample, "
                  "$256/day gross / $161/day net of slippage, 27.5% win rate, p=0.074 (not significant), "
                  "stocks not futures. Nothing here changes that verdict or the paper-trade gate.")
    lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {OUT_MD}")


if __name__ == "__main__":
    main()
