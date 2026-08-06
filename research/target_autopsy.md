# Target Autopsy — what rule is he actually using (omen-3.4, T4)

**Population:** 117 clean trade marks = the real-trade subset of `research/blind_marks_all.jsonl` (260 lines; 143 are `_no_trade` annotations with no target and are excluded from target classification). Written to `research/marks_clean.jsonl` so the bucket count below sums to that file's line count.

**Why this file, not a pre-existing `marks_clean.jsonl`:** the named input `research/marks_clean.jsonl` and the named node generator `research/levels.py` did not exist in the checked-out `main` (consistent with T1's MISSING findings — several omen-3.4 inputs only ever lived on `wip/v3-carryover`, uncommitted). Per T1's frozen inputs (`research/omen34_inputs.md`), the only hand-marked corpus present is `blind_marks_all.jsonl`; its 117 trade records are the clean marks. `levels.py` is reconstructed here from the documented exit ladder and the only 1m bar material in the checkout, `data_archive/<SYMBOL>/<YYYY-MM-DD>.csv`.

## Method

- **2R test:** `at_2R` iff `|rr - 2.0| <= 0.25` (within 0.25R of exactly 2.0R). `rr` is the mark's own reward/risk; the 2R target price is `entry + 2*risk*dir`.

- **Level test:** `at_level` iff the target is within `max(2 ticks, 0.30*ATR_1m)` of a node of weight >= 2.0. `tick = $0.01`.

- **ATR_1m:** 14-bar 1-minute ATR over RTH bars up to the entry bar, indexed the way the trader indexed them (09:30 start; verified: `CSV[RTH0 + entry_i].time == entry_t`). Where a mark's day is outside the archive window or the symbol is un-archived, ATR falls back to `risk / 0.84` (the median `risk/ATR_1m` over the 59 archived marks with enough bars); this keeps the tolerance on a data-grounded scale instead of collapsing to 2 ticks.

- **Nodes:** whole psychological numbers (always, price-derivable) plus, where RTH bars exist, HOD/LOD, prior-day PDH/PDL + floor pivots, prior-month PMH/PML, and 3-bar swing pivots. Weights follow the documented exit ladder (HOD/LOD 3.0, PDH/PDL/PMH/PML 2.5, psych $50/$10/$5/whole = 3.0/2.5/2.3/2.0, pivots & swings 2.0). The 2.0 floor on whole dollars is what makes "whole psychological numbers" qualify for `at_level`.

- **Bar coverage:** rth=75, prior=0, none=42 (ATR source: rth=75, fallback=42). Marks with `none` rely on psych nodes only; this asymmetry is reported below and is the main caveat.

- **Exactly one bucket per mark; no `unknown`.** A mark the code cannot classify would be a classifier bug and would `assert`-fail the run. The run passed: all 117 placed.


## Bucket distribution

| bucket | count | share |
|---|---:|---:|
| at_level | 21 | 17.9% |
| at_2R | 39 | 33.3% |
| both | 38 | 32.5% |
| open_air | 19 | 16.2% |
| **total** | **117** | **100%** |

**Headline:** 21 targets sit on a structural level (17.9%), 39 on a blind 2R (33.3%), 38 on both at once (32.5%), and 19 on neither (16.2%). Counting the rule either way, the 2R test is satisfied by 77 marks (65.8%) and the level test by 59 (50.4%); pure 2R (39) also beats pure level (21). **2R is the dominant target rule.** The smoking gun is the rr distribution below: it clusters *hard* at exactly 2.0 (Q1=2.000, median=2.039, Q3=2.290) — his hand targets 2R even though his coaching says 2R is only a minimum.

## Bucket distribution by tier

| tier | at_level | at_2R | both | open_air | total |
|---|---:|---:|---:|---:|---:|
| S | 3 | 21 | 18 | 8 | 50 |
| A | 18 | 18 | 20 | 11 | 67 |

## Bucket distribution by `smeared`

`smeared` = the target sits within tolerance of **2+ distinct rule-source families** at once (e.g. a whole dollar that is also a floor pivot and also ~2R), so you cannot cleanly attribute it to one rule. Families: psych, HOD, LOD, PDH, PDL, PMH, PML, pivot, swing, and 2R.

| smeared | at_level | at_2R | both | open_air | total |
|---|---:|---:|---:|---:|---:|
| false | 13 | 39 | 0 | 19 | 71 |
| true | 8 | 0 | 38 | 0 | 46 |

## Bucket distribution by tier × smeared (contamination check)

| tier | smeared | at_level | at_2R | both | open_air | total |
|---|---|---:|---:|---:|---:|---:|
| S | false | 2 | 21 | 0 | 8 | 31 |
| S | true | 1 | 0 | 18 | 0 | 19 |
| A | false | 11 | 18 | 0 | 11 | 40 |
| A | true | 7 | 0 | 20 | 0 | 27 |

**Contamination verdict:** clean marks distribute [level 18.3% / 2R 54.9% / both 0.0% / open_air 26.8%]; smeared marks distribute [level 17.4% / 2R 0.0% / both 82.6% / open_air 0.0%]. Smeared marks are 38.0% of the S tier and 40.3% of the A tier. 
The two tiers smear at similar rates, so smearing does **not** materially contaminate the tier labels; the S/A split is not an artefact of coincident levels.


## PRECEDENCE

When a level and 2R disagree (the level node price L and the 2R price are more than the tolerance apart), which does his target actually follow?

- Marks where level and 2R **disagree**: 75 of 117 (the rest are `both`/agree, or open_air with no competing 2R structure).

- Of those, target is **closer to the level** in 28 marks, **closer to 2R** in 47 marks, **tied** in 0 marks.

- **Winner: 2R.** When the round-number level and the blind 2R price point to different places, his target tracks the **2R**.

- Cross-check via pure buckets (marks attributable to exactly one rule): pure `at_level` = 21, pure `at_2R` = 39, `both` (they agreed) = 38. 
2R claims more solo marks than levels, confirming the precedence.

- So the precedence among his four stated rules is: **2R first, structural level (whole psychological number / HOD-LOD / HTF level / pivot) second.** The structural level only wins the target when it happens to coincide with 2R (the `both` bucket, 38 marks); when they point to different places he takes 2R (47 of 75 disagree marks). **This contradicts his stated rule.** His coaching (`research/scarface-rules-accelerator.md`) says *"2:1 is the MINIMUM aggregate R:R expectation, not the exit mechanism"* and that targets are *liquidity levels* — but his hand targets 2R (rr Q1=2.000, median=2.039). The autopsy answer to "what rule is he actually using" is therefore **2R**, not the liquidity ladder he describes.


## Distance from target to nearest node (ticks)

Distribution of signed `target - nearest_node`, in ticks (tick = $0.01), over ALL marks (nearest node of any type/weight):

- signed: min=-47.0, p10=-33.0, p25=-14.0, median=-1.1, p75=11.0, p90=31.0, max=49.0

- |distance|: median=12.0 ticks, p75=31.0, p90=40.0, max=49.0

- in ATR units: median |d/ATR|=0.272


### Osler queue-effect check — signed distance to nearest whole-dollar

Signed `(target - nearest whole-dollar)` in ticks, by side. **Just short of a round number** = for a long (call) the target sits a few ticks *below* the round number (he exits before price reaches it); for a put, a few ticks *above* the lower round number.

- calls (n=61): median=-1.0 ticks, mean=-1.0, p25=-27.0, p75=20.0, frac negative(target below round#)=52.5%
- puts (n=56): median=0.0 ticks, mean=3.7, p25=-23.0, p75=32.0, frac positive(target above round#)=48.2%

**Targets sit essentially *on* the round numbers** (median within ~1 tick on both sides). No just-short cluster → the queue effect is *not* visible in his hand; his targets are the round numbers themselves. Not directly actionable as a shave; treat the round number as the exit.


## rr distribution

- n=117, min=0.500, max=12.368

- median=2.039, Q1=2.000, Q3=2.290

- fraction below 1.0: 4 (3.4%)

- fraction above 5.0: 5 (4.3%)


## Nearest-node type breakdown (all marks)

| nearest node type | count | share |
|---|---:|---:|
| psych | 76 | 65.0% |
| psych_half | 9 | 7.7% |
| LOD | 8 | 6.8% |
| HOD | 7 | 6.0% |
| pivot_PP | 5 | 4.3% |
| PDL | 3 | 2.6% |
| pivot_S1 | 2 | 1.7% |
| pivot_R2 | 2 | 1.7% |
| PDH | 2 | 1.7% |
| swing_low | 1 | 0.9% |
| pivot_R1 | 1 | 0.9% |
| swing_high | 1 | 0.9% |

## Caveats

1. **Bar coverage is partial:** 75/117 marks have archived RTH 1m bars (full node set + real ATR); 42 rely on psych nodes only + the risk/0.84 ATR fallback. The 42 are mostly pre-2024-07 marks and the un-archived symbols DIA/GOOG/IWM. The `at_level` verdict for those 42 rests on psychological numbers alone — a structural level (HOD/LOD/pivot/HTF) the trader may have used is invisible to the classifier there. This biases those 42 *toward* `open_air`/`at_2R` and *against* `at_level`; the true level-share is likely higher than reported.

2. `marks_clean.jsonl` and `levels.py` did not exist on `main` and were reconstructed for this task (see top of file). If the spec's intended versions surface, re-run `research/target_autopsy.py`.

3. The 2R test uses the mark's own `rr`; the level test uses a reconstructed node set, not the trader's internal one. Where they disagree, the precedence answer is robust (it is a distance comparison), but per-mark `at_level` booleans for the 42 no-bar marks are psych-only.


---
_Reproducible: `python3 research/target_autopsy.py` regenerates this file._

