# G7.1 / rtarget — the dollar answer, one trade and done

**Austin:** *"what +r for money should i be targeting? is that the ev or the mean 2r,
less worried about that and need the financial numbers, but the financial numbers if we
do the one trade and done strategy."* · *"the purpose of this was to make money, thats the
simple layer"* · *"i want green weeks"* · *"i dont have money just credit line so prop firm
stocks is my way to a free financial life."* · *"that i would fail a prop challenge 10
percent of the time"*

---

## The answer in one line

**Target $300 of expected profit per trading day. Not mean R.**

That is the number that pays rent, it is the number a prop floor can price, and it is
**exactly where the system already sits on the exit he would actually trade live**
($305/day). Mean R 2.0 is not a target he can aim at — it is a target that requires an
average *winner* of 5.455R, and the exit he owns produces 1.91R.

| what he should track | today | the goal |
|---|---:|---:|
| **E$ per trading day** (one trade, $1,000/R, live exit) | **$305** | **$1,000** |
| E$ per month (21 days) | $6,386 | $21,000 |
| P(green week) | 70.0% | 85%+ |
| P(green month) | 86.8% | 97%+ |

Everything below is that sentence with its receipts.

Script: `research/g71_rtarget_model.py` (run 2026-08-29, seed 84, 40,000 MC trials).
Output: `research/g71_rtarget.json`.
Book: `research/bt2y_trades.json`, generated 2026-08-29T03:14:29 — 500 sessions
2024-08-21 → 2026-08-21, 76,019 signals, 2,437 traded. Nothing is re-simulated; a day
policy is pure selection over existing rows, the argument `research/g71_firsts_policy.py`
makes, and this script **imports that module's candidate stream and causal walk** rather
than re-implementing either.

---

## 1. What "one trade and done" actually earns, in dollars

At **1R = $1,000** (`CLAUDE.md`'s reporting unit — see §4, he cannot trade this unit):

| policy | E$/day | E$/month | sd $/month | P(green month) | P(green week) |
|---|---:|---:|---:|---:|---:|
| **P1 one trade a day (measured)** | **$611** | $12,797 | $8,441 | 94.2% | **73.5%** |
| **P1 on the LIVE exit (winners clipped at 2R)** | **$305** | $6,386 | $5,717 | 86.8% | **70.0%** |
| P2 "win = done, 2 losses = done" (his sentence) | $806 | $16,897 | $10,011 | 96.6% | 80.6% |
| P4 until net green, 3-loss cap | $897 | $18,852 | $11,307 | 96.4% | 83.1% |
| today's headline rate (43.1%/+0.5481R) at 1/day | $548 | $11,498 | $8,115 | 94.4% | 71.2% |
| **the money gate 55% / 2.0R at 1/day** | $2,000 | $41,926 | $12,538 | 100.0% | 98.2% |
| realistic intermediate 55% / 1.20R at 1/day | $1,200 | $25,215 | $9,172 | 99.6% | 86.9% |

**The realised calendar agrees with the model** — no bootstrap needed:

| policy | months green | weeks green | 2-year total |
|---|---|---|---:|
| P1 | 22/25 = 88.0% | **77/105 = 73.3%** | +303.3R = $303,289 |
| P1 live-capped | 21/25 = 84.0% | **73/105 = 69.5%** | +151.4R = $151,374 |
| P2 | 22/25 = 88.0% | 83/105 = 79.0% | +399.6R = $399,561 |
| P4 | 23/25 = 92.0% | 85/105 = 81.0% | +444.8R = $444,823 |

**He wants green weeks. One trade a day gives him a red week roughly every fourth week
(73.3% green), and there is no sizing choice that changes that** — the frequency of a green
week is a property of the edge, not of the risk unit. The only two levers that move it are
*more trades per day* (P4 → 81.0%) and *a better edge* (the 55%/1.20R arm → 86.9%).

---

## 2. THE FINDING: half the money is booked past 2R, and the live path cannot book it

`research/g71_rtarget_model.py` §0b, and it re-derives independently what
`research/g71_rrcap.md` found in the code:

```
trades that ran past 2R: 94 of 496 = 18.95%
R booked ABOVE the 2R line by those trades: +151.92R of +303.29R total = 50.1% of all profit
P1 mean R with every winner clipped at 2.0R: +0.3052R  (total +151.37R)
```

**50.1% of every dollar the one-trade-a-day strategy makes over two years comes from the
19% of trades that ran past 2R.** The live path — `options_sizer.py:25` `DEFAULT_RR = 2.0`,
consumed at `:202`/`:223`/`:291`, and `paper_trader.py:132-143` closing the **whole**
position on the 2R touch — has no scale rung and no runner. It books **zero** of that 151.92R.

So the honest live number is **+0.3052R per day = $305/day at $1,000/R**, not $611. Every
dollar figure in §1's first row describes a backtest exit he does not own.

**This is the single highest-value fix on the board and it is not a grading problem.**
It is `DEFAULT_RR = 2.0` in one file. Restoring the backtest's ladder to the live path
doubles E$/day from $305 to $611 — a bigger move than any A/B this project has run, and
unlike those it is not inside the ±1.5799R error bar because it is not a statistical claim,
it is an arithmetic one about which rows exist.

---

## 3. Mean R vs EV: which number to target

**Target EV in dollars per day. Mean R is a ratio and it lies at low trade counts.**

Three reasons, in order of force:

1. **Mean R 2.0 is unreachable on this exit by arithmetic, not by tuning.**
   `mean R = wT − (1−w)`. At P1's measured 54.86% win rate, mean R = 2.0 requires
   T = (2.0 + 0.4514)/0.5486 = **5.455R average winner**. The measured average winner is
   **1.9149R**. Nothing in the exit family closes a 3.5R gap — `DIRECTION.md` prices the
   whole family at +0.06R.
2. **P1 already passes the win-rate half of the money gate.** 54.86% vs the 55% target,
   inside noise. The gate is not two conditions; on one-trade-and-done it is one, and it
   is the one that cannot be met.
3. **Mean R hides trade count, and trade count is what pays.** P4 has a *worse* mean R
   than P1 (+0.5166 vs +0.6115) and earns **47% more money** ($897/day vs $611), because it
   takes 1.74 trades a day instead of 1.00. Ranking by mean R picks the poorer policy.
   EV per day ranks them correctly, because EV per day is what lands in the account.

**What to write on the wall:**

> One trade a day, $1,000 risk. Expect **+$300 a day** today, **$6,400 a month**.
> The job is to get that to **$1,000 a day**.

And the conversion, so he can move between the two units — mean R needed per trade at one
trade a day, 21 days a month (`g71_rtarget_model.py` §8):

| goal $/month | at $250/R | at $350/R | at $500/R | at $1,000/R |
|---|---:|---:|---:|---:|
| $2,000 | 0.38R | 0.27R | 0.19R | 0.10R |
| $5,000 | 0.95R | 0.68R | 0.48R | 0.24R |
| $10,000 | 1.90R | 1.36R | 0.95R | 0.48R |
| $20,000 | 3.81R | 2.72R | 1.90R | 0.95R |

Read the $500/R column: **his current live +0.305R already clears $5,000/month at a $500
risk unit.** Mean R 2.0 is not needed for a living. It is needed for nothing he has asked for.

---

## 4. The 10% prop-failure question — and there are two of them

**Apex $150K EOD** (specs from `research/g4_prop_fit.md`): target **+$9,000**, trailing
drawdown **$4,000 on end-of-day peaks**, floor locks at start+$100 once profit ≥ $4,100,
100% split, up to 20 copyable accounts, eval seat expires in 30 days.

### 4a. Failing the EVAL ≤ 10% of the time

`g71_rtarget_model.py` §5 — largest $25-grid risk unit whose P(fail) ≤ 10%:

| what he trades | risk/trade at 10% fail | P(fail) | median days to pass |
|---|---:|---:|---:|
| **P1, backtest exit, no time cap** | **$550** | 9.6% | 24 |
| **P1, LIVE 2R exit, no time cap** | **$375** | 8.0% | **69** |
| P2 (his sentence), no time cap | $475 | 9.8% | 21 |
| P4, no time cap | $375 | 9.0% | 24 |
| money gate 55%/2.0R | $975 | 5.6% | 5 |
| 55%/1.20R intermediate | $775 | 5.1% | 9 |
| **P1 or P2 or P4 on a 30-DAY eval** | **NONE** | — | — |

The full curve, measured P1 stream, no time cap (§6):

| risk/trade | P(fail) | median days | E$/month |
|---:|---:|---:|---:|
| $250 | 0.2% | 58 | $3,210 |
| $350 | 1.8% | 40 | $4,494 |
| **$500** | **8.0%** | 27 | $6,420 |
| $750 | 18.2% | 16 | $9,631 |
| $1,000 | 32.1% | 10 | $12,841 |
| $1,500 | 41.2% | 6 | $19,261 |

**Answer: $500–$550 per trade.** Below $400 the failure risk is negligible; at $1,000 —
the unit `CLAUDE.md` reports in — he fails **one eval in three**, three times his stated
tolerance.

### 4b. The 30-day eval is not passable at one trade a day

**No risk unit at or above $25 clears a 10% failure rate on a 30-day seat under any
one-trade-a-day policy.** The mechanism: at ~21 trading days and +0.6115R/day, expected
profit is 12.8R. To reach $9,000 you need $700/R — and at $700/R the $4,000 floor is only
5.7R deep, so the blow-up rate outruns the target. Small units expire; large units blow.
There is no middle.

**Consequence: buy the no-time-limit seat.** Topstep ($149/mo, no time limit) or MFF
($477/mo, no time limit) per `research/g4_prop_fit.md` §1, or an Apex promo window long
enough to matter. **This is a purchasing decision, not an engineering one, and it is worth
more than any code change on the board this week.**

### 4c. The other 10%: losing the FUNDED seat

Passing is not the goal, keeping it is (§7c, 8R working buffer, monthly withdrawal):

| policy | $200/R | $250/R | $350/R | $500/R |
|---|---:|---:|---:|---:|
| P1 measured | 11.2% | 12.1% | 14.0% | 16.9% |
| **P1 live 2R exit** | **14.7%** | **16.7%** | **20.9%** | **28.2%** |
| P2 | 20.9% | 22.2% | 23.8% | 27.8% |
| 55%/1.20R intermediate | 2.8% | 2.6% | 3.2% | 4.3% |

**P1 misses the 10% tolerance at every risk unit, and shrinking the unit barely helps** —
because once the floor locks at +$100 the working buffer scales with the unit, so death
risk is nearly flat in size. **Funded survival is an edge problem, not a sizing problem.**
The intermediate arm (55% win / 1.20R) drops it to ~3%, comfortably inside tolerance. That
is the target that makes the prop plan safe, and it is reachable — it needs the average
winner to go from 1.91R to 3.0R, which is the runner the live path already fails to run (§2).

### 4d. P(drawdown > X% of $150k), 12-month path, measured P1 (§4b)

| floor | $250/R | $350/R | $500/R | $750/R | $1,000/R |
|---|---:|---:|---:|---:|---:|
| 2% = $3,000 | 7.6% | 37.7% | 83.5% | 99.7% | 100.0% |
| 3% = $4,500 | 0.3% | 4.9% | 30.7% | 83.5% | 99.0% |
| 4% = $6,000 | 0.0% | 0.5% | 7.6% | 46.2% | 83.5% |
| 5% = $7,500 | 0.0% | 0.1% | 1.7% | 19.6% | 56.2% |
| 6% = $9,000 | 0.0% | 0.0% | 0.3% | 7.6% | 30.7% |

Consistent with `research/g71_drawdown.md`'s $350–$408 finding for the *full* book, reached
by a different route on a different policy.

---

## 5. What one funded account is worth in a year

§7, one account, 12 months, 8R working buffer, monthly withdrawal above it, dies on a floor
breach:

| policy | $/R | E paid, 12 months | median | alive at 12 months |
|---|---:|---:|---:|---:|
| P1 measured | $250 | $34,733 | $35,768 | 88.4% |
| P1 measured | $500 | $66,152 | $70,893 | 82.7% |
| **P1 LIVE 2R exit** | **$250** | **$16,215** | $16,667 | 82.5% |
| **P1 LIVE 2R exit** | **$500** | **$29,478** | $32,538 | 71.6% |
| 55%/1.20R intermediate | $250 | $72,474 | $72,900 | 97.2% |

Gross of the $397 eval and $99 activation, and **ignoring Apex's 6-payout ladder
($2,500 → $5,000) and the 50% consistency rule**, both of which slow the first year. For a
×20 copy-stack figure use `research/g4_prop_fit.md`'s lifecycle model
(**$17.4k–$31.8k/month** at 43.0–45.5% win) — not this number times twenty.

**The honest headline: one Apex seat at $250/trade on the exit he owns today is worth about
$16,000 in year one, with a 1-in-6 chance of losing the seat.** That is real money and it is
not a free financial life. Two things move it: the runner (§2, ×2) and the copy stack
(`g4_prop_fit.md`, ×20).

---

## 6. Where this model is soft

- **The book is the backtest, not the live path.** `DIRECTION.md`: `live_scanner._tier():546`
  promotes only on `grade == "A+"`, which fires twice in 45,193 signals. **Every row here
  assumes the live gate is fixed to route what `backtest_week` routes.** If it is not, the
  live E$/day is not $305, it is ~$0.
- **Headline mismatch.** `DIRECTION.md` cites 43.1% / +0.5481R on 2,595 trades; the book
  regenerated 2026-08-29T03:14:29 reads 49.5% / +0.5495R on 2,437. Both are carried as
  separate scenarios rather than silently reconciled.
- **The two-point parametric arms are optimistic on the left tail** (real one-trade losses
  average −0.984R and never exceed −1.00R) **and pessimistic on the right** (no +10R day
  exists in a two-point model). Only the `today_book`, `today_1`, `gate` and `mid` rows use it;
  every P-row is an empirical bootstrap of realised days.
- **496 days is one sample.** The block bootstrap (5-day blocks) preserves serial
  correlation, but the right tail rests on 94 trades.
- **The 8R working buffer in §7/§7c is a modelling choice**, sized to survive P1's realised
  11-trade losing run (`research/g71_drawdown.json` `streaks.max_consec_losing_trades`).
  A larger buffer lowers death risk and slows withdrawals; §7c's *ordering* is robust to it,
  its *levels* are not.
- **No commissions, no slippage, no options spread.** At a $250 unit on 0DTE contracts the
  spread is a material haircut and is not modelled anywhere in this repo.

---

## 7. Proposed change — NOT applied

The one code change this track's numbers justify. Diagnosis pass; do not apply here.

```diff
--- a/options_sizer.py
+++ b/options_sizer.py
@@ -22,7 +22,17 @@
 CONTRACT_MULTIPLIER = 100
 DEFAULT_MAX_LOSS = 1000.0
-DEFAULT_RR = 2.0
+# LIVE_RR_CAP -- research/g71_rtarget.md §2 and research/g71_rrcap.md.
+#
+# 50.1% of the two-year one-trade-a-day profit (+151.92R of +303.29R) is booked
+# ABOVE the 2R line by the 18.95% of trades that ran past it. A whole-position
+# exit at 2.0R books none of it: measured mean R falls +0.6115 -> +0.3052, and
+# E$/day at $1,000/R falls $611 -> $305.
+#
+# This constant is the live ceiling. The backtest's SCALE_PLAN
+# ("hod_then_runner_be") is what produced every published money number; the live
+# path has no scale rung and no runner. Raising this constant alone does NOT
+# restore the ladder -- it only moves the single exit. The real fix is to route
+# paper_trader through the same scale plan. This comment is the marker for it.
+DEFAULT_RR = 2.0
 DEFAULT_DELTA = 0.5  # ATM ~ 0.5
```

That is a comment, not a behaviour change, and deliberately so: **raising `DEFAULT_RR`
would make things worse, not better** — a single whole-position exit at 3R books fewer
winners at a worse rate. The fix is a scale plan on the live path, which is a real piece of
work in `paper_trader.py`, and it should be scoped, not slipped in as a constant.

---

## 8. The three numbers to put in front of him

1. **$305 a day.** What one trade a day earns right now on the exit he actually owns,
   at $1,000 risk. $6,400 a month. That is the simple layer, and it is the honest number.
2. **$500 a trade.** The largest risk unit that fails a prop eval less than 10% of the
   time — **but only on a no-time-limit seat.** A 30-day Apex seat is not passable at one
   trade a day at any size. Buy the seat without the clock.
3. **19% → 100%.** The share of trades allowed to run past 2R in the backtest, versus the
   0% the live path allows. Half the money is on the other side of that line.
