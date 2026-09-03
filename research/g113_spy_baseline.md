---
date: 2026-09-03
row: S4
status: done
---

# S4 — flip INCLUDE_SPY_IN_BACKTEST, re-baseline 25 months

## What the row asked

Set `INCLUDE_SPY_IN_BACKTEST = True`, re-run the 25-month backtest, report SPY's
contribution to recall, money and durability separately from the rest of the book.

## Flipped it — `universe.py:72`

```
- INCLUDE_SPY_IN_BACKTEST = False
+ INCLUDE_SPY_IN_BACKTEST = True
```

Matches Austin's ratified decision (`Projects/omen-x-board.md`, "Decisions taken
2026-08-28": *"flip it on — indices are the first real-money opportunity and are a
separate backtest metric"*).

## The flag turned out to already be moot for the current book

`backtest_2y.py` — the money/durability rig `CLAUDE.md` names as canonical — pulls its
symbol universe from `universe.ALL_SYMS`, the newer `MAJOR_15`/`INDEX_POOL`/`OTHER_POOL`
pool system (2026-08-11). SPY has been in `INDEX_POOL`, and therefore in `ALL_SYMS`,
unconditionally since that pool system shipped. `INCLUDE_SPY_IN_BACKTEST` only ever gated
the older `CORE_SYMBOLS`/`BACKTEST_SYMBOLS` lists, which this script uses solely for a
cosmetic `"tier"` label on each row (`"core"` vs `"experimental"` vs `"other"`).

Verified directly, not assumed: ran the full 730-day book both ways (flag off, then on) and
diffed every row. **124,834 signal rows identical before and after**, except the 4,247 SPY
rows' `tier` field flips from `"other"` to `"core"`. Zero trades, fills, grades, or dollars
changed. SPY was already fully in this book — the flag just relabels it.

`INCLUDE_SPY_IN_BACKTEST` still matters for the older scripts that gate directly on
`CORE_SYMBOLS`/`BACKTEST_SYMBOLS` (`backtest_week.py` run standalone, `check_24mo.py`,
`backtest_regimes*.py`, `research/g91_lane_slice.py`, `research/r9_simple_book.py`, and a
few more) — those now include SPY too, as intended, and that's a real behavior change for
whoever runs them next.

## SPY's contribution, sliced out of the current 730-day/29-symbol book

Script: `research/g113_spy_baseline.py` (re-runnable; `--book` flag reuses an existing
book). Full data: `research/g113_spy_baseline_data.json`.

**Money and durability**, on `traded` (counted) rows over 496 sessions
(2024-08-19..2026-08-17):

| scope | n | mean R | win% | $/day | months active | green |
|---|---:|---:|---:|---:|---:|---:|
| SPY, all traded | 129 | −0.015 | 48.1% | −$3.97 | 25 | 10 (40%) |
| rest (28 syms), all traded | 3,839 | −0.046 | 44.0% | −$354.05 | 25 | 10 (40%) |
| whole book, all traded | 3,968 | −0.045 | 44.2% | −$358.02 | 25 | **8 (32%)** |
| SPY, S-tier only | 37 | −0.068 | 48.6% | −$5.10 | 15 | 8 |
| rest, S-tier only | 619 | −0.072 | 42.5% | −$90.30 | 25 | 6 |
| whole book, S-tier only | 656 | −0.072 | 42.8% | −$95.39 | 25 | 9 |

**SPY does not carry the book — nor does either slice tell the durability story alone.**
The whole book is green in only 8 of 25 months (32%), *fewer* than either SPY's own 10/25
or rest's own 10/25. That's not an error: durability doesn't add across slices — a month
can be positive for SPY and negative for the rest (or vice versa) without the combined
month clearing zero. Real dynamic, not a bug in the script.

**Recall**, on `austin_marks_v2.jsonl` (159 marks, +/-2 bar join, same method as
`t0_heldout_recall.py`/`regression_gate.py`):

| scope | recalled | total | recall% |
|---|---:|---:|---:|
| SPY, all tiers | 5 | 21 | 23.8% |
| rest, all tiers | 43 | 138 | 31.2% |
| SPY, S-tier | 3 | 8 | 37.5% |
| rest, S-tier | 22 | 69 | 31.9% |

SPY is 21 of Austin's 159 marks (13.2%), 8 of them S-tier.

## Adversarial instruction: refute any SPY lift from fewer than 20 SPY trades

There is a small nominal SPY lift in three of the four comparisons above (mean R and win%
on the all-traded and S-tier money slices; recall on S-tier marks) — and every one of them
either fails the row's own 20-trade floor outright or isn't statistically real:

- **S-tier money** (SPY mean R −0.068 vs rest −0.072): SPY n=37, clears 20 — but computed
  the 95% CI on the difference anyway (Welch): **diff +0.030, 95% CI [−0.112, +0.173]**
  (all-traded scope; the S-tier scope's CI is wider still, `[−0.252, +0.260]`) — comfortably
  straddles zero both ways. **Not a real lift, refuted.**
- **S-tier recall** (SPY 37.5% vs rest 31.9%): SPY n=8. **Fails the 20-trade floor outright
  — refuted by the row's own rule**, before any significance test. 3 of 8 vs 22 of 69 is
  not a sample anything should be read from.
- **All-traded recall** (SPY 23.8% vs rest 31.2%): this direction is a SPY *cost*, not a
  lift, and n=21 — also thin, also not claimed as a finding here.

**Conclusion: SPY is not currently pulling its weight, and it is not currently dragging the
book down either — every SPY-vs-rest gap measured here is inside noise, on samples this
row's own adversarial rule says are too small to trust.** Nothing here contradicts Austin's
2026-08-28 call to trade indices; it says the current book doesn't yet have enough SPY
volume to tell.

(20-trade floor: `universe.MIN_SAMPLE_N`, settled in `research/p12_sample_floor.md` and
reused here rather than inventing a second number.)

## Adversarial pass

A separate agent, instructed to refute and default to refuted when uncertain,
independently reproduced all five numbered claims above: the flag state, the byte-exact
before/after diff of the full 730-day book (its own independent diff script, same result —
4,247 SPY-row `tier`-only diffs, 0 elsewhere, plus a code-path trace confirming
`backtest_2y.py`'s call to `simulate_day` never touches `CORE_SYMBOLS` at all), the
money/durability table, the recall table, and the Welch CI / 20-trade-floor conclusions.
Verdict: **CONFIRMED** on all five, exact numeric matches throughout. It also confirmed
`universe.py` was left correctly restored to `INCLUDE_SPY_IN_BACKTEST = True` after its own
temporary before/after toggling.

## verify

`grep -rq 'INCLUDE_SPY_IN_BACKTEST[[:space:]]*=[[:space:]]*True' .` — matches
`universe.py:72`. Report carries with-SPY and without-SPY rows (the tables above).

## plain

Turning on the SPY setting Austin asked for didn't actually change anything in the main
backtest — SPY was already being counted — and on its own, SPY is currently neither helping
nor hurting the trading numbers by an amount that's more than noise.
