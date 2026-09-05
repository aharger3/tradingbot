# g154 -- F5 ambiguous-stop-candidates

**What is different now:** measured Austin's rule that an ambiguous stop (two disagreeing stop candidates, or a muddled structure) is a downgrade in itself, as a refusal-indicator arm over the one-trade-a-day book.

## Ambiguous rate

9.19% of all 8227 fired/halted candidates are flagged ambiguous (8176 had a computable avg_rng).

### Against his S/A/C/none grades

| grade | n candidates | n ambiguous | pct ambiguous |
|---|---:|---:|---:|
| ungraded | 7255 | 659 | 9.1% |
| none | 405 | 38 | 9.4% |
| S | 295 | 31 | 10.5% |
| A | 205 | 25 | 12.2% |
| C | 54 | 2 | 3.7% |
| B | 13 | 1 | 7.7% |

### Against realized R

| bucket | n | mean R |
|---|---:|---:|
| ambiguous | 756 | -0.057 |
| clean | 7471 | -0.023 |

## Baseline (no drop) vs arm (drop ambiguous)

| arm | pop | n | $/day | mean R | win | green/mo | max DD |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | overall | 498 | $33.93 | 0.0339 | 46.5% | 13/25 | $-21404.68 |
| baseline | H1 | 249 | $135.71 | 0.1357 | 49.6% | 9/12 | $-13978.64 |
| baseline | H2 | 249 | $-67.85 | -0.0678 | 43.4% | 4/13 | $-21404.68 |
| arm | overall | 498 | $29.94 | 0.0299 | 45.9% | 12/25 | $-21468.32 |
| arm | H1 | 249 | $131.35 | 0.1313 | 48.8% | 8/12 | $-13978.64 |
| arm | H2 | 249 | $-71.47 | -0.0715 | 43.0% | 4/13 | $-21468.32 |

candidates/day: 16.52 -- fires/day baseline: 1.0 -- fires/day arm: 1.0
S recall (100-card, 34 S): baseline 5.9% (2/34) -- arm 5.9% (2/34)
S recall (all bar-backed): baseline 5.2% (18/347) -- arm 5.5% (19/347)
precision: baseline 30.5% (18/59) -- arm 31.7% (19/60)

## Survivor verdict

H1 delta $/day: -4.36 -- H2 delta $/day: -3.62
**survivor = True**

survivor = True only if (H1 AND H2 both improve $/day) OR precision improves, AND S-recall-100 does not fall below baseline. 'On the adverse side of entry with a gap between' is read as: exclude a candidate that sits on the WRONG side of entry (not a live competing stop) before testing the >1x avg_rng gap -- this is how 'neither nests inside the other' is operationalized here, since two same-side points on a line can't nest, they can only be near or far. Ambiguity is scored over the FULL candidate population (not just first-of-day picks) for the rate-vs-his-grades and rate-vs-realized-R reads; the $/day arm applies the drop only inside first-of-day selection, per the row's arm instruction.
