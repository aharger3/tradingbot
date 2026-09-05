Live bars now flow again: one batched yfinance call per scan replaces the
per-symbol fallback, and a real dry run gets bars for all 29 pool symbols
(was 0).

## Before

`journal/scanner-2026-09-04.log` / `journal/scanner_status.json` from that
day: `"bars_fetched": 0` out of the full pool. Tastytrade was down (401
invalid_credentials, unfixed per CLAUDE.md), and the per-symbol
`_yf_recent_bars` fallback in `live_scanner.py` made one `yf.Ticker(...).history()`
HTTP call per symbol per scan — on that day every one of them came back
empty, so the scan loop saw zero bars and fired nothing.

## What changed

`live_scanner.py`:
- New `_yf_batch_recent_bars(symbols, lookback_minutes=60)`: one
  `yf.download(symbols, period="1d", interval="1m", group_by="ticker",
  threads=False)` call for every symbol that needs the fallback this cycle
  (not one call per symbol), sliced per symbol out of the returned
  MultiIndex frame into `Candle` lists. Cached 55s (`_YF_BATCH_CACHE`) so a
  scan loop faster than that reuses the same pull instead of re-fetching.
  Retries once with a 5s backoff on `Too Many Requests`, then gives up
  cleanly (empty list per symbol, not a hung scan).
- `scan_once`'s fetch loop now does two passes: (1) try Tastytrade per
  symbol, collecting the failures; (2) ONE `_yf_batch_recent_bars` call for
  all of them. Tastytrade-first behavior is unchanged — a symbol Tastytrade
  serves never touches yfinance at all.
- `scanner_status.json.bars_fetched` unchanged in meaning: count of symbols
  with >=1 candle this cycle, out of `len(symbols)`.
- `_yf_recent_bars` (single-symbol, unbatched) is untouched and still backs
  the QQQ-only break check (`compute_qqq_breaks`) — that path fetches one
  symbol, batching buys nothing there.

## After — real dry run, 2026-09-05 (Saturday; yfinance's `period="1d"`
returns the most recent session's bars regardless of what day it's queried)

`python live_scanner.py --paper --once --window 09:30-11:00`, full 29-symbol
pool (`universe.MAJOR_15 + INDEX_POOL + OTHER_POOL`):

- Tastytrade: `401 invalid_credentials` on every symbol (the known L2 outage,
  untouched by this row) — all 29 queued for the yfinance batch.
- All 29 symbols printed a PDH/PDL/HTF context line (proof bars arrived);
  `journal/scanner_status.json` after the run:
  `"bars_fetched": 29`, `"symbols_scanned": 29`, `"last_error": null`.
- 0 signals fired this cycle (single scan, no setups on the bar in view —
  expected, not a bug; this row is about bars arriving, not about firing).

| | before (09-04 log) | after (dry run, 09-05) |
|---|---:|---:|
| bars_fetched | 0 / 29 | **29 / 29** |
| last_error | (0 bars, no signals possible) | None |

`--replay 2026-09-04` was not usable for this check: `ReplayFeed` reads
archived bars via `polygon_feed`, and `data_archive` has been `403
NOT_AUTHORIZED` since 2026-08-27 (CLAUDE.md) — it has no 09-04 data to
replay regardless of this fix. The live `--paper --once` dry run above is the
substitute the row itself offers ("or the clock forced").

## Verify

- `python research/test_live_batch_fetch.py` — 7 tests, mocks `yfinance.download`
  (no network): one batched call per scan for a multi-symbol failure set,
  correct per-symbol slicing, a symbol missing from the returned frame maps
  to `[]` rather than raising, cache hit inside 55s / miss after TTL, one
  retry on `Too Many Requests` then a clean give-up, and an integration test
  that `scan_once` with an all-failing Tastytrade feed makes exactly one
  batched yfinance call for 3 symbols. **Exit 0.**
- `python research/regression_gate.py` — PASS, no baseline-fired mark went
  silent.
- `python research/test_runner_stop.py` — 70 checks across 3 sections, all
  pass.
