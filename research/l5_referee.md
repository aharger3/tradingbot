# L5 referee — **refuted**

**Row:** L5, `DAY_POLICY=3fires_stop_win_or_2loss`.
**Builder's commit:** `9b5fdc5a` ("L5: DAY_POLICY lands OFF -- no number yet").
**Builder's filed decision:** `not_enough`, "no number yet, build stage incomplete".
**Referee verdict:** **refuted.** The row's number does exist — the builder's own
background build finished after it filed — and on the settled core-11 lane the flag
is a **complete no-op**. Every dollar of the movement the ON book shows comes from
applying the policy to all 28 symbols and then reading the core 11.

Everything below is re-derived by `research/l5_referee.py` (committed beside this
page); full console output in `research/tape/logs/l5_referee_out.log`.

**Every dollar on this page names its terms once:** fill = honest close
(`backtest_2y.py` default `ENTRY_FILL=close`); exit = shipped engine, 1R hard stop
filled on the intrabar touch (`DISASTER_STOP_R=1.0`), `SCALE_PLAN=hod_then_runner_be`,
`LOSS_HALT` on; unit = `up_to_3_stop_win_or_2loss` on the 11 core symbols (the loop's
baseline unit, `research/tape/loop.json`); window 2024-09-04 → 2026-09-04, 499
sessions; script = `research/l5_referee.py`.

---

## What the flag actually is, and whether it matches the sentence

`omen_recall.py "day policy up to 3 S fires stop after a win or after 2 losses"`
returns, verbatim:

> **2026-09-05: day policy: up to 3 S fires; stop after a win or 2 losses.**
> First-S-only reported beside it.
> — `omen-rulebook.md`, "Decided 2026-09-05 (the /call 60, afternoon) — omen-10.0"

and the spec's settled table row:

> | day policy | **up to 3 S fires; stop after a win or after 2 losses**; "first S only" reported beside it |

`day_policy.py`'s rule — up to 3 taken trades, day ends on the first closed win or
the second closed loss — **is** that sentence, read causally. On semantics alone the
flag is faithful. Two mechanical assumptions I suspected of breaking it do **not**:

- `out` is populated on every taken row (`win` 1,797 / `loss` 2,222 / `scratch` 34),
  so the win- and loss-counters are live, not dead branches.
- `entry_i` is a **consistent per-day grid across symbols** — 0 of 2,751 adjacent
  intraday pairs have entry time increasing while `entry_i` decreases, and no
  `(day, entry-time)` pair maps to two different `entry_i`. Ordering and the
  "has it closed yet" arithmetic are sound.

The refutation is not the rule. It is where the rule is applied and what it is
stacked on.

---

## Defect 1 (decisive) — the whole number is a universe artifact

`backtest_2y.py` runs `day_policy.apply_to_book(rows)` over the **entire 28-symbol
book**. The loop's settled universe is `CORE_SYMBOLS` — 11 names
(`loop.json: universe.row_filter = tier == "core"`). So the ON arm measures a trader
who spends his three daily fires anywhere in 28 symbols, and then only his core-11
trades are counted.

| arm | whole $/day | green | trades | H1 $/day, green | H2 $/day, green |
|---|---:|---:|---:|---:|---:|
| OFF (= baseline `2c39ced2697c26cc`) | **−52** | 11/25 | 769 | +9, 6/12 | −111, 5/13 |
| ON as the row built it (28-sym) | **−34** | 10/25 | 717 | +50, 7/12 | −118, 3/13 |
| ON with the policy applied to the core 11 | **−52** | 11/25 | 769 | +9, 6/12 | −111, 5/13 |

The third row is identical to the first **in every cell**, even though the policy
blocks 1,072 core rows there. The gate verdicts follow: as built, H1 passes and H2
**fails** (green 5 → 3, and $/day −111 → −118, worse than the 5% ceiling) → hold;
applied to the correct lane, both halves pass trivially because nothing moves.

Sample sizes carry a verdict on every cell: whole 769 trades / 25 months, H1 382 / 12,
H2 387 / 13 — all above the 30-trade, 12-month floor.

Why it is a no-op on the right universe: the loop's baseline **unit**
(`loop_cycle.up_to_3_rows`) already applies the same rule with hindsight, and hindsight
is strictly stricter than causality here. Every row the causal pass blocks is a row the
lens had already stopped short of. Filtering the book first changes nothing the lens
then reports.

Why it is not a no-op on the wrong universe: removing a core row that a **non-core**
symbol's earlier win or losses knocked out shifts the lens's top-3 window down the day.
**20 core-11 sessions lose every candidate they had** (e.g. 2024-10-01: 7 core trades in
the OFF book, 0 in the ON book — the day was already "over" in non-core names before
QQQ fired at 09:50), and **137 rows the OFF arm never picked are promoted into the ON
arm**, against 188 removed. That churn, not the day policy, is the −52 → −34.

## Defect 2 — the two implementations disagree about the candidate pool

`day_policy.apply_to_book` counts only `status == "fired" and traded`.
`loop_cycle.up_to_3_rows` deliberately counts those **plus** `status == "halted"` — the
1,952 core rows (on 421 of 499 sessions) that R31's account-wide two-loss halt removed,
"so a halt this unit's OWN stop-rule would not have reached yet does not silently erase
the rest of that day". Stacking the two means the halt is inside one pool and outside
the other. The ON arm is therefore not "the day policy, more faithfully" — it is *the
causal policy over a pool without halted rows, then the look-ahead policy over a pool
with them.* No single trader's behaviour corresponds to that composition.

## Defect 3 — the spec asked for a unit, and the unit comparison was never made

The spec row reads: *"L5 — day policy `DAY_POLICY=3fires_stop_win_or_2loss`, **measured
as a unit** beside `first_of_day_arm`. Report daily loss distribution and the prop-firm
daily-loss pass rate."* The comparison that framing calls for changes the **unit**, not
the book — same baseline book, core 11:

| unit | whole $/day | green | trades | avg win ÷ avg loss |
|---|---:|---:|---:|---:|
| first of day | −39 | 9/25 | 498 | 1.064 |
| up to 3, stop on a win or 2 losses (shipped lens, look-ahead) | −52 | 11/25 | 769 | 1.119 |
| up to 3, stop on a win or 2 losses (**causal**) | **+16** | 11/25 | 1,031 | 1.121 |

The builder's own causality argument is correct and worth **$68/day** on this book —
but it belongs in the unit, where it would be an R3-level change to the loop's baseline,
not in a book filter underneath the existing unit. As a unit change it is out of scope
for an L-row; as a book filter it produced the artifact above. Either way the row as
built does not deliver it.

### The daily-loss numbers the row owed (and never reported)

Daily P&L, core 11, baseline unit, OFF arm: 498 days traded, median day **+$99**, worst
day **−$2,000**; 132 days at or below −$1,000 (73.5% pass), 70 at or below −$2,000
(85.9%), **0 below −$2,500 (100% pass)**.

That 100% is an artifact of the same look-ahead. On the **causal** reading the worst day
is **−$3,000** and **10 of 498 days breach a $2,500 daily-loss limit (98.0% pass)** —
three 1R losses can all be in flight before any of them closes. Any prop-firm claim
should quote the causal row, not the lens row.

## Defect 4 — the live lane silently ignores the new value

`live_scanner.py:1624` branches only on `_LIVE_DAY_POLICY == "one_and_done"`. With
`DAY_POLICY=3fires_stop_win_or_2loss` the live scanner falls through to
`MAX_TRADES_PER_DAY=3` / `CONSECUTIVE_LOSS_HALT=2` — i.e. exactly `first3`, which keeps
firing after a win. The flag named for Austin's ratified policy would not implement it
live. Harmless today (default is `first3`), but V4 makes the live default follow the
loop's shipped flags, so this is a live trap the moment the row ever ships.

## Defect 5 — process

`loop_cycle.py --stage build` exited **3221225794** (`0xC0000142`, a Windows process
teardown failure) *after* both books were written correctly, so `--stage gate` never
ran, `research/tape/cycles.md` has **no L5 row**, `loop_state.json` was not advanced,
`research/l5_day_policy.md` does not exist, and both books were left **untracked**. The
builder filed `not_enough` while its own number was already on disk.

## Defect 6 — stamps

`book_DAY_POLICY_off.json.gz`'s stamp carries `commit: ""` — an empty string, no commit
at all — so that book fails the stamped-book rule as written even though its `book_id`
independently proves its provenance. The ON book stamps `commit: 9b5fdc5a` with
`dirty_py_count: 1`; that one dirty file is almost certainly **this referee's own
untracked `research/l5_referee.py`**, created minutes before that build, and it is not
imported by the engine, so it does not touch the book. Both stamps carry `script: null`.

---

## What holds up

- **OFF book reproduces the baseline exactly**: `book_id 2c39ced2697c26cc`, equal to
  `loop.json`'s `baseline_book_id`. The code landing changed nothing at its default.
- **The ON book is exactly the OFF book plus the post-pass.** I derived an ON book by
  applying `day_policy.apply_to_book` to the stamped baseline in memory and it
  fingerprints to `bbf3ef57756b9614` — **the builder's ON book id, bit for bit**. So the
  flag adds no look-ahead into signal generation, changes no detection, and touches
  nothing but the post-build filter. This is the cleanest possible proof of the row's
  "one change" claim.
- **The two stamps differ in exactly one flag**: `signal_runner.DAY_POLICY`
  `first3 → 3fires_stop_win_or_2loss`. Nothing else moved.
- **The flag is in `research/book_stamp.py` `FLAG_SOURCES`**, and
  `day_policy.MAX_FIRES=3` / `day_policy.LOSS_STOP=2` are stamped into both books.
- **The default in code is `first3`** — the row is OFF, which is the correct default for
  an unmeasured research arm, and matches the decision.
- **One change per row respected**: `git show --stat 9b5fdc5a` = `backtest_2y.py` (+9),
  `day_policy.py` (new, 105), `research/book_stamp.py` (+7), `signal_runner.py` (+19).
  One flag, one enforcement module, its wiring and its stamp.
- **No mark file touched** — not in the commit, not in the working tree.
- **The verify gate is green at `9b5fdc5a`.** I ran all three myself:
  `regression_gate.py` exit 0, `test_runner_stop.py` exit 0,
  `test_universe_single_source.py` exit 0.
- **My arithmetic agrees with `loop_cycle.py`'s** on all 12 cells checked (2 units × 2
  arms × 3 slices), computed independently and cross-printed.

## What the dispatcher should do with this

1. The correct reading of L5 on the settled lane is **no change at all** — the day
   policy is already in the baseline unit, so the flag has nothing left to remove.
   That is a **hold**, and it is a hold on a *zero*, not on a −$18/day regression.
2. Before any future book-level day-policy pass is measured, it must be applied
   **inside the core-11 lane** and must share the unit's candidate pool (halted rows
   included), or it measures cross-universe churn.
3. The genuinely valuable finding here is the builder's causality argument, which is an
   **R3-level question about the baseline unit** (+$16/day vs −$52/day, and a worse
   prop-firm daily-loss profile: −$3,000 worst day, 10 breaches of $2,500), not an
   L-row. It deserves its own row, put to Austin as a measurement-honesty question.
4. `live_scanner.py` needs a branch for the third value before this flag can ever ship.

**Plain English, if a line of this reaches Austin:** the rule "take up to three a day,
stop after a win or after two losses" is already how we score every result, so switching
it on inside the engine changes nothing on your eleven main stocks. The only reason it
looked like it changed something is that the engine was spending the three daily trades
across twenty-eight symbols, then we were only counting eleven of them.

---
---

# L5 referee — PASS 2 (after the repair) — **refuted**

**Builder's commit under review:** `350b02fc` ("L5 repair: day_policy scoped to
core-11 lane + shared candidate pool (referee Defect-1/2) — $/day -52 -> -52,
green 11 -> 11, measured no-op both halves; ships as new default"), on top of
`5e8b5b89` (the `day_policy.py` repair itself).
**Builder's filed decision:** `ship`, default flipped to
`DAY_POLICY=3fires_stop_win_or_2loss`.
**Pass-2 verdict: refuted — the measurement, not the decision.** Every number the
builder published reproduces under independent arithmetic, both pass-1 defects are
genuinely fixed, and the flag is exactly the measured no-op it claims to be. **The
ship is what fails.** Flipping the default turns `backtest_2y.py`'s *default* book
into a different book, and the loop's own guard — "the OFF arm must fingerprint to
the baseline" — will now block every remaining L-row.

Everything below is re-derived by `research/l5_referee_pass2.py` (committed beside
this page; pass 1's `research/l5_referee.py` is left untouched as evidence). The
pass-2 script deliberately re-implements the unit rather than importing
`research/loop_cycle.py`, so the gate figures are independent of the code that
produced them.

**Terms, once:** fill = honest close (`backtest_2y.py` default `ENTRY_FILL=close`);
exit = shipped engine, 1R hard stop filled on the intrabar touch
(`DISASTER_STOP_R=1.0`), `SCALE_PLAN=hod_then_runner_be`, account-wide `LOSS_HALT`
on; unit = `up_to_3_stop_win_or_2loss` on the 11 core symbols (`research/tape/loop.json`)
unless a line names another; window 2024-09-04 → 2026-09-04, 499 sessions, 498 of
them with a fire; script = `research/l5_referee_pass2.py`.

---

## What the repair got right (re-derived, all of it)

| check | result |
|---|---|
| pass-1 Defect 1 (universe) fixed | **yes** — all **1,095** blocked rows are `tier=="core"`; 0 non-core rows touched |
| pass-1 Defect 2 (candidate pool) fixed | **yes** — pool is `(fired and traded) or halted`, byte-identical wording to `loop_cycle.up_to_3_rows`; halted rows occupy a slot and are never relabelled |
| OFF book == baseline | **yes** — `book_id 2c39ced2697c26cc` = `loop.json: baseline_book_id` |
| stamps differ in exactly one flag | **yes** — 77 flags stamped, 1 differs: `signal_runner.DAY_POLICY 'first3' -> '3fires_stop_win_or_2loss'` |
| stamp provenance | both books: `commit 5e8b5b89` (an ancestor of `350b02fc`), `dirty_py_count 0`, `dirty_engine_py []`, `built_at` 21:34 / 21:37, `entry_fill "close"`, 127,513 rows. `script` is `null` on both — a pre-existing `book_stamp.stamp()` gap the builder names |
| ON book is OFF + one post-pass | **yes** — applying `day_policy.apply_to_book` to the stamped baseline rows in memory fingerprints to **`205d3dcee96c5282`**, the ON book's stamped id, bit for bit |
| flag semantics vs the rulebook | **match** (quoted below) |
| `DAY_POLICY` in `book_stamp.FLAG_SOURCES` | **yes** |
| mark files | **none touched** in `5e8b5b89`, `350b02fc`, or the working tree |
| verify gate at `350b02fc` | **green** — I ran all three: `regression_gate.py` exit 0, `test_runner_stop.py` exit 0 (70 checks), `test_universe_single_source.py` exit 0 |

`omen_recall.py "day policy up to 3 S fires stop after a win or 2 losses"` returns,
verbatim:

> **2026-09-05: day policy: up to 3 S fires; stop after a win or 2 losses.**
> First-S-only reported beside it. — `omen-rulebook.md`, "Decided 2026-09-05
> (the /call 60, afternoon) — omen-10.0"

and the spec's settled row: *"day policy — up to 3 S fires; stop after a win or
after 2 losses; 'first S only' reported beside it."* `day_policy.py`'s rule — up to
3 taken trades, day over on the first **closed** win or the second **closed** loss —
is that sentence read causally. Not adjacent; faithful.

### The gate, recomputed with my own arithmetic

| arm | half | trades | $/day | green | months | avg win ÷ avg loss | fires/day |
|---|---|---:|---:|---:|---:|---:|---:|
| OFF | whole | 769 | **−51.59** | 11 | 25 | 1.119 | 1.541 |
| OFF | H1 | 382 | +8.84 | 6 | 12 | 1.308 | 1.540 |
| OFF | H2 | 387 | −111.30 | 5 | 13 | 0.949 | 1.542 |
| ON | whole | 769 | **−51.59** | 11 | 25 | 1.119 | 1.541 |
| ON | H1 | 382 | +8.84 | 6 | 12 | 1.308 | 1.540 |
| ON | H2 | 387 | −111.30 | 5 | 13 | 0.949 | 1.542 |

`research/tape/cycles.md`'s L5 row reads `-52.0 -> -52.0`, `11 -> 11`, H1 pass, H2
pass, 769 trades. Mine agrees in every cell (the row rounds −51.59 to −52). H1 and H2
drops are **0.00%**. Sample sizes clear both floors everywhere a verdict is given:
whole 769 trades / 25 months, H1 382 / 12, H2 387 / 13.

Daily P&L, core-11 baseline unit, 498 traded days: p5 −$2,000, p25 −$1,025, median
**+$99**, p75 +$627, p95 +$1,792, worst −$2,000, best +$9,732. Breaches: 132 days at
or below −$1,000 (73.5% pass), 70 at or below −$2,000 (85.9%), **0 below −$2,500
(100% pass)**. Fires histogram: 0 fires on 1 day, 1 on 229, 2 on 267, 3 on 2. Every
one of these reproduces the builder's table.

`first_of_day`, the unit the spec asks to be reported beside: **498 trades,
−$39.12/day, 9/25 green**, identical on both books. The builder's −$39 / 9-of-25 /
498 is right.

---

## Defect 1 (decisive) — the default flip breaks the loop's own baseline guard

`backtest_2y.py:293` calls `day_policy.apply_to_book(rows)` **unconditionally**; the
only gate is `signal_runner.DAY_POLICY`, whose default `350b02fc` changed. So a
plain `python backtest_2y.py` now produces a *different book*. Run at HEAD, 12-day
window:

    R31 loss halt: 75 trades blocked (ON)
    L5 day policy: 24 trades blocked (3fires_stop_win_or_2loss)
    book id 990d563cc3e06c05 from commit 350b02fc

`DAY_POLICY` is not set in `.env`, not in the process environment, and
`loop.json: rebuild.env` is `{}`. `loop_cycle.stage_build` builds the OFF arm with
`build_book({}, off_path, …)` — **no override** — then:

> `if base_id != off_id: decision = "blocked" … "the OFF arm's book_id does not
> match the configured baseline's — the code landing changed the book even with the
> flag at its default"`

At HEAD that comparison is `2c39ced2697c26cc` vs `205d3dcee96c5282` — proven by
re-derivation, not forecast: applying `day_policy.apply_to_book` at the HEAD default
to the stamped baseline's own rows blocks 1,095 rows and fingerprints to
`205d3dcee96c5282`. **L6, L7, L8 and every future cycle return `blocked` on the build
stage.** `loop.json` is untouched by `350b02fc` (`git show --stat`), so the baseline
was never re-pinned. L5 is the loop's first *ship*, and the loop has no re-baseline
step; the ship needed one and did not get it.

## Defect 2 (decisive) — "it costs nothing" is false for every reader but the gate

The gate measures one unit. The **default book** is read by all of them. Same two
books, core 11, same fill and exit:

| unit | OFF (baseline) | ON (the new default) |
|---|---|---|
| `up_to_3_stop_win_or_2loss` (the gate's unit) | 769 trades, −$51.59/day, 11/25 green | 769, −$51.59/day, 11/25 |
| `first_of_day` (the "reported beside" unit) | 498 trades, −$39.12/day, 9/25 | 498, −$39.12/day, 9/25 |
| **`every_signal`** | **1,909 trades, −$132.47/day, 10/25** | **814 trades, −$3.81/day, 12/25** |

`every_signal` loses **57% of its traded rows** and moves **+$129/day** on the
default book. That is not a no-op; it is a no-op *only through the one lens the gate
looks through*. Anything reading the default book on the whole-book unit — T1's tape,
the per-symbol tables, any future row that quotes "every traded signal" — silently
changes meaning at `350b02fc`. The builder's sentence in `signal_runner.py`,
"Shipped because it costs nothing," is not supported.

## Defect 3 — the gate that authorised the ship is vacuous

Of the 1,095 rows the flag blocks, **0** are rows the OFF arm's unit ever counted
(re-derived: `blocked rows that the OFF arm's unit actually counted: 0`). The gate
therefore compared the arm against itself. `pass / pass` here carries no information
about the flag. SWARM.md's law 2 makes the no-regression gate a **veto** on shipping,
not a warrant for it; "the gate mechanically returned decision=ship" is not a reason
to change a default. A no-op flag's correct landing is **hold on a zero** — which is
exactly what pass 1 recommended, and the builder agreed with the physics and shipped
anyway.

## Defect 4 — the live lane, now live and wrong

`live_scanner.py` contains no occurrence of the string `3fires_stop_win_or_2loss`
(checked); its only branch is `if _LIVE_DAY_POLICY == "one_and_done"` (line 1624), so
the third value falls through to `MAX_TRADES_PER_DAY=3` / `CONSECUTIVE_LOSS_HALT=2`,
i.e. `first3` — which keeps firing after a win. Meanwhile `live_scanner.py:502`
writes `"day_policy": "3fires_stop_win_or_2loss"` into the session record. Pass 1
filed this as harmless-while-OFF; the ship makes it **a live mislabel today**. The
builder named it and filed it as a follow-up task instead of blocking on it. A
default the live engine does not implement should not have gone in ahead of that fix.

## Defect 5 — two comments now assert the opposite of the shipped default

- `day_policy.py` module docstring: *"OFF unless `signal_runner.DAY_POLICY ==
  "3fires_stop_win_or_2loss"` (default stays `"first3"`, unchanged — L5 lands this
  OFF)."* — false at HEAD.
- `backtest_2y.py:292`: *"No-op unless DAY_POLICY=3fires_stop_win_or_2loss; OFF by
  default."* — false at HEAD.

`signal_runner.py`'s block was updated; these two were not. The next agent reading
either file will believe the flag is off.

## Defect 6 (minor, arithmetic) — a denominator

The report's prop-firm line reads "132/499 days breach (73.5% pass)". There are 499
sessions but **498** traded days (one session has no fire). 132/498 = 26.5% breach,
73.5% pass — the percentage quoted is right, the denominator printed beside it is
not.

## Carried over, still open (the builder named all three)

- Pass-1 Defect 3's substance — the **causal-own-picks** unit reads **+$16/day** on
  this book against the lens's −$52/day, and its prop-firm profile is worse
  (worst day −$3,000, 10 of 498 days breaching $2,500, 98.0% pass, against the lens's
  0 and 100%). That is an R3-level question about the loop's baseline unit, correctly
  ruled out of an L-row.
- `script: null` on every book stamp — a `book_stamp.stamp()` gap, not this row's.
- `live_scanner.py` needs the third branch (Defect 4).

---

## What the dispatcher should do

1. **Revert the default to `first3`** — one line, `signal_runner.py`. Keep
   `day_policy.py`'s repair (it is correct and now proven), keep both stamped books,
   keep the cycles row, and change its decision to **hold on a zero**. Without this
   the loop's next build stage returns `blocked`.
2. If a future call decides the default really should flip, the ship needs three
   companion steps in the same landing: re-pin `loop.json`'s `baseline_book`/
   `baseline_book_id` to the new default book, add the `live_scanner.py` branch, and
   correct the two comments in Defect 5.
3. The genuinely valuable finding remains the causal-unit question (+$16/day, worse
   daily-loss tail), and it is an R3 row, not an L row.

**Plain English, if a line of this reaches Austin:** the rule "take up to three a day,
stop after a win or after two losses" is already how we score every backtest, so
switching it on inside the engine changes nothing on your eleven main stocks — the
result is the same to the dollar. The problem is that switching it on also quietly
changed the standard two-year book everything else is measured against, and the live
scanner does not actually know how to follow the new setting. So the right move is to
leave the setting where it was and keep the fix.
