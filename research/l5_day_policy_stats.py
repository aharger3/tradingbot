"""L5 report numbers (2026-09-05 repair) -- daily P&L distribution, prop-firm
daily-loss pass rate, and fires/day histogram, on BOTH readings of the day
policy: the loop's own baseline UNIT (up_to_3_stop_win_or_2loss, look-ahead --
sorts a day's taken rows by entry time and reads each one's own final pnl
immediately) and the CAUSAL enforcement this row ships (day_policy.py, a
trade only counts once it has actually closed).

Fill = honest close (backtest_2y.py default ENTRY_FILL). Exit = shipped
engine, 1R hard stop on the intrabar touch, SCALE_PLAN=hod_then_runner_be,
LOSS_HALT on. Unit = up_to_3_stop_win_or_2loss on the 11 core symbols
(loop.json). Source = research/tape/book_DAY_POLICY_off.json.gz (== the R3
baseline, book_id 2c39ced2697c26cc) and book_DAY_POLICY_on.json.gz (the same
book with day_policy.apply_to_book, referee-repaired, applied). Script =
research/l5_day_policy_stats.py.
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.loop_cycle import up_to_3_rows, apply_universe_filter  # noqa: E402


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def core_rows(rows):
    return apply_universe_filter(rows, {"row_filter": 'tier == "core"'})


def daily_pnl(unit_rows):
    """day -> summed pnl over the unit's picked rows for that day."""
    by_day = defaultdict(float)
    for r in unit_rows:
        by_day[r["day"]] += r.get("pnl", 0.0)
    return by_day


def fires_per_day_hist(unit_rows, all_days):
    counts = defaultdict(int)
    for r in unit_rows:
        counts[r["day"]] += 1
    hist = defaultdict(int)
    for d in all_days:
        hist[counts.get(d, 0)] += 1
    return hist


def pctile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def report_unit(label, unit_rows, all_days):
    by_day = daily_pnl(unit_rows)
    vals = sorted(by_day.get(d, 0.0) for d in all_days)
    n = len(vals)
    worst = vals[0] if vals else 0.0
    p5, p25, med, p75, p95 = (pctile(vals, q) for q in (0.05, 0.25, 0.5, 0.75, 0.95))
    breach_1000 = sum(1 for v in vals if v <= -1000)
    breach_2500 = sum(1 for v in vals if v <= -2500)
    hist = fires_per_day_hist(unit_rows, all_days)
    fires_per_day = len(unit_rows) / len(all_days) if all_days else 0.0
    print("== %s ==" % label)
    print("  days: %d, fires/day: %.3f, total fired-and-taken rows: %d"
          % (n, fires_per_day, len(unit_rows)))
    print("  daily P&L (all %d sessions, 0-fire days included): p5=%.0f p25=%.0f "
          "median=%.0f p75=%.0f p95=%.0f worst=%.0f"
          % (n, p5, p25, med, p75, p95, worst))
    print("  prop-firm daily-loss pass rate: $1,000 limit -> %d/%d breach (%.1f%% pass); "
          "$2,500 limit -> %d/%d breach (%.1f%% pass)"
          % (breach_1000, n, 100.0 * (n - breach_1000) / n if n else 0.0,
             breach_2500, n, 100.0 * (n - breach_2500) / n if n else 0.0))
    print("  days with 0/1/2/3 fires: %d / %d / %d / %d"
          % (hist.get(0, 0), hist.get(1, 0), hist.get(2, 0), hist.get(3, 0)))
    return {
        "days": n, "fires_per_day": round(fires_per_day, 3),
        "p5": p5, "p25": p25, "median": med, "p75": p75, "p95": p95, "worst": worst,
        "breach_1000": breach_1000, "breach_2500": breach_2500,
        "pass_1000_pct": round(100.0 * (n - breach_1000) / n, 1) if n else 0.0,
        "pass_2500_pct": round(100.0 * (n - breach_2500) / n, 1) if n else 0.0,
        "hist_0_1_2_3": [hist.get(0, 0), hist.get(1, 0), hist.get(2, 0), hist.get(3, 0)],
    }


def main():
    off_meta, off_rows = load(ROOT / "research/tape/book_DAY_POLICY_off.json.gz")
    on_meta, on_rows = load(ROOT / "research/tape/book_DAY_POLICY_on.json.gz")
    off_core = core_rows(off_rows)
    on_core = core_rows(on_rows)
    all_days = sorted({r["day"] for r in off_core if r.get("day")})
    print("core-11 sessions: %d (%s .. %s)" % (len(all_days), all_days[0], all_days[-1]))
    print()

    lens_rows = up_to_3_rows(off_core)
    out_lens = report_unit(
        "LENS (loop_cycle.up_to_3_rows, look-ahead -- the loop's baseline unit)",
        lens_rows, all_days)
    print()

    # Causal: the ON book already carries day_policy's causal stop marks
    # (status=='day_policy_halt' for a row it blocked). The unit's own
    # picked rows are what's left fired+traded (plus halted, unaffected).
    causal_rows = up_to_3_rows(on_core)
    out_causal = report_unit(
        "CAUSAL (day_policy.py's enforcement, referee-repaired, read through "
        "the same lens)", causal_rows, all_days)
    print()

    print(json.dumps({"lens": out_lens, "causal": out_causal}, indent=2))


if __name__ == "__main__":
    main()
