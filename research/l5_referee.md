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
