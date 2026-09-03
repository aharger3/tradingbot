# G7.1 `scaleladderverify` — adversarial verify of the `scaleladder` runner-fraction claim

**Verdict: NOT REFUTED.** The 12-cell grid reproduces exactly under an independent
re-implementation. Three qualifications below; none of them move the number.

Scripts (written this pass, not committed by me):
- `research/g71_scaleladderverify_repro.py` — a from-spec re-implementation of the four-tranche
  ladder. Does **not** import `g71_scaleladder.run_ladder`. Shares only `stop_rule` (mandated
  single fill definition) and `p21_target_availability.levels_for_entry` (the level roster).
- `research/g71_scaleladderverify_book.py` — the same grid on the loss-halt-OFF book.

## 1. Reproduction — exact

All 2,437 trades, all 12 cells, mine vs `research/g71_scaleladder_rows.json`:

| cell | n | win% | mine | theirs | delta |
|---|---:|---:|---:|---:|---:|
| f=0% / be | 2437 | 53.5 | +0.5317 | +0.5317 | 0.0000 |
| f=0% / 1r | 2437 | 56.6 | +0.5326 | +0.5326 | 0.0000 |
| f=0% / struct | 2437 | 56.2 | +0.5226 | +0.5226 | 0.0000 |
| f=10% / be | 2437 | 52.9 | +0.5391 | +0.5391 | 0.0000 |
| f=10% / 1r | 2437 | 56.5 | +0.5368 | +0.5368 | 0.0000 |
| f=10% / struct | 2437 | 56.0 | +0.5264 | +0.5264 | 0.0000 |
| f=20% / be | 2437 | 51.7 | +0.5464 | +0.5464 | 0.0000 |
| f=20% / 1r | 2437 | 56.0 | +0.5410 | +0.5410 | 0.0000 |
| f=20% / struct | 2437 | 55.4 | +0.5301 | +0.5301 | 0.0000 |
| f=30% / be | 2437 | 50.3 | +0.5537 | +0.5537 | 0.0000 |
| f=30% / 1r | 2437 | 55.5 | +0.5452 | +0.5452 | 0.0000 |
| f=30% / struct | 2437 | 54.8 | +0.5339 | +0.5339 | 0.0000 |

Per-trade `|mine − theirs|` on `f=10%/be`: **max 0.000000**, 0 rows over 1e-6.

Claim's arithmetic: 0.5537 − 0.5317 = **+0.0220R** ("+0.022R"); grid span 0.5226 → 0.5537 =
**0.0311R** ("0.031R"); best cell `f=30%/be` +0.554, worst `f=0%/struct` +0.523. All correct.

## 2. Look-ahead — none in the grid

- `_swing_levels` (`g71_scaleladder.py:112`) scans all bars but files a pivot at `j+strength`;
  bar `i` only reads pivots whose confirming bars are `<= i`. Causal.
- `p21.levels_for_entry(..., entry_i)` is as-of the entry bar. The one theoretical hole is
  `ORH`/`ORL` from `rth[:5]` when `entry_i < 4` — **0 of 2,437 trades qualify**. Inert.
- T1's session extreme is `max(bars[:ei+1])`, a running max. Causal.
- `mfe_r` is hindsight, but it feeds only the ceiling and ORACLE rows in §3 of the report, not
  the 12-cell grid.
- Alignment sanity: corr(ladder, book `r`) = 0.808, sign agreement 85.6% — same trades, same
  side, same entry bar.

## 3. Reachability — all 12 branches fire, but the grid is 3 measurements, not 12

`run_ladder`'s exit decisions never read `weights`. `open_w` holds them but no branch tests a
value. Therefore each leg's realised R is weight-independent and the composite is **exactly
linear in f**: predicting `f=10%` and `f=20%` from the `f=0%`/`f=30%` endpoints gives
max abs deviation **3.55e-15** over all 2,437×3 rows.

So the f dimension is one scalar per trail rule, `mean(L4) − mean(L̄123)`:

| trail | slope per unit f | f=0% | implied f=100% |
|---|---:|---:|---:|
| be | +0.0732 | +0.5317 | +0.6049 |
| 1r | +0.0419 | +0.5326 | +0.5745 |
| struct | +0.0379 | +0.5226 | +0.5605 |

The implied `f=100%/be` of **+0.6049R** matches the report's independently-derived +0.605R.
Calling this a "12-cell grid" overstates the evidence — it is 3 measurements sampled at 4
collinear points — but linearity makes the extrapolation exact rather than assumed, which
*strengthens* the claim.

Paired significance (same trades, so the ±1.5799R unpaired bar is the wrong one):
`f=0%/be → f=30%/be` paired d = **+0.0220R, 95% CI [−0.0203, +0.0642]**. Straddles zero even
on the tight paired bar.

## 4. The book — n=2,437, and it does not matter

`research/bt2y_trades.json` (generated 2026-08-29T03:14:29) carries `traded: 2437`,
`loss_halt: true`, `halted: 857`, 76,019 signals. **DIRECTION.md's 2,595 is stale** — it is the
post-T0 / pre-T23 book (75,953 signals). T23 landed R31 and the halt now blocks 857 rows. The
scaleladder read the current on-disk book and states n=2437 honestly; it is not the 1,017-trade
book.

Restoring the 857 halted rows (`status == "halted"`, loss-halt OFF, 3,294 trades):

| cell | n | win% | mean R |
|---|---:|---:|---:|
| f=0% / be | 3294 | 51.5 | +0.4887 |
| f=0% / 1r | 3294 | 54.8 | +0.4775 |
| f=0% / struct | 3294 | 54.5 | +0.4707 |
| f=30% / be | 3294 | 48.4 | +0.5132 |
| f=30% / 1r | 3294 | 53.8 | +0.4863 |
| f=30% / struct | 3294 | 53.2 | +0.4786 |

`f 0% → 30%` delta = **+0.0245R** (vs +0.0220R on the halted book), grid span 0.0425R. Same
conclusion, same order of magnitude. The claim is book-robust.

## 5. What IS wrong, and it is scope not arithmetic

1. **"Not a lever" is true for mean R only.** Across the *same* 12 cells win rate spans
   **50.3% → 56.6% (6.3 pts)** and **7 of 12 cells clear the 55% money-gate arm**; max DD spans
   **10.1R → 17.2R**. f and mean R move together while f and win rate move *opposite* —
   `f=30%/be` is the best mean R **and** the worst win rate. The money gate is `55% win AND
   mean R >= 2.0`; the runner fraction is a live lever on the arm the claim does not measure.
2. **`trail` is applied to the whole open position, not to the runner.**
   `g71_scaleladder.py:262-269` sets `work_stop` for every leg still open. At `f=0%` there is no
   runner at all and trail still moves mean R 0.5317 → 0.5226. Austin's words scope BE to the
   runner ("10 runner stop loss break even"). The grid's trail axis is therefore a
   whole-position trail, not a runner trail. Does not affect the f-delta.
3. **Report §4 mis-attributes one gap.** "A 100% runner ... books only +0.605R. The gap to 2.0
   is +1.461R" — 2.0 − 0.605 = 1.395R. The 1.461R is 2.0 − 0.539 (his ladder). Against the best
   cell it is 1.446R. The claim's "1.46R gap" inherits this. Cosmetic.
4. **Population is conditioned on the incumbent exit.** R31's halt was applied using the
   *shipped* exit's win/loss labels, so which 857 rows are missing depends on an exit the grid
   is trying to replace. Shared across all 12 cells, so the f-delta is unaffected, but no
   absolute mean-R level off this rig is exit-independent.

## Corrected claim

> Across `f = 0/10/20/30%` (remainder split equally over the three scale points) on the current
> **2,437**-trade post-T23 book, mean R moves **+0.0220R** (+0.532 → +0.554) and the 12-cell
> f × trail grid spans **+0.523 → +0.554**, a 0.031R range against a **1.446R** gap to the 2.0R
> gate. Independently reproduced per-trade to 0.000000, and robust to the book (+0.0245R with
> the loss halt off, n=3,294). **The runner fraction is not a lever on mean R** — the composite
> is exactly linear in f with slope +0.0732R/unit, so even `f=100%` implies only +0.605R.
> It *is* a lever on the money gate's other arm: the same 12 cells span 50.3%–56.6% win rate,
> 7 of them clearing 55%, and f trades win rate away for mean R.
