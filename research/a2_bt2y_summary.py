"""A2 -- headline summary off a backtest_2y.py-shaped trades file.

Task A2 re-runs every published OMEN figure on the 2-year rig and records
which moved (`research/a2_figure_refresh.md`). This is the small runner that
makes that comparison possible: it reads a `research/bt2y_trades.json`-shaped
file (the canonical file itself, or a fresh `--out` from `backtest_2y.py`)
and prints the same whole-book numbers `research/p7_84_rule.py` /
`research/p8_scratch.py` compute (`_book()`), plus a per-month breakdown and
an annualised-dollar figure using the same formula as
`research/t60_baseline.py::summarise()` (mean_r * RISK_DOLLARS * trades_per_year,
trades_per_year = n * 252 / distinct_trading_days), so the two rigs' dollar
figures are computed the same way even though they read different corpora.

Nothing here recomputes a grade, a stop, or an R-multiple -- it only
aggregates the `r` / `ym` / `traded` / `out` / `sym` fields backtest_2y.py
already wrote. If those fields are wrong this script inherits the error
rather than hiding it.

Usage:
    python research/a2_bt2y_summary.py --in research/bt2y_trades.json
    python research/a2_bt2y_summary.py --in research/a2_bt2y_rerun.json --symbols TSLA,NVDA,AAPL,AMD,META,GOOGL,AMZN,MSFT,PLTR,SPY,QQQ
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRADING_DAYS_PER_YEAR = 252
RISK_DOLLARS = 1000.0


def quarter_of(ym: str) -> str:
    y, m = ym.split("-")
    return "%s-Q%d" % (y, (int(m) - 1) // 3 + 1)


def book(rows):
    """Whole-book money read, same convention as p7_84_rule.py / p8_scratch.py
    `_book()`: win rate is of DECIDED trades (scratches excluded)."""
    tr = [r for r in rows if r["traded"]]
    w = sum(1 for r in tr if r["out"] == "win")
    l = sum(1 for r in tr if r["out"] == "loss")
    rs = [r["r"] for r in tr]
    days = {r["day"] for r in tr}
    by_m, by_q = defaultdict(float), defaultdict(float)
    for r in tr:
        by_m[r["ym"]] += r["r"]
        by_q[quarter_of(r["ym"])] += r["r"]
    mean_r = statistics.fmean(rs) if rs else 0.0
    per_year = len(rs) * TRADING_DAYS_PER_YEAR / max(len(days), 1)
    return {
        "signals": len(rows), "traded": len(tr), "w": w, "l": l,
        "scratch": len(tr) - w - l,
        "wr": round(w / (w + l) * 100, 1) if (w + l) else 0.0,
        "meanr": round(mean_r, 4),
        "totr": round(sum(rs), 2),
        "worst": round(min(rs), 4) if rs else 0.0,
        "trading_days": len(days),
        "trades_per_year": round(per_year, 1),
        "ann_dollars": round(mean_r * RISK_DOLLARS * per_year),
        "months_green": sum(1 for v in by_m.values() if v > 0), "months": len(by_m),
        "quarters_green": sum(1 for v in by_q.values() if v > 0), "quarters": len(by_q),
        "by_month": {k: round(v, 2) for k, v in sorted(by_m.items())},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="inp", default="research/bt2y_trades.json")
    ap.add_argument("--symbols", default=None,
                     help="comma list to filter to (e.g. the regime report's 11-symbol set)")
    a = ap.parse_args()

    p = ROOT / a.inp if not Path(a.inp).is_absolute() else Path(a.inp)
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = d["trades"]
    label = a.inp
    if a.symbols:
        want = {s.strip().upper() for s in a.symbols.split(",")}
        rows = [r for r in rows if r["sym"] in want]
        label += " [symbols=%s]" % ",".join(sorted(want))

    b = book(rows)
    print("=== %s ===" % label)
    print("meta.generated:", d.get("meta", {}).get("generated"))
    print("meta.first..last:", d.get("meta", {}).get("first"), "..", d.get("meta", {}).get("last"))
    print("signals=%d traded=%d W=%d L=%d scratch=%d wr=%.1f%% meanR=%+.4f totR=%+.2f worst=%.4f"
          % (b["signals"], b["traded"], b["w"], b["l"], b["scratch"], b["wr"],
             b["meanr"], b["totr"], b["worst"]))
    print("trading_days=%d trades_per_year=%.1f ann_dollars=%s"
          % (b["trading_days"], b["trades_per_year"], format(b["ann_dollars"], "+,")))
    print("months green: %d / %d   quarters green: %d / %d"
          % (b["months_green"], b["months"], b["quarters_green"], b["quarters"]))
    print(json.dumps(b, indent=None))


if __name__ == "__main__":
    main()
