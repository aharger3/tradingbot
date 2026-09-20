# Monday 2026-09-21 09:25 ET preflight

| # | check | result | evidence |
|---|---|---|---|
| 1 | OmenSignalBot scheduled task | GREEN | Action → `run_daily.ps1` (exists). Trigger weekdays 09:25 ET, DaysOfWeek=62. RunLevel Limited, UserId aharg. NextRunTime Mon 09/21 09:25. LastTaskResult 267014 (SCHED_S_TASK_TERMINATED) is **by design**: main loop never self-exits past MANAGE_END (sleeps 60s forever); ExecutionTimeLimit PT8H kills it — 09/18 log starts 09:25, file mtime 17:25, exactly 8h. Not an error. |
| 2 | `python -c "import live_scanner"` | GREEN | Same python313 + `PYTHONIOENCODING=utf-8` as the task. Prints `adopted flags: none`. No ImportError. |
| 3 | Alpaca paper wiring | GREEN | `research/test_alpaca_wiring.py` — 9/9 passed. `.env` has `ALPACA_PAPER_KEY`/`ALPACA_PAPER_SECRET` (names confirmed, values not read); log line `AlpacaBroker: ALPACA_PAPER_KEY/SECRET loaded from .env (override)`. |
| 4 | `journal/alpaca-paper.jsonl` | GREEN | File writable (touch/rm round-trip ok). Last rows are the 09/16 wiring dry-fire + an ORCL entry/cancel — no real legacy fills yet, expected: Monday is the first session `ENGINE_LEGACY_PAPER` trades for real. |
| 5 | Data sources | YELLOW (informational) | yfinance: single AAPL 1m pull hit `YFRateLimitError` just now (transient, re-test at open). **Tastytrade auth is currently working** — 09/18 log shows `Access token obtained`, `Connected. 2 account(s)`, and real HTF bias (bullish/bearish/neutral) on all 29 symbols. This contradicts the "Tastytrade 401" premise in this task, which traces to a stale 2026-09-01 CLAUDE.md note — **HTF bias will NOT be "unknown" Monday** unless auth regresses overnight. Polygon 403-on-current-day is old/known and already worked around (`archive_1m.py --back 1`, bug B-09, fixed). |
| 6 | v5_session_counter + task | GREEN (premise corrected) | No standalone `OmenV5SessionCounter` task exists — it was **retired today (2026-09-20)** and folded into `OmenNightlyLoop` → `nightly_loop.run_v5_session_counter()` (see nightly_loop.py:219 comment). OmenNightlyLoop last ran today 07:54, LastTaskResult 0. `python research/v5_session_counter.py --test` passes. |
| 7 | Dry rehearsal (synthetic legacy g88 fire) | GREEN | `live_scanner.py --replay` exists but never constructs a broker (replay must never place orders), so it can't exercise `flatten_legacy`. Used `research/test_v5_undry.py` instead: synthetic TSLA signal books `{event:entry, legacy:True, entry_rule:g88, dry:False}` against a FakeBroker, then `flatten_legacy()` cancels 1 stale order + flattens 1 filled position. Also confirms `ENGINE_LEGACY_PAPER=0` kill switch. 4/4 passed. |

## Adopt-flags sanity
`research/tape/shipped_flags.json` has 2 rows (`BNR_DISPLACEMENT_GATE`, `SCALE_PLAN`), both `adopt: false` — `load_and_apply()` sets nothing, confirmed by "adopted flags: none" on every import/test run above.

## Noted, not fixed (pre-existing, out of scope)
The scan loop's forever-sleep past MANAGE_END means `run_daily.ps1`'s later steps (`archive_1m.py`) likely never run under normal 8h-limit termination — consistent with the already-documented "data_archive stopped 2026-08-27." Not caused by tonight's changes; design/rules-level, left for a human call. `research/loop_cycle.py` has an unrelated uncommitted local diff (+15/-1) from research activity — untouched.
