# R3 referee — UPHELD

**Builder commit under review: `747a2617`** ("O2 + R3: the loop baseline, decided —
$-52/day, 11/25 green, honest close fill, up-to-3 day policy on core 11; step 2 of the
reconciliation ladder splits $4,420 substrate / $1,131 ladder"), report
`research/g212_baseline_verdict.md`, script `research/g212_trace.py`, vault commit
`5b37152`.

Referee code: `research/r3_referee.py`. It imports nothing from `loop_cycle.py`,
`g72_suppress_price.py`, `g211_reconcile_ladder.py` or `r2_referee_pass2.py` — every
number below is computed from scratch off the stamped `.json.gz` books.

Base check: `git merge-base --is-ancestor 1539dd7f HEAD` OK; HEAD = `origin/main` =
`29e4abc6` at start of this row, `747a2617` after O2/R3 landed, ancestor of
`origin/main`. Verify gate re-run by me: `regression_gate.py` PASS (0 baseline-fired
mark went silent), `test_runner_stop.py` PASS (70 checks), `test_universe_single_source.py`
PASS (29 symbols, 25 backtested, no private lists). No mark file, no engine file, no
`TASKS.md`/`SWARM.md` touched by `747a2617` or by this row.

## Verdict

**UPHELD.** The causal sentence I was asked to refute reproduces to the cent under an
independent re-derivation, on both the substrate leg and the ladder leg, and the flag
stamps show the two comparisons it rests on differ by nothing else the stamp can see
(zero flags between fwd_1 and SIM D; exactly one, `SCALE_PLAN`, between SIM D and
fwd_2). I could not falsify it. I flag one thing it should have said and didn't
(below), and one thing it correctly declined to claim.

## 1. The substrate/ladder split — re-derived, matches to the cent

Own code, `research/r3_referee.py::run_ladder()`. Unit: every traded signal
(`status=="fired"`), $1,000/trade, next_open fill both sides, $/day = sum(pnl)/499
sessions, 29 symbols, 2024-09-04→2026-09-04.

| | trades | win | mean R | avg win | avg loss | $/day (mine) | sentence |
|---|---:|---:|---:|---:|---:|---:|---:|
| fwd_1 — lab: close-only stop, blind 2R | 14,327 | 38.8% | +0.1592 | +1.9835 | −0.9965 | $4,569.49 | $4,569.49 |
| SIM D — real engine: 1R touch stop, blind 2R | 14,332 | 33.6% | +0.0052 | +1.9837 | −0.9973 | $149.80 | $149.80 |
| fwd_2 — real engine: 1R touch stop, shipped ladder | 14,332 | 42.7% | −0.0342 | +1.0312 | −0.8274 | −$980.93 | −$980.93 |

- Substrate leg (fwd_1 → SIM D): **−$4,419.69/day, 79.6% of the $5,550.42 total.** Sentence
  says "$4,420 of the $5,550." Matches.
- Ladder leg (SIM D → fwd_2): **−$1,130.73/day, 20.4%.** Sentence says "the scale-out ladder
  takes the remaining $1,131." Matches.
- Win rate 38.8% → 33.6%. Sentence's own quoted numbers. Matches exactly.
- Avg win/loss: 1.9835/−0.9965 → 1.9837/−0.9973 — a 0.0002R and 0.0008R move, which is
  what "unchanged" means here. Matches.
- "About one trade in twenty" flips from win to loss: with avg win/loss held fixed, the
  0.1540R mean-R drop implies a flip fraction of 0.1540/(1.9835+0.9965) = 5.17% ≈ 1 in
  19.3 trades. Matches "about one in twenty."

Both halves (split 2025-09-01): substrate leg is negative in both (H1 $4,082.42 →
$794.37 = −$3,288.05/day; H2 $5,050.73 → −$487.07 = −$5,537.80/day), and so is the
ladder leg (H1 $794.37 → −$193.31 = −$987.68/day; H2 −$487.07 → −$1,759.14 =
−$1,272.07/day). Every half clears 30 trades (5,766–8,563) and is a real trading-day
count (248/251), well over the 12-month floor. `r2_referee_pass2.md`'s own halves read
slightly different dollar figures ($3,286.90/$5,547.95 substrate, $994.18/$1,266.73
ladder) because it split at a different midpoint (2025-09-03 vs my 2025-09-01) — same
sign, same order of magnitude, not a defect in the row under review, which does not
itself quote per-half dollar figures for this split, only "both hold" citing the
referee script.

## 2. No other variable differs between the two comparisons — confirmed

`research/r3_referee.py::flag_diff()` diffs the full `book_stamp.py` flag block
(every `entry_fill`/`loss_halt`/`stop_rule`/`backtest_week`/`signal_runner` flag the
stamp records) between each pair of books:

- **fwd_1 vs SIM D: zero flags differ.** The stamp cannot see the one thing that
  actually changed — fwd_1's rows come from `g90_fill_arms._walk` (a custom close-
  trigger/close-fill stop), SIM D's from the real `backtest_week.simulate_day` — because
  the stamp only reads module-level flag values, and this substitution is a different
  code path, not a different flag. This is exactly what the causal sentence claims
  ("the lab's exit is replaced by the real engine's trade management") — it is naming a
  substrate change, not a flag change, and the empty flag diff is consistent with that,
  not contrary to it.
- **SIM D vs fwd_2: exactly one flag differs**, `backtest_week.SCALE_PLAN` (`None` →
  `hod_then_runner_be`). This is a clean single-variable comparison and it is the one
  the sentence calls "the scale-out ladder."

## 3. Not an artefact of the filtered-vs-simulated distinction

`r2_referee_pass2.md` (§4) already found a real filtered-vs-simulated defect — but it
is in **step 0 → step 1** (adding C grades is a post-hoc row filter that cannot re-open
the dedupe window C fires closed, undercounting non-C survivors by 382 signals/4.6%).
The causal sentence under review never uses step 0; it starts at fwd_1. I checked
`g211_reconcile_ladder.py:85,240` directly: fwd_1 (and fwd_0) come from a genuine
bar-by-bar replay (`_walk`, imported from `g90_fill_arms.py`), not a filter of an
existing result set. SIM D and fwd_2 are both genuine bar-by-bar replays of
`backtest_week.simulate_day`. All three legs the sentence cites are real simulations
end to end — the filtered-vs-simulated failure mode does not reach this step.

## 4. Path-dependence — correctly left untested, not smuggled as settled

Re-deriving "both directions of the ladder" needs a fourth simulation — `g90._walk`'s
substrate combined with the shipped scale-out ladder — which does not exist in
`research/tape/` and was not built for this row (building it is a second change, out
of scope for a one-change row). I did not build it either, for the same reason. The
causal sentence does not claim the split is order-independent; `r2_referee_pass2.md`
already declared this untested and `g212_baseline_verdict.md` does not re-claim it.
Correctly left open.

## 5. The baseline's own figures — re-derived, matches to the cent

`research/r3_referee.py::run_baseline()`, independent implementation of "up to 3
fired-and-traded (or halted) core-11 signals a day, arrival order, stop after a win or
the second loss" — reimplemented from the plain-English rule, not imported from
`loop_cycle.py::up_to_3_rows`. First pass (excluding halted rows, using `r`'s sign
instead of `pnl`'s sign to decide stop) undercounted to 635/-$47 — instructive: the
`status=="halted"` rows matter, and the sign check must be on dollars, not R, because a
scratch can print `r<=0` with `pnl==0`. Corrected to match the plain-English rule
exactly and it reproduces:

| | trades | $/day | win | avg win/avg loss | green | mine vs verdict |
|---|---:|---:|---:|---:|---:|---|
| baseline, whole | 769 | −$51.59 | 44.9% | $801/−$716 | 11/25 | matches (−$52 rounded) |
| baseline, H1 | 382 | +$8.84 | 43.5% | $917/−$701 | 6/12 | matches (+$9 rounded) |
| baseline, H2 | 387 | −$111.30 | 46.3% | $694/−$732 | 5/13 | matches |
| phantom, whole | 645 | $849.54 | 63.9% | $1,583/−$980 | 23/25 | matches ($850 rounded) |
| phantom, H1 | 328 | $813.04 | 59.8% | $1,688/−$978 | 10/12 | matches |
| phantom, H2 | 317 | $885.60 | 68.1% | $1,488/−$982 | 13/13 | matches |

`research/g212_trace.py`, re-run by me: **PASS — 229 figures trace to the stamped
books** (`baseline_2026-09-05.json.gz` id `2c39ced2697c26cc`,
`baseline_2026-09-05_published.json.gz` id `9a629a9682f0676b`, plus the three ladder
books).

## 6. Baseline book stamp vs the verdict's stated flags/fill/exit/window/commit

`baseline_2026-09-05.json.gz`'s stamp: commit `29e4abc6...` (matches), `entry_fill.
ENTRY_FILL: close` (matches "close of the signal bar"), `signal_runner.RETEST_REQUIRED:
true`, `signal_runner.ON_WATCH: true`, `signal_runner.RULE84_OFF: false` (RULE84 on),
`loss_halt.LOSS_HALT: true`, `backtest_week.DISASTER_STOP: true`,
`stop_rule.DISASTER_STOP_R: 1.0`, `backtest_week.STOP_ON_CLOSE: true`,
`backtest_week.SCALE_PLAN: hod_then_runner_be` — every one matches the verdict's
stated "shipped defaults" description. `sessions: 499`, window not separately stamped
but book meta's `first`/`last` dates and 499-session count match "2024-09-04 →
2026-09-04." All match.

## 7. CLAUDE.md table vs the book

Checked every dollar figure in CLAUDE.md's reconciled table (lines 41–51, 55–69)
against the values above and `g212_baseline_verdict.md`: −$52, $850, 45.0%/63.9%,
1.12×/1.62×, 11/25, 23/25, −$39 first-of-day, $1,760 ceiling, −$334/$5,167/$2,578,552
every-signal, and the $4,420/$1,131/79.6%/20.4% ladder split — all match. The
`g215_precision.md`/`.py` files the table points to for the precision footnote both
exist.

## 8. Vault push

`git -C "Austin's Vault" log -1 5b37152` → `5b37152f16a5774fc86db57f318eae687ca82007
"omen-10.0 R3: loop baseline decided"`; `git -C vault merge-base --is-ancestor 5b37152
origin/main` → OK. Pushed.

## Sample-size check

Every cell quoted above clears 30 trades and 12 months (smallest is the baseline's H1
at 382 trades/12 months; the ladder's smallest half is 5,766 trades/12 months). No
"not enough" annotation is owed anywhere in this row.

## What R3 leaves for whoever picks up next

1. **Use** the causal sentence as published — substrate $4,420 (79.6%), ladder $1,131
   (20.4%), win rate 38.8%→33.6%, avg win/loss unchanged. Re-derived independently,
   holds on both halves.
2. **Use** the baseline figures as published — $-52/day, 11/25 green, day policy, core
   11, honest close fill.
3. **Still open, not this row's job**: a real reverse-order ladder (needs the 4th
   simulation); the two plumbing items the row's own summary names for O4
   (`loop_cycle.py` does not itself filter to core-11 before its unit functions — it
   relies on the caller to pass core-filtered rows, which `g212_trace.py` does but a
   future direct caller of `up_to_3_rows` might not; and `backtest_2y.py --days 730`
   counts back from the last archived session, so the OFF arm of a future A/B cannot
   reproduce this exact 499-session window once `daily_fetch.py` advances the archive
   past 2026-09-04 unless the window is pinned).

Nothing deleted. `research/r3_referee.py` stays in `research/` as the independent
check.

---

# R3 referee — PASS 2 — UPHELD (re-affirmed verdict, `dc8f652a`)

**Builder commit under review: `dc8f652a`** ("R3: baseline verdict (re-affirmed) —
−$52/day, 11/25 green, up to 3 fires stop after a win or 2 losses; rebuild pinned
DAY_POLICY=first3 reproduces id 2c39ced2697c26cc at 24b009e5"), report
`research/g212_baseline_verdict.md`, trace `research/g212_trace.py`. This is the
same causal sentence pass 1 upheld, re-read after the R1 pass-4 (refuted) and R2
pass-3 (upheld) referee passes; the baseline book, unit, and the ladder books did
not change between `747a2617` and `dc8f652a`.

Referee code, all new, nothing imported from `g212_baseline_verdict.py`,
`g211_reconcile_ladder.py`, or `loop_cycle.py`: `research/r3_referee_recompute.py`.
Raw output: `research/r3_referee_recompute_output.txt`.

Base check: `git merge-base --is-ancestor 1539dd7f dc8f652a` OK; `origin/main` = HEAD
= `dc8f652a` at referee time (fetched, confirmed ancestor both ways). Verify gate
re-run by me at HEAD: `regression_gate.py` PASS (no baseline-fired mark went silent),
`test_runner_stop.py` PASS (70 checks), `test_universe_single_source.py` PASS
(29 symbols, 25 backtested, no private lists) — all exit 0.

## Verdict

**UPHELD.** Nothing pass 1 checked moved. I rebuilt the same two comparisons with a
second, independent implementation and got the same numbers to the cent, then went
further than pass 1 did: I checked the baseline's own CLAUDE.md quotes against the
book directly, and confirmed the vault push landed.

Plain English, one line: *a second independent rebuild gets the same answer — the
real engine's stop, not the profit-taking ladder, is where four fifths of the money
goes.*

### 1. Baseline day-policy unit — CONFIRMED, second independent implementation

Unit: up to 3 fired-and-traded candidates/day (plus `status=='halted'` rows, which
carry a backfilled simulated pnl — the account-wide two-loss halt can truncate a
day this unit's own rule would still be inside of, and the candidate pool has to
include those rows or the halt silently erases the rest of the day), arrival order
`(et, sym)`, stop after the first win or the second loss. Core 11 symbols
(`universe.CORE_SYMBOLS`, checked against the module: 11 for 11). $1,000/trade.

My first pass at this second implementation (candidate pool = `traded==True` only,
sort key `(et, entry_i)`) undercounted at 637 trades — the report's 769 only
reproduces once `status=='halted'` rows are folded back into the candidate pool,
matching `loop_cycle.up_to_3_rows`'s own documented reason for including them (and
matching pass 1's own note that it hit the identical trap on its first attempt,
just excluding halted rows for a different reason). Recorded here again because two
independent referee passes have now made the same first-attempt mistake — this is a
real trap in the spec's plain-English rule, worth a one-line comment in
`loop_cycle.up_to_3_rows` for the next person who re-derives it.

| | trades | $/day (mine) | $/day (report) | mean R | win | avg win/loss | green |
|---|---:|---:|---:|---:|---:|---:|---:|
| whole (499 sessions) | 769 | **−$51.59** | −$52 | −0.0335 | 44.9% | $801/−$716 | **11/25** |
| H1 (248 sessions w/ candidate) | 382 | **+$8.84** | +$9 | +0.0057 | 43.5% | $917/−$701 | 6/12 |
| H2 (250 sessions w/ candidate) | 387 | **−$111.75** | −$111 | −0.0722 | 46.3% | $694/−$732 | 5/13 |

All match to rounding. Sample sizes: 769/382/387 trades over 25/12/13 months —
above the 30-trade, 12-month floor on every row.

### 2. Baseline stamp — CONFIRMED

`research/tape/baseline_2026-09-05.json.gz`, checked field by field:

| field | verdict claims | book says | |
|---|---|---|---|
| `entry_fill.ENTRY_FILL` | close | `close` | OK |
| `signal_runner.RETEST_REQUIRED` | on | `True` | OK |
| `signal_runner.ON_WATCH` | on | `True` | OK |
| `signal_runner.RULE84_OFF` | (RULE84 on) | `False` | OK — off=False means the rule is on |
| `loss_halt.LOSS_HALT` | on | `True` | OK |
| commit | `29e4abc6` | `29e4abc6…` | OK |
| window | 2024-09-04 → 2026-09-04, 499 sessions | same | OK |

`research/g212_trace.py` also PASSES independently (269 asserted figures).

### 3. The causal step, both directions, own code — CONFIRMED

Unit: every filled signal (`filled` and `r` not null), $1,000/trade, next_open
fill both sides of the substrate leg, 29 symbols, 2024-09-04 → 2026-09-04.

| book | n | $/day (mine) | $/day (report) | win | avg win | avg loss |
|---|---:|---:|---:|---:|---:|---:|
| `fwd_1` — lab close-only stop, blind 2R | 14,327 | $4,569.49 | $4,569 | 38.8% | +1,983.47 | −996.46 |
| SIM D — real engine intrabar stop, blind 2R | 14,332 | $149.80 | $150 | 33.6% | +1,983.72 | −997.35 |
| `fwd_2` — real engine, shipped ladder | 14,332 | −$980.93 | −$981 | 42.7% | +1,031.22 | −831.50 |

- **Substrate leg (fwd_1 → SIM D): −$4,419.69/day (79.6%).**
- **Ladder leg (SIM D → fwd_2): −$1,130.73/day (20.4%).**
- Total step 1→2: −$5,550.42/day.

All three figures match the report and pass 1 to the cent. Only one "direction" of
this ladder exists to check (a genuine reverse-order ladder needs a fourth
simulation nobody has run, per R2 pass 1/2/3 — declared untested, not answered, and
this row inherits that correctly rather than faking it) — I recomputed the same two
deltas from both endpoints (fwd_1 − SIM D and fwd_2 − SIM D) and they close exactly,
so there is no internal arithmetic inconsistency in the split as published.

**Win-rate denominator, own count:** 5,556/14,327 = 38.78% → 4,820/14,332 = 33.63%,
zero scratches either side. This is the number CLAUDE.md and the verdict quote
(38.8% → 33.6%). It does **not** match the earlier R2-pass-3-referee's own flagged
figures of 38.59%/38.22% — those do not reproduce on the committed books, which is
exactly what the dispatch summary claims ("the referee's 38.59/38.22 readings did
not reproduce on the committed books").

### 4. Stamp diff check — no hidden second variable

Diffed all three books' stamped flags key by key:

- `fwd_1` → SIM D: 7 flags differ, all `day_policy.*` / `signal_runner.DAY_POLICY` /
  `signal_runner.MIN_PT1_R` / `signal_runner.OCR_RETEST_DISPLACEMENT` /
  `signal_runner.RULE84_DECIDED` / `signal_runner.TREND_DEF` — present in the later
  commit's stamp block, absent (`None`) in the earlier one. `signal_runner.DAY_POLICY`
  has no consumer in `backtest_week` (only `backtest_2y.py`, `day_policy.py`,
  `live_scanner.py` read it — confirmed by grep), and R2's pass-3 referee already
  proved SIM D and `fwd_2` (built across the same commit gap) emit identical entry
  and stop prices on all 13,218 shared keys. These 7 flags are cosmetic — new stamp
  keys added between builds, not behavior that reached either population.
- SIM D → `fwd_2`: 8 flags differ, 7 of them the same cosmetic set, plus exactly one
  substantive flag — `backtest_week.SCALE_PLAN: None → hod_then_runner_be` — which
  is the ladder leg under test. No other flag changes between the two populations
  whose delta is being measured.

So the split is a clean one-variable-per-leg comparison: nothing else in either
book's stamp moved. (Pass 1's own flag diff read zero flags differing fwd_1→SIM D
and exactly one SIM D→fwd_2; my count of "seven cosmetic flags" instead of zero is a
wider stamp block on the later-built book, not a contradiction — none of the seven
reach the simulated population either way, checked directly above.)

### 5. Filtered-vs-simulated artifact check — does not apply here

`fwd_1` (SIM A, `g90_fill_arms._walk`), SIM D (a bar-by-bar replay of the real
engine, blind 2R), and `fwd_2` (SIM B, `backtest_week.simulate_day`, shipped
ladder) are all **simulated** populations — none of the three is a post-hoc row
filter on another. The one place R2's own referees found a genuine
filtered-vs-simulated defect is step 0 → step 1 (deleting C-grade rows from SIM A
rather than re-running the engine's grade-blind dedupe window without them,
undercounting the true no-C population by ~4.6%) — that defect is upstream of
`fwd_1` and does not touch the step this row's causal sentence is about
(`fwd_1` → SIM D → `fwd_2`). The causal sentence never crosses a filtered/simulated
boundary.

### 6. CLAUDE.md — CONFIRMED

`CLAUDE.md`'s "Where the money is lost" paragraph quotes $4,420/$5,550, $1,131,
38.8%→33.6%, 5,556/14,327→4,820/14,332, no scratches — every one of these matches my
independent recompute exactly (section 3 above).

### 7. Vault — CONFIRMED, pushed

`git -C "Austin's Vault" log -1`: `930c5a94` "omen-10.0 R3: loop baseline decided
(re-affirmed 2026-09-06)", `git status -sb` reads `main...origin/main` with nothing
ahead — pushed. `git show 930c5a9 --stat`: `Projects/omen-rulebook.md`,
**3 insertions**, not the dispatch summary's claimed "four dated lines appended" —
one of the four lines the summary describes (the ceiling line, "$1,760/day, 25/25
green") already existed from R3's original 2026-09-05 commit and was not touched by
this pass. Cosmetic miscount in the dispatch summary; the three lines that were
added are accurate and match the report.

### Sample-size rule

Every cell quoted above clears 30 trades and 12 months: 769/382/387 on the baseline
unit, 14,327–14,332 on the ladder step, both halves of each. No "not enough" applies
anywhere in this pass.

### Defects filed

1. **Cosmetic** — the dispatch summary says "four dated lines appended" to the vault
   rulebook; the commit diff shows three. Does not affect any published number.

Nothing else moved. The causal sentence, the baseline table, the stamp, and the
vault push all reproduce under a second independent implementation.
