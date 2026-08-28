# H1 — the 2-year book with ON WATCH off, and the runners named

**The headline finding is not the number, it is that the two books being compared have never been on the same clock.** The shipped ladder's R comes from `backtest_week.py`, which runs an open position to the **16:00 EOD close** (`backtest_week.py:692`) — `ENTRY_CUTOFF = 11:00` is an entry cutoff, not an exit clock. `flat_2r` comes from `exit_lab`, which force-flats at **11:00** (`CLOCK_BAR = 90`). **22 of 1091 ladder trades (2.0%) book more R than the 11:00 window ever offered**, which is only possible because they were still open after 11:00. Every "the simple 2R book earns less than the ladder" comparison in this project, `research/r9_simple_book.md` included, is a five-hour handicap read as an exit result.

**Put both exits on the same clock and a quarter of the gap turns out to be the clock.** Same entries, same stops, same `exit_lab` rig, ON WATCH off: at 11:00 the ladder is +0.7746 R and `flat_2r` is +0.5893 R, a gap of **0.1853 R** — against the 0.2523 R gap the cross-rig comparison reports. Let both run to EOD instead and the ladder is +0.7452 R against `flat_2r`'s +0.5932 R. **Neither book, on either clock, reaches the 2.0 R money gate.**

**With ON WATCH removed the book is 1091 trades at **+0.8416 R** on the shipped ladder and **+0.5893 R** on flat 2R. Both FAIL the 2.0 R money gate — by 1.1584 R and 1.4107 R. Durability FAILS too: 24 of 25 months green on the ladder, 24 of 25 on flat 2R, against a gate of every month. Removing ON WATCH costs -0.1136 R against the shipped arm and buys back 74 trades and a green month.**

**And the ceiling says the exit is not what is missing.** The tape offered **+3.8436 R** of mean maximum favourable excursion before the stop closed, inside the 11:00 clock. The shipped ladder captures **21.9%** of it. **53.8%** of trades touched 2R at some point; **25.9%** of them finish there or better.

Script: `research/h1_2y_nowatch.py`. Books: `research/g3_arm_ow0.json` (ON_WATCH=0) and `research/g3_arm_ow1.json` (ON_WATCH=1), both replayed by `research/g3_onwatch_2y.py` at `47e60796`. Window 2024-08-21 → 2026-08-21, 500 sessions, 28 symbols, `data_archive/` replay, zero fetches.

---

## 1. The whole book, ON WATCH off

Win rate is of DECIDED trades (R = 0 excluded) — the convention `research/a2_bt2y_summary.py::book` prints. The gate is `CLAUDE.md`'s: mean R = 2.0, every month green, win rate a secondary read.

| book | n | mean R | median R | win rate | total R | months green | worst month | vs 2.0 R gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **ladder `30_30_30_10`, ON WATCH off** | 1091 | **+0.8416** | +0.4120 | 54.3% | +918.1 | **24 / 25** | 2025-06 -2.9 | **FAIL** — 1.1584 R short |
| **`flat_2r`, ON WATCH off** | 1091 | **+0.5893** | +2.0000 | 56.4% | +642.9 | **24 / 25** | 2024-09 -1.5 | **FAIL** — 1.4107 R short |
| ladder, ON WATCH on (shipped) | 1017 | +0.9551 | +0.5660 | 53.4% | +971.4 | 23 / 25 | — | FAIL |
| `flat_2r`, ON WATCH on (shipped) | 1017 | +0.6997 | +2.0000 | 59.9% | +711.6 | — | — | FAIL |
| **gate** | — | **≥ +2.0000** | — | — | — | **25 / 25** | > 0 | — |

**Removing ON WATCH does not close the gap and it was never going to.** The flag moves 0 of 45193 signals (`research/g3_onwatch_2y.md`, `47e60796`) — it is a price rule at 2 of `signal_runner.fill_price`'s 10 call sites, not a detector. Its whole reach is the break-and-retest bars that close jammed against the session extreme.

**The error bar still swallows the delta.** One-directional, from the intrabar-fill ambiguity (`research/p26_intrabar_ambiguity.py`, `8bb78c77`): repricing an ambiguous row can only make R worse, so every mean below is a CEILING.

| book, ON WATCH off | mean R | wide deduction | narrow deduction |
|---|---:|---:|---:|
| ladder | +0.8416 | −1.3388 | −0.0088 |
| `flat_2r` | +0.5893 | −1.2028 | −0.0055 |

The ON WATCH delta itself is **+0.1136 R**, which is **11.8×** smaller than the wide bar of ±1.3388 R on this arm. It is not resolvable on this rig in either direction.

## 1b. Ladder vs simple 2R, on ONE rig and ONE clock

Austin, 2026-08-27: *"it is concerning the simpler 2r condensed omen doesent have edge or is worse."* Part of that is a measurement artefact, and this table is the correction. Every row below is `exit_lab` on the identical entries, stops and sides of the ON-WATCH-off arm — only the exit and the clock vary. The 30/30/30/10 ladder is `exit_lab.scale_out`, the same policy `research/g7_exit_sweep.py` sweeps.

| exit | clock | n | mean R | median R | win rate | total R | months green | vs 2.0 R gate |
|---|---|---:|---:|---:|---:|---:|---:|---|
| ladder `30_30_30_10` | 11:00 force-flat | 1091 | **+0.7746** | -0.0246 | 49.8% | +845.1 | 24 / 25 | FAIL |
| **`flat_2r`** | 11:00 force-flat | 1091 | **+0.5893** | +2.0000 | 56.4% | +642.9 | 24 / 25 | FAIL |
| ladder `30_30_30_10` | runs to EOD | 1091 | **+0.7452** | -0.4050 | 47.7% | +813.0 | 23 / 25 | FAIL |
| **`flat_2r`** | runs to EOD | 1091 | **+0.5932** | +2.0000 | 55.9% | +647.2 | 22 / 25 | FAIL |
| shipped ladder (`backtest_week`) | **entry ≤ 11:00, exit to EOD** | 1091 | +0.8416 | +0.4120 | 54.3% | +918.1 | 24 / 25 | FAIL |
| **gate** | — | — | **≥ +2.0000** | — | — | — | **25 / 25** | — |

**The cross-rig gap is 0.2523 R; the same-rig, same-clock gap is 0.1853 R.** So most of what looked like "the simple book is worse" was the ladder being allowed to hold past 11:00 while `flat_2r` was force-flat. It is a real difference in exit design, but it is a difference in SESSION LENGTH, and Austin's stated rule is that he does not trade past 11:00 (`signal_runner.py:554`).

**The other half of the answer: holding past 11:00 buys nothing, and that is the first time this repo has priced it on the same rig.** Same ladder, two clocks: +0.7746 R at 11:00 vs +0.7452 R to EOD — a delta of **-0.0295 R**, and it costs a green month (24/25 → 23/25). `flat_2r` moves +0.0039 R. The 11:00 force-flat is therefore NOT what is holding the runners back, which kills the obvious first guess and reproduces `research/g7_exit_sweep.md`'s clock finding on a second rig. The two rigs still need to agree on one clock — `backtest_week.py` runs to EOD and `exit_lab` stops at 11:00 — but the choice is worth ~0.03 R, not the gap to the gate.

| what the extra session buys | ladder | `flat_2r` |
|---|---:|---:|
| mean R at 11:00 | +0.7746 | +0.5893 |
| mean R to EOD | +0.7452 | +0.5932 |
| **delta** | **-0.0295** | **+0.0039** |
| mean MFE at 11:00 | +3.8436 | — |
| mean MFE to EOD | +4.8665 | — |

**Neither exit gains from the afternoon, and yet the afternoon is where the movement is.** Mean MFE rises +3.8436 R → +4.8665 R when the clock comes off — the tape offers **26.6% more room** after 11:00 — and both exits book LESS of it (-0.0295 R and +0.0039 R). **That is the honest version of "let runners run": the runners are not being cut short by the 11:00 clock. They are being cut short by the trail, which gives back more than the extra session offers.** The ladder captures 20.2% of the tape at 11:00 and 15.3% of it by EOD.

## 2. Durability, spelled out

### Every month

The durability gate is EVERY month green. Both books are shown so a red month can be blamed on the exit or cleared of it.

| month | n | ladder total R | ladder mean R | `flat_2r` total R | `flat_2r` mean R |
|---|---:|---:|---:|---:|---:|
| 2024-08 | 19 | +12.8 | +0.674 | +15.8 | +0.832 |
| 2024-09 | 30 | +4.4 | +0.148 | **-1.5** | -0.049 |
| 2024-10 | 23 | +27.7 | +1.204 | +19.4 | +0.841 |
| 2024-11 | 34 | +26.6 | +0.783 | +25.5 | +0.749 |
| 2024-12 | 29 | +7.1 | +0.243 | +11.3 | +0.391 |
| 2025-01 | 53 | +30.2 | +0.570 | +16.6 | +0.313 |
| 2025-02 | 37 | +10.6 | +0.287 | +13.9 | +0.375 |
| 2025-03 | 41 | +35.3 | +0.860 | +38.5 | +0.939 |
| 2025-04 | 72 | +86.9 | +1.207 | +64.9 | +0.902 |
| 2025-05 | 28 | +20.5 | +0.731 | +12.7 | +0.453 |
| 2025-06 | 25 | **-2.9** | -0.116 | +0.5 | +0.020 |
| 2025-07 | 27 | +35.0 | +1.297 | +37.2 | +1.379 |
| 2025-08 | 34 | +43.1 | +1.268 | +24.7 | +0.726 |
| 2025-09 | 30 | +0.1 | +0.003 | +0.0 | +0.000 |
| 2025-10 | 48 | +9.4 | +0.195 | +19.5 | +0.407 |
| 2025-11 | 54 | +57.2 | +1.060 | +38.2 | +0.708 |
| 2025-12 | 42 | +41.0 | +0.977 | +24.1 | +0.575 |
| 2026-01 | 50 | +40.4 | +0.808 | +23.9 | +0.478 |
| 2026-02 | 62 | +53.6 | +0.865 | +29.1 | +0.469 |
| 2026-03 | 66 | +46.0 | +0.697 | +19.1 | +0.290 |
| 2026-04 | 51 | +44.9 | +0.881 | +49.0 | +0.960 |
| 2026-05 | 61 | +70.3 | +1.152 | +27.3 | +0.448 |
| 2026-06 | 79 | +56.4 | +0.714 | +52.0 | +0.658 |
| 2026-07 | 69 | +98.3 | +1.425 | +54.8 | +0.795 |
| 2026-08 | 27 | +63.3 | +2.343 | +26.3 | +0.974 |

Bold is a red month. **Ladder 24 / 25, `flat_2r` 24 / 25.** The gate is 25 / 25.

### Per pool

| pool | n | ladder mean R | `flat_2r` mean R | win rate (ladder) | months green | P(touch 2R) |
|---|---:|---:|---:|---:|---:|---:|
| `equity` | 658 | +0.8271 | +0.6172 | 55.0% | 24 / 25 | 54.3% |
| `other` | 410 | +0.8805 | +0.5314 | 52.0% | 21 / 25 | 53.2% |
| `index` | 23 | +0.5588 | +0.8208 | 73.9% | 8 / 11 | 52.2% |

Rows under `universe.MIN_SAMPLE_N` (=20) are marked thin — marked, not dropped, and still inside every whole-book total above.

### Per Austin grade

| Austin grade | n | ladder mean R | `flat_2r` mean R | win rate (ladder) | months green | P(touch 2R) |
|---|---:|---:|---:|---:|---:|---:|
| `C` | 681 | +0.7864 | +0.5617 | 50.8% | 23 / 25 | 52.7% |
| `A` | 266 | +0.8533 | +0.5742 | 55.6% | 21 / 25 | 53.8% |
| `S` | 144 | +1.0806 | +0.7475 | 68.1% | 23 / 25 | 59.0% |

Rows under `universe.MIN_SAMPLE_N` (=20) are marked thin — marked, not dropped, and still inside every whole-book total above.

### Per setup

| setup | n | ladder mean R | `flat_2r` mean R | win rate (ladder) | months green | P(touch 2R) |
|---|---:|---:|---:|---:|---:|---:|
| `break_and_retest` | 1022 | +0.8624 | +0.6019 | 54.5% | 23 / 25 | 54.5% |
| `one_candle_rule` | 66 | +0.4632 | +0.3543 | 50.0% | 14 / 23 | 42.4% |
| `reentry_84_rule` _(thin)_ | 3 | +2.0690 | +1.4615 | 66.7% | 1 / 2 | 66.7% |

Rows under `universe.MIN_SAMPLE_N` (=20) are marked thin — marked, not dropped, and still inside every whole-book total above.

### Per symbol

| symbol | n | ladder mean R | `flat_2r` mean R | months green | P(touch 2R) | mean MFE R |
|---|---:|---:|---:|---:|---:|---:|
| SPCX _(thin)_ | 14 | +2.1489 | +0.7387 | 3 / 3 | 57.1% | +6.939 |
| HOOD | 80 | +1.6840 | +0.6888 | 18 / 22 | 58.8% | +5.305 |
| INTC | 29 | +1.3295 | +1.2532 | 9 / 13 | 75.9% | +4.769 |
| UBER | 29 | +1.2933 | +0.5262 | 9 / 12 | 51.7% | +4.368 |
| ACHR _(thin)_ | 2 | +1.2790 | +2.0000 | 2 / 2 | 100.0% | +3.575 |
| MU | 82 | +1.1957 | +0.7085 | 18 / 24 | 56.1% | +4.975 |
| CRM | 23 | +1.1111 | +0.3279 | 10 / 12 | 47.8% | +4.378 |
| ORCL | 54 | +0.8954 | +0.7415 | 15 / 19 | 59.3% | +4.172 |
| META | 45 | +0.8559 | +0.3699 | 15 / 22 | 46.7% | +2.730 |
| NFLX | 34 | +0.8349 | +0.6083 | 13 / 19 | 55.9% | +3.868 |
| AMD | 74 | +0.7718 | +0.6437 | 16 / 25 | 54.1% | +4.205 |
| NVDA | 52 | +0.7661 | +0.4964 | 15 / 22 | 51.9% | +3.424 |
| PLTR | 83 | +0.7635 | +0.5580 | 14 / 21 | 54.2% | +3.915 |
| AVGO | 56 | +0.7471 | +0.6195 | 15 / 21 | 53.6% | +3.514 |
| AAPL _(thin)_ | 19 | +0.7083 | +0.8902 | 12 / 14 | 57.9% | +3.189 |
| TSM | 27 | +0.7013 | +0.4996 | 9 / 12 | 51.9% | +2.577 |
| IWM _(thin)_ | 7 | +0.6617 | +0.9672 | 5 / 6 | 57.1% | +2.914 |
| TSLA | 80 | +0.5929 | +0.7274 | 15 / 24 | 58.8% | +4.086 |
| COIN | 112 | +0.5866 | +0.6778 | 18 / 25 | 58.0% | +3.427 |
| QQQ _(thin)_ | 10 | +0.5672 | +1.0271 | 4 / 6 | 60.0% | +3.006 |
| IREN | 55 | +0.5318 | +0.3103 | 8 / 12 | 47.3% | +3.947 |
| MSFT | 30 | +0.5168 | +0.1606 | 10 / 15 | 36.7% | +2.415 |
| AMZN | 35 | +0.4530 | +0.2070 | 11 / 18 | 37.1% | +2.737 |
| SPY _(thin)_ | 6 | +0.4248 | +0.3060 | 2 / 3 | 33.3% | +2.315 |
| BABA | 21 | +0.3938 | +0.0308 | 7 / 13 | 38.1% | +2.112 |
| GOOGL | 25 | +0.2881 | +0.5222 | 9 / 15 | 52.0% | +2.249 |
| MARA _(thin)_ | 2 | +0.2610 | +0.3750 | 2 / 2 | 50.0% | +2.193 |
| SOFI _(thin)_ | 5 | -0.2536 | -0.5160 | 2 / 5 | 20.0% | +0.984 |

**No slice passes the 2.0 R gate.** Every row above that clears it is thin.

## 3. Which trades are runners

**The metric.** Maximum favourable excursion (MFE) in R before the close-triggered stop, inside the 11:00 ET clock. It is a property of entry, stop and tape — not of any exit — so it is the CEILING every exit policy in this repo is measured against. `mfe_r()` runs the identical causal loop `exit_lab.flat_target` runs; `--selfcheck` asserts `mfe_r >= 2.0` exactly when `r9.reaches_target` says the 2R target was reached, on every row of both arms.

| statistic | value |
|---|---:|
| mean MFE | **+3.8436 R** |
| median MFE | +2.2333 R |
| ladder captures | **21.9%** of mean MFE |
| `flat_2r` captures | 15.3% of mean MFE |

### The ladder of reach

| target | TOUCHED by 11:00 | TOUCHED by EOD | ladder BOOKS ≥ it | give-back vs 11:00 |
|---|---:|---:|---:|---:|
| 1R | 72.8% | 73.6% | 36.9% | **35.8 pts** |
| 2R | 53.8% | 55.7% | 27.0% | **26.8 pts** |
| 3R | 41.1% | 43.2% | 17.5% | **23.6 pts** |
| 4R | 32.5% | 36.2% | 10.8% | **21.7 pts** |
| 5R | 26.2% | 31.3% | 6.5% | **19.7 pts** |

**The give-back at 2R is the whole argument for a simpler book, and it is also why the simpler book loses.** `flat_2r` converts the 2R touch into a 2R booking, which is why its win rate is higher — and it truncates every trade that was going to reach 4R or 5R, which is why its mean R is lower. The 32.5% that touch 4R carry the ladder.

### Who the runners are

A **runner** is defined here as a trade whose MFE reached 4R — twice the money gate — before its stop closed. The question is whether anything known AT ENTRY separates them.

| population | n | share | ladder mean R | `flat_2r` mean R |
|---|---:|---:|---:|---:|
| runners (MFE ≥ 4R) | 355 | 32.5% | +3.0134 | +2.0000 |
| middle (1R ≤ MFE < 4R) | 439 | 40.2% | +0.2322 | +0.5980 |
| dead (MFE < 1R) | 297 | 27.2% | -0.8538 | -1.1098 |

**The separator table.** For each entry-time cut, the share of that slice that turns into a runner. A cut that selects runners shows a rate above the book's **32.5%** base rate by more than sampling noise.

| cut | value | n | runner rate | lift vs base | mean MFE R |
|---|---|---:|---:|---:|---:|
| Austin grade | `C` | 681 | 30.4% | -2.1 pts | +3.755 |
| Austin grade | `A` | 266 | 33.8% | +1.3 pts | +3.841 |
| Austin grade | `S` | 144 | 40.3% | +7.7 pts | +4.269 |
| setup | `break_and_retest` | 1022 | 33.1% | +0.5 pts | +3.928 |
| setup | `one_candle_rule` | 66 | 22.7% | -9.8 pts | +2.433 |
| setup | `reentry_84_rule` _(thin)_ | 3 | 66.7% | +34.1 pts | +5.993 |
| pool | `equity` | 658 | 33.1% | +0.6 pts | +3.885 |
| pool | `other` | 410 | 32.2% | -0.3 pts | +3.836 |
| pool | `index` | 23 | 21.7% | -10.8 pts | +2.798 |
| side | `S` | 554 | 32.1% | -0.4 pts | +3.908 |
| side | `L` | 537 | 33.0% | +0.4 pts | +3.777 |
| intrabar fill | `True` | 815 | 35.8% | +3.3 pts | +4.179 |
| intrabar fill | `False` | 276 | 22.8% | -9.7 pts | +2.854 |

**Read the lift column, not the rate column.** A cut is only a selector if its lift is large relative to how many trades it keeps. A cut that lifts a few points while keeping 60% of the book is describing the book, not selecting inside it.

## 4. P(2R), the path rate

`p2r` imported from `research/r9_simple_book.py` unmodified. The PATH rate is the 2R target trading before a close beyond the stop; the BOOKED rate is the ladder actually finishing at ≥ +2.0 R. Deductions are one-directional and these are ceilings.

| arm | policy | n | P(2R) | wide deduction | narrow deduction |
|---|---|---:|---:|---:|---:|
| ON WATCH off | `flat_2r` path | 1091 | **53.80%** | −38.96 pts | −0.18 pts |
| ON WATCH off | ladder booked | 1091 | **25.94%** | −20.35 pts | −0.18 pts |
| ON WATCH on (shipped) | `flat_2r` path | 1017 | **57.23%** | −45.82 pts | −0.20 pts |
| ON WATCH on (shipped) | ladder booked | 1017 | **29.30%** | −24.48 pts | −0.20 pts |

## 5. The stop, checked against the code

Austin, 2026-08-27: *"You said you like the -1.25R, but it should still be -1R for all the trades. That's just to prevent, you know, slippage."*

**That is already exactly what this engine does, and no change is needed.** Read off `research/exit_lab.py` at this commit:

| piece | code | what it means |
|---|---|---|
| the stop level | the structural stop, `r["stop"]` | 1R **is** `abs(entry − stop)` by definition — every trade risks exactly 1R |
| the trigger | `exit_lab._stop_hit_first`, `exit_lab.py:153` | fires on the candle CLOSE beyond the stop; wicks stop nothing |
| the fill | that bar's close | not the stop price — the close it actually happened at |
| the slippage cap | `MAX_LOSS_R = 1.25`, `exit_lab.py:55` | a close far beyond the stop books at most −1.25 R |

So −1.0 R is the stop and −1.25 R is the slippage ceiling, which is the design he described. On this book **0 of 1091 trades (0.0%) book worse than −1.00 R**, and **0 (0.0%) land exactly on the −1.25 R floor** — the floor is doing real work and it is not doing much of it.

## 6. Scratch, checked against the code

**Scratch is already gone from the backtest and was never in it in any measurable way.** `research/p8_scratch.py` (`7979a61e`) instrumented the rule over n=43,374 created trades: the entry bar's close sat on the good side of both the stop and the retested level **every single time** — zero crossings — because the backtest only takes the intrabar-fill entry after it has already seen that bar's completed close. The branch was deleted and the book came out byte-identical on all 45,175 rows. Nothing in this report contains a scratch. What remains unimplemented is the LIVE path (`research/g11_live_scratch_scope.md`, `00d64ad5`), which this file does not touch.

## 7. Gaps and provenance

| arm | rows that could not be replayed | reason |
|---|---:|---|
| A | 0 | 0 no archived session, 0 entry minute absent, 0 entry index past end |
| B | 0 | 0 no archived session, 0 entry minute absent, 0 entry index past end |

A row that cannot be replayed is REPORTED here, never silently dropped into a denominator — `build_arm`'s own contract, imported.

| number | script | commit |
|---|---|---|
| every figure in §1–§5 and §7 | `research/h1_2y_nowatch.py` | this commit |
| both fill-arm books | `research/g3_onwatch_2y.py` | `47e60796` |
| `build_arm`, `agg_r`, `months`, `mean_bar`, `p2r`, `reaches_target` | `research/r9_simple_book.py` | `e4de7858` |
| the intrabar classification behind the error bar | `research/p26_intrabar_ambiguity.py` | `8bb78c77` |
| the scratch finding | `research/p8_scratch.py` | `7979a61e` |
| held-out recall (unchanged by this arm) | `research/t70_test1_score.py` | `30fbc3f8` |

**Held-out recall is IDENTICAL in both arms and is not re-measured here.** ON WATCH moves 0 of 45193 signals, so it cannot change what the engine detects. The held-out number stands where `research/t70_test1_score.py` left it: **3 of 15 S days = 20%**, against **12 of 42 X days = 29%** false fires, on the 100 cards Austin graded 2026-08-27.

