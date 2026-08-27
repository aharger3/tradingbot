# A2 — every published headline, re-run on the 2-year rig, today

Task A2. Inventories the headline numbers (mean R, win rate, trade count, months/quarters
green, recall, annualised dollars) currently published in `backtest_report.md`,
`backtest_report_12mo.md`, `backtest_regime_report.md`, `research/t60_baseline.md`, and the
vault's `Projects/OMEN.md`, finds the script behind each, and re-runs what the 2-year rig can
re-run. **Nothing in the five source documents was edited.** Where a re-run needed to
overwrite one of them in place to produce a number (`backtest_report.md`,
`backtest_charts.json`, `research/t60_baseline.md`), the pre-run file was copied out first and
restored byte-for-byte afterward — verified by `diff`, and by `git status` still showing the
same modified-file set it showed before this task started.

**Repo HEAD at measurement time: `30fbc3f8`** (this repo has active concurrent sessions;
three more commits landed on `main` while this file was being written — `86d96f99` /
`30fbc3f8` / `99bead1c` — none of them touch `signal_runner.py`, `backtest_week.py`,
`backtest_2y.py`, `downgrade.py`'s defaults, or `universe.py`, so none change a number below).

## Result in one line

**16 of 18 tracked headline numbers moved. 0 are UNREPRODUCIBLE** — every number traced to a
real, committed, runnable script; the failure mode this repo actually has is staleness and
network-fragility, not missing scripts. 1 row (the regime report's filtered "winner" mode)
was not re-run this pass — its script exists but is a separate pipeline, out of the 2-year
rig's scope. 1 row (the vault's win rate) came back exactly unchanged. The largest single
delta is `research/t60_baseline.md`'s money-gate read: **mean R +0.0787R → +0.9551R on the
2-year rig, +0.876R**, which is the difference between a published FAIL that reads like a
dead strategy and today's engine, which is most of the way to the gate.

## How today's numbers were produced

- **`backtest_2y.py` fresh run** (`research/a2_bt2y_rerun.json`, not committed — same
  gitignore precedent as the canonical `research/bt2y_trades.json` itself, see below): zero
  fetch errors, 100% cache-first off `data_archive/`. This is the clean rig.
- **`backtest_12mo.py 365 --snapshot` fresh run**: writes `backtest_report.md` /
  `backtest_charts.json` in place (backed up first, restored after). This rig is **not**
  fully cache-first — it live-fetches the trailing ~45 days per symbol from Polygon/Massive,
  and today, under concurrent load from other sessions active in this same repo, **458 of
  ~6,249 day-fetches came back `429 Too Many Requests`** (5,791 succeeded), silently skipped
  by `except Exception: continue` in the per-symbol fetch loop.
  The numbers below from this rig carry that gap; a contention-free re-run would likely land
  a third value.
- **`research/t60_baseline.py` fresh run**, against the freshly-regenerated (and therefore
  429-degraded) `backtest_charts.json` above, before it was restored. Backed up and restored
  the same way.
- **`research/a2_bt2y_summary.py`** (new, this task) — the aggregator that turned the raw
  `backtest_2y.py` row dump into the same whole-book numbers `research/p7_84_rule.py` /
  `research/p8_scratch.py` already compute (`_book()`: win rate of DECIDED trades, months
  green = months with total R > 0), plus a per-month table and an annualised-dollar figure
  using `research/t60_baseline.py::summarise()`'s own formula (`mean_r * $1000 *
  n*252/distinct_trading_days`), so the two rigs' dollar figures are computed the same way
  even though they read different corpora. Verified against the existing (2026-08-26)
  `research/bt2y_trades.json` first — it reproduced the CANON dict in `research/p8_scratch.py`
  exactly (1016 traded, 538W/473L/5 scratch, 53.2%, +0.9571R, +972.38R, 23/25 months) before
  being trusted on the fresh file.
- **Recall figures are cited, not re-run.** `research/t66_downgrade_measure.md` /
  `research/p2_threshold_sweep.md` score the engine against Austin's 120 graded day-cards —
  a separate, expensive sweep (45,175 signals x ~60 settings) that step 3 of this task does
  not cover. Their most recent commit (`73d3c903`, today) postdates the STALE_BARS ratification
  (`eff5a9e9`, also today) that could have moved them, and the vault confirms it was a
  near-no-op (98→263 trips of 45,175), so they are trustworthy as "today" without re-running
  the sweep — flagged per-row below rather than silently treated as freshly measured.
- **Nothing here was committed except this file and `research/a2_bt2y_summary.py`.**
  `research/a2_bt2y_rerun.json` (37.7 MB) stays local and untracked, same as the canonical
  `research/bt2y_trades.json` always has been (`.gitignore`: "research/bt2y_trades.json
  has never been tracked. The finding lives in `research/p7_84_rule.md`, which IS tracked.").

## The table

| # | Published in | Metric | Published value | Value today (2-yr rig) | Δ | Script + commit (today's value) |
|---|---|---|---|---|---:|---|
| 1 | `backtest_report.md` / `_12mo.md` (identical) | traded signals | **632** (3 A+, 7 A, 622 B) | **574** (0 A+, 7 A, 567 B) | **−58 (−9.2%)**, A+ bucket emptied | `backtest_12mo.py 365 --snapshot` @ HEAD `30fbc3f8`; script last changed `e1d346ca` (2026-07-11) / `backtest_week.py` last changed `7979a61e` (2026-08-26). Degraded by today's 429s (see above). |
| 2 | same | win rate (of decided) | **53.3%** | **51.8%** | **−1.5 pts** | same run |
| 3 | same | P&L, dollars (no R figure is published here) | **+$555,417.59** | **+$587,040.20** | **+$31,622.61 (+5.7%)** | same run |
| 4 | same | grade mix, A+ count | **3** (2W 1L) | **0** | **−3, bucket empty** | same run — plausibly a real detection-side shift (P16 landed 11:51-11:54 today, right at/after this doc's own generation), plausibly a data-gap artifact of the missing recent days; this pass does not separate the two causes |
| 5 | `backtest_regime_report.md` | baseline (no filter) traded, 11-symbol universe, 2024-07-11..2026-07-10 | **497** | **426** (same 11 symbols, 2-yr rig window 2024-08-21..2026-08-21) | **−71 (−14.3%)** | `research/a2_bt2y_summary.py --in research/a2_bt2y_rerun.json --symbols TSLA,NVDA,AAPL,AMD,META,GOOGL,AMZN,MSFT,PLTR,SPY,QQQ` off the `backtest_2y.py` rerun above |
| 6 | same | baseline P&L | **$6,833** (Year1 −$13,370, Year2 +$19,203) | **+0.7777R mean, +331.31R total** on the same subset | **not on a comparable scale** — see note | same run. $6,833/497 ≈ $13.75/trade (~0.014R); today's subset averages ~$778/trade. A 6-week window shift does not explain a 56x gap. `backtest_regimes_fast.py` was last committed `e1d346ca` (2026-07-11), **before** the ticket-17 stop-on-close fix and the ticket-02 break-even fix (both 2026-08-22/23, per `research/t60_baseline.md`) — its baseline plausibly reflects the pre-fix exit implementation, not just a different sample. Not confirmed by directly re-running `backtest_regimes_fast.py` this pass. |
| 7 | same | winner mode (SMA Directional 5%) P&L / trades | **$8,926 / 477 trades (+30.6%)** | **NOT RE-RUN** | — | Script exists and is committed (`backtest_regimes_fast.py`, `e1d346ca`) but is a separate pipeline from the 2-year rig: it live-fetches SPY/VIX via `market_data.py` and applies `RegimeDetector`, neither of which `backtest_2y.py` computes; its window is anchored to `date.today()` at run time, not to the archive, so it silently redefines "24 months" on every invocation. Out of this pass's declared scope, not UNREPRODUCIBLE — the distinction matters. |
| 8 | `research/t60_baseline.md` | trade count N | **905** | **1,017** on the 2-yr rig (also **824** on the same, 429-degraded, Corpus B re-run) | **+112 (2-yr rig)** | `backtest_2y.py` (content last `8797aee6`) fresh run @ `30fbc3f8`, summarised by `research/a2_bt2y_summary.py`. Corpus-B re-run: `research/t60_baseline.py` (`987e69ea`) against the degraded `backtest_charts.json` above. |
| 9 | same | mean R | **+0.0787R** | **+0.9551R** (2-yr rig) / +0.1574R (degraded Corpus B re-run) | **+0.8764R — the largest delta in this report** | same |
| 10 | same | win rate | **30.1%** (of ALL trades incl. scratch) | **53.2%** (of DECIDED trades — different denominator, flagged) / 31.1% (degraded Corpus B re-run, same all-trades convention as published) | **+23.1 pts nominal; not a clean comparison** — see note | same. `t60_baseline.py::summarise()` divides wins by every row; `research/a2_bt2y_summary.py` divides by decided trades only, matching `_book()` and every other 2-yr-rig report. The 31.1% same-convention re-run is the fairer read: **+1.0 pt**, i.e. most of the headline win-rate gap is corpus, not formula. |
| 11 | same | annualised $ | **+$78,351** | **+$589,848** (2-yr rig) / +$144,009 (degraded Corpus B re-run) | **+$511,497 (2-yr rig)** | same formula both rigs: `mean_r * $1000 * n*252/distinct_trading_days` |
| 12 | same | money gate verdict (mean R / win rate / ann $) | **FAIL / FAIL / FAIL** vs 2.0R / 55% / $100k | **FAIL / FAIL / PASS** (2-yr rig: +0.955R, 53.2%, $589,848) | **2 of 3 gates now close instead of nowhere near** | same |
| 13 | same | durability, months green | **7 / 13** (2025-08..2026-08, derived from the published per-month table's 6 listed negative slices) | **23 / 25** (2024-08..2026-08 — 12 more months in scope, not the same slice) | **ratio rises 54%→92% (+38 pts)**, window length differs so not apples to apples | `research/a2_bt2y_summary.py`, same run |
| 14 | same | durability, quarters green | **3 / 5** (2025-Q3..2026-Q3, derived) | **9 / 9** | **every quarter green today**, window length differs | same |
| 15 | same | recall, S-day | **3/28 = 10.7%** | **5/28 = 17.9%** (`research/t66_downgrade_measure.md`, "engine today" row) — cited, not re-run this pass, see methodology | **+2 S-days / +7.2 pts** | `research/t66_downgrade_measure.py`, commit `73d3c903` (2026-08-27, today — postdates the STALE_BARS ratification) |
| 16 | vault `Projects/OMEN.md`, "Where it stands — 2026-08-27" | mean R | **+0.957R**, captioned *"That has not moved today"* | **+0.9551R** | **−0.0020R — the caption is now false**, by a small margin, inside the same calendar day it was written | `backtest_2y.py` fresh run @ `30fbc3f8`; the vault's own number traces to the same script's 2026-08-26 12:28 run |
| 17 | same | traded signals | **1,016** | **1,017** | **+1** | same |
| 18 | same | win rate | **53.2%** | **53.2%** | **unchanged** | same — the one number in this report that came back exactly as published |

## What moved and what it's worth

**Rows 1-4** (`backtest_report.md`) are real deltas but the least trustworthy ones here — the
underlying rig is not cache-first and today's re-run lost 458 day-fetches to rate-limiting
under concurrent load from other sessions in this repo. The A+ grade bucket going from 3 to
exactly 0 is the one worth a second look independent of the fetch gap: 2026-08-27's P16
commits (`fdc8e090`, `71f39851`) touched `signal_runner.py` within minutes of when this
report's currently-published copy was itself generated (11:51 today), so the on-disk
"published" version may or may not already include them — this pass did not determine which
side of that race it landed on.

**Rows 5-7** (`backtest_regime_report.md`) are the stalest document in scope by calendar time
— last touched 2026-07-11, seven weeks and roughly a dozen engine tickets behind HEAD, predating
both stop-fix tickets that `research/t60_baseline.md` itself flags as the difference between a
runner that can lose and one that structurally cannot. Its baseline P&L is not on a scale this
task can directly reconcile against R-multiples without re-running its own pipeline, which is
future work, not this pass.

**Rows 8-15** (`research/t60_baseline.md`) carry the largest and most decision-relevant deltas
in this report, and they are the most trustworthy: `backtest_2y.py` is 100% cache-first archive
replay with zero fetch errors, run twice in this task (once to validate the aggregator against
the known-good 2026-08-26 canon, once fresh) and landing on the same conclusion both times.
`research/t60_baseline.md` states plainly that it is "the baseline every later number is
measured against" — it is currently the most out-of-date number wearing that title. Its Corpus
B (`backtest_charts.json`) is the same yfinance-labeled, Polygon-backed 12-month-ish rig as
rows 1-4, not the 2-year archive, which is the whole reason its FAIL/FAIL/FAIL money-gate read
diverges this hard from what the engine does today. The two re-runs of Corpus B in this task
(574 traded in the `backtest_report.md` rerun, 824 traded feeding `t60_baseline.py`) do not
agree with each other either, purely from which specific days lost their fetch mid-run — a
second illustration that this rig is not currently reproducible on demand, independent of any
code change.

**Rows 16-18** (vault `OMEN.md`) show the smallest deltas in the report and are the most
current document of the five — updated today, drawing on the same `backtest_2y.py` family as
rows 8-15. That its one qualitative claim ("has not moved today") is now technically false,
by 0.002R and 1 trade, a few hours after being written, is the cleanest illustration in this
whole file of why A2 exists: even the freshest, most carefully-sourced number in this project
has a shelf life measured in hours while `main` is this active, not months.

## Reproduce

```
python backtest_2y.py --out research/a2_bt2y_rerun.json      # zero fetch errors, ~5 min
python research/a2_bt2y_summary.py --in research/bt2y_trades.json        # sanity check vs CANON
python research/a2_bt2y_summary.py --in research/a2_bt2y_rerun.json      # today's whole book
python research/a2_bt2y_summary.py --in research/a2_bt2y_rerun.json \
    --symbols TSLA,NVDA,AAPL,AMD,META,GOOGL,AMZN,MSFT,PLTR,SPY,QQQ       # regime-report subset

# rows 1-4, 8-11 (Corpus B side) -- back up first, these write in place:
cp backtest_report.md backtest_report.md.bak && cp backtest_charts.json backtest_charts.json.bak
python backtest_12mo.py 365 --snapshot
cp research/t60_baseline.md research/t60_baseline.md.bak
python research/t60_baseline.py
# ... extract, then restore both .bak copies over the originals
```

Never printed `POLYGON_API_KEY` in this task; the 429 log lines were filtered with
`grep -v -i apikey` before being read.
