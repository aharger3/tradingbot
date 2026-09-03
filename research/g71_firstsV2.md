# G7.1 `firsts` — adversarial verify of the green-day claim

**Verdict: REFUTED.** The arithmetic reproduces exactly; every load-bearing
interpretation around it fails.

Scripts: `research/g71_firstsV2_greenday.py`, `research/g71_firstsV2_ddboot.py`.
Substrate: `research/bt2y_trades.json` (generated 2026-08-29T03:14:29).

## 1. The numbers reproduce, bit for bit

| arm | trades | t/day | green days | green% | totalR | meanR | maxDD | RoMaD | months green |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 shipped | 2437 | 4.91 | 288/496 | 58.1% | 1339.1 | 0.5495 | 14.71 | **91.0** | **25/25** |
| P0seq control | 1865 | 3.76 | 315/496 | 63.5% | 930.2 | 0.4988 | 27.81 | 33.5 | 24/25 |
| P3 green | 972 | **1.96** | 390/496 | **78.6%** | 472.5 | 0.4861 | 15.92 | 29.7 | **23/25** |
| P4 green/3L | 861 | 1.74 | 379/496 | 76.4% | 444.8 | 0.5166 | **12.93** | 34.4 | **23/25** |

No look-ahead in P3/P4: `g71_firsts_policy.py:walk()` evaluates `decide` on
closed-trade cum-R only, and the `ekey(c) < free` guard forces
`entry >= previous exit`. The branch is reachable and causal. Conceded.

## 2. The green days are the stopping rule's own termination condition

P3 halts the day the moment cum-R > 0, so every day that ever goes positive
ends positive **by construction**. Green-day share is not an outcome of the
policy, it is its definition.

**Null-book control** (`g71_firstsV2_greenday.py`, 30 seeds): permute every
row's `r`/`out` across the whole two years, destroying all signal identity,
all ordering quality, all engine information. P3 still returns **73.6%** green
days vs P0seq's **62.0%** — an 11.7pp gap against the claimed 15.1pp.
**77% of what "the rule buys" survives a book with zero content.** It is
stop-when-ahead arithmetic, not something the rule extracts from the engine.

Not a trade-count artifact either — fixed-k=2 (1.97 t/day, matched to P3's
1.96) gets 60.3% green. The gap is the condition, and the condition is circular.

## 3. It buys green days by breaking the gate that is actually met

- P3/P4 = **23/25 months green**. The shipped book is **25/25** — the durability
  gate, met for the first time at T0 (`TASKS.md:144`). Both promoted arms
  break it.
- P3 mean day delta vs P0seq = **−0.9228R, se 0.1459, t = −6.32** — already in
  the claim's own `_g71_firsts.json:meta.paired_vs_P0seq`. Significantly
  *negative*. TotalR 930.2 → 472.5, half the book thrown away.
- Mean R 0.4861 against the 2.0 money gate. Green days are not a gate.

## 4. The drawdown claim is path luck plus a scale artifact

Day-order bootstrap, 2000 reps (`g71_firstsV2_ddboot.py`):

| arm | actual maxDD | boot median | p5 | p95 | percentile of actual |
|---|---:|---:|---:|---:|---:|
| P0 shipped | 14.71 | 15.76 | 11.63 | 23.36 | 37% |
| P0seq | **27.81** | 16.24 | 11.99 | 24.24 | **98%** |
| P3 | 15.92 | 14.53 | 10.46 | 21.92 | 65% |
| P4 | **12.93** | 13.22 | 9.42 | 19.81 | 47% |

The control's 27.81R sits at the **98th percentile of its own day-order
bootstrap** — one unlucky sequencing, not a property of "take everything".
P4's 12.93R is the **47th percentile** — dead average. Expected-DD spread
across arms is ~3R (13.2 → 16.2), not the 15R the claim quotes.

Risk-normalised, P4 is worse than the control's *shipped* sibling and tied
with the control itself: DD as % of total R — P0 shipped **1.10%**, P4 2.91%,
P0seq 2.99%, P3 3.37%. Return-over-max-DD: shipped **91.0** vs P4 **34.4**.
P4's DD is small because it earns a third as much.

"Lowest of any non-oracle arm" is also not robust: P5b = 13.03 and
fixed-k=3 = 13.12, both inside the bootstrap noise of 12.93.

## 5. The novelty claim is false

"No existing measurement in the repo scores green-day share" —

- `research/x12_weekly_durability.py:67` — `green days %d of %d traded days`,
  under the header `--- DAILY WIN RATE (the number Scarface quotes) ---`.
  Run output: **green days 265 of 415 traded days = 63.9%**, plus best/worst
  month by green-day rate and months-at-100%.
- `research/x12_selectivity.py:54` — `green day %3d/%3d (%.0f%%)` on every arm.

Same rig family (the 2-year book), already committed.

## 6. Book provenance discrepancy

`research/t0_ratified_rebaseline.md:24` documents `research/bt2y_trades.json`
as "the AFTER book (75,953 signals, **2,595 traded**, 500 sessions)".
The file on disk carries `signals: 76019, traded: 2437, halted: 857,
loss_halt: True` — it was regenerated after R30/R31 landed (T23). So the
claim was scored on a **post-T23** book, newer than the published one, but
its "shipped book 288/496" describes a book no published figure covers, and
`DIRECTION.md:20`'s headline (2,595 trades / +0.5481R) is stale against it.
