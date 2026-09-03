# G7.1 / rtargetV — adversarial verify of track `rtarget`'s "mean R ranks policies backwards"

Script: `research/g71_rtargetV_verify.py` (re-implements the candidate stream and causal
walk from `g71_firsts_policy.py`'s docstring spec **without importing it**). Read-only on
the book; no engine file touched.

## Verdict: REFUTED — the descriptive numbers reproduce exactly, three of the four offered supports do not

| what reproduces | mine | claimed |
|---|---|---|
| P1 mean R/trade | +0.6115 | +0.6115 |
| P4 mean R/trade | +0.5166 | +0.5166 |
| P1 trades/day, $/day | 1.0000, $612 | 1.00, $611 |
| P4 trades/day, $/day | 1.7359, $897 | 1.74, $897 |
| uplift | +46.7% | 47% |

No look-ahead: `P_GREEN3 = cum > 0 or losses >= 3` reads only realised P&L, and the walk
enforces `entry_key >= last exit_key`. Halted rows average +0.3735R vs traded +0.5495R, so
including them is conservative, not favourable.

## Five defects

1. **5.455R is arithmetically wrong.** `mean R = wT − (1−w)` ⇒ `T = (2.0 + 0.4514)/0.5486
   = 4.4685R`, not 5.455. 5.455 = (2.0 + **1.0**)/0.55 — the numerator's (1−w) was replaced
   by 1.0. The script's own `Scenario("gate")` computes `T = (2.0+0.45)/0.55 = 4.4545`
   (`g71_rtarget_model.py:168`), contradicting the note string it carries at
   `g71_rtarget_model.py:340`. The real gap to the 1.9149R measured winner is **2.55R, not
   3.5R**. `DIRECTION.md:47` states the same formula correctly (4.56R at 54%).
2. **P1 does not meet the win-rate half of the gate.** 54.86% < 55.0%. The report asserts
   "already passes".
3. **The +47% is measured at unequal risk deployment** — the exact apples/oranges error the
   claim accuses mean R of. `g71_rtarget_model.py:41-45` declares the risk unit "a FREE
   VARIABLE ... not $1,000". Size P1 up 1.736× to deploy P4's 1.7359R/day and P1 earns
   **$1,062/day vs P4's $897** — mean R/trade ranks them **correctly**, by exactly
   0.6115/0.5166 = 1.184.
4. **On the live exit the report itself calls the only honest one, the gap vanishes.**
   Under the 2R clip (`options_sizer.py:25 DEFAULT_RR=2.0`, the report's own §2): P1 $305,
   P4 $341. Paired over the 496 shared days, P4−P1 = **+0.0358R/day, t=0.73,
   95% CI [−0.0606, +0.1323]** — inside noise, and far inside `DIRECTION.md`'s standing
   ±1.5799R bar. The +47% is a property of an uncapped backtest exit §2 disowns.
5. **Two books in one table.** The model loaded `bt2y_trades.json` generated
   2026-08-29T03:14:29 = 76,019 signals / **2,437 traded / 49.50% win / +0.5495R**. That is
   neither the old 1,017 book nor the 2,595-trade post-T0 book T0 ratified (75,953 / 2,595 /
   43.1% / +0.5481R, `research/t0_ratified_rebaseline.md:24,91`). §1's parametric row
   "today's headline rate (43.1%/+0.5481R)" is priced off DIRECTION's book while the
   P1/P2/P4 rows beside it are computed on a different, later R31-halted regeneration.

## What survives

Under a **drawdown** budget — the constraint the report's own §4/§5 prop model imposes —
P4 does beat P1: return/maxDD 34.41 vs 15.06 (+128%) on the realised 2-year path. Trade
count buys drawdown smoothing that mean R does not price. That vindicates a
drawdown-normalised ranking, not "EV per day", and not +47%.

Also standing: `DIRECTION.md:57` already says "gate on held-out recall, never on mean R".
The claim's headline is repo doctrine, re-attributed to a mechanism that does not hold up.

Neither P1 nor P4 is on the live path: `live_scanner._tier():546` promotes only `A+`,
2 of 45,193 signals in two years (`DIRECTION.md:31-34`).
