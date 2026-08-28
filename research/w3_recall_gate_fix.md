# W3 — the recall gate, green, on a book that is still takeable

**`python research/regression_gate.py` exits 0 with `ENABLE_MIN_RISK_FILL_CLAMP=1`, and the 2-year book it produces is 1.1% untakeable against HEAD's 2.2%.** The gate has been RED since `5e3677ea` (2026-08-11) — 16 days and 112 commits before anyone ran it. `s_grade` goes **5 → 13** on a 10-mark gate, all 76 detections kept, and none of the six marks G12 named is dropped any more.

**Held-out first, because that is the rule.** On the 100 HELD-OUT OMEN Test 1 cards S recall is **3/15 = 20% before and 3/15 = 20% after** — it does not fall, and it does not rise. False fires on days Austin refused go 12/42 = 29% → 21/42 = 50%. The in-sample recall gain does not reproduce out of sample, exactly as it failed to for the three arms A/B'd on 2026-08-27. Treat the +8 in-sample S marks as a gate result, not as evidence the engine sees more of what he sees.

The mechanism in one sentence. **G13 moved the floor and left the sizer behind; this moves the FILL and leaves both where they are.** The floor and `backtest_week`'s position size read the same `|entry - stop|` in both arms, so a book of clamped fills satisfies `|entry - stop| >= floor` BY CONSTRUCTION — the property g13 measured the absence of in 73.3%% of its rows. The clamped entry is never better than the back-dated fill and never worse than the bar's own close, so it is a price the bar traded through on its way to the level: a concession, not a windfall.

Nothing here ships. `signal_runner.ENABLE_MIN_RISK_FILL_CLAMP` defaults to **False**, `5e3677ea` is not reverted, `B&R_MIN_RISK` is not retuned, and the engine is not re-frozen — that would VOID `research/omen6_forward.py` and it is Austin's call. Measured at _this commit_ by `research/w3_recall_gate_fix_ab.py`.

## 1. What was implemented

| | |
|---|---|
| flag | `signal_runner.ENABLE_MIN_RISK_FILL_CLAMP`, **default False**, `ENABLE_MIN_RISK_FILL_CLAMP=1` to A/B |
| functions | `signal_runner.min_risk_floor()`, `signal_runner.clamp_fill_to_min_risk()` |
| OFF | `clamp_fill_to_min_risk` returns its `entry` argument unchanged — the same float in, the same float out |
| ON | long `entry := min(close, max(entry, stop + floor + tick))`; short `entry := max(close, min(entry, stop - floor - tick))` |
| unchanged either way | the floor's value, the floor's denominator, the R denominator, the sizer, `STOP_RANGE_MULT`, `fill_price`, `intrabar_stop` |
| call sites | `signal_runner.py` B&R long and B&R short, immediately AFTER `intrabar_stop()` and before `stock_risk` |

**The floor is neither disabled, widened, nor retuned.** `B&R_MIN_RISK = 0.0015 x close` is one of the 33 constants `research/hallucination-audit.md` classes UNMENTIONED — Austin never stated it, it is ours, and it is flagged HIGH. This ticket had licence to tune it and did not: lowering the multiplier admits precisely the rows the floor was written to reject, and *untakeable* would then be measured against a yardstick the change had moved. The clamp makes the engine OBEY the constant on the price it books instead of using it to delete setups. If Austin later says the constant is wrong, the clamp still holds — it reads whatever `min_risk_floor()` returns.

A signal whose fill was never back-dated already clears the floor, so the clamp is a no-op on it. The only rows this can touch are the ones `fill_price()` moved.

### Why the clamp runs AFTER `intrabar_stop()`, and what the other order costs

`intrabar_stop()` exists for the same wound — its docstring says *"223 of 744 B&R signals (30%) collapsed this way and were dropped by the minimum-risk gate"*. Its answer is to move the STOP to the entry bar's extreme; the clamp's answer is to move the FILL. Running the clamp LAST makes the two compose instead of compete, and buys the property this whole ticket rests on:

> **The clamp can only ever raise `|entry - stop|`, so `risk_on >= risk_off` on every signal and the minimum-risk floor can never newly reject one.** Checked, not asserted: of the 143 rows HEAD trades and this arm does not, **0** are `skipped_d` — the whole loss column is `skipped_tight_stop/C` 94, `fired/C` 36 and `skipped_repeat_entry` 13, every one of them a downstream SELECTION effect and none of them the gate this ticket touches.

Those 143 are worth naming rather than rounding away, because they are G4 §6's finding showing up again. A row logged `skipped_tight_stop/C` is a row that is now a `C`, and the only thing that demotes it is losing `_calibration_grade`'s first-with-trend-signal-of-the-day `B` floor to an EARLIER signal the clamp newly admitted. Arrival order, not the setup, is what moved — which is exactly the lever G14 is queued to A/B. Inferred from the logged status; not separately instrumented here.

Running the clamp FIRST is the other coherent design and it was built and measured. It restores an invariant `signal_runner.py` states in its own `NO_REPEAT_ENTRIES` comment — *"`sig["stop"]` IS the retested structural level for every setup"* — which `intrabar_stop` breaks, and which `idea_key`, the no-repeat scope and `spec0b_levels_check.py` all read. It is **variant B**, and it is not shipped. On W12's 8-candle fixture:

| | `stop` emitted | `entry` | risk |
|---|---:|---:|---:|
| HEAD | — (signal deleted, `skipped_d`) | 101.00 | 0.100 |
| **shipped: clamp after `intrabar_stop`** | 100.90 (bar low) | 101.06255 | 0.16255 |
| variant B: clamp before `intrabar_stop` | 101.00 = PDH | 101.16255 | 0.16255 |

Same risk either way; the ordering decides whether the stop is the broken level or the entry bar's wick, and whether the entry pays ten more cents for it.

**Why variant B lost.** It is not additive. Where the close sits too near the level for the clamp to reach the floor, variant B resolves to the close and the floor rejects the setup — whereas HEAD had already rescued that row by moving the stop to the wick. Measured on the same 2-year rig at this commit, by re-ordering the two lines and re-running every arm:

| | shipped (clamp last) | variant B (clamp first) |
|---|---:|---:|
| recall gate | GREEN, `s_grade` 13 | GREEN, `s_grade` 13 |
| held-out S recall | 3/15 | 3/15 |
| held-out false fires | 21/42 | 20/42 |
| n traded | 2,435 | 1,558 |
| untakeable | 1.1% | 1.7% |
| mean R | +0.9635 | +1.1061 |
| months green | 25 / 25 | 25 / 25 |
| **trades HEAD takes that it DROPS** | **143, 0 to the floor** | **588, of which 584 were takeable** |
| rows traded by BOTH arms | 874 | 429 |
| those rows' median R, HEAD -> arm | +0.6005 -> +0.6015 | +0.7870 -> **−1.0000** |
| those rows' win rate, HEAD -> arm | 53.4% -> 53.4% | 55.7% -> **49.8%** |

Variant B books a higher mean R and 25/25 months green, and it earns them by refusing 588 of HEAD's trades and by making the trades it keeps WORSE: on the 429 rows variant B and HEAD both take it pays a higher entry AND holds the tighter level stop, and the median outcome goes from +0.7870 R to a full stop-out. A mean R that rises while the median goes to −1.0 on identical rows is the failure mode this project has already hit three times (G13, G16, R9); it is not shipped for that reason. Reproduce it by swapping the two lines at `signal_runner.py` B&R long/short and re-running every arm.

**Austin's wick-stop rule is untouched either way.** `intrabar_stop` is not edited. In the shipped order it still fires exactly where it fires today; in variant B the clamp would leave it nothing to react to. Which answer he wants — the wick stop of `5e3677ea` or the structural level of SPEC0 — is a rules question, it is what `spec0b_levels_check.py` is really asking, and it is left to him.

`_FILL_CLAMP_TICK = 0.01` — the clamp lands one tick PAST the floor, not onto it, and both reasons are about a number being written down rather than about a rule.

1. **IEEE 754.** `(stop + floor) - stop` is not `floor`; it misses by ~6e-15, and two of the six marks (`UBER|2025-09-11|15`, `GOOGL|2024-10-15|32`) sit exactly on that edge. Clamping onto the floor recovers 4 of 6, not 6 of 6.
2. **The book stores entry and stop at 2 decimals.** A fill resting exactly ON the floor rounds to one that reads a cent under it, so every downstream reader — including §4's takeable/untakeable split, which reads the stored prices and not the engine's — scores a correctly-clamped row as unsizeable. Measured, before the tick was added: the same book read **32.5% untakeable**, with 773 of those 792 rows sitting at 0.95–1.00 of the floor and a median of 0.9931. That is a rounding boundary, not a class of rows; the tick removes it (`python research/w3_recall_gate_fix_ab.py stats`).

A cent is the smallest price the tape quotes, so the tick cannot decide anything the arithmetic did not already mean to pass, and it makes the clamped fill one tick WORSE, never better.

## 2. With the flag OFF the book is byte-identical to HEAD

`backtest_2y.py` run three times against the same `data_archive/`: once from **unmodified engine code before the flag existed**, then twice from the patched tree with the flag forced off and on in the child's environment. sha256 over the `trades` array; `meta.generated` is a wall clock and is the one field excluded.

The `head` control was taken at `f5ff006a`, this branch's base before W12's `c2c93280..02b4760d` landed under it. Those two engine edits are a docstring (`omen_bot.grade_trade`) and a branch W12 measured taking **0 of 853,010** evaluations (`research/downgrade.py::find_ocr`), so they are behaviour-neutral by their own measurement — and the `off` arm below, run at the rebased HEAD, reproducing that control byte for byte is the independent proof of it.

| run | code | signals | traded | sha256 of `trades` |
|---|---|---:|---:|---|
| `head` | unmodified engine, `f5ff006a` | 45,193 | 1,017 | `1b70bb06994e3213725deeb5e856d502` |
| `off` | patched, `ENABLE_MIN_RISK_FILL_CLAMP=0` | 45,193 | 1,017 | `1b70bb06994e3213725deeb5e856d502` |
| `on` | patched, `ENABLE_MIN_RISK_FILL_CLAMP=1` | 45,194 | 2,435 | `4bfecc4124195bdcbcd3894d2b89a815` |

**`head` and `off` are identical.** The flag-off engine is the flag-less engine — every field of every row equal. Reproduce with `python research/w3_recall_gate_fix_ab.py identical`.

## 3. Done criterion 1 — the recall gate

| arm | `any_signal` | `s_grade` | dropped vs baseline | gate |
|---|---:|---:|---|---|
| baseline (`research/baseline_3.8.json`) | 60 | 10 | — | — |
| `off` (== HEAD) | 75 | **5** | 0 any_signal, 6 s_grade | **RED** |
| `on` (fill clamp) | 76 | **13** | 0 any_signal, 0 s_grade | **GREEN** |

`python research/regression_gate.py` exits **0** with the flag on and **1** with it off.

Three answers to the same wound, one measurement each. G13's row is `research/g13_floor_fix_ab.md`; the close-fill revert is G12's `--ab-close-fill` upper bound.

| arm | what it moves | `any_signal` | `s_grade` | S marks fired | X marks fired | gate |
|---|---|---:|---:|---:|---:|---|
| HEAD | — | 75 | 5 | 5 / 77 | 2 / 22 | RED |
| G13 structural floor | the floor's denominator | 75 | 11 | 11 / 77 | 4 / 22 | RED (1 mark) |
| revert the fill (G12 `--ab-close-fill`) | every B&R entry price | 75 | 13 | 13 / 77 | 5 / 22 | — |
| **W3 fill clamp** | the price booked | 76 | **13** | 13 / 77 | 5 / 22 | **GREEN** |

The clamp lands on the same `s_grade 13` a full revert of the fill reaches, and on the same 5 X-tier fires — while KEEPING the fill rule, which is Austin's own (*"those candles that move fast and close at high of day or low of day, i just want to try to not miss out"*). It is not a smaller change than the revert on this gate; it is the same recall at a better price. The extra 3 X-tier fires are the cost and they are named, not averaged away.

## 4. Done criterion 2 — is the resulting book takeable

*Untakeable* is g13's definition, imported not restated (`research/g13_floor_fix_ab.py::sizeable`): a booked row whose `|entry - stop|` — the distance `backtest_week` divides by to size the trade — is below `max(0.10, 0.0015 x entry)`, the engine's own floor. Such a row's 1R is a position that does not exist and its R is a division by ~0. The yardstick is HEAD's floor constant in both arms; this ticket does not move it, which is what makes the comparison mean anything.

| arm | traded | takeable | **untakeable** | of which `entry == stop` | max R in the book |
|---|---:|---:|---:|---:|---:|
| `off` (== HEAD) | 1,017 | 995 | **22 (2.2%)** | 0 | +14.3 |
| `on` (fill clamp) | 2,435 | 2,408 | **27 (1.1%)** | 0 | +19.9 |
| G13 `on` (structural floor) | 1,553 | 414 | **1,139 (73.3%)** | 79 | +7,099.8 |

**1.1% against the <5% target, and against G13's 73.3%.** The residual is HEAD's own 2dp-rounding artifact, not a class of readmitted rows: the engine's floor reads the signal bar's unrounded close and the book stores a 2dp fill, so a handful of rows land a cent under this proxy in BOTH arms.

| arm | population | signals | n traded | mean R | median R | win rate | months green | total R |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `off` (== HEAD) | whole book | 45,193 | 1,017 | +0.9551 | +0.5660 | 53.2% | 23 / 25 | +971.4 |
| `off` (== HEAD) | S subset | 7,454 | 128 | +1.2829 | +1.1290 | 66.4% | 23 / 25 | +164.2 |
| `on` (fill clamp) | whole book | 45,194 | 2,435 | +0.9635 | +0.5120 | 55.1% | 25 / 25 | +2346.2 |
| `on` (fill clamp) | S subset | 7,454 | 419 | +1.0822 | +0.6820 | 61.5% | 23 / 25 | +453.4 |

Win rate is of DECIDED trades (scratches excluded), the convention `research/a2_bt2y_summary.py` prints. `months green` is months with positive total R; the durability gate is EVERY month green. The S subset is `sgrade == "S"`, `research/downgrade.py`'s ladder.

### The matched comparison

Rows are matched across arms on `(symbol, day, entry time, setup, direction, level)`. Detection is unchanged by the flag, so the same setup on the same bar is the same row.

| | count | of which takeable |
|---|---:|---:|
| traded in BOTH arms | 874 | — |
| **lost** — traded `off`, not `on` | 143 | 139 |
| **gained** — traded `on`, not `off` | 1,561 | 1,550 |

| arm | n | mean R | median R | win rate | total R |
|---|---:|---:|---:|---:|---:|
| `off` | 874 | +0.9934 | +0.6005 | 53.4% | +868.3 |
| `on` | 874 | +1.0013 | +0.6015 | 53.4% | +875.1 |

**+0.0079 R on 874 matched trades, 36 of which actually moved.** That is the money delta this ticket can defend, and it is **too small to read**: the narrow error bar, recomputed on each arm's own book and never quoted, is ±0.0095 R, and the delta is 0.8× that — it does not clear the bar, so its SIGN is not established. The bar is narrow because Austin settled the question it existed for on 2026-08-28: a stop is triggered by a candle CLOSE and by nothing else, and the entry candle's own close counts — one bar has one close, so a stop cannot fire inside the entry bar ahead of the back-dated fill. The WIDE bar (±1.5799 R) is **RETIRED** and is not quoted here as a live interval.

What became of the lost trades in the `on` arm: `fired/C` 36, `skipped_repeat_entry/B` 2, `skipped_repeat_entry/C` 11, `skipped_tight_stop/C` 94.

**Neither arm passes the money gate.** The gate is mean R = 2.0 with EVERY month green. `off` books +0.9551 R with 23 of 25 months green; `on` books +0.9635 R with 25 of 25. The fill clamp is a RECALL fix, and it is not what stands between this book and the money gate.

## 5. Done criterion 3 — the 100 held-out OMEN Test 1 cards

`research/marks/probe_omen_test1_2026-08-27.jsonl` — 15 S / 27 A / 16 C / 42 X, graded 2026-08-27, never shown to the engine and never fitted on. Scored by `research/t70_test1_score.py`'s own `score_all`, imported not reimplemented, once per arm. `grade_std: "none"` is his **X**: he looked at the day and refused it, so a fire there is a false fire.

| metric | `off` (== HEAD) | `on` (fill clamp) | Δ |
|---|---:|---:|---:|
| **S recall** — fires at all on an S day | 3/15 = 20% | 3/15 = 20% | +0 pts |
| S recall, in-universe | 2/12 = 17% | 2/12 = 17% | +0 pts |
| **false fire** on refused (X) days | 12/42 = 29% | 21/42 = 50% | +21 pts |
| false fire, in-universe | 11/37 = 30% | 19/37 = 51% | +22 pts |
| entry match ±2 bars (of the graded) | 4/58 = 7% | 6/58 = 10% | +3 pts |
| day precision (of days it fired on) | 15/27 = 56% | 21/42 = 50% | -6 pts |

**S recall 3/15 = 20% in both arms — criterion 3 is met by not falling, and it buys nothing.** None of the days the clamp newly fires on is a day he graded S. This is the fourth arm in two days to buy in-sample S recall and exactly zero held-out S recall; two of the other three are `research/g13_floor_fix_ab.md` §5 and `research/r3_downgrade_grader_ab.md`, and the third is G16's `ENABLE_STRUCTURAL_RISK`.

| his grade | days newly fired by the flag |
|---|---|
| **S** | 0 |
| **A** | 3 — COIN 2025-08-05, MSFT 2025-04-11, NVDA 2025-10-07 |
| **C** | 3 — AVGO 2026-06-30, MSFT 2025-05-19, NFLX 2026-03-24 |
| **X** | 9 — AMD 2025-09-16, AMZN 2025-02-11, AVGO 2025-01-17, AVGO 2025-04-25, GOOGL 2026-05-06, IWM 2026-06-09, NVDA 2026-07-17, PLTR 2025-06-30, TSLA 2025-12-02 |
| (lost a fire) | 0 |

The engine was already more likely to fire on a day he refused than on a day he called S. This widens that.

## 5b. `spec0b_levels_check.py` — the cheapest reproduction, and the half of it that is not this mechanism

W12's bug sweep (`research/w12_bug_sweep.md`, finding 7) found `spec0b_levels_check.py` red at HEAD and diagnosed the cause as this ticket's mechanism, reproduced on **8 synthetic candles** rather than a corpus run. That diagnosis is CONFIRMED, and the check is also carrying a second, independent defect that is not this mechanism. Both are named here rather than adjusted away.

| | `python spec0b_levels_check.py`, line 44 |
|---|---|
| HEAD (flag off) | RED — `AssertionError: PDH B&R missing: []`. The signal does not exist. |
| `ENABLE_MIN_RISK_FILL_CLAMP=1` (shipped) | the signal EXISTS — `entry 101.06255, stop 100.9, grade B`. Still red, now on `stop == 101.0`. |
| `ENABLE_MIN_RISK_FILL_CLAMP=1`, variant B ordering | GREEN — `PDH B&R fires: entry 101.16255, stop 101.0, grade B` |

The fixture's retest bar closes at 101.70, inside 25% of its own high, so `fill_price` back-dates the entry onto PDH 101.00 — which IS the stop. Risk collapses to 0.10 against a floor of 0.15255 and the signal is force-graded `D`. Same arithmetic as the six marks, on eight candles. **The clamp fixes that half: the signal comes back, graded B, with risk 0.16255.**

**What is left is a different rule, and the check is right to still be red about it.** `assert pdh_sigs[0]["stop"] == 101.0` says a B&R's stop is the broken level — which is what `BNR_STOP_MODE = "level"` and `signal_runner.py`'s own `NO_REPEAT_ENTRIES` comment both say. `intrabar_stop` (`5e3677ea`) moves it to the entry bar's wick, on Austin's five recovered quotes. Those two rules disagree, they disagreed before this ticket, and only the variant B ordering — which costs 588 of HEAD's trades and turns the matched median into a stop-out — resolves it in SPEC0's favour. **That is a rules question for Austin, not a bug to patch and not a test to adjust.**

The check does not reach its HTF assertions under either ordering except variant B, where it then dies at `:60` asserting that `HTF_BIAS_VETO` defaults OFF. It does not — it has read `os.getenv("HTF_BIAS_VETO", "1")` since it was introduced and gates 47.0% of the 2-year book. W12 established that (finding 5) and fixed the four artefacts that misreported it; the stale assertion belongs to that finding and to R6 (*the veto has no author*), not to W3.

## 6. The verdict against the three done criteria

| # | criterion | result |
|---:|---|---|
| 1 | `python research/regression_gate.py` exits 0 | **PASS** |
| 2 | under 5% untakeable rows, g13's definition | **PASS** — 1.1% |
| 3 | held-out S recall does not fall | **PASS** — 3/15 = 20% → 3/15 = 20% |

All three are met. **What is NOT claimed:** that the engine now sees more of what Austin sees. Held-out S recall is flat at 3/15 = 20% and false fires rose +9 on his refused days, so the honest summary is that the clamp removes a self-inflicted recall bug without improving the engine's eye. The gate is green because the six marks it was written to protect are back, not because detection got better.

## 7. What this does not say

- **It does not ship.** `ENABLE_MIN_RISK_FILL_CLAMP` stays `False`. Flipping it changes what trades, and re-freezing the engine voids `research/omen6_forward.py` — Austin's call alone.
- **It does not revert `5e3677ea`** and does not touch `fill_price()` or `intrabar_stop()`. The intrabar fill is Austin's own rule.
- **It does not retune `B&R_MIN_RISK` or `STOP_RANGE_MULT`.** Both are UNMENTIONED constants in `research/hallucination-audit.md` and both are still open questions; this fix simply does not need them moved. `STOP_RANGE_MULT`'s second gate — the one that killed `QQQ|2025-02-25|16` under G13 — is cleared here because a clamped fill carries floor-sized risk, which on that bar is 0.7750 against a threshold of 0.5633.
- **It does not claim the money delta is large.** +0.0079 R on 874 matched rows, against a narrow bar of ±0.0095 R, is not a claim about the money gate — which neither arm passes.
- **It does not buy held-out recall.** See §5. A 3/15 → 3/15 read rules out a LARGE out-of-sample gain, not a small one; the held-out sample is 15 S days.
- **It does not say G12 or G13 was wrong.** G12's diagnosis is confirmed line for line and G13's warning — that the floor and the sizer must read one number — is the constraint this design was built to satisfy.
- Every mean R here is a ceiling: each back-dated fill assumes the trigger beat the stop inside a minute nobody can see (`research/p26_intrabar_ambiguity.py`).

## 8. Reproduce

```bash
python research/w3_recall_gate_fix_ab.py --selfcheck
python research/test_fill_clamp.py
python spec0b_levels_check.py                  # red at HEAD (W12 finding 7)
ENABLE_MIN_RISK_FILL_CLAMP=1 python spec0b_levels_check.py   # line 44 green
git stash                                  # HEAD control, before the flag
python backtest_2y.py --days 730 --out research/w3_arm_head.json
git stash pop
python research/w3_recall_gate_fix_ab.py book --arm off
python research/w3_recall_gate_fix_ab.py book --arm on
python research/w3_recall_gate_fix_ab.py identical   # head == off, byte for byte
python research/w3_recall_gate_fix_ab.py gate
python research/w3_recall_gate_fix_ab.py marks
python research/w3_recall_gate_fix_ab.py test1
python research/w3_recall_gate_fix_ab.py stats
python research/w3_recall_gate_fix_ab.py report
ENABLE_MIN_RISK_FILL_CLAMP=1 python research/regression_gate.py
```

The three books are ~40 MB each and are NOT committed, the convention `research/g3_onwatch_2y.py`'s arms follow. `data_archive/` must be identical across all three runs; the `head`/`off` sha256 match is the proof it was.

## Provenance

Generated by `research/w3_recall_gate_fix_ab.py report` at _this commit_ (`--selfcheck` green). Engine change: `signal_runner.py` (`ENABLE_MIN_RISK_FILL_CLAMP`, `min_risk_floor`, `clamp_fill_to_min_risk`), default False. Assert-based check: `research/test_fill_clamp.py`. Diagnosis it implements: `research/g12_recall_regression.md`. Prior arms it is measured against: `research/g13_floor_fix_ab.md` (structural floor) and G16's `ENABLE_STRUCTURAL_RISK` (structural floor + structural R denominator, not in `main`). Every measurement function is imported from `research/g13_floor_fix_ab.py` and rebound onto this flag by `_rebind()`; none is reimplemented. Held-out scorer: `research/t70_test1_score.py`. Books: `off` 2026-08-28T03:38:58, `on` 2026-08-28T04:01:43.
