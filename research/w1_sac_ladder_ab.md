# W1 -- kill `B`: Austin's S/A/C/X ladder as the engine's grade

**Held-out first, and the verdict arm is the `B`-floor removal ON ITS OWN** (`CLAUDE.md`: held-out beats in-sample, always). On the 100 OMEN Test 1 cards `nofloor` moves S recall **3/15 = 20% -> 0/15 = 0%** and false fires on days Austin refused **12/42 = 29% -> 8/42 = 19%**. It buys 4 fewer false fires by going silent on the S days too.

**AND THE LADDER ITSELF IS REFUTED.** On 2026-08-28 Austin graded **59** of these `B`-only signals himself (`research/marks/deck_marks_h2_3lane_2026-08-28.jsonl`). Scored against the spec's ladder his agreement is **26/59 = 44.1%** -- *worse* than always guessing `X`, which scores **52.5%** on the same rows. Section 2 is that measurement. Killing the `B` floor is still right, because arrival order should not select the book; "count the downgrades and map to S/A/C/X" is a hypothesis that has now been tested against his own verdicts and failed, and it is reported here as a control rather than as the answer.

**On the money: median R +0.5660 -> -0.4285, mean R +0.9551 -> +1.3161, months green 23/25 -> 12/18, and the book falls 1,017 -> 48 traded rows -- -969, 95.3% of it.** 7 of the 27 symbols that traded at all lose their ENTIRE book (section 5 names them).

**And the `B` floor is not only doing arrival order -- it is the mechanism that BYPASSES the tight-stop gate.** `backtest_week.Trade.counted` excludes `C`: a `C` is alert-only and never reaches traded P&L, and a `C` also has to clear `_min_viable_stop` where a `B` does not. So demoting the 968 floored signals back to `C` does not re-rank them, it removes them: 1,394 fired -> 703, of which 655 are alerts. The spec's ladder says `C` IS tradeable (section 1.2); this engine says `C` is alert-only. Those two cannot both be true and only Austin closes it.

**The ladder arms are still reported, and which variables they count is not the shipped eight.** `research/w9_downgrade_signs.md` (2026-08-28) re-signed all eight on this same book: `level_not_respected` is **wrong-signed** and fires on 62.7% of it (tripped +1.0046R vs clean +0.8711R), and `break_then_rejection` never trips on a traded row at all. Dropping the wrong-signed one and keeping the rest is the ONLY set of the three W9 simulated that is **not monotonic** -- C collapses onto the stop floor and ties with X. W9's set (c) -- the seven right-signed variables plus `sequence_gate` turned on -- is monotonic without carrying the bug, so that is what `on_w9c` counts, and the shipped eight are arm `on`. Neither set survives section 2.

Nothing here ships. `signal_runner.ENABLE_SAC_LADDER` defaults to **False**, `SAC_LADDER_VARSET` defaults to `"shipped"`, `downgrade.ENABLE_SEQUENCE_GATE`'s committed default is **not touched** (the `w9c` arm passes `enable_sequence_gate=True` per call, the opt-in `score()` already provides), the `B` floor is not deleted, `ON_WATCH` stays at its shipped default (spec section 1.5), and the engine is not re-frozen -- that would VOID `research/omen6_forward.py` and it is Austin's call. Measured at _this commit_ by `research/w1_sac_ladder_ab.py`.

| arm | what it is |
|---|---|
| `off` | == HEAD, the control. `_grade_for_levels` + the counter-day-trend cap + the first-with-trend `B` floor. |
| `nofloor` | **the verdict arm.** The first-with-trend `B` floor removed and NOTHING else -- a `C` that would have been floored to `B` stays a `C`. This is the half of W1 that Austin's 59 verdicts did not refute. |
| `on_w9c` | the count ladder, counting `research/w9_downgrade_signs.md` set (c): the seven right-signed shipped variables (i.e. minus `level_not_respected`) plus `sequence_gate` turned on. Regrades only what the incumbent chain left tradeable. |
| `on` | the same ladder counting all EIGHT variables as shipped, including the wrong-signed `level_not_respected`. A labelled control, kept because the comparison between the two sets is itself the finding. |
| `on_all` | the shipped-eight ladder ALSO regrading the 42,937 `_grade_pa` vetoes. That is R3's lever reached by a different road; it makes the book grow. |

## 1. What was implemented

> "B is not supposed to be a trade. We changed it to A and C. S and A and C."  
> "S A C grades are kept, A one downgrade, C two downgrades, revisit B trades and mold them into those grades or 'x' kill them."  
> -- Austin, 2026-08-28

`research/g4_dropped_s.md` is the finding this implements: **968 of the 1,016 traded signals (95.3%) are `B` ONLY because of `_calibration_grade`'s first-with-trend-signal-of-the-day floor.** The engine trades on grade, so arrival order -- not the setup -- selects the entire book.

| | |
|---|---|
| flag | `signal_runner.ENABLE_SAC_LADDER`, **default False** |
| variable set | `signal_runner.SAC_LADDER_VARSET`, **default `"shipped"`**; `"w9c"` is W9's set (c) |
| reach | `signal_runner.SAC_LADDER_REGRADE_ALL`, **default False** -- see section 6 |
| seam | `SignalRunner._calibration_grade` -> `SignalRunner._sac_ladder_grade`, the LAST write to `sig["grade"]` before `_route` decides |
| OFF | `_grade_for_levels` + the counter-day-trend cap + the first-with-trend `B` floor -- the shipped chain, unchanged |
| ON | the floor does not run; the final grade is the **net downgrade count** from `research/downgrade.py::score()` |
| unchanged either way | detection, the counter-day-trend cap, the fill, the stop, the R denominator, the downgrade variables' own code, `ON_WATCH` |

**The ladder.** `signal_runner.SAC_TIER` maps his grade onto the engine's alphabet, and `B` is deliberately **not in the range** -- killing it is the whole point:

| net downgrades | his grade | engine tier | tradeable |
|---:|---|---|---|
| 0 or fewer | **S** | `A+` | yes |
| 1 | **A** | `A` | yes |
| 2 | **C** | `C` | yes |
| 3 or more | **X** | `X` | **no -- `_SKIP_GRADES`** |

`net` is the tripped count after `downgrade.py`'s confluence `+1` (Austin, 2026-08-24: BR+OCR confluence "counts as +1 instead of a downgrade"). W9 floors `net` at 0 and this does not; the two are grade-equivalent, since anything at or below 0 is `S` either way. The round trip against `research/t70_test1_score.LADDER` is exact -- `A+ -> S`, `A -> A`, `C -> C` -- so this A/B and the held-out scorer count the same thing. `research/test_sac_ladder.py` asserts it.

**The two variable sets, named rather than buried.**

| set | variables counted |
|---|---|
| `shipped` (arm `on`) | the eight as committed, including the wrong-signed `level_not_respected` and the never-tripping `break_then_rejection` |
| `w9c` (arm **`on_w9c`**) | those eight minus `level_not_respected`, **plus `sequence_gate` turned on for this call** (ballot b2, right-signed at -0.3216R on this book) |

`sequence_gate` needs state `score()` cannot compute -- the 1-based ordinal of this entry among every entry graded on the same symbol-day. `SignalRunner._sac_seq` supplies it, incremented on **every** signal that reaches the grader whatever its incumbent grade, which is the same population and ordering `research/p20_sequence_gate.annotate_sequence` uses over the book -- so the engine and W9's simulation count the same thing. The 84%-rule re-entry is exempt, per Austin.

**One conflict, resolved in the spec's favour and named rather than hidden.** `downgrade.score()` FLOORS its own ladder at `C` -- Austin, 2026-08-24, asked directly what happens at three or more downgrades. The 2026-08-28 ladder above kills the 3+ bucket as `X` instead. This flag implements the LATER answer, the one `Specs/omen6-h2-master-spec.md` section 1.2 makes the contract, by reading the tripped list rather than `score()["grade"]` -- so `downgrade.py` itself is untouched and the floor simply is not applied. **If Austin meant the C floor to stand, the 3+ bucket becomes `C` and most of the lost book comes back**; that is a one-line change and it is his call, not mine.

A signal `score()` cannot grade (no bars, or no level) is `X`, not a guess -- absence of an input is not evidence of a setup, the convention `downgrade.py` itself uses.

## 2. The ladder does not reproduce him -- his own 59 verdicts

On 2026-08-28 Austin graded **59 engine-proposed `B`-only signals** himself: `research/marks/deck_marks_h2_3lane_2026-08-28.jsonl`, lane `b_remap`. These are the exact rows the remap is about, so for the first time the ladder can be scored against the thing it claims to reproduce rather than against a book. Scored by `research/w1_ladder_vs_marks.py`.

| | agreement with Austin | 95% CI |
|---|---:|---:|
| **the spec's ladder** (raw downgrade count) | **26/59 = 44.1%** | [32.2%, 56.7%] |
| the ladder on the NET count (confluence +1 applied) | 20/59 = 33.9% | [23.1%, 46.6%] |
| **majority class** -- always guess `X` | **31/59 = 52.5%** | [40.0%, 64.7%] |

**The ladder is worse than guessing.** A grader that cannot beat "always say X" has not learned anything about his judgement. The net count is worse still (33.9%), and 24 of the 59 cards pin the confluence bit exactly -- where they do not, the raw count is used, which can only flatter the net row.

**And `B` is not garbage.** He takes **28 of 59 = 47.5%** of them, including **5 S**. His S grades came at downgrade counts [2, 2, 2, 3, 3] and **never at 0**; at 0 downgrades, where the ladder says `S`, he said `A` both times. The count is not monotonic in his judgement.

| downgrades | cards | ladder says | his S | his A | his C | his X |
|---:|---:|---|---:|---:|---:|---:|
| 0 | 2 | S | 0 | 2 | 0 | 0 |
| 1 | 8 | A | 0 | 4 | 1 | 3 |
| 2 | 19 | C | 3 | 2 | 4 | 10 |
| 3 | 23 | X | 2 | 1 | 4 | 16 |
| 4 | 6 | X | 0 | 2 | 2 | 2 |
| 5 | 1 | X | 0 | 1 | 0 | 0 |

### No single variable separates either

His base X rate on these cards is 52.5%. A variable carries information only if his X rate differs between the rows it trips on and the rows it does not.

| variable | trips | X rate when tripped | X rate when clean | delta |
|---|---:|---:|---:|---:|
| `no_displacement` | 29 (49.2%) | 58.6% | 46.7% | +12.0 pts |
| `stale_retest` | 0 (0.0%) | n/a | 52.5% | n/a |
| `level_not_respected` | 37 (62.7%) | 59.5% | 40.9% | +18.6 pts |
| `exhausted` | 4 (6.8%) | 50.0% | 52.7% | -2.7 pts |
| `counter_trend_not_respected` | 55 (93.2%) | 52.7% | 50.0% | +2.7 pts |
| `break_then_rejection` | 0 (0.0%) | n/a | 52.5% | n/a |
| `no_retest` | 6 (10.2%) | 66.7% | 50.9% | +15.7 pts |
| `ocr_not_respected` | 13 (22.0%) | 38.5% | 56.5% | -18.1 pts |

`counter_trend_not_respected` fires on 93% of the cards -- a variable that is true of almost every row cannot separate anything, whichever way it points. `stale_retest` and `break_then_rejection` never trip at all, which is the same finding `research/w9_downgrade_signs.md` reached on the 2-year book from the other direction.

### Does ANY function of the eight beat the baseline?

Scored on TAKE vs SKIP -- the decision the engine actually makes, and the easier of the two problems. Every fitted family is scored **leave-one-out**, refitting inside each fold, so that fitting on n=59 cannot be mistaken for a result.

| rule | accuracy | 95% CI | separates from baseline? |
|---|---:|---:|---|
| majority class (always `skip`) | 52.5% | [40.0%, 64.7%] | -- |
| the spec's ladder (no fitting) | 34/59 = 57.6% | [44.9%, 69.4%] | no -- beats it by 3 rows, CI still contains it |
| best count threshold (LOO) | 35/59 = 59.3% | [46.6%, 70.9%] | no -- beats it by 4 rows, CI still contains it |
| best single variable (LOO) | 35/59 = 59.3% | [46.6%, 70.9%] | no -- beats it by 4 rows, CI still contains it |
| weighted score (LOO) | 26/59 = 44.1% | [32.2%, 56.7%] | no |

**Nothing tried separates from the majority-class baseline.** The best of them (`count_threshold`, 59.3%) is 4 rows better than the baseline on 59 cards, and its interval still contains it. Fitting harder on 59 rows is how a project convinces itself of something that is not there, so this stops here.

**Caveats, stated where the number is quoted.** n=59 is small; one row of a 60-card lane may not have been pasted (the file carries 59 graded rows and 0 were skipped as ungraded or off-lane). He grades the remaining 60 cards tomorrow morning, so this is a **first read, not a verdict** -- but it is enough to stop the ladder shipping as though it reproduced him.

## 3. With the flag OFF the book is byte-identical to HEAD

The claim, checked rather than asserted. `backtest_2y.py` was run once per arm against the same `data_archive/` -- first from **unmodified HEAD code before the flag existed**, then from the patched tree with the flag forced in each child's environment. sha256 is taken over the whole `trades` array; `meta.generated` is a wall clock and is the one field excluded. `data_archive/` is cache-first and no run made a network call.

| run | environment | signals | traded | sha256 of `trades` |
|---|---|---:|---:|---|
| `head` | unmodified HEAD, no flag | 45,193 | 1,017 | `1b70bb06994e3213725deeb5e856d502a1ffb23c38b07da8ff56e17cc8f94d25` |
| `off` | `ENABLE_SAC_LADDER=0` | 45,193 | 1,017 | `1b70bb06994e3213725deeb5e856d502a1ffb23c38b07da8ff56e17cc8f94d25` |
| `nofloor` | `ENABLE_KILL_B_FLOOR=1` | 45,193 | 48 | `a8b901acab78f5268b2ccdff42a15aa13a57a014bbc707fcf8c19f75ddf79ce3` |
| `on_w9c` | `ENABLE_SAC_LADDER=1` `SAC_LADDER_VARSET=w9c` | 45,252 | 649 | `9ee67334ef3934a719cfa815ab9f48a4ef019c27283bb5e14e0a48f98d9b4cfb` |
| `on` | `ENABLE_SAC_LADDER=1` | 45,246 | 564 | `fa2b1b301ad47622e41d65068be9362ea614078670c2bdefcd01185be4155bee` |
| `on_all` | `ENABLE_SAC_LADDER=1` `SAC_LADDER_REGRADE_ALL=1` | 45,924 | 12,770 | `62eb3e07d2e776cf52897dd9583011524506bd372d22d0f9ed8c0bdd9400beea` |

**`head` and `off` are identical.** The flag-off engine is the flag-less engine -- 45,193 signals and 1,017 traded rows, every field of every row equal. Reproduce with `python research/w1_sac_ladder_ab.py identical`.

## 4. The 100 HELD-OUT OMEN Test 1 cards -- reported first

`research/marks/probe_omen_test1_2026-08-27.jsonl` -- 15 S / 27 A / 16 C / 42 X, graded 2026-08-27, never shown to the engine and never fitted on. Scored by `research/t70_test1_score.py`'s own `score_all`, imported not reimplemented, once per arm. `grade_std: "none"` is his **X**: he looked at the day and refused it, so a fire there is a false fire, not an unlabelled day.

| metric | `off` | **`nofloor`** | `on_w9c` | `on` | `on_all` |
|---|---:|---:|---:|---:|---:|
| **S recall** -- fires at all on an S day | 3/15 = 20% | 0/15 = 0% | 1/15 = 7% | 2/15 = 13% | 6/15 = 40% |
| S recall, in-universe | 2/12 = 17% | 0/12 = 0% | 0/12 = 0% | 1/12 = 8% | 3/12 = 25% |
| **false fire** on refused (X) days | 12/42 = 29% | 8/42 = 19% | 8/42 = 19% | 7/42 = 17% | 33/42 = 79% |
| false fire, in-universe | 11/37 = 30% | 8/37 = 22% | 8/37 = 22% | 7/37 = 19% | 28/37 = 76% |
| entry match +-2 bars (of the 58) | 4/58 = 7% | 1/58 = 2% | 2/58 = 3% | 3/58 = 5% | 10/58 = 17% |
| day precision (of days it fired on) | 15/27 = 56% | 10/18 = 56% | 8/16 = 50% | 10/17 = 59% | 31/64 = 48% |
| **grade agreement** on the 58 he graded | 5/58 = 9% | 4/58 = 7% | 2/58 = 3% | 2/58 = 3% | 13/58 = 22% |
| engine tier mix | {'A': 1, 'B': 21, 'C': 5} | {'A': 1, 'C': 17} | {'A': 10, 'A+': 2, 'C': 4} | {'A': 6, 'A+': 6, 'C': 5} | {'A': 19, 'A+': 42, 'C': 3} |

**The verdict arm moves S recall -3 and false fires -4.**

**Read the recall and the false fires together.** The combined gate (`research/p23_combined_arms.md`) is recall minus false-fire rate: `off` -0.086, `nofloor` -0.190, `on_w9c` -0.124, `on` -0.033, `on_all` -0.386. An arm that fires less often gives up recall and false fires at the same time, so neither column ranks it alone.

**Recall governs** (`CLAUDE.md` / ballot q20: a complete engine miss of an S trade matters more than tier accuracy). On the verdict arm S recall moves -3, so this ladder **does not pay for its shrunken book in recall**. The only arm here that buys held-out recall is `on_all`, and it buys it by firing on far more refused days as well -- see section 6.

### Which held-out S days each arm finds

| arm | S days found (of 15) |
|---|---|
| `off` | 3 -- BABA 2026-02-04, IWM 2025-04-14, MU 2026-03-09 |
| `nofloor` | 0 -- none |
| `on_w9c` | 1 -- IWM 2025-04-14 |
| `on` | 2 -- BABA 2026-02-04, IWM 2025-04-14 |
| `on_all` | 6 -- AAPL 2026-07-08, ACHR 2026-04-10, BABA 2026-02-04, IWM 2025-03-14, IWM 2025-04-14, MU 2026-03-09 |

### Which held-out days each arm switches, against `off`

| his grade | `nofloor`: +fired / -lost | `on_w9c`: +fired / -lost | `on`: +fired / -lost | `on_all`: +fired / -lost |
|---|---|---|---|---|
| **S** | +0 -- / -3 BABA 2026-02-04, IWM 2025-04-14, MU 2026-03-09 | +0 -- / -2 BABA 2026-02-04, MU 2026-03-09 | +0 -- / -1 MU 2026-03-09 | +3 AAPL 2026-07-08, ACHR 2026-04-10, IWM 2025-03-14 / -0 -- |
| **A** | +0 -- / -0 -- | +0 -- / -2 AVGO 2025-01-14, MU 2026-02-19 | +0 -- / -1 MU 2026-02-19 | +11 AAPL 2025-06-03, COIN 2025-08-05, CRM 2026-05-14, IWM 2026-02-11, MARA 2025-08-06, META 2025-02-27, MSFT 2025-04-11, PLTR 2025-08-18, PLTR 2025-11-03, SPY 2026-04-17, UBER 2025-09-18 / -0 -- |
| **C** | +0 -- / -2 IREN 2025-09-10, NFLX 2025-10-02 | +0 -- / -3 NFLX 2025-10-02, PLTR 2025-12-16, TSLA 2026-01-08 | +0 -- / -3 NFLX 2025-10-02, PLTR 2025-12-16, TSLA 2026-01-08 | +4 ACHR 2025-12-11, AVGO 2026-06-30, MSFT 2025-05-19, NFLX 2026-03-24 / -2 NFLX 2025-10-02, TSLA 2026-01-08 |
| **X** | +0 -- / -4 COIN 2025-12-10, HOOD 2026-06-26, IWM 2025-05-02, NFLX 2025-01-07 | +0 -- / -4 HOOD 2026-06-26, IWM 2025-05-02, MU 2026-05-22, NFLX 2025-01-07 | +0 -- / -5 COIN 2025-12-10, HOOD 2026-06-26, IWM 2025-05-02, MU 2026-05-22, NFLX 2025-01-07 | +21 ACHR 2026-03-06, ACHR 2026-05-29, AMD 2025-09-16, AMZN 2025-02-11, AVGO 2025-01-17, AVGO 2025-04-25, GOOGL 2026-05-06, GOOGL 2026-05-28, INTC 2025-01-17, INTC 2025-01-21, IWM 2025-02-18, IWM 2026-06-09, MARA 2025-10-24, MSFT 2025-03-11, MSFT 2026-08-17, MU 2025-09-19, NVDA 2026-07-17, PLTR 2025-06-30, PLTR 2026-07-20, TSLA 2025-08-07, TSLA 2025-12-02 / -0 -- |

### Grade agreement

Rows are his grade; columns are the best engine tier fired that day, mapped onto his ladder by `t70_test1_score.maps_to`. The diagonal is agreement.

**`off`** -- diagonal 5/58 = 9%

| his \ engine | A+ (his S) | A / B (his A) | C (his C) | silent (his X) | row total |
|---|---:|---:|---:|---:|---:|
| **S** | 0 | 3 | 0 | 12 | 15 |
| **A** | 0 | 4 | 2 | 21 | 27 |
| **C** | 0 | 5 | 1 | 10 | 16 |

**`nofloor`** -- diagonal 4/58 = 7%

| his \ engine | A+ (his S) | A / B (his A) | C (his C) | silent (his X) | row total |
|---|---:|---:|---:|---:|---:|
| **S** | 0 | 0 | 0 | 15 | 15 |
| **A** | 0 | 0 | 6 | 21 | 27 |
| **C** | 0 | 0 | 4 | 12 | 16 |

**`on_w9c`** -- diagonal 2/58 = 3%

| his \ engine | A+ (his S) | A / B (his A) | C (his C) | silent (his X) | row total |
|---|---:|---:|---:|---:|---:|
| **S** | 0 | 1 | 0 | 14 | 15 |
| **A** | 0 | 2 | 2 | 23 | 27 |
| **C** | 1 | 2 | 0 | 13 | 16 |

**`on`** -- diagonal 2/58 = 3%

| his \ engine | A+ (his S) | A / B (his A) | C (his C) | silent (his X) | row total |
|---|---:|---:|---:|---:|---:|
| **S** | 1 | 1 | 0 | 13 | 15 |
| **A** | 1 | 1 | 3 | 22 | 27 |
| **C** | 2 | 1 | 0 | 13 | 16 |

**`on_all`** -- diagonal 13/58 = 22%

| his \ engine | A+ (his S) | A / B (his A) | C (his C) | silent (his X) | row total |
|---|---:|---:|---:|---:|---:|
| **S** | 5 | 1 | 0 | 9 | 15 |
| **A** | 10 | 7 | 0 | 10 | 27 |
| **C** | 4 | 3 | 1 | 8 | 16 |

## 5. Money -- the 2-year book, median R first

Austin's stated goal (spec section 0) is **raising the median R:R**, so median R leads this table and mean R follows it. Every arm: `backtest_2y.py` shelled once with the flag forced in the child's environment, same `data_archive/`, cache-first with zero fetches. Win rate is of DECIDED trades (scratches excluded), the convention `research/a2_bt2y_summary.py` prints and this table imports. `months green` is months with positive total R; the durability gate is EVERY month green.

| arm | population | signals | **n traded** | **median R** | mean R | win rate | months green | total R |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `off` | whole book | 45,193 | **1,017** | **+0.5660** | +0.9551 | 53.2% | **23 / 25** | +971.4 |
| `off` | S subset (`sgrade`) | 7,454 | **128** | **+1.1290** | +1.2829 | 66.4% | **23 / 25** | +164.2 |
| **`nofloor`** | whole book | 45,193 | **48** | **-0.4285** | +1.3161 | 48.9% | **12 / 18** | +63.2 |
| **`nofloor`** | S subset (`sgrade`) | 7,454 | **8** | **+1.7735** | +1.6005 | 75.0% | **6 / 7** | +12.8 |
| `on_w9c` | whole book | 45,252 | **649** | **+0.8000** | +1.0912 | 56.2% | **24 / 25** | +708.2 |
| `on_w9c` | S subset (`sgrade`) | 7,460 | **189** | **+0.9890** | +1.0922 | 60.3% | **22 / 25** | +206.4 |
| `on` | whole book | 45,246 | **564** | **+0.7745** | +1.0341 | 55.4% | **25 / 25** | +583.2 |
| `on` | S subset (`sgrade`) | 7,459 | **188** | **+0.9945** | +1.1115 | 60.6% | **21 / 25** | +209.0 |
| `on_all` | whole book | 45,924 | **12,770** | **-1.0000** | +7.4974 | 43.7% | **25 / 25** | +95741.9 |
| `on_all` | S subset (`sgrade`) | 7,485 | **5,186** | **-1.0000** | +6.1880 | 45.7% | **25 / 25** | +32090.7 |

| delta vs `off` | n traded | **median R** | mean R | win rate | months green | total R |
|---|---:|---:|---:|---:|---:|---:|
| `nofloor`, whole book | -969 | **-0.9945** | +0.3610 | -4.3 pts | -11 | -908.2 |
| `nofloor`, S subset | -120 | **+0.6445** | +0.3176 | +8.6 pts | -17 | -151.4 |
| `on_w9c`, whole book | -368 | **+0.2340** | +0.1361 | +3.0 pts | +1 | -263.2 |
| `on_w9c`, S subset | +61 | **-0.1400** | -0.1907 | -6.1 pts | -1 | +42.2 |
| `on`, whole book | -453 | **+0.2085** | +0.0790 | +2.2 pts | +2 | -388.1 |
| `on`, S subset | +60 | **-0.1345** | -0.1714 | -5.8 pts | -2 | +44.8 |
| `on_all`, whole book | +11753 | **-1.5660** | +6.5423 | -9.5 pts | +2 | +94770.5 |
| `on_all`, S subset | +5058 | **-2.1290** | +4.9051 | -20.7 pts | +2 | +31926.5 |

**The money gate is mean R = 2.0 with EVERY month green. Only `on_all` appear to reach it and it do not count -- 84.6% of that arm's rows are UNTAKEABLE (section 9), so its mean R is arithmetic, not money.** On the verdict arm the median goes +0.5660 -> -0.4285 (**-0.9945**), which is the number Austin actually asked to move, and the mean goes +0.9551 -> +1.3161.

### Is the ladder monotonic on the book it produces?

W9's whole point: a ladder is only a ladder if the buckets are ordered. Measured here on each arm's OWN traded rows, by the engine grade it actually shipped.

| arm | A+ = S (n, median R) | A (n, median R) | C (n, median R) |
|---|---:|---:|---:|
| `off` | 2, +3.2465 | 15, -1.0000 | 0, -- |
| `nofloor` | 2, +3.2465 | 15, -1.0000 | 0, -- |
| `on_w9c` | 190, +1.1330 | 459, +0.5490 | 0, -- |
| `on` | 188, +0.9945 | 376, +0.6295 | 0, -- |
| `on_all` | 5186, -1.0000 | 7584, -1.0000 | 0, -- |

### `B` is gone -- the engine-grade mix over the traded rows

| arm | `A` | `A+` | `B` | total |
|---|---:|---:|---:|---:|
| `off` | 15 | 2 | 1,000 | 1,017 |
| `nofloor` | 15 | 2 | 31 | 48 |
| `on_w9c` | 459 | 190 | 0 | 649 |
| `on` | 376 | 188 | 0 | 564 |
| `on_all` | 7,584 | 5,186 | 0 | 12,770 |

**`B` traded rows: 1,000 on `off`, 31 on `nofloor`, 0 on `on_w9c`, 0 on `on`, 0 on `on_all`.** The ladder arms emit no `B` at all. `nofloor` still shows a residue because it removes the ARRIVAL-ORDER floor only -- the 84%-rule blocks in `detect_signals` emit `B` directly and are untouched by this ticket.

## 6. How hard the book shrinks, and who loses everything

| | `off` | `nofloor` | `on_w9c` | `on` | `on_all` |
|---|---:|---:|---:|---:|---:|
| signals detected | 45,193 | 45,193 | 45,252 | 45,246 | 45,924 |
| **traded rows** | 1,017 | 48 | 649 | 564 | 12,770 |
| change vs `off` | -- | -969 (-95.3%) | -368 (-36.2%) | -453 (-44.5%) | +11753 (1155.7%) |
| symbols with a book | 27 | 20 | 27 | 27 | 28 |
| total R | +971.4 | +63.2 | +708.2 | +583.2 | +95741.9 |

### Every symbol that loses its ENTIRE book on `nofloor`

**7 symbols, 105 trades, +90.3 R of booked result.** Rows under `universe.MIN_SAMPLE_N` (=20) are MARKED, never dropped -- below ~20 trades one more trade swings the mean by the same order as the money gate itself.

| symbol | trades lost | median R it was booking | mean R | total R |
|---|---:|---:|---:|---:|
| NFLX | 30 | -0.2440 | +0.8931 | +26.8 |
| UBER | 26 | -1.0000 | +1.2548 | +32.6 |
| GOOGL | 21 | -1.0000 | +0.3646 | +7.7 |
| AAPL _(low n)_ | 19 | +1.1850 | +0.8597 | +16.3 |
| IWM _(low n)_ | 5 | +1.2590 | +0.7316 | +3.7 |
| ACHR _(low n)_ | 2 | +1.2790 | +1.2790 | +2.6 |
| SOFI _(low n)_ | 2 | +0.3335 | +0.3335 | +0.7 |

On `on_w9c` the same count is **0** symbol(s).
On `on` the same count is **0** symbol(s).
On `on_all` the same count is **0** symbol(s).

### Per symbol

| symbol | `off` n / mean R | `nofloor` n / mean R | `on_w9c` n / mean R | `on` n / mean R | `on_all` n / mean R |
|---|---:|---:|---:|---:|---:|
| COIN | 104 / +0.7468 | 8 _(low n)_ / +0.5191 | 78 / +0.9554 | 71 / +1.1878 | 644 / +9.5444 |
| TSLA | 75 / +0.8187 | 4 _(low n)_ / +1.1747 | 52 / +1.3597 | 52 / +1.5057 | 638 / +8.1545 |
| MU | 82 / +1.1982 | 3 _(low n)_ / -0.1803 | 50 / +1.3013 | 47 / +0.7905 | 558 / +13.7144 |
| HOOD | 75 / +1.8421 | 3 _(low n)_ / +0.7937 | 47 / +1.8899 | 39 / +1.8593 | 572 / +4.1673 |
| PLTR | 77 / +0.8192 | 2 _(low n)_ / +2.4240 | 47 / +0.8444 | 38 / +0.7400 | 546 / +5.0164 |
| AMD | 69 / +0.8884 | 2 _(low n)_ / +2.0385 | 34 / +1.3488 | 31 / +0.9574 | 558 / +4.7991 |
| NVDA | 48 / +0.7326 | 3 _(low n)_ / +0.7813 | 26 / +0.6248 | 21 / +0.4934 | 583 / +4.5830 |
| META | 42 / +1.0200 | 3 _(low n)_ / +0.5043 | 31 / +0.9328 | 29 / +0.8367 | 541 / +6.1800 |
| ORCL | 52 / +0.8962 | 1 _(low n)_ / +4.1860 | 43 / +1.0572 | 36 / +0.9802 | 505 / +6.1468 |
| AVGO | 55 / +0.7998 | 1 _(low n)_ / -1.0000 | 32 / +0.9359 | 29 / +0.9326 | 506 / +4.9604 |
| AMZN | 33 / +0.5010 | 1 _(low n)_ / +2.5480 | 19 _(low n)_ / +0.7582 | 14 _(low n)_ / +0.9933 | 531 / +35.0200 |
| INTC | 30 / +1.2219 | 1 _(low n)_ / -1.0000 | 23 / +0.7698 | 17 _(low n)_ / +0.6235 | 514 / +4.6824 |
| GOOGL | 21 / +0.3646 | -- | 16 _(low n)_ / +0.5212 | 7 _(low n)_ / +0.2713 | 504 / +9.2813 |
| QQQ | 9 _(low n)_ / +0.7413 | 2 _(low n)_ / +0.1285 | 4 _(low n)_ / +1.4643 | 4 _(low n)_ / +1.4643 | 514 / +7.6622 |
| ACHR | 2 _(low n)_ / +1.2790 | -- | 1 _(low n)_ / +0.8440 | 1 _(low n)_ / +0.8440 | 514 / +2.5485 |
| IWM | 5 _(low n)_ / +0.7316 | -- | 1 _(low n)_ / +1.2590 | 1 _(low n)_ / +1.2590 | 508 / +4.2779 |
| NFLX | 30 / +0.8931 | -- | 18 _(low n)_ / +0.0838 | 17 _(low n)_ / -0.1313 | 443 / +3.9328 |
| AAPL | 19 _(low n)_ / +0.8597 | -- | 9 _(low n)_ / +0.9230 | 6 _(low n)_ / +1.2720 | 470 / +4.8122 |
| SPY | 4 _(low n)_ / +0.7442 | 1 _(low n)_ / +1.8250 | 5 _(low n)_ / +0.3954 | 6 _(low n)_ / +0.7480 | 463 / +4.9529 |
| MSFT | 29 / +0.5982 | 4 _(low n)_ / +1.1515 | 17 _(low n)_ / +1.1009 | 14 _(low n)_ / +1.2684 | 404 / +6.2270 |
| IREN | 52 / +0.8645 | 1 _(low n)_ / +13.9170 | 37 / +1.9112 | 27 / +2.2705 | 333 / +6.8786 |
| BABA | 16 _(low n)_ / +0.8820 | 2 _(low n)_ / +0.0500 | 11 _(low n)_ / +0.9985 | 13 _(low n)_ / +0.7982 | 397 / +4.5027 |
| TSM | 27 / +0.7458 | 1 _(low n)_ / -1.0000 | 13 _(low n)_ / +0.3584 | 14 _(low n)_ / -0.0634 | 299 / +6.2869 |
| MARA | -- | -- | -- | -- | 336 / +10.2997 |
| UBER | 26 / +1.2548 | -- | 17 _(low n)_ / +1.9806 | 16 _(low n)_ / +1.4181 | 273 / +9.3499 |
| SOFI | 2 _(low n)_ / +0.3335 | -- | 1 _(low n)_ / -1.0000 | 1 _(low n)_ / -1.0000 | 307 / +5.1525 |
| CRM | 18 _(low n)_ / +1.3416 | 1 _(low n)_ / +0.1430 | 10 _(low n)_ / +1.0402 | 8 _(low n)_ / +0.4399 | 266 / +6.5864 |
| SPCX | 15 _(low n)_ / +1.9390 | 4 _(low n)_ / +3.7795 | 7 _(low n)_ / -0.7743 | 5 _(low n)_ / -0.3630 | 43 / +2.1100 |

## 7. What killing `B` does to three gates downstream

`research/w12_bug_sweep.md` swept the grade and gate path the night this ticket ran, precisely because 1,000 of the 1,017 rows in the traded book are `B`. Three of its findings are downstream of this remap and are **measured here on the actual arm books**, not simulated.

### 1. The tight-stop gate is consulted on `C` only, and it is sign-backwards

`signal_runner._route` asks `_min_viable_stop` when `sig["grade"] == "C"` and never otherwise. Re-derived on the graded bar over the 1,017 traded rows (`research/w12_tight_stop.py`), it **rejects the better half**: rejected rows mean **+1.0861 R**, kept rows **+0.6188 R** -- a gap of **0.4673 R, 49x the +-0.0095 R narrow bar**, in the wrong direction.

Today it barely matters because `C` is small. **This ticket is what makes it matter**, and the arm books show it happening:

| arm | `skipped_tight_stop` | vs `off` |
|---|---:|---:|
| `off` | 805 | -- |
| `nofloor` | 1,506 | +701 |
| `on_w9c` | 560 | -245 |
| `on` | 634 | -171 |
| `on_all` | 16,786 | +15981 |

Read that table carefully: `nofloor` sends **+701** more rows into the gate, because demoting the floored `B`s leaves them all `C`. The ladder arms send FEWER, because the ladder promotes most of those same rows to `A+`/`A` where the gate is never consulted at all -- so on those arms the gate is not doing the shrinking, the `X` bucket is.

**So `C`'s mean R in every table above is depressed by a gate that throws away its better rows, and the verdict arm's collapse is mostly that gate rather than the grade.** Nothing here fixes it -- widening it to all grades, dropping it, or leaving it is a decision with a 0.4673 R price tag on it, and it is Austin's.

### 2. `C` is alert-only, so the spec's `C = tradeable` cannot happen

`backtest_week.SimTrade.counted` is `status == "fired" and grade != "C"`. Spec section 1.2 says two downgrades = `C` = **tradeable: yes**. Those two cannot both be true, and the code wins today: no `C` has ever entered the traded book.

| arm | fired | of which alerts (`C`) | traded |
|---|---:|---:|---:|
| `off` | 1,394 | 377 | 1,017 |
| `nofloor` | 703 | 655 | 48 |
| `on_w9c` | 899 | 250 | 649 |
| `on` | 847 | 283 | 564 |
| `on_all` | 14,155 | 1,385 | 12,770 |

W12 priced the difference on the shipped-eight ladder: **n=379 mean +1.0926 median +0.9400** with `C` excluded against **n=710 mean +1.0069 median +0.7070** with `C` included. This report's book columns are the `C`-excluded reading, because that is what the engine does.

### 3. The 84%-rule arm population moves by 22x as a side effect

`backtest_week._arm_84` needs `t.counted and t.grade in ("A+", "A")`. The shipped grader emits 17 such rows in 45,193 signals, so the 84% rule fires three times in two years. The ladder emits `A+` and `A` freely, and the arm population moves with it -- **nobody chose that**:

| arm | traded rows graded `A+` or `A` |
|---|---:|
| `off` | 17 |
| `nofloor` | 17 |
| `on_w9c` | 649 |
| `on` | 564 |
| `on_all` | 12,770 |

`research/test_w12_grade_gates.py` asserts all three of these at HEAD and is **green** with every flag here at its default, which is the point of the defaults. Flip one and those asserts are the tripwire, not a regression.

## 8. Which trades the ladder swapped, and the two levers kept apart

`on_all` is reported beside the verdict arm and never averaged into it. It lets the same ladder ALSO regrade the **42,937** signals `omen_bot._grade_pa` already vetoed on candle shape. That is R3's lever (`ENABLE_DOWNGRADE_GRADER`, priced in `research/r3_downgrade_grader_ab.md`) reached by a different road: it makes the book GROW rather than shrink, and conflating the two would turn W1 into an experiment that was already run.

Rows below are matched between `off` and `nofloor` on `(symbol, day, entry time, setup, direction, level)` -- detection does not read the grade, so the same setup on the same bar is the same row (`g13_floor_fix_ab.row_key`). That key is not unique in every book: **0 `off` and 0 `nofloor` traded rows collide on it** and are counted once here. Every headline number above is taken from the RAW traded list, never from this deduped view.

| | count | of which takeable | mean R | median R | max R |
|---|---:|---:|---:|---:|---:|
| traded in BOTH arms | 48 | -- | +1.3161 | -0.4285 | -- |
| **lost** -- traded `off`, not `nofloor` | 969 | 953 | +0.9373 | +0.5830 | +14.3 |
| **gained** -- traded `nofloor`, not `off` | 0 | 0 | +0.0000 | +0.0000 | +0.0 |

What became of the lost trades in the `nofloor` arm: `fired/C` 259, `skipped_d/X` 10, `skipped_repeat_entry/C` 7, `skipped_tight_stop/C` 693.

**The matched population is the one place the ladder could change price rather than membership, and it does not**: 48 rows traded by both arms, **0** with a different R. This flag moves MEMBERSHIP. Every R delta above is a different book, not the same book priced better.

## 9. Does the delta clear its error bar

**The wide bar (+-1.5799 R) is RETIRED** -- Austin, 2026-08-28: a stop fires only on a candle CLOSE and there is one close per bar, so the 790-of-792 `intrabar_stop` class was never ambiguous (spec section 1.1). The bar this report is read against is the **narrow** one, recomputed on each arm's own book by `research/g3_onwatch_2y.error_bars` rather than quoted. The spec's published figure is +-0.0088 R on the ON-WATCH-off arm and +-0.0095 R on the shipped arm; the recomputations are below.

| | |
|---|---|
| NARROW bar, `off` arm (recomputed) | +-0.0095 R |
| NARROW bar, `nofloor` arm (recomputed) | +-0.2003 R |
| NARROW bar, `on_w9c` arm (recomputed) | +-0.0167 R |
| NARROW bar, `on` arm (recomputed) | +-0.0170 R |
| NARROW bar, `on_all` arm (recomputed) | +-0.0256 R |
| NARROW bar carried from the spec | +-0.0088 R |
| **`nofloor` median R delta** | **-0.9945 R** |
| does the median delta clear the narrow bar? | **yes**, by 105x |
| `nofloor` mean R delta, as booked | +0.3610 R |
| does the mean delta clear the narrow bar? | **yes**, by 38x |
| `nofloor` takeable-only mean R delta | +0.5049 R |
| does THAT clear the narrow bar? | **yes**, by 53x |
| `on_w9c` median R delta | +0.2340 R (**yes**, by 25x) |
| `on` median R delta | +0.2085 R (**yes**, by 22x) |
| `on_all` median R delta | -1.5660 R (**yes**, by 166x) |

Both bars are one-directional -- the booked mean R is a **ceiling**, never a midpoint, because each back-dated fill assumes the trigger beat the stop inside a minute nobody can see.

### The G13 sizing trap, checked on every arm

`backtest_week` sizes every trade at `RISK_DOLLARS / |entry - stop|`, so a row whose risk is under the engine's own floor has a 1R that is a position size nobody can take and an R that is a division by ~0. G13's arm was 73.3% such rows and its mean R of +14.72 was arithmetic rather than money. The same test, `g13_floor_fix_ab.sizeable`, imported:

| arm | traded | takeable | **untakeable** | of which `entry == stop` | max R |
|---|---:|---:|---:|---:|---:|
| `off` | 1,017 | 995 | **22 (2.2%)** | 0 | +14.3 |
| `nofloor` | 48 | 42 | **6 (12.5%)** | 0 | +13.9 |
| `on_w9c` | 649 | 636 | **13 (2.0%)** | 0 | +14.3 |
| `on` | 564 | 550 | **14 (2.5%)** | 0 | +13.9 |
| `on_all` | 12,770 | 1,961 | **10,809 (84.6%)** | 998 | +15100.0 |

**THE TRAP FIRES ON `nofloor`, `on_all` -- read those arms' takeable-only row only.** Takeable-only mean R on the verdict arm: `off` +0.9716 (n=995), `nofloor` +1.4765 (n=42) -- delta **+0.5049 R**.

## 10. The in-sample recall gate -- `research/regression_gate.py`

**The gate is RED at HEAD and that is not this ticket's doing**: six `s_grade` marks were dropped by `5e3677ea`, diagnosed in `research/g12_recall_regression.md`. What this row owes is whether the ladder adds NEW drops. Held-out beats in-sample, so this section is BELOW section 3 on purpose.

| arm | `any_signal` | `s_grade` | dropped vs baseline | NEW drops | gate |
|---|---:|---:|---|---|---|
| baseline (`research/baseline_3.8.json`) | 60 | 10 | -- | -- | -- |
| `off` | 75 | **5** | 0 any_signal, 6 s_grade | -- | **RED** |
| `nofloor` | 76 | **4** | 0 any_signal, 7 s_grade | 1 s_grade ['COIN|2025-06-26|18'] / 0 any_signal [] | **RED** |
| `on_w9c` | 75 | **3** | 0 any_signal, 7 s_grade | 1 s_grade ['MARA|2024-10-18|11'] / 0 any_signal [] | **RED** |
| `on` | 75 | **4** | 0 any_signal, 7 s_grade | 1 s_grade ['MARA|2024-10-18|11'] / 0 any_signal [] | **RED** |
| `on_all` | 75 | **27** | 0 any_signal, 3 s_grade | 1 s_grade ['MARA|2024-10-18|11'] / 0 any_signal [] | **RED** |

## 11. What this does not say

- **It does not recommend the ladder, and after section 2 it cannot.** 26/59 against a 52.5% baseline is a refutation, not a tuning problem. The ladder arms are in this report so the cost of the idea is on record.
- **It does not clear the `B`-floor removal either.** `nofloor` is right in principle -- arrival order should not select a book -- and on this engine it costs every held-out S day (3/15 -> 0/15) and 95.3% of the book, because `C` is alert-only and faces a sign-backwards gate. The principle is not what is broken; the two gates in section 7 are.
- **n=59 is small, and it is a FIRST READ.** One row of a 60-card lane may not have been pasted. Austin grades the remaining 60 cards in the morning; every number in section 2 should be recomputed against 119 before anything is decided on it.
- **It does not ship anything.** `ENABLE_SAC_LADDER` stays `False`, `ENABLE_KILL_B_FLOOR` stays `False`, `SAC_LADDER_VARSET` stays `"shipped"`, `downgrade.ENABLE_SEQUENCE_GATE` stays `False`, and the `B` floor is not deleted. Flipping any of them changes what trades, and re-freezing the engine voids `research/omen6_forward.py`.
- **It does not say the variables are right, even in set (c).** `research/a1_threshold_sweep.md` measured the grader as overfit -- mix distance from Austin 0.086 in-sample against 0.282 on the held-out 100 -- and every threshold in `research/downgrade.py` except `STALE_BARS` is a number Austin never gave. W9 fixed the SIGNS, not the thresholds. W1 was told not to change the variables themselves and did not.
- **It does not settle the C floor.** `downgrade.py` floors at C (2026-08-24); this ladder kills 3+ as X (2026-08-28). Section 1 names the conflict; only Austin closes it, and closing it the other way brings most of the lost book back.
- **It does not fix the exit.** Spec section 0: the tape offers +3.8436 R of MFE and the incumbent ladder keeps 21.9% of it. A grade change chooses which trades are taken; it cannot make a taken trade keep more.
- **It does not fix arrival order for the SILENT days.** Killing the `B` floor stops arrival order promoting a C. It does nothing about the days the engine never speaks on, which is where the held-out recall of 3/15 actually lives (W5).
- The held-out sample is 100 cards and 15 S days. A 3/15 -> 0/15 read has a wide interval of its own; what it can rule out is a LARGE out-of-sample recall change, not a small one.

## 12. Reproduce

```bash
git stash push -- signal_runner.py          # HEAD control, before the flag
python backtest_2y.py --days 730 --out research/w1_arm_head.json
git stash pop
python research/test_sac_ladder.py          # the assert-based check
python research/w1_sac_ladder_ab.py --selfcheck
python research/w1_sac_ladder_ab.py book --arm off
python research/w1_sac_ladder_ab.py book --arm nofloor
python research/w1_sac_ladder_ab.py book --arm on_w9c
python research/w1_sac_ladder_ab.py book --arm on
python research/w1_sac_ladder_ab.py book --arm on_all
python research/w1_sac_ladder_ab.py identical   # head == off, byte for byte
python research/w1_sac_ladder_ab.py test1       # the 100 held-out cards
python research/w1_sac_ladder_ab.py gate
python research/w1_sac_ladder_ab.py stats
python research/w1_sac_ladder_ab.py report
```

The arm books are ~40 MB each and are NOT committed, the same convention `research/g3_onwatch_2y.py`, `research/g13_floor_fix_ab.py` and `research/r3_downgrade_grader_ab.py` follow. `data_archive/` must be identical across every run; the `head` run's 45,193 signals / 1,017 traded is the check that it was.

## Provenance

Generated by `research/w1_sac_ladder_ab.py report` at _this commit_ (`--selfcheck` green, `research/test_sac_ladder.py` green). Engine change: `signal_runner.py` (`ENABLE_KILL_B_FLOOR`, `ENABLE_SAC_LADDER`, `SAC_LADDER_REGRADE_ALL`, `SAC_LADDER_VARSET`, `SAC_VARSET_DROP`, `SAC_VARSET_SEQ`, `SAC_TIER`, `SignalRunner._sac_ladder_grade`, and the `not ENABLE_SAC_LADDER` guard on `_calibration_grade`'s `B` floor), all defaults unchanged. Diagnosis it implements: `research/g4_dropped_s.md`; contract: `Specs/omen6-h2-master-spec.md` section 1.2 / W1. Variable signs and the set-(c) recommendation: `research/w9_downgrade_signs.md`. Ladder arithmetic: `research/downgrade.py` at its committed constants, held-out calibration `research/a1_threshold_sweep.md`. Sequence-gate ordinal definition: `research/p20_sequence_gate.py::annotate_sequence`. Held-out scorer: `research/t70_test1_score.py`. A/B shell and the takeability test: `research/g13_floor_fix_ab.py`; held-out helpers: `research/r3_downgrade_grader_ab.py`. Austin's 59 verdicts and the baseline test: `research/w1_ladder_vs_marks.py` over `research/marks/deck_marks_h2_3lane_2026-08-28.jsonl` (tracked in git, and in `research/build_deck.py::LEGACY_MARK_FILES` so the no-repeat guarantee holds). Downstream gates: `research/w12_bug_sweep.md`, `research/w12_tight_stop.py`, `research/test_w12_grade_gates.py` (green at these defaults). Error bars: `research/g3_onwatch_2y.py`, recomputed here. Sample floor: `universe.MIN_SAMPLE_N` = 20.

Books: `head` 2026-08-28T02:12:58, `off` 2026-08-28T02:22:51, `nofloor` 2026-08-28T03:21:17, `on_w9c` 2026-08-28T03:07:47, `on` 2026-08-28T03:21:17, `on_all` 2026-08-28T02:49:58. 0 symbol-day(s) could not be classified for the error bar (missing day) and 0 row(s) had no matching bar; both are excluded from the bar, never from the money.
