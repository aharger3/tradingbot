# W9 score — vision-classifier eye test

No: neither Claude Haiku nor Claude Sonnet, reading the same 100 chart cards blind, reproduces Austin's S marks above the 30.5% graded-day baseline by a margin that survives their own bootstrap error bars — Haiku's point estimate clears it (43.6% vs 30.5%) but its 95% band runs 28.6%–60.0%, straddling the baseline; Sonnet's point estimate barely clears it (38.5%) with a band of 14.3%–66.7% that sits mostly below it.

Produced by `research/g211_eye_test.py`, reading `research/g210_cards/index.json` (his grades, 100 cards, this deck's own S rate is 34.0%) against `research/g211_reads_haiku.json` and `research/g211_reads_sonnet.json` (each model's independent grade for the same 100 cards, S/A/C/none plus a prose reason). No trade money, no market data, no fill — this is a label-agreement measurement only.

## Confusion matrices (S vs not-S)

**Haiku**

| | model S | model not-S |
|---|---:|---:|
| **his S** | 17 | 17 |
| **his not-S** | 22 | 44 |

Precision (S) = 0.436, Recall (S) = 0.500

**Sonnet**

| | model S | model not-S |
|---|---:|---:|
| **his S** | 5 | 29 |
| **his not-S** | 8 | 58 |

Precision (S) = 0.385, Recall (S) = 0.147

## Precision, recall, agreement, baseline, bootstrap band

| model | precision (S) | recall (S) | raw S/A/C/none agreement | vs 30.5% baseline | bootstrap 95% band (n=2000) |
|---|---:|---:|---:|---|---|
| Haiku | 0.436 | 0.500 | 36/100 = 0.360 | above | [0.286, 0.600] |
| Sonnet | 0.385 | 0.147 | 32/100 = 0.320 | above | [0.143, 0.667] |

Both point-estimate precisions clear the 30.5% baseline, but at n=100 cards (Haiku fires S on 39 of them, Sonnet on 13) the bootstrap bands are wide enough that neither result is distinguishable from the baseline with confidence — Sonnet's band in particular puts a large share of its mass *below* 30.5%. Haiku also has 2x Sonnet's recall (0.500 vs 0.147): Sonnet is far more conservative about calling S and misses most of what Austin actually marked S.

## Both models said S, he said none (false positives)

Only 4 cards met this condition (not 10 — the two models rarely both fire S on the same card, let alone on one Austin refused):

| card | haiku reason (truncated) | sonnet reason (truncated) |
|---|---|---|
| AMD_2025-04-24 | Clean break above ORH with tight retest; small red OCR candle at the level respected as stop, price confirms higher by 09:55. | Sweeps below ORL, reversal candle reclaims and closes back above ORL by 09:37, every candle after respects it — clean BR+OCR confluence. |
| ORCL_2024-09-25 | Break of ORH at 09:39 + 09:40 displacement candle generates OCR confluence; retest holds above 167 through cut. | Displacement through ORL then ORH; retest is a one-candle-rule bar respected (bought back, no close through) — BR+OCR confluence. |
| ARM_2026-04-29 | ORL breaks below at 09:46–09:47, retests 09:48–09:50 with green OCR candles in a downtrend; confluence cancels the light displacement downgrade. | Displacement through PML into PDL; 09:48 wick below PDL closes back above; 09:49 green candle is the one-candle-rule reversal. |
| IREN_2025-09-25 | BR of ORL/PDL at 44.00 with OCR confluence from 09:36 red candle; displacement confirmed by sustained green candles with higher lows. | Sweeps below ORL into 09:38–09:39 low, one up-close candle against the down-move, reclaims and closes back above ORL with force. |

Both models independently reach S on these four via textbook BR+OCR structure; Austin refused all four. Four cards is a hint that the models' notion of "clean confluence" is more permissive than his, not a diagnosis — no rule can be inferred from four.

## He said S, both models said none (misses)

Only 3 cards met this condition (not 10):

| card | haiku reason (truncated) | sonnet reason (truncated) |
|---|---|---|
| QQQ_2025-09-23 | No displacement behind the early drop below ORH; drifting price action without level commitment. | Chopping around ORL with repeated closes through the level instead of a clean break and reaction. |
| MARA_2025-07-18 | Breaks PDH at 09:32, runs without retesting; subsequent chop closes through price rather than respecting support. | Only wicked down near ORL/PML and rallied to chop directly under PDH/ORH — no level has actually broken. |
| BABA_2026-06-12 | Chops through ORH without breaking decisively; candles close through levels repeatedly instead of reacting. | Broke ORH toward 09:33, reversed hard through ORL by 09:34, chopping right on ORL — refusal case. |

On all three, both models read the price action as unresolved chop with no respected level — exactly the condition the rulebook calls a refusal — while Austin still marked S. This is the same pattern the project CLAUDE.md already names from his own 2026-08-30 marks: entries he takes read as "close but didn't actually touch" rather than the clean textbook shape either model is pattern-matching for.

## What this means for a vision classifier

- **Not ready to gate anything.** At n=100 with only 34 true S cards, both models' precision estimates carry error bars wide enough to overlap the 30.5% baseline (Sonnet's band mostly sits below it). Neither model beats the baseline with statistical confidence on this sample.
- **The two models disagree with each other more than either agrees with him.** Haiku fires S on 39/100 cards, Sonnet on 13/100 — a >3x gap in willingness to call S — and their agreement with his full S/A/C/none ladder (36% and 32%) is barely better than chance among two collapsed classes.
- **The false positives and misses point the same direction as the human marks already on file.** Where the models disagree with Austin, it looks structural: they call S on textbook BR+OCR shapes he refuses, and call none on chop where he still saw a trade — consistent with the recorded finding that his entries are "close but didn't actually touch," a unit narrower than either model is reading off the chart.
- **Before this becomes a candidate classifier**, it needs a much larger graded sample (100 cards, 34 positives, is too small to separate signal from noise at these precision gaps) and a prompt/rubric change aimed specifically at his tighter retest tolerance rather than the textbook BR+OCR shape both models default to.
