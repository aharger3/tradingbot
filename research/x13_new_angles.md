# X13 — new angles: what the twelve lanes are not looking at

Run: `python research/x13_new_angles.py` (script ships beside this file; seven sections,
all offline, all off `research/g3_arm_ow1.json` + `research/x1_mfe_mae.json` +
`data_archive/`). Every number below is printed by that script.

The twelve lanes converged on one shape: build an arm, A/B it against the shipped book,
watch it move less than the error bar. G15 is right that the loop cannot decide anything
at the size its arms move. The way out is not more arms — it is to attack the three
things the project has structurally avoided: **the instrument**, **day selection**, and
**the ceiling of the feature set**.

Twelve angles, ranked by expected value. Six carry a number I measured today; six are
specified measurements with a stated cost.

---

## The one-paragraph summary

Two levers were never priced, and each is larger than every exit lane in the digest
combined. **The instrument**: the same 1,017 trades, scored as the 0DTE ATM contracts
they are actually traded in rather than as the underlying, book **+1.1941 R to +1.4988 R**
instead of +0.9551 R — convexity, minus theta. **Day selection**: pick one trade per
calendar day with hindsight and the book is **+2.2125 R at 76.6% win**, which clears both
halves of the money gate; X1's exit oracle needed hindsight over the whole path to reach
+3.4986 R, this one needs only a ranking of at most 8 candidates. Everything else the
project has been tuning moves ±0.06 R.

---

## 1 — THE INSTRUMENT. R is scored on the wrong thing. (measured)

`options_sizer.py:20` is `DEFAULT_DELTA = 0.5` and that flat linear delta is the entire
options model in this repo. There is no Black-Scholes, no gamma, no theta anywhere
(`grep -rl "black_scholes\|norm.cdf" --include=*.py` finds two research scripts, both
using the normal CDF for p-values). X9 states it plainly: *"there is NO options tape in
this repo at all."* So two years of R — and the ±0.0095 R error bar, and the 2.0 gate —
are measured on the underlying, on an instrument nobody trades.

Re-scoring the same 1,017 rows as 0DTE ATM contracts (strike = entry, expiry = today's
close, sigma = the day's Parkinson range vol, 1R defined the way `options_sizer` defines
it — the modelled premium loss at the stop, so a stop-out is −1R by construction):

| IV assumption | contract mean R | contract win | underlying |
|---|---:|---:|---:|
| IV = 1.0x realised | **+1.4988** | 38.5% | +0.9551 / 53.4% |
| IV = 1.2x realised | **+1.3551** | 38.5% | +0.9551 / 53.4% |
| IV = 1.5x realised | **+1.1941** | 38.5% | +0.9551 / 53.4% |

The effect is **+0.2390 R to +0.5437 R**, sign-stable across the whole plausible IV band,
25x to 57x the ±0.0095 R bar, and 4x to 9x the best exit policy ever found (X1's +0.0609 R).
Contract R p90 is +6.26 against a p50 of −0.32: convexity pays the runners and theta eats
the scratches — which is *exactly* Austin's "let runners run" instinct, and the engine has
never been able to see it because it books in stock points.

And it exposes a contradiction nobody has stated: **on the real instrument the two halves
of the money gate pull in opposite directions.** Win rate falls 53.4% → 38.5% while mean R
rises. You cannot have ≥55% win AND mean R ≥ 2.0 on a convex, decaying instrument; the
peers X12 quotes (50–60% win at 2R) are quoting the contract, not the stock.

**What is wrong with this number, stated up front.** The IV proxy uses `drange`, a
full-session range, so it is look-ahead; the strike is perfectly ATM where real strikes sit
on a $1–$5 grid against a $0.26 stop; the scale-out ladder is not modelled on the contract;
theta is continuous BS with constant sigma on a day when intraday vol is U-shaped; no
bid/ask. This is a **magnitude, not a measurement of the shipped book**.

**To settle it (≈1 day):** replace the IV proxy with prior-day/20-day realised vol (ex-ante),
snap the strike to `options_sizer.STRIKE_INCREMENT`, walk the real 1-minute path instead of
the booked exit, run the scale-out on the contract, and charge X9's spread. Report both
instruments side by side forever after.

**If it comes back yes:** every published R in this repo is restated, the error bar is
recomputed on the contract, and the money gate has to be rewritten because its two halves
are incompatible on the instrument Austin actually trades.

---

## 2 — THE SELECTION ORACLE. Nobody has priced selection's ceiling. (measured)

X1 priced the exit lever's ceiling (+3.4986 R hindsight-perfect) and closed the exit lane
with it. Nobody has done the same for selection. Here it is:

| one trade per calendar day (415 days) | mean R | win |
|---|---:|---:|
| **ORACLE — best trade of the day** | **+2.2125** | **76.6%** |
| biggest premarket range (ex-ante, §3) | +1.1502 | — |
| biggest \|gap\| | +1.0796 | — |
| sgrade S>A>C | +1.0550 | — |
| **first by time (what the engine does)** | **+1.0527** | 58.1% |
| random | +0.8809 (sd 0.0751) | — |
| last by time | +0.6563 | — |
| whole book, no selection | +0.9551 | 53.4% |

**The selection ceiling clears both halves of the money gate.** It is the only ceiling in
this entire investigation that does. And it needs far less than the exit oracle: a ranking
of at most 8 same-day candidates, not knowledge of the whole path.

Three structural facts nobody has published:

- **The competition is CROSS-SYMBOL, not within a symbol-day.** 1,008 traded symbol-days,
  of which **9** carry more than one signal. That is why X8 found 98.8% of the book is
  `seq == 1` and concluded arrival order is unmeasurable — `seq` is arrival *within a
  symbol-day*, and there is almost never a second one. The real contest is 2.45 symbols
  firing on the same calendar day, and no ticket in the repo is framed at that unit.
- **Arrival order is a genuinely positive selector**, +1.0527 vs +0.8809 random — 2.3
  random-draw sd. G14 is aimed at the floor that produces it; the floor is not obviously
  wrong, it is obviously *weak*.
- **The gate is only reachable at ~1 trade/day.** Oracle top-1 +2.2125, top-2 +1.5043,
  top-3 +1.1711. Adding trades destroys mean R even with perfect hindsight — which is the
  first evidence anywhere that the live governor's one-trade-a-day shape (X7, X9) is
  *right*, and that "more trades" and "mean R 2.0" are incompatible asks.

Honest limits: the oracle is +1.7343 in H1 and +2.6884 in H2, so it clears 2.0 only in the
second year; and on **97 of 415 days (23.4%) every trade of the day loses**, so a perfect
ranker still eats those.

**To extend (≈4 hours):** score every ex-ante day-ranker under one temporal split and
report the held-out ranking, then hand the best one to G14 as its treatment arm instead of
an on/off flag.

---

## 3 — PREMARKET, THE EX-ANTE VERSION OF X8's LOOK-AHEAD. (measured)

X8's strongest whole-book dimension was `rangeb = big range day` (+0.8417 R), and its own
critic showed `rangeb` is the **full-session** high−low, unknowable at a 09:42 entry.
Nobody looked for an ex-ante substitute. Premarket bars are in `data_archive` for
**1,017 of 1,017 rows** (files run 04:00–20:00), and no research script uses them as a
feature — `premarket` appears in `build_*.py` only to construct PMH/PML *levels*.

Mean R by quartile, all ex-ante at 09:29:

| feature | Q1 | Q2 | Q3 | Q4 |
|---|---:|---:|---:|---:|
| **premarket range %** | +0.663 | +0.954 | +0.637 | **+1.565** |
| premarket volume | +0.746 | +0.831 | +1.104 | +1.139 |
| \|premarket return\| | +0.712 | +0.854 | +1.097 | +1.158 |
| entry's position in the pm range | +0.809 | +0.840 | +0.977 | +1.193 |

A **+0.902 R** Q4−Q1 spread on premarket range, ~95x the error bar, with nothing from
after 09:30 in it. As a day-ranker it is the best ex-ante one tested (+1.1502 vs +1.0527
for arrival order).

**If it comes back yes:** X8's look-ahead result has a legitimate ex-ante replacement, and
the engine gains a day filter that needs no new data, no new detector and no engine change.

---

## 4 — A DAY-LEVEL MODEL OF AUSTIN'S EYE (the recall gate's only untried lever)

X6's central finding is that on his S days the engine gets the setup right 88.9% and the
entry bar right 78.6% *when it fires* — it is not failing to see his setups, it is failing
to pick his **days** (it trades 15.5% of them). Every recall attempt in the project's
history is signal-level: detector thresholds (X3), grade ladders (W1, R3), the risk floor
(W3, G13), the fill (X4). X6 also proved loosening is exhausted — maximum possible
loosening reaches 73.3% recall at 90.5% false fire and breaks the money gate one step in.

Nobody has asked whether **pre-09:30 information alone** separates his S days from his
refusals. The labels exist (817 judged symbol-days, 240 S), the premarket bars exist for
all of them, and there is a clean held-out set (15 S / 42 none).

**Measurement (≈1 day):** premarket feature set → binary S-vs-none day classifier, fit on
the in-sample corpus, scored on `research/marks/probe_omen_test1_2026-08-27.jsonl`.
**Held-out AUC and held-out S recall reported before any in-sample number.**

**If it comes back yes:** the recall gate has a lever that does not require firing more
signals, which is the only kind of lever left. If it comes back no, the recall gate is
provably unreachable from anything the engine can compute before the open, and that is
worth knowing before another detector ticket is written.

---

## 5 — THE CEILING OF THE EIGHT VARIABLES (the largest available scope kill)

W1 refuted the *count* ladder (26/59 = 44.1% against a 52.5% always-guess-X baseline).
X5 attributed the eight variables against **R** and swept the confluence weight. Nobody
has asked the question that subsumes all of it: **what is the best that ANY function of the
eight variables can do at predicting Austin's grade?**

The eight are binary. There are 256 cells. The fully saturated lookup table *is* the
ceiling — a continuous score, a weighted score, a re-tuned threshold, a different
confluence credit all live strictly beneath it.

**Measurement (≈half a day):** compute `research/downgrade.py`'s eight on every judged
symbol-day with bars, fit the 256-cell table, 5-fold CV, and a label-permutation null.

**If the CV ceiling is at or near the base rate**, then the eight variables do not contain
his eye, and every ladder ticket in the project dies in one measurement: S/A/C thresholds
(R2), the continuous-score proposal, the confluence weight, `ENABLE_SAC_LADDER`,
`ENABLE_DOWNGRADE_GRADER`. That is the single biggest scope reduction on the board, and it
is also the honest precondition for asking Austin to grade another card.

---

## 6 — WHAT A SELF-IMPROVING DAILY LOOP NEEDS TO BE TRUE

X14 flags this as the one Austin question no lane touched. Nobody has priced it.

The arithmetic, from numbers already in hand: the book runs **2.45 trades per traded day**
with **sd 2.3189 R** (`python research/x13_new_angles.py loop`):

| effect to detect | trades needed (95%/80%) | trading days | years |
|---|---:|---:|---:|
| +0.05 R | 33,726 | 13,762 | 54.6 |
| **+0.10 R** | **8,431** | **3,441** | **13.7** |
| +0.20 R | 2,108 | 860 | 3.4 |

**A daily loop cannot learn from money.** That has to be said out loud before anyone
builds one.

The signals that *do* update at a usable daily rate are: (a) agreement with a new mark,
(b) fired-or-silent on a day he graded, (c) execution health. So the loop Austin is asking
for is a **mark loop or a health loop, and never a P&L loop** — and X9's finding that the
live feed has been fully blind for 12 sessions with 1 paper position ever and the sentry
never firing is the loop's actual first job.

**Measurement (≈2 hours):** an information-per-day table — for each candidate daily signal,
the events/day it produces and the effect size detectable in one month. It turns an
impossible ask into a specified one.

---

## 7 — THE 2R TARGET IS A SELF-IMPOSED CAP, AND IT IS AN ENTRY QUESTION

Every row in the book plans **exactly** R:R 2.000 (mean 1.9998, median 2.0000, min 1.615,
max 2.167). The money gate then asks the *realised mean* to equal the *plan*, which at
today's win rate requires the average winner to go +2.6618 → **+4.6188 R, a 74% increase**.
The target is set at 2× risk regardless of where the next structural level sits — the
opposite of Austin's own rule (rulebook b4: size for the mean 2rr *"if there are no other
levels to target"*). MFE says the room is there: **43.9% of trades reach ≥3R, 34.4% ≥4R,
27.7% ≥5R** (X1's archive).

**Measurement (≈half a day):** re-target each trade at the next structural level (PMH/PML/
HOD/LOD/prior pivot — the level map already exists in the engine) instead of 2× risk, and
make trades with no reachable level *ineligible*. That is a filter, not an exit rule, which
is why it escapes X1's closed exit lane.

---

## 8 — SIZING, OUT OF SAMPLE, AND WHAT IT COSTS DURABILITY

X12's S3/A1/C0 risk weighting (+0.9551 → +1.1693 R/unit) is the largest single in-sample
lever any lane found, and it is the one thing Austin has **not** rejected — he rejected
scale-in, not risk weighting. But it is one in-sample point, and nobody has asked the
question sizing always raises: **it increases variance, so what does it do to the
durability gate?** X14 stacked it with X8's A1 (+1.1959, sub-additive) — also in-sample.

**Measurement (≈3 hours):** fit the weights on H1, score on H2, and report red-week and
red-month counts under each weighting beside the mean. Mean R and durability move in
opposite directions here and no lane has looked.

---

## 9 — THE DURABILITY GATE AGAINST ITS OWN NULL (measured)

Nobody has asked whether "every month green" is attainable by *any* process with this edge
and this variance. Shuffling the same 1,017 R's into buckets of the same sizes:

| | observed red | iid-shuffle mean | p50 | p95 |
|---|---:|---:|---:|---:|
| **weeks** (105) | 16 (worst −6.60R) | 11.6 | 12 | 16 |
| **months** (25) | 2 (worst −5.63R) | 0.2 | 0 | 1 |

Two readings, both actionable. **A weekly gate is unattainable by construction** — an
*idealised iid version of this exact book* still shows ~12 red weeks in 105, so X12's
proposal to move the durability gate to weekly should be declined, not escalated. And the
**monthly gate is nearly free under iid (0.2 expected) while 2 were observed**, i.e. the
two red months are above the p95 of chance: they are real clustering, not variance, and
they should be autopsied as a regime event rather than tolerated as noise.

---

## 10 — CONCURRENCY: the book is not 1,017 independent 1R bets

2.45 trades per day, up to 8, all inside a 90-minute window, mostly SPY-aligned. X2
measured max drawdown as a *sequence* (11.44 R over 17 trades). Nobody has measured
same-day outcome correlation, the day-level R distribution, or the effective number of
independent bets.

**Measurement (≈2 hours):** day-level R distribution, same-day pairwise outcome correlation
conditioned on side, and n_eff. **If the same-day correlation is high**, then "1R = $1,000"
is really up to $8,000 of correlated risk in 90 minutes, the durability gate is reading
fewer independent samples than it thinks, and the one-trade-a-day governor is correct for a
reason nobody in the repo has yet written down.

---

## 11 — ADD A NINTH VARIABLE INSTEAD OF DELETING ONE

X5 deleted four of eight, X3 deleted detectors, X7 deleted 787 lines. **Zero lanes tested
adding.** X6 §5 already publishes the candidates, measured, on the engine's false-S days:
`clean` 32.5% vs 55.5%, `late` 52.9% vs 32.2%, counter-aligned 47.8% vs 37.0%, 10:30 slot
35.7% vs 22.6%. Those are 20–23 point separations — larger than any of the eight existing
variables shows in X5, where `level_not_respected` trips on 62.7% of the book and points
**backwards**.

**Measurement (≈3 hours):** add `late` (or the 10:30-slot flag) as a ninth variable; score
against Austin's marks for agreement **and** against held-out recall, held-out first.

---

## 12 — SYMBOL SELECTION IS DEAD. Close it before anyone opens it. (measured)

Per-symbol means invite a roster ticket every few weeks (HOOD +1.8421 on n=75, GOOGL
+0.3646 on n=21; R4/SPY; retire-a-symbol; `MIN_SAMPLE_N`). It is noise:

- split-half Pearson **r = +0.000** across the 18 symbols with ≥20 trades;
- the top 6 chosen on H1 book **+0.8752** in H2 against **+1.0815** for all of H2;
- a walk-forward "trade the best trailing symbol" day-ranker books **+0.8719** — worse than
  random (+0.8809) and much worse than arrival order (+1.0527).

No roster decision should be argued from a per-symbol mean again.

---

## Ranked

| # | angle | cost | status |
|---|---|---|---|
| 1 | the options instrument | ~1 day | magnitude measured (+0.24…+0.54 R) |
| 2 | the day-level selection oracle | done + ~4h to extend | measured (+2.2125 R) |
| 3 | the 256-cell ceiling of the eight variables | ~half a day | specified |
| 4 | a day-level premarket model of his eye | ~1 day | specified |
| 5 | ex-ante premarket features | done | measured (+0.902 R spread) |
| 6 | pricing the self-improving loop | ~2h | arithmetic in hand |
| 7 | target = next structural level | ~half a day | specified |
| 8 | sizing out of sample + its durability cost | ~3h | specified |
| 9 | the durability gate vs its null | done | measured |
| 10 | concurrency / n_eff | ~2h | specified |
| 11 | add a ninth downgrade variable | ~3h | specified |
| 12 | symbol persistence | done | measured — closed |
