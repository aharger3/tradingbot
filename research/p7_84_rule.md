# P7 / G1 — the 84% rule, three arms

The 84%-rule re-entry fires **3 times in two years** on the shipped
configuration. This is the measurement of why, and of what the two
alternative arming gates cost.

Rig: `research/p7_84_rule.py` over the on-disk 1-minute archive, 500 sessions 2024-08-21..2026-08-21, 28 symbols, ladder B, stops on the close.
Every arm is the same replay with one env flag moved; nothing else differs.

| arm | flag | reading of the rulebook |
|---|---|---|
| strict | `RULE84_STRICT=1` (shipped) | "you need an A+ entry", scored on the legacy `_grade_pa` ladder |
| loose | `RULE84_STRICT=0` | arm off any counted stop-out on an arming setup |
| S-grade | `RULE84_ARM_SGRADE=1` | "you need an A+ entry", scored on **Austin's** ladder (`research/downgrade.py`): the original must be **S** |

---

## The arm-gate funnel

Where the rule's opportunities go. Counted in-process at the single arm point
(`backtest_week._arm_84`); the last row is read back off the written rows.

| stage | strict — RULE84_STRICT=1 (shipped) | loose — RULE84_STRICT=0 | S-grade — RULE84_ARM_SGRADE=1 |
|---|---|---|---|
| counted full stop-outs | 473 | 521 | 477 |
| on an arming setup (B&R / OCR) | 472 | 472 | 472 |
| past the grade gate | 7 | 472 | 43 |
| past the 11:00 SESSION_END check = ARMED | 5 | 433 | 39 |
| **produced a re-entry signal** | **3** | **116** | **12** |
| of those, traded (not C-grade) | 3 | 79 | 7 |

The gap between *armed* and *produced a signal* is the detector, not the
gate: an armed session still needs price to reclaim the failed entry, on a
bullish/bearish bar, more than 20% of the day's range away from the extreme,
with >=1.5x remaining reward, before 11:00, within the 2-attempt cap.

---

## The re-entries as their own set

| arm | signals | traded | W | L | scratch | win rate | mean R | total R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| strict — RULE84_STRICT=1 (shipped) | 3 | 3 | 2 | 1 | 0 | 66.7% | +2.069 | +6.21 |
| loose — RULE84_STRICT=0 | 116 | 79 | 30 | 49 | 0 | 38.0% | +0.792 | +62.57 |
| S-grade — RULE84_ARM_SGRADE=1 | 12 | 7 | 2 | 5 | 0 | 28.6% | -0.073 | -0.51 |

## The whole book

| arm | signals | traded | W | L | win rate | mean R | total R | months green |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| strict — RULE84_STRICT=1 (shipped) | 45175 | 1016 | 538 | 473 | 53.2% | +0.957 | +972.4 | 23 / 25 |
| loose — RULE84_STRICT=0 | 45288 | 1092 | 566 | 521 | 52.1% | +0.942 | +1028.7 | 25 / 25 |
| S-grade — RULE84_ARM_SGRADE=1 | 45184 | 1020 | 538 | 477 | 53.0% | +0.947 | +965.7 | 23 / 25 |

Deltas against the shipped arm:

- **loose — RULE84_STRICT=0**: +76 traded signals, -1.1 pts win rate, -0.015 mean R, +56.3 total R, +2 months green.
- **S-grade — RULE84_ARM_SGRADE=1**: +4 traded signals, -0.2 pts win rate, -0.010 mean R, -6.7 total R, +0 months green.

---

## What actually changed

The rest of the book is **identical** in all three arms — same trades, same
R, to the cent:

| arm | non-84% trades | their total R |
|---|---:|---:|
| strict — RULE84_STRICT=1 (shipped) | 1013 | +966.17 |
| loose — RULE84_STRICT=0 | 1013 | +966.17 |
| S-grade — RULE84_ARM_SGRADE=1 | 1013 | +966.17 |

So nothing here is a knock-on effect: the arming gate changes the 84%
re-entries and **only** the 84% re-entries. Every delta below is attributable
to that set alone.

### The durability gate

`strict — RULE84_STRICT=1 (shipped)`'s red months, and what each arm did to them:

| month | strict | loose | sgrade | 84% R in that month (loose) |
|---|---|---|---|---|
| 2025-06 | -5.63 | +3.84 | -5.63 | +9.47 |
| 2025-09 | -2.72 | +5.44 | -2.72 | +8.17 |

That is the whole of the loose arm's durability gain — and it is thin.
Drop the single best re-entry from each of those months:

- **2025-06**: +3.84 with the re-entries, -3.55 without the best one (+7.38) — **red again**
- **2025-09**: +5.44 with the re-entries, +0.76 without the best one (+4.68)

### Is the loose arm's edge real, or three fat winners?

n=79 traded re-entries, mean **+0.792R** — but the **median is -1.000R**: 30 win, 49 lose.
The expectancy is a right tail, not a hit rate.

| cut | n | mean R |
|---|---:|---:|
| all traded re-entries | 79 | +0.792 |
| excluding the top 3 | 76 | +0.479 |
| excluding the top 5 | 74 | +0.333 |

| year | n | mean R | total R |
|---|---:|---:|---:|
| 2024 | 9 | -0.419 | -3.77 |
| 2025 | 37 | +0.845 | +31.28 |
| 2026 | 33 | +1.063 | +35.07 |

Even after trimming the five biggest winners the set stays positive, but at
a mean R well under the book it dilutes rather than adds. 2024 is negative.

### Does Austin's grade sort the re-entries themselves?

The S-grade ARM gates on the **original** trade. This instead cuts the loose
arm's re-entries by the grade of the **re-entry**, which is the thing R3 would
actually route on:

| re-entry's grade | n | win rate | mean R | total R |
|---|---:|---:|---:|---:|
| S | 14 | 50.0% | +0.756 | +10.59 |
| A | 18 | 44.4% | +1.179 | +21.21 |
| C | 47 | 31.9% | +0.655 | +30.77 |

It does not sort cleanly — A beats S beats C, and every bucket is under
n=50. This is not a filter worth acting on at this sample size.


## Every re-entry the arms produced

Both grade columns describe the **re-entry signal itself**, not the stopped-out
trade that armed it. `alert-only` rows are C-grade and excluded from traded P&L.

| arm | symbol | day | entry | legacy grade | Austin's grade | outcome | R |
|---|---|---|---|---|---|---|---:|
| strict | TSLA | 2026-05-19 | 09:57 | A | A | win | +3.145 |
| strict | MSFT | 2026-05-29 | 10:33 | A | S | win | +4.062 |
| strict | SPCX | 2026-06-18 | 10:59 | A | C | loss | -1.000 |
| loose | AMD | 2024-08-21 | 10:26 | C | C | win (alert-only) | +2.952 |
| loose | AVGO | 2024-09-09 | 10:24 | B | S | win | +2.529 |
| loose | TSLA | 2024-09-12 | 10:13 | A | A | loss | -1.000 |
| loose | MSFT | 2024-09-13 | 10:17 | A | S | loss | -1.000 |
| loose | NVDA | 2024-09-18 | 10:10 | C | C | loss (alert-only) | -1.000 |
| loose | AVGO | 2024-09-26 | 09:56 | C | C | win (alert-only) | +0.519 |
| loose | AMZN | 2024-09-27 | 10:25 | C | C | win (alert-only) | +0.359 |
| loose | COIN | 2024-10-28 | 09:57 | B | C | loss | -1.000 |
| loose | AVGO | 2024-11-13 | 10:03 | C | S | win (alert-only) | +1.786 |
| loose | ORCL | 2024-11-13 | 10:23 | C | C | win (alert-only) | +1.451 |
| loose | PLTR | 2024-11-21 | 10:15 | C | C | loss (alert-only) | -1.000 |
| loose | PLTR | 2024-11-29 | 10:02 | B | C | win | +0.698 |
| loose | NVDA | 2024-12-16 | 10:05 | A | C | loss | -1.000 |
| loose | AMZN | 2024-12-19 | 09:44 | B | A | loss | -1.000 |
| loose | TSLA | 2024-12-19 | 10:04 | B | A | loss | -1.000 |
| loose | AMD | 2024-12-30 | 10:16 | B | C | loss | -1.000 |
| loose | AAPL | 2025-01-08 | 09:53 | C | C | loss (alert-only) | -1.000 |
| loose | PLTR | 2025-01-14 | 10:55 | B | C | win | +3.227 |
| loose | NFLX | 2025-01-21 | 10:29 | B | C | loss | -1.000 |
| loose | TSLA | 2025-01-22 | 10:35 | B | C | loss | -1.000 |
| loose | ORCL | 2025-01-28 | 10:48 | B | C | loss | -1.000 |
| loose | ORCL | 2025-01-29 | 10:56 | B | C | loss | -1.000 |
| loose | BABA | 2025-02-21 | 10:00 | C | A | win (alert-only) | +2.425 |
| loose | GOOGL | 2025-02-28 | 10:36 | B | C | loss | -1.000 |
| loose | HOOD | 2025-03-05 | 10:19 | B | A | loss | -1.000 |
| loose | AMD | 2025-03-12 | 10:21 | B | C | win | +1.278 |
| loose | GOOGL | 2025-04-08 | 10:59 | B | S | win | +2.408 |
| loose | ORCL | 2025-04-08 | 10:55 | B | C | win | +2.932 |
| loose | BABA | 2025-04-10 | 10:31 | C | C | win (alert-only) | +1.500 |
| loose | COIN | 2025-04-10 | 10:25 | B | S | loss | -1.000 |
| loose | AVGO | 2025-04-25 | 10:43 | B | C | loss | -1.000 |
| loose | NFLX | 2025-04-29 | 10:30 | B | C | win | +4.045 |
| loose | META | 2025-05-16 | 10:24 | B | A | win | +2.711 |
| loose | AAPL | 2025-05-22 | 10:34 | C | A | loss (alert-only) | -1.000 |
| loose | AMD | 2025-05-22 | 10:43 | C | C | loss (alert-only) | -1.000 |
| loose | NFLX | 2025-05-22 | 10:42 | C | A | loss (alert-only) | -1.000 |
| loose | META | 2025-06-04 | 10:51 | A | C | win | +4.160 |
| loose | HOOD | 2025-06-05 | 10:24 | B | S | loss | -1.000 |
| loose | HOOD | 2025-06-10 | 10:09 | B | S | win | +0.923 |
| loose | COIN | 2025-06-12 | 09:54 | B | C | loss | -1.000 |
| loose | TSLA | 2025-06-12 | 10:54 | B | A | win | +7.383 |
| loose | COIN | 2025-06-23 | 10:42 | B | C | loss | -1.000 |
| loose | TSLA | 2025-06-23 | 09:42 | C | C | win (alert-only) | +1.423 |
| loose | COIN | 2025-07-10 | 10:40 | C | S | loss (alert-only) | -1.000 |
| loose | AVGO | 2025-08-08 | 10:33 | B | A | loss | -1.000 |
| loose | AMZN | 2025-08-27 | 09:54 | C | C | loss (alert-only) | -1.000 |
| loose | TSM | 2025-09-22 | 10:14 | B | C | win | +4.484 |
| loose | HOOD | 2025-09-26 | 10:41 | B | C | win | +4.683 |
| loose | INTC | 2025-09-26 | 10:57 | B | S | loss | -1.000 |
| loose | TSLA | 2025-10-01 | 10:07 | X | A | win (alert-only) | +4.193 |
| loose | UBER | 2025-10-10 | 10:21 | C | A | win (alert-only) | +4.225 |
| loose | TSM | 2025-10-21 | 10:38 | A | C | loss | -1.000 |
| loose | HOOD | 2025-10-22 | 09:56 | A | C | loss | -1.000 |
| loose | META | 2025-10-24 | 10:55 | C | C | win (alert-only) | +1.439 |
| loose | IREN | 2025-10-27 | 10:38 | B | S | loss | -1.000 |
| loose | IREN | 2025-10-30 | 10:23 | B | C | loss | -1.000 |
| loose | META | 2025-10-31 | 10:05 | B | C | loss | -1.000 |
| loose | MU | 2025-11-03 | 10:42 | B | C | loss | -1.000 |
| loose | COIN | 2025-11-07 | 10:45 | C | C | loss (alert-only) | -1.000 |
| loose | IREN | 2025-11-07 | 10:00 | A | C | win | +3.660 |
| loose | PLTR | 2025-11-07 | 10:01 | C | C | loss (alert-only) | -1.000 |
| loose | ORCL | 2025-11-10 | 10:33 | C | A | win (alert-only) | +5.150 |
| loose | ORCL | 2025-11-13 | 10:35 | A | C | win | +11.250 |
| loose | AMZN | 2025-11-21 | 10:38 | C | C | loss (alert-only) | -1.000 |
| loose | HOOD | 2025-11-28 | 10:21 | B | S | win | +1.132 |
| loose | PLTR | 2025-12-08 | 10:02 | B | C | loss | -1.000 |
| loose | IREN | 2025-12-16 | 09:52 | B | C | loss | -1.000 |
| loose | TSLA | 2025-12-17 | 10:16 | B | C | loss | -1.000 |
| loose | MU | 2025-12-29 | 10:29 | B | S | loss | -1.000 |
| loose | NFLX | 2026-01-06 | 09:47 | B | C | win | +3.571 |
| loose | IREN | 2026-01-28 | 10:48 | C | C | win (alert-only) | +0.967 |
| loose | COIN | 2026-01-30 | 10:56 | B | A | win | +3.589 |
| loose | AMZN | 2026-02-06 | 10:03 | B | C | loss | -1.000 |
| loose | COIN | 2026-02-10 | 09:50 | B | C | loss | -1.000 |
| loose | UBER | 2026-02-11 | 10:45 | A | C | win | +6.681 |
| loose | IREN | 2026-02-12 | 10:20 | B | S | win | +3.442 |
| loose | MU | 2026-02-12 | 10:02 | A | C | loss | -1.000 |
| loose | ORCL | 2026-02-12 | 10:36 | B | A | win | +5.100 |
| loose | SPY | 2026-02-13 | 10:46 | C | S | loss (alert-only) | -1.000 |
| loose | META | 2026-02-17 | 10:06 | C | C | loss (alert-only) | -1.000 |
| loose | IREN | 2026-02-20 | 10:31 | C | C | loss (alert-only) | -1.000 |
| loose | MU | 2026-03-05 | 10:50 | B | A | loss | -1.000 |
| loose | ORCL | 2026-03-05 | 09:47 | A | A | win | +1.993 |
| loose | ORCL | 2026-03-09 | 10:24 | B | A | loss | -1.000 |
| loose | NFLX | 2026-03-10 | 09:56 | B | C | win | +2.106 |
| loose | COIN | 2026-03-12 | 10:18 | X | C | loss (alert-only) | -1.000 |
| loose | PLTR | 2026-03-12 | 10:36 | B | S | loss | -1.000 |
| loose | MU | 2026-03-18 | 10:45 | C | C | win (alert-only) | +3.325 |
| loose | TSM | 2026-03-27 | 10:51 | C | C | loss (alert-only) | -1.000 |
| loose | TSM | 2026-04-01 | 10:07 | A | C | loss | -1.000 |
| loose | AMD | 2026-04-16 | 10:25 | B | C | win | +7.515 |
| loose | COIN | 2026-04-27 | 10:59 | B | A | win | +4.798 |
| loose | ORCL | 2026-04-29 | 09:43 | C | C | loss (alert-only) | -1.000 |
| loose | GOOGL | 2026-04-30 | 09:52 | B | A | loss | -1.000 |
| loose | AVGO | 2026-05-04 | 09:59 | B | C | loss | -1.000 |
| loose | AVGO | 2026-05-13 | 10:11 | A | C | loss | -1.000 |
| loose | AMZN | 2026-05-19 | 10:07 | A | C | win | +2.480 |
| loose | TSLA | 2026-05-19 | 09:57 | A | A | win | +3.145 |
| loose | MSFT | 2026-05-29 | 10:33 | A | S | win | +4.062 |
| loose | IREN | 2026-06-11 | 09:44 | C | C | loss (alert-only) | -1.000 |
| loose | PLTR | 2026-06-11 | 10:52 | C | A | loss (alert-only) | -1.000 |
| loose | SPCX | 2026-06-18 | 10:59 | A | C | loss | -1.000 |
| loose | META | 2026-06-22 | 10:15 | B | S | win | +3.090 |
| loose | CRM | 2026-06-23 | 10:20 | B | A | loss | -1.000 |
| loose | INTC | 2026-06-24 | 10:08 | B | C | loss | -1.000 |
| loose | COIN | 2026-07-02 | 10:04 | A | C | loss | -1.000 |
| loose | ORCL | 2026-07-06 | 09:46 | C | C | loss (alert-only) | -1.000 |
| loose | AMD | 2026-07-10 | 10:16 | B | C | loss | -1.000 |
| loose | HOOD | 2026-07-14 | 10:23 | B | C | loss | -1.000 |
| loose | NVDA | 2026-07-14 | 10:00 | B | A | loss | -1.000 |
| loose | UBER | 2026-07-27 | 09:46 | C | C | loss (alert-only) | -1.000 |
| loose | MSFT | 2026-07-28 | 10:42 | B | A | win | +2.494 |
| loose | ORCL | 2026-08-06 | 10:49 | B | C | loss | -1.000 |
| loose | AMD | 2026-08-10 | 10:27 | B | C | loss | -1.000 |
| loose | META | 2026-08-10 | 10:13 | C | A | win (alert-only) | +3.997 |
| loose | MU | 2026-08-11 | 10:30 | C | C | scratch (alert-only) | +3.629 |
| sgrade | TSLA | 2024-09-12 | 10:13 | A | A | loss | -1.000 |
| sgrade | AVGO | 2024-11-13 | 10:03 | C | S | win (alert-only) | +1.786 |
| sgrade | NFLX | 2025-01-21 | 10:29 | B | C | loss | -1.000 |
| sgrade | ORCL | 2025-01-29 | 10:56 | B | C | loss | -1.000 |
| sgrade | BABA | 2025-04-10 | 10:31 | C | C | win (alert-only) | +1.500 |
| sgrade | COIN | 2025-04-10 | 10:25 | B | S | loss | -1.000 |
| sgrade | NFLX | 2025-05-22 | 10:42 | C | A | loss (alert-only) | -1.000 |
| sgrade | META | 2025-10-24 | 10:55 | C | C | win (alert-only) | +1.439 |
| sgrade | ORCL | 2026-03-05 | 09:47 | A | A | win | +1.993 |
| sgrade | MU | 2026-03-18 | 10:45 | C | C | win (alert-only) | +3.325 |
| sgrade | MSFT | 2026-07-28 | 10:42 | B | A | win | +2.494 |
| sgrade | AMD | 2026-08-10 | 10:27 | B | C | loss | -1.000 |

---

## Cross-check: what the corpus says (P11)

`research/p11_parameter_provenance.md` row **A8** scored
`RULE84_ARM_BNR_ONLY` **CONTRADICTED (partial — source narrower)**:

> TRADER_SAID `scarface-rules-videos.md:162` — "the thing you need to know about
> the 84% rule is you need an A plus entry." Source restricts arming to
> A+-quality entries; the coded gate arms on any break-and-retest stop-out
> regardless of quality.

That is an independent line of evidence, arrived at from what a trader actually
said rather than from P&L, and it lands on the same side as this measurement:
**there should be a quality gate on arming, and the loose arm is the one the
corpus rules out.** Two different methods, same conclusion, is the strongest
result in this ticket.

The question P11 leaves open is the one this A/B was built to answer — *which*
ladder "A+" means — and the honest answer is that this measurement does not
settle it. Reading it as Austin's `S` produced 12 signals and 7 traded trades.
n=7 cannot rule a gate in or out. So the corpus says *gate on quality*, and the
book says *the legacy reading currently shipped is not beaten by the one
alternative testable today*. Both are consistent with leaving the default alone
and revisiting after R3.

Note the direction of the disagreement, because it matters: P11 contradicts the
**loose** arm, not the strict one. Nothing in the corpus sweep says the shipped
gate is wrong — only that removing it would be.

---

## Verdict

**The strict gate is not protecting the book — but it is not costing much
either.** The loose arm's re-entries are a positive-expectancy set (+0.792R on
n=79) that is nonetheless *below the book's own mean*, so switching the default
buys +56R of total R and two green months at the price of 1.1 points of win rate
and 0.015R of mean R. Against a money gate written as **mean R >= 2.0 and win
rate >= 55%**, both of the numbers the gate is written in move the wrong way.

**The S-grade arm is the worst of the three and should not be shipped.** Gating
on the original trade's S grade produced 12 signals and 7 traded, at -0.073R.
It is the arm the diagnosis predicted would work, and it did not. Two honest
reasons, and they point in different directions:

1. n=7 is not a measurement. Nothing here rules the idea in or out.
2. The premise may just be wrong. "The original was clean" is a statement about
   the setup that **already failed**. A stop-out on an S setup may be evidence
   the read was wrong, not evidence the level is worth a second bite.

**Recommendation: keep `RULE84_STRICT=1` as the shipped default. Change nothing.**
Reasons, in order:

- No arm reaches the money gate, or moves the book toward it. The gate is mean R
  2.0; the arms sit at +0.957 / +0.942 / +0.947. This is not where the 2.0R comes
  from, and G7 already established that entry selection, not management, is the
  binding constraint.
- The loose arm's headline (25/25 months green) is **one trade deep**. Remove the
  single best re-entry from 2025-06 and the month is red again. A durability claim
  that survives on one +7.4R outlier is not a durability claim.
- More than half the loose re-entries lose (median -1.000R). Austin's own framing
  of the rule is that it is a high-probability second bite; a 38% win rate is not
  that, and shipping it would put a losing-more-often-than-not setup into the book
  under a name that says 84%.

**What this does settle**, which is the point of the ticket: the rule is dead in
backtest because of the gate, not the detector — 7 of 472 opportunities survive
the strict gate. Open it and 116 signals appear. So the question "is the 84% rule
broken?" is answered: it is gated off, deliberately, and opening the gate is
worth roughly nothing on the metrics the project is graded on.

**What is still open** (queue it, do not do it here):

- The loose arm's re-entries are strongly year-dependent (2024 negative, 2026
  +1.06R). Worth a walk-forward before anyone reads +0.792R as stable.
- The detector, not the gate, is the next bottleneck: 433 armings produced 116
  signals. Nobody has autopsied the 317 armings that never fired.
- R2/R3 own the real decision. If `downgrade.py` is ever wired into detection,
  this A/B should be re-run on that book — the S arm's n=7 is a sample-size
  result, not a verdict on Austin's ladder.

---

Reproduce: `python research/p7_84_rule.py run --arm {strict,loose,sgrade}` then `python research/p7_84_rule.py report`.
