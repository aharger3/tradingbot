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

---
---

# R1 referee — SECOND PASS, post-repair — **REFUTED** (the ranking), on the builder's commit `3676a230`

Referee: second pass, a different model, told to refute. Builder's repair commit
**`3676a230`** (repairing `738e856d`); report `research/g210_fill_arms_v2.md`;
repair script `research/r1_repair.py`. Referee code for THIS pass:
**`research/r1_referee2.py`** — a fresh implementation that imports neither
`g90_fill_arms`, nor `g210_fill_arms_v2`, nor `r1_repair`, nor pass 1's
`r1_referee.py`. Every fill, exit and statistic below is re-derived from the raw
`data_archive/*.csv` bars and the stamped books in `research/tape/`. Pass 1
above is left untouched; this section is additive.

Base check: `git merge-base --is-ancestor 1539dd7f HEAD` passes; `HEAD` =
`origin/main` = `3676a230`. OK.

## Verdict in one sentence

**Every number in the repaired report reproduces exactly under independent code —
including all twelve size-gated cells, all twelve honest avg-win/avg-loss cells and
the exit-model reprice — and the repair fixed the defects it claimed to fix. The
row stays REFUTED on the same point pass 1 refuted it on: the six-arm table still
prices five fills under one exit model and `close` under another, so "which fill
wins" is unanswered.** Four new defects, none of which move a number.

## Pass-1 defects: fixed, or not

| # | pass-1 defect | second-pass finding |
|---|---|---|
| 1 | two exit models in one table (`stats_for`) | **not fixed, correctly labelled refuted.** The report now carries a bolded correction above both headline tables. Legitimately a second change |
| 2 | `close` published under a "blind 2R" exit header | **partially fixed.** `g210_fill_arms_v2.md:3` still reads "Blind 2R exit" with no qualifier; the correction is two paragraphs below it |
| 3 | asymmetry direction backwards | **fixed in the report, NOT in the generator** — see new defect 8 |
| 4 | tautological +2.0000/−1.0000 | **fixed.** Honest columns added; my recompute matches all 24 cells |
| 5 | `mid_candle`'s −75.5491R row | **fixed** (surfaced by name). Re-derived: AMD 2026-04-24, entry 343.5249, stop 343.50 → risk $0.0249, i.e. a 100,000-share position. 14 rows worse than −5R sum to −186.2R against the book's total +550.0R |
| 6 | ungated headline table | **fixed** (sized table added). All 12 cells reproduce |
| 7 | `mid_candle_full29` stamped `c7d52853` | **disclosed, not fixable.** Confirmed: 11 books stamp `57f2fbd2`, that one stamps `c7d52853`, both ancestors of `3676a230`, all 12 written 16:34:03–16:34:07, `dirty_engine_py` empty on all 12 |

## What reproduced, with my own code

**Headline arithmetic — all six arms, both pools, 12/12 books** (`r1_referee2.py stats`).
Trades, unfilled, mean R, months, green months and $/day match the report cell for
cell, including the two the brief named:

| cell | report | second-pass referee |
|---|---|---|
| next_open full29 | 7857/0, +0.1690R, 23/25 green, $2,660/day | 7857/0, +0.1690R, 23/25, $2,660/day |
| next_open core11 | 3629/0, +0.1718R, 22/25 green, $1,250/day | 3629/0, +0.1718R, 22/25, $1,250/day |
| close full29 | 7857/0, −0.0141R, 11/25 green, −$221/day | 7857/0, −0.0141R, 11/25, −$221/day |
| close core11 | 3629/0, −0.0063R, 13/25 green, −$46/day | 3629/0, −0.0063R, 13/25, −$46/day |

Avg win / avg loss (sign-based, scratches included) also match all 12 rows of the
repair's honest table — e.g. full29 `next_open` +1.9817/−0.9973, `close`
+1.9823/−0.9980, `mid_candle` +1.9942/−1.1467 (worst −75.5491R, 573 rows worse
than −1R), `limit_level` +2.0000/−1.0469 (worst −3.9865R, 28 rows). Per-trade win
rates match (full29: as_booked 58.4%, limit_level 39.3%, next_open 39.1%,
chase_once 31.1%, close 33.0%, mid_candle 39.3%). `pnl` equals `r × $1,000` on
every filled row of every book (0 exceptions in 12 books).
Unit: every traded signal (fired, legacy grade ≠ C, `reentry_84_rule` excluded).
Fill: as named per arm. Exit: as originally priced per arm. Script:
`research/r1_referee2.py stats`.

**Size-gated table — 12/12 cells reproduce** (`r1_referee2.py sized`), independent
implementation of `max($0.10, 0.0015 × entry)` on `|entry − stop|`: full29
`as_booked` 187 trades / +0.4439R / $166/day / 15-25 green, `limit_level` 160 /
+0.0165R / $5/day / 11-25, `next_open` 6428 / +0.1704R / $2,195/day / 22-25,
`chase_once` 4686 / −0.0657R / −$617/day / 9-25, `close` 6581 / −0.0083R /
−$109/day / 12-25, `mid_candle` 3472 / +0.1293R / $900/day / 21-25; core11
identical to the report including its `12/24` months cell for `limit_level`.

**Lookahead: clean, 120 rows, physically truncated** (`r1_referee2.py lookahead --n 30`).
For each sampled row I loaded the day's bars from the raw CSV, found the signal bar
by its timestamp, cut the list to `bars[signal+1:]` — the signal bar and all history
physically gone — and re-derived the fill from the remainder alone:

| arm | sampled | entry re-derived | fill bar re-derived | fill at or before the signal bar |
|---|---:|---:|---:|---:|
| next_open | 30 | 30 | 30 | 0 |
| limit_level | 30 | 30 | 30 | 0 |
| chase_once | 30 | 30 | 30 | 0 |
| mid_candle | 30 | 26 (+4 rounding) | 30 | 0 |

The four `mid_candle` "misses" are the book's 4-decimal rounding of the midpoint
(largest gap 5.0e-5, e.g. AVGO 2026-06-22 book 401.6450 vs exact 401.64505) — not
a fill difference. `mid_candle` reads the signal bar's own high/low for its price
reference, which is known at that bar's close; its resting scan is strictly after
it. **No arm needs a bar at or before the signal bar.**

**`close` is the engine's own fill on 100% of rows, both pools** (`r1_referee2.py close`):
`entry_fill.ENTRY_FILL == 'close'`, and the booked entry equals that minute's own
printed close in the raw archive on **7,857/7,857** (full29) and **3,629/3,629**
(core11) rows, 0 mismatches, 0 missing bars. `as_booked`'s entry equals `close`'s on
**0** rows in either pool, so the arms are distinct prices.

**`SCALE_PLAN` is `None` inside the worker processes** (`r1_referee2.py scaleplan`),
established by my own `multiprocessing.Pool`, not the builder's: start method on this
box is **spawn**; workers that set `OMEN_SCALE_PLAN=none` before importing
`backtest_week` (g210's pattern, and its `assert` at
`research/g210_fill_arms_v2.py:174` is inside `run_symbol`, i.e. in the worker)
report `SCALE_PLAN=None`, `hasattr(bw, 'LADDER_MODE') == False`, `DISASTER_STOP=True`,
`DISASTER_R=1.0` from their own pids; control workers without the env report
`'hod_then_runner_be'`. **What g90's `close` column really was:** the shipped
`hod_then_runner_be` scale-out ladder book (g90 set the dead `LADDER_MODE`
attribute, which `backtest_week` does not have), not a blind-2R column — so g90's
+0.7382R / $1,645/day `close` row is a ladder result and is not comparable to this
row's 2R columns.

**The `entry_idx` mismatch re-derived** (`r1_referee2.py achr`): ACHR 2026-04-06,
390 candles, 15 captured signals, 11 trades; the key
`('break_and_retest', 'call', 5.665, 'fired')` holds **two** signals, at candle
**16** and candle **20**; the counted trade carries `entry_idx = 20` and the
harness's `used[k]` counter hands it the bar-16 signal. `g210_fill_arms_v2.py:259`
counts the mismatch and `continue`s, so the row is absent from all 12 books rather
than wrong. The builder's diagnosis is correct — with the caveat in new defect 11.

**`research/g210_verify.py` exits 0 and reads raw bars.** Run here: exit 0, output
`PASS: next_open/limit_level match raw bars on 20 sampled rows; close matches the
engine's default fill on 7857/7857 rows (100%)`. It opens
`data_archive/<SYM>/<day>.csv` with `csv.DictReader`, not the book — but see new
defect 9 for how weak its `limit_level` assertion is.

## The refutation still stands, re-derived independently

`r1_referee2.py closewalk` re-prices the `close` arm on a close-only structural stop
(the exit the other five arms get), from the raw bars, with my own walk:

| pool | `close` as booked (`simulate_day`, DISASTER_STOP on) | `close` on the close-only stop | rows better / worse |
|---|---:|---:|---:|
| full29 (7,857) | −0.0141R · −$221/day | **+0.1547R · +$2,437/day**, 22/25 green | 475 / 28 |
| core11 (3,629) | −0.0063R · −$46/day | **+0.1566R · +$1,139/day**, 20/25 green | 206 / 12 |

Identical to the builder's repaired figures and to pass 1's. So: the published
`next_open` − `close` gap is +0.1831R (full29); held to one exit model it is
**+0.0143R**, an order of magnitude inside the ±1.58R error bar this project
measures on every A/B. **The DISASTER_STOP asymmetry does change the ranking** — it
moves `close` from second-worst to statistically tied with the published winner —
so per the brief the ranking cannot be upheld. The builder agrees and has labelled
it refuted; that labelling is now accurate.

## New defects (second pass)

**8. The repair lives only in the report; the script that writes the report still
emits the pre-repair text.** `research/g210_fill_arms_v2.py:688–700` still composes
the backwards asymmetry paragraph ("`close`'s losses can be capped at −1.000R
intrabar while the other five arms' … can be worse than −1R"), and line 559 still
writes the unqualified "Blind 2R exit" header. The report's own **Reproduce**
section says to run `python research/g210_fill_arms_v2.py --procs 8`, and that
command overwrites `research/g210_fill_arms_v2.md` — silently reverting every
correction, the honest tables, the sized table and the Refereed section. The
numbers are reproducible (`r1_repair.py` is committed and its output reproduces);
the *report* is not. Severity: the next agent who re-runs the row inherits the
refuted text as if it were current.

**9. `research/g210_verify.py`'s `limit_level` assertion is too weak to fail.** It
checks only that the booked fill lies inside the fill bar's `[low, high]` — a
condition `_resting_fill` guarantees by construction, since it fills only when the
level sits inside that range. It does not check `entry == level_price`, and it does
not check that the fill bar is strictly after the signal bar, which is the lookahead
class the whole arm was rewritten for on 2026-09-03. A verify that cannot fail is
not a verify. (The strong version — truncate and re-derive — is
`r1_referee2.py lookahead`, and it passes 30/30 on this arm, so **no number moves**.)

**10. The `mid_candle` book rounds its entry to 4 decimals**, so an exact
re-derivation of the midpoint differs by up to 5e-5 on ~13% of sampled rows. Named
so a future referee does not read it as a mismatch. No number moves.

**11. The duplicate-key correlation bug is under-counted by its own counter.** The
harness pairs trades to signals on
`(signal_type, direction, round(entry, 4), status)` and detects a bad pairing only
when the two candidates sit on *different* candles. On the same ACHR day the key
`('break_and_retest', 'put', 5.605, 'skipped_d')` holds two signals **both at candle
40** — a collision that would pair silently, recording the other signal's `_level`
(hence the row's `level_price`, which is what `as_booked` and `limit_level` price
off) with no counter firing. That instance is not counted (`skipped_d`), but the
class is invisible to the "1 of 7858" figure. Quantifying it needs the replay, so
this is an open item, **not** a claim that any published cell is wrong.

**12. Unit magnitude is stated but not made comparable.** $2,660/day is 7,857 trades
over 499 sessions — **15.7 trades a day at $1,000 risk each**. The report names the
unit ("every traded signal") but never says this is ~10x the 1–3 fires a day THE
LANE is about, so the figure invites comparison with the $397/day bar, which it is
not on the same footing as. One sentence would fix it.

**13. Observation, not a defect — the shipped book is not size-gated on the fill it
books.** `signal_runner` does apply the same floor at detection
(`signal_runner.py:3051` / `:3332`, `floor_reference_risk(...) < min_risk_floor(...)`
→ grade D), yet **1,276 of 7,857** fired rows in the `close` full29 book carry
`|entry − stop|` below `max($0.10, 0.0015 × entry)`: 1,067 `break_and_retest`
(all grade B) and 209 `one_candle_rule` (181 B, 28 A). Examples are marginal, not
razor-thin (GOOG 2026-08-28 09:56, risk $0.470 vs floor $0.510). Two candidate
explanations — the retest re-price landing on a later bar than the bar the floor was
checked on, or emitters that never reach those two call sites — and I did not pin
which, so this is filed as an open question for a later row. It does **not**
invalidate the repair's post-hoc sized table; it means that table is a real,
binding filter rather than a formality.

## Standard checks (second pass, all run here)

| check | result |
|---|---|
| sample size | smallest cell 78 trades (core11 `limit_level` sized) over 24 months; every other cell ≥ 94 trades / 25 months. No cell under 30 trades or 12 months carries a verdict. OK |
| every dollar names fill / exit / unit / script | fill: yes. unit: yes. script: yes. exit: **now** named for `close` in the correction paragraph, but the report's own header line still says "Blind 2R exit" unqualified (pass-1 defect 2, partially fixed) |
| stamps | 12/12 books carry `book_stamp` with commit, `dirty_engine_py` (empty on all 12), every flag value (70 flags), build time, window `2024-09-04`→`2026-09-04`, script. 11 stamp `57f2fbd2`, one stamps `c7d52853`; both are ancestors of `3676a230`. Disclosed in the report. OK |
| build base disclosed | yes — `57f2fbd2`, and `git diff c13bdf8c 57f2fbd2` over the engine files is empty, so no number moves. Verified here |
| one change per row | `git show --stat 3676a230`: `research/g210_fill_arms_v2.md` + `research/r1_repair.py`, no engine file, no book rewritten. OK |
| mark files | none in either commit, none in the working tree. OK |
| verify gate at `3676a230` | run here: `regression_gate.py` PASS (no baseline-fired mark went silent) · `test_runner_stop.py` PASS (70 checks) · `test_universe_single_source.py` PASS (29 symbols, no private lists). **Green** |
| plain English | nothing in this row reaches Austin. OK |

## What R2 is handed

Unchanged from pass 1, and now confirmed by a second independent implementation:
**do not start from `next_open` as the winner.** Held to one exit model, `close`
(+0.1547R / $2,437/day full29) and `next_open` (+0.1690R / $2,660/day full29) are
inside each other's error bar. R2 needs one exit model across all six arms and the
size gate on, or it will attribute an exit difference to a fill. Add: R2 should also
regenerate the report from its script rather than hand-editing it (defect 8).

## Reproduce (second pass)

```
python research/r1_referee2.py stats
python research/r1_referee2.py lookahead --n 30
python research/r1_referee2.py close
python research/r1_referee2.py scaleplan
python research/r1_referee2.py closewalk
python research/r1_referee2.py sized
python research/r1_referee2.py achr
```



---
---

# R1 referee — THIRD PASS — **REFUTED** (the ranking, and now the winner's own headline), on the builder's commit `738e856d`

Referee: third pass, told to refute, dispatched against the ORIGINAL builder
report at **`738e856d`**. Referee code for this pass: **`research/r1_referee3.py`**
— a third independent implementation that imports neither `g90_fill_arms`, nor
`g210_fill_arms_v2`, nor `r1_repair`, nor pass 1's `r1_referee.py`, nor pass 2's
`r1_referee2.py`. It has its own CSV bar loader, its own resting-fill, its own
walk and its own statistics. The only project modules it touches are
`signal_runner` (for `CHASE_PCT`), `entry_fill` (to read the shipped fill mode)
and `backtest_week`/`t8_two_year` (for the single-day ACHR replay).

Passes 1 and 2 above are left untouched; this section is additive.

Base check: `git fetch origin`; `HEAD` = `origin/main` = **`ccd7fa06`**;
`git merge-base --is-ancestor 1539dd7f HEAD` passes; `HEAD` is an ancestor of or
equal to `origin/main`. OK. The row has since been repaired (`3676a230`) and
refereed twice (`e5a9ed7f`, `cb45ffa2`); this pass re-derives everything from
scratch rather than reading those two verdicts as evidence.

---

## Verdict in one sentence

**Every mechanic in the row is sound and every published cell reproduces exactly
under a third independent implementation — and the row is still refuted, on a
larger point than either earlier pass made: the exit-model confound does not only
under-price `close`, it over-prices the arm the row crowned. Put every arm on the
stop trigger the shipped engine actually uses, and `next_open` — the arm R2 was
told to start from — falls from `+0.1690R / $2,660/day / 23-of-25 green` to
`+0.0088R / $138/day / 13-of-25 green` (full29, every traded signal, blind 2R
target, `research/r1_referee3.py uniform`).**

---

## What reproduced, cell for cell (`r1_referee3.py stats`)

All twelve stamped books, re-derived from the flat rows with my own arithmetic.
Trades, unfilled, mean R, months, green months, `$/day` and the report's win-rate
column match **12 books × 7 columns, 84 of 84 cells**. The two the brief named:

| cell | report | third-pass referee |
|---|---|---|
| next_open core11 | 3629/0, +0.1718R, 22/25 green, $1,250/day | 3629/0, +0.1718R, 22/25, $1,250/day |
| next_open full29 | 7857/0, +0.1690R, 23/25 green, $2,660/day | 7857/0, +0.1690R, 23/25, $2,660/day |
| close core11 | 3629/0, −0.0063R, 13/25 green, −$46/day | 3629/0, −0.0063R, 13/25, −$46/day |
| close full29 | 7857/0, −0.0141R, 11/25 green, −$221/day | 7857/0, −0.0141R, 11/25, −$221/day |

`avg win / avg loss` does **not** reproduce, exactly as passes 1 and 2 found: the
report's `+2.0000 / −1.0000` on all twelve rows is a construction artifact of
dropping `scratch`. Sign-based over the same books: `next_open` full29
**+1.9817 / −0.9973**, `close` full29 **+1.9823 / −0.9980**, `limit_level` full29
**+2.0000 / −1.0469**, `mid_candle` full29 **+1.9942 / −1.1467**. Independently
confirmed.

---

## The refutation, extended: one exit model, all six arms, both directions

Passes 1 and 2 repriced **`close` upward** onto the five arms' close-only stop.
Neither repriced **the five arms downward** onto the intrabar-touch stop the
engine gives `close`. Both directions are single-exit-model comparisons and only
one of them is the exit the shipped engine runs. `r1_referee3.py uniform` does
both, from the raw bars, with my own walk:

**Model A — stop triggers only on a candle CLOSE through the level, fills at the
level** (what `g90_fill_arms._walk` gives the five arms):

| arm (full29) | trades | mean R | $/day | green |
|---|---:|---:|---:|---:|
| as_booked | 551 | +0.7532 | $832 | 24/25 |
| next_open | 7857 | +0.1690 | $2,660 | 23/25 |
| **close** | 7857 | **+0.1547** | **$2,437** | **22/25** |
| limit_level | 443 | +0.1499 | $133 | 17/25 |
| mid_candle | 6376 | +0.0867 | $1,108 | 17/25 |
| chase_once | 5421 | −0.0695 | −$756 | 8/25 |

**Model B — stop is a resting order at the level, filled on an intrabar TOUCH**
(the engine's `DISASTER_STOP` at `DISASTER_STOP_R = 1.0`, which for every arm sits
exactly on the structural stop because risk is defined as `|entry − stop|`):

| arm (full29) | trades | mean R | $/day | green |
|---|---:|---:|---:|---:|
| as_booked | 551 | +0.6171 | $681 | 24/25 |
| **next_open** | 7857 | **+0.0088** | **$138** | **13/25** |
| close | 7857 | −0.0141 | −$221 | 11/25 |
| limit_level | 443 | −0.0668 | −$59 | 8/25 |
| mid_candle | 6376 | −0.1460 | −$1,865 | 5/25 |
| chase_once | 5421 | −0.2450 | −$2,661 | 1/25 |

Core 11 reads the same way: `next_open` **+0.1718R / $1,250/day / 22-of-25** under
model A, **+0.0060R / $44/day / 12-of-25** under model B.

**Why the walker can be trusted.** It is validated in both directions on books it
did not build. Under model A it reproduces the five `_walk` arms' published cells
(`as_booked` +0.7532, `limit_level` +0.1499, `next_open` +0.1690, `chase_once`
−0.0695, `mid_candle` +0.0867 vs the published +0.0863 — 4e-4, rounding). Under
model B it reproduces the `close` arm the real `simulate_day` produced, to four
decimals in both pools (**−0.0141** full29, **−0.0063** core11). A walk that
reproduces both sides of the confound from opposite directions is measuring the
confound, not adding one.

**What this changes.** The published headline is `next_open $2,660/day` against
the shipped `close` fill's `−$221/day`. Neither figure survives holding the exit
constant:

- On model A both are large and close together (`$2,660` vs `$2,437`).
- On model B both are small (`$138` vs `−$221`), and `next_open`'s green months
  fall from **23/25 to 13/25**.

So the entire "next_open makes $2,660/day" result — the one R2's spec line says to
start from — is priced on an exit trigger the engine does not use. The `$2,660`
is not a fill number and not an engine number; it is a `_walk` number.

**Paired CI on the one thing that does survive** (`r1_referee3.py pairci`, paired
on 7,538 rows where both arms have a value, full29):

| exit model | mean(next_open − close) | 95% CI |
|---|---:|---|
| A close-only stop | +0.0140R | [+0.0047, +0.0234] |
| B intrabar-touch stop | +0.0239R | [+0.0136, +0.0341] |

The **direction** of the ranking (next_open over close) does survive holding the
exit constant, and the paired interval separates from zero in both models — which
is a sharper statement than passes 1 and 2's "inside the ±1.58R error bar",
because that bar is an unpaired per-book figure. But the **magnitude** collapses
from the published +0.1831R to +0.014R–+0.024R per trade: roughly a
seventh-to-a-thirteenth of what the table shows, and at model B's absolute level
($138/day on 15.7 trades a day) it is not a result anyone should build on.

Per the brief, a plausible ranking change makes the ranking `not_enough`; a
measured one makes it refuted. This is measured. **Refuted.**

---

## Row-specific checks, all run here

**Lookahead — clean** (`r1_referee3.py lookahead --n 30`, 120 rows). For every
sampled row I rebuilt the day from the raw `data_archive/*.csv`, located the
signal bar by its timestamp, **deleted every bar at or before it** (`bs[si+1:]`)
and re-derived the fill from the truncated list alone:

| arm | sampled | re-derivation matches the book (price and fill minute) | fill bar at or before the signal bar |
|---|---:|---:|---:|
| next_open | 30 | 30 | 0 |
| limit_level | 30 | 30 | 0 |
| chase_once | 30 | 30 | 0 |
| mid_candle | 30 | 30 | 0 |

`mid_candle`'s price reference — the midpoint of the completed signal bar's own
high/low — is captured as a scalar *before* truncation and the fill scan then sees
only bars strictly after the signal bar, so the signal bar is never scanned for a
resting fill. One honest caveat on `chase_once`, which no pass has named: its
fill *price* is `max(next.open, next.close)` for a long, so the decision whether
to chase at all uses a bar that has not finished when the order would be sent.
It is the worse-for-the-trade of the two, so it is pessimistic rather than
optimistic, and it never reaches back to or before the signal bar — it does not
meet the brief's refutation condition, but it is not a causally clean rule
either, and `chase_once` is last in every table anyway.

**The one `entry_idx` mismatch — reproduced exactly** (`r1_referee3.py achr`).
Re-running ACHR 2026-04-06 from raw bars: 390 bars, 15 captured signals, 11
trades. The key `('break_and_retest', 'call', 5.665, 'fired')` holds **two**
signals, at candle **16** and candle **20**; the counted trade carries
`entry_idx = 20` and the harness's `used[k]` counter hands it the bar-16 signal.
Builder's diagnosis is right: a signal↔trade correlation ambiguity in this
harness's own matching key, not in `signal_runner`/`backtest_week`, and the row is
dropped rather than mis-priced. I also independently reproduce pass 2's defect 11:
the same day carries a **second** colliding key,
`('break_and_retest', 'put', 5.605, 'skipped_d')`, whose two signals sit on the
**same** candle (40) — a collision the counter cannot see, so "1 of 7858" is a
lower bound on the class, not a count of it. That instance is `skipped_d` and
never reaches a book.

**`close` is the engine's own fill on 100% of rows — my code** (`r1_referee3.py
closecheck`). `entry_fill.ENTRY_FILL == 'close'`, `needs_future_bars()` is
`False`, and **7,857 of 7,857** rows in `fillarms_close_full29.json.gz` equal that
minute's own printed close in the raw archive CSV; 0 mismatches, 0 bars missing.
`as_booked`'s entry equals `close`'s on **0** of 7,857 rows, so the two arms are
genuinely different prices.

**`SCALE_PLAN` inside the worker — confirmed** (`r1_referee3.py scaleplan`). Start
method on this box is `spawn`. A real `multiprocessing.Pool(2)` running a worker
that sets `OMEN_SCALE_PLAN=none` before importing reports, from its own pid,
`SCALE_PLAN = None`, `DISASTER_STOP = True`, `DISASTER_R = 1.0`, and
`hasattr(bw, 'LADDER_MODE') is False`. The same pool without the env var reports
`'hod_then_runner_be'` from both workers, and so does the parent. So:
`g90_fill_arms.py`'s `bw.LADDER_MODE = None` created a dead attribute on a module
that has no such name and changed nothing, and **g90's published `close` column
(+0.7382R, $1,645/day, 25-of-25 green) was the shipped `hod_then_runner_be`
scale-out book with `DISASTER_STOP` on — not blind 2R.** It must never be read as
a 2R column. Builder's central diagnosis: upheld.

**`DISASTER_STOP` asymmetry and the ranking** — measured above. It does change the
ranking's meaning in both directions, so the ranking is refuted, not upheld.

**`research/g210_verify.py` exits 0 and really reads raw bars.** It opens
`data_archive/<SYM>/<day>.csv` with `csv.DictReader` (lines 41–52) and prints
`PASS: next_open/limit_level match raw bars on 20 sampled rows; close matches the
engine's default fill on 7857/7857 rows (100%)`, exit code 0. Pass 2's defect 9
stands: its `limit_level` assertion (booked fill inside the fill bar's
`[low, high]`) is true by construction of `_resting_fill` and cannot fail. My
truncation test is the version that can, and it passes 30/30.

---

## New defect (third pass)

**14. The books' `SCALE_PLAN = None` stamp was produced by the operator's shell,
not by the script — so the documented reproduce command stamps a book that
contradicts itself.** `g210_fill_arms_v2.py` sets `OMEN_SCALE_PLAN=none` inside
each **worker**, which is where it must be set for the arms to be priced right.
But `write_book` → `book_stamp.stamp` → `engine_flags()` imports `backtest_week`
in the **parent**, which never sets it. Measured in a clean shell here:
`book_stamp.engine_flags()['backtest_week.SCALE_PLAN']` is `'hod_then_runner_be'`,
and `OMEN_SCALE_PLAN` is absent from the environment. The twelve committed books
all stamp `None`, so the run that produced them had the variable exported in the
operator's shell — an input the report's **Reproduce** section
(`python research/g210_fill_arms_v2.py --procs 8`) does not mention. Run that
command as written on a clean box and you get books whose arms are priced with
`SCALE_PLAN = None` and whose stamp says `'hod_then_runner_be'`: exactly the
"a book built with the ladder on was indistinguishable from one built without it"
failure `research/book_stamp.py`'s own docstring exists to end. **No published
number moves** — the committed books' stamps are correct for the run that made
them. The fix is one line: set the env var at the top of `main()` as well as in
the worker. Filed, not fixed (not this referee's row).

---

## Standard checks (third pass)

| check | result |
|---|---|
| sample size | smallest cell 252 trades (`limit_level` core11) over 25 months; every cell ≥ 30 trades and ≥ 12 months. No under-sized cell carries a verdict here. OK |
| every dollar names fill / exit / unit / script | in **this section**: yes, on every figure. In the row's own report the `close` row's exit was mis-named "blind 2R" at `738e856d` and is now corrected in a paragraph two lines below a header that still says "Blind 2R exit". Partially fixed, as pass 2 found |
| stamps | 12/12 books carry `book_stamp.stamp`: commit, `dirty_engine_py` (empty on all 12), `dirty_py_count` 5–6 non-engine files, ~70 flag values, window `2024-09-04`→`2026-09-04`, script. 11 stamp `57f2fbd2`, `fillarms_mid_candle_full29.json.gz` stamps `c7d52853`; **both are ancestors of `738e856d`**, so the rule passes. The tree WAS dirty at build time (non-engine `.py` only); the report at `738e856d` did not say so, the repaired report does. See new defect 14 for the flag the stamp cannot vouch for |
| build base vs stated base | the report at `738e856d` says "Base `c13bdf8c`"; the books were built at `57f2fbd2`. `git diff c13bdf8c 57f2fbd2` over the engine files is empty, so no number moves. Disclosed only after the repair |
| one change per row | `git show --stat 738e856d`: 3 research files + 12 books, **no engine file**. OK |
| mark files | none in `git show --name-only 738e856d`, none in `git status`. OK |
| verify gate | run here at `HEAD = ccd7fa06`: `regression_gate.py` **PASS** (no baseline-fired mark went silent) · `test_runner_stop.py` **PASS** (70 checks) · `test_universe_single_source.py` **PASS** (29 symbols, no private lists). Green. I could not run it at `738e856d` itself without checking out another commit, which this swarm forbids; pass 1 ran it there and reported green |
| plain English | nothing in this row reaches Austin. OK |

---

## What R2 and R3 should take from this pass

1. **Do not start from R1's `next_open` book.** Its `$2,660/day, 23-of-25 green`
   is priced on a close-only stop the engine does not run. On the engine's own
   intrabar-touch stop the same book is `$138/day, 13-of-25 green`.
2. **The fill question is still unanswered, and it is small.** Held to one exit
   model, `next_open` beats `close` by +0.014R (model A) to +0.024R (model B) per
   trade — a real, paired, separated difference, and an economically tiny one.
   Whatever R3 picks as the baseline fill, it should not claim the fill is where
   the money is.
3. **The money in this row is in the exit trigger, not the fill.** Moving all six
   arms from a close-only stop to an intrabar-touch stop costs the full-29 book
   `$2,522/day` on `next_open` and ten green months. That is the largest single
   effect anywhere in R1, and it is an exit variable, which is R2's ladder.

## Reproduce (third pass)

```
python research/r1_referee3.py stats
python research/r1_referee3.py lookahead --n 30
python research/r1_referee3.py closecheck
python research/r1_referee3.py scaleplan
python research/r1_referee3.py achr
python research/r1_referee3.py uniform
python research/r1_referee3.py pairci
```

---
---

# R1 referee — FOURTH PASS, post pass-3 repair — **REFUTED** (the published headline), on the builder's commit `0f6a826a`

Referee: fourth pass, told to refute. Builder's repair landed inside commit
**`0f6a826a`** (see standard checks — it is an unattended auto-commit, not a
row commit). Report `research/g210_fill_arms_v2.md`; changed code
`research/g210_fill_arms_v2.py`, `research/g210_verify.py`. Referee code for
this pass: **`research/r1_referee4.py`** — a fourth independent
implementation with its own CSV bar loader, its own resting-fill, its own two
exit walks and its own statistics. It imports nothing from `g90_fill_arms`,
`g210_fill_arms_v2`, `r1_repair`, `r1_referee`, `r1_referee2` or
`r1_referee3` for any arithmetic. The two deliberate exceptions are *tests of
builder code*, each isolated in its own subcommand: `avgwl` imports the
repaired `avg_win_loss` in order to run it, and `scaleplan`/`achr` import
`backtest_week`/`t8_two_year` because those modules are the question.

Base check: `git fetch origin`; `HEAD` = `origin/main` = `0f6a826a`;
`git merge-base --is-ancestor 1539dd7f HEAD` passes. OK.

Passes 1–3 above are left untouched; this section is additive.

---

## Verdict in one sentence

**All three claimed repairs are real and reproduce, and every one of the 12
books' 84 cells plus the whole uniform-exit table re-derives exactly under a
fourth independent implementation — but the row is still REFUTED, because the
answer it publishes first is still the refuted one and its own script will put
that answer back**: `research/g210_fill_arms_v2.py` still generates the
unqualified "Blind 2R exit" header (line 581) and the measured-backwards
`DISASTER_STOP` paragraph (lines 712–720), and `main()` writes that text over
`research/g210_fill_arms_v2.md` (line 756) — the exact command the report's
own **Reproduce** section tells the next agent to run.

---

## The three claimed repairs, each checked by running it

**1. `avg_win_loss()` now buckets by the sign of the row's own R multiple — CONFIRMED.**
`r1_referee4.py avgwl` calls the repaired function on rows rebuilt from the 12
committed books and compares against this file's own sign-bucketed recompute:
**24 of 24 cells match, 0 mismatches.** The function no longer prints the
tautological `+2.0000 / −1.0000`; `limit_level` full29 reads `+2.0000 /
−1.0469` and `mid_candle` full29 `+1.9942 / −1.1467`, i.e. the scratch rows it
used to drop are now inside the average loss. Its `> 0` / `<= 0` split matches
`research/r1_repair.py:72–73` exactly, so the "matches the already-published
honest table" claim holds. Affects future runs only; the 12 books are
untouched, as claimed.

**2. `book_stamp`'s `SCALE_PLAN` misread — CONFIRMED fixed, and the diagnosis is right.**
`r1_referee4.py scaleplan`, in fresh subprocesses:

| process | reading |
|---|---|
| clean parent, no env var | `backtest_week.SCALE_PLAN = 'hod_then_runner_be'` |
| `book_stamp.engine_flags()` before the fix | `'hod_then_runner_be'` |
| `book_stamp.engine_flags()` after `bw.SCALE_PLAN = None` (the one-line repair) | `None` |
| real spawned worker with `OMEN_SCALE_PLAN=none` set before import | `SCALE_PLAN = None`, `DISASTER_STOP = True`, `DISASTER_STOP_R = 1.0`, `hasattr(bw,'LADDER_MODE') = False` |

Start method on this box is `spawn`, so the assertion at
`research/g210_fill_arms_v2.py:174` runs **inside the worker**, not the
parent — confirmed by a worker printing from its own pid. No published number
moves: the workers priced every arm under `SCALE_PLAN=None` all along, only
the parent's self-description was wrong.

**What g90's `close` column really was.** `research/g90_fill_arms.py:111` sets
`bw.LADDER_MODE = None`, and `backtest_week` has no such attribute
(`hasattr` is `False` in every process tested here); g90 never sets
`OMEN_SCALE_PLAN` anywhere in the file. So g90's `close` row
(+0.7382R, $1,645/day, 25-of-25 green) was the **shipped
`hod_then_runner_be` scale-out ladder book with `DISASTER_STOP` on**, read off
`t.pnl` — not a blind-2R column, and not comparable to any 2R column in this
row or in R2.

**3. `research/g210_verify.py`'s new no-lookahead assertion — CONFIRMED live, and it can fail.**
The added check compares the fill minute to the signal's own `entry_time`
minute. It is guarded by `if sig_minute and minute`, so it would silently skip
on a blank `entry_time`: checked, **0 of the 20 sampled rows carry a blank**,
and the real gaps run 1 minute (`next_open`) to 12 minutes (`limit_level`,
e.g. IWM 2024-10-14 signal 10:07 → fill 10:19). `python research/g210_verify.py`
run here: **exit 0**, `20` sampled rows, `7857/7857` close rows, 0 mismatches,
and it reads `data_archive/<SYM>/<day>.csv` with `csv.DictReader` (lines
41–52), not the book.

---

## Everything reproduced, with a fourth implementation

**All 12 books, all cells** (`r1_referee4.py stats`) — trades, unfilled, mean R,
sign-bucketed avg win / avg loss, per-trade win %, months, green months,
$/day, worst row and the count worse than −1R. Every published cell matches,
including the four the brief named:

| cell | report | fourth-pass referee |
|---|---|---|
| next_open core11 | 3629/0, +0.1718R, avgW/L +1.9888/−0.9989, 22/25, $1,250/day | identical |
| next_open full29 | 7857/0, +0.1690R, +1.9817/−0.9973, 23/25, $2,660/day | identical |
| close core11 | 3629/0, −0.0063R, +1.9881/−0.9990, 13/25, −$46/day | identical |
| close full29 | 7857/0, −0.0141R, +1.9823/−0.9980, 11/25, −$221/day | identical |

Unit: every traded signal (fired, legacy engine grade ≠ C, `reentry_84_rule`
excluded), 499 signal-days, 1R = $1,000. Fill: as named per arm. Exit: as each
book priced it. Script: `research/r1_referee4.py stats`. The `$/day`
denominator is **days with at least one signal (499)**, not calendar sessions —
inherited from `g90_fill_arms.arm_stats`, correct but worth stating.

**The uniform-exit table reproduces cell for cell** (`r1_referee4.py uniform`),
independently of pass 3:

| pool | exit model | as_booked | limit_level | next_open | chase_once | close | mid_candle |
|---|---|---:|---:|---:|---:|---:|---:|
| core11 | A close-only stop | $479 24/25 | $98 16/25 | $1,250 22/25 | −$397 10/25 | $1,139 20/25 | $627 20/25 |
| core11 | B intrabar touch | $395 22/25 | −$23 8/25 | $44 12/25 | −$1,457 3/25 | −$46 13/25 | −$720 7/25 |
| full29 | A close-only stop | $832 24/25 | $133 17/25 | $2,660 23/25 | −$756 8/25 | $2,437 22/25 | $1,108 17/25 |
| full29 | B intrabar touch | $681 24/25 | −$59 8/25 | $138 13/25 | −$2,661 1/25 | −$221 11/25 | −$1,865 5/25 |

Every cell equals the builder's republished table. The walk is validated at
both anchors from opposite directions: under model A it reproduces the five
`_walk` arms' own booked cells (`mid_candle` core11 +0.1056 vs booked +0.1057,
1e-4 rounding; the other four exact), and under model B it reproduces the
`close` arm the real `simulate_day` produced (−0.0063 core11, −0.0141 full29,
exact). Unit and fill as above; exit as labelled; script
`research/r1_referee4.py uniform`.

**Lookahead — clean, 120 rows, physically truncated** (`r1_referee4.py lookahead --n 30`).
For each sampled row the day is rebuilt from the raw CSV, the signal bar
located by its timestamp, and **every bar at or before it deleted**
(`bs[si+1:]`) before the fill is re-derived from what is left:

| arm | sampled | price re-derived | fill minute re-derived | fill at or before the signal bar |
|---|---:|---:|---:|---:|
| next_open | 30 | 30 | 30 | 0 |
| limit_level | 30 | 30 | 30 | 0 |
| chase_once | 30 | 30 | 30 | 0 |
| mid_candle | 30 | 30 | 30 | 0 |

`mid_candle`'s price reference (the midpoint of the completed signal bar's own
high/low) is taken as a scalar before truncation; the resting scan then sees
only bars strictly after it, so the signal bar is never scanned for a resting
fill. `chase_once` re-derived with `signal_runner.CHASE_PCT = 0.005`.

**`close` is the engine's own fill on 100% of rows, both pools**
(`r1_referee4.py closecheck`): `entry_fill.ENTRY_FILL == 'close'`,
`needs_future_bars()` is `False`, and the booked entry equals that minute's own
printed close in the raw archive on **7,857/7,857** (full29) and
**3,629/3,629** (core11) rows — 0 mismatches, 0 bars missing.
`as_booked`'s entry equals `close`'s on **0** of 7,857 rows.

**The one `entry_idx` mismatch, re-derived** (`r1_referee4.py achr`). ACHR
2026-04-06: 390 bars, 15 captured signals, 11 trades. The key
`('break_and_retest','call',5.665,'fired')` holds **two** signals, at candles
**16 and 20**; the counted trade carries `entry_idx = 20`, and the harness's
`used[k]` counter hands it the candle-16 signal, so the row is counted as a
mismatch and dropped. The builder's explanation is correct in every particular:
it is a correlation-key ambiguity in this harness's own bookkeeping, not in
`signal_runner`/`backtest_week`, and the row is absent from the books rather
than wrong. I also reproduce pass 2's caveat: the same day carries a second
colliding key, `('break_and_retest','put',5.605,'skipped_d')`, whose two
signals sit on the **same** candle (40) — a collision the counter cannot see,
so "1 of 7,858" is a lower bound on the class. That instance never reaches a
book.

**The `DISASTER_STOP` asymmetry does change the ranking — measured, not
plausible.** Holding the exit constant moves `close` from 5th to 3rd on full29
(model A, $2,437 against `next_open`'s $2,660) and collapses `next_open` from
$2,660/day, 23-of-25 green to **$138/day, 13-of-25 green** on the engine's own
intrabar-touch stop. Per the brief a *plausible* ranking change is
`not_enough`; this one is measured, so the ranking is **refuted**, exactly as
the builder now labels it.

**Paired next_open − close, held to one exit model** (`r1_referee4.py pairci`):

| pool | model A close-only | model B intrabar touch |
|---|---|---|
| full29 (n=7,538) | +0.0140R [+0.0047, +0.0234] | +0.0239R [+0.0136, +0.0341] |
| core11 (n=3,479) | +0.0141R [+0.0022, +0.0261] | **+0.0128R [+0.0001, +0.0256]** |

Both full29 figures match the builder's exactly. See new defect 17 for the
core11 cell the builder did not publish.

---

## New defects (fourth pass)

**15. The report generator still emits the refuted text, and the documented
Reproduce command overwrites the report with it.** `research/g210_fill_arms_v2.py:581`
still writes the header "Blind 2R exit" with no qualifier — over a table one of
whose six rows (`close`) is not on a blind 2R exit at all — and lines 712–720
still compose the `DISASTER_STOP` paragraph in the direction three referee
passes have now measured to be backwards ("`close`'s losses can be capped at
−1.000R intrabar while the other five arms' … can be worse than −1R"; measured:
`as_booked`, `next_open`, `chase_once` and `close` have **zero** rows worse than
−1R, `limit_level` has 28 and `mid_candle` 573). `main()` writes `a.out_md`
(line 756), whose default is the committed report. So
`python research/g210_fill_arms_v2.py --procs 8` — the command the report's own
**Reproduce** section gives — deletes the correction banner, both honest
tables, the size-gated table and both Refereed sections, and republishes the
refuted prose as if current. This is pass-2 defect 8, unfixed. It is also
**not listed** in the repair's own "Not fixed" section, which names only
`chase_once` and the stamp mismatch — so a repair pass whose job was disclosure
left its largest open item undisclosed. No published number moves today; the
next agent who re-runs the row inherits the refuted report.

**16. The refuted tables are still the report's first answer.** The two
six-arm headline tables (with `next_open` $1,250/$2,660 and `close`
−$46/−$221) sit at the top under a correction paragraph; the operative
uniform-exit table sits ~150 lines below, under "Refereed (pass 3)". A reader
going top-down reads the refuted ranking first. Presentation, not arithmetic —
but combined with defect 15 it means the row's committed deliverable still
leads with the wrong answer and its script can only regenerate that one.

**17. The published paired CI does not name its pool, and the claim
"separates from zero both ways" is a full29-only claim.** The builder's
numbers block gives model A `+0.0140R [+0.0047, +0.0234]` and model B
`+0.0239R [+0.0136, +0.0341]` with no pool label; both are full29. On
**core11 under model B — the engine's own exit** — the same statistic is
`+0.0128R [+0.0001, +0.0256]`: the lower bound is one ten-thousandth of an R
above zero, i.e. indistinguishable from zero at 95%. The direction survives on
full29; on the 11-symbol pool the spec actually names as the universe, under
the engine's real stop, it does not. Script: `research/r1_referee4.py pairci`.

**18. `g210_verify.py`'s `limit_level` *price* assertion is still
true-by-construction.** The new strictly-after check (repair 3) is a different
assertion and a good one, but the price check remains "the booked fill lies
inside the fill bar's `[low, high]`" — which `_resting_fill` guarantees, since
it only ever selects a bar whose range already brackets the price. The book
carries `level_price`; one comparison (`entry == level_price`) would make the
`limit_level` arm's actual claim falsifiable. Pass-2 defect 9 is half-fixed.
No number moves — my truncation test is the falsifiable version and it passes
30/30.

**19. The row landed inside an unrelated unattended auto-commit, so "one change
per row" cannot be read off the history.** `git show --stat 0f6a826a` is
`wip: auto-commit Sun 09/06/2026 0:23` over four files: the three R1 files and
**`research/o4_referee_pass3.py` (458 lines), which belongs to another agent's
row**. SWARM's commit protocol ("stage only files you own, by name";
`"<ROW>: <what> -- <the number that moved>"`) was not met, and the R1 repair is
not identifiable in the log. The builder disclosed this and correctly did not
rewrite the commit. Separately, the repair itself is three code changes
(`avg_win_loss` bucketing, a parent-process flag assignment in `main()`, a new
assertion in `g210_verify.py`) rather than one function; each is small and
**none moves a published number**, so this is named, not a reason to refute.

---

## Standard checks (fourth pass, all run here)

| check | result |
|---|---|
| sample size | smallest cell 252 trades (`limit_level` core11) over 25 months; smallest cell anywhere in the row 78 trades / 24 months (`limit_level` core11, size-gated table). Every cell ≥ 30 trades and ≥ 12 months. No under-sized cell carries a verdict. OK |
| every dollar names fill / exit / unit / script | in **this section**, yes on every figure. In the row's report: fill, unit and script yes; **exit still mis-named in the generated header** ("Blind 2R exit", defect 15). Partially fixed |
| stamps | 12/12 books carry `book_stamp`: `built_at` 2026-09-05T16:34:03–07, `git.commit`, `git.dirty_engine_py = []` on all 12, `dirty_py_count` 5–6 (non-engine), **70 flag values incl. `SCALE_PLAN: None`**, window `2024-09-04`→`2026-09-04`, script `research/g210_fill_arms_v2.py`. 11 stamp `57f2fbd2`, `fillarms_mid_candle_full29.json.gz` stamps `c7d52853`; **both are ancestors of `0f6a826a`** (checked). The tree was dirty at build time in non-engine `.py` only, and the report says so. OK |
| no book rewritten by this repair | confirmed — `0f6a826a` touches no file under `research/tape/` |
| one change per row | `git show --stat 0f6a826a`: 3 R1 research files + 1 file belonging to another row, no engine file, no book. See defect 19 |
| mark files | none in `git show --name-only 0f6a826a`; `git status --porcelain` shows only this pass's own untracked `research/r1_referee4.py`. No mark corpus touched. OK |
| verify gate at `0f6a826a` | run here: `regression_gate.py` **PASS** ("no baseline-fired mark went silent") · `test_runner_stop.py` **PASS** (70 checks) · `test_universe_single_source.py` **PASS** (29 symbols, no private lists). **Green** |
| `g210_verify.py` | exit **0**, reads raw `data_archive` CSVs, 20 sampled rows + 7857/7857 close rows |
| plain English | nothing in this row reaches Austin. OK |

---

## What R2 and R3 are handed, after four passes

1. **The mechanics of R1 are sound.** Fills, lookahead, the engine-fill
   identity, the `SCALE_PLAN` diagnosis and every book cell have now
   reproduced under four independent implementations. Nothing in the arm
   arithmetic needs re-running.
2. **Do not start R2 from `next_open`'s $2,660/day book.** On the engine's own
   intrabar-touch stop the same book is $138/day, 13-of-25 green.
3. **The fill question is real but tiny, and pool-dependent.** Held to one
   exit model, `next_open` beats `close` by +0.014R (A) to +0.024R (B) per
   trade on full29; on core 11 under the engine's exit the interval is
   [+0.0001, +0.0256] and should be read as no difference.
4. **Fix the generator before anyone re-runs `g210_fill_arms_v2.py`** — as it
   stands, that command deletes the row's corrected report and restores text
   three referee passes have refuted.

## Reproduce (fourth pass)

```
python research/r1_referee4.py stats
python research/r1_referee4.py avgwl
python research/r1_referee4.py closecheck
python research/r1_referee4.py lookahead --n 30
python research/r1_referee4.py uniform
python research/r1_referee4.py pairci
python research/r1_referee4.py scaleplan
python research/r1_referee4.py achr
python research/r1_referee4.py stamps
python research/g210_verify.py
```
