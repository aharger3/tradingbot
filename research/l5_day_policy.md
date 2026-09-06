# L5 — day policy: up to 3 S fires a day, stop after a win or 2 losses

**Flag:** `signal_runner.DAY_POLICY=3fires_stop_win_or_2loss` (now the **default**,
`day_policy.py` enforces it causally, scoped to `tier=="core"` rows, on the built book).
**Decision: ship** (loop controller, cycle 5) — but read the numbers section before
treating "ship" as "this moved something": on the settled core-11 lane it is a
**measured no-op**. Every cell of the gate below is identical before/after.

**Recall (`research/omen_recall.py "day policy up to 3 S fires stop after a win or
after 2 losses"`)**, quoted verbatim:

> 2026-09-05: **day policy: up to 3 S fires; stop after a win or 2 losses.**
> First-S-only reported beside it.
> — `omen-rulebook.md`, "Decided 2026-09-05 (the /call 60, afternoon) — omen-10.0"

Matches the spec's settled table row exactly. `day_policy.py`'s rule — up to 3
taken trades, day ends on the first CLOSED win or the second CLOSED loss — is
that sentence, read causally (a trade only counts once it has actually closed,
the same discipline `loss_halt.py` uses for R31).

Every dollar below names its terms once: **fill** = honest close
(`backtest_2y.py` default `ENTRY_FILL`); **exit** = shipped engine, 1R hard stop
on the intrabar touch (`DISASTER_STOP_R=1.0`), `SCALE_PLAN=hod_then_runner_be`,
account-wide `LOSS_HALT` on; **unit** = `up_to_3_stop_win_or_2loss` on the 11
core symbols (`research/tape/loop.json`, the loop's baseline unit) unless a row
says "causal-own-picks"; **window** 2024-09-04 → 2026-09-04, 499 sessions;
**script** = `research/loop_cycle.py` (gate) / `research/l5_day_policy_stats.py`
(distributions) / `research/l5_referee.py` (independent cross-check).

---

## Referee section

`research/l5_referee.md` **refuted** the first landing (commit `9b5fdc5a`). Its
verdict: the row's own background build had finished with a real number on
disk (`not_enough` was wrong to file), and that number was an **artifact**:
`backtest_2y.py` ran `day_policy.apply_to_book(rows)` over the whole 28-symbol
book while the loop's settled universe is the core 11
(`loop.json: universe.row_filter = tier == "core"`), so the flag blocked 1,072
core rows the gate never sees applied inside its own lane, while cross-universe
churn (20 core sessions losing every candidate to an earlier non-core stop;
137 rows promoted that the OFF arm never picked) produced the apparent
-$52 → -$34/day movement. A second defect: `day_policy.apply_to_book` counted
only `status=="fired" and traded`, while the loop's own unit
(`loop_cycle.up_to_3_rows`) also counts `status=="halted"` rows (R31's
account-wide two-loss halt) — two different candidate pools stacked on each
other, corresponding to no single trader's behavior.

**What changed in the repair (`day_policy.py`, no engine-code edit):**

1. **Defect 1 fixed.** `apply_to_book`'s per-day candidate pool is now
   filtered to `tier == "core"` before the causal walk — the same slice the
   settled unit (`loop_cycle.up_to_3_rows`, driven by `loop.json`) measures.
   A non-core row is never counted toward a day's 3 slots or its win/loss
   stop, and never gets blocked by this flag.
2. **Defect 2 fixed.** The candidate pool now matches
   `loop_cycle.up_to_3_rows`'s own pool exactly: `(status=="fired" and
   traded)` **or** `status=="halted"`. A halted row (kept by `loss_halt.py`
   with every measured field, so it still carries a real `pnl`/`out`) still
   occupies a slot and can trip the win/loss stop, but its `status` is left
   alone — day_policy never relabels an R31 halt as its own, which would
   have erased that halt's own count.
3. **Rebuilt both arms clean.** OFF book_id `2c39ced2697c26cc` — bit-for-bit
   the R3 baseline (`baseline_2026-09-05.json.gz`), proving the code change
   is inert at its default. ON book_id `205d3dcee96c5282`, now blocking
   **1,095** core-tier rows (up from the flawed 28-symbol version's 1,072,
   because halted rows now correctly occupy slots too) — commit `5e8b5b89`,
   `dirty_py_count=0` on both stamps (the earlier landing's `commit: ""` on
   the OFF book — Defect 6 — does not reproduce on this rebuild; both stamps
   now carry a real commit and a clean tree).

**Result after the repair — the referee's own prediction, confirmed exactly:**
applied inside the correct lane with the correct pool, the flag is a
**complete no-op** on every cell (see Numbers, below). This matches Defect 1's
own explanation: the loop's baseline unit already applies the identical rule
with **hindsight** (reads a day's picks back with their final `pnl` already
known), which is strictly **stricter** than the causal version — every row the
causal pass can block is a row the look-ahead lens had already excluded from
its top-3 window. There is no daylight left between "the flag is off" and "the
flag is on, correctly scoped" for this measurement.

**Not fixed in this row (out of the one-change budget, or genuinely a
different row):**

- **Defect 3** (the spec's own "measured as a UNIT beside first_of_day_arm"
  comparison) is unresolved. The referee's own numbers stand: on this book,
  `first_of_day` reads -$39/day (9/25 green, 498 trades); the shipped
  look-ahead lens reads -$52/day (11/25, 769 trades); the **causal-own-picks**
  unit (day_policy's picks read directly, not through the lens) reads
  **+$16/day** (11/25, 1,031 trades) — a real, +$68/day-relative finding, but
  it is a proposed change to the **loop's baseline unit itself**
  (`research/loop_cycle.py::up_to_3_rows`), an R3-level question, not
  something an L-row can ship as a book filter. Flagging for Austin as a
  measurement-honesty question, per the referee's recommendation.
- **Defect 4** (`live_scanner.py` has no branch for
  `3fires_stop_win_or_2loss`, so a live session would silently run `first3`
  behavior) is untouched — `live_scanner.py` is not in this row's authorized
  edit and the flag's default was `first3` when the referee found this;
  now that the default is `3fires_stop_win_or_2loss`, **this is live**, not
  theoretical: a real session today would silently mismatch its own
  configured day policy. This needs a live_scanner.py fix before the next
  live run and is flagged here as a blocking follow-up, not resolved.
- **`script: null`** on both book stamps (Defect 6, second half) is a
  pre-existing gap in `research/book_stamp.py::stamp()` — no book of any kind
  stamps which script built it; `backtest_2y.py`'s call site never passes a
  `script=` kwarg. Out of this row's one-function budget (fixing it means
  editing `backtest_2y.py`, engine code, for a second unrelated reason).
  Flagging for a future row.

## Numbers (loop gate, cycle 5, `research/tape/cycles.md`)

| | OFF (baseline) | ON (day policy, repaired) |
|---|---:|---:|
| book_id | `2c39ced2697c26cc` | `205d3dcee96c5282` |
| $/day (whole, 25mo) | −52 | −52 |
| green months | 11/25 | 11/25 |
| trades | 769 | 769 |
| H1 (12mo) $/day, green | +9, 6/12 | +9, 6/12 |
| H2 (13mo) $/day, green | −111, 5/13 | −111, 5/13 |
| avg win ÷ avg loss | 1.119 | 1.119 |

H1: **pass** (enough=true, 382 trades/12mo). H2: **pass** (enough=true, 387
trades/13mo). Both halves trivially identical to OFF — sample sizes clear the
30-trade / 12-month floor everywhere a verdict is given.

`target_met`: **false** (per `loop_state.json` — the loop's target is
$/day ≥ some positive floor with every month green; −$52/day, 11/25 green,
does not meet it, independent of this flag).

## Fires/day before → after

Both readings: **1.541 fires/day** (769 fired-and-taken rows / 499 sessions).
No movement — the causal enforcement never reaches a row the lens's own
hindsight had not already excluded.

## Daily P&L distribution (core 11, `research/l5_day_policy_stats.py`)

Both the LENS unit (loop's baseline, look-ahead) and the CAUSAL unit read
**through the same lens** (day_policy's marks applied first, then
`up_to_3_rows` reads the result) are **identical**, all 499 sessions:

| | p5 | p25 | median | p75 | p95 | worst |
|---|---:|---:|---:|---:|---:|---:|
| LENS (baseline) | −2,000 | −1,024 | +99 | +624 | +1,793 | −2,000 |
| CAUSAL (repaired, through the lens) | −2,000 | −1,024 | +99 | +624 | +1,793 | −2,000 |

**Prop-firm daily-loss pass rate**, both readings: **$1,000 limit → 132/499
days breach (73.5% pass)**; **$2,500 limit → 0/499 days breach (100% pass)**.

That 100% is the look-ahead artifact the referee named in Defect 3: reading
day_policy's own picks **without** the lens's hindsight (the causal-own-picks
unit above) puts the worst day at **−$3,000** with **10/498 days breaching
$2,500 (98.0% pass)** — three 1R losses can all be in flight before any of
them closes, which the lens can never show because it already knows each
trade's outcome the instant it reads the row. Any prop-firm claim should name
which of these two it is quoting; this report names both.

## Days with 0/1/2/3 fires (core 11, 499 sessions, both readings identical)

| fires | days |
|---:|---:|
| 0 | 1 |
| 1 | 229 |
| 2 | 267 |
| 3 | 2 |

## Sample-size rule

Every cell above carries a verdict only where the floor is cleared: whole
769 trades / 25 months, H1 382 / 12, H2 387 / 13 — all above 30 trades and 12
months. No cell in this report is under that floor; none needed "not enough."

## What holds for the referee to re-derive

- OFF book (`research/tape/book_DAY_POLICY_off.json.gz`) reproduces the R3
  baseline bit-for-bit: `book_id 2c39ced2697c26cc`.
- ON book (`research/tape/book_DAY_POLICY_on.json.gz`) is the OFF book plus
  `day_policy.apply_to_book`, repaired, applied once — `book_id
  205d3dcee96c5282`.
- Both stamps: commit `5e8b5b89`, `dirty_py_count=0`, `dirty_engine_py=[]`.
- `signal_runner.DAY_POLICY` default flipped `first3 → 3fires_stop_win_or_2loss`
  in this same landing (commit named below), consistent with the row's step
  6 ("gate passes on both halves → flip default, verify, commit").
- Verify gate green: `regression_gate.py`, `test_runner_stop.py`,
  `test_universe_single_source.py`, all exit 0.
