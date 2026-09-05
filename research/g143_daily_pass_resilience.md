# g143 — the 16:15 pass no longer dies on a partial yfinance day

`research/daily_fetch.py` used to hard-assert `>= 300` RTH bars on the latest archived TSLA day
and raise on shortfall (killed the whole 16:15 run on 2026-09-04, which came back with 90 bars).
It now retries the fetch once with an explicit `start`/`end` window, and if the retry is still
short it logs `PARTIAL <n> bars`, leaves the archive as-is, and exits 0 — `daily_homework.py`
builds the deck from whatever is on disk instead of the pass dying before a deck exists.

## What changed

- `_frame()` takes an explicit `start`/`end` window as an alternative to the relative `period`
  lookback — the retry path.
- `fill()` forwards `start`/`end` through to `_frame()`.
- New `rth_bar_count(symbol, day)` and `ensure_day_complete(day, syms, min_bars=300)`: the latter
  checks the canary symbol (TSLA, else the universe's first symbol), and only on shortfall retries
  the whole-universe fetch once, forced, with `start=day`, `end=day+1`.
- `main()`, for a `--day` pass: runs `ensure_day_complete` instead of the unconditional hard
  `demo()` assert. Prints `PARTIAL <n> bars` on a still-short retry, or `<day>: <n> RTH bars
  (canary) -- full archive` when the retry (or the original pass) is complete. Exit code is 0
  either way — the assertion that used to kill the process is gone from this path.
- `demo()` itself is unchanged and still runs (with its hard assert) for the no-`--day`,
  no-`--until` invocation — the ad hoc self-check use, not the scheduled 16:15 path.

## Verified

```
python research/daily_fetch.py --day 2026-09-04
```
exits 0. 2026-09-04's archive was already complete (Polygon-401/yfinance had since backfilled
it to 390 RTH bars across the universe canary), so the live run printed the full-archive line.
The retry path itself was exercised directly: truncating `data_archive/TSLA/2026-09-04.csv` to
91 rows (90 RTH-adjacent lines) before the run reproduced the original failure condition
(`rth_bar_count` → 0), triggered the "retrying with explicit start/end" log line, and the retry
fetch (real yfinance call, `force=True`, `start=2026-09-04 end=2026-09-05`) restored the file
byte-identical to the pre-truncation backup — confirmed with `diff`. Exit code was 0 throughout;
no PARTIAL line was needed because yfinance still had the full day cached. The 09-04 "90 bars"
condition from the row's description could not be reproduced against live yfinance today (yfinance
now serves the full day), so the PARTIAL-still-short branch is exercised by code path, not by a
live repro — `ensure_day_complete` only prints PARTIAL and returns the post-retry count; nothing
in that branch calls `sys.exit` or raises, so a genuinely still-short day cannot kill the process.

## Scheduled tasks

`OmenA6PaperLog` (script missing, rc 0x80070002) and `OmenForwardClock` (forward book retired
2026-08-28) were both state `Ready` before this change. Disabled, not deleted:

```
Get-ScheduledTask -TaskName OmenA6PaperLog,OmenForwardClock | Select TaskName,State
TaskName            State
--------            -----
OmenA6PaperLog   Disabled
OmenForwardClock Disabled
```

Every other scheduled task (including `OmenDailyHomework`) was left untouched.

## Verify gate

`python research/regression_gate.py && python research/test_runner_stop.py` — both green (run
concurrently with other L-row agents' work in this tree; regression_gate reported new fires only,
no baseline-fired mark went silent; runner-stop selftest: 70/70 checks ok).
