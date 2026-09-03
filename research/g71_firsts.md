# G7.1 / `firsts` — one trade a day, and stop when you're green

**Question (Austin, 2026-08-29):** *"all these s trades would not be done in one day, what
would happen is we trade the s trade that comes up first, and if it wins, were done for the
day. the 2 trades losses done for the day is a scarface rule… keep trading s trades until
youve hit profit."*

**Answer in one line: his rule is a green-DAY machine, not a money-gate fix.** It takes the
share of days that finish green from 58% to 79%, and it costs about one R a day in total
return. It also breaks the one gate OMEN currently meets (durability), and the S restriction
he names cannot be run today because the engine's S is significantly *anti*-predictive.

Scripts: `research/g71_firsts_policy.py` (the table), `research/g71_firsts_isfirstspecial.py`
(the error bars). Data: `research/_g71_firsts.json`. Book:
`research/bt2y_trades.json`, generated 2026-08-29T03:14:29, 500 sessions
2024-08-21 → 2026-08-21, 76,019 signals, 3,294 counted, 2,437 traded after R31.

---

## Method

Nothing is re-simulated. Every row's R is a property of that signal alone — entry, stop,
target and fill are fixed at detection — so a day policy is pure **selection** over rows
`backtest_2y.py` already wrote. No engine file was touched.

- **Candidate stream** = `status=="fired" and traded` (2,437) + `status=="halted"` (857) =
  **3,294** counted rows over **496 days** (6.64/day). The 857 are counted rows R31 flipped
  to `traded=False`; they keep every measured field (`loss_halt.py::apply_to_book`).
  The 1,050 legacy-`C` rows are alert-only and are excluded except in the P5b arm.
- **Causality** uses the same tuple keys `loss_halt.py` uses, for the reason its docstring
  gives: `entry_key=(entry_i, et, sym)`, `exit_key=(entry_i+bars, et, sym)`. A policy may
  only take a candidate whose entry key is at or after the last trade's exit key — you
  cannot decide trade #2 before trade #1 has closed, and a human holds one position.
- **`mean R per DAY` is over all 496 candidate days**, not over the days a policy traded.
- **Months/weeks green** = calendar sum > 0 out of the fixed 25 months / 105 ISO weeks.
- **Max DD** = peak-to-trough of the daily cumulative-R curve, in R.
- **Max red run** = longest run of consecutive traded days with day R < 0.

---

## The table

| policy | trades | WR% | R/trade | R/day | total R | months green | weeks green | max DD (R) | max red run | green days | % of oracle |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **P0** shipped, all signals, R31 ON | 2437 | 49.50 | +0.5495 | 2.6998 | **1339.1** | **25/25** | 91/105 | 14.7 | 6 | 288 (58.1%) | 78.5 |
| P0u all counted, R31 OFF | 3294 | 46.76 | +0.5037 | 3.3451 | 1659.2 | 25/25 | 93/105 | 27.9 | 5 | 337 (68.0%) | 97.2 |
| **P0seq** all counted, one at a time *(control)* | 1865 | 46.31 | +0.4988 | 1.8754 | 930.2 | 24/25 | 93/105 | 27.8 | 5 | 315 (63.5%) | 54.5 |
| **P1** first signal only | 496 | **54.86** | **+0.6115** | 0.6115 | 303.3 | 22/25 | 77/105 | 20.1 | 6 | 273 (55.0%) | 17.8 |
| **P2** first; win=done; 2 losses=done | 705 | 52.49 | +0.5668 | 0.8056 | 399.6 | 22/25 | 83/105 | 16.3 | 5 | 341 (68.8%) | 23.4 |
| **P3** until the day is net green, no cap | 972 | 48.81 | +0.4861 | 0.9526 | 472.5 | 23/25 | 87/105 | 15.9 | 5 | **390 (78.6%)** | 27.7 |
| **P4** until net green, 3-loss cap | 861 | 50.35 | +0.5166 | 0.8968 | 444.8 | 23/25 | 85/105 | **12.9** | 5 | 379 (76.4%) | 26.1 |
| **P5** P2 on S only (counted) | 327 | 45.87 | +0.2753 | 0.1815 | 90.0 | 14/25 | 59/105 | 15.7 | 6 | 140 | 5.3 |
| P5b P2 on S only, incl. legacy-C alerts | 378 | 44.68 | +0.2944 | 0.2244 | 111.3 | 16/25 | 57/105 | 13.0 | 7 | 159 | 6.5 |
| P3s until net green, S only | 340 | 45.59 | +0.2754 | 0.1888 | 93.7 | 14/25 | 59/105 | 16.6 | 6 | 144 | 5.5 |
| RANDOM one-per-day (EV control) | 496 | 47.19 | +0.5110 | 0.5110 | 253.4 | — | — | — | — | — | 14.9 |
| LAST signal of the day only (control) | 496 | 42.01 | +0.5251 | 0.5251 | 260.4 | 22/25 | 73/105 | 9.6 | 6 | — | 15.3 |
| **ORACLE** best single trade/day *(look-ahead)* | 496 | 93.44 | **+3.4404** | 3.4404 | 1706.4 | 25/25 | 105/105 | 4.0 | 4 | 464 (93.5%) | 100 |
| ANTI-ORACLE worst single trade/day | 496 | 5.24 | −0.8812 | −0.8812 | −437.1 | 0/25 | 1/105 | 437.1 | 147 | 26 | −25.6 |

**The oracle on this book is +3.4404R at 93.44%, not the +2.2125R / 76.6% `DIRECTION.md`
cites.** That figure was measured on the pre-T0 1,017-trade book; the ratified book has
6.64 candidates a day instead of ~2, so the best-of-day is drawn from a wider hand. Update
the citation.

---

## The five things this measures

### 1. Every day-policy loses money against the honest control, and it is not noise

The right control is **P0seq**, not P0: P0 holds **2.37 positions at once on average, 18 at
the peak, 2+ on 368 of 496 days**. A human running his rule holds one. Paired day by day
against P0seq (496 paired days):

| arm | mean day delta vs P0seq | se | t | verdict |
|---|---:|---:|---:|---|
| P1 | **−1.2639R** | 0.1685 | −7.50 | significant |
| P2 | **−1.0698R** | 0.1574 | −6.80 | significant |
| P3 | **−0.9228R** | 0.1459 | −6.32 | significant |
| P4 | **−0.9786R** | 0.1515 | −6.46 | significant |
| P5 | −1.6939R | 0.1879 | −9.02 | significant |
| P0 (concurrent) | +0.8244R | 0.2072 | +3.98 | significant |
| ORACLE | +1.5650R | 0.1389 | +11.27 | significant |

This is the rare A/B in this project that **clears its own error bar** (the standing finding
is that they don't). The cost is real and it is about one R per trading day. P3 is the
cheapest version of his rule; P1 the most expensive.

### 2. What the rule actually buys is green days — a lot of them

| policy | green days | share |
|---|---:|---:|
| P0 shipped | 288 | 58.1% |
| P0seq control | 315 | 63.5% |
| P1 | 273 | 55.0% |
| P2 | 341 | 68.8% |
| **P3** | **390** | **78.6%** |
| P4 | 379 | 76.4% |
| oracle | 464 | 93.5% |

"Keep trading until you've hit profit" does exactly what the sentence says: **P3 finishes
78.6% of days green against the control's 63.5%**, +15.1 points, on 1.96 trades a day. That
is the objective his rule optimises, and no measurement in this repo was scoring it before.
It also **halves the shipped book's drawdown risk profile**: P4 has the lowest max DD of any
arm that isn't the oracle (12.9R vs P0seq's 27.8R).

Note the split: **P1 has the best mean R per trade and the *worst* green-day share of the
four.** One trade a day means a red day whenever it loses, with no chance to fix it. His
"keep going" clause is not a decoration on the rule; it is the part that produces the effect
he wants.

### 3. Durability — the one gate OMEN meets — breaks under every version of the rule

| arm | red months |
|---|---|
| P0 shipped | none (25/25) |
| P0seq | 2025-09 −8.7R |
| P1 | 2025-06 −3.9R · 2025-09 −6.9R · 2025-10 −4.4R |
| P2 | 2025-05 −3.9R · 2025-09 −7.3R · 2025-10 −5.9R |
| P3 | 2025-05 −8.7R · 2025-09 −9.1R |
| P4 | 2025-05 −3.9R · 2025-09 −10.9R |
| P5 | eleven red months |

**2025-09 is red under every arm including the control** and is the durability wound; P0's
25/25 is bought with concurrency, not with edge. Adopting his rule as written costs the
durability gate (25/25 → 22 or 23/25) unless 2025-05 and 2025-09 are separately explained.

### 4. The money gate: P1 is the closest anything has come to the win-rate half, and it is
still nowhere near the R half

- P1: **54.86% win rate** (±2.24pp) against a 55% gate — inside the bar of the gate.
  Mean R **+0.6115** against a 2.0 gate. Not close.
- The arithmetic is the same wall `DIRECTION.md` names: P1's mean *winner* is **+1.897R**;
  at 54.86% you need the average winner at ~**4.6R** for mean R 2.0.
- And the win-rate lift is a *composition* effect, not a quality one: first signals win more
  often (54.86% vs 45.32% for the rest, a 9.5-point gap at ±2.24/±0.94pp — real) but their
  winners are **smaller** (+1.897R vs +2.228R). Losers are identical (−0.984 vs −0.990).

### 5. "Is FIRST special?" — barely, and not on R

Paired per day, first-signal R minus that day's mean candidate R over the 485 days with
more than one candidate: **+0.1028R, se 0.0785, t = +1.31 — inside the bar.** Against the
random-single-pick EV control, P1 is +0.5110 → +0.6115 per trade, which is that same
non-significant gap.

**The win rate gap is real; the R gap is not.** First-of-day is a higher-probability, lower-
payoff trade. That is a coherent thing for a rule that says "if it wins, we're done" —
you want the highest P(win) on trade #1, and that is what arrival order gives you.
The day ends on trade #1 on **271 of 496 days (54.6%)**.

---

## The S restriction cannot be run today, and the reason is a finding

P5 needs an S gate. **There is none in detection** — `signal_runner.S_GATE = False`
(`signal_runner.py:380`), `ENABLE_SAC_LADDER = 0` (`signal_runner.py:660`). The proxy used
is `sgrade == "S"`, the `research/downgrade.py` ladder `backtest_2y.py:152` already attaches
to every row; it is causal (every check in `downgrade.CHECKS` reads bars ≤ `entry_idx`) and
it is the same gate P4/R3 in `PHASES.md` would wire in.

**On this book that gate selects worse trades, significantly.**

| sgrade | n | mean R | se |
|---|---:|---:|---:|
| S | 426 | **+0.2721** | 0.0827 |
| A | 728 | +0.5517 | 0.0791 |
| C | 2140 | +0.5335 | 0.0482 |

S minus non-S: **−0.2659R, se 0.0924, t = −2.88 — significant.** Win rates are flat
(46.8 / 48.0 / 46.3), so the whole effect is in payoff size. This is consistent with, and
independent evidence for, the T1 finding in `DIRECTION.md`: *zero of Austin's 34 S days were
graded S by the engine.* The engine's S is not his S, and routing on it today would cost
about a quarter R per trade on top of the day policy's own cost.

**So P5's numbers (+0.2753R, 14/25 months) measure the broken proxy, not his rule.** Do not
report P5 to Austin as "your S rule tested worse." The honest statement is: his rule cannot
be tested on S until something can identify S.

---

## Recommendation

1. **Do not adopt any of P1–P5 as a routing change today.** All five lose ~1R/day against
   the one-position-at-a-time control, and all five cost the durability gate.
2. **Start scoring green-day share as a first-class metric** next to mean R and months green.
   It is the objective his rule optimises, it moves 15 points, and nothing in the repo
   reports it. `research/g71_firsts_policy.py` computes it.
3. **The blocker is unchanged and it is upstream:** an S that means what he means. Until the
   grader can find his S days, "trade the first S of the day" has no first S to trade.
   `sgrade == "S"` is a negative signal — flag that before anyone wires R3 on the assumption
   it is neutral.
4. **Fix the oracle citation** in `DIRECTION.md`: on the current book it is **+3.4404R at
   93.44%, 1,706.4R total**, not +2.2125R at 76.6%.

## Open question for Austin

The rule works as a green-day rule and costs about one R a day in return. Which does he
want measured as "the goal" — total R, or the share of days that finish green? And when
he says "if it wins we're done", does a **scratch** end the day, or does he keep going?
(Measured here as: keep going, a scratch is neither a win nor one of the two losses. 38
scratches in the counted stream, so it barely moves — but it should be his answer, not mine.)
