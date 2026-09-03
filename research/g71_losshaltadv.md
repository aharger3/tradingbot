# G7.1 / losshaltadv — adversarial verify of `research/g71_losshalt.md` S2c

**Scripts** `research/g71_losshaltadv_verify.py`, `research/g71_losshaltadv_money.py`
(independent re-implementations; they do not import `g71_losshalt_grid`).
**Data** `research/bt2y_trades.json`. **Diagnosis only — no engine file touched.**

## Verdict: REFUTED on interpretation, CONFIRMED on arithmetic

### 1. The counts reproduce exactly

| arm | trades taken | blocked | days with >=1 block | %  of 496 |
|---|--:|--:|--:|--:|
| halt=1 | 1524 | 1770 (54%) | **394** | 79% |
| halt=2 (shipped) | 2437 | 857 (26%) | **245** | 49% |
| halt=3 + -2R floor | 2599 | 695 (21%) | **185** | 37% |
| -2R floor alone | 2702 | 592 (18%) | **145** | 29% |

No look-ahead found. `loss_halt.apply_to_book` runs as a post-process at
`backtest_2y.py:213` after every row is built, so rebuilding the pool as
`(fired and traded) or halted` = 3,294 is exact. `entry_i` is an index into
`pf.rth(day)` (`backtest_2y.py:174`), so cross-symbol entry ordering is sound.
Book is the post-T23 one (3,294 candidates), a superset of the post-T0 2,595 —
not the old 1,017.

### 2. Nothing is "benched". Zero days, every arm.

`traded_days = 496` in `g71_losshalt_grid.json` for **all 40 cells**, halt=1
included. My walker: **0 zero-trade days on every arm.** The gate is structurally
incapable of benching a day — it needs `halt_n` already-CLOSED losses first.

- halt=2: minimum trades already taken on a "benched" day = **2**; median taken
  before the first block = **4**.
- -2R floor: a single trade cannot reach -2R (per-trade floor is -1.25R), so >=2
  taken there too.

"Days it stops you trading" counts *days on which a later entry was blocked*, and
labels them as days he could not trade. He traded on every one.

### 3. So it is not R20's collision measured

R20's source text, `research/marks/probe_master_2026-08-29.jsonl`, card
`fact_s_plus_per_day`: *"Quality over quantity but I want to **at least trade
every day**."* At-least-once-a-day is satisfied **496/496** by all 40 cells.
There is no collision. `research/t22_adjudication.md:101-102,276-279` (blocker 7)
carries the same conflation and asks Austin to resolve a conflict the book does
not contain.

### 4. And money DOES separate them — on the gate's own metric

`g71_losshalt.md` bootstraps **total R**, which is monotone in trades taken here
(the marginal blocked trade means +0.373R), so it can never separate arms that
differ only in removal count. CLAUDE.md's money gate is **mean R per trade**.
Paired day-block bootstrap, B=20,000, seed 1234, vs the shipped halt=2:

| arm | delta mean R/trade | 95% CI | |
|---|--:|---|---|
| -2R floor alone | **-0.0351** | [-0.0610, -0.0095] | **separates** |
| halt=3 + -2R floor | **-0.0237** | [-0.0453, -0.0019] | **separates** |
| no governor | -0.0458 | [-0.0945, +0.0055] | tie |

Both proposed replacements are readably **worse per trade** than the shipped rule,
and worse on win rate (49.2% -> 48.2% / 47.5%). Total R (+27.4R / +50.8R, both CIs
spanning zero) reproduces, but it is the wrong instrument.

**Net:** the S2c table is arithmetically sound and mislabelled. The real separator
is trade count vs per-trade quality, which is exactly the money gate — and on it
the shipped `halt_n=2` wins.
