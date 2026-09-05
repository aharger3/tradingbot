# OMEN 10.0 R1 -- the six fill arms, re-run on the current engine

Base `c13bdf8c`-era code; the replay actually ran at HEAD `57f2fbd2` (six non-engine `.py` files dirty at build time per the books' own stamps -- no engine file differs between `c13bdf8c` and `57f2fbd2`, so no number below moves, but the report should have named the commit it built on and did not; corrected here per the referee, see "Refereed" section below). Window `2024-09-04` to `2026-09-04` (two years ending at the last archived session on disk, computed from `data_archive/`, not hardcoded). Full pool: 29 symbols (MAJOR_15+INDEX_POOL+OTHER_POOL), 12123 symbol-days. Core pool: `universe.CORE_SYMBOLS` (11 symbols: TSLA, NVDA, AAPL, AMD, META, GOOGL, AMZN, MSFT, PLTR, QQQ, SPY), a subset of the same replay. Blind 2R exit (`OMEN_SCALE_PLAN=none`, fixing the stale `LADDER_MODE` attribute g90 set -- see script docstring), `STOP_ON_CLOSE=1`. $1,000 risk/trade. Signal set: fired, legacy engine grade != C, `reentry_84_rule` excluded -- identical definition to g90.

## The current engine's default fill

`entry_fill.ENTRY_FILL` defaults to `"close"` and `entry_fill_price(mode="close")` unconditionally returns the signal minute's own close -- no level, no clamping. `signal_runner.fill_price()` is a pure pass-through to that on the default path. **The current engine's default fill equals arm `close`, exactly** (not `as_booked`, which is the raw structural level, unconditionally -- a different price on almost every row). The `close` arm below is therefore never recomputed: every field is read off the real `SimTrade` the committed engine produced for that signal.

**Correction (see "Refereed" section below): the headline ranking in the two tables immediately below is REFUTED.** The `close` arm is exited by the real `backtest_week.simulate_day` (an intrabar DISASTER_STOP touch can end it); the other five arms are exited by `g90_fill_arms._walk` (a close-only structural stop, no intrabar touch of any kind). The tables therefore price six fills under two different exit models, not one exit model across six fills -- do not read `next_open`'s edge over `close` as a fill difference. Also: `win rate` below is FILLED win rate (wins / (wins+losses), scratches excluded from the denominator), not per-trade win rate; `avg win`/`avg loss` read a tautological +2.0000/-1.0000 on every arm because `_walk` returns exactly the target or exactly the stop by construction and the "scratch" rows (which can lose far more than -1R under `_walk`, e.g. `mid_candle`'s worst row is -75.5491R) are excluded from both columns. Honest versions of both, plus the size-gated table CLAUDE.md's size-gate rule calls for, are in the "Refereed" section.

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

**1. `close` moves from g90's +0.7382R / $1,645/day to -0.0141R / $-221/day (full29, this window) -- EXPLAINED, not a regression.** g90's `close` was silently the shipped ladder-B scale-out book (see the `LADDER_MODE`/`SCALE_PLAN` bug in this script's module docstring). **Correction (referee, e5a9ed7f): the header's claim that this row's `close` is "blind 2R exit" is also not quite right.** `close` is read straight off the real `SimTrade` (per this file's own "current engine's default fill" section above), so it is exited by `backtest_week.simulate_day`'s real per-bar loop -- with `OMEN_SCALE_PLAN=none` that loop no longer scales out, but its `DISASTER_STOP` (an intrabar -1R touch) is still live and is not gated by `SCALE_PLAN`. The other five arms never touch `simulate_day`'s loop at all -- they are exited entirely by this script's own `_walk`, which only checks a close-based structural stop and the 2R target. Repricing `close` on `_walk` instead (removing the disaster stop, holding everything else fixed) moves it from -0.0141R/-$221/day to +0.1547R/+$2,437/day on full29 and from -0.0063R/-$46/day to +0.1566R/+$1,139/day on core11 (475 of 7857 rows flip) -- 92% of the published next_open-over-close gap is this exit difference, not the fill. See "Refereed" section.

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

**`DISASTER_STOP` asymmetry, restated plainly -- DIRECTION CORRECTED (referee, e5a9ed7f).** The first draft of this paragraph said `close`'s losses are capped at -1.000R while the other five arms' can be worse. That is backwards. Measured off the actual books: `as_booked`, `next_open`, `chase_once` and `close` have ZERO rows worse than -1.000R in either pool. Only `limit_level` (28 of 443 full29 rows, worst -3.9865R, QQQ 2025-03-05) and `mid_candle` (573 of 6376 full29 rows, worst -75.5491R, AMD 2026-04-24 -- a single row that alone contradicts CLAUDE.md's "max loss is -1R hard") go past -1R, and they get there through `_walk`'s "scratch" path (a closed-back structural stop that can gap far past the level), not through any disaster stop. The real asymmetry is the opposite of what was written: `close` is the ONLY arm exposed to an intrabar disaster-stop touch (because it alone runs through `simulate_day`'s real loop); the other five never see one, and `limit_level`/`mid_candle` can still lose more than -1R anyway via `_walk`'s scratch path. This is inherited from g90 unchanged (out of this row's one-change scope) and is the same asymmetry `CLAUDE.md`'s "Rules that hold everywhere" section documents for `stop_rule.py` in general -- but the direction stated there does not transfer to this script's `_walk`-priced arms without checking, which is what this correction does.

**Size gate: NOT applied in the replay; applied here, after the fact, from the already-written books (referee, e5a9ed7f -- see "Refereed" section).** `signal_runner.min_risk_floor` (`max(0.10, 0.0015 x close)`) is never called in `g210_fill_arms_v2.py`'s arm loop -- the only risk check there is `if risk <= 0`, so the two headline tables above are the UNSIZED arithmetic CLAUDE.md warns about ("Ungated, the g87 sweep printed $15,119/day -- arithmetic, not money"): a fill landing a cent from its stop is not excluded, and would size to an unrealistic position under `$1,000` fixed risk. g90 did not apply this gate either (inherited, not new). Re-running the replay WITH the gate wired into the arm loop is still a second change and out of this row's scope (it would move every trade count and require the hour-long replay again). What `research/r1_repair.py` (this repair) DOES do without a rerun: read the 12 already-written books and exclude any row where `abs(entry-stop) < max($0.10, 0.0015 x entry)` (using the booked `entry` as the stand-in for the candle close `min_risk_floor` actually reads -- the books do not carry the raw candle), then recompute mean R / $/day / green months on what is left:

| pool | arm | trades (sized) | mean R (sized) | $/day (sized) | green/months (sized) |
|---|---|---:|---:|---:|---:|
| core11 | as_booked | 94 | +0.6277 | $118 | 14/25 |
| core11 | limit_level | 78 | +0.2425 | $38 | 12/24 |
| core11 | next_open | 2810 | +0.1718 | $967 | 21/25 |
| core11 | chase_once | 2504 | -0.0563 | $-282 | 10/25 |
| core11 | close | 2856 | -0.0147 | $-84 | 11/25 |
| core11 | mid_candle | 1492 | +0.1715 | $513 | 20/25 |
| full29 | as_booked | 187 | +0.4439 | $166 | 15/25 |
| full29 | limit_level | 160 | +0.0165 | $5 | 11/25 |
| full29 | next_open | 6428 | +0.1704 | $2,195 | 22/25 |
| full29 | chase_once | 4686 | -0.0657 | $-617 | 9/25 |
| full29 | close | 6581 | -0.0083 | $-109 | 12/25 |
| full29 | mid_candle | 3472 | +0.1293 | $900 | 21/25 |

This confirms the referee's own recompute exactly (`as_booked` full29 $832->$166, `limit_level` $133->$5, `next_open` $2,660->$2,195). Two of the six arms' verdicts flip sign or lose most of their green months once sized: `as_booked` full29 loses 9 green months (24->15) and 78% of its $/day; `limit_level` full29 falls from $133 to $5/day and 17->11 green months. Script: `research/r1_repair.py`, run against the same 12 stamped books, no rerun of the replay.

**Honest avg win / avg loss and per-trade win rate (referee, e5a9ed7f -- also from `research/r1_repair.py`, no rerun):**

| pool | arm | avg win | avg loss | per-trade win% | worst loss (R) | rows < -1.000R |
|---|---|---:|---:|---:|---:|---:|
| core11 | as_booked | +2.0000 | -1.0000 | 59.0% | -1.0000 | 0 |
| core11 | limit_level | +2.0000 | -1.0559 | 40.9% | -3.9865 | 17 |
| core11 | next_open | +1.9888 | -0.9989 | 39.2% | -1.0000 | 0 |
| core11 | chase_once | +1.9853 | -0.9980 | 31.3% | -1.0000 | 0 |
| core11 | close | +1.9881 | -0.9990 | 33.2% | -1.0000 | 0 |
| core11 | mid_candle | +1.9963 | -1.1509 | 39.9% | -75.5491 | 239 |
| full29 | as_booked | +2.0000 | -1.0000 | 58.4% | -1.0000 | 0 |
| full29 | limit_level | +2.0000 | -1.0469 | 39.3% | -3.9865 | 28 |
| full29 | next_open | +1.9817 | -0.9973 | 39.1% | -1.0000 | 0 |
| full29 | chase_once | +1.9817 | -0.9971 | 31.1% | -1.0000 | 0 |
| full29 | close | +1.9823 | -0.9980 | 33.0% | -1.0000 | 0 |
| full29 | mid_candle | +1.9942 | -1.1467 | 39.3% | -75.5491 | 573 |

`avg win`/`avg loss` above include every row `_walk` labelled "scratch" in whichever column its own R multiple belongs to (positive scratches, if any, in avg win; the rest in avg loss) rather than excluding them, which is why `limit_level` and `mid_candle` now show an avg loss worse than -1.0000 instead of the tautological -1.0000 the original tables printed. `per-trade win%` divides wins by ALL filled rows (win + loss + scratch), not by (win+loss) only -- it reads materially lower than the "win rate" column in the two headline tables above for every arm with scratches (e.g. `limit_level` full29: 41.9% filled-only vs 39.3% per-trade).

## Refereed

The referee (`research/r1_referee.md`, `research/r1_referee.py`, commit `e5a9ed7f`) verified every mechanic in this row -- both fills reproduce independently on 100% of sampled rows, `close` matches the raw archive tape on 7857/7857 rows, the ACHR entry_idx mismatch reproduces exactly, the SCALE_PLAN/LADDER_MODE diagnosis is correct, `g210_verify.py` passes, no mark file was touched, one change per row was respected -- **but refuted the row's headline ranking**: the six-arm table compares `close` (exited by the real `simulate_day`, which still runs its DISASTER_STOP intrabar-touch check under `OMEN_SCALE_PLAN=none`) against the other five arms (exited by `_walk`, a close-only structural stop with no intrabar check at all). That single exit-model difference is 92% of the published next_open-over-close gap (475/7857 rows flip on full29 when `close` is repriced on `_walk`, moving it from -0.0141R/-$221/day to +0.1547R/+$2,437/day).

**Fixed in this repair, without a rerun (`research/r1_repair.py`, driven off the same 12 stamped books):**
- Base commit disclosed: `57f2fbd2`, not `c13bdf8c` (6 dirty non-engine `.py` files at build time; no engine file differs between the two commits, so no number moves).
- The `DISASTER_STOP` asymmetry paragraph's direction was backwards -- corrected: `as_booked`/`next_open`/`chase_once`/`close` have zero rows worse than -1.000R; only `limit_level` (28/443 full29, worst -3.9865R) and `mid_candle` (573/6376 full29, worst -75.5491R) do, via `_walk`'s scratch path, not a disaster stop.
- The "blind 2R exit" header claim for `close` corrected to name its real exit (`simulate_day` + live `DISASTER_STOP`), and the size of the exit-model gap quantified (92% of the next_open-close difference, 475/7857 rows flip).
- Honest avg win / avg loss added (the original +2.0000/-1.0000 on every arm was tautological -- `_walk` returns the target or the stop by construction and excluded every "scratch" row, including `mid_candle`'s -75.5491R rows, from both columns).
- Honest per-trade win rate added alongside the original filled-only win rate, with the gap named (e.g. `limit_level` full29: 41.9% filled-only vs 39.3% per-trade).
- The size gate applied after the fact to all 12 books: `as_booked` full29 $832/day, 24/25 green -> $166/day, 15/25 green; `limit_level` full29 $133/day, 17/25 green -> $5/day, 11/25 green; `next_open` full29 $2,660/day -> $2,195/day. Two of six arms' verdicts do not survive the gate.
- `mid_candle`'s -75.5491R single row (inside its published $1,102/day full29 figure) surfaced explicitly as contradicting CLAUDE.md's "max loss is -1R hard" rule.

**Not fixed -- kept, refuted.** The headline ranking itself (which fill "wins") cannot be repaired without re-running the replay under one exit model held constant for all six arms -- the referee's own words: "R2 must not start from next_open-as-winner; it needs one exit model held constant and the size gate on, or it will attribute an exit difference to a fill." That is a second change (it touches every arm's exit mechanics, not one flag) and is out of this repair's one-change scope; it is R2's job, not R1's. The two headline tables above are left in place, now with the correction notice at the top of this file and the honest/sized numbers alongside them, rather than deleted or silently patched.

**Not fixed -- disclosed, unfixable without a rerun.** One of the 12 books (`fillarms_mid_candle_full29.json.gz`) stamps commit `c7d52853` while its eleven siblings, written by the same process within the same four seconds, stamp `57f2fbd2` -- another agent's commit landed on `main` mid-write. Both are ancestors of `738e856d`, the commit this row was ultimately built on top of, so the books are still valid, but the stamp mismatch is a real defect (`book_stamp.py` reads live git state, not a value fixed at process start) and re-stamping the file after the fact would misrepresent when it was actually built, so it is left as-is and named here.

## What could not be done in this row

Nothing was cut for time in this run. Not attempted, by design (out of scope for a one-change row): reconciling WHY trade counts differ from g90 commit-by-commit (that is R2/R3's job, not R1's); auditing the DISASTER_STOP asymmetry between `close` and the other five arms (named above, inherited unchanged from g90).

## Reproduce

```
python research/g210_fill_arms_v2.py --procs 8
```

Window and pools are computed from `data_archive/` at run time, not passed as flags -- re-running after the archive advances will move the window forward.

Verify: `python research/g210_verify.py` (exits nonzero on any mismatch; PASS as of this row -- see above).

Referee's repair tables ("Refereed" section above): `python research/r1_repair.py` (reads the 12 stamped books below, writes no new files, no rerun of the replay).

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