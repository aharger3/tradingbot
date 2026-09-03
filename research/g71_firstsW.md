# G7.1 / `firstsW` — adversarial verify of the `firsts` durability claim

**Verdict: NOT REFUTED.** Every load-bearing number reproduces exactly from
`research/bt2y_trades.json` with an independently written implementation
(minute arithmetic, not the report's tuple keys). Four defects in the wording
and one attribution gap, none of which overturn the claim.

Scripts: `research/g71_firstsW_recheck.py` (re-derivation + causality
sensitivity + time-weighted concurrency), `research/g71_firstsW_fragility.py`
(tie-break and exposure controls), `research/g71_firstsW_conc.py` (concurrency
after de-duplication).

## Reproduced, exactly

| arm | n | WR | R/trade | total R | months green | red months |
|---|---:|---:|---:|---:|---:|---|
| P0 shipped | 2437 | 49.50% | +0.5495 | +1339.1 | **25/25** | none |
| P0u counted, halt off | 3294 | 46.76% | +0.5037 | +1659.2 | 25/25 | none |
| P0seq control | 1865 | 46.31% | +0.4988 | +930.2 | 24/25 | 2025-09 −8.72 |
| P1 | 496 | 54.86% | +0.6115 | +303.3 | **22/25** | 2025-06 −3.91, 2025-09 −6.93, 2025-10 −4.36 |
| P2 | 705 | 52.49% | +0.5668 | +399.6 | **22/25** | 2025-05 −3.91, 2025-09 −7.27, 2025-10 −5.90 |
| P3 | 972 | 48.81% | +0.4861 | +472.5 | **23/25** | 2025-05 −8.74, 2025-09 −9.06 |
| P4 | 861 | 50.35% | +0.5166 | +444.8 | **23/25** | 2025-05 −3.91, 2025-09 −10.89 |

Robustness: 247 day-minutes carry more than one candidate, so "first" has an
arbitrary tie-break. Over 40 random tie-break orders P1 = 22/25 always,
P2 = 22/25 always, P4 = 23/25 always, P3 = 22–23 (median 23). Forcing a
1-minute gap between exit and next entry changes nothing; allowing overlap
makes it worse (P2 21, P4 22). No look-ahead: P1–P4's stop predicates read only
`n`, wins, losses and cumulative R of already-CLOSED trades. All branches
reachable (P3 takes 972 trades against P1's 496, so `cum > 0` fires).

## Four defects in the wording

1. **"holds 2.37 positions at once on average" is a mean of daily MAXIMA**, not
   an average holding — the JSON key is literally `p0_max_concurrent_positions`.
   The genuine time-weighted average is **1.087** positions while any position
   is open and **0.202** across the 391-minute RTH day (39,270 position-minutes
   over 496 days). The claim overstates the average by ~2.2×.
2. **"18 at peak" is inflated by duplicate rows.** 86 shipped rows (3.5%) share
   a `(day, sym, minute)` key and 12 are byte-identical on
   `(day, sym, minute, bars, R)` — e.g. 2025-08-22 carries INTC 10:02 bars=116
   r=0.425 twice. Collapse to one row per symbol-minute and the peak is **12**;
   mean-of-daily-max only moves 2.37 → 2.29, days with 2+ 368 → 366.
3. **"2025-09 is red under every arm including the control" is false as
   written.** P0 = **+3.92R**, P0u = +2.55R, ORACLE green. The true statement is
   "red under every one-position-at-a-time arm". The ORACLE is the direct
   counterexample: one trade a day, zero concurrency, 25/25 green — so a
   single-position book *can* clear 2025-09 given selection edge.
4. **The book is not the 2,595-trade post-T0 book.** It is 76,019 signals /
   3,294 counted / **2,437 traded** with R31 loss-halt ON, generated
   2026-08-29T03:14:29, committed at `145d564e` (T23) — newer than T0's
   75,953-signal / 2,595-traded book, not older. P0 on this book still gives
   **25/25**, so the "gate OMEN currently meets" baseline is intact, but
   `DIRECTION.md:22` describes a book the table is not measured on.

## The attribution gap

The claim reads as "his rule costs the gate". The mechanism is the
single-position constraint, not the stop rule:

| policy | months green |
|---|---:|
| P0 shipped (concurrent) | 25/25 |
| P0seq (one at a time, no stop rule) | 24/25 |
| RANDOM one-per-day × 200 seeds | mean **21.41**, median 21, min 17, max 25, P(25/25) = **2%** |
| RANDOM-order sequential × 200 seeds | mean 23.30, min 23, max 24 |
| P1 / P2 | 22/25 |
| P3 / P4 | 23/25 |

A **random** one-trade-a-day policy averages 21.4/25 and reaches 25/25 two
times in a hundred. P1's 22/25 is *above* that median; P3/P4's 23/25 is above it
by two. So the honest sentence is: **any one-position-a-day book loses the
durability gate on this data — Austin's rule loses it slightly less than chance
does.** Only 1,865 of 3,294 counted rows (56.6%) are even reachable one at a
time. The report's RANDOM row leaves `months_green = -1`
(`g71_firsts_policy.py:284`), which is exactly the control that would have
made this visible.

## Corrected claim

> Adopting the rule costs the one gate OMEN currently meets: months green falls
> 25/25 → 22/25 (P1, P2) or 23/25 (P3, P4), on the current 2,437-traded book
> (`145d564e`), robust to tie-break and causality-rule perturbation. 2025-09 is
> red under every **one-position-at-a-time** arm including the P0seq control
> (−8.7R), while shipped P0 is +3.9R there — its 25/25 is bought by holding
> multiple positions (peak 12 distinct symbols on 2025-08-22, 2+ open at some
> point on 368 of 496 days, time-weighted average 1.09 while open), not by
> per-trade edge. But the cost is an **exposure** effect, not a property of his
> stop rule: a random one-trade-a-day policy averages 21.4/25.
