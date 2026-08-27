# R3 -- `downgrade.py` as the grader, priced on held-out days first

**Held-out first, per `research/g13_floor_fix_ab.md`'s lesson: an in-sample recall gain that does not reproduce out of sample is not a result.** On the 100 OMEN Test 1 cards the flag moves S recall **3/15 -> 3/15** and false fires on days Austin refused **12/42 -> 14/42**.

**On the money it trades +293 more (1,017 -> 1,310) and the takeable-only mean R goes +0.9716 -> +0.8427, a delta of -0.1289 R -- inside T3's wide error bar of +-1.5799, so this rig does not resolve its sign.** The `on` arm's book is not contaminated (0 rows with `entry == stop`, 4.2% untakeable against 2.2% on `off`), so unlike G13 that number is money rather than arithmetic -- it simply is not big enough to read.

Nothing here ships. `signal_runner.ENABLE_DOWNGRADE_GRADER` defaults to **False**, `omen_bot.PriceActionAnalyzer._grade_pa` is not deleted, and the engine is not re-frozen -- that would VOID `research/omen6_forward.py` and it is Austin's call. Measured at _this commit_ by `research/r3_downgrade_grader_ab.py`.

## 1. What was implemented

`research/g4_dropped_s.md` is the diagnosis this implements: over two years `research/downgrade.py` scores **7,485** signals `S` and `_grade_pa` drops **7,225** of them (96.5%), 2,120 on its first line (the entry bar closed the wrong colour); and **968 of the 1,016** traded signals are `B` only because of `_calibration_grade`'s first-with-trend-signal-of-the-day floor -- the engine's real entry rule is arrival order, not grade.

| | |
|---|---|
| flag | `signal_runner.ENABLE_DOWNGRADE_GRADER`, **default False**, `ENABLE_DOWNGRADE_GRADER=1` to A/B |
| seam | `SignalRunner._grade_trade()` -- all **ten** detection sites now post through it instead of calling `PriceActionAnalyzer.grade_trade` directly |
| OFF | `PriceActionAnalyzer.grade_trade`, the same function on the same bar with the same arguments |
| ON | `research/downgrade.py::score()` on `SignalRunner._dg_bars()` -- the bar dicts `_label_confluence` and `backtest_2y.py` already grade every row with -- and the level the setup broke |
| unchanged either way | the HTF veto and the neutral-hour cap `grade_trade` wraps around `_grade_pa`, every downstream promotion and cap, the fill, the stop, the R denominator |

**His ladder onto the engine's, stated out loud.** `signal_runner.DOWNGRADE_TIER` is `S -> A+`, `A -> B`, `C -> C` -- the exact inverse of the mapping `research/t70_test1_score.py` already declares in the other direction, so a grade round-trips and the A/B and the held-out scorer count the same thing. His `A` maps onto the engine's `B` and not its `A` because `_grade_pa` can only ever emit `A+/B/C/X`: the ON arm emits from the SAME alphabet as the OFF arm, so no downstream `grade.value in ("A+", "A")` cap sees a tier the shipped grader never makes. `research/test_downgrade_grader.py` asserts the round trip.

**`downgrade.score()` has no `X`.** It floors at `C` (Austin, 2026-08-24), so on the ON arm the grader never skips anything: every signal it sees reaches at least the alert tier, and every skip in the ON book comes from a gate that is *not* the grader -- the min-risk floor, `_min_viable_stop`, the repeat-entry rule. That is the whole shape of the change, and section 4 is what it costs.

## 2. With the flag OFF the book is byte-identical to HEAD

The claim, checked rather than asserted. `backtest_2y.py` was run three times against the same `data_archive/` -- once from **unmodified HEAD code before the flag existed** (`git stash`), then twice from the patched tree with the flag forced off and on in the child's environment. sha256 is taken over the whole `trades` array; `meta.generated` is a wall clock and is the one field excluded.

| run | code | signals | traded | sha256 of `trades` |
|---|---|---:|---:|---|
| `head` | unmodified HEAD | 45,193 | 1,017 | `1b70bb06994e3213725deeb5e856d502a1ffb23c38b07da8ff56e17cc8f94d25` |
| `off` | patched, `ENABLE_DOWNGRADE_GRADER=0` | 45,193 | 1,017 | `1b70bb06994e3213725deeb5e856d502a1ffb23c38b07da8ff56e17cc8f94d25` |
| `on` | patched, `ENABLE_DOWNGRADE_GRADER=1` | 45,194 | 1,310 | `db8453ea19a8b784f0a6e8841325b2be7f2640fa3474c754a73dad6af811ea3d` |

**`head` and `off` are identical.** The flag-off engine is the flag-less engine -- 45,193 signals and 1,017 traded rows, every field of every row equal. Reproduce with `python research/r3_downgrade_grader_ab.py identical`.

## 3. The 100 HELD-OUT OMEN Test 1 cards -- reported first

`research/marks/probe_omen_test1_2026-08-27.jsonl` -- 15 S / 27 A / 16 C / 42 X, graded 2026-08-27, never shown to the engine and never fitted on. Scored by `research/t70_test1_score.py`'s own `score_all`, imported not reimplemented, once per arm. `grade_std: "none"` is his **X**: he looked at the day and refused it, so a fire there is a false fire, not an unlabelled day.

| metric | `off` (== HEAD) | `on` (downgrade grader) | delta |
|---|---:|---:|---:|
| **S recall** -- fires at all on an S day | 3/15 = 20% | 3/15 = 20% | +0 |
| S recall, in-universe | 2/12 = 17% | 2/12 = 17% | +0 |
| **false fire** on refused (X) days | 12/42 = 29% | 14/42 = 33% | +2 |
| false fire, in-universe | 11/37 = 30% | 13/37 = 35% | +2 |
| **grade agreement** on the 58 he graded | 5/58 = 9% | 6/58 = 10% | +1 |
| entry match +-2 bars (of the 58) | 4/58 = 7% | 4/58 = 7% | +0 |
| day precision (of days it fired on) | 15/27 = 56% | 17/31 = 55% | -- |
| engine tier mix | {'A': 1, 'B': 21, 'C': 5} | {'A': 2, 'B': 23, 'C': 6} | -- |

**Read the recall and the false fires together.** The gate Austin asked for first is recall minus false-fire rate (`research/p23_combined_arms.md`): `off` -0.086, `on` -0.133 -- **-0.048**. An arm that fires more often buys recall and false fires at the same time, so neither column ranks it alone.

**And `research/p23_combined_arms.md`'s other warning, which applies here: an arm can improve one thing and lose the gate that governs.** Grade agreement on the 58 goes 5/58 = 9% -> 6/58 = 10% and day precision 15/27 = 56% -> 17/31 = 55% while the recall gate goes -0.086 -> -0.133. Both are reported above and the money gate is section 5; no single column is the verdict.

### Which held-out days the flag switches, by his grade

G13's cautionary tale in one table: its in-sample fix lit up 12 new days and **not one** was a day Austin graded S.

| his grade | days newly fired by the flag | days that LOSE their fire |
|---|---|---|
| **S** | 0 | 0 |
| **A** | 1 -- COIN 2025-08-05 | 0 |
| **C** | 1 -- NFLX 2026-03-24 | 0 |
| **X** | 2 -- GOOGL 2026-05-06, NVDA 2026-07-17 | 0 |

### Grade agreement, both arms

Rows are his grade; columns are the best engine tier fired that day, mapped onto his ladder by `t70_test1_score.maps_to`. The diagonal is agreement.

**`off` (== HEAD)** -- diagonal 5/58 = 9%

| his \ engine | A+ (his S) | A / B (his A) | C (his C) | silent (his X) | row total |
|---|---:|---:|---:|---:|---:|
| **S** | 0 | 3 | 0 | 12 | 15 |
| **A** | 0 | 4 | 2 | 21 | 27 |
| **C** | 0 | 5 | 1 | 10 | 16 |

**`on` (downgrade grader)** -- diagonal 6/58 = 10%

| his \ engine | A+ (his S) | A / B (his A) | C (his C) | silent (his X) | row total |
|---|---:|---:|---:|---:|---:|
| **S** | 0 | 3 | 0 | 12 | 15 |
| **A** | 0 | 5 | 2 | 20 | 27 |
| **C** | 0 | 6 | 1 | 9 | 16 |

## 4. The in-sample recall gate -- `research/regression_gate.py`

**The gate is RED at HEAD and that is not this ticket's doing**: six `s_grade` marks were dropped by `5e3677ea`, diagnosed in `research/g12_recall_regression.md` and priced in `research/g13_floor_fix_ab.md`. What this row owes is that the flag adds **no new** drops.

| arm | `any_signal` | `s_grade` | dropped vs baseline | gate |
|---|---:|---:|---|---|
| baseline (`research/baseline_3.8.json`) | 60 | 10 | -- | -- |
| `off` (== HEAD) | 75 | **5** | 0 any_signal, 6 s_grade | **RED** |
| `on` (downgrade grader) | 75 | **6** | 0 any_signal, 6 s_grade | **RED** |

**New drops introduced by the flag: 0 `s_grade`, 0 `any_signal`.** The six red marks are the pre-existing ones; this row adds none.

## 5. Money -- the 2-year book

Both arms: `backtest_2y.py` shelled once per arm with the flag forced in the child's environment, same `data_archive/`. Win rate is of DECIDED trades (scratches excluded), the convention `research/a2_bt2y_summary.py` prints and this table imports. `months green` is months with positive total R; the durability gate is EVERY month green. The S subset is `sgrade == "S"` -- `research/downgrade.py`'s ladder as `backtest_2y.py` attaches it to every row after the fact, so it is the **same population in both arms** and not each arm's own idea of S.

| arm | population | signals | n traded | mean R | median R | win rate | months green | total R | error bar (wide / narrow) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `off` (== HEAD) | whole book | 45,193 | 1,017 | +0.9551 | +0.5660 | 53.2% | **23 / 25** | +971.4 | +-1.5799 (+-0.0095) |
| `off` (== HEAD) | S subset | 7,454 | 128 | +1.2829 | +1.1290 | 66.4% | **23 / 25** | +164.2 | +-1.2573 (+-0.0751) |
| `on` (downgrade grader) | whole book | 45,194 | 1,310 | +0.8304 | +0.2680 | 50.2% | **24 / 25** | +1087.8 | +-1.3205 (+-0.0035) |
| `on` (downgrade grader) | S subset | 7,453 | 202 | +0.9895 | +0.7470 | 59.4% | **21 / 25** | +199.9 | +-0.9251 (+-0.0225) |

| delta (`on` - `off`) | signals | n traded | mean R | median R | win rate | months green | total R |
|---|---:|---:|---:|---:|---:|---:|---:|
| whole book | +1 | +293 | **-0.1247** | -0.2980 | -3.0 pts | +1 | +116.4 |
| S subset | -1 | +74 | **-0.2934** | -0.3820 | -7.0 pts | -2 | +35.7 |

### The G13 sizing trap, checked on this arm

`backtest_week` sizes every trade at `RISK_DOLLARS / |entry - stop|`, so a row whose risk is under the engine's own floor has a 1R that is a position size nobody can take and an R that is a division by ~0. G13's arm was 73.3% such rows, 79 of them with `entry == stop` exactly, and its mean R of +14.72 was arithmetic rather than money. **The same test, `g13_floor_fix_ab.sizeable`, imported and run on this arm:**

| arm | traded | takeable | **untakeable** | of which `entry == stop` | max R in the book |
|---|---:|---:|---:|---:|---:|
| `off` (== HEAD) | 1,017 | 995 | **22 (2.2%)** | 0 | +14.3 |
| `on` (downgrade grader) | 1,310 | 1,255 | **55 (4.2%)** | 0 | +14.3 |

| arm | population | n | mean R | median R |
|---|---|---:|---:|---:|
| `off` | takeable | 995 | +0.9716 | +0.6000 |
| `off` | untakeable | 22 | +0.2127 | -1.0000 |
| `on` | takeable | 1,255 | +0.8427 | +0.3200 |
| `on` | untakeable | 55 | +0.5482 | -1.0000 |

**The trap does not fire on this arm** -- 0 rows with `entry == stop` in either arm, and the max R is +14.3 in both. The `on` arm's untakeable share is 4.2% against 2.2% on `off`, so unlike G13 the mean R below is money rather than arithmetic. **Takeable-only mean R, the uncontaminated read:** `off` +0.9716 (n=995), `on` +0.8427 (n=1,255) -- delta **-0.1289 R**.

### Which trades the flag swapped

Rows are matched across the arms on `(symbol, day, entry time, setup, direction, level)` -- detection is unchanged by the flag, so the same setup on the same bar is the same row (`g13_floor_fix_ab.row_key`). (Detection itself does not read the grade; the whole-signal count still moves by +1 because the no-repeat / idea bookkeeping is keyed on which signals were ACCEPTED, and a different grade changes that.) That key is not unique in every book: **0 `off` and 2 `on` traded rows collide on it** and are counted once here. The takeable-only means above are taken from the RAW traded list, never from this deduped view, so a collision cannot move a headline number.

| | count | of which takeable | mean R | median R | max R |
|---|---:|---:|---:|---:|---:|
| traded in BOTH arms | 958 | -- | +0.9847 | +0.6250 | -- |
| **lost** -- traded `off`, not `on` | 59 | 54 | +0.4745 | -1.0000 | +7.7 |
| **gained** -- traded `on`, not `off` | 350 | 312 | +0.3980 | -1.0000 | +10.6 |

What became of the lost trades in the `on` arm: `absent` 1, `fired/C` 19, `skipped_d/X` 1, `skipped_repeat_entry/C` 2, `skipped_tight_stop/C` 36.

**The matched population is the one place the flag could change price rather than membership, and it does not**: 958 rows traded by both arms, **1** with a different R. This flag moves MEMBERSHIP. Every R delta above is a different book, not the same book priced better.

### Does the delta clear its own error bar

T3 (`research/g3_onwatch_2y.md`, `47e60796`) established both bars and they are recomputed here on each arm's own book, never quoted: the WIDE bar reprices every ambiguous intrabar row to -1.0R; the NARROW floor reprices only rows whose stop is NOT the entry bar's own extreme. Both are one-directional -- the booked mean R is a **ceiling**, never a midpoint.

**The delta the verdict is taken on is the TAKEABLE-ONLY one.** G13's whole lesson is that an as-booked mean R can be moved by rows whose risk denominator is ~0, and a number cannot clear an error bar by breaking the quantity the bar is measured on.

| | |
|---|---|
| whole-book mean R delta, as booked | -0.1247 R (the `on` arm's untakeable share is 4.2%, against 2.2% on `off` -- this delta is not made of near-zero-risk rows) |
| **takeable-only mean R delta -- the defensible one** | **-0.1289 R** |
| WIDE bar, `off` arm | +-1.5799 R |
| does the defensible delta clear it? | **no -- 12x smaller** |
| NARROW floor, `off` arm | +-0.0095 R |
| does it clear THAT? | **yes, by 14x -- but only if a stop resting on the entry bar's own wick is ruled unreachable inside that bar, the one question Austin has not answered** |
| WIDE bar, `on` arm | +-1.3205 R |

**The defensible delta of -0.1289 R is INSIDE the `off` arm's wide bar of +-1.5799 R, so this rig does not resolve its sign.** The direction may be real; a 100-card holdout and a 2-year book cannot separate it from noise at this size.

**Neither arm passes the money gate and neither is durable.** The gate is mean R = 2.0 and EVERY month green. `off` books +0.9551 R with 23 of 25 months green; `on` books +0.8304 R with 24 of 25. The grader is not what stands between this book and the gate.

### Per symbol

Rows under `universe.MIN_SAMPLE_N` (=20) are MARKED `(low n)`, never dropped and never excluded from the whole-book totals above -- below ~20 trades one more trade swings the mean by the same order of magnitude as the money gate itself.

**22 of the 27 symbols traded by both arms move DOWN and 4 move up (over the 18 that clear MIN_SAMPLE_N in both arms: 15 down).** The whole-book delta is not one symbol; it is the same direction almost everywhere, which is what makes a delta smaller than the error bar worth reporting as a direction rather than discarding as noise.

| symbol | n `off` | mean R `off` | n `on` | mean R `on` | delta mean R |
|---|---:|---:|---:|---:|---:|
| COIN | 104 | +0.7468 | 138 | +0.8237 | +0.0769 |
| MU | 82 | +1.1982 | 101 | +1.1694 | -0.0288 |
| HOOD | 75 | +1.8421 | 93 | +1.5027 | -0.3394 |
| TSLA | 75 | +0.8187 | 92 | +0.5732 | -0.2455 |
| PLTR | 77 | +0.8192 | 84 | +0.7112 | -0.1080 |
| AMD | 69 | +0.8884 | 91 | +0.8006 | -0.0878 |
| IREN | 52 | +0.8645 | 71 | +0.7819 | -0.0826 |
| AVGO | 55 | +0.7998 | 67 | +0.7363 | -0.0635 |
| ORCL | 52 | +0.8962 | 62 | +1.0127 | +0.1165 |
| META | 42 | +1.0200 | 66 | +0.9076 | -0.1124 |
| NVDA | 48 | +0.7326 | 56 | +0.3515 | -0.3811 |
| AMZN | 33 | +0.5010 | 37 | +0.8068 | +0.3058 |
| MSFT | 29 | +0.5982 | 39 | +0.5351 | -0.0631 |
| INTC | 30 | +1.2219 | 37 | +0.9367 | -0.2852 |
| TSM | 27 | +0.7458 | 37 | +0.5305 | -0.2153 |
| NFLX | 30 | +0.8931 | 31 | +0.8320 | -0.0611 |
| GOOGL | 21 | +0.3646 | 37 | +0.2964 | -0.0682 |
| UBER | 26 | +1.2548 | 30 | +1.1023 | -0.1525 |
| CRM | 18 _(low n)_ | +1.3416 | 24 | +0.9975 | -0.3441 |
| AAPL | 19 _(low n)_ | +0.8597 | 23 | +0.7859 | -0.0738 |
| BABA | 16 _(low n)_ | +0.8820 | 24 | +0.9149 | +0.0329 |
| QQQ | 9 _(low n)_ | +0.7413 | 27 | +0.5011 | -0.2402 |
| SPCX | 15 _(low n)_ | +1.9390 | 16 _(low n)_ | +1.5594 | -0.3796 |
| SPY | 4 _(low n)_ | +0.7442 | 14 _(low n)_ | +0.1230 | -0.6212 |
| IWM | 5 _(low n)_ | +0.7316 | 8 _(low n)_ | +0.3070 | -0.4246 |
| ACHR | 2 _(low n)_ | +1.2790 | 3 _(low n)_ | +0.5193 | -0.7597 |

## 6. What this does not say

- **It does not ship the grader.** `ENABLE_DOWNGRADE_GRADER` stays `False` and `_grade_pa` is not deleted. R3 is Austin's call; flipping it changes what trades, and re-freezing the engine voids `research/omen6_forward.py`.
- **It does not say the eight variables are right.** `research/a1_threshold_sweep.md` (`99bead1c`) measured the grader itself as overfit: mix distance from Austin **0.086 on the 120 cards it was tuned against and 0.282 on the held-out 100**, A undercounted 3x, S-day recall 5/15, and `level_not_respected` **wrong-signed** (tripped +0.996R vs clean +0.892R) at a 63-68% trip rate. P15 tried three faithful reformulations and all three failed. This row measures the grader **as committed**; a better-calibrated version of it is a different experiment.
- **It does not resolve a mean-R delta inside the error bar.** T3's wide bar is +-1.5799 R on the `off` arm. A delta smaller than that is not a result in either direction, and this report says so above rather than quoting the sign.
- **It does not lift the HTF veto.** That is a separate, unowned rule (`research/g4_dropped_s.md` section 8) and it is applied identically in both arms, so the arm is a swap of the grader alone.
- **It does not fix arrival order.** G4's finding that outranks the drop table is that `_calibration_grade`'s first-with-trend floor, not the grader, is what promotes 95.3% of the traded book. A different grader changes which signal is *first*; it does not change that first is what gets taken.
- The held-out sample is 100 cards and 15 S days. A 3/15 -> 3/15 read has a wide interval of its own; what it can rule out is a LARGE out-of-sample recall change, not a small one.
- Every mean R here is a ceiling: each back-dated fill assumes the trigger beat the stop inside a minute nobody can see (T2 / `research/p26_intrabar_ambiguity.py`).

## 7. Reproduce

```bash
git stash push -- signal_runner.py           # HEAD control, before the flag
python backtest_2y.py --days 730 --out research/r3_arm_head.json
git stash pop
python research/test_downgrade_grader.py     # the assert-based check
python research/r3_downgrade_grader_ab.py --selfcheck
python research/r3_downgrade_grader_ab.py book --arm off
python research/r3_downgrade_grader_ab.py book --arm on
python research/r3_downgrade_grader_ab.py identical   # head == off, byte for byte
python research/r3_downgrade_grader_ab.py test1       # the 100 held-out cards
python research/r3_downgrade_grader_ab.py gate        # regression_gate, both arms
python research/r3_downgrade_grader_ab.py stats
python research/r3_downgrade_grader_ab.py report
```

The three books are ~40 MB each and are NOT committed, the same convention `research/g3_onwatch_2y.py` and `research/g13_floor_fix_ab.py` follow. `data_archive/` must be identical across all three runs; the `head` run's 45,193 / 1,017 is the check that it was.

## Provenance

Generated by `research/r3_downgrade_grader_ab.py report` at _this commit_ (`--selfcheck` green). Engine change: `signal_runner.py` (`ENABLE_DOWNGRADE_GRADER`, `DOWNGRADE_TIER`, `SignalRunner._grade_trade`, `SignalRunner._downgrade_grade`), default False. Assert-based check: `research/test_downgrade_grader.py`. Diagnosis it implements: `research/g4_dropped_s.md`. Grader measured: `research/downgrade.py`, at its committed constants, whose own held-out calibration is `research/a1_threshold_sweep.md` (`99bead1c`). Held-out scorer: `research/t70_test1_score.py` (`30fbc3f8`). A/B shell and the takeability test: `research/g13_floor_fix_ab.py` (`6d89513d`). Error bars: `research/g3_onwatch_2y.py` (`47e60796`), recomputed here. Sample floor: `universe.MIN_SAMPLE_N` = 20.

Books: `head` 2026-08-27T19:08:36, `off` 2026-08-27T19:13:56, `on` 2026-08-27T19:19:22. 0 symbol-day(s) could not be classified for the error bar (missing day) and 0 row(s) had no matching bar; both are excluded from the bar, never from the money.
