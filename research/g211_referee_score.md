# W9 referee (scoring) — REFUTED: the eye-test measures a caption, against the wrong null, on a reader that does not agree with itself

**REFUTED.** Nothing in `research/g211_eye_test.md` may be quoted as evidence about vision. Three
independent defects, any one of which is fatal: (1) Austin's grade is printed on every chart — the
cut time is his answer, and a reader that ignores the candles scores **1.000 precision / 1.000
recall**; (2) the 30.5% comparison is a different measurement on a different population — the honest
null is this deck's own 34.0% S rate, against which **neither reader is distinguishable from chance**
(Haiku p=0.385, Sonnet p=0.459) and a trivial "always S" reader **beats both on F1**; (3) the reader
data was silently replaced between two commits under the same filenames, and the same model reading
the same 100 cards agreed with its own earlier pass on only **41 of 100** grades — the instrument's
run-to-run noise is several times larger than the effect being claimed.

Produced by `research/g211_referee_score.py` (my own recompute — it does not import the g211 script)
plus a clean re-run of `research/g211_eye_test.py`. Label agreement only: no money, no fill, no
market data, so no fill convention applies. This file supersedes the earlier referee pass committed
in `86d81171`, whose arithmetic was computed on the reads that commit `e326b1cd` later overwrote;
that pass's conclusion is upheld, its numbers are not the current ones.

## What reproduces

`research/g211_eye_test.py` re-runs clean on the committed reads. My independent recompute lands on
the same confusion matrices, and the bootstrap reproduces at a different seed and draw count (Haiku
committed [0.200, 0.583] vs mine at seed 11/20k [0.200, 0.577] and seed 99/50k [0.200, 0.579];
Sonnet committed [0.100, 0.727] vs mine [0.100, 0.750] both times). The code is honest and the
arithmetic is right. **The design is what fails.**

## 1. The answer is printed on the chart — verified independently from the index alone

| his grade | cards | cut time | 1-min candles on the panel |
|---|---:|---|---|
| S | 34 | his entry minute, 09:34–10:19, 19 distinct values, **never 10:00** | 5 to 50, median 13 |
| none | 66 | **10:00:00, all 66** | **exactly 31, all 66** |

Zero overlap in either channel. The title (`SYMBOL DATE (1-min, cut HH:MM)`), the x-axis clock, and
the candle count each carry the label perfectly.

| trivial reader | precision | recall |
|---|---:|---:|
| "S iff the cut is not 10:00" | **1.000** (34/34) | **1.000** (34/34) |

**In fairness to the readers, neither exploited it.** Haiku placed 10 of its 26 S-calls on
cut≠10:00 cards against a chance expectation of 8.8; Sonnet 4 of 10 against 3.4. So the reported
numbers are not inflated. They are unusable for a different reason: the experiment cannot separate
a model reading price action from a model reading a clock, so no future reader — a better prompt, a
fine-tune, a stronger model — can be scored on these PNGs either. **64 of Sonnet's 100 written
reasons contain the word "cut"**: the readers demonstrably saw the field that carries the answer.

Symbol and date are also on every image and in every filename, giving a model with memorised market
history a second, weaker channel. It cannot be ruled out from these files.

## 2. The baseline is the wrong quantity

`research/g211_eye_test.py:28` hardcodes `BASELINE_PRECISION = 0.305`. That is **graded-day
precision on the engine's one-trade-a-day pick, 18 of 59 graded days** (morning report, line 70).
This test is **card-level S-precision on a deck curated to 34.0% S**. Different unit, different
denominator, different population — the same error the morning report itself flags at line 83 for
the `>39.5%` target. The script computes the deck's own rate, prints it, and compares to 0.305 anyway.

| reader | S-calls | precision | recall | F1 | one-sided binomial vs 34.0% | label-permutation p |
|---|---:|---:|---:|---:|---:|---:|
| Haiku | 26 | 0.385 | 0.294 | 0.333 | **0.385** | 0.373 |
| Sonnet | 10 | 0.400 | 0.118 | 0.182 | **0.459** | 0.467 |
| trivial "always S" | 100 | 0.340 | 1.000 | **0.507** | — | — |

Against the honest null, Haiku is +4.5pp and Sonnet +6.0pp, both a coin-flip away from nothing, and
**a reader that says S on all 100 cards beats both on F1**. The `.md` sentence "Both readers land a
few points above the point-estimate baseline" is an artifact of the wrong constant and should not
survive. The `.md` does note the 34% rate in passing, and its own bottom line ("does not by itself
justify building a vision classifier") lands in the right place — by luck of the direction, not by
the comparison it made.

## 3. The bootstrap is sound and was never a test

`bootstrap_precision_band` is a legitimate percentile CI and it reproduces (above). But a CI on an
estimate is not a test against a null; no multiplicity correction is applied across the two readers;
and the band the `.md` reasons about straddles the wrong constant. Both bands also straddle 34.0%,
so correcting the null does not rescue anything — it points the same way, harder.

## 4. New this pass: the reads were swapped, and the reader does not agree with itself

`research/g211_reads_{haiku,sonnet}.json` were committed in `50d3f7d0`, then **overwritten** in
`e326b1cd` ("rerun with task-provided reader data"). Every one of the 200 rows has different prose;
the grades moved on 59 of 100 Haiku cards and 51 of 100 Sonnet cards. Two passes of the same model
over the same images, scored by the same script:

| reader | exact S/A/C/none agreement, pass 1 vs pass 2 | S vs not-S agreement | precision | recall |
|---|---:|---:|---|---|
| Haiku | **41/100** | 67/100 | 0.436 → 0.385 | 0.500 → **0.294** |
| Sonnet | **49/100** | 87/100 | 0.385 → 0.400 | 0.147 → 0.118 |

Haiku's recall moved 20.6 points between two runs of the same experiment. The claimed effect over
the correct null is 4.5 points. **The measurement is noisier than the thing it is measuring**, and
which numbers `g211_eye_test.md` reports depends only on which pass happened to be committed last.
Neither pass is more valid than the other, because neither has a harness.

## 5. Reproducibility — there is no reader harness

No committed script opens a PNG, calls a model, and writes those rows. No model id, no prompt text,
no rulebook-digest hash, no temperature, no timestamps. `CLAUDE.md`: *"If you publish a number,
commit the script that made it."* The reads are internally clean — 100 unique card_ids each, no
missing rows, no extras, grades spread across S/A/C/none — but they cannot be regenerated or
audited, which is exactly how a silent swap of the entire dataset went unnoticed.

## What has to change before this modality can be scored at all

1. **Cut every card at the same clock time** — or draw the cut from a distribution independent of
   his grade, e.g. sample each refused card's cut from the 34 observed S cut minutes. Nothing on the
   image may vary with the label: cut, candle count, axis range, or anything else.
2. **Strip the title and the axis clock.** Index by an opaque card id; keep symbol, date and cut in
   `index.json`, and move `index.json` (which carries `his_grade`) out of the directory a reader is
   pointed at.
3. **Score against the deck's own S rate**, with a binomial or permutation test and a multiplicity
   correction across readers — never a point estimate beside a constant borrowed from a different
   measurement.
4. **Commit the reader harness**, one row per call with model id, prompt and digest hash, and run it
   at least three times per reader so the run-to-run band is reported alongside the effect.
5. **Power.** At 34 positives with ~20pp of self-disagreement, nothing under roughly +15pp is
   visible. Size the deck to the effect worth acting on before spending the reads.

The g211 file is real work and a real negative; nothing needs deleting. What it does not contain is
evidence, in either direction, about whether Austin's S signal is visual.
