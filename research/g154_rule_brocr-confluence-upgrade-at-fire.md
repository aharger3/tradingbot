# g154 -- brocr-confluence-upgrade-at-fire (F5)

One sentence: filtering the one-trade-a-day arm to fired candidates with BR+OCR confluence (8369 of 10830 fired rows, 77.3%) does NOT clearly improve $/day or precision vs the unfiltered baseline on both halves, so this candidate is NOT a survivor.

| arm | $/day | mean R | win | green months | max DD | fires/day | precision | recall_100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (first-of-day) | $33.94 | 0.0339 | 0.4639 | 13/25 | -21404.68 | 1.0 | 0.3051 | 0.0588 |
| S-indicator (confluence==yes) | $30.83 | 0.0309 | 0.4829 | 12/25 | -16993.59 | 0.998 | 0.3036 | 0.1471 |
| inverse (confluence==no) | $-1.78 | -0.0019 | 0.4292 | 13/25 | -37210.77 | 0.9217 | 0.3333 | 0.0294 |

recall_all_s_days (all bar-backed S days, marks_pool.s_days()): baseline 0.0519, arm 0.049, inverse 0.0548

## H1 (< 2025-09-01) / H2 (>= 2025-09-01) split

| arm | H1 $/day | H2 $/day | H1 green | H2 green |
|---|---:|---:|---:|---:|
| baseline | $135.71 | $-67.84 | 9/12 | 4/13 |
| S-indicator | $91.06 | $-29.41 | 7/12 | 5/13 |
| inverse | $80.05 | $-83.61 | 8/12 | 5/13 |

H1/H2 delta vs baseline (S-indicator arm): $-44.65 / $38.43

## fire-time ladder fold (confluence=='yes' fired rows, engine A+/A/B/C/X)

before: {'B': 3959, 'C': 6808, 'A': 63}

after +1-capped upgrade: {'B': 6300, 'C': 1481, 'A': 2993, 'A+': 56}

candidates/day (pre-selection, confluence=='yes' fired rows): 16.8052

sanity check -- confluence=='yes' agrees with 'brocr' in tags on 99.29% of fired rows (not literally identical; predicate uses confluence=='yes')

survivor = False (H1 and H2 both improve $/day or precision, recall_100 not below baseline)
