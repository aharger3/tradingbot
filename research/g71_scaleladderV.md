# G7.1 `scaleladderV` — adversarial verify of `g71_scaleladder.md` §3

**Verdict: NOT REFUTED.** Every number in the claim reproduces to 4 decimals from an
independently written rig (`research/g71_scaleladderV_legs.py`, reusing only
`run_ladder`/`tranche2_target` so no fill is re-implemented). Raw output:
`_g71_slV_out.txt` below.

## What was checked, and what came back

| check | claim | independently recomputed | verdict |
|---|---|---|---|
| book identity | 2,437 traded | 2,437 traded, 76,019 signals, `generated 2026-08-29T03:14:29` — byte-identical to `git show HEAD:research/bt2y_trades.json` | RIGHT BOOK |
| his-ladder win rate | 52.9% | **52.85%** | ✓ |
| mean loss | −0.785R | **−0.7847R** | ✓ |
| mean winner, actual | +1.720R | **+1.7199R** | ✓ |
| required winner T | +4.484R | **+4.4841R** = (2.0 − 0.4715·(−0.7847)) / 0.5285 | ✓ |
| runner leg mean R | +0.605R | **+0.6049R** (n=2437) | ✓ |
| f sweep 10/30/50/75/100 | .539/.554/.568/.587/.605 | **.5391/.5537/.5683/.5866/.6049** | ✓ |
| required runner leg | +26.8R | **+26.841R** = (4.4841 − 0.9·2.0)/0.10 | ✓ |

## The three attacks I ran, and why each failed

**1. Wrong book?** The prompt's "2,595-trade post-T0 book" is itself stale. T0's book
(75,953 sig / 2,595 traded) was superseded by T23 (`145d564e`), which re-ran the two
years on the 7.1 stack: 76,019 sig / **2,437 traded** / +0.5495R / 49.50% win. That is
what is on disk and at HEAD, and it is what `g71_scaleladder.py:main` reads
(`--inp research/bt2y_trades.json`). The report's incumbent row (2437 / 49.7% / +0.549 /
+1339R / 25-25 months) matches T23's published book; the 49.7 vs 49.50 gap is
`agg():g71_scaleladder.py:314` dropping `r == 0` from the win-rate denominator, a
convention it inherits from `p21_target_availability.py::agg`. Book is correct and is
the newest one. Attack fails.

**2. Look-ahead in the arm the claim rests on?** None found.
- T1: `ext` seeds from `max(b[1] for b in bars[:ei+1])` (`g71_scaleladder.py:213`) — a
  running extreme through the entry bar; the stall test compares bar `i` to `bars[i-1]`.
- T3: `_swing_levels` files a pivot under `j + strength` (`:124`, `:127`) and it is
  consulted at bar `i == j + strength`, so a pivot is never read before it is confirmed.
- T2: resting limit, TOUCH, evaluated after the close-based stop — pessimistic ordering.
- Six-level roster: PDH/PDL/PMH/PML are prior-session; ORH/ORL come from `rth[:5]`
  (`p21_target_availability.py:160`), i.e. known at bar 4. **min `entry_i` across all
  2,437 rows is 5**, so ORH/ORL is causal on every single trade. Zero rows at risk.
- The only hindsight in §3 is the ORACLE runner, and the report labels it as such and
  reports it separately (`f = 34%`). The claim quotes the REAL arm.
Attack fails.

**3. Unreachable branch / dead leg?** No. T1 reaches its own rung 1,095/2,437, T2
1,404/2,437, T3 872/2,437. T4 has no rung by construction and the report says so.
The disaster stop, the −1.25R floor and the BE arm all fire (`--selftest` asserts each).
Attack fails.

## The one real defect — and it runs the wrong way for a refutation

§3's justifying sentence — *"90% of the position is structurally capped at or below
~2R"* — is **false in the report's own table**. T3's own-rung mean is **+2.815R** and
T1's is **+2.223R**; neither leg has a cap. Only T2 is a limit at ≤2R.

But the report does not lean on the cap; it says *"Even granting all three the full 2R"*,
which I confirmed is **generous, not stingy**:

| frame | required 10% runner leg |
|---|---:|
| report's: other three granted a flat 2R, target = the winner T (+4.4841R) | **+26.84R** |
| same frame, other three at their REAL winner-conditional means (+1.843/+1.434/+1.814) | **+29.57R** |
| unconditional: other three at their measured all-exit means (+0.580/+0.467/+0.548), target = mean R 2.0 | **+15.21R** |

So the honest number in the report's own frame is **worse** (+29.6R), and the
unconditional framing still demands **+15.2R** from a leg that books **+0.605R** — a
25x shortfall. The "capped at 2R" wording should be struck; the conclusion it supports
survives either way.

## Why "unreachable at ANY runner fraction" is exhaustive, not a sampled claim

`mean_at(f)` is exactly linear in `f`:
`mean(f) = (1−f)·mean(⅓(L1+L2+L3)) + f·mean(L4) = 0.5317 + 0.0732·f`.
Per-leg R in `run_ladder` is independent of `weights` — the exits depend only on the
price path and `be_moved`, and `be_moved` is armed by whichever rung fires first
regardless of its weight. I confirmed this the hard way by re-simulating with
`weights=(0,0,0,1)`: mean R **+0.6049**, identical to the reweighted f=100% figure. So
a 101-point grid over f∈[0,1] has its maximum at the endpoint f=1.00 = **+0.6049R**,
and the gap to 2.0 is **+1.395R**. There is no f that closes it.

## Residual caveats (none load-bearing)

- 2,437 of 3,294 non-halted candidates: `loss_halt` blocks 857. T20 measured the halt at
  +0.0493R, inside the error bar, so it does not change the arithmetic's sign.
- The claim's conclusion is about **exits only**. It says nothing about the entry side,
  and the report's own read is that 55% of trades are swept by the shared stop before any
  rung — an entry problem. That is a scope note, not a contradiction.
