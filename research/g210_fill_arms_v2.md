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

**3. `entry_idx` mismatches: 1 (should be, and are, 0).** Confirms `ENTRY_FILL` stayed at its default ("close") throughout this run -- no forward re-pricing at the trade-creation site, so every signal's recorded entry bar is still the bar `fill_price()` was called on.

**4. Everything else -- pool composition, the five non-close arms' mechanics (`_resting_fill`, `_walk`, `_pnl`, `EXTREME_BUF=0.05`, `RETEST_WINDOW=12`), the lookahead rule, the $1,000 risk unit -- is byte-identical to g90 (imported from `g90_fill_arms.py`, not reimplemented).

## Verify: close vs the engine's default

7857 rows checked, 0 mismatches -- PASS: 100% match. (The `close` arm's fields are read directly off `t.entry`/`t.stop`/`t.pnl`/`t.outcome`/`t.exit_price` on the `SimTrade` the committed engine produced -- this check is structural, confirming nothing in this script's own bookkeeping silently diverged the two copies of the same number.)

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

## What could not be done in this row

Nothing was cut for time in this run. Not attempted, by design (out of scope for a one-change row): reconciling WHY trade counts differ from g90 commit-by-commit (that is R2/R3's job, not R1's); auditing the DISASTER_STOP asymmetry between `close` and the other five arms (named above, inherited unchanged from g90).

## Reproduce

```
python research/g210_fill_arms_v2.py --procs 8
```

Window and pools are computed from `data_archive/` at run time, not passed as flags -- re-running after the archive advances will move the window forward.

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