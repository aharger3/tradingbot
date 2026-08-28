# T24 — the stop taxonomy: three stops, and the setup picks

Austin, 2026-08-28: *"stops are wherever makes sense live. they are not pre known because we dont have HTF thesis from corpus yet. examples wick of OCR, candle entered on, break and retest of a level stop loss that level. most popular off the top of my head. market and limit orders a different beast."*

Script: `research/t24_stop_taxonomy.py`. Engine flags: `signal_runner.STOP_PLACEMENT` (default `entry_bar`) and `signal_runner.STOP_FILL_ORDER` (default `as_booked`), both added by this ticket, both DEFAULT OFF. Book: `research/g3_arm_ow1.json`, 1,017 traded rows of 45,193 signals, 500 sessions, 28 symbols, 2024-08-21..2026-08-21, engine at `246873b7`. Error bar on an A/B of this book is ±0.0095 R; anything smaller is noise and is labelled so.

**The book at `246873b7` means +0.8341 R at 53.1% win, 23 of 25 months green, 1,017 traded rows.** The +0.9551 R figure still quoted in the wave-1 brief predates T11's stop-fill fix; `DIRECTION.md` already carries the corrected pair. Every number below is measured on the +0.8341 R book.

## Verdict, in four lines

1. **The taxonomy is already implemented.** `routed` — OCR to the block wick, B&R to the broken level — reproduces the shipped book **byte for byte across all 45,193 signals**. Not "within the error bar": the same sha256. The detectors already pick structurally; the ticket's premise that one entry-bar stop is applied to every setup is not what the code does.
2. **What overwrites the choice is the FILL, not the detector.** `intrabar_stop` moves a B&R stop onto the entry bar's own extreme whenever the back-dated fill lands on the level-stop. It fires on **803 of 947 traded B&R rows (84.8%)**, so the shipped book *is* mostly the entry bar — by accident of the fill rule, not by the setup picking it.
3. **Austin parked the knob that decides this, and it is worth the whole book.** Under the shipped back-dated fill, a broken-level stop has **zero risk on 83.7% of traded rows** — the level and the fill are the same price. Under a market order at the bar's close the same book means **+0.0955 R at 46.3% win, 18 of 25 months**, against +0.8341 / 53.1% / 23 of 25. Reported, not decided.
4. **Held-out S recall does not move.** 3/15 on `entry_bar`, 3/15 on `routed`, and the two uniform candle placements LOSE one (2/15). No placement buys recall.

## 0. The single stop derivation, by file and line

| site | line at `246873b7` | what it sets | Austin's placement |
|---|---|---|---|
| B&R long | `signal_runner.py:2040` `stop = level_hi` | the broken level | (c) |
| B&R short | `signal_runner.py:2300` `stop = level_lo` | the broken level | (c) |
| OCR long | `signal_runner.py:2184` `stock_risk = entry - block.low` | the block's far wick | (a) |
| OCR short | `signal_runner.py:2409` `stock_risk = block.high - entry` | the block's far wick | (a) |
| 84% re-entry | `signal_runner.py:2256` / `:2474` `stop_84 = stop_chk` | the original stop | — |
| **the rewriter** | `signal_runner.py:982` `intrabar_stop()` | the entry bar's own extreme | (b) |

`BNR_STOP_MODE` is `"level"` (`signal_runner.py:127`), `FVG_RETEST` and `FLAG_ENABLED` are both False, so the live detectors are exactly three: B&R (947 traded), OCR (67) and the 84% re-entry (3).

## 1. HELD-OUT S RECALL FIRST

`research/marks/probe_omen_test1_2026-08-27.jsonl` — 15 S / 27 A / 16 C / 42 X, scored by `research/t70_test1_score.py::score_all`, imported not reimplemented. Every in-sample recall gain in this project's history has bought zero held-out recall, so this table comes before any book number.

| arm | placement | fill | held-out S recall | false fire | entry match |
|---|---|---|---:|---:|---:|
| `entry_bar` | entry_bar | as_booked | **3/15** | 12/42 | 4/58 |
| `candle_entered` | candle_entered | as_booked | **2/15** | 8/42 | 2/58 |
| `ocr_wick` | ocr_wick | as_booked | **2/15** | 9/42 | 2/58 |
| `broken_level` | broken_level | as_booked | **3/15** | 11/42 | 4/58 |
| `routed` | routed | as_booked | **3/15** | 12/42 | 4/58 |
| `entry_bar_mkt` | entry_bar | market_on_close | **3/15** | 21/42 | 6/58 |
| `routed_mkt` | routed | market_on_close | **3/15** | 21/42 | 6/58 |
| `broken_level_mkt` | broken_level | market_on_close | **3/15** | 20/42 | 6/58 |

## 2. Where HIS OWN stops sit

The only direct evidence about the taxonomy, and it is his. Every mark corpus in `research/p25_midcandle_entry.MARK_FILES`; a row counts when it carries an entry bar index, an entry price, and a stop `p25.clean_stop` accepts as a price rather than a typed note (he types "931" meaning the 9:31 wick).

114 usable marked stops. Skipped: no_entry 976, stop_is_a_note 8.

| where his stop sits | n | share |
|---|---:|---:|
| elsewhere (a level, not a candle) | 58 | 50.9% |
| entry bar extreme | 17 | 14.9% |
| inside the entry bar | 31 | 27.2% |
| previous bar extreme | 8 | 7.0% |

| his setup label | n | placement split |
|---|---:|---|
| 84 | 3 | elsewhere (a level, not a candle) 2, inside the entry bar 1 |
| ? | 5 | elsewhere (a level, not a candle) 4, previous bar extreme 1 |
| BR | 56 | elsewhere (a level, not a candle) 24, entry bar extreme 10, inside the entry bar 17, previous bar extreme 5 |
| BR+OCR | 20 | elsewhere (a level, not a candle) 9, entry bar extreme 4, inside the entry bar 7 |
| OCR | 30 | elsewhere (a level, not a candle) 19, entry bar extreme 3, inside the entry bar 6, previous bar extreme 2 |

His median risk: **$0.645**, **0.197%** of entry, **0.901** of the entry bar's own range (n=114).

His own words in the `stop_src` box, verbatim:

| stop_src | n |
|---|---:|
| ORH | 4 |
| ORL | 5 |
| PDH | 3 |
| PDL | 2 |
| PML | 2 |
| swing high 09:39 | 2 |
| swing high 09:40 | 1 |
| swing high 09:44 | 2 |
| swing high 09:45 | 1 |
| swing high 09:46 | 1 |
| swing high 09:50 | 1 |
| swing high 09:52 | 1 |
| swing high 09:53 | 2 |
| swing high 10:10 | 2 |
| swing high 10:16 | 1 |

## 3. `|entry − stop|` per setup family, before and after

p10 / median / p90 over the traded rows of each arm's own book. Bar-ranges is the fraction of the ENTRY BAR's own high-low range — the only unit comparable across symbols and across days.

### ALL

| arm | n | price | % of entry | bar-ranges | zero-risk rows |
|---|---:|---|---|---|---:|
| `entry_bar` | 1017 | 0.170 / 0.420 / 1.150 | 0.159% / 0.226% / 0.405% | 0.355 / 0.656 / 0.936 | 0 |
| `candle_entered` | 1133 | 0.160 / 0.400 / 1.110 | 0.159% / 0.220% / 0.408% | 0.392 / 0.652 / 0.844 | 0 |
| `ocr_wick` | 1205 | 0.160 / 0.420 / 1.150 | 0.159% / 0.225% / 0.421% | 0.394 / 0.671 / 0.912 | 0 |
| `broken_level` | 962 | 0.160 / 0.400 / 1.130 | 0.161% / 0.226% / 0.421% | 0.354 / 0.641 / 0.889 | 1 |
| `routed` | 1017 | 0.170 / 0.420 / 1.150 | 0.159% / 0.226% / 0.405% | 0.355 / 0.656 / 0.936 | 0 |
| `entry_bar_mkt` | 1543 | 0.170 / 0.470 / 1.350 | 0.163% / 0.251% / 0.563% | 0.466 / 0.770 / 1.276 | 0 |
| `routed_mkt` | 1543 | 0.170 / 0.470 / 1.350 | 0.163% / 0.251% / 0.563% | 0.466 / 0.770 / 1.276 | 0 |
| `broken_level_mkt` | 1519 | 0.170 / 0.450 / 1.340 | 0.164% / 0.248% / 0.569% | 0.462 / 0.754 / 1.152 | 0 |

### B&R

| arm | n | price | % of entry | bar-ranges | zero-risk rows |
|---|---:|---|---|---|---:|
| `entry_bar` | 947 | 0.160 / 0.400 / 1.120 | 0.161% / 0.226% / 0.426% | 0.354 / 0.641 / 0.889 | 0 |
| `candle_entered` | 1100 | 0.160 / 0.390 / 1.120 | 0.160% / 0.222% / 0.421% | 0.389 / 0.656 / 0.848 | 0 |
| `ocr_wick` | 1134 | 0.160 / 0.400 / 1.130 | 0.161% / 0.226% / 0.428% | 0.393 / 0.666 / 0.878 | 0 |
| `broken_level` | 952 | 0.160 / 0.400 / 1.120 | 0.161% / 0.226% / 0.423% | 0.354 / 0.642 / 0.889 | 0 |
| `routed` | 947 | 0.160 / 0.400 / 1.120 | 0.161% / 0.226% / 0.426% | 0.354 / 0.641 / 0.889 | 0 |
| `entry_bar_mkt` | 1478 | 0.160 / 0.445 / 1.340 | 0.164% / 0.251% / 0.573% | 0.459 / 0.755 / 1.169 | 0 |
| `routed_mkt` | 1478 | 0.160 / 0.445 / 1.340 | 0.164% / 0.251% / 0.573% | 0.459 / 0.755 / 1.169 | 0 |
| `broken_level_mkt` | 1483 | 0.160 / 0.450 / 1.340 | 0.164% / 0.251% / 0.573% | 0.459 / 0.757 / 1.169 | 0 |

### OCR

| arm | n | price | % of entry | bar-ranges | zero-risk rows |
|---|---:|---|---|---|---:|
| `entry_bar` | 67 | 0.540 / 0.690 / 1.380 | 0.114% / 0.218% / 0.338% | 0.629 / 1.058 / 2.298 | 0 |
| `candle_entered` | 30 | 0.530 / 0.640 / 0.970 | 0.084% / 0.158% / 0.294% | 0.388 / 0.631 / 0.728 | 0 |
| `ocr_wick` | 68 | 0.540 / 0.700 / 1.320 | 0.114% / 0.206% / 0.339% | 0.532 / 0.992 / 2.298 | 0 |
| `broken_level` | 8 | 0.630 / 0.700 / 1.180 | 0.083% / 0.189% / 0.225% | 0.456 / 0.594 / 0.660 | 0 |
| `routed` | 67 | 0.540 / 0.690 / 1.380 | 0.114% / 0.218% / 0.338% | 0.629 / 1.058 / 2.298 | 0 |
| `entry_bar_mkt` | 65 | 0.560 / 0.710 / 1.480 | 0.110% / 0.237% / 0.362% | 1.127 / 1.549 / 2.367 | 0 |
| `routed_mkt` | 65 | 0.560 / 0.710 / 1.480 | 0.110% / 0.237% / 0.362% | 1.127 / 1.549 / 2.367 | 0 |
| `broken_level_mkt` | 36 | 0.540 / 0.740 / 1.180 | 0.113% / 0.189% / 0.284% | 0.518 / 0.669 / 0.888 | 0 |

### 84%

| arm | n | price | % of entry | bar-ranges | zero-risk rows |
|---|---:|---|---|---|---:|
| `entry_bar` | 3 | 0.390 / 0.640 / 0.640 | 0.145% / 0.172% / 0.172% | 0.464 / 0.842 / 0.842 | 0 |
| `candle_entered` | 3 | 0.290 / 0.480 / 0.480 | 0.072% / 0.154% / 0.154% | 0.569 / 0.571 / 0.571 | 0 |
| `ocr_wick` | 3 | 0.290 / 0.480 / 0.480 | 0.072% / 0.154% / 0.154% | 0.569 / 0.571 / 0.571 | 0 |
| `broken_level` | 2 | 0.000 / 0.025 / 0.000 | 0.000% / 0.014% / 0.000% | 0.000 / 0.030 / 0.000 | 1 |
| `routed` | 3 | 0.390 / 0.640 / 0.640 | 0.145% / 0.172% / 0.172% | 0.464 / 0.842 / 0.842 | 0 |

## 4. The book re-scored under each placement

| arm | traded | mean R | win % | months green | rows < −1.0R | at the −1.25R floor | unsizeable | mean risk $ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `entry_bar` | 1017 | +0.8341 | 53.1% | 23/25 | 460 | 303 | 22 | 0.589 |
| `candle_entered` | 1133 | +0.7748 | 50.1% | 23/25 | 549 | 364 | 23 | 0.570 |
| `ocr_wick` | 1205 | +0.7237 | 49.8% | 24/25 | 584 | 384 | 29 | 0.587 |
| `broken_level` | 962 | +0.8550 | 53.1% | 23/25 | 436 | 286 | 8 | 0.574 |
| `routed` | 1017 | +0.8341 | 53.1% | 23/25 | 460 | 303 | 22 | 0.589 |
| `entry_bar_mkt` | 1543 | +0.0955 | 46.3% | 18/25 | 646 | 387 | 23 | 0.669 |
| `routed_mkt` | 1543 | +0.0955 | 46.3% | 18/25 | 646 | 387 | 23 | 0.669 |
| `broken_level_mkt` | 1519 | +0.0975 | 46.2% | 17/25 | 637 | 386 | 17 | 0.663 |

## 5. The order-type fork, priced but NOT decided

Austin, same message: *"market and limit orders a different beast."* He parked it, and this ticket does not un-park it. But it is the knob that decides whether a broken-level stop has any risk under it, so both conventions are run.

Counterfactual on the shipped book's own traded rows, straight from the tape (`|entry − the broken level|`, entries left where they are):

| family | rows | zero-risk under a level stop | share |
|---|---:|---:|---:|
| B&R | 947 | 803 | 84.8% |
| OCR | 67 | 46 | 68.7% |
| **all traded** | **1,014** | **849** | **83.7%** |

That is the whole mechanism. A resting LIMIT at the level fills AT the level, and for a break-and-retest the level IS the stop, so `|entry − stop|` is zero and the setup cannot be sized. `intrabar_stop` exists to rescue exactly those rows, and it rescues them onto placement (b). A MARKET order fills at the bar's close, which is beyond the level by construction, so the same stop carries real risk — and a different book:

| convention | traded | mean R | win % | months green | mean risk $ |
|---|---:|---:|---:|---:|---:|
| `as_booked` (shipped) | 1017 | +0.8341 | 53.1% | 23/25 | 0.589 |
| `market_on_close` | 1543 | +0.0955 | 46.3% | 18/25 | 0.669 |

**The two conventions are +0.7386 R apart on the same two years.** The market arm is not the shipped book with a worse fill — it trades 1543 rows against 1017, because a fill at the bar's close leaves real risk under the stop and the minimum-risk gate stops deleting setups. Neither arm is decided here: this is the size of the question Austin parked, stated in the unit the money gate reads.

## 6. Does `routed` shrink or grow the R denominator?

**Neither. It does not move it at all.** Mean `|entry − stop|` is $0.5887 on both arms, mean R is +0.8341 on both, and the two books share one sha256 over all 45,193 rows (`ebf04f2b32e55d42`). The routed policy is the shipped policy.

**So no published OMEN R-multiple is over- or under-stated by the setup family's stop being wrong.** The three placements Austin named are already routed correctly at the point the detector picks them. What the ticket suspected — that two of three families carry the wrong stop — is refuted by a byte-identity check, not by an estimate.

The denominator IS understated against a different reference, and that reference is his own marks. On the 114 marked stops this script could locate, his median stop sits **0.90 of the entry bar's own range** from his entry; the shipped book's traded rows sit at **0.66** (B&R 0.64, OCR 1.06). His stop is wider than the entry bar's extreme on **64 of 114 (56.1%)** of them. Two cautions, both load-bearing: these are **different populations** (114 marked symbol-days against 1,017 engine-traded rows), so this is an indication and not an A/B; and it is a statement about the ENGINE's stop, never about his marks, which are the ground truth every gate here is scored against.

Note also which family already matches him. **OCR — the one family whose stop is a candle wick by construction — books 1.06 bar-ranges, the closest of the three to his 0.90.** B&R, which is 93.1% of the traded book, books 0.64 because `intrabar_stop` pulls its stop in to the entry bar. If a wider stop is wanted, the lever is the fill rule, not the placement.

## 7. What is still open

- **Order type.** Parked by Austin. Both conventions are published above and neither is shipped; `STOP_FILL_ORDER` defaults to `as_booked`.
- **His `stop_src` vocabulary is a FOURTH placement.** The free-text box on the held-out cards is dominated by `swing high HH:MM` / `swing low HH:MM` and by named levels (`ORH`, `ORL`, `PDH`, `PDL`, `PML`). Pivot structure is in the engine (`PIVOT_LEVELS=1`) but as one of seven level families, not as a stop placement. That is a ticket, not a finding, and it is not invented here — it is his own typing.
- **`intrabar_stop` is the real subject.** It rewrites 84.8% of B&R stops and it is the only reason the book is sizeable under the shipped fill. Any future work on the R denominator goes there, not into the placement router.

## Provenance

Every number here comes from a file this script wrote: `_t24_his_stops.json`, `_t24_test1.json`, `_t24_dist.json`, `_t24_stats.json`, and one `_t24_arm_*.json` book per arm (8 full 2-year replays of `backtest_2y.py`, one per arm, each in a child process with the two variables forced in its environment). `STOP_PLACEMENT=entry_bar` is proved byte-identical to the shipped book by `python research/t24_stop_taxonomy.py identical`, and `research/test_runner_stop.py` carries one case per placement (red at `246873b7`, where `signal_runner.placed_stop` does not exist).

