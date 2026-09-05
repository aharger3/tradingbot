# g154 F5 -- displacement-forgiven-unless-exempt

**One sentence: not a survivor -- H1 -11/day, H2 -11/day** on the honest, retest-on book, one-trade-a-day unit, size-gated.

Predicate: KEEP if disp tag / confluence=yes / et<=09:45 (flag-at-open proxy). DROP if nodisp (tag or downgrade) AND confluence=no AND et>09:45. **HTF-thesis exemption has no field and is not modeled** -- this measurement is blind to it.

Fired base rates (status=='fired', 10830 rows, NOT the one-a-day unit): nodisp tag 8014, disp tag 2285, confluence=yes 8369.

candidates/day (raw arrival stream, whole pool): **16.52**

## Money -- one trade a day, whole pool, size-gated

| arm | split | $/day | mean R | win | months green | max DD | fires/day |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| baseline | H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| baseline | H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |
| candidate | (whole book) | $22.86 | +0.023 | 45.8% | 13/25 | $22950 | 0.998 |
| candidate | H1 | $124.68 | +0.125 | 49.2% | 9/12 | $13979 | 1.000 |
| candidate | H2 | $-78.95 | -0.079 | 42.3% | 4/13 | $22950 | 0.996 |

H1/H2 split at **2025-09-01**. delta $/day: H1 -11.03, H2 -11.10.

## S recall

| set | n | baseline | candidate |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 44.1% |
| bar-backed S days (canonical_pool) | 341 | 49.6% | 46.0% |

## Precision (fired days graded S / fired days graded at all)

| arm | precision | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate | 30.0% | 18 / 60 |

Survivor rule: H1 AND H2 both improve $/day or precision, and recall on both S-day panels does not fall below baseline. **Result: NOT a survivor.**
