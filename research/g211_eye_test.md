# W9 -- vision eye-test (g211)

No -- reading the blind, level-annotated chart alone does not reproduce his S marks materially above the 30.5% baseline: both readers land near or only marginally above it, and neither model's bootstrap band clears the baseline.

Inputs: `research/g210_cards/index.json` (his grades, 100 cards, 34 marked S = 34.0% of the deck) against two independent readers -- Claude Haiku and Claude Sonnet -- each grading S/A/C/none off the same blind PNG chart cut at the entry bar plus the rulebook digest, with no access to his answer. Script: `research/g211_eye_test.py`. Reader outputs: `research/g211_reads_haiku.json`, `research/g211_reads_sonnet.json`.

Note: the S base rate in this 100-card deck is 34%, not 30.5% -- the 30.5% figure is the graded-day precision baseline named in the W9 spec row (`omen-9-0-spec.md`), used here as-given, not re-derived.

## Confusion matrices (S vs not-S)

| | his S | his not-S |
|---|---:|---:|
| **Haiku says S** | 10 | 16 |
| **Haiku says not-S** | 24 | 50 |

| | his S | his not-S |
|---|---:|---:|
| **Sonnet says S** | 4 | 6 |
| **Sonnet says not-S** | 30 | 60 |

## Precision / recall / agreement

| model | precision (S) | recall (S) | exact S/A/C/none agreement | bootstrap 95% band | clears 30.5% baseline? |
|---|---:|---:|---:|---:|---:|
| Haiku | 38.5% | 29.4% | 45/100 (45.0%) | [20.0%, 58.3%] | False |
| Sonnet | 40.0% | 11.8% | 45/100 (45.0%) | [10.0%, 72.7%] | False |

Baseline: 30.5% (30.5% graded-day precision, per the W9 spec row). Bootstrap: 10,000 resamples of the 100 cards with replacement, 95% percentile interval on precision-for-S.

Both readers land a few points above the point-estimate baseline (38.5% and 40.0% vs 30.5%), but each is built on a small number of S calls (26 for Haiku, 10 for Sonnet) and the bootstrap band on both spans well below and well above the baseline -- the point estimate is not distinguishable from the baseline at this sample size.

## 2 of 2 false positives -- both models said S, he said none

### HOOD_2025-07-01
- **Haiku:** ORH break with OCR retest confluence; strong displacement and bull progression with immediate buyback of the retest candle. Early-window trade with clear level respect.
- **Sonnet:** The 09:51-09:52 displacement candles break the PDH/ORH confluence level clean, and the 09:53 candle retests it in one bar, wicking under but closing back on the correct side — no stale retest, no rejection, level respected. Confluence of the two stacked levels plus bull PA sitting above 5 of the 6 levels I watch each earn a +1, so with zero downgrades tripped this floors at S, long.

### IREN_2025-09-25
- **Haiku:** Displacement break above 46.00 at 09:50 rallies to 46.80; retest at 09:56 respects level close without chop. Entry on retest close; stop on broken level, clean setup, no downgrades.
- **Sonnet:** Displacement candle at 09:49-09:50 clears ORH (~46.00) with force out of a clean uptrend off the 09:39 low, then the 09:55 candle retests back into the level (low ~46.10, within tolerance) and closes back above without ever closing through it — level respected, retest not stale. No downgrade variable trips: no exhaustion, no chop on the level, counter-trend candles are small and bought back, so this grades S.

## 3 of 3 misses -- he said S, both models said none

### MSTR_2025-08-26
- **Haiku:** The 09:32 displacement candle peaked below ORH without breaking a defined level. Counter-trend candles (five consecutive reds) are not respected and lack OCR confluence or a clear retest hold pattern by the cut.
- **Sonnet:** No level has broken yet — price wicked up toward PMH/ORH (~345.3-345.7) at 09:34-09:36 but never closed through, so there is no BR and no retest to trade; it's chopping between ORH/PMH above and ORL/PML below with no displacement candle establishing a level. No level, no BR — refuse the trade at this cut.

### MSTR_2026-03-13
- **Haiku:** Exhaustion filter (3-point HOD-to-LOD move before cut) disqualifies. Counter-trend bounce candles (09:36–09:38) rejected immediately with no BR+OCR confluence at the cut.
- **Sonnet:** Price broke PMH (~144.6) and then ORL (~143.65) and ran straight down without ever coming back to retest either level — variable 7, no retest — so there is no confirmation-regime close at a level to trigger on. The 09:37–09:41 chop sits below both broken levels, not on them, so this is a refusal at the cut, not a C: wait for price to reclaim back up to ORL or PMH and close there before there's anything to trade.

### BABA_2026-06-12
- **Haiku:** ORH break-and-retest at 09:32-09:33 is stale; price trades much lower without displaced break structure. No fresh level respected at cut; price action choppy through opening range.
- **Sonnet:** Price is chopping inside its own opening range (ORH ~112.65 / ORL ~112.1), closing on and around ORL repeatedly with no clean break of any of the six levels — that's disrespect/chop, not a setup. No level has broken and retested, so there's no BR to grade and nothing OCR has manufactured either.

## What this means for a vision classifier

- Neither reader's precision-for-S clears the 30.5% baseline with statistical confidence at n=100 -- the bootstrap lower bound sits below the baseline for both (Haiku 20.0%, Sonnet 10.0%). A 100-card sample cannot settle this; it can only say the signal is not obviously present, not that it is absent.
- Recall for S is low for both models (29.4% for Haiku, 11.8% for Sonnet) -- most of his S cards read as A or none from the chart alone. Sonnet in particular grades conservatively (fewer S calls, higher bar for 'no downgrades'), trading recall for a marginally higher precision.
- The false positives read as textbook clean break-and-retests by rulebook mechanics -- both models describe zero downgrade variables tripped. What they miss is whatever he sees beyond the rulebook: the qualitative chart judgement (candle force, how a level *feels* respected) that the eight-variable digest does not capture in words.
- The misses lean toward exhaustion/no-clean-level reads where he apparently still saw an S -- consistent with the project's standing finding that his time buys the eye test and his calls are not fully reducible to the rulebook.
- Bottom line: this single-pass read (no examples, no fine-tuning, first-look grading) does not by itself justify building a vision classifier. It also does not rule one out -- the signal-to-noise here could reflect prompt/rubric quality rather than the modality. A larger sample, and/or a few-shot or fine-tuned reader, would be needed before spending build time on this lane.
