# T3 — the selection ranker

**Answer in one line:** the ranker **fails its check** — no feature computable at 09:29 beats
arrival order in both halves of a temporal split, and every paired comparison in the lane sits
inside its own ±0.24R–±0.44R bar — but the same features used as a **bottom-quartile filter**
instead of a one-a-day governor book **+1.1120R on 779 of 1,017 trades**, clear a Welch bar in
**both** halves, survive a label-permutation null at P≈0.05%, and cost **zero held-out S
recall**.

Script: `research/t3_selection_ranker.py` (`--selfcheck` 5/5 green; run it for the full dump).
Substrate: the standing 2-year book — 1,017 traded rows, +0.9551 mean, content sha
`afe1d3655081c329`. Repo HEAD at measurement: `3810ea87`. Marks:
`research/marks/probe_omen_test1_2026-08-27.jsonl`.

---

## 0. HELD-OUT S RECALL — before any in-sample number

The standing held-out recall is **3/15 = 20.0%** (`research/t70_test1_score.md`). A one-trade-a-day
governor is **subtraction**: it can keep or drop an S day the engine already fires on, never add
one. Ceiling 3/15, floor 0/15. So this column is a **cost**, and the incumbent selector pays it too.

| arm | held-out S recall | top-2 |
|---|---:|---:|
| engine today, whole book, no governor | **3/15 = 20.0%** | — |
| + ranker[level] top-1 per day | 1/15 = 6.7% | 2/15 |
| + ranker[within] top-1 per day | **0/15 = 0.0%** | 2/15 |
| + ranker[x13] top-1 per day | 1/15 = 6.7% | 2/15 |
| + **first-by-time top-1 (the incumbent)** | 1/15 = 6.7% | **3/15 = 20.0%** |
| + random top-1 (expectation) | 1.14/15 = 7.6% | — |
| + **ranker[x13] score ≥ p25 (the FILTER)** | **3/15 = 20.0%** | — |
| + ranker[x13] score ≥ p50 | 3/15 = 20.0% | — |
| + ranker[level] / ranker[within] ≥ p25 | 2/15 = 13.3% | — |
| + any arm at p75 | 1/15 or 0/15 | — |

The three S days the engine finds, ranked against that calendar day's whole candidate field.
Weights always come from the **other** half, so no S day is scored by a model fitted on its own year:

| sym | day | engine fires | field | rank: level | within | x13 | by time |
|---|---|---|---:|---|---|---|---|
| BABA | 2026-02-04 | 09:57 | 7 | 5/7 | 6/7 | 4/7 | 2/7 |
| IWM | 2025-04-14 | 09:41 | 2 | 2/2 | 2/2 | 2/2 | **1/2** |
| MU | 2026-03-09 | 09:49 | 2 | **1/2** | 2/2 | **1/2** | 2/2 |

Two things to read off it. **The incumbent already drops two of the three** — first-by-time takes
ORCL 09:44 over MU 09:49 and UBER 09:46 over BABA 09:57. And **the only shape with no recall cost
at all is the filter**: dropping the bottom quartile by premarket score keeps all three.

Nothing here moves the recall gate. **12 of his 15 S days produce no fired entry of any grade**, so
12/15 of the gap is upstream of selection and no ranker can reach it. The gate stays FAIL at a
20.0% ceiling. n=3 is far too small to rank the three model forms by this column and it is not used
to.

---

## 1. What was measured, and one substrate hazard that has to be said first

`research/g3_arm_ow1.json` is `.gitignore`d (`.gitignore:118`) and is a **shared, rewritable**
artifact. It was rewritten **twice** during this track's run:

| time | mean R | traded | what it was |
|---|---:|---:|---|
| 2026-08-27T17:27 | **+0.9551** | 1,017 | the standing book |
| 2026-08-28T14:03:05 | +0.9551 | 1,017 | re-run of `g3_onwatch_2y.py`, rows **identical** (content sha `afe1d365…`) |
| 2026-08-28T14:13:17 | **+0.8341** | 1,017 | rewritten by **T11** (fill convention), rows different |

Nothing warned. `load_book()` therefore hashes the 1,017 **traded rows** and refuses to run against
anything but the standing set; it found them in `research/a2_bt2y_rerun.json`, which is a
byte-for-content copy written 2026-08-27. Every number in this file is on the standing book, which
is the book T3's check is stated against (first-by-time +1.0527, random +0.8809).

**This is a wave-level hazard, not a T3 detail.** Any wave-1 track that read `g3_arm_ow1.json`
after 14:13 measured a different book and its numbers are not comparable with anyone else's. The
14:03 re-run is separately good news: `g3_onwatch_2y.py` reproduces its own book exactly.

Read-only track. No engine module, default or flag is touched; there is no `ENABLE_*` to ship OFF
because nothing here is wired. `test_book_untouched` is the "byte-identical" proof, and it has
already fired once for real.

---

## 2. The no-lookahead rule, and a leak in the prototype

X8's strongest whole-book dimension was `rangeb`, the **full-session** high−low, unknowable at a
09:42 entry. X13's premarket prototype repeated a softer version of that mistake, and it is worth
naming because the prototype's table is what this track was built on:

- `pmr_pct = (pm_hi − pm_lo) / **entry** × 100` — the denominator is a post-09:30 price.
- `pm_pos` places **`entry`** inside the premarket range — the whole feature is post-09:30.

So **two of the four "ex-ante" prototype features are not 09:29-knowable**. Both are rebuilt here
off the premarket close. The leak turns out to be nearly harmless in size — Spearman(leaky,
ex-ante) = **+0.9996** over 1,017 rows, and as a day-ranker the leaky version books **+1.1502**
against the ex-ante **+1.1373** — but "nearly harmless" is a measurement, not an assumption, and
it is now measured. `gap` in the book is also post-09:29 (it uses the 09:30 open); the ex-ante
substitute is the premarket close against the prior session close.

Three tests hold the line, all green:

- `test_no_post_0930_feature` — no feature name is a book field at all, and every feature is `pm_*`.
- `test_builder_ignores_rth` — the features are rebuilt from a copy of NVDA 2025-06-02's CSV with
  **every 09:30-and-later bar physically deleted**, and come out identical.
- `test_trailing_window_is_strictly_prior` — a synthetic volume spike shows in its own day's `rvol`
  and **not** in the day before it.
- (plus `test_ranker_is_pure_ranking` — the picks do not move when every realised R is shuffled.)

---

## 3. The features — six, all computable at 09:29:00 ET

Complete vectors on **1,009 of 1,017** traded rows (99.2%); the 8 misses are symbols inside their
first five archived sessions, where the trailing median does not exist yet.

| feature | definition | Q1 | Q2 | Q3 | Q4 |
|---|---|---:|---:|---:|---:|
| `pm_range_pct` | (pm high − pm low) / pm close × 100 | +0.666 | +0.905 | +0.716 | **+1.531** |
| `pm_ret_abs` | \|pm close − pm open\| / pm open × 100 | +0.712 | +0.854 | +1.097 | +1.158 |
| `pm_gap_abs` | \|pm close − prior close\| / prior close × 100 | +0.614 | +0.748 | +1.197 | +1.262 |
| `pm_rvol` | pm volume ÷ median pm volume, **prior 20 sessions** | +0.555 | +1.058 | +1.117 | +1.092 |
| `pm_rrange` | `pm_range_pct` ÷ its own prior-20 median | +0.704 | +0.959 | +0.999 | +1.156 |
| `pm_edge` | how close the pm close sits to a pm range extreme | +0.825 | +1.072 | +1.020 | +0.905 |

The X13 quartile spreads reproduce on the de-leaked features. **This is real information** — the
Q4−Q1 spread on `pm_range_pct` is +0.865R — but a quartile table is a whole-book, in-sample,
non-competitive read. Everything below is the competitive, out-of-sample version, and it is a much
harder test.

Three ranker forms, **all declared before any was scored**, all fitted on the fit half's percentile
transform:

- **level** — OLS of R on the six percentiles. Predicts the level of R.
- **within** — OLS on **within-calendar-day demeaned** percentiles and R. The estimator that
  matches the task: it throws away everything separating days and fits only what separates
  candidates competing on the same day.
- **x13** — **no fit at all**: the equal-weight mean of the percentiles of X13's own four features.
  Zero parameters, nothing to overfit.

---

## 4. The check — FAILED

Split by calendar day: **H1 2024-08-21…2025-09-09** (207 days / 441 trades), **H2 2025-09-10…2026-08-21**
(208 days / 576 trades). **295 of 415 days carry more than one candidate** — the only days a ranker
can act on at all. Each half is scored by the model fitted on the **other** half, so both columns
are out of sample.

| arm | H1 | vs first | H2 | vs first | verdict |
|---|---:|---:|---:|---:|---|
| ranker[level] | +0.8302 | −0.1188 | +1.1834 | +0.0275 | H2 only |
| ranker[within] | +0.7422 | −0.2068 | **+1.4221** | +0.2661 | H2 only |
| ranker[x13] | +0.8043 | −0.1447 | +1.3050 | +0.1490 | H2 only |
| `pm_range_pct` alone | +0.9350 | −0.0140 | +1.3385 | +0.1826 | H2 only |
| `pm_ret_abs` alone | +0.8366 | −0.1124 | +1.2489 | +0.0929 | H2 only |
| `pm_gap_abs` alone | +0.8230 | −0.1260 | +1.2643 | +0.1083 | H2 only |
| `pm_rvol` alone | +0.6705 | −0.2785 | +1.2264 | +0.0704 | H2 only |
| `pm_rrange` alone | +0.6524 | −0.2966 | +1.1337 | −0.0223 | no |
| `pm_edge` alone | +0.7614 | −0.1876 | +1.0511 | −0.1049 | no |
| sgrade S>A>C | +0.9818 | +0.0328 | +1.1278 | −0.0281 | H1 only |
| **first by time (incumbent)** | **+0.9490** | — | **+1.1560** | — | the incumbent |
| ORACLE (hindsight) | +1.7343 | +0.7853 | +2.6884 | +1.5325 | the ceiling |

**Nine ex-ante arms and one grade arm. Not one beats arrival order in both halves.** Every
premarket arm loses in H1 and wins in H2 — a clean sign flip, not a shrinking edge. `pm_range_pct`,
the best of them and X13's headline, misses H1 by 0.014R.

And the paired A/B — same days, same field, the only comparison that is not two independent noisy
means — says the lane is **undecidable at this n**:

| paired ranker − first-by-time | H1 (207 days) | H2 (208 days) |
|---|---|---|
| level | −0.1188 ±0.2434 | +0.0275 ±0.3422 |
| within | −0.2068 ±0.2416 | **+0.2661 ±0.3242** |
| x13 | −0.1447 ±0.2504 | +0.1490 ±0.3586 |

**Six comparisons, six confidence intervals containing zero.** The ±0.0095R house bar does not
apply here — it is for an A/B whose two arms share nearly every trade. A one-a-day governor's arms
share almost nothing, so the bar is 25×–45× wider, and the whole day-selection lane is inside it.
X13's oracle (+0.79R in H1, +1.53R in H2 over the incumbent) is the only figure in this lane that
is outside its own bar.

---

## 5. The low-variance read: does the ranker find the day's best trade?

Mean R over 207 days cannot separate these arms. "Did the pick equal the day's best trade" is a
Bernoulli on the same days with a ~7–8pp bar, and it can.

| arm | H1 hit rate | H2 hit rate |
|---|---|---|
| **RANDOM (expectation)** | **40.2%** | **34.8%** |
| `pm_range_pct` | 55.3% ±8.5 | 50.9% ±7.7 |
| `pm_ret_abs` | 54.5% ±8.5 | 46.0% ±7.7 |
| `pm_gap_abs` | 52.3% ±8.5 | 45.4% ±7.6 |
| ranker[x13] | 50.8% ±8.5 | 47.9% ±7.7 |
| ranker[level] | 50.0% ±8.5 | 46.0% ±7.7 |
| ranker[within] | 46.2% ±8.5 | 52.1% ±7.7 |
| `pm_rvol` | 47.0% ±8.5 | 48.5% ±7.7 |
| `pm_edge` | 47.7% ±8.5 | 40.5% ±7.5 |
| **first by time** | **56.1% ±8.5** | 46.0% ±7.7 |
| sgrade S>A>C | 58.3% ±8.4 | 42.3% ±7.6 |

Two findings, and they point in opposite directions.

1. **Premarket information really does rank same-day candidates.** Every single ex-ante feature
   beats random in both halves, `pm_range_pct` by +15.1pp and +16.1pp. The features are not noise.
2. **They still do not beat arrival order.** No ranker is more than one bar from first-by-time in
   either half, and first-by-time itself beats random by **+15.9pp / +11.2pp** — in both halves,
   at zero cost, with no model. X13 §2's "arrival order is a genuinely positive selector" is
   confirmed on the statistic that can actually see it.

That is the diagnosis of the whole track. The oracle's +2.2125R needs the day's best trade picked
~100% of the time. The best available ex-ante ranker picks it ~50–53%, the incumbent ~51%,
and chance picks it ~37%. **Most of the oracle's headroom lives in the half of the ranking these
features cannot see**, and that half is the trade's own path.

---

## 6. The one thing that survives: the filter, not the governor

A top-k governor competes with first-by-time and loses. A **score filter** does not compete with
it at all — it competes with the whole book, keeps most of the trades, and is the only shape here
that points the way Austin asked ("more trades, not fewer"). Judged x8's way: a **disjoint** slice
against its complement, on a Welch 95% CI.

| filter | H1 slice | H1 Δ vs complement | H2 slice | H2 Δ vs complement | |
|---|---|---|---|---|---|
| ranker[level] ≥ p25 | n=293 +0.9144 | +0.3441 ±0.3762 | n=426 +1.1742 | +0.3818 ±0.4134 | both + |
| ranker[level] ≥ p50 | n=199 +0.7676 | −0.0570 ±0.3952 | n=304 +1.2163 | +0.2997 ±0.4024 | |
| ranker[level] ≥ p75 | n=104 +0.9168 | +0.1543 ±0.5302 | n=174 +1.3497 | +0.3939 ±0.4781 | both + |
| ranker[within] ≥ p25 | n=329 +0.8819 | +0.3268 ±0.4006 | n=422 +1.2300 | +0.5807 ±0.4023 | both + |
| ranker[within] ≥ p50 | n=189 +0.8273 | +0.0498 ±0.4011 | n=301 +1.3340 | +0.5430 ±0.4007 | both + |
| ranker[within] ≥ p75 | n=113 +0.8607 | +0.0831 ±0.4863 | n=168 +1.2632 | +0.2660 ±0.4849 | both + |
| **ranker[x13] ≥ p25** | **n=314 +0.9186** | **+0.4158 ±0.3841** | **n=465 +1.2425** | **+0.8705 ±0.4245** | **CLEARS BOTH BARS** |
| ranker[x13] ≥ p50 | n=205 +0.8115 | +0.0236 ±0.3919 | n=305 +1.3594 | +0.6050 ±0.3972 | both + |
| ranker[x13] ≥ p75 | n=105 +0.9006 | +0.1335 ±0.4901 | n=152 +1.7177 | +0.8734 ±0.5321 | both + |

**One of nine clears its own bar in both halves**: drop the bottom quartile of candidates by the
zero-parameter X13 composite. Nine arms were tried, so that has to be priced — a label-permutation
null (R shuffled **within** each half, same rows kept, 2,000 draws) puts P(both halves clear) at
**0.05%** for this arm and 0.00–0.15% across all nine, so the family-wise chance of seeing one is
≲1%.

Pooled, out of sample, in x8's currency:

| arm | n | mean R | ΔN | ΔR | trades per +0.01R | win | mgreen | H1 | H2 | held-out S |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **A0 incumbent whole book** | **1017** | **+0.9551** | 0 | — | — | 53.2% | 23/25 | +0.7989 | +1.0748 | **3/15** |
| **ranker[x13] ≥ p25 (FILTER)** | **779** | **+1.1120** | **−238** | **+0.1568** | **15.2** | 54.8% | **23/25** | +0.9186 | +1.2425 | **3/15** |
| ranker[x13] ≥ p50 | 510 | +1.1392 | −507 | +0.1840 | 27.5 | 52.7% | 21/25 | +0.8115 | +1.3594 | 3/15 |
| ranker[x13] ≥ p75 | 257 | +1.3839 | −760 | +0.4287 | 17.7 | 56.0% | 22/25 | +0.9006 | +1.7177 | 1/15 |
| ranker[within] ≥ p50 | 490 | +1.1386 | −527 | +0.1834 | 28.7 | 53.3% | 22/25 | +0.8273 | +1.3340 | 2/15 |
| ranker[within] top-1/day | 415 | +1.0829 | −602 | +0.1278 | 47.1 | 53.5% | 23/25 | +0.7422 | +1.4221 | 0/15 |
| first-by-time top-1/day | 415 | +1.0527 | −602 | +0.0976 | 61.7 | 58.1% | 23/25 | +0.9490 | +1.1560 | 1/15 |
| first-by-time top-2/day | 710 | +1.0077 | −307 | +0.0525 | 58.5 | 55.9% | 22/25 | +0.7787 | +1.2169 | **3/15** |
| ranker[x13] top-1/day | 415 | +1.0553 | −602 | +0.1001 | 60.1 | 53.3% | 23/25 | +0.8043 | +1.3050 | 1/15 |

**`ranker[x13] ≥ p25` is the cheapest lever on this board at 15.2 trades per +0.01R** — against
x8's cheapest at 11.8 — and unlike every arm in x8 §4 it holds durability at 23/25 and costs
**nothing** in held-out S recall. Its weakness is stated plainly: the H1 margin is **1.08× its own
bar** and H2 is 2.05×; the effect is real in the second year and marginal in the first.

**It still does not reach the money gate.** The best filter arm on this board is +1.3839R, 0.62R
short of 2.0, and the aggressive one is +0.9006 in H1. X8's verdict — *you cannot filter your way
to mean R = 2.0* — now holds on a completely different, ex-ante, premarket feature family. The
oracle itself clears 2.0 only in H2 (+2.6884) and not in H1 (+1.7343).

---

## 7. The deployable form — and why top-1-of-the-day is not one

Top-1-of-the-day is **not live-implementable**: at 09:35 you do not know what will fire at 10:20,
and the ranking needs the whole day's field. First-by-time needs no ranking at all — it is an online
greedy rule — which is a second, practical reason it is hard to beat.

What *is* implementable at 09:29 is a **shortlist**: rank every symbol before the open, watch the
top k, trade whatever fires there. Every mean below is out of sample.

| arm | k | days with a trade | trades | mean R | win | mgreen | H1 | H2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| shortlist[x13] | 1 | 65 / 415 | 66 | +1.4252 | 59.1% | **14/20** | +1.1780 | +1.5488 |
| shortlist[x13] | 2 | 109 | 116 | +1.3317 | 56.0% | 20/25 | +0.8657 | +1.6847 |
| shortlist[x13] | 3 | 161 | 179 | +1.2439 | 53.1% | 21/25 | +0.9530 | +1.4685 |
| shortlist[x13] | 5 | 242 | 298 | +1.2934 | 55.0% | 23/25 | +0.9255 | +1.5781 |
| shortlist[x13] | 8 | 301 | 445 | +1.2066 | 54.8% | 22/25 | +0.9578 | +1.4231 |
| shortlist[level] | 8 | 304 | 472 | +1.0582 | 51.9% | 23/25 | +0.9244 | +1.1759 |
| shortlist[within] | 8 | 297 | 469 | +1.1071 | 53.9% | 22/25 | +1.0210 | +1.1819 |

The shortlist is **positive in both halves at every k for the x13 composite**, which is the same
signal the filter shows. But it is a far more expensive way to buy it: k=1 books +1.4252R on **66
trades over two years**, trades on 65 of 415 days, and its durability collapses to 14 of 20 months
green. The filter buys most of the same mean while keeping 779 trades. **If any of this ships, it
should ship as the filter, not as the shortlist and not as a governor.**

---

## 8. What this closes, and what it opens

**Closed.** The ex-ante day-ranker as a *governor* is refuted on this book: nine arms, three model
forms, zero survive both halves, and every paired difference is inside its own bar. Do not write
another ticket that ranks the day's candidates on premarket features to pick one trade. The gap
between the oracle's +2.2125R and everything reachable ex-ante is **not** a modelling gap that a
better ranker closes — the hit-rate table shows the features get ~50% of days right against
chance's ~37% and the oracle's 100%.

**Confirmed, and free.** Arrival order is a genuinely positive selector — +15.9pp / +11.2pp over
random on oracle-hit in both halves — and it is what the engine already does. G14 is aimed at a
floor that is weak, not wrong.

**Open, and it needs Austin** (it changes what trades): `ranker[x13] ≥ p25` — refuse the bottom
quartile of candidates by an equal-weight premarket composite. 779 trades instead of 1,017,
+0.1568R, 23/25 months green, **held-out S recall unchanged at 3/15**, clears its bar in both
halves at a permutation null of 0.05%. It is a filter, so it subtracts, and Austin has said he
wants more trades — but it is the cheapest subtraction anyone has measured and the only one that
costs no recall.

**Open, unmeasured here.** The oracle's headroom is mostly in the path, which is X1's closed exit
lane by a different door: a selector that could see 1R of MFE ahead would clear the gate, and
nothing at 09:29 can. Whether the *contract* (T2) changes the ranking — convexity pays the runners
and the ranking is over which runner to hold — is not measured by this track and should not be
assumed to follow from it.

---

## 9. Method

- **Split**: by calendar day, `days[:207]` / `days[207:]`, matching `x13_new_angles.py`'s
  convention. Cross-fitted: H1 is scored by the H2 model and H2 by the H1 model, so **both**
  reported halves are out of sample. Score thresholds are also taken from the fit half's score
  distribution, never from the half being scored.
- **Transform**: each feature is mapped through the **fit half's** empirical CDF, so the model is
  monotone-invariant and outlier-proof, then OLS. No hyperparameter, nothing to tune.
- **Bars**: paired day-level differences use 1.96·sd/√n on the per-day difference. Disjoint slices
  use a Welch 95% CI against their complement (x8's rule). The ±0.0095R house bar is **not** used
  anywhere here and the reason is stated in §4.
- **Ties** break to the earliest entry, matching x13.
- **Win rate** excludes scratches from the denominator, matching the standing 53.2%.
- Every number in this file is printed by `python research/t3_selection_ranker.py`.
