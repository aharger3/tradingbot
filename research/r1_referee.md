# R1 referee — REFUTED (the ranking), on the builder's commit `738e856d`

Referee: opus, told to refute. Builder's row: R1, `research/g210_fill_arms_v2.py` /
`research/g210_fill_arms_v2.md`, commit **`738e856d`**. Referee code:
`research/r1_referee.py` (nothing in it imports `g90_fill_arms`'s or
`g210_fill_arms_v2`'s arithmetic; every stat, fill and exit here is re-implemented
against the raw `data_archive/*.csv` bars and the stamped books in `research/tape/`).

Base check: `origin/main` = `HEAD` = `738e856d`; `1539dd7f` is an ancestor. OK.

---

## Verdict in one sentence

**The arithmetic reproduces exactly and the lookahead is clean, but the table's
headline — the shipped `close` fill loses $221/day while `next_open` makes
$2,660/day — is not a fill result. It is an exit-model artifact.** Repriced with
the *same* exit the other five arms use, `close` pays **+0.1547R / $2,437/day**
(full29) and **+0.1566R / $1,139/day** (core11), i.e. inside noise of `next_open`.
The six arms in this table are not six fills; they are five fills under one exit
model plus one fill under a different one.

---

## The refutation (`research/r1_referee.py closewalk`)

`close` is the only arm read off the real `SimTrade`, so it is managed by
`backtest_week.simulate_day`. Under `SCALE_PLAN=None` that loop **still runs
`DISASTER_STOP`** (`backtest_week.py:411`, default on): a resting order at
`DISASTER_STOP_R = 1.0` × risk from entry, filled on an **intrabar touch**. Since
entry − 1.0 × (entry − stop) = stop, that order sits exactly on the structural
stop — so **the `close` arm is stopped out by a wick.**

The other five arms are priced by `g90_fill_arms._walk`, which stops **only on a
candle close through the stop** and then fills **at the stop price**. A wick that
tags the stop and reverses is a stop-out for `close` and a non-event for the
other five.

Same entry, same stop, same 2R target, only the exit machinery swapped:

| pool | `close` as booked (real engine exit) | `close` repriced with `_walk` | rows that flip |
|---|---:|---:|---:|
| full29 (7,857 rows) | −0.0141R · −$221/day | **+0.1547R · +$2,437/day** | 475 better, 28 worse |
| core11 (3,629 rows) | −0.0063R · −$46/day | **+0.1566R · +$1,139/day** | 206 better, 12 worse |

Exit-model contamination in the `close` row: **+0.1688R per trade** (full29),
**+0.1630R** (core11). The published `next_open` − `close` gap is +0.1831R
(full29) and +0.1781R (core11). **92% of that gap is the exit, not the fill, in
both pools** (0.1688/0.1831 and 0.1630/0.1781). Unit: every traded signal (fired, legacy grade ≠ C, `reentry_84_rule`
excluded). Fill: as named per arm. Exit: as stated. Script: `research/r1_referee.py`.

The builder named this asymmetry and got its **direction backwards**
(`research/g210_fill_arms_v2.md:95`): *"`close`'s losses can be capped at −1.000R
intrabar while the other five arms' losses are only capped at whatever the next
closed candle prints, which can be worse than −1R."* Measured from the books
(`r1_referee.py losses`, full29): `as_booked`, `next_open`, `chase_once` and
`close` all have **zero** losses worse than −1R (every one lands at exactly
−1.0000R). The two arms that *do* book worse than −1R are `limit_level` (28 rows,
worst **−3.9865R**) and `mid_candle` (573 rows, worst **−75.5491R**) — and they do
it through `_walk`'s scratch path, not through any disaster stop. So the cap is
not what separates `close`; the **wick trigger** is, and it costs `close` 475
rows.

Per the referee brief, a plausible ranking change makes the verdict `not_enough`
on the ranking. This one is not plausible, it is measured: **refuted**.

---

## Second defect: `avg win +2.0000 / avg loss −1.0000` is a construction artifact

Every cell of those two columns in both tables reads exactly +2.0000 / −1.0000.
That is not a measurement. `research/g210_fill_arms_v2.py:347` (`avg_win_loss`)
averages only rows whose `outcome` is literally `"win"` or `"loss"`; `_walk`
returns the target price for a win and the stop price for a loss, so those rows
are ±2R and −1R **by construction**, and every row that lost more than −1R
carries `outcome == "scratch"` and is silently excluded from the "avg loss"
column it belongs in.

Sign-based averages over the same books (`r1_referee.py stats`):

| arm (full29) | report avg loss | referee avg loss (all negative rows) | rows worse than −1R |
|---|---:|---:|---:|
| limit_level | −1.0000 | **−1.0469** | 28 (worst −3.9865R) |
| mid_candle | −1.0000 | **−1.1467** | 573 (worst −75.5491R) |
| next_open | −1.0000 | −0.9973 | 0 |
| close | −1.0000 | −0.9980 | 0 |

The spec's target is *"average winner = 2× average loser"*. As printed, this
table meets it on all six arms trivially and carries no information about it.
It also hides a single **−75.55R** row (−$75,551 at 1R = $1,000) inside
`mid_candle`'s $1,102/day, which contradicts `CLAUDE.md`'s "Max loss is −1R
hard".

## Third defect: the headline table is ungated arithmetic

The builder flags this honestly at `research/g210_fill_arms_v2.md:97`, but
publishes the ungated table as the headline anyway. Applying
`signal_runner.min_risk_floor(entry)` = `max(0.10, 0.0015 × entry)` to the same
books moves the answer, not the decimals (full29):

| arm | ungated $/day | gated $/day | rows dropped | green months gated |
|---|---:|---:|---:|---:|
| as_booked | $832 | **$166** | 364 | 15/25 (was 24/25) |
| limit_level | $133 | **$5** | 283 | 11/25 (was 17/25) |
| next_open | $2,660 | **$2,195** | 1,429 | 22/25 (was 23/25) |
| chase_once | −$756 | −$617 | 735 | 9/25 |
| close | −$221 | −$109 | 1,276 | 12/25 |
| mid_candle | $1,102 | **$900** | 2,904 | 21/25 |

`as_booked`'s "+0.75R, 24/25 green" and `limit_level`'s $133/day do not survive
the gate. Whatever R2 starts from, it should not start from the ungated column.

---

## What the referee could NOT refute (upheld)

**1. Every headline number reproduces from the books, with my own code.**
`r1_referee.py stats` re-derives trades, unfilled, mean R, months, green months
and $/day from the flat rows in each `.json.gz`, and matches the report cell for
cell on all twelve books — including the two the brief named:

| cell | report | referee |
|---|---|---|
| next_open core11 | 3629/0, +0.1718R, 22/25, $1,250/day | 3629/0, +0.1718R, 22/25, $1,250/day |
| next_open full29 | 7857/0, +0.1690R, 23/25, $2,660/day | 7857/0, +0.1690R, 23/25, $2,660/day |
| close core11 | 3629/0, −0.0063R, 13/25, −$46/day | 3629/0, −0.0063R, 13/25, −$46/day |
| close full29 | 7857/0, −0.0141R, 11/25, −$221/day | 7857/0, −0.0141R, 11/25, −$221/day |

The only column that differs is **win rate**, and only by definition: the report's
denominator is wins + losses (scratches dropped), mine is positives + negatives.
That makes the report's `limit_level` 41.9% read as 39.3% and `mid_candle` 43.1%
read as 39.3% on a per-trade basis. The report does not say scratches are
excluded from the win-rate denominator. Documentation defect, not an error.

**2. No lookahead in any forward arm** (`r1_referee.py lookahead --n 30`, 120 rows).
For each sampled row I rebuilt the day from the raw CSV, located the signal bar
by its timestamp, **physically truncated the list to `bars[idx+1:]`**, and
re-derived the fill from the truncated list alone:

| arm | sampled | re-derivation matches book | fill bar at or before the signal bar |
|---|---:|---:|---:|
| next_open | 30 | 30 | 0 |
| limit_level | 30 | 30 | 0 |
| chase_once | 30 | 30 | 0 |
| mid_candle | 30 | 30 | 0 |

Entry price *and* fill-bar timestamp both match. `mid_candle` takes its price
reference — the midpoint of the signal bar's own high/low — from the completed
signal bar, which is known at the moment the signal exists; its resting scan is
still strictly after that bar, so it satisfies "the signal bar is never scanned
for a resting fill".

**3. The `close` arm really is the engine's own fill, on 100% of rows.**
`r1_referee.py close`, my code, not the builder's: `entry_fill.ENTRY_FILL ==
'close'`, `needs_future_bars()` is False, `entry_fill_price(..., mode="close")`
returns the bar's close verbatim, and **7,857 of 7,857** rows in
`fillarms_close_full29.json.gz` equal that minute's own printed close in the raw
archive CSV — 0 mismatches. `as_booked`'s entry equals `close`'s on **0** of
7,857 rows, so the arms are genuinely distinct prices.

**4. The `SCALE_PLAN` / `LADDER_MODE` claim is correct.** `backtest_week` has **no**
`LADDER_MODE` attribute (`hasattr(bw, 'LADDER_MODE')` is `False`), so
`g90_fill_arms.py`'s `bw.LADDER_MODE = None` created a dead attribute and changed
nothing. Default `bw.SCALE_PLAN` is `'hod_then_runner_be'`. The assertion **does**
run in the worker: `r1_referee.py scaleplan` spawns a real `multiprocessing.Pool`
(start method on this box is `spawn`), sets `OMEN_SCALE_PLAN=none` inside the
worker before importing, and both workers report `SCALE_PLAN=None` from their own
pids, while the parent — importing without the env — reports
`'hod_then_runner_be'`. **What g90's `close` column really was:** the shipped
`hod_then_runner_be` scale-out book, with `DISASTER_STOP` on, priced from
`t.pnl` — not blind 2R. g90's +0.7382R / $1,645/day / 25-of-25-green `close` row
is a ladder book and must never be compared to a 2R column.

**5. The single `entry_idx` mismatch reproduces exactly as described.**
`r1_referee.py achr` re-runs ACHR 2026-04-06 from raw bars: 390 bars, 15 captured
signals, and the key `('break_and_retest', 'call', 5.665, 'fired')` holds **two**
signals, at candle index **16** and **20**. The counted trade carries
`t.entry_idx = 20` and the harness's `used[k]` counter hands it the bar-16 signal
— mismatch, row dropped. The builder's diagnosis (a signal↔trade correlation
ambiguity in this harness's own matching key, not in `signal_runner`/
`backtest_week`) is right, and 1 dropped row of 7,857 moves no headline.

**6. `research/g210_verify.py` exits 0 and really reads raw bars** — it opens
`data_archive/<SYM>/<day>.csv` with `csv.DictReader` (lines 44–48), not the book.
Output: `PASS: next_open/limit_level match raw bars on 20 sampled rows; close
matches the engine's default fill on 7857/7857 rows (100%)`.

---

## Standard checks

| check | result |
|---|---|
| sample size | every cell ≥ 30 trades (min 252) and 25 months. No under-sized cell carries a verdict. OK |
| dollar naming | each table names fill, unit and script; **the `close` row's exit is mis-named** — the header says "blind 2R" but `close` is exited by `simulate_day` with `DISASTER_STOP` on. Defect |
| stamps | all 12 books carry `book_stamp.stamp` with commit, flags, window, script. **11 name `57f2fbd2`; `fillarms_mid_candle_full29.json.gz` names `c7d52853`** although all 12 were written by one process inside four seconds (16:34:03–16:34:07) — a git race during a sibling agent's commit. Both are ancestors of `738e856d`, so the rule passes, but one stamp does not identify its own build |
| build commit vs stated base | the report's first line says "Base `c13bdf8c`"; the books were built at `57f2fbd2`. `git diff c13bdf8c 57f2fbd2` over `signal_runner.py backtest_week.py entry_fill.py stop_rule.py backtest_2y.py universe.py omen_bot.py research/downgrade.py` is **empty**, so no number moves — but the report names a base it did not build on, and does not disclose the 5–6 dirty non-engine `.py` files the stamp records (`dirty_engine_py` is empty) |
| one change per row | `git show --stat 738e856d`: 3 research files + 12 books, no engine file. OK |
| mark files | none touched, in the commit or the working tree. OK |
| verify gate at `738e856d` | `regression_gate.py` PASS · `test_runner_stop.py` PASS (70 checks) · `test_universe_single_source.py` PASS (29 symbols, no private lists). Green |
| plain English | the report is agent-facing; nothing here reaches Austin. OK |

---

## Defects, by line

1. `research/g210_fill_arms_v2.py:361` — `stats_for` routes `close` to
   `close_stats` (real-engine exits, `DISASTER_STOP` on) and the other five to
   `arm_stats` (`_walk`, close-only stop). Six fills, two exit models, one table.
2. `research/g210_fill_arms_v2.md:28` — `close` full29 `−$221/day` is published
   under a header (line 3) that names the exit "blind 2R". Its real exit is the
   shipped `simulate_day` loop.
3. `research/g210_fill_arms_v2.md:95` — the `DISASTER_STOP` asymmetry paragraph
   states the direction backwards.
4. `research/g210_fill_arms_v2.py:347` — `avg_win_loss` excludes `scratch`, making
   both avg columns +2.0000 / −1.0000 on every arm and hiding 601 sub-−1R rows.
5. `research/g210_fill_arms_v2.md:29` — `mid_candle` $1,102/day contains a single
   −75.5491R row.
6. `research/g210_fill_arms_v2.md:97` — the size gate is flagged but the ungated
   table is still the headline; gating halves `as_booked` and erases
   `limit_level`.
7. `research/tape/fillarms_mid_candle_full29.json.gz` — stamp commit `c7d52853`
   disagrees with the 11 sibling books written in the same four seconds.

## What R2 should be handed

Not `next_open` as the winner. The one comparison this row has not yet made is
the six fills **on one exit model**. On `_walk` (close-only stop, fill at the
stop, blind 2R, no size gate), `close` is +0.1547R / $2,437/day full29 against
`next_open`'s +0.1690R / $2,660/day — a difference well inside the ±1.58R error
bar this project measures on every A/B. R2 should start from a book where the
exit is held constant and the size gate is on, or it will inherit this row's
confound and attribute an exit difference to a fill.

## Reproduce

```
python research/r1_referee.py stats
python research/r1_referee.py lookahead --n 30
python research/r1_referee.py close
python research/r1_referee.py achr
python research/r1_referee.py scaleplan
python research/r1_referee.py losses
python research/r1_referee.py closewalk --pool full29
python research/r1_referee.py closewalk --pool core11
```
