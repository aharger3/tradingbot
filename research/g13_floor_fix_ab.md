# G13 — G12's floor fix, priced

**G12's smallest fix recovers 5 of its 6 dropped S marks (`s_grade` **5 → 11**, all 75 detections kept) and CANNOT BE PRICED, because the book it produces is 73.3% untakeable.** With the flag on, 1,139 of the 1,553 traded rows have a stop distance below the very floor the fix moved — 79 of them with `entry == stop` EXACTLY — and the rig sizes 1R off that distance. Mean R +0.9551 → **+14.72** and 25/25 months green are arithmetic, not money.

The mechanism is one sentence. **The floor and the position size have to read the SAME number, and this fix makes them read different ones.** `backtest_week` sizes every trade at `RISK_DOLLARS / |entry - stop|` — the POST-fill distance. Move the floor onto the pre-fill distance and the two are no longer the same quantity, so the floor now admits exactly the rows whose sizing risk is smallest and rejects the rows whose sizing risk is largest. Measured, on the 2-year book: **1,107 of the 1,124 trades the fix ADDS are untakeable, and 584 of the 588 trades it REMOVES were takeable.**

On the 100 HELD-OUT OMEN Test 1 cards the fix buys **zero** S recall (3/15 both arms) and takes false fires on days Austin refused from **12/42 to 19/42**. So the +6 S marks are an in-sample result that does not reproduce out of sample.

**This does not say G12 was wrong.** G12's diagnosis is confirmed here line for line: all six marks are lifted out of `D`, on the same bars, by the same arithmetic. What it says is that the two-line version of the fix is HALF of it. G12's own sentence — *"the R denominator it is judged on should not shrink because the fill improved"* — is the other half, and moving the floor without moving the denominator is worse than moving neither.

Nothing here ships. `signal_runner.ENABLE_STRUCTURAL_RISK_FLOOR` defaults to **False**, `5e3677ea` is not reverted, and the engine is not re-frozen — that would VOID `research/omen6_forward.py` and it is Austin's call. Measured at _this commit_ by `research/g13_floor_fix_ab.py`.

## 1. What was implemented

G12's smallest fix, verbatim: *evaluate the minimum-risk floor on the structural geometry, not on the improved fill*. One flag, one function, two call sites.

| | |
|---|---|
| flag | `signal_runner.ENABLE_STRUCTURAL_RISK_FLOOR`, **default False**, `ENABLE_STRUCTURAL_RISK_FLOOR=1` to A/B |
| function | `signal_runner.floor_reference_risk()` |
| OFF | the floor reads `entry - stop` — the POST-fill risk, the same float `stock_risk` already is |
| ON | the floor reads `close - structural_stop` — the bar close against the stop the setup had BEFORE `fill_price()` moved the entry and `intrabar_stop()` reacted |
| unchanged either way | the price paid, the R denominator, `stop_width_pct`, and the selection score's `stock_risk / close` |
| call sites | `signal_runner.py` B&R long and B&R short, the two the floor lives at |

**The floor is not disabled and not widened.** A signal whose fill was never back-dated has `close == entry` and `structural_stop == stop`, so both arms read the identical number and the floor rejects it identically.

## 2. With the flag OFF the book is byte-identical to HEAD

The claim, checked rather than asserted: `backtest_2y.py` was run three times against the same `data_archive/` — once from **unmodified HEAD code before the flag existed**, then twice from the patched tree with the flag forced off and on in the child's environment. sha256 is taken over the `trades` array; `meta.generated` is a wall clock and is the one field excluded.

| run | code | signals | traded | sha256 of `trades` |
|---|---|---:|---:|---|
| `head` | unmodified HEAD | 45,193 | 1,017 | `1b70bb06994e3213725deeb5e856d502` |
| `off` | patched, `ENABLE_STRUCTURAL_RISK_FLOOR=0` | 45,193 | 1,017 | `1b70bb06994e3213725deeb5e856d502` |
| `on` | patched, `ENABLE_STRUCTURAL_RISK_FLOOR=1` | 45,192 | 1,553 | `e194d762bc58b02fc28ec822e32da2ab` |

**`head` and `off` are identical.** The flag-off engine is the flag-less engine — 45,193 signals and 1,017 traded rows, every field of every row equal. Reproduce with `python research/g13_floor_fix_ab.py identical`.

The `head` run is also a cross-check on the archive: 45,193 signals / 1,017 traded reproduces `research/g3_onwatch_2y.md`'s shipped arm exactly, so `data_archive/` has not moved under this measurement.

## 3. Recall — `research/regression_gate.py`, both arms

| arm | `any_signal` | `s_grade` | dropped vs baseline | gate |
|---|---:|---:|---|---|
| baseline (`research/baseline_3.8.json`) | 60 | 10 | — | — |
| `off` (== HEAD) | 75 | **5** | 0 any_signal, 6 s_grade | **RED** |
| `on` (structural floor) | 75 | **11** | 0 any_signal, 1 s_grade | **RED** |

**`s_grade` 5 → 11, not the 13 the ticket expected — and that gap is the finding.** 13 is G12's number for *reverting the fill*, which is a bigger change than *keeping the fill and moving the floor*. G12 said so in its own caveat and this is the A/B it asked for. Three arms, one measurement, at this commit:

| arm | what changes | `any_signal` | `s_grade` | S marks fired | X marks fired |
|---|---|---:|---:|---:|---:|
| HEAD | — | 75 | 5 | 5 / 77 | 2 / 22 |
| **structural floor** | the floor's denominator | 75 | **11** | 11 / 77 | 4 / 22 |
| revert the fill (`--ab-close-fill`) | every B&R entry price | 75 | 13 | 13 / 77 | 5 / 22 |

The structural floor buys 6 of the 8 S entries a full revert buys and costs 2 of its 3 extra X fires. It is the strictly smaller change, and it is priced like one.

### G12's six, one row each

`risk` is the POST-fill risk the floor reads today; `floor` is `max(0.10, 0.0015 × close)`; `tight thr` is `STOP_RANGE_MULT × avg_range`, the SECOND gate — `_min_viable_stop`, which only a `C` has to pass. Produced by `python research/g13_floor_fix_ab.py marks`.

| mark | bar | level | risk | floor | tight thr | off | on | recovered |
|---|---:|---|---:|---:|---:|---|---|---|
| `GOOGL\|2024-10-15\|32` | 32 | OR high | 0.1150 | 0.2502 | 0.1369 | X/skipped_d | **B/fired** | yes |
| `IWM\|2025-04-10\|16` | 16 | OR low | 0.1000 | 0.2757 | 0.4566 | X/skipped_d | **B/fired** | yes |
| `IWM\|2025-12-01\|11` | 12 | OR high | 0.2100 | 0.3695 | 0.2212 | X/skipped_d | **B/fired** | yes |
| `IWM\|2025-12-04\|56` | 58 | PDH | 0.1600 | 0.3758 | 0.2036 | X/skipped_d | **B/fired** | yes |
| `IWM\|2025-12-04\|56` | 58 | PMH | 0.1500 | 0.3758 | 0.2036 | X/skipped_d | **C/skipped_tight** | yes |
| `QQQ\|2025-02-25\|16` | 17 | OR low | 0.4900 | 0.7750 | 0.5633 | X/skipped_d | **C/skipped_tight** | **no** |
| `UBER\|2025-09-11\|15` | 15 | OR high | 0.1328 | 0.1427 | 0.2395 | X/skipped_d | **B/fired** | yes |

**All six are lifted out of `D`. Five then fire; one does not.** `QQQ|2025-02-25|16` is promoted `X` → `C` exactly as designed and is then killed by the other gate G12 named — `_min_viable_stop`, whose human-proof leg rejects a stop that sits inside one typical candle's range: risk **0.4900** against a threshold of **0.5633** (`STOP_RANGE_MULT` 0.75 × avg_range 0.7511). That is not the floor and the floor fix cannot reach it. The gate therefore stays RED after the fix, on 1 mark instead of 6.

`IWM|2025-12-04|56`'s PMH twin lands in the same place — promoted to `C` by the fix, then capped and skipped tight — but its PDH twin fires, so the mark is recovered.

## 4. Money — the 2-year book

Both arms: 2024-08-21 → 2026-08-21, 500 sessions, 28 symbols, `backtest_2y.py` shelled once per arm with the flag forced in the child's environment. Win rate is of DECIDED trades (scratches excluded), the convention `research/a2_bt2y_summary.py` prints and this table imports. `months green` is months with positive total R; the durability gate is EVERY month green. The S subset is `sgrade == "S"` — `research/downgrade.py`'s ladder, the same filter `research/g3_onwatch_2y.md` uses.

| arm | population | signals | n traded | mean R | median R | win rate | months green | total R | error bar (wide RETIRED / narrow CARRIED) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `off` (== HEAD) | whole book | 45,193 | 1,017 | +0.9551 | +0.5660 | 53.2% | **23 / 25** | +971.4 | ±1.5799 (±0.0095) |
| `off` (== HEAD) | S subset | 7,454 | 128 | +1.2829 | +1.1290 | 66.4% | **23 / 25** | +164.2 | ±1.2573 (±0.0751) |
| `on` (structural floor) | whole book | 45,192 | 1,553 | +14.7170 | +1.7080 | 59.1% | **25 / 25** | +22855.5 | ±14.0571 (±0.0062) |
| `on` (structural floor) | S subset | 7,454 | 330 | +32.0360 | +2.0370 | 65.7% | **25 / 25** | +10571.9 | ±31.5355 (±0.0291) |

| delta (`on` − `off`) | signals | n traded | mean R | median R | win rate | months green | total R |
|---|---:|---:|---:|---:|---:|---:|---:|
| whole book | -1 | +536 | **+13.7619** | +1.1420 | +5.9 pts | +2 | +21884.1 |
| S subset | +0 | +202 | **+30.7531** | +0.9080 | -0.7 pts | +2 | +10407.7 |

The `off` arm reproduces `research/g3_onwatch_2y.md`'s shipped arm to four decimal places on every column — n 1,017, mean R +0.9551, median +0.5660, 53.2%, 23/25, ±1.5799 (retired) / ±0.0095 (carried). The rig is the rig.

### Why the `on` row is not a number

A mean R of +14.72 against a MEDIAN of +1.7080 is not a book that got better; it is a book dividing by zero. `backtest_week` sizes every trade at `RISK_DOLLARS / |entry - stop|`, so as that distance goes to zero the row's R goes to infinity. Split each arm's traded book by whether it clears the engine's OWN floor on the geometry the rig sizes on:

| arm | traded | takeable | **untakeable** | of which `entry == stop` | max R in the book |
|---|---:|---:|---:|---:|---:|
| `off` (== HEAD) | 1,017 | 995 | **22 (2.2%)** | 0 | +14.3 |
| `on` (structural floor) | 1,553 | 414 | **1,139 (73.3%)** | 79 | +7099.8 |

| arm | population | n | mean R | median R | win rate |
|---|---|---:|---:|---:|---:|
| `off` | takeable | 995 | +0.9716 | +0.6000 | 53.7% |
| `off` | untakeable | 22 | +0.2127 | -1.0000 | 28.6% |
| `on` | takeable | 414 | +1.3038 | +0.8665 | 57.1% |
| `on` | untakeable | 1,139 | +19.5924 | +2.6470 | 59.9% |

The `off` arm's 22 untakeable rows are a 2dp-rounding artifact — the engine's floor reads the signal bar's CLOSE and the book stores the 2dp fill, so a handful land a cent under this proxy. The `on` arm's 1,139 are not an artifact: they are the class the floor exists to reject, readmitted.

### Which trades the flag swapped

Rows are matched across the arms on `(symbol, day, entry time, setup, direction, level)` — detection is unchanged by the flag, so the same setup on the same bar is the same row.

| | count | of which takeable |
|---|---:|---:|
| traded in BOTH arms | 429 | — |
| **lost** — traded `off`, not `on` | 588 | **584** |
| **gained** — traded `on`, not `off` | 1,124 | **17** |

**584 of 588 trades lost were takeable. 1,107 of 1,124 trades gained are not.** The swap is almost perfectly the wrong way round, and it is not random: the two risks are anti-correlated by construction. Where `fill_price` back-dates the entry and `intrabar_stop` then moves the stop to the entry bar's own extreme, the POST-fill distance is WIDER than the structural one, so the structural floor rejects a row the account could have sized. Where the fill is a squeeze onto the bar's extreme with the stop left on the level, the post-fill distance is NARROWER, so the structural floor admits a row the account cannot size.

What became of the 588 lost trades in the `on` arm: `skipped_d/X` 540, `skipped_tight_stop/C` 30, `fired/C` 15, `absent` 1, `skipped_repeat_entry/B` 1, `skipped_repeat_entry/C` 1. The 540 that go `skipped_d` are the structural floor rejecting them outright.

### The only matched comparison in this file

The 429 rows traded by BOTH arms are the one population where the flag changes price rather than membership. 7 of them have a different R.

| arm | n | mean R | median R | win rate | total R |
|---|---:|---:|---:|---:|---:|
| `off` | 429 | +1.2457 | +0.7760 | 55.5% | +534.4 |
| `on` | 429 | +1.4355 | +0.7760 | 55.5% | +615.8 |

**+0.1898 R on 429 matched trades, 7 of which actually moved.** That is the honest money delta this ticket can defend, and it clears the carried narrow error bar below by 20×. *(Retired framing: against the wide bar it was 74× smaller and this line said it did not clear. The wide bar was retired 2026-08-28.)*

### Does the delta clear its own error bar

T3 (`research/g3_onwatch_2y.md`, `47e60796`) established both bars and they are recomputed here on each arm's own book, never quoted: the WIDE bar reprices every ambiguous intrabar row to −1.0R; the NARROW floor reprices only rows whose stop is NOT the entry bar's own extreme. Both are one-directional — the booked mean R is a **ceiling**, never a midpoint.

**The NARROW bar is the one this verdict is taken against. The WIDE bar was RETIRED on 2026-08-28.** It existed only because nobody had ruled on whether a stop resting inside the entry bar could have fired before the back-dated fill. Austin ruled: a stop is triggered by a candle CLOSE and by nothing else, and the entry candle's own close counts — *"out on that same close"*. One bar has exactly one close, so the `intrabar_stop` class cannot have fired ahead of the fill and is not ambiguous. The wide rows below are kept so the retired verdict stays traceable; do not quote them as a live interval.

| | |
|---|---|
| whole-book mean R delta, as booked | +13.7619 R — **do not use** |
| S-subset mean R delta, as booked | +30.7531 R — **do not use** |
| matched-trade mean R delta (429 rows) | **+0.1898 R** |
| NARROW bar — CARRIED, `off` arm (== T3's ±0.0095) | ±0.0095 R |
| does the matched delta clear THAT? | **yes**, by 20× — a stop resting on the entry bar's own wick is ruled unreachable inside that bar: Austin, 2026-08-28, "out on that same close" |
| WIDE bar — RETIRED 2026-08-28, `off` arm (== T3's ±1.5799) | ±1.5799 R |
| did the matched delta clear it? | no — 8× smaller. **That bar is retired**; this row is kept so the old verdict stays traceable |
| WIDE bar, `on` arm | ±14.0571 R — itself contaminated |

**The as-booked delta of +13.7619 R is 9× LARGER than the `off` arm's wide bar and that means nothing**, because both the delta and the `on` arm's own bar (±14.0571 R) are made of the same untakeable rows. A number cannot clear an error bar by breaking the quantity the bar is measured on. The defensible delta is the matched one, **+0.1898 R**, and it CLEARS the carried narrow bar by 20×. It was inside the wide bar, which is retired.

**Neither arm passes the money gate and neither is durable.** The gate is mean R = 2.0 and EVERY month green. `off` books +0.9551 R with 23 of 25 months green. `on`'s 25/25 is not durability — it is 1,139 rows with a denominator near zero making every month positive. The floor fix is not what stands between this book and the gate.

### Per symbol

Rows under `universe.MIN_SAMPLE_N` (=20) are MARKED `(low n)`, never dropped and never excluded from the whole-book totals above — below ~20 trades one more trade swings the mean by the same order of magnitude as the money gate itself. Symbols whose traded count and mean R are both unchanged are omitted. **Every `on` column here carries the same contamination as the whole-book row: read it as which symbols the flag TOUCHES, not as what they earn.**

| symbol | n `off` | mean R `off` | n `on` | mean R `on` | **untakeable `on`** |
|---|---:|---:|---:|---:|---:|
| COIN | 104 | +0.7468 | 125 | +6.5523 | 80 |
| MU | 82 | +1.1982 | 116 | +14.5401 | 74 |
| TSLA | 75 | +0.8187 | 104 | +9.3577 | 74 |
| PLTR | 77 | +0.8192 | 99 | +10.0624 | 70 |
| HOOD | 75 | +1.8421 | 98 | +6.0630 | 67 |
| AVGO | 55 | +0.7998 | 83 | +5.1003 | 65 |
| AMD | 69 | +0.8884 | 90 | +85.1954 | 64 |
| ORCL | 52 | +0.8962 | 79 | +10.8658 | 58 |
| META | 42 | +1.0200 | 66 | +4.9506 | 50 |
| NVDA | 48 | +0.7326 | 66 | +8.5337 | 48 |
| NFLX | 30 | +0.8931 | 52 | +22.4897 | 44 |
| GOOGL | 21 | +0.3646 | 47 | +9.0727 | 42 |
| AMZN | 33 | +0.5010 | 52 | +13.0631 | 42 |
| BABA | 16 _(low n)_ | +0.8820 | 47 | +6.6064 | 41 |
| CRM | 18 _(low n)_ | +1.3416 | 42 | +14.1354 | 39 |
| UBER | 26 | +1.2548 | 44 | +5.6221 | 36 |
| MSFT | 29 | +0.5982 | 46 | +21.0738 | 36 |
| IREN | 52 | +0.8645 | 71 | +5.5393 | 33 |
| AAPL | 19 _(low n)_ | +0.8597 | 37 | +6.5513 | 33 |
| INTC | 30 | +1.2219 | 47 | +16.2795 | 28 |
| TSM | 27 | +0.7458 | 35 | +11.9019 | 24 |
| IWM | 5 _(low n)_ | +0.7316 | 25 | +14.9152 | 23 |
| QQQ | 9 _(low n)_ | +0.7413 | 19 _(low n)_ | +13.1447 | 17 |
| SOFI | 2 _(low n)_ | +0.3335 | 15 _(low n)_ | +41.0495 | 15 |
| MARA | — | — | 13 _(low n)_ | +2.6025 | 13 |
| ACHR | 2 _(low n)_ | +1.2790 | 10 _(low n)_ | +10.0507 | 10 |
| SPY | 4 _(low n)_ | +0.7442 | 9 _(low n)_ | +9.0430 | 8 |
| SPCX | 15 _(low n)_ | +1.9390 | 16 _(low n)_ | +17.4638 | 5 |

Every symbol's `on` mean R is inflated by its own untakeable rows; the last column is the honest one. The contamination is not concentrated in a corner of the universe — it lands on 28 of the 28 symbols traded.

## 5. The 100 held-out OMEN Test 1 cards

`research/marks/probe_omen_test1_2026-08-27.jsonl` — 15 S / 27 A / 16 C / 42 X, graded 2026-08-27, never shown to the engine and never fitted on. Scored by `research/t70_test1_score.py`'s own `score_all`, imported not reimplemented, once per arm. `grade_std: "none"` is his **X**: he looked at the day and refused it, so a fire there is a false fire, not an unlabelled day.

| metric | `off` (== HEAD) | `on` (structural floor) | Δ |
|---|---:|---:|---:|
| **S recall** — fires at all on an S day | 3/15 = 20% | 3/15 = 20% | +0 pts |
| S recall, in-universe | 2/12 = 17% | 2/12 = 17% | +0 pts |
| **false fire** on refused (X) days | 12/42 = 29% | 19/42 = 45% | +17 pts |
| false fire, in-universe | 11/37 = 30% | 18/37 = 49% | +19 pts |
| entry match ±2 bars (of the 58 graded) | 4/58 = 7% | 5/58 = 9% | +2 pts |
| day precision (of days it fired on) | 15/27 = 56% | 19/38 = 50% | -6 pts |

**S recall does not move at all: 3/15 in both arms.** Not one of the 12 days the flag switched on is a day he graded S. The in-sample gate's +6 S marks do not reproduce out of sample.

| his grade | days newly fired by the flag |
|---|---|
| **S** | 0 |
| **A** | 3 — COIN 2025-08-05, MSFT 2025-04-11, NVDA 2025-10-07 |
| **C** | 2 — MSFT 2025-05-19, NFLX 2026-03-24 |
| **X** | 7 — AMD 2025-09-16, AMZN 2025-02-11, AVGO 2025-01-17, GOOGL 2026-05-06, NVDA 2026-07-17, PLTR 2025-06-30, TSLA 2025-12-02 |
| (lost a fire) | 1 — AVGO 2025-01-14 (his A) |

So the fix broadens the engine on unseen days: **+4 tradeable days (S/A/C) and +7 refused days**, and day precision goes 15/27 = 56% → 19/38 = 50%. The engine was already more likely to fire on a day he refused than on a day he called S; this widens that.

**The flag is not one-directional, and that is worth knowing.** AVGO 2025-01-14 LOSES its fire. For a short, `intrabar_stop()` can move the stop to the entry bar's HIGH, which is further from the fill than the structural level is from the close — so on that bar the post-fill risk is WIDER than the structural risk and the structural floor is the stricter of the two. The fix rejects those, exactly as it accepts squeezes. It is a change of denominator, not a relaxation.

## 6. What this does not say

- **It does not ship the fix.** `ENABLE_STRUCTURAL_RISK_FLOOR` stays `False`. Flipping it changes what trades, and re-freezing the engine voids `research/omen6_forward.py` — Austin's call alone.
- **It does not revert `5e3677ea`.** The intrabar fill is Austin's own rule (*"those candles that move fast and close at high of day or low of day, i just want to try to not miss out"*) and is untouched.
- **It does not claim the matched money delta is large.** Since 2026-08-28 it clears the carried narrow bar by 20× and its sign is readable — but +0.1898 R on 429 rows, 7 of which moved, is not what stands between this book and a 2.0 R gate, and it bought zero held-out S recall. *(This bullet used to say the delta was smaller than the error bar on the number it is a delta of; that was the retired wide bar.)*
- **It does not turn the recall gate green.** One mark of the six is blocked by `_min_viable_stop`, a different gate with a different rule.
- **It does not say the structural floor is the wrong idea.** It says that moving the floor's denominator WITHOUT moving the sizing denominator is incoherent. A version that moves both — the floor, `stock_risk`, and the R denominator all onto the structural geometry, with `fill_price` improving only the price paid — is a different experiment and has not been run. G12's prose asks for that one; its two-line fix is not it.
- The takeable/untakeable split uses the stored 2dp `entry` where the engine's floor uses the signal bar's unrounded close. That costs the `off` arm 22 marginal rows out of 1,017 and cannot account for the `on` arm's 1,139.
- The held-out sample is 100 cards and 15 S days. A 3/15 → 3/15 read has a wide interval of its own; what it rules out is a LARGE out-of-sample S recall gain, not a small one.
- Every mean R here is a ceiling: each back-dated fill assumes the trigger beat the stop inside a minute nobody can see (T2 / `research/p26_intrabar_ambiguity.py`).

## 7. Reproduce

```bash
git stash                                   # HEAD control, before the flag
python backtest_2y.py --days 730 --out research/g13_arm_head.json
git stash pop
python research/g13_floor_fix_ab.py --selfcheck
python research/test_structural_floor.py    # the assert-based check
python research/g13_floor_fix_ab.py book --arm off
python research/g13_floor_fix_ab.py book --arm on
python research/g13_floor_fix_ab.py identical   # head == off, byte for byte
python research/g13_floor_fix_ab.py gate        # regression_gate, both arms
python research/g13_floor_fix_ab.py marks       # G12's six, bar by bar
python research/g13_floor_fix_ab.py test1       # the 100 held-out cards
python research/g13_floor_fix_ab.py stats
python research/g13_floor_fix_ab.py report
python research/g12_attribute.py --ab-close-fill   # the revert-the-fill bound
```

The three books are ~40 MB each and are NOT committed, the same convention `research/g3_onwatch_2y.py`'s arms follow. `data_archive/` must be identical across all three runs; the `head` run's 45,193 / 1,017 is the check that it was.

## Provenance

Generated by `research/g13_floor_fix_ab.py report` at _this commit_ (`--selfcheck` green). Engine change: `signal_runner.py` (`ENABLE_STRUCTURAL_RISK_FLOOR`, `floor_reference_risk`), default False. Assert-based check: `research/test_structural_floor.py`. Diagnosis it implements: `research/g12_recall_regression.md` (`df8e1c89`). Error bars: `research/g3_onwatch_2y.py` (`47e60796`), recomputed here. Held-out scorer: `research/t70_test1_score.py` (`30fbc3f8`). Sample floor: `universe.MIN_SAMPLE_N` = 20.

Books: `head` 2026-08-27T18:39:53, `off` 2026-08-27T18:45:21, `on` 2026-08-27T18:45:23 — all three against the same `data_archive/`, and the `head`/`off` sha256 match is the proof they saw the same tape. 0 symbol-day(s) could not be classified for the error bar (missing day) and 0 row(s) had no matching bar; both are excluded from the bar, never from the money.
