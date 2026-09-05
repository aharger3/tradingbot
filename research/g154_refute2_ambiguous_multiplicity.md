# g154 refuter #2 -- ambiguous-stop-candidates is REFUTED

**What is different now:** the rule's numbers reproduce exactly, but the survivor verdict rests on a single symbol-day, the money read is worse in both halves, and a rule that drops a random 9% of candidates passes the same gate about as often -- with 25 candidates tried, that is what multiplicity looks like, not an edge.

Fill: entry = signal bar CLOSE; stops per stop_rule.stop_fill_price as booked in bt2y_trades_retest_on.json; size-gated on signal_runner.min_risk_floor via omen_metrics._row_is_sizeable; 1R = $1,000; unit = one-trade-a-day first_of_day.

Scripts: `research/g154_rule_ambiguous-stop-candidates.py` (reproduced verbatim, byte-identical output) and `research/g154_refute2_ambiguous_multiplicity.py` (this file).

## 1. The arm barely moves the book

Of 498 sessions, dropping ambiguous candidates changes the day's pick on **6**.

| day | baseline pick | his grade | $ | arm pick | his grade | $ |
|---|---|---|---:|---|---|---:|
| 2024-09-18 | IWM | none | 274.47 | AVGO | none | -1000.0 |
| 2024-09-23 | HOOD | ungraded | -8.82 | PLTR | ungraded | -310.18 |
| 2025-05-16 | COIN | ungraded | 368.36 | NVDA | ungraded | -58.61 |
| 2025-06-17 | PLTR | ungraded | -1000.0 | AMD | ungraded | 952.62 |
| 2025-06-26 | NFLX | ungraded | 37.84 | COIN | S | -1000.0 |
| 2026-08-04 | PLTR | ungraded | 760.5 | INTC | ungraded | -141.67 |

The claim survives ONLY on precision, because $/day gets worse in both halves (H1 -4.36, H2 -3.62). Precision goes 18/59 to 19/60 -- **one card**. The only swap that touches a graded day:

| day | from | to |
|---|---|---|
| 2025-06-26 | NFLX (ungraded) | COIN (S) |

Note the direction. The rule removed **zero** wrongly-fired graded days. It raised precision by ADDING one graded-S day to the numerator and the denominator at the same time -- and that added S day lost $1,000.

## 2. Paired bootstrap on sessions (4000 resamples)

| quantity | 95% CI | mean |
|---|---|---:|
| delta $/day overall | [-14.1, 7.38] | -3.99 |
| delta $/day H1 | [-23.6, 17.02] | -4.41 |
| delta $/day H2 | [-11.52, 0.0] | -3.58 |
| delta precision (pp) | [0.0, 3.94] | 1.19 |

The precision gain is positive in only **65.0%** of resampled books. It is not distinguishable from zero, because it is one card.

## 3. Multiplicity: a placebo passes the same gate

Drop a uniformly random 9.19% of candidates -- the same drop rate the ambiguity flag has, carrying no information at all -- then re-run the identical selection and the identical survivor gate, 3000 times.

| placebo outcome | share |
|---|---:|
| precision improves | 64.8% |
| $/day improves in BOTH halves | 18.0% |
| **passes the survivor gate** | **63.9%** |

With **25 candidates tried** and no multiplicity correction anywhere in F5, the chance at least one pure placebo clears this gate is **100.0%**, and the expected number of placebo survivors is **16.0 of 25**.

## Verdict: REFUTED

- Every number reproduces exactly: $33.93 -> $29.94, H1 -4.36, H2 -3.62, precision 30.5 -> 31.7, recall_100 5.9 -> 5.9. No lookahead found -- every stop candidate is read at index <= entry_i, and the order-block call is sliced `candles[:entry_i+1]`.
- The survivor bit is an OR gate satisfied by a +1.2pp precision move that is one symbol-day out of 498, and that day was a $1,000 loser.
- $/day is worse in both halves, which is the only direction the money read agrees on.
- An information-free placebo passes the same gate 63.9% of the time; across the 25 candidates tried, 16.0 placebo survivors are expected by chance.
