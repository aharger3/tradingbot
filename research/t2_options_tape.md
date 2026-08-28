# T2 — The options tape

Every number here comes from `research/t2_options_tape.py` (in this directory, run it)
and `black_scholes.py` (repo root, has its own `python black_scholes.py` selfcheck).
Inputs: `research/g3_arm_ow1.json` (the shipped 2-year book, 1,017 traded rows,
2024-08-21..2026-08-21, 500 sessions, 28 symbols) and `data_archive/<SYM>/<DAY>.csv`.
No network. Written 2026-08-28 against `3810ea87`.

```
python research/t2_options_tape.py --selfcheck    # the ticket's three checks
python research/t2_options_tape.py                # every table below
```

**The book is pinned by hash.** This tree is worked by several tracks at once and
`research/g3_arm_ow1.json` was transiently rewritten under this run (T11's stop-fill
change, briefly, before it was restored). Every number below was measured on:

```
book a05ebf5a84d92da2  n=1017  mean r +0.9551  PINNED
```

`--selfcheck` refuses to run against any other book and every section prints that
fingerprint first. **When T11 lands for real, these numbers must be regenerated, not
re-read** — the fingerprint is what makes that impossible to miss.

---

## 0. Held-out S recall — first, before any in-sample number

| | held-out S recall | in-universe |
|---|---|---|
| before T2 | **3/15 = 20.0%** | 2/12 = 17% |
| after T2 | **3/15 = 20.0%** | 2/12 = 17% |

**+0.0 points. T2 does not touch the recall gate and was never going to.**
`research/marks/probe_omen_test1_2026-08-27.jsonl`, census re-counted by this script:
15 S / 27 A / 16 C / 42 X. Provenance: `python research/t70_test1_score.py`, re-run for
this ticket, `research/t70_test1_score.md` regenerated **byte-identical**.

T2 is a scoring skin on an already-selected book — same rows in, same rows out, a
different unit on the P&L. The files it touches are `black_scholes.py` (new),
`options_sizer.py` (sizing only, flag OFF), `research/t2_options_tape.{py,md}` (new).
None is on the detection path (`signal_runner` / `backtest_week` / `backtest_2y` /
`downgrade`), and `--selfcheck` asserts that by reading their source.

---

## The headline, and the contradiction it fixes

The ticket asked me to reproduce the prototype and then report that the two halves of
the money gate **pull in opposite directions on the real instrument** — mean R rises
while win rate falls 53.4% → 38.5%.

**Reproduced exactly, and then refuted.** The win-rate collapse is not the instrument.
It is an unlabelled change of **exit convention** inside the prototype.

`research/x13_new_angles.py::option_r` prices **one exit for the whole position** at
`row["exit"]`. But **538 of the 1,017 rows carry `scaled: true`**: the shipped exit plan
is `backtest_week.SCALE_PLAN = "hod_then_runner_be"` — 50% off at the as-of-entry session
extreme, 50% riding to `exit` — and the book's `r` is the blend
`0.5*scale_r + 0.5*run_r` (`backtest_week.py:249-253`). On **536 rows**
`(exit − entry)/risk ≠ r`. So the prototype compared **contract-under-one-exit** against
**underlying-under-the-ladder**. Two variables moved; one was named.

Score both conventions on both instruments and the comparison closes:

| convention | instrument | mean R | win rate |
|---|---|---:|---:|
| SINGLE (full size to `exit`) | contract, IV 1.2× | **+1.3551** | **38.5%** |
| SINGLE (full size to `exit`) | underlying | +0.9994 | **38.8%** |
| LADDER (the book's own 50/50) | contract, IV 1.2× | **+1.3025** | **52.7%** |
| LADDER (the book's own 50/50) | underlying | **+0.9551** | **53.4%** |

**The instrument costs 0.3 win-rate points under SINGLE and 0.7 under LADDER — not 15.**
The 15-point drop was the scale-out ladder being removed, and it drops the *underlying*
book by exactly as much (53.4% → 38.8%). Holding full size into the fat right tail is
what trades win rate for mean R, and it does so in stock points too.

What the instrument is actually worth, matched convention against matched convention:

| IV | Δ mean R (contract − underlying), SINGLE | Δ mean R, LADDER | Δ win rate, LADDER |
|---|---:|---:|---:|
| 1.0× realised | +0.4994 | **+0.4783** | −0.7 pt |
| 1.2× realised | +0.3557 | **+0.3474** | −0.7 pt |
| 1.5× realised | +0.1947 | **+0.2027** | −0.8 pt |

The effect is the same size under either convention, which is what "this is the
instrument, not the exit plan" looks like when it is measured properly. It is **21× to 50× the ±0.0095 R error bar**. It is not noise.

**And it does not reach the gate.** The money gate is mean R ≥ 2.0. The book is
+0.9551; the gap is 1.0449 R. The instrument closes **33%** of it at IV 1.2×, **46%** at
IV = realised, **19%** at 1.5×. The remaining 0.70 R has to come from somewhere else —
T3's selection ranker is the only measured ceiling that clears both halves.

---

## 1. The book, both instruments, three IV arms

`python research/t2_options_tape.py book`

Model: strike = entry (perfectly ATM), expiry = the 16:00 close, sigma = the day's
Parkinson range vol × the IV multiplier, **1R = the modelled premium loss when the
underlying reaches the stop**, priced at the entry minute so it is knowable at entry.

### SINGLE — x13's convention, full size to `exit`. Reproduces the prototype.

| IV | n | contract R | win | underlying R | win |
|---|---:|---:|---:|---:|---:|
| 1.0× | 1017 | **+1.4988** | 38.5% | +0.9994 | 38.8% |
| 1.2× | 1017 | **+1.3551** | 38.5% | +0.9994 | 38.8% |
| 1.5× | 1017 | **+1.1941** | 38.5% | +0.9994 | 38.8% |

x13 published +1.4988 / +1.3551 / +1.1941 and 38.5% win. Reproduced to 4 decimal
places by an independently written pricer; `--selfcheck` asserts it and fails the run
if it ever drifts. Contract R distribution at 1.2×: p10 −1.13, **p50 −0.32**,
**p90 +6.26**, max +21.36 — x13's p90 +6.26 / p50 −0.32 exactly.

### LADDER — the book's own 50/50 scale plan. The apples-to-apples arm.

The scale price is recovered **exactly** from the book by algebra on fields it already
stores (`scale_r = 2r − run_r`); the book does not record `scale_level`. The recovered
ladder reproduces **1,012 of 1,017** book `r` values to 1e-9 — the other 5 are the EOD
scratches, where the writer rounds `r` to 3dp and the lost digits cannot be recovered
(max 0.0016 R on a row, 1.77e-06 R on the book mean, three orders under the error bar).

The book does not record the **minute** the scale fired either. It is bounded — not
before entry, not after exit — so the ladder is a band over that timing, never a point:

| IV | scale timed at | contract R | win | underlying R | win |
|---|---|---:|---:|---:|---:|
| 1.0× | entry | +1.4578 | 52.8% | +0.9551 | 53.4% |
| 1.0× | midpoint | **+1.4334** | 52.7% | +0.9551 | 53.4% |
| 1.0× | exit | +1.4065 | 52.7% | +0.9551 | 53.4% |
| 1.2× | entry | +1.3323 | 52.7% | +0.9551 | 53.4% |
| 1.2× | midpoint | **+1.3025** | 52.7% | +0.9551 | 53.4% |
| 1.2× | exit | +1.2696 | 52.4% | +0.9551 | 53.4% |
| 1.5× | entry | +1.1954 | 52.7% | +0.9551 | 53.4% |
| 1.5× | midpoint | **+1.1578** | 52.6% | +0.9551 | 53.4% |
| 1.5× | exit | +1.1158 | 51.9% | +0.9551 | 53.4% |

The whole scale-timing band is **0.0627 R wide** at IV 1.2× — 6.6× the error bar, so it
is not ignorable, but it is small next to the +0.3474 R the instrument itself is worth.

`k = |delta₀| · |entry−stop| / premium_risk` = mean **1.1166**, median 1.0691. `k > 1`
because the premium risk is convex-shrunk: the loss decelerates on the way into the
stop, so the contract's 1R buys ~11% more underlying distance than the flat-0.5-delta
model assumes. That is the first thing `DEFAULT_DELTA = 0.5` gets wrong, and it is
wrong in the direction of **under-sizing**.

---

## 2. Per month — and durability moves

`python research/t2_options_tape.py month` · IV 1.2×, LADDER (midpoint)

| month | n | contract R | win | underlying R | win | green |
|---|---:|---:|---:|---:|---:|---|
| 2024-08 | 16 | +1.0907 | 56.2% | +0.8393 | 56.2% | both |
| 2024-09 | 26 | +0.3980 | 38.5% | +0.2715 | 38.5% | both |
| 2024-10 | 21 | +1.4265 | 57.1% | +1.1592 | 57.1% | both |
| 2024-11 | 35 | +1.1022 | 60.0% | +0.9056 | 60.0% | both |
| 2024-12 | 28 | +0.6854 | 42.9% | +0.4018 | 42.9% | both |
| 2025-01 | 48 | +0.8972 | 50.0% | +0.6805 | 50.0% | both |
| 2025-02 | 35 | +0.5649 | 51.4% | +0.4896 | 51.4% | both |
| 2025-03 | 40 | +1.3135 | 65.0% | +1.0701 | 65.0% | both |
| 2025-04 | 67 | +1.4430 | 62.7% | +1.2457 | 62.7% | both |
| 2025-05 | 24 | +0.7463 | 50.0% | +0.8444 | 54.2% | both |
| **2025-06** | 26 | **+0.0361** | 30.8% | **−0.2165** | 30.8% | **contract only** |
| 2025-07 | 28 | +1.7968 | 75.0% | +1.3973 | 75.0% | both |
| 2025-08 | 37 | +1.1258 | 51.4% | +1.0581 | 56.8% | both |
| **2025-09** | 29 | **−0.1343** | 37.9% | **−0.0939** | 37.9% | **red in both** |
| 2025-10 | 45 | +0.4259 | 40.0% | +0.3686 | 42.2% | both |
| 2025-11 | 46 | +1.9181 | 52.2% | +1.4075 | 52.2% | both |
| 2025-12 | 35 | +1.6254 | 60.0% | +1.2187 | 60.0% | both |
| 2026-01 | 46 | +1.3604 | 52.2% | +0.9871 | 52.2% | both |
| 2026-02 | 54 | +1.1851 | 46.3% | +0.9242 | 48.1% | both |
| 2026-03 | 63 | +0.9577 | 42.9% | +0.6396 | 42.9% | both |
| 2026-04 | 49 | +1.2290 | 53.1% | +0.9965 | 55.1% | both |
| 2026-05 | 57 | +2.3441 | 57.9% | +1.3892 | 57.9% | both |
| 2026-06 | 71 | +1.3115 | 47.9% | +0.8846 | 49.3% | both |
| 2026-07 | 64 | +2.2595 | 65.6% | +1.6202 | 65.6% | both |
| 2026-08 | 27 | **+3.9790** | 63.0% | +2.3427 | 63.0% | both |

**Durability: 24 of 25 green on the contract against 23 of 25 on the underlying.**
2025-06 flips green (−0.2165 → +0.0361). 2025-09 stays red on both — the instrument
does not launder it, which is the right answer: T18 still has a regime to name.

**Three** months clear mean R 2.0 on the contract (2026-05, 2026-07, 2026-08; 2025-11 at
+1.92 is close); **one** clears it on the underlying (2026-08).

---

## 3. Per setup family

`python research/t2_options_tape.py family` · IV 1.2×

### SINGLE

| family | n | contract R | win | underlying R | win | contract p90 |
|---|---:|---:|---:|---:|---:|---:|
| break_and_retest | 947 | +1.3464 | 38.3% | +1.0304 | 38.6% | +6.20 |
| one_candle_rule | 67 | +1.3741 | 40.3% | +0.5038 | 40.3% | +6.62 |
| reentry_84_rule | 3 | +3.6846 | 66.7% | +2.2819 | 66.7% | +6.73 |

### LADDER (midpoint)

| family | n | contract R | win | underlying R | win | contract p90 |
|---|---:|---:|---:|---:|---:|---:|
| break_and_retest | 947 | +1.3026 | 52.9% | +0.9880 | 53.6% | +5.39 |
| one_candle_rule | 67 | +1.2129 | 49.3% | +0.4413 | 49.3% | +5.11 |
| reentry_84_rule | 3 | +3.2905 | 66.7% | +2.0690 | 66.7% | +6.00 |

**OCR is the family the instrument rescues.** In stock points it books +0.4413 R, less
than half of B&R's +0.9880. As the contract it books +1.2129 against B&R's +1.3026 —
**the gap closes from 0.55 R to 0.09 R.** Measured, not guessed, here is why (SINGLE,
IV 1.2×):

| family | n | delta leg | convexity leg | theta leg | held (median) | premium risk |
|---|---:|---:|---:|---:|---:|---:|
| break_and_retest | 947 | +1.1088 | +0.4458 | −0.2082 | 6 min | $0.184 |
| one_candle_rule | 67 | +0.6396 | **+0.7625** | **−0.0280** | 5 min | $0.292 |
| reentry_84_rule | 3 | +2.5959 | +1.1633 | −0.0746 | 7 min | $0.291 |

OCR has a **weaker linear leg** (+0.64 vs +1.11 — which is its poor underlying R), a
**71% larger convexity leg**, and a theta leg **7× smaller**. Net non-linearity:
**+0.7345 R for OCR against +0.2376 R for B&R.** OCR's edge is not in the direction of
the move, it is in the shape of it — and stock points cannot see shape.
`DIRECTION.md`'s open bug — "One Candle Rule is 4,389 detections → 67 traded" — is
being argued down on a metric that under-prices the setup by 0.77 R a trade. **n=67,
so this is a flag, not a verdict.** `reentry_84_rule` at n=3 is not a number at all.

By outcome label (LADDER, IV 1.2×): win 538 rows +3.4407 (underlying +2.6690), loss 474
rows **−1.1170** (underlying −1.0000), scratch 5 rows +0.6134 (underlying +1.8924).

---

## 4. Theta and convexity, separated

`python research/t2_options_tape.py theta` · SINGLE, IV 1.2×

The decomposition is an **identity**, not a Taylor series (max residual 3.55e-15 over
1,017 rows, asserted by `--selfcheck`):

```
contract R  =  delta leg          d0*(Sx-S0)/risk                    the linear part
            +  convexity leg      [P(Sx,T0) - P0 - d0*(Sx-S0)]/risk  curvature, time frozen
            +  theta leg          [P(Sx,T1) - P(Sx,T0)]/risk         decay, price frozen
```

| leg | mean | median | p10 | p90 |
|---|---:|---:|---:|---:|
| delta | +1.0823 | +0.0000 | −1.1427 | +4.9411 |
| **convexity** | **+0.4688** | +0.1134 | +0.0000 | +1.2766 |
| **theta** | **−0.1960** | −0.0411 | −0.3241 | −0.0072 |
| = contract R | +1.3551 | −0.3159 | −1.1347 | +6.2596 |

**Convexity beats theta by +0.2728 R per trade.** Austin's runner thesis, priced: it is
right, by a factor of 2.4 to 1, on this book, at this IV, at these holding times
(median 6 minutes, p90 32, max 344). The convexity leg is ≥ 0 and the theta leg ≤ 0 on
**all 1,017 rows** — asserted, not assumed.

Where each leg is earned:

| outcome | n | delta | convexity | theta | contract R |
|---|---:|---:|---:|---:|---:|
| win | 538 | +2.9954 | **+0.7818** | −0.2370 | +3.5401 |
| loss | 474 | −1.1041 | +0.1041 | −0.1170 | −1.1170 |
| scratch | 5 | +2.5068 | +1.3689 | **−3.2623** | +0.6134 |

### The one table Austin should read

| held (min) | n | convexity | theta | **net** | contract R |
|---|---:|---:|---:|---:|---:|
| 0–5 | 404 | +0.3156 | −0.0287 | **+0.2869** | +0.6995 |
| 5–15 | 374 | +0.3859 | −0.0928 | **+0.2930** | +1.4676 |
| 15–30 | 126 | +0.6354 | −0.2294 | **+0.4061** | +2.1411 |
| 30–60 | 66 | +1.1842 | −0.4884 | **+0.6957** | +3.1947 |
| 60–120 | 27 | +0.7897 | −0.9587 | **−0.1690** | +2.2608 |
| 120+ | 20 | +1.2714 | −3.2995 | **−2.0282** | +0.2516 |

**Convexity out-earns decay out to about 60 minutes, and loses badly past it.** Between
30 and 60 minutes the contract earns +0.70 R of pure non-linearity — that is the runner
thesis working. Past 120 minutes (20 rows, the EOD holds) decay costs −2.03 R net and
the contract books +0.2516 R where the underlying books far more. **For a hold longer
than an hour the 0DTE contract is the wrong instrument**, and no exit rule fixes that —
it is the contract, not the trade. That is a real constraint on the runner design and
it has never been stated in this repo.

### The stop-out arm, stated exactly

- **At frozen time a stop-out is exactly −1.0000 R by construction** (max deviation
  0.00e+00 across all 1,017 rows — `--selfcheck` check 1). That is the definition of
  the R unit: the premium lost when the underlying reaches the stop *now*.
- **Realised, the 474 stop-outs book −1.1170 R**, because a median 10.8 minutes of decay
  ran before the bar closed beyond the level. The whole gap is the theta leg: −0.1170 R.
- The underlying scores every one of those rows a flat −1.0000. The contract does not,
  and cannot.

### The −1.25R floor, which has never bound on a single underlying row

| | rows worse than −1.25R | worst row |
|---|---:|---:|
| underlying | **0 of 1,017** | −1.000 |
| contract, SINGLE | **53 of 1,017 (5.2%)** | **−14.399 R** |
| contract, LADDER | **44 of 1,017 (4.3%)** | **−7.895 R** |

`CLAUDE.md` records that the −1.25R floor "never binds today — it exists for the
slippage case". **On the instrument he actually trades it binds on one row in twenty,
and without it the worst row is −7.9 R.** The mechanism is not slippage: a stop that
triggers on the **underlying** does not cap the **contract's** loss. Max loss is the
whole premium, `−p0/risk` — median **−5.27 R**, p10 **−18.27 R**, worst **−88.89 R**.
"Flat on the stock" can be several R on the option, paid entirely in decay.

This is the single largest thing `DEFAULT_DELTA = 0.5` hides, and it is a risk
statement, not a P&L one. `paper_trader.py:81-91` says in its own comment that the
floor is not applied on the premium side. Whoever wires it will meet this live where
the backtest has never met it.

---

## 5. Assumptions, and the sensitivity of the headline to each

`python research/t2_options_tape.py assume`

**There is no options tape in this repo.** No option price, IV, spread or fill in this
document was read from a market. The underlying bars, the book's entry/stop/exit, the
holding times and the daily ranges are real; everything with a dollar sign on the option
side is modelled. Headline = **LADDER, midpoint, IV 1.2× = +1.3025 R** (SINGLE +1.3551).
Error bar on an A/B of this book: **±0.0095 R**.

| # | assumption | arm | mean R | Δ headline |
|---|---|---|---:|---:|
| **A1** | IV level | 1.0× realised Parkinson | +1.4334 | **+0.1309** |
| | | 1.2× (headline) | +1.3025 | 0 |
| | | 1.5× realised | +1.1578 | **−0.1447** |
| **A2** | IV is **look-ahead** | prior session's range instead (n=1016) | **+0.9873** | **−0.3153** |
| **A3** | strike is perfectly ATM | K on the real strike grid | +1.6684 | +0.3658 † |
| **A4** | carry r = q = 0 | r = 5% annual | +1.3003 | **−0.0022** |
| **A5** | fill at mid, no spread | $0.05 round trip | +0.9906 | **−0.3120** |
| | | $0.10 round trip | +0.6786 | −0.6239 |

**A1 — IV level.** The three arms *are* the sensitivity. ±0.14 R across the plausible
band, 15× the error bar. Not decisive, but the headline is quotable only with its IV
attached.

**A2 — the IV is look-ahead, and this is the biggest honest hit.** `drange` is the
**full-session** high-low range. It is not known at 09:42. Re-priced on the **prior
session's** RTH Parkinson range — genuinely ex-ante, from `data_archive` — the book
books **+0.9873 R (LADDER) / +1.0435 (SINGLE)**, a −0.3153 R hit that removes **91% of
the instrument's advantage**. One row has no earlier session on disk. This is the
number to carry into any decision: *the shipped-quality figure is +1.30; the figure you
could have known at the time is +0.99, which is the underlying book to within
0.03 R.* Priced on tomorrow's realised vol, the contract wins; priced on yesterday's,
it is a wash. A real IV series — which no one in this repo has — sits somewhere between.

**A3 — read the median, not the mean, on this row.** † Rounding K onto the real
`$1–$5` strike grid moves the *mean* +0.3658 R but the *median* barely at all
(−0.3159 → −0.3312). Off ATM the premium risk — **the R denominator** — can collapse:
minimum $0.0005 on the grid against $0.0440 at the money, and 4 rows blow past |25 R|
(max +206.9 R). So the ATM assumption is load-bearing for the **unit**, not the centre.
**A real strike grid needs a minimum-premium guard before contract R is quotable per
trade.** That is a ship blocker for anything that sizes off this number.

**A4 — carry.** r = 5% annual moves the book −0.0022 R over a 0DTE contract. That is
0.23× the error bar. **r = q = 0 is safe and now measured rather than asserted.**

**A5 — the spread, carried from `research/x9_live_gap_premortem.md` §2.2 as an explicit
assumption.** x9 assumed a **$0.05 round trip** and charged the *underlying* book
−0.2042 R. On the **contract** the same nickel costs **−0.3120 R**, because the
contract's 1R is a thinner unit: modelled premium risk per share is a **median $0.19**
(p10 $0.08, p90 $0.46).

| round trip | median R cost | mean R cost | LADDER after |
|---:|---:|---:|---:|
| $0.01 | 0.0514 | 0.0624 | +1.2402 |
| $0.02 | 0.1028 | 0.1248 | +1.1778 |
| **$0.05 (x9)** | **0.2571** | **0.3120** | **+0.9906** |
| $0.10 | 0.5142 | 0.6239 | +0.6786 |
| $0.15 | 0.7712 | 0.9359 | +0.3666 |

**A $0.209 round-trip spread erases the entire contract edge.** x9 put the underlying's
death point at $0.162. Nobody has read a real NBBO on these names' 0DTE contracts —
Polygon returns `403 NOT_AUTHORIZED` on the options snapshot and Tastytrade session auth
is failing (x9 §2.2). Until someone logs a week of real quotes, this row is a parameter,
not a number.

**A6 — the entry and exit prices are the book's, and x9 says they are optimistic.**
961 of 1,017 rows book a price the bar traded before it closed; paying the close costs
−0.6653 R on the underlying. **Contract R inherits that whole.** It is not re-litigated
here and A5 and A6 are **not additive by hand** — they interact through the same
denominator. T11 owns the fill convention.

**A7 — flat vol surface.** One sigma from entry to exit. No smile, no term structure,
no IV crush on the news-day and open-drive setups. Unmeasurable without an options tape.
Direction is known: IV crush would make the winners worse, so **the headline is biased
optimistic by an unmeasured amount.**

**A8 — expiry = the 16:00 close.** Time to expiry is floored at 1.0 minute at entry and
0.5 minutes at exit so a run-to-the-bell prices instead of dividing by zero. 5 of 1,017
rows exit inside the last 5 minutes; those five are also the 5 scratches, and they carry
the −3.2623 R theta leg above. **This is a modelling floor doing real work on 5 rows.**

**A9 — no commission, no market impact, continuous size.** x9 §2.2: the sizer wants a
median 47 and up to 200 contracts of a 0DTE ATM option filled at the mid; 17.4% of rows
want ≥100. Modelled nowhere, including here.

---

## 6. What shipped, and the proof it changed nothing

**`black_scholes.py`** (new, repo root). Textbook Black-Scholes-Merton with analytic
delta / gamma / vega / theta and a Parkinson range-vol helper. No I/O, no globals, no
flags. `python black_scholes.py` checks put-call parity with carry on, every greek
against a central difference, the convexity inequality, and the degenerate T→0 and
sigma→0 limits. Before T2 the repo had no pricer: `grep` finds `norm.cdf` in exactly
two research scripts, both computing p-values.

**`options_sizer.py`** (modified). `ENABLE_CONTRACT_R`, **default OFF**, read once from
the environment. **OFF, `atm_delta()` returns `DEFAULT_DELTA` before touching the
pricer and the premium arithmetic is bit-for-bit what it was.** ON — and only with an
`iv` and a `minutes_to_expiry` handed in, because there is no options tape and no safe
IV to invent — `premium_risk` becomes a full reprice at the stock stop instead of
`stock_risk × 0.5`. With neither input it degrades to the old constant rather than
guessing.

`DEFAULT_DELTA = 0.5` is **not** deleted. It is still the fallback and still what ships.

### The check that the book did not move

1. **Structural.** `--selfcheck` reads `backtest_2y.py`, `backtest_week.py` and
   `signal_runner.py` and asserts that none of them contains the string `options_sizer`
   or `black_scholes`. The 2-year book generator cannot see this flag.
2. **Empirical.** `ON_WATCH=1 python backtest_2y.py --days 730 --out research/_t2_book_flagoff.json`
   re-ran the full replay with the flag off. Canonical SHA-256 over all 45,193 rows:

   ```
   shipped research/g3_arm_ow1.json  a05ebf5a84d92da2cc0797bf0e15b10e74db59d4a3d0fe023d7d4fff47cc0ad2
   regenerated, flag OFF             a05ebf5a84d92da2cc0797bf0e15b10e74db59d4a3d0fe023d7d4fff47cc0ad2
   ```

   Identical. The only differing byte anywhere in the file is `meta.generated`, the
   wall-clock stamp. 45,193 signals, 1,017 traded, both.
3. `python spec2_grading_check.py` still passes.

### `--selfcheck`, all green

```
[ok] stop-out == -1R by construction on all 1017 rows (max dev 0.00e+00)
[ok] recovered 50/50 ladder reproduces 1012/1017 book r exactly; the 5
     EOD scratches differ by <=0.0016 R (book rounds r to 3dp), and
     the book mean moves 1.77e-06 R -- under the +/-0.0095 error bar
[ok] delta + convexity + theta == contract R (max residual 3.55e-15)
[ok] convexity leg >= 0 and theta leg <= 0 on all 1017 rows
[ok] IV 1.0x SINGLE = +1.4988  (x13 prototype +1.4988)
[ok] IV 1.2x SINGLE = +1.3551  (x13 prototype +1.3551)
[ok] IV 1.5x SINGLE = +1.1941  (x13 prototype +1.1941)
[ok] contract win rate 38.5% (x13 38.5%) vs underlying 53.4%
[ok] ENABLE_CONTRACT_R defaults OFF; iv/minutes are inert while it is
[ok] backtest_2y / backtest_week / signal_runner import neither
     options_sizer nor black_scholes
ALL T2 SELFCHECKS PASSED
```

---

## 7. What this track did not settle

- **Order type is still open.** Austin, 2026-08-28: *"market and limit orders a
  different beast."* Every figure here is a **mid fill**, which is neither. A5 is the
  price of that gap and nothing here decides it.
- **A2 is the finding that decides whether the instrument is a real lever.** Realised
  vol says +1.30; yesterday's vol says +0.99. Somebody has to get a real IV series
  before the +0.35 R is spendable.
- **A3 blocks per-trade sizing.** Contract R off ATM has an unbounded denominator. A
  minimum-premium guard has to exist before this number sizes anything.
- **OCR at n=67 is a flag, not a verdict.** The instrument closes its gap to B&R from
  0.55 R to 0.09 R, which is a reason to re-open `DIRECTION.md`'s OCR bug, not to
  conclude it.
- **Holds over 60 minutes are the wrong instrument.** 47 rows, and past 120 minutes the
  net non-linearity is −2.03 R. That is a constraint on the runner design that belongs
  in the rulebook, and it needs Austin — it is a claim about what he should hold, not
  about what the engine measured.
- **The −1.25R floor needs a decision it has never needed.** It binds on 4.3% of contract
  rows and on 0% of underlying rows. Applying it caps the worst row at −1.25 instead of
  −7.90; not applying it means one trade in twenty can lose several R while the
  underlying stop was never breached. That is Austin's call, not the engine's, and it is
  a different question from the slippage case the floor was written for.
- **T2 did not move the recall gate, and the recall gate is still the wound.** 3/15.
