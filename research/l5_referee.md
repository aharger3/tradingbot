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


---

# L5 referee — PASS 3 — **refuted**

**Row:** L5, `DAY_POLICY`.
**Builder's commit under review:** `99b2bf0b` — "L5 repair (referee pass 2, 34c1546e):
DAY_POLICY default reverted to first3 (OFF)".
**Builder's filed decision:** `hold`.
**Referee verdict (pass 3): refuted — on the write-up and the ledgers, not on the
decision or the numbers.**

The decision is right and I could not break it. Every published number reproduces to
the dollar under a fourth independent implementation, the no-op is exact row-for-row,
the two stamps differ in exactly the one flag, and the OFF book is the baseline
bit-for-bit. What is refuted is the claim that this repair closed pass 2. Pass 2 asked
for **two** things in one landing — revert the default **and** "change its decision to
**hold on a zero**" in the cycles row. The builder did the first and explicitly
declined the second, and that omission is not cosmetic: it leaves a **committed test
failing at HEAD**, three ledgers asserting a ship that did not happen, and the row's
own report still telling the next reader that `3fires_stop_win_or_2loss` is the
default and is live.

Re-derived by `research/l5_referee_pass3.py` (committed beside this page). Nothing in
it imports `research/loop_cycle.py`, `research/g72_suppress_price.py` or the two
earlier referee scripts — the unit walk, the monthly buckets, the halves split and the
gate arithmetic are all re-implemented from the `loop.json` / SWARM.md definitions, so
a shared bug cannot make the builder's number and mine agree.

**Every dollar on this page names its terms once:** fill = honest close
(`backtest_2y.py` default `ENTRY_FILL=close`); exit = shipped engine, 1R hard stop
filled on the intrabar touch (`DISASTER_STOP_R=1.0`), `SCALE_PLAN=hod_then_runner_be`,
`LOSS_HALT` on; unit = `up_to_3_stop_win_or_2loss` on the 11 core symbols
(`research/tape/loop.json`, `universe.row_filter = tier == "core"`); window
2024-09-04 → 2026-09-04, 499 sessions (H1 248, H2 251); books
`research/tape/book_DAY_POLICY_{off,on}.json.gz`; script `research/l5_referee_pass3.py`.

---

## 1. The numbers — every cell reproduces (upheld)

My own gate, my own arithmetic, both books, boundary 2025-09-01:

| slice | sessions | OFF $/day | OFF green | OFF trades | ON $/day | ON green | ON trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| whole | 499 | −52 | 11/25 | 769 | −52 | 11/25 | 769 |
| H1 (< 2025-09-01) | 248 | +9 | 6/12 | 382 | +9 | 6/12 | 382 |
| H2 (≥ 2025-09-01) | 251 | −111 | 5/13 | 387 | −111 | 5/13 | 387 |

avg win ÷ avg loss **1.119** both arms; fires/day **1.541** both arms. Identical to
the published table in `research/l5_day_policy.md` and to `research/tape/cycles.md`'s
L5 row in every cell.

Stronger than "the summary statistics match": I compared the two unit row-sets key by
key — `(day, et, sym, pnl)` — and they are **identical, 769 for 769**. This is a true
no-op on the measured lane, not a coincidence of aggregates.

**The mechanism is confirmed, not just the total.** The ON book carries **1,095**
`status="day_policy_halt"` rows, all core-tier, and **0 of the 1,095** are rows the
OFF book's unit had picked. That is exactly the report's stated cause: the measurement
lens already applies the same rule with hindsight, which is strictly stricter than the
causal pass, so every row the causal pass can block was already outside the lens's
top-3 window.

**Sample size, per cell and per half:** whole 769 trades / 25 months; H1 382 / 12;
H2 387 / 13. Every cell clears the 30-trade and 12-month floor, so every verdict on
this page is allowed. No cell needed "not enough".

**The gate itself, re-derived, returns `ship`** (H1 pass, H2 pass — both arms
identical, so nothing can fall). The row is nonetheless correctly **held**, for a
reason that is *not* the no-regression gate: see §2.

## 2. The stamps and the baseline pin (upheld)

- OFF `book_id` **2c39ced2697c26cc** = `baseline_2026-09-05.json.gz` = `loop.json`'s
  `baseline_book_id`. The OFF-arm-equals-baseline guard holds.
- ON `book_id` **205d3dcee96c5282**.
- The two stamps differ in **exactly one** flag: `signal_runner.DAY_POLICY`
  `"first3"` → `"3fires_stop_win_or_2loss"`. Nothing else moved.
- Both built at commit `5e8b5b89`, `dirty_py_count = 0`, `dirty_engine_py = []`, and
  `5e8b5b89` is an ancestor of `99b2bf0b`.
- Both stamps carry **no `script` field and no `window` field** — the disclosed
  `book_stamp.stamp()` gap. `meta` carries `first/last/sessions`
  (2024-09-04 / 2026-09-04 / 499), so the window is recoverable, but the stamp itself
  does not satisfy "commit, dirty flag, every flag value, date, window, script" as
  written. Pre-existing, correctly flagged by the builder, not this row's to fix.

**The builder's headline reason for the hold checks out without a rebuild.**
`book_stamp.book_id` hashes `status` and `traded` per row; `backtest_2y.py:293` calls
`day_policy.apply_to_book(rows)` unconditionally and that call is a no-op only while
`signal_runner.DAY_POLICY != "3fires_stop_win_or_2loss"`. With the default flipped, a
bare `python backtest_2y.py --days 730` flips 1,095 rows to `day_policy_halt` and
therefore *must* produce `205d3dcee96c5282`, not the baseline. The claim is
mechanically forced by the two committed books at the same commit; it needed no
730-day rebuild to confirm, and I confirm it.

## 3. DEFECT 1 (blocking) — a committed test fails at HEAD

`research/test_live_follows_loop.py` (V4's parity test, refereed **upheld** at
`dc0f77bb` two commits before this landing) reads `research/tape/cycles.md` and
requires the live lane to carry whatever the tape says. At `99b2bf0b`:

```
AssertionError: live lane does not carry the loop's shipped defaults:
  DAY_POLICY: cycles.md says 'ship' (want '3fires_stop_win_or_2loss'),
              live_scanner has 'first3'
```

Exit code **1**. This is a test another row landed specifically so that "the live lane
can never silently drift from the loop", and this landing put it red. It is not in the
`verify:` line, which is why the builder's three green scripts did not catch it — but
it is committed, it is runnable, and it fails.

The fix is the half of pass 2's instruction the builder skipped: set the cycles.md
decision cell to `hold`. Then the test's `expected_env_value` returns `first3` and the
row goes green with no further code change.

## 4. DEFECT 2 (blocking) — three ledgers still assert a ship that did not happen

| ledger | says | truth at HEAD |
|---|---|---|
| `research/tape/cycles.md`, L5 row, decision cell | `ship` | held, default `first3` |
| `research/tape/loop_state.json`, cycle 5 | `"decision": "ship"` | held |
| `research/tape/loop.json`, `_comment` REBUILD PIN | "L5 (350b02fc) flipped … so a bare `python backtest_2y.py --days 730` at HEAD builds book_id 205d3dcee96c5282, not this baseline" | false since `99b2bf0b`; a bare build reproduces the baseline again |

`loop_state.json`'s `consecutive_holds` is also **0** on the strength of that ship.
Corrected to `hold` it becomes 1 — which matters, because the loop stops after five
consecutive holds and this project has already had that counter mis-set twice (its own
`_repair_note` records both). L1–L4 are four holds; recording L5 honestly makes the
next hold the fifth and triggers the card the spec asks for. Leaving it as `ship`
silently resets the loop's own stop condition.

The `loop.json` line is the least harmful (its pin is now conservative rather than
wrong-in-the-dangerous-direction), but it is the file every future L-row reads to
learn how to rebuild the baseline, and it currently tells them the opposite of the
truth.

## 5. DEFECT 3 (blocking) — the row's own report is now false in three sentences

`research/l5_day_policy.md` is untouched by this landing and still publishes:

1. "`signal_runner.DAY_POLICY=3fires_stop_win_or_2loss` (now the **default**…)"
2. "**Decision: ship** (loop controller, cycle 5)"
3. "…the flag's default was `first3` when the referee found this; **now that the
   default is `3fires_stop_win_or_2loss`, this is live**, not theoretical: a real
   session today would silently mismatch its own configured day policy."

All three are false at `99b2bf0b`. Sentence 3 is the worst kind of false — it is a
**safety warning that the revert actually resolved**, still standing as an open alarm.
A reader of this repo's own report cannot tell from it what the engine does.

This is the same defect class that refuted L1, L2, L3 and L4 in this swarm: the
decision is fine, the arithmetic is fine, and the published prose describes an engine
that no longer exists.

## 6. DEFECT 4 (material, undisclosed) — "stop after a win" has two definitions

`day_policy.py` decides a day is over on `is_win_key = out == "win"`.
`loop_cycle.up_to_3_rows` — the measurement unit this row is priced against, and the
R3 baseline — decides on `pnl > 0`. On the core-11 causal pool (3,861 rows) those two
disagree on **12 rows**, all of them `out == "scratch"` with a **positive** P&L,
several of them large: NVDA 2025-07-15 10:42 **+$4,825**, NVDA 2025-07-15 10:47
**+$6,714**, AAPL 2024-10-16 10:03 **+$4,788**, MSFT 2025-09-18 10:52 **+$4,779**,
NVDA 2026-05-13 10:40 **+$3,325**.

The lens calls those a win and ends the day; the causal flag does not and keeps firing.
On this book the divergence is invisible because the lens is strictly stricter
everywhere, so the totals still match to the cent — but the flag as written does **not**
enforce the same sentence the unit measures, and no report says so. If the causal unit
is ever promoted (the +$16/day R3 question pass 1 raised), this is a live discrepancy,
not a footnote.

`out == "loss"` and `pnl < 0` agree on 3,861 of 3,861 rows; only the win half diverges.

## 7. DEFECT 5 (semantics, inherited not invented) — "up to 3 **S** fires"

`omen_recall.py "day policy up to 3 S fires stop after a win or after 2 losses"`
returns, verbatim, the sentence this row must implement:

> 2026-09-05: **day policy: up to 3 S fires; stop after a win or 2 losses.**
> First-S-only reported beside it.
> — `omen-rulebook.md`, "Decided 2026-09-05 (the /call 60, afternoon) — omen-10.0"

and the spec's settled table row, verbatim:

> **day policy** — **up to 3 S fires; stop after a win or after 2 losses**;
> "first S only" reported beside it.

`day_policy.py` counts **every** fired-and-traded core row toward the three slots and
the win/loss stop, with no grade test at all. Of the 769 rows the unit actually books,
`sgrade` is **C on 434 (56.4%)**, **A on 187 (24.3%)** and **S on only 148 (19.2%)**.
So "up to 3 S fires" is implemented as "up to 3 fires".

I am **not** refuting the row on this. The same is true of `loop_cycle.up_to_3_rows`,
i.e. of the R3 baseline unit itself (upheld at `b601e54a`), and `CLAUDE.md` records
that gating on `sgrade == "S"` was already priced at **−$29/day** and that
`compute_austin_tier` is reported-only. This is a settled repo-wide design, not an L5
invention. What *is* a defect is the report's sentence "`day_policy.py`'s rule … **is
that sentence**, read causally" — it is that sentence with its subject silently
widened, and the report should say so rather than claim an exact match.

## 8. What is clean

- One change per row: `git show --stat 99b2bf0b` = `signal_runner.py` only, and inside
  it only the `DAY_POLICY` default line and its comment block.
- No mark file touched, in the commit or in the tree.
- `verify:` gate green at `99b2bf0b`, run by me: `research/regression_gate.py` PASS,
  `research/test_runner_stop.py` exit 0, `research/test_universe_single_source.py`
  exit 0.
- The default matches the decision: a research arm does not default ON, and
  `DAY_POLICY` now defaults to `first3`.
- `DAY_POLICY` is in `research/book_stamp.py` `FLAG_SOURCES`, and so are
  `day_policy.MAX_FIRES` / `day_policy.LOSS_STOP`.
- The revert genuinely removes pass-1 Defect 4's live risk: with the default back at
  `first3`, `live_scanner.py`'s missing third branch is theoretical again.

## 9. The push line

Cycle 5's ntfy push read, in effect:

> `[OMEN] cycle 5: up to three trades a day, stop after a win or two losses (repair)
> -- shipped. $/day -52.0 -> -52.0, green months 11 -> 11`

Plain English, apart from the bare "(repair)". But it told Austin the rule **shipped**,
and it did not. Whoever fixes the cycles row should send the correction in the same
plain language.

## 10. What the dispatcher should do

One bookkeeping row, no engine code, no rebuild:

1. `research/tape/cycles.md` — L5 decision cell `ship` → `hold`, with an HTML comment
   beside it saying the gate passed on a delta of exactly zero and the row is held
   because shipping it moves the default book away from the baseline. That single edit
   turns `research/test_live_follows_loop.py` green.
2. `research/tape/loop_state.json` — cycle 5 `"decision": "hold"`, and
   `consecutive_holds` recomputed (it becomes 5 across L1–L5, which is the loop's own
   stop condition and should be allowed to fire, not suppressed).
3. `research/tape/loop.json` — replace the REBUILD PIN paragraph; a bare build
   reproduces the baseline again as of `99b2bf0b`.
4. `research/l5_day_policy.md` — the three false sentences in §5 above, plus the
   semantics qualifier in §7 and the two-definitions-of-a-win disclosure in §6.

None of that changes a number. Nothing here should be deleted: both books, both
earlier referee passes and this one stay as the evidence trail.

**Plain English, if a line of this reaches Austin:** the rule "take up to three a day,
stop after a win or after two losses" is already exactly how we score every backtest,
so switching it on inside the engine changes nothing on your eleven main stocks — same
result to the dollar, 769 trades either way. Somebody correctly switched it back off
last night, because leaving it on quietly changed the standard two-year book that
everything else gets compared against. What they did not do is update the three
scoreboards, so the notes still say the rule shipped when it did not, and one of our
own automatic checks is now failing because of it. Nothing about your money changed;
the paperwork is wrong and needs ten minutes.

---

# L5 referee — PASS 4 — **refuted**

**Row:** L5, `DAY_POLICY`.
**Builder's commit under review:** `58c00a7b` — "L5 repair: complete pass-2's
instruction -- flip cycles.md/loop_state.json decision to hold, set
consecutive_holds=5 and stop=true, fix loop.json rebuild pin, correct
l5_day_policy.md's false headline sentences, disclose win-definition and
S-grade-scope gaps (referee pass 3)".
**Builder's filed decision:** `hold`.
**Referee verdict (pass 4): refuted — on the write-up again, not on the decision
and not on a single number.**

Five of pass 3's six findings are genuinely closed: the committed parity test is
green, all three ledgers now say `hold`, the stop counter is honest, and both
semantics gaps are disclosed. The hold is right and I could not break it — every
cell reproduces to the dollar under a **fifth** independent implementation, and
this time even pass 1's `causal-own-picks` figures reproduce exactly, which no
earlier pass had re-derived. What is refuted is that the commit did what its own
message says it did. It claims to have fixed "l5_day_policy.md's three false
headline sentences"; there were **four**, and the one still standing is inside the
section headed *"What holds for the referee to re-derive"* — the checklist the
next referee is pointed at. And the disclosure this commit **added** publishes a
ceiling that is 40% below the real one.

Re-derived by `research/l5_referee_pass4.py` (committed beside this page). It
imports nothing from `research/loop_cycle.py`, `research/g72_suppress_price.py`,
`research/day_policy.py` or the three earlier referee scripts: the universe
filter, the unit walk, the monthly buckets, the halves split and the gate
arithmetic are re-implemented from `research/tape/loop.json` and SWARM.md.

**Every dollar on this page names its terms once:** fill = honest close
(`backtest_2y.py` default `ENTRY_FILL=close`); exit = shipped engine, 1R hard stop
filled on the intrabar touch (`DISASTER_STOP_R=1.0`), `SCALE_PLAN=hod_then_runner_be`,
`LOSS_HALT` on; unit = `up_to_3_stop_win_or_2loss` on the 11 core symbols
(`loop.json`, `universe.row_filter = tier == "core"`); window 2024-09-04 →
2026-09-04, 499 sessions (H1 248, H2 251); books
`research/tape/book_DAY_POLICY_{off,on}.json.gz`; script
`research/l5_referee_pass4.py`.

---

## 1. Pass 3's defects — what is actually fixed

| pass-3 defect | status at `58c00a7b` | how I checked |
|---|---|---|
| D1 `research/test_live_follows_loop.py` RED at HEAD | **fixed** — exit 0, "OK: live lane matches research/tape/cycles.md's shipped defaults." | ran it |
| D2 three ledgers assert a ship | **fixed** — `cycles.md` L5 decision cell `hold`; `loop_state.json` cycle 5 `"decision": "hold"`; `loop.json` REBUILD PIN rewritten and now correct (a bare `backtest_2y.py --days 730` at HEAD does reproduce `2c39ced2697c26cc`, because `signal_runner.DAY_POLICY` imports as `first3`) | read all three; imported the module |
| D2b `consecutive_holds` stuck at 0 | **fixed** — `5`, and `loop_state.json` history reads `['hold','hold','hold','hold','hold']`; `stop: true`, `stop_reason: "5 consecutive holds"`, byte-identical to `loop_cycle.py:421`'s own string with `MAX_CONSECUTIVE_HOLDS = 5` | read both files |
| D3 three false sentences in `l5_day_policy.md` | **partly fixed — see DEFECT A** | grepped the file |
| D4 "stop after a win" has two definitions | **disclosed — but with a false bound, see DEFECT B** | re-derived all 12 rows |
| D5 "up to 3 **S** fires" implemented with no grade test | **fixed (disclosed)** — my own count of the 769 unit rows: `C` 434 (56.4%), `A` 187 (24.3%), `S` 148 (19.2%), exactly as published | independent `Counter` over the unit |

## 2. The numbers — every cell reproduces (upheld)

My arithmetic, both stamped books, boundary 2025-09-01:

| slice | sessions | OFF $/day | OFF green | OFF trades | ON $/day | ON green | ON trades | aw÷al |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| whole | 499 | −52 | 11/25 | 769 | −52 | 11/25 | 769 | 1.119 / 1.119 |
| H1 (< 2025-09-01) | 248 | +9 | 6/12 | 382 | +9 | 6/12 | 382 | 1.308 / 1.308 |
| H2 (≥ 2025-09-01) | 251 | −111 | 5/13 | 387 | −111 | 5/13 | 387 | 0.949 / 0.949 |

fires/day **1.541** both arms. My gate: H1 `{enough: true, pass: true}`, H2
`{enough: true, pass: true}` → the gate itself returns `ship` on a delta of
exactly zero, and the row is nonetheless correctly **held** for the separate
reason pass 2 established (shipping it moves the default book away from the
pinned baseline). This matches `research/tape/cycles.md`'s L5 row **cell for
cell**: `hold | -52.0 -> -52.0 | 11 -> 11 | pass | pass | 769`.

Stronger than matching aggregates: the two unit row-sets are **identical, 769
for 769**, on the key `(day, et, sym, pnl)`. The ON book carries **1,095**
`status="day_policy_halt"` rows, **all core-tier**, and **0 of the 1,095** were
ever picked by the OFF unit. A true no-op, mechanism confirmed.

**Sample size, per cell and per half:** whole 769 trades / 25 months; H1 382 / 12;
H2 387 / 13. Every cell clears the 30-trade and 12-month floor, so every verdict
here is allowed. No cell needed "not enough".

**Also reproduced, and no earlier pass had done this:** pass 1's `causal-own-picks`
unit — the time-aware walk where a stop condition only counts once the trade has
actually closed (`research/l5_referee.py::unit_up_to_3_causal`) — re-implemented
from scratch gives **1,031 trades, +$16/day, 11/25 green, worst day −$3,000,
10 of 498 traded days breaching a $2,500 daily-loss limit (98.0% pass)**, exactly
as `research/l5_day_policy.md` publishes. I first tried three simpler readings of
"day_policy's own picks" and got 769 / 814 / 2,766 rows; the published figures are
right and the simpler readings were mine, not the report's. `first_of_day` on the
same book: **498 trades, −$39/day, 9/25 green** — also exact.

The whole-window distribution and the prop-firm cells reproduce from the committed
`research/l5_day_policy_stats.py`: p5 −2,000 / p25 −1,024 / median +99 / p75 +624 /
p95 +1,793 / worst −2,000; `$1,000 limit → 132/499 breach (73.5% pass)`,
`$2,500 limit → 0/499 (100% pass)`; fires histogram 1/229/267/2. Both readings
identical, as published.

## 3. The stamps and the baseline pin (upheld)

- The OFF book is the baseline **row for row**, not merely by hash: all 127,513
  rows agree on `(day, sym, et, status, traded, pnl, out, entry, stop)`.
  Recomputed `book_id` OFF = baseline = **2c39ced2697c26cc** =
  `loop.json: baseline_book_id`. ON = **205d3dcee96c5282**.
- The two flag stamps differ in **exactly one** key:
  `signal_runner.DAY_POLICY: 'first3' → '3fires_stop_win_or_2loss'`. Nothing else.
- Both built at commit `5e8b5b89`, `dirty_py_count = 0`, `dirty_engine_py = []`,
  and `git merge-base --is-ancestor 5e8b5b89 58c00a7b` succeeds — the stamp's
  commit is an ancestor of the row's commit, and the tree was clean.
- Both stamps still carry **no `script` and no `window` field** — the
  pre-existing `book_stamp.stamp()` gap, correctly disclosed by the builder and
  not this row's to fix. `meta` carries `first`/`last`/`sessions`
  (2024-09-04 / 2026-09-04 / 499), so the window is recoverable.

## 4. Semantics, default and plumbing (upheld)

`omen_recall.py "day policy up to 3 S fires stop after a win or 2 losses"`
returns, verbatim, the sentence this row must implement:

> 2026-09-05: **day policy: up to 3 S fires; stop after a win or 2 losses.**
> First-S-only reported beside it.
> — `omen-rulebook.md`, "Decided 2026-09-05 (the /call 60, afternoon) — omen-10.0"

and the spec's settled table row, verbatim:

> | day policy | **up to 3 S fires; stop after a win or after 2 losses**; "first S only" reported beside it |

`day_policy.py`'s rule is that sentence with its subject widened from "S fires"
to "fires" — the report now says so instead of claiming an exact match, which is
the correction pass 3 asked for. The widening is the R3 baseline unit's own scope
(`loop_cycle.up_to_3_rows`), settled repo-wide, not an L5 invention.

- **Default matches the decision.** `signal_runner.py` line reads
  `DAY_POLICY = os.getenv("DAY_POLICY", "first3").strip().lower()`; importing the
  module gives `'first3'`. A held research arm does not default ON. ✔
- **`DAY_POLICY` is in `research/book_stamp.py` `FLAG_SOURCES`**, in the
  `signal_runner` group (line 50 of the tuple). ✔
- **One change per row.** `git show --stat 58c00a7b` = four files, all ledgers and
  prose (`research/l5_day_policy.md`, `research/tape/cycles.md`,
  `research/tape/loop.json`, `research/tape/loop_state.json`). No engine code, no
  rebuild, no number moved. ✔
- **No mark file touched**, in the commit or in the working tree. ✔
- **Verify gate green at `58c00a7b`, run by me:** `research/regression_gate.py`
  PASS (exit 0), `research/test_runner_stop.py` exit 0 (70 checks),
  `research/test_universe_single_source.py` exit 0. Plus
  `research/test_live_follows_loop.py` exit 0. ✔
- **`cycles.md`'s push line is plain English** — "up to three trades a day, stop
  after a win or two losses" — apart from the trailing "(repair)", which pass 3
  already flagged and which survives. Minor.

## 5. DEFECT A (blocking) — the fourth false sentence, in the section a referee is sent to

The commit message says it "correct[ed] `l5_day_policy.md`'s **three** false
headline sentences". There were four. `research/l5_day_policy.md`, lines 216–218,
untouched by this commit, still reads:

> - `signal_runner.DAY_POLICY` default flipped `first3 → 3fires_stop_win_or_2loss`
>   in this same landing (commit named below), consistent with the row's step
>   6 ("gate passes on both halves → flip default, verify, commit").

Every clause is false at HEAD. The default was **not** flipped — it was flipped at
`350b02fc` and reverted at `99b2bf0b`; `signal_runner.DAY_POLICY` imports as
`'first3'`. Step 6 did **not** execute. And "(commit named below)" names no
commit: the file ends two bullets later.

This is worse than the three the repair did fix, for two reasons. First, it sits
under the heading **"What holds for the referee to re-derive"** — a list whose
whole purpose is to tell the next reader which facts are load-bearing, and it
asserts the single fact this entire three-pass repair sequence exists to correct.
Second, it flatly contradicts the same file's own header seven lines from the top
("the **default stays `first3`**"), so the report now argues with itself and a
reader has no way to tell which half is current.

Same defect class that refuted L1, L2, L3 and L4 in this swarm, on its fourth
consecutive appearance in this row: the decision is fine, the arithmetic is fine,
and the published prose describes an engine that does not exist.

## 6. DEFECT B (material) — the disclosure this commit added publishes a false ceiling

New in `58c00a7b`, the Refereed section's win-definition disclosure:

> They disagree on 12 of 3,861 core-11 causal-pool rows, all `out=="scratch"`
> with positive P&L (**up to +$6,713.75**, NVDA 2025-07-15 10:47)

The pool size (3,861) and the count (12) are right; I get both. The ceiling is
not. All 12, re-derived, sorted by P&L:

| day | et | sym | out | status | pnl |
|---|---|---|---|---|---:|
| 2025-12-23 | 10:30 | AMZN | scratch | halted | **+$9,428.57** |
| 2026-05-22 | 10:41 | PLTR | scratch | halted | **+$8,603.96** |
| 2025-07-15 | 10:47 | NVDA | scratch | halted | +$6,713.75 |
| 2025-07-15 | 10:42 | NVDA | scratch | halted | +$4,824.56 |
| 2024-10-16 | 10:03 | AAPL | scratch | halted | +$4,787.88 |
| 2025-09-18 | 10:52 | MSFT | scratch | halted | +$4,779.41 |
| 2026-05-13 | 10:40 | NVDA | scratch | halted | +$3,324.81 |
| 2026-09-01 | 10:43 | MSFT | scratch | halted | +$2,880.06 |
| 2026-08-27 | 09:49 | AMZN | scratch | halted | +$1,720.93 |
| 2026-08-11 | 10:34 | MSFT | scratch | halted | +$1,552.08 |
| 2024-11-22 | 10:46 | GOOGL | scratch | halted | +$1,459.46 |
| 2026-05-22 | 10:21 | META | scratch | halted | +$1,259.45 |

The true maximum is **+$9,428.57**, 40.4% above the published bound, and two rows
exceed it. The repair copied pass 3's illustrative top-five list — which was
labelled "several of them large", not a maximum — and reprinted its largest entry
as "up to". A disclosure whose whole point is *how big the divergence can get*
understates the divergence.

One thing the table adds that no pass has said: **all 12 are `status == "halted"`**
— they are R31 account-halt rows carried into the pool, never `fired and traded`.
So the divergence lives entirely in the halted arm of the candidate pool, which
narrows where it could ever bite if the causal unit is promoted (the +$16/day R3
question). Worth a sentence in the report; there is none.

## 7. What is clean, in one list

Books stamped and clean; OFF = baseline row-for-row; one-flag stamp diff; commit
`5e8b5b89` an ancestor of `58c00a7b`; gate reproduces cell-for-cell; unit row-set
identical 769-for-769; every sample size clears the floor; default is `first3`;
`DAY_POLICY` in `FLAG_SOURCES`; one change per row; no mark file touched; all four
tests green at HEAD; `causal-own-picks`, `first_of_day` and the prop-firm cells all
re-derive exactly.

## 8. What the dispatcher should do

One more bookkeeping edit, no code, no rebuild, no number:

1. `research/l5_day_policy.md`, the bullet at lines 216–218 — delete it or replace
   it with the truth: the default was flipped at `350b02fc`, refuted at pass 2
   (`34c1546e`) and **reverted at `99b2bf0b`**; the shipped default is `first3` and
   step 6 did not run. While there, name the commit that "(commit named below)"
   promises, or drop the phrase.
2. Same file, the win-definition disclosure — change "up to +$6,713.75, NVDA
   2025-07-15 10:47" to "**up to +$9,428.57** (AMZN 2025-12-23 10:30; PLTR
   2026-05-22 10:41 at +$8,603.96 is second)", and add that all 12 divergent rows
   are `status == "halted"`.
3. Optional, carried from pass 3 and still open: the cycle-5 ntfy push told Austin
   the rule shipped. No correction has been sent.

Nothing here should be deleted. Both books, all four referee passes and both
referee scripts stay as the evidence trail.

**Plain English, if a line of this reaches Austin:** the rule "take up to three
trades a day, stop after a win or after two losses" is already exactly how we
score every backtest, so switching it on inside the engine changes nothing on your
eleven main stocks — same result to the dollar, 769 trades either way, and it is
correctly switched off. Last night's fix repaired the three scoreboards that were
wrong, and the automatic check that was failing is green again. Two things in the
write-up are still wrong: one paragraph still tells the next reader the rule was
switched on when it was not, and a footnote that measures how far two definitions
of "a winning trade" can drift apart quotes the third-largest gap instead of the
largest ($6,714 instead of $9,429). Neither changes a dollar of your results. Ten
more minutes of paperwork.
