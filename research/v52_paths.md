# OMEN 5.2 — path map (T1 discovery file)

Every later row is a fresh context and learns the repo only from this file.
Each path below was confirmed to exist with `os.path.exists` and each
`module.function` was opened and read before writing. Repo-relative, run from
the repo root.

bars_loader: research.levels.load_rth_bars
bars_cache: data_archive
backtest_trades: backtest_charts.json
grade_fn: signal_runner.compute_austin_tier

## What each line is

- **bars_loader** — `research/levels.py :: load_rth_bars(symbol, day)` returns
  the RTH (>=09:30) 1-min OHLCV bars for a symbol+date as a list of
  `{t, o, h, l, c}` dicts, read from `data_archive/<SYMBOL>/<YYYY-MM-DD>.csv`.
  Returns `None` if the day is absent. Confirmed at `research/levels.py:52`.
- **bars_cache** — `data_archive/` at the repo root: one `<SYMBOL>/` subdir
  per symbol, each holding `<YYYY-MM-DD>.csv` 1-min files (e.g.
  `data_archive/TSLA/2024-01-02.csv`). `data_archive` is a directory.
- **backtest_trades** — `backtest_charts.json` at the repo root: a JSON array
  of the engine's per-trade records, each carrying `symbol, day, setup,
  direction, grade, entry, stop, target, exit_price, entry_i, exit_i, candles`
  (the embedded `candles` field carries that trade's 1-min bars). This is the
  per-trade ledger `research/backtest_churn.py` loads as "the live backtest
  trade set" (`CURRENT_BACKTEST = REPO_ROOT / "backtest_charts.json"`).
  The full 1,289-trade engine run is summarised in `backtest_metrics_full.json`
  (`overall.trade_count == 1289`); the candle-bearing ledger here is the subset
  that carries bar paths, and is the corpus T5 replays exits over.
- **grade_fn** — `signal_runner.py :: compute_austin_tier(sig, candles,
  fired_ideas, htf_bias) -> str` assigns Austin's tier to a signal: returns
  `"S"`, `"A"` or `"C"` (never X). All four S-clauses -> S; clause 1 with 1-2
  failures -> A; otherwise C. Confirmed at `signal_runner.py:752`.

## Path-existence checks (run before writing this file)

- `os.path.exists("research/levels.py")` -> True
- `os.path.isdir("data_archive")` -> True
- `os.path.exists("backtest_charts.json")` -> True
- `os.path.exists("signal_runner.py")` -> True
