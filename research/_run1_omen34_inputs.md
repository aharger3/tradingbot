# omen-3.4 inputs — frozen inventory (T1)

Every path below was resolved and every count was produced by **parsing the file on
this checked-out repo** (`/home/runner/work/loop-ci/loop-ci/work`, branch `main`).
No count is inferred from a filename, a doc, or a prior version's claim.

Downstream rows MUST read paths and counts from this file and MUST NOT hardcode any
path this file contradicts. Where the vault/spec names a file that is not present on
this checkout, it is listed under **MISSING**.

## Population denominator

POPULATION_N: 974

`POPULATION_N` is the count of trade records in the engine trade population present
on this checkout (see `backtest_charts_12mo.json` below — 974 records, parsed). It is
the denominator for the whole version.

Note on naming: the omen-3.4 spec calls the engine trade population
`backtest_metrics_full.json` and places it at the repo root. That file does **not**
exist on this checkout (see MISSING). On this repo the engine writes one artifact per
run that is *both* the trade population *and* the 1-minute bar material — each record
is a trade carrying its embedded 1-min candles. The full 12-month run
(`backtest_charts_12mo.json`, 974 records) is the population used for POPULATION_N;
`backtest_charts.json` (793 records) is the earlier/30d-tagged run over the same
window. Prior docs quote this artifact as 875 / 1,289 / 1,982 / 2,061 / 63,520 trades;
those are not reconciled by argument here — the file on this checkout parses to 974.

## Engine trade population

- **`backtest_charts_12mo.json`** (full 12-month population; POPULATION_N source)
  - Path: `backtest_charts_12mo.json` (repo root)
  - Bytes: 3,292,869
  - Records (parsed): **974** trade/signal records
    - Traded A+/A/B (`alert_only=false`): 761 (A+ 13, A 55, B 693)
    - C-grade alert-only (`alert_only=true`): 213
  - Day range: 2025-07-14 .. 2026-07-10
  - Record fields: `symbol, day, setup, direction, grade, alert_only, outcome,
    htf_bias, entry, stop, target, exit_price, pnl, scaled, scale_level,
    runner_target, entry_i, exit_i, reason, levels, candles`
- **`backtest_charts.json`** (earlier/30d run, same window; NOT the POPULATION_N source)
  - Path: `backtest_charts.json` (repo root)
  - Bytes: 2,693,799
  - Records (parsed): **793** trade/signal records
    - Traded A+/A/B (`alert_only=false`): 620 (A+ 11, A 29, B 580)
    - C-grade alert-only (`alert_only=true`): 173
  - Day range: 2025-07-14 .. 2026-07-10
  - Same record schema as the 12mo file.

## Predicate module

See **MISSING** (`predicates.py`). No predicate module under any name exists on this
checkout (verified: `find` for `predicates*` and `grep -rln predicates` over the repo
return no source file).

## 1-minute bar material

- **`backtest_charts.json`** and **`backtest_charts_12mo.json`** (repo root)
  - Each trade record embeds its own 1-min candles in the `candles` field.
  - Embedded candles parsed:
    - `backtest_charts.json`: 32,142 candles across 793 records
    - `backtest_charts_12mo.json`: 39,394 candles across 974 records
  - See the engine-trade-population section above for byte sizes and record counts.
- **`.cache/`** (repo root) — cached 1-min bar downloads, one `.pkl` per symbol/date batch
  - Path: `.cache/`
  - Files (parsed): **61** `.pkl` files
  - Total bytes: 32,748,330
  - Structure (parsed): each `.pkl` is a `dict` with keys `days` (dict of date → list
    of 390 1-min RTH bars) and `hourly` (list of (timestamp, bar) tuples).
  - 1-min bars in `days` across all 61 files (parsed): **435,234**
  - Hourly bars across all 61 files (parsed): 26,474
  - Symbols covered (21): AAPL AMD AMZN AVGO COIN GOOG GOOGL HOOD INTC IREN META MSFT
    NFLX NVDA ORCL PLTR QQQ SMCI SOFI SPY TSLA

## Hand-marked corpus

See **MISSING** (`research/blind_marks_all.jsonl`).

## MISSING

The following files are named in the vault/spec docs but **do not exist on this
checked-out repo**. They are not git-tracked and do not appear in any branch or in
git history (all branches, including deleted-file history). They are absent from the
working tree.

- **`backtest_metrics_full.json`** (spec's name for the engine trade population;
  claimed at repo root) — MISSING. The real engine trade population on this checkout
  is `backtest_charts_12mo.json` (974 records) / `backtest_charts.json` (793 records);
  see above.
- **`predicates.py`** (predicate module; claimed at repo root) — MISSING. No
  predicate module exists under any name on this checkout.
- **`research/blind_marks_all.jsonl`** (hand-marked corpus) — MISSING. The only
  `.jsonl` files under `research/` are `archive_gaps.jsonl` and
  `discord_extracted/*.jsonl` (Discord extraction shards), none of which is a
  hand-marked trade corpus.

## Resolved-path summary (non-MISSING paths only; all verified to exist)

| Path | Bytes | Records (parsed) |
|------|------:|-----------------:|
| `backtest_charts_12mo.json` | 3,292,869 | 974 trade records |
| `backtest_charts.json` | 2,693,799 | 793 trade records |
| `.cache/` | 32,748,330 | 61 `.pkl` files / 435,234 1-min bars |

POPULATION_N: 974
