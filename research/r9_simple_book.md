# R9 / A4 — `flat_2r` as its own book, and what the fill is worth

**A flat 2R exit is a real book and it is not the shipped one: 1017 trades, mean +0.6997 R, 24 of 25 months green — it fails the 2.0R money gate by 1.3003 R and fails durability, and it books 0.2554 R LESS than the incumbent ladder on the identical entry set.** Its one genuine advantage is the one Austin asked about: it reaches 2R on **57.2%** of trades where the shipped ladder only KEEPS 2R on 29.3%.

**The intrabar fill does NOT raise P(2R). It halves it.** Take the 175 signals the extra intrabar-fill class can actually reach — the closest this engine gets to "enter as the candle is forming" — and hold the denominator fixed. Filled at the close they reach 2R **36.00%** of the time. Back-dated into the still-forming candle, **14.29%**. The 62.50% you get by scoring only the 40 that survive is survivorship: **135 of the 175 never reach the traded book at all**, because the earlier fill puts them on or through their own stop. And on the survivors the earlier fill shrinks the risk unit to a median 63% of its close-fill value, so "2R" is a 37% smaller price move — the goalposts move with the metric.

That sends the question back to entry SELECTION, which is where `research/g7_exit_sweep.md` (eight exit policies, none beat the ladder) and the G4/G9 line already pointed. **The exit was not the constraint and neither is the fill.**

Read-only. No default changed, no flag added, no bar fetched — both books were replayed by `research/g3_onwatch_2y.py` and are re-read here.

## The two fill arms, named for what they do

There is **no close-fill arm in this engine** and this file does not pretend to one. `research/g3_onwatch_2y.md` (T3) settled it: `signal_runner.fill_price` back-dates a fill on EITHER of two predicates, and `ON_WATCH` gates only one of them, at 2 of that function's 10 call sites. Turning the flag off still leaves 74.7% of traded fills intrabar. So the arms are named for what they do:

| arm | what back-dates a fill | flag | traded | intrabar fills | of traded |
|---|---|---|---:|---:|---:|
| **A** — bar-extreme back-dating only | `bar_extreme_veto` only | `ON_WATCH=0` | 1,091 | 815 | 74.7% |
| **B** — + session-extreme back-dating | `bar_extreme_veto` **plus** break-and-retest bars closing jammed against the session extreme | `ON_WATCH=1, shipped` | 1,017 | 913 | 89.8% |

**B is A plus one extra class of intrabar fill, and that class is the whole experiment.** 90 rows of arm B's 1,017 traded (175 of arm A's 1,091) have `near_session_extreme` as the ONLY predicate that could have moved their price — those are the rows where B fills at the level and A fills at the close. Everything else fills identically in both arms. So B−A is a test of MORE intrabar fill against LESS, never of intrabar against close, and a delta measured across the whole book is diluted by every row the two arms agree on.

## Deliverable 1 — `flat_2r` as a standalone book

The shipped fill arm (**B**), the shipped 11:00 ET force-flat (`exit_lab.CLOCK_BAR = 90`), the shipped close-triggered stop floored at −1.25R (`exit_lab.MAX_LOSS_R`). 100% of the position out at +2.0R, nothing else: no tranches, no trail, no break-even move, no HOD rule. `research/g7_exit_sweep.md` already showed the no-clock arm is worse for every trailing policy and worth +0.000 R to `flat_2r` itself, so only the clock arm is carried here.

Win rate is of DECIDED trades (R = 0 scratches excluded), the convention `research/a2_bt2y_summary.py::book` prints. The incumbent row is `backtest_2y.py`'s own ladder-B result on the identical entry set — same entries, same stops, same sides, only the exit differs.

| book | n | mean R | median R | win rate | total R | months green | worst month |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`flat_2r`** (this ticket) | 1,017 | **+0.6997** | +2.0000 | 59.9% | +711.6 | **24 / 25** | 2025-06 -0.7 |
| incumbent ladder B (shipped) | 1,017 | +0.9551 | +0.5660 | 53.4% | +971.4 | **23 / 25** | 2025-06 -5.6 |
| **gate** | — | **≥ +2.0000** | — | — | — | **25 / 25** | > 0 |

**It fails both gates, and it fails the money gate by more than the ladder does.** Mean R is +0.6997 against a gate of +2.0000 — short by 1.3003 R, where the ladder is short by 1.0449 R. Durability needs EVERY month green and `flat_2r` delivers 24 of 25; the ladder delivers 23 of 25. The trade `flat_2r` makes is 6.5 points of win rate for -0.2554 R of mean R, which is the same trade every fixed target in `research/g7_exit_sweep.md` makes and the same one it loses.

### Per pool

`universe.pool_for`, imported. `index` is QQQ/SPY/IWM, `equity` is the MAJOR_15, `other` is the rest of the 28-symbol replay. Rows under `universe.MIN_SAMPLE_N` (20) are marked thin — marked, not dropped, and still inside every whole-book total above.

| pool | n | mean R `flat_2r` | mean R ladder | delta | win rate | months green | P(2R) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `index` _(thin)_ | 18 | +1.1938 | +0.7393 | +0.4545 | 77.8% | 8 / 10 | 61.1% |
| `equity` | 624 | +0.6968 | +0.9000 | -0.2032 | 59.9% | 24 / 25 | 56.7% |
| `other` | 375 | +0.6808 | +1.0572 | -0.3764 | 58.9% | 23 / 25 | 57.9% |

### Per grade

| Austin grade | n | mean R `flat_2r` | mean R ladder | delta | P(2R) |
|---|---:|---:|---:|---:|---:|
| S | 128 | +0.9768 | +1.2829 | -0.3061 | 66.4% |
| A | 251 | +0.6450 | +0.9956 | -0.3505 | 55.8% |
| C | 638 | +0.6656 | +0.8735 | -0.2079 | 56.0% |

## Deliverable 2 — P(2R), four ways

**The metric.** `flat_2r`'s row is the PATH rate: the 2R target trades before a close beyond the stop. It is a property of entry, stop and tape, so it is what ANY exit has available to it. The ladder's row is the BOOKED rate: ladder B actually finishes at ≥ +2.0R. The gap between them is what the shipped exit gives back after 2R has already printed.

**The error bar is inline and it is one-directional.** An ambiguous row is an intrabar fill whose entry bar also contains the trade's stop; OHLCV cannot say which traded first and the engine assumes fill-then-stop every time. Priced the other way the trade never happened, so it reached nothing — every deduction strikes hits and none adds any. Wide strikes the whole ambiguous class; narrow strikes only rows whose stop is not the entry bar's own extreme (T3: 2 rows of 913 on the shipped arm). **These are ceilings, not midpoints.**

| policy | fill arm | n | **P(2R)** | error bar (wide / narrow) | P(2R) at the wide floor | mean R | mean R error bar |
|---|---|---:|---:|---:|---:|---:|---:|
| `flat_2r` | **A** bar-extreme back-dating only | 1,091 | **53.80%** | ∓38.96 pts / ∓0.18 pts | 14.85% | +0.5893 | ∓1.2028 / ∓0.0055 |
| `flat_2r` | **B** + session-extreme back-dating (shipped) | 1,017 | **57.23%** | ∓45.82 pts / ∓0.20 pts | 11.41% | +0.6997 | ∓1.4137 / ∓0.0059 |
| incumbent ladder B | **A** bar-extreme back-dating only | 1,091 | **25.94%** | ∓20.35 pts / ∓0.18 pts | 5.59% | +0.8416 | ∓1.3388 / ∓0.0088 |
| incumbent ladder B | **B** + session-extreme back-dating (shipped) | 1,017 | **29.30%** | ∓24.48 pts / ∓0.20 pts | 4.82% | +0.9551 | ∓1.5799 / ∓0.0095 |

| delta (B − A), each arm's own book | P(2R) | vs the WIDE bar (carried) | vs the NARROW floor |
|---|---:|---|---|
| `flat_2r` (path) | **+3.42 pts** | **inside it** — the bar is 13× larger, so this is unresolved | **clears it** — 17.4× the bar |
| incumbent ladder B (booked) | **+3.36 pts** | **inside it** — the bar is 7× larger, so this is unresolved | **clears it** — 17.1× the bar |

**Both bars are reported and the split is the same one T3 hit.** The wide bar strikes the `intrabar_stop` class, which is manufactured by a stop rule rather than found in the tape — but manufactured is not resolved, and whether a stop resting on the entry bar's own wick is reachable inside that bar is **Austin's call and he has not made it**. Against the wide bar this delta is noise; against the narrow floor it clears. Neither answers the ticket, because both are computed on **each arm's own book** and those are different sets of trades. The next table removes that.

### First correction — the same trade in both arms

Everything above compares each arm's own book, and those are **not the same trades**. Arm B's traded book is 74 rows smaller than arm A's, and the missing rows are not random: a fill back-dated to the level lands on or through the level-stop, so the trade is re-stopped on its own entry bar by `signal_runner.intrabar_stop` or dropped by the minimum-risk gate. **The trades the intrabar fill kills never appear in arm B at all.** That is survivorship, and it runs in the direction that FLATTERS arm B — so a whole-book delta cannot separate "the fill is better" from "the losers were deleted".

So the two books are joined on `(sym, day, entry_i, side, setup)` and the delta is taken only where the SAME trade exists in both arms:

| set | pairs | P(2R) arm A | P(2R) arm B | **delta** | mean R A | mean R B | delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| all matched pairs | 953 | 56.1% | 57.3% | **+1.15 pts** | +0.6691 | +0.7041 | +0.0350 |
| **of those, the fill actually MOVED** — B fills at the level, A at the close | 39 | 35.9% | 64.1% | **+28.21 pts** | +0.0343 | +0.8894 | +0.8551 |
| of those, entry and stop identical — must agree exactly | 914 | 57.0% | 57.0% | **+0.00 pts** | +0.6962 | +0.6962 | +0.0000 |

The bottom row is the control and it is why the rest can be believed: 914 pairs whose entry and stop are identical in both arms must replay identically, and `--selfcheck` asserts they do — same P(2R), same mean R, to 1e-9. Any drift there would mean the two books disagree about the tape rather than about the fill.

**The middle row looks like Austin is right, and it is the wrong number.** +28.21 points of P(2R) and +0.8551 R, on 39 pairs. It is wrong for a reason that is visible from the join itself: **matching on trades that exist in BOTH arms still conditions on surviving arm B.** The pair only exists because the back-dated fill did not kill the trade. That is the same survivorship, one level down.

### The fixed candidate set — the only view that is not survivorship

So the denominator is nailed down. The candidate set is **every one of arm A's 175 signals where `near_session_extreme` is the only predicate that could move the price** — the complete population the extra intrabar-fill class can reach, filled at the close in A and back-dated to the level in B. Both arms are then scored over that SAME 175, and a candidate arm B never traded counts as a non-hit rather than disappearing: **it did not become a better trade, it stopped being a trade.** The back-dated fill landed on or through its own level-stop and `signal_runner.intrabar_stop` or the minimum-risk gate removed it.

| view | denominator | 2R hits | **P(2R)** | vs arm A |
|---|---:|---:|---:|---:|
| **A** — filled at the close | 175 | 63 | **36.00%** | — |
| **B** — back-dated into the forming candle, **intention-to-treat** | 175 | 25 | **14.29%** | **-21.71 pts** |
| _B, survivors only (per-protocol)_ | 40 | 25 | _62.50%_ | _+27.50 pts_ |
| _A, on those same survivors_ | 40 | 14 | _35.00%_ | _—_ |

**135 of the 175 candidates — 77% — never reach arm B's traded book at all.** Held to the fixed denominator, back-dating the fill takes P(2R) from **36.00% to 14.29%**: it does not raise the odds of reaching 2R, it **more than halves them**. The 62.50% per-protocol figure is what you get by scoring only the 40 that lived.

And the trades it removes are not disasters it saved you from. Under the close fill those 135 killed candidates book a mean **-0.0058 R** under `flat_2r` — roughly flat. The earlier fill does not cut a tail off the book; it converts 77% of a break-even population into no-trades and keeps the 40 that were already working.

**There is a second reason the per-protocol number cannot be read as an edge, and it is arithmetic.** R is denominated in `|entry − stop|`, and back-dating the entry to the level shrinks exactly that. On the 39 surviving moved pairs arm B's risk unit is a **median 63% of arm A's** (mean 69%; smaller in 33 of 39). So arm B's 2R target sits about **37% nearer in price** than arm A's on the same trade. A nearer target is hit more often whether or not the fill was better — the goalposts moved with the metric.

For completeness, the un-matched view — each arm's own rows where `near_session_extreme` is the ONLY predicate that could have moved the price. **This is the table survivorship ruins**, kept only so the size of that ruin is visible:

| arm | rows where session-extreme is the only trigger | P(2R) path | mean R `flat_2r` | mean R ladder |
|---|---:|---:|---:|---:|
| **A** — bar-extreme back-dating only | 175 | 36.0% | -0.0040 | +0.2323 |
| **B** — + session-extreme back-dating | 90 | 60.0% | +0.7431 | +1.0881 |

That reads as +24.0 points of P(2R) and it is **an artefact**: arm A's 175 rows include every trade the back-dated fill would have killed, and arm B's 90 do not. The fixed-denominator table above is the same question with those rows held in place, and it answers -21.71 points.

## Which names do not fit a flat 2R exit

Austin's roster: `universe.CORE_SYMBOLS` + `universe.INDEX_POOL`, imported — 12 names (QQQ is in both). The shipped fill arm. **The rule is stated before the numbers: a name FITS if swapping the incumbent ladder for `flat_2r` does not lose money on it — `delta = mean R flat_2r − mean R ladder ≥ 0`.** That is the actual decision the ticket is about; P(2R) is shown beside it as the mechanism, not as the test. Rows under `universe.MIN_SAMPLE_N` (20) are marked **thin** and are excluded from the verdict — they are shown, not dropped, and they remain in every whole-book total above.

| symbol | pool | n | **P(2R)** | error bar | mean R `flat_2r` | mean R ladder | delta | months green | verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **AAPL** | equity | 19 | 68.4% | ∓63.2 pts | +1.2265 | +0.8597 | +0.3668 | 13 / 15 | **thin** — n < 20, no verdict |
| **AMD** | equity | 69 | 56.5% | ∓47.8 pts | +0.7550 | +0.8884 | -0.1335 | 19 / 25 | **does NOT fit** |
| **AMZN** | equity | 33 | 42.4% | ∓33.3 pts | +0.3863 | +0.5010 | -0.1147 | 11 / 18 | **does NOT fit** |
| **GOOGL** | equity | 21 | 57.1% | ∓42.9 pts | +0.6909 | +0.3646 | +0.3263 | 10 / 14 | fits |
| **IWM** | index | 5 | 60.0% | ∓40.0 pts | +1.2041 | +0.7316 | +0.4725 | 3 / 4 | **thin** — n < 20, no verdict |
| **META** | equity | 42 | 50.0% | ∓28.6 pts | +0.5087 | +1.0200 | -0.5113 | 13 / 21 | **does NOT fit** |
| **MSFT** | equity | 29 | 41.4% | ∓27.6 pts | +0.2078 | +0.5982 | -0.3904 | 5 / 15 | **does NOT fit** |
| **NVDA** | equity | 48 | 54.2% | ∓45.8 pts | +0.5642 | +0.7326 | -0.1684 | 15 / 21 | **does NOT fit** |
| **PLTR** | equity | 77 | 54.5% | ∓51.9 pts | +0.5707 | +0.8192 | -0.2485 | 11 / 20 | **does NOT fit** |
| **QQQ** | index | 9 | 66.7% | ∓33.3 pts | +1.2580 | +0.7413 | +0.5167 | 5 / 6 | **thin** — n < 20, no verdict |
| **SPY** | index | 4 | 50.0% | ∓0.0 pts | +1.0363 | +0.7442 | +0.2920 | 2 / 3 | **thin** — n < 20, no verdict |
| **TSLA** | equity | 75 | 62.7% | ∓41.3 pts | +0.8507 | +0.8187 | +0.0319 | 19 / 24 | fits |
| _roster total_ | — | 431 | 55.0% | — | +0.6644 | +0.7772 | -0.1128 | — | — |

**The list, which is the answer to his question.**

- **Does not fit a flat 2R exit** (6 of 8 names above the floor): **AMD** (-0.1335 R), **AMZN** (-0.1147 R), **META** (-0.5113 R), **MSFT** (-0.3904 R), **NVDA** (-0.1684 R), **PLTR** (-0.2485 R)
- **Fits** (2): **GOOGL** (+0.3263 R), **TSLA** (+0.0319 R)
- **Thin, no verdict** (4, n < 20): AAPL (n=19), IWM (n=5), QQQ (n=9), SPY (n=4)

A second cut of the same table, because "fits" above is relative to the ladder and a name can beat the ladder while still losing money: **0 roster names book a NEGATIVE mean R under `flat_2r`** — _none_. Every thick roster name is at least profitable under a flat 2R exit.

## What this does not say

- **It does not say the fill is irrelevant.** It says the fill DIFFERENCE this engine can express — one predicate at 2 of 10 call sites — is smaller than the doubt the fill assumption already carries. A genuine close-fill arm would need `fill_price` itself changed, and this ticket changes nothing.
- **It does not say `flat_2r` is worthless.** It is the simplest exit in the lab and it books 59.9% wins. It is worth 0.2554 R of mean R less than the ladder, and that is the price of the simplicity, stated so Austin can decide whether he wants to pay it.
- It does not re-open the stop rule. Stops trigger on the candle CLOSE, fill at that close, floored at −1.25R; wicks stop nothing out.
- **`exit_lab` and `backtest_2y` floor losses differently and that is on purpose.** `exit_lab` floors at −1.25R (`MAX_LOSS_R`); the backtest floors at the stop. So the `flat_2r` and ladder columns measure slightly different downside, exactly as `research/g7_exit_sweep.md` states. The delta column is biased AGAINST `flat_2r` by that difference and it is not corrected for.
- The intrabar marker can only UNDER-count: `backtest_2y.py:169` stores entry at 2dp, so a clamped level that rounds into the close's own cent is recorded as a close fill. Every intrabar and ambiguity count here is a floor.
- P(2R) is not win rate and the two must not be swapped. A trade that reaches 2R and is booked at +2.0 is one row of both; a trade that books +0.3 is a win and not a 2R.
- **The intention-to-treat table makes one choice and it is stated, not hidden: a candidate arm B never traded counts as a non-hit.** The alternative — dropping it — is what every per-arm table in this repo does implicitly, and it is what produces the 62.50% figure. Neither is a measurement; the choice is between two denominators, and the ITT one is the question a trader asks (*if I adopt this fill, what happens to the 175 setups I would otherwise have taken?*). It does NOT claim those 135 trades lost money — under the close fill they book -0.0058 R, roughly flat.
- **The candidate set is 175 signals and the surviving arm is 40.** That is above `universe.MIN_SAMPLE_N` but it is not large, and the per-symbol cut of it would be far below the floor, so it is not attempted. The direction of the ITT result is a 22-point move and would survive a good deal of noise; the exact figure would not.
- **`moved` is measured from the stored 2dp entry and stop, so it is a floor.** A back-dated fill whose clamped level rounds into the close's own cent is recorded as unmoved — the same under-count as the intrabar marker. The true number of moved fills is at least the 39 counted here.
- Nothing here is a walk-forward. Every number is in-sample over the same 500 sessions every other 2-year table in this repo reads.

## Provenance

Produced by `research/r9_simple_book.py` at _this commit_, over the two fill arms `research/g3_arm_ow0.json` and `research/g3_arm_ow1.json` replayed by `research/g3_onwatch_2y.py` (T3, commit `47e60796`): 2024-08-21 → 2026-08-21, 500 sessions, 45,193 signals per arm. Regenerate with `python research/r9_simple_book.py`; verify the rig with `python research/r9_simple_book.py --selfcheck`.

**Nothing is re-derived that another rig already derived.** `flat_2r` is `research/exit_lab.flat_target` called unmodified at 2.0R with `CLOCK_BAR = 90` and `MAX_LOSS_R = 1.25` untouched. The intrabar marker, its 2dp rounding correction, the two fill predicates and the ambiguity test are imported from `research/p26_intrabar_ambiguity.py` (T2). The whole-book money read is `research/a2_bt2y_summary.py::book`. The symbol roster and the sample floor are imported from `universe.py`. What this file adds is the JOIN between the two arms — `matched()` and `candidates()` — and one boolean naming whether the 2R target was reached; `--selfcheck` asserts that boolean agrees with `flat_target(...) == +2.0` on all 2,108 traded rows of both arms, and that the 914 pairs with identical entry and stop replay bit-identically.

Bars were read from `data_archive/` only, through `p26.load_day`, whose guard makes a network fetch impossible. Gaps: 0 rows with no archived session, 0 with an entry minute that has no bar, 0 with an `entry_i` past the end of the session — across both arms, out of 2,108 traded rows.

`python research/regression_gate.py` is RED at HEAD and was red before this ticket, which adds only new files under `research/` and edits no engine module. It is being bisected separately. Re-run after this file landed, it drops the SAME six `s_grade` marks and no others — `GOOGL|2024-10-15|32`, `IWM|2025-04-10|16`, `IWM|2025-12-01|11`, `IWM|2025-12-04|56`, `QQQ|2025-02-25|16`, `UBER|2025-09-11|15` — so this ticket added no new drop. `python research/test_provenance.py` passes.
