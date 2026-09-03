# The backtest artifacts — inventory, kill-list, and the one report

Austin: *"too much random variety on the backtest artifacts too"* and
*"One track of 22 failed outright stuff like that makes no sense to me, dont speak in code."*

He is right, and the variety is worse than cosmetic. **The two documents that say
"where OMEN stands" disagree with the book file sitting on disk.**

---

## 0. The headline

`research/bt2y_trades.json` is the current two-year book: 67.6 MB, stamped
`2026-08-29T03:14:29`, **76,019 setups, 2,437 traded**.

`DIRECTION.md` and `research/t0_ratified_rebaseline.md` publish the money and
durability rows as **75,953 setups, 2,595 traded, 43.1% win, 32.43R drawdown**.
That is a *different book* — the one T0 built at 02:5x, before T20 (loss halt),
T4 (index parity) and T23 landed later the same day.

Re-measured off the file on disk, using T0's own definitions verbatim
(`research/t0_rebaseline.py:43-49` for drawdown, `:59` for win rate), by
`research/g71_standard_report.py`:

| figure | published in `DIRECTION.md` | the book actually on disk | gap |
|---|---:|---:|---:|
| trades | 2,595 | **2,437** | −158 |
| average per trade | +0.5481 R | **+0.5495 R** | +0.0014 |
| win rate | 43.1% | **49.5%** | **+6.4 pts** |
| months green | 25 of 25 | 25 of 25 | 0 |
| worst drawdown | 32.43 R | **17.13 R** | **−15.3 R** |
| worst month | +6.01 R | **+3.92 R** | −2.09 R |
| total money | (not published) | **$1,339,071** | — |
| weeks green | (never measured) | **91 of 105 (87%)** | — |

The win rate on the gate table is understated by 6.4 points and the drawdown is
overstated by nearly half. Neither is a rounding difference; both are "nobody
re-rendered the page after the engine changed." **This is the whole problem in
one row.** Evidence: `research/omen_report.json`, written by
`research/g71_standard_report.py` from `research/bt2y_trades.json`.

---

## 1. Inventory — every backtest artifact in the repo

### Top level (all seven are committed to git)

| file | bytes | last written | what produced it | against which book | verdict |
|---|---:|---|---|---|---|
| `backtest_report.md` | 2,339,044 | 2026-08-28 09:25 | `backtest_week.py:910 write_report`, driven by `backtest_12mo.py` | a 12-month yfinance-era run titled "Week of 2025-08-25 to 2026-08-21"; 632 traded, +$555,417, 53.3% win | **SUPERSEDED** |
| `backtest_report_12mo.md` | 2,339,044 | 2026-08-28 09:25 | `shutil.copy2` at `backtest_12mo.py:179` | **byte-identical to the row above** (md5 `96de5e2c…` both) | **DELETE — pure duplicate** |
| `backtest_charts.json` | 3,750,071 | 2026-08-28 09:25 | `backtest_week.py:1213` | same run as `backtest_report.md` | **SUPERSEDED** |
| `backtest_charts_12mo.json` | 3,750,071 | 2026-08-28 09:25 | `shutil.copy2` at `backtest_12mo.py:178` | **byte-identical** (md5 `6e0b68fc…` both) | **DELETE — pure duplicate** |
| `backtest_regime_report.md` | 2,056 | 2026-07-11 (commit `e1d346ca`) | `backtest_regimes.py:514` | 2024-07-11→2026-07-10, an 11-symbol private list, $6,833 baseline, dollars only, no R | **SUPERSEDED** |
| `backtest_metrics_full.json` | 5,486 | 2026-08-09 | (producer not in tree) | quoted as `POPULATION_N` by `research/h3_veto.py:11` | **SUPERSEDED** |
| `backtest_rule6_comparison.md` | 51,375 | 2026-07-12 | `compare_rule6.py:15`, which reads `backtest_report.md` | the July book; the 84% rule was rewritten from source on 2026-08-29 (`03a611eb`) | **SUPERSEDED** |

Three separate defects in `backtest_report.md` alone, and Austin reads this file:

1. **The title lies about the range.** `backtest_week.py:916` hardcodes
   `f"# Backtest Report: Week of {days[0]} to {days[-1]}"`. The run was 12
   months. The page says "Week."
2. **The assumptions block lies about the data.** `backtest_week.py:919` prints
   *"Data: yfinance 1-min RTH bars"*, but `backtest_12mo.py:19` imports
   `polygon_feed`. The header describes a data source the run did not use.
3. **It publishes a $271 million number.** Line 12: *"D filtered: 21009 …
   ($271,820,001.36 if traded)"*. That is the X bucket — and per `DIRECTION.md`,
   `X` is not a grade, it means the engine should not have fired. The report
   prices a bug report at a quarter of a billion dollars and puts it two lines
   under the summary.

### Reports in `research/`

| file | bytes | last written | producer | book | verdict |
|---|---:|---|---|---|---|
| `research/omen-2y-backtest.html` | 10,674,106 | 2026-08-29 03:27 | `research/build_bt2y_report.py:754` | `research/bt2y_trades.json` — the **current** book | **KEEP** as the drill-down. Untracked; 10.7 MB. |
| `research/omen-71-verdict.html` | 20,976 | 2026-08-29 03:38 | commit `a0997963` | the T0 book (2,595) | **SUPERSEDED** by §0 |
| `research/omen-h2-tape.html` | 6,360,190 | 2026-08-28 05:14 | H2 tape session | pre-T0 | **ARCHIVE** |
| `research/h2_summary.html` | 11,057 | 2026-08-28 09:25 | H2 | pre-T0 | **ARCHIVE** |
| `research/t0_rebaseline_table.md` | — | 2026-08-29 | `research/t0_rebaseline.py` | the 02:5x book | **SUPERSEDED** — keep as history, stop quoting it |
| `research/t0_ratified_rebaseline.md` | — | 2026-08-29 | ditto | the 02:5x book | **SUPERSEDED for numbers**, still correct as the record of *what changed* |
| ~180 other `research/*.md` | — | Jul–Aug | one per track | each its own arm | history; not reports |

Deck and probe HTML under `research/decks/` and `research/probes/` are **homework
instruments, not backtest artifacts**. Out of scope, keep all of them.

### The actual mass

| what | count | size |
|---|---:|---:|
| one-off A/B arm books at `research/*.json` over 5 MB | **77** | **3.0 GB** |
| all files directly in `research/` | 1,103 | 3.21 GB |
| `research/audio_extracted/` (video work, unrelated) | — | 12 GB |
| `research/` total | — | 16 GB |

Seventy-seven 40–70 MB book files named `t4_arm_on`, `w1_arm_off`,
`_g71s_D_150`, `_t24_arm_routed_mkt`, `g13_arm_head` — none of them labelled
canonical, none of them dated in the filename, and one of them
(`research/bt2y_trades.json`) silently *is* the book of record. **That is the
"random variety."** It is not that the arms exist; it is that the book of record
looks exactly like the 77 throwaways.

---

## 2. The kill-list

**Delete outright** (byte-identical duplicates; a `shutil.copy2` is not a snapshot):

- `backtest_report_12mo.md`
- `backtest_charts_12mo.json`

**Archive to `research/_archive/2026-08-29/`** (keep the bytes, get them off the
front page, stop quoting them):

- `backtest_report.md`, `backtest_charts.json`
- `backtest_regime_report.md`, `backtest_metrics_full.json`,
  `backtest_rule6_comparison.md`
- `research/omen-h2-tape.html`, `research/h2_summary.html`,
  `research/omen-71-verdict.html`

**Sweep** (untracked, regenerable, 3.0 GB): every `research/*_arm_*.json`,
`research/_*.json` and `research/_g71s_*.json` older than the current book. Keep
only `research/bt2y_trades.json`.

**Rename, so the book of record cannot be mistaken for an arm:**
`research/bt2y_trades.json` → `research/book_current.json`, with every arm
written to `research/arms/`.

**The one canonical read going forward:**

> ### `research/omen_report.md`
> rendered by `research/g71_standard_report.py` from the current book, with
> `research/omen_report.json` beside it as the machine-readable sidecar so the
> next run can print a "moved" column.

`research/omen-2y-backtest.html` stays as the **drill-down** — the place to slice
the book by symbol, setup, hour. It is not the read. The read is one page of
plain numbers.

---

## 3. The one standard report

Script: `research/g71_standard_report.py`. Live render:
`research/omen_report.md`. Sidecar: `research/omen_report.json`.

```
python research/g71_standard_report.py                       # current book
python research/g71_standard_report.py --against research/omen_report.json
```

Four questions, always in this order, always these numbers. No track IDs, no
`R31`, no `T23`, no `A+`/`X`, no "arm", no "lever". Every target is stated in the
row next to the number so nothing has to be looked up.

### The template

```
# OMEN — the book, as of <date>

Every trade the engine would have taken over <N> market days, <first> to <last>,
across <K> symbols. Risk on every trade is $1,000. "R" is that $1,000: +2R is +$2,000.

It looked at <S> setups and took <T> of them.

## 1. Did it make money?
| | this run | needs to be | there yet? | moved |
| Money made              | $X       | —      | —   | ±$ |
| Average made per trade  | +0.55R ($550) | +2.00R | no  | ±R |
| Win rate                | 49.5%    | 55.0%  | no  | ± pts |
<one line: winners, losers, flats, best trade, worst trade, $ made per $1 lost>

## 2. Did it hold up?
| Months in profit    | 25 of 25       | all 25          | YES | ± |
| Weeks in profit     | 91 of 105 (87%)| —               | —   | ± |
| Worst run of losses | 17.1R (-$17,132)| smaller is better | — | ± |
<one line: worst month, and what "worst run of losses" means>

## 3. Did it find his trades?
| Fires on the days he graded best        | 18 of 34 (52.9%) | 90% | no | ± pts |
| Also fires on days he refused           | 33 of 66 (50.0%) | fewer is better | — | — |
| Of the setups it saw and threw away,
  how many he wanted                      | 0 of 9 | all of them | no | — |
<one line: which never-tuned-on sample this was measured against>
(if not re-measured this run: says so, and prints no number)

## 4. How busy is it?
| Trades per market day | 4.87   | ± |
| Trades in total       | 2,437  | ± |
| Setups looked at      | 76,019 | ± |

## The scoreboard
**1 of 3 finished.** OMEN is done when all three are true at once: it averages
+2R a trade at a 55% win rate, every month is green, and it fires on 90% of the
days he grades best.

## Month by month
| month | R | dollars |   ← every month, both units

---
Book: <path> (built <stamp>). Page: <script>. Numbers: <sidecar>.
```

### Why it is built this way

- **Every gate target sits in the row.** Austin never has to remember whether the
  bar was 2R or 55% — it is printed beside the number, with a plain YES/no.
- **Dollars and R on every money row.** R is the result, dollars are the sizing
  skin; the page shows both so neither has to be converted in his head.
- **Recall refuses to go stale.** If `--recall` is not passed, section 3 prints
  *"Not measured this run"* and no number. A stale recall figure is exactly the
  failure in §0; the page will not repeat it.
- **The "moved" column is opt-in and honest.** It only appears when a previous
  sidecar is handed in, and it names the date and book it is comparing against.
- **Weeks green is new.** Durability was only ever measured monthly; 25 of 25
  green months hides that 14 of 105 weeks are red. That is the number that
  matters for a person who trades every day.
- **No re-implementation.** The script counts rows a book already contains. It
  does not price a fill, apply a stop, or assign a grade.

### The rule that goes with it

Every future measurement publishes **this page and nothing else** as its
headline. A track may write its own working note, but the number that lands in
`DIRECTION.md` comes from `research/omen_report.json`, produced in the same run
that produced the book. The §0 disagreement becomes impossible the moment the
report is rendered by the same command that writes the book.

---

## 4. Proposed diffs (not applied)

**(a) Stop manufacturing byte-identical duplicates.**

```diff
--- a/backtest_12mo.py
+++ b/backtest_12mo.py
@@
     charts_path = ROOT / "backtest_charts.json"
     charts_path.write_text(json.dumps(chart_records), encoding="utf-8")
-    if args.snapshot:
-        shutil.copy2(charts_path, ROOT / "backtest_charts_12mo.json")
-        shutil.copy2(ROOT / "backtest_report.md", ROOT / "backtest_report_12mo.md")
-        print("  snapshot: backtest_charts_12mo.json + backtest_report_12mo.md written")
+    if args.snapshot:
+        stamp = date.today().isoformat()
+        snap = ROOT / "research" / "_archive" / stamp
+        snap.mkdir(parents=True, exist_ok=True)
+        shutil.copy2(charts_path, snap / "backtest_charts.json")
+        shutil.copy2(ROOT / "backtest_report.md", snap / "backtest_report.md")
+        print(f"  snapshot -> {snap}")
```

**(b) Stop the report header from lying about its own range and data source.**

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@
-    lines = [f"# Backtest Report: Week of {days[0]} to {days[-1]}" if days
-             else "# Backtest Report", ""]
+    lines = [f"# Backtest Report: {days[0]} to {days[-1]} "
+             f"({len(days)} sessions)" if days else "# Backtest Report", ""]
     lines += ["## Assumptions",
-              "- Data: yfinance 1-min RTH bars; walk-forward replay through SignalRunner.detect_signals",
+              f"- Data: {DATA_SOURCE} 1-min RTH bars; walk-forward replay through SignalRunner.detect_signals",
```

…with `DATA_SOURCE` set by whichever runner called in (`"yfinance"` in
`backtest_week`, `"Polygon"` in `backtest_12mo`).

**(c) Drop the $271M line.** `backtest_week.py`'s summary prices the X bucket
"if traded". X means the engine should not have fired. Delete the parenthetical
rather than print a quarter-billion-dollar counterfactual above the real result.

---

## 5. What I did not do

Nothing was deleted, moved, archived or committed. No shared engine file was
edited. `research/g71_standard_report.py` and this note are the only new files,
plus the two outputs the script wrote (`research/omen_report.md`,
`research/omen_report.json`).
