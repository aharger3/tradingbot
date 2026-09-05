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

