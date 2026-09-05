# g154 F5 -- or-break-without-retest

**One sentence: not a survivor -- H1 +9/day, H2 +18/day** on the honest, retest-on book, one-trade-a-day unit, size-gated.

Predicate (ARM, OR-specific): DROP if level in (OR high, OR low) AND 'no_retest' in downgrades. Predicate (CONTROL, blanket): DROP if 'no_retest' in downgrades, any level. Pure refusal-indicator -- there is no keep/S-indicator half.

Fired base (status=='fired', 10830 rows, NOT the one-a-day unit): OR high **1140**, OR low **1037**. **2711** fired rows carry 'no_retest' in downgrades regardless of level -- RETEST_REQUIRED caps grade at fire time, it does not veto the fire.

candidates/day (raw arrival stream, whole pool): **16.52**

## Money -- one trade a day, whole pool, size-gated

| arm | split | $/day | mean R | win | months green | max DD | fires/day |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| baseline | H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| baseline | H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |
| candidate (OR-specific) | (whole book) | $47.44 | +0.047 | 46.9% | 13/25 | $21405 | 1.000 |
| candidate (OR-specific) | H1 | $144.27 | +0.144 | 50.0% | 9/12 | $13979 | 1.000 |
| candidate (OR-specific) | H2 | $-49.39 | -0.049 | 43.8% | 4/13 | $21405 | 1.000 |
| control (blanket) | (whole book) | $37.92 | +0.038 | 46.8% | 13/25 | $19455 | 0.998 |
| control (blanket) | H1 | $128.69 | +0.129 | 49.6% | 9/12 | $18286 | 1.000 |
| control (blanket) | H2 | $-52.85 | -0.053 | 44.0% | 4/13 | $19455 | 0.996 |

H1/H2 split at **2025-09-01**. delta $/day (OR-specific arm vs baseline): H1 +8.56, H2 +18.46.

## Is the OR specificity real?

OR-specific arm $/day **$47.44** vs blanket control $/day **$37.92**; OR-specific precision **30.5%** vs blanket precision **32.2%**. **OR SPECIFICITY REAL** -- the OR-specific arm beats the blanket one, so the claimed OR specificity is supported.

## S recall

| set | n | baseline | candidate (OR-specific) | control (blanket) |
|---|---:|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 44.1% | 44.1% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 48.7% | 47.2% |

## Precision (fired days graded S / fired days graded at all)

| arm | precision | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate (OR-specific) | 30.5% | 18 / 59 |
| control (blanket) | 32.2% | 19 / 59 |

Survivor rule: H1 AND H2 both improve $/day or precision (OR-specific arm vs baseline), and recall on both S-day panels does not fall below baseline. **Result: NOT a survivor.**
