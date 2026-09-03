"""G7.1 track `levels` -- the PMH/PML name collision, measured.

`research/levels.py::prior_month_nodes` (:196) emits nodes typed "PMH"/"PML"
holding the PRIOR CALENDAR MONTH's high/low. Everywhere else in this repo --
`signal_runner.py:1809`, `backtest_week.py:734`, `research/build_levels.py`,
`research/downgrade.py::CONFLUENCE_LEVELS`, `research/t21_card_filter._levels`,
`research/p21_target_availability.levels_for_entry` -- PMH/PML means the
PREMARKET high/low of the same morning, which is one of Austin's six.

Two different prices under one name. This measures how different, over the
archive, so the size of the confusion is a number and not an opinion.

Usage: python research/g71_levels_pmh_collision.py
"""
from __future__ import annotations
import os, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

import polygon_feed as pf   # noqa: E402
import levels as rl         # research/levels.py  # noqa: E402
import backtest_2y as b2    # noqa: E402

SYMS = ["NVDA", "TSLA", "AAPL", "SPY", "QQQ", "AMD", "META", "MSFT"]

gaps_h, gaps_l, n = [], [], 0
for sym in SYMS:
    days = b2.archive_days(sym)[-120:]
    for d in days:
        pm = rl.prior_month_nodes(sym, d)
        if not pm:
            continue
        pmonth_h = next(x["price"] for x in pm if x["type"] == "PMH")
        pmonth_l = next(x["price"] for x in pm if x["type"] == "PML")
        try:
            bars = pf.fetch_day(sym, d)
        except Exception:
            continue
        pre_h, pre_l = pf.premarket_hi_lo(bars)
        if pre_h is None or pre_l is None:
            continue
        n += 1
        gaps_h.append(abs(pmonth_h - pre_h) / pre_h * 100)
        gaps_l.append(abs(pmonth_l - pre_l) / pre_l * 100)

print("symbol-days compared: %d" % n)
print("|PMH_prior_month - PMH_premarket| as %% of premarket high: "
      "median %.2f%%  mean %.2f%%  p90 %.2f%%"
      % (st.median(gaps_h), st.fmean(gaps_h), sorted(gaps_h)[int(.9 * len(gaps_h))]))
print("|PML_prior_month - PML_premarket| as %% of premarket low:  "
      "median %.2f%%  mean %.2f%%  p90 %.2f%%"
      % (st.median(gaps_l), st.fmean(gaps_l), sorted(gaps_l)[int(.9 * len(gaps_l))]))
print("exact matches: PMH %d, PML %d"
      % (sum(1 for g in gaps_h if g < 1e-9), sum(1 for g in gaps_l if g < 1e-9)))
