# OMEN 10.0 R1 -- the six fill arms, re-run on the current engine

Base `c13bdf8c`. Window `2024-09-04` to `2026-09-04` (two years ending at the last archived session on disk, computed from `data_archive/`, not hardcoded). Full pool: 29 symbols (MAJOR_15+INDEX_POOL+OTHER_POOL), 12123 symbol-days. Core pool: `universe.CORE_SYMBOLS` (11 symbols: TSLA, NVDA, AAPL, AMD, META, GOOGL, AMZN, MSFT, PLTR, QQQ, SPY), a subset of the same replay. Blind 2R exit (`OMEN_SCALE_PLAN=none`, fixing the stale `LADDER_MODE` attribute g90 set -- see script docstring), `STOP_ON_CLOSE=1`. $1,000 risk/trade. Signal set: fired, legacy engine grade != C, `reentry_84_rule` excluded -- identical definition to g90.

## The current engine's default fill

`entry_fill.ENTRY_FILL` defaults to `"close"` and `entry_fill_price(mode="close")` unconditionally returns the signal minute's own close -- no level, no clamping. `signal_runner.fill_price()` is a pure pass-through to that on the default path. **The current engine's default fill equals arm `close`, exactly** (not `as_booked`, which is the raw structural level, unconditionally -- a different price on almost every row). The `close` arm below is therefore never recomputed: every field is read off the real `SimTrade` the committed engine produced for that signal.

## Result -- core11 (11 symbols, 3629 signals)

| arm | trades | unfilled | win rate | mean R | avg win | avg loss | months | green months | $/day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| as_booked | 310 | 3319 | 59.0% | +0.7710 | +2.0000 | -1.0000 | 25 | 24/25 | $479 |
| limit_level | 252 | 3377 | 43.8% | +0.1931 | +2.0000 | -1.0000 | 25 | 16/25 | $98 |
| next_open | 3629 | 0 | 39.0% | +0.1718 | +2.0000 | -1.0000 | 25 | 22/25 | $1,250 |
| chase_once | 3095 | 534 | 31.1% | -0.0639 | +2.0000 | -1.0000 | 25 | 10/25 | $-397 |
| close | 3629 | 0 | 33.0% | -0.0063 | +2.0000 | -1.0000 | 25 | 13/25 | $-46 |
| mid_candle | 2963 | 666 | 43.4% | +0.1057 | +2.0000 | -1.0000 | 25 | 20/25 | $628 |

## Result -- full29 (29 symbols, 7857 signals)

| arm | trades | unfilled | win rate | mean R | avg win | avg loss | months | green months | $/day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| as_booked | 551 | 7306 | 58.4% | +0.7532 | +2.0000 | -1.0000 | 25 | 24/25 | $832 |
| limit_level | 443 | 7414 | 41.9% | +0.1499 | +2.0000 | -1.0000 | 25 | 17/25 | $133 |
| next_open | 7857 | 0 | 38.9% | +0.1690 | +2.0000 | -1.0000 | 25 | 23/25 | $2,660 |
| chase_once | 5421 | 2436 | 30.9% | -0.0695 | +2.0000 | -1.0000 | 25 | 8/25 | $-756 |
| close | 7857 | 0 | 32.7% | -0.0141 | +2.0000 | -1.0000 | 25 | 11/25 | $-221 |
| mid_candle | 6376 | 1481 | 43.1% | +0.0863 | +2.0000 | -1.0000 | 25 | 17/25 | $1,102 |

## g90's published table, for comparison (verbatim, not recomputed)

`2024-08-12 to 2026-08-11`, 29 symbols (MAJOR_15+INDEX_POOL+OTHER_POOL), 925 traded signals -- from `research/g90_fill_arms.md`.

| arm | trades | unfilled | win rate | mean R | months | green months | $/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| as_booked | 793 | 132 | 58.5% | +0.7552 | 25 | 25/25 | $1,443 |
| limit_level | 659 | 266 | 45.9% | +0.2760 | 25 | 21/25 | $438 |
| next_open | 925 | 0 | 41.8% | +0.2551 | 25 | 22/25 | $569 |
| chase_once | 785 | 140 | 35.1% | +0.0564 | 25 | 14/25 | $107 |
| close | 925 | 0 | 57.9% | +0.7382 | 25 | 25/25 | $1,645 |
| mid_candle | 742 | 183 | 47.0% | +0.2381 | 25 | 20/25 | $426 |

## Differences from g90, explained

**1. `close` moves from g90's +0.7382R / $1,645/day to -0.0141R / $-221/day (full29, this window) -- EXPLAINED, not a regression.** g90's `close` was silently the shipped ladder-B scale-out book (see the `LADDER_MODE`/`SCALE_PLAN` bug in this script's module docstring); this run is genuinely blind 2R for every arm including `close`. The two numbers answer different questions and should not be read as the same quantity moving.

**2. Trade counts differ from g90's for every arm -- EXPLAINED.** Two independent causes, both expected: (a) the window is different (g90: 2024-08-12 to 2026-08-11; here: the current two-year window computed from disk, above) -- a different set of trading days will produce a different number of signals on the same detector; (b) the engine itself has changed between g90's base and `c13bdf8c` (new flags, gates and fixes have landed in `signal_runner.py`/`backtest_week.py` in the interim per `CLAUDE.md`'s changelog) -- this row does not attempt to isolate which commits moved the count, only to price the current committed code.

**3. `entry_idx` mismatches: 1 of 7858 candidate rows (should be 0) -- FOUND, DIAGNOSED, does not change any book.** The one mismatch is `ACHR` `2026-04-06`, a `break_and_retest` B-grade signal at `09:50:00` (`t.entry=5.665`, `t.stop=5.63`, level `5.63`). Cause: this script correlates each `SimTrade` back to the captured signal dict that produced it by the tuple key `(signal_type, direction, round(entry, 4), status)`, consuming matches in `captured` order (`used[k]` counter) -- on this day two distinct ACHR signals share an identical rounded entry price under that key, so the counter paired this trade with the WRONG signal's candle id, and the recomputed `entry_idx` (16) disagreed with the trade's own recorded `entry_idx` (20). This is a correlation bug in THIS harness's bookkeeping, not in `signal_runner`/`backtest_week` -- `t.entry`/`t.stop`/`t.pnl` on the real trade are unaffected either way. The row is defensively `continue`d before being appended, so the effect on every book is that this ONE row (of 7858 candidates) is simply ABSENT from all 12 books rather than silently wrong -- 0.013% of the full29 signal set. Not fixed in this row (one change per row; the fix is a tie-break on entry TIME as well as price, which touches the matching loop -- a second change) -- documented, not silent.

**4. Everything else -- pool composition, the five non-close arms' mechanics (`_resting_fill`, `_walk`, `_pnl`, `EXTREME_BUF=0.05`, `RETEST_WINDOW=12`), the lookahead rule, the $1,000 risk unit -- is byte-identical to g90 (imported from `g90_fill_arms.py`, not reimplemented).

## Verify: close vs the engine's default

7857 rows checked against the raw archive tape, 0 mismatches -- PASS: 100% match. This is an INDEPENDENT check (`verify_close_matches_default`), not a tautology: for every row it re-opens the raw archive CSV for that symbol/day and confirms `committed_entry` equals the entry minute's own printed close -- the exact quantity `entry_fill.entry_fill_price(mode="close")` returns and `signal_runner.fill_price()` passes through unmodified on the default path. The same method runs standalone, and exits nonzero on any mismatch, as `research/g210_verify.py` (also re-derives `next_open`/`limit_level` on 20 sampled trades from raw bars): `python research/g210_verify.py` -> `PASS: next_open/limit_level match raw bars on 20 sampled rows; close matches the engine's default fill on 7857/7857 rows (100%).`

## Hand-verification: 20 sampled next_open / limit_level fills against raw archive bars


**next_open** (10 of 7857 filled rows sampled):

| symbol | day | minute | bar O/H/L/C | booked fill | match |
|---|---|---|---|---:|---|
| CRM | 2025-05-02 | 10:27 | 274.9900/275.1000/274.9050/275.0250 | 274.9900 | YES |
| AVGO | 2025-01-30 | 10:03 | 218.0000/218.0000/216.9900/217.0350 | 218.0000 | YES |
| AMZN | 2024-12-03 | 10:08 | 211.8501/211.9200/211.7917/211.9114 | 211.8501 | YES |
| ACHR | 2026-01-16 | 09:45 | 8.8295/8.9397/8.8295/8.9350 | 8.8295 | YES |
| HOOD | 2026-01-05 | 10:46 | 121.1300/121.3000/121.0650/121.2700 | 121.1300 | YES |
| INTC | 2026-05-07 | 10:21 | 113.5800/114.2500/113.5406/114.0350 | 113.5800 | YES |
| MSFT | 2026-06-26 | 09:39 | 360.9950/361.7188/360.9300/361.4400 | 360.9950 | YES |
| ORCL | 2025-11-17 | 10:25 | 219.0900/219.0900/218.4900/218.6002 | 219.0900 | YES |
| PLTR | 2026-07-07 | 09:49 | 134.5100/134.7350/134.4400/134.5700 | 134.5100 | YES |
| TSLA | 2025-01-22 | 09:39 | 423.9001/424.7200/422.9100/423.6300 | 423.9001 | YES |

**limit_level** (10 of 443 filled rows sampled):

| symbol | day | minute | bar O/H/L/C | booked fill | match |
|---|---|---|---|---:|---|
| CRM | 2025-07-17 | 10:46 | 257.2000/257.4200/257.2000/257.4100 | 257.4000 | YES |
| BABA | 2025-03-03 | 10:37 | 132.9300/132.9550/132.6800/132.7900 | 132.8000 | YES |
| AMZN | 2025-08-28 | 11:00 | 231.4400/231.5070/231.2900/231.4238 | 231.4100 | YES |
| IWM | 2024-10-14 | 10:19 | 221.4800/221.4900/221.1800/221.1800 | 221.3600 | YES |
| GOOGL | 2026-05-28 | 10:53 | 388.9050/389.1050/388.8300/388.9900 | 388.9800 | YES |
| MSFT | 2025-01-16 | 09:54 | 425.7100/426.4100/425.6200/426.2950 | 426.3400 | YES |
| MU | 2024-10-02 | 10:14 | 101.0500/101.1000/100.7900/100.9000 | 100.9900 | YES |
| NVDA | 2025-08-08 | 10:55 | 182.5500/182.5850/182.3500/182.4900 | 182.4300 | YES |
| QQQ | 2025-07-10 | 10:45 | 554.4400/554.5600/554.2400/554.2700 | 554.2600 | YES |
| TSLA | 2026-07-27 | 10:07 | 308.5100/309.1900/308.3401/308.6200 | 308.8600 | YES |

## What else changed between g90's run and now

**`RETEST_REQUIRED` defaults ON** (`signal_runner.RETEST_REQUIRED` reads `os.getenv("RETEST_REQUIRED", "1")`, currently `True`), shipped 2026-09-02 (`CLAUDE.md`) -- AFTER g90's 2026-08-11-window run. Both this row and g90 ran with whatever `RETEST_REQUIRED` defaulted to at the time, i.e. this run has a gate g90's did not. It changes which signals `signal_runner` fires (and therefore the whole signal set priced below) -- it is folded into cause (b) of item 2 above (the engine changed between the two runs), named here explicitly because the spec calls it out by name.

**`DISASTER_STOP` asymmetry, restated plainly.** `close` can book a disaster stop-out (a resting -1R touch, `backtest_week.py`'s own per-bar loop) that the other five arms' shared `_walk` implementation has no equivalent for -- `_walk` only checks a close-based structural stop and the 2R target, never an intrabar touch. So `close`'s losses can be capped at -1.000R intrabar while the other five arms' losses are only capped at whatever the next closed candle prints, which can be worse than -1R. This is inherited from g90 unchanged (out of this row's one-change scope) and is the same asymmetry `CLAUDE.md`'s "Rules that hold everywhere" section documents for `stop_rule.py` in general.

**Size gate: NOT applied.** `signal_runner.min_risk_floor` (`max(0.10, 0.0015 x close)`) is never called in this script's arm loop -- the only risk check is `if risk <= 0`. So every number in both tables above is the UNSIZED arithmetic CLAUDE.md warns about ("Ungated, the g87 sweep printed $15,119/day -- arithmetic, not money"): a fill landing a cent from its stop is not excluded, and would size to an unrealistic position under `$1,000` fixed risk. g90 did not apply this gate either (inherited, not new). Applying it is a second change (touches the per-arm risk computation, which would move every trade count and therefore require re-running the hour-long replay) and is out of this row's one-change scope -- flagged here rather than left silent, per the size-gate rule. A follow-up row should re-run `g210_fill_arms_v2.py` with a `risk < sr.min_risk_floor(entry)` exclusion added to the arm loop and republish both tables.

## What could not be done in this row

Nothing was cut for time in this run. Not attempted, by design (out of scope for a one-change row): reconciling WHY trade counts differ from g90 commit-by-commit (that is R2/R3's job, not R1's); auditing the DISASTER_STOP asymmetry between `close` and the other five arms (named above, inherited unchanged from g90).

## Reproduce

```
python research/g210_fill_arms_v2.py --procs 8
```

Window and pools are computed from `data_archive/` at run time, not passed as flags -- re-running after the archive advances will move the window forward.

Verify: `python research/g210_verify.py` (exits nonzero on any mismatch; PASS as of this row -- see above).

Every book below carries `research/book_stamp.py`'s identity block (commit, dirty-engine flag, every behaviour-changing flag's effective value, window, script) under its `meta.stamp` key, alongside `meta.entry_fill`/`meta.pool`/`meta.signals`/`meta.traded`/`meta.window` -- `gzip.open(path, "rt")` + `json.load` then read `["meta"]`.

Books written:

- `research\tape\fillarms_as_booked_core11.json.gz`
- `research\tape\fillarms_limit_level_core11.json.gz`
- `research\tape\fillarms_next_open_core11.json.gz`
- `research\tape\fillarms_chase_once_core11.json.gz`
- `research\tape\fillarms_close_core11.json.gz`
- `research\tape\fillarms_mid_candle_core11.json.gz`
- `research\tape\fillarms_as_booked_full29.json.gz`
- `research\tape\fillarms_limit_level_full29.json.gz`
- `research\tape\fillarms_next_open_full29.json.gz`
- `research\tape\fillarms_chase_once_full29.json.gz`
- `research\tape\fillarms_close_full29.json.gz`
- `research\tape\fillarms_mid_candle_full29.json.gz`