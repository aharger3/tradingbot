# Corpus Engine Entries (T3)

Detection run over every covered `(symbol, day)` from the merged coverage set
(`research/corpus_bar_coverage.md`, covered total = **3595** distinct symbol-days
across 28 symbols — the denominator T4 divides by).

## Detection entry point

Detection was NOT reimplemented. The entry point called is
**`backtest_week.simulate_day(symbol, day_iso, candles, pdh, pdl, bias, pmh, pml,
pdo, pdc, qqq=...)`** — the exact function `backtest_12mo.py` calls internally in
its per-day loop (backtest_12mo.py:141). `simulate_day` wraps
`SignalRunner.detect_signals` (via the `BacktestRunner` it constructs) and replays
the session bar-by-bar, so it is the engine's real detection path. A trade is
recorded only when `t.status == "fired"` (an entry the engine would actually
take); D-grade / tight-stop skips and alert-only signals are excluded.

The per-day inputs (`pdh`/`pdl`/`pdo`/`pdc` from the prior trading day,
`htf_bias_for` SMA20 of resampled hourly closes, premarket hi/lo, QQQ
key-level breaks) are wired identically to `backtest_12mo.py`. Each covered day
was run with the 6 trading days before it fetched for context (enough for the
>=20 hourly closes `htf_bias_for` needs and for the real prior trading day's
levels); this was validated bit-identical to a full-window fetch on AAPL
(25/25 entries match, multiset-equal).

## `minute_i` convention (the trap)

`minute_i` is **minutes since 09:30** in the T1 frame, computed as
`int(HH)*60 + int(MM) - 570` from the fired trade's `entry_time` timestamp
(`SimTrade.entry_time`, format `HH:MM:SS`), which is the bar timestamp the
signal fired on. This is NOT `entry_i`. In `research/*_charts.json` an `entry_i`
field indexes that chart's `candles` array (a windowed slice); that index is
NOT minutes since 09:30 and is chart-specific. Here we emit the absolute
minutes-since-09:30 frame directly from the bar timestamp, so it joins against
T1 without any per-chart offset arithmetic.

## Results

- **Total engine entries: 417**
- **Distinct symbol-days with >=1 entry: 380** (of 3595 covered; 3215 covered
  symbol-days produced no fired entry)

## Grade distribution

| grade | count |
|---|---|
| A+ | 4 |
| A | 23 |
| B | 298 |
| C | 92 |

Total: 417

## Entries per symbol

| symbol | entries | symbol | entries |
|---|---|---|---|
| AAPL | 25 | META | 22 |
| AMD | 62 | MSFT | 17 |
| AMZN | 21 | MU | 19 |
| ARM | 2 | NFLX | 2 |
| AVGO | 3 | NVDA | 50 |
| COIN | 3 | ORCL | 6 |
| GOOGL | 8 | PLTR | 18 |
| HOOD | 10 | QCOM | 1 |
| INTC | 12 | QQQ | 23 |
| IREN | 1 | SMCI | 1 |
| SPY | 14 | TSLA | 94 |
| TSM | 2 | | |

BABA, IWM, SOFI, UBER produced 0 fired entries (few covered days / no setups
cleared the fired gate).

Per-line records live in `research/corpus_engine_entries.jsonl`, one JSON object
per entry with `symbol`, `day`, `minute_i`, `direction`, `grade`, `entry`,
`stop`, `target`, `setup`.
