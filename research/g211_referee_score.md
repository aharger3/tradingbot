# W9 referee — the vision eye-test is void: the answer is printed on every chart

**REFUTED.** The g211 eye-test is not blind. Every card's PNG carries the title
`SYMBOL  DATE  (1-min, cut HH:MM)`, and the cut time is a **perfect** function of Austin's grade:
all 34 cards he graded S are cut at his entry minute, all 66 he refused are cut at exactly 10:00.
A reader that ignored the candles entirely and answered "S if the title does not say 10:00" would
score **precision 1.000, recall 1.000**. Whatever this deck measured, it cannot be called a blind
read of the chart — and the arithmetic that was reported is also scored against the wrong null.

Produced by `research/g211_referee_check.py` (independent recompute, 20,000-resample bootstrap)
plus a re-run of `research/g211_eye_test.py`. No money, no fill, no market data — label agreement only.

## 1. Leakage — fatal, and it is in the image

`research/g210_render_cards.py:199` draws
`ax1.set_title("%s  %s  (1-min, cut %s)" % (symbol, day, cut_t[:5]))`, and line 179 sets
`cut_t = entry_t if entry_t else "10:00:00"` where `entry_t` comes from `notes.min` — the minute he
wrote down **because he took the trade**. The script's own docstring says it: *"Cards graded 'no'
rarely carry a min; treat that as blind to 10:00."* The label is the cut, the cut is the title.

| "S if cut != 10:00" reader | TP | FP | FN | precision | recall |
|---|---:|---:|---:|---:|---:|
| against his 100 grades | 34 | 0 | 0 | **1.000** | **1.000** |

Three separate carriers of the same fact on each image: the printed cut time, the x-axis tick
labels, and the candle count (S cards carry 5 to 50 candles, median 13; every refused card carries exactly 31). The
`g210_render_cards.md` claim "No grade or engine field is drawn on any PNG" is true word-for-word
and false in effect.

**In fairness to the two readers: neither exploited it.** Haiku put 17 of its 39 S-calls on
leaked cards, Sonnet 5 of 13 — both close to chance, because neither was told the correlation
existed. So the reported numbers are not inflated by the leak. They are simply unusable as
evidence about vision, because the experiment cannot distinguish a model reading price action from
a model reading a caption, and any future reader — a prompt tweak, a fine-tune, a smarter model —
would find the caption first.

Symbol and date are also printed, so a model with memorised market history has a second channel.
Secondary next to the cut time, but it is there.

## 2. The baseline comparison is not apples-to-apples

`research/g211_eye_test.py:28` hardcodes `BASELINE_PRECISION = 0.305`. That number is **graded-day
precision on the engine's one-trade-a-day pick, 18 of 59 graded days**. This test is **card-level
S-precision on a deck curated to 34.0% S**. Different unit, different denominator, different
population — the same class of error the morning report already flagged for the 39.5% figure.

The honest null here is the deck's own S rate. The script even computes it (`s_rate = 0.340`),
prints it, and then compares to 0.305 anyway.

| reader | S-calls | precision | recall | F1 | one-sided binomial vs 34.0% |
|---|---:|---:|---:|---:|---:|
| Haiku | 39 | 0.436 | 0.500 | 0.466 | **p = 0.137** |
| Sonnet | 13 | 0.385 | 0.147 | 0.213 | **p = 0.469** |
| trivial "always S" | 100 | 0.340 | 1.000 | **0.507** | — |

**A reader that says S on all 100 cards beats both models on F1.** Neither model is distinguishable
from that null. The `.md`'s "Both point-estimate precisions clear the 30.5% baseline" is an artifact
of the wrong constant; against 34.0% Haiku is +9.6pp at p=0.14 and Sonnet is +4.5pp at p=0.47.

## 3. The bootstrap reproduces, and it was never a test

`bootstrap_precision_band` resamples the 100 cards with replacement and recomputes S-precision —
a legitimate percentile CI, and it reproduces: my 20,000-draw run gives Haiku [0.280, 0.595] against
the committed [0.286, 0.600], Sonnet [0.118, 0.667] against [0.143, 0.667].

But a CI on the estimate is not a test against a null, no multiplicity correction is applied across
the two models, and the band the `.md` reasons about straddles the *wrong* constant. Both bands
also straddle 34.0%, so the corrected reading is the same direction and stronger: **no result.**

## 4. Reproducibility — the reads have no script

`research/g211_reads_haiku.json` and `..._sonnet.json` were committed in `50d3f7d0` with no harness.
There is no committed script that opens a PNG, calls a model, and writes those rows; no model id, no
prompt text, no temperature, no timestamps in the files. `CLAUDE.md`: *"If you publish a number,
commit the script that made it."* The reads are internally clean — 100 unique card_ids each, no
missing, no extras, grades spread S/A/C/none — but they cannot be regenerated or audited, and the
prose in them shows the readers did see the cut time (e.g. Sonnet on CRM: *"by the 09:40 cut"*).

## 5. What has to change before this modality is worth re-running

1. **Cut every card at the same clock time** (10:00, or a fixed 30 bars), or draw the cut from
   something that is not his answer. Nothing on the image may vary with the label.
2. **Strip the title.** No symbol, no date, no cut, no axis clock labels — index by an opaque card id.
3. **Score against the deck's own S rate** (34.0% here), and report a permutation or binomial test,
   not a naked point estimate beside a constant from a different measurement.
4. **Commit the reader harness** — model id, prompt, the rulebook digest hash, one row per call.
5. **Power.** At 34 positives, a real effect under +15pp is invisible; size the deck to the effect
   worth acting on before spending the reads.

Nothing in the g211 file needs deleting — it is a real negative and the code is honest work with a
design flaw. The single sentence that should not survive is *"both point-estimate precisions clear
the 30.5% baseline"*.
