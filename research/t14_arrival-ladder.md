# T14 -- the arrival-order ladder (R18): keep both, and the switch still cannot be thrown

**Null result: no ladder that keeps arrival order AND the downgrade count beats the incumbent's held-out S recall.** The best of them, `s_promote`, ties it exactly -- **0 S days gained, 0 lost, on the same 34 cards** -- and its two-year mean R moves **+0.0075R against its own +/-0.0870R bar**. `gate` and `credit` land at or below the incumbent too. **That is the answer that keeps Austin's live alerts working: do not throw the routing switch.**

**And the premise of the track has itself moved.** The brief says arrival order picks **95.3%** of the traded book -- 968 of 1,016 rows. On the RATIFIED engine it picks **66.3%** (1,689 of 2,548 here; 66.6% recomputed on T0's own committed book). T0's ratified changes gave a third of the book a road to `B` that is not arrival order. The floor is still the single largest selector; it is no longer substantially all of it.

Incumbent held-out S recall on the 100 blind cards of 2026-08-28 (34 S): **18/34 = 52.9%** taking the trade, **18/34 = 52.9%** counting `C` alerts -- and that second number is the **52.9%** `DIRECTION.md` publishes, reproduced here at this commit.

- **`s_promote`**: 18/34 = 52.9% traded, 18/34 = 52.9% incl. `C` alerts. Paired on the same 34 cards it gains **0** and loses **0** (exact binomial p = 1.000); false fire on the 66 days he refused 32/66 = 48.5%.
- **`gate`**: 17/34 = 50.0% traded, 17/34 = 50.0% incl. `C` alerts. Paired on the same 34 cards it gains **0** and loses **1** (exact binomial p = 1.000); false fire on the 66 days he refused 27/66 = 40.9%.
- **`credit`**: 18/34 = 52.9% traded, 18/34 = 52.9% incl. `C` alerts. Paired on the same 34 cards it gains **0** and loses **0** (exact binomial p = 1.000); false fire on the 66 days he refused 30/66 = 45.5%.
- **`credit_all`**: 33/34 = 97.1% traded, 34/34 = 100.0% incl. `C` alerts. Paired on the same 34 cards it gains **15** and loses **0** (exact binomial p = 0.000); false fire on the 66 days he refused 61/66 = 92.4%.

Measured by `research/t14_arrival_ladder.py` at this commit. **Nothing ships**: `signal_runner.ARRIVAL_LADDER` defaults to `"off"` and the `off` arm below IS HEAD.

**The substrate, stated because it is not the number T0 published.** Every book here was replayed from THIS worktree's `data_archive/`, whose last session is **2026-08-10**; T0's committed book runs to 2026-08-21. So the `off` arm here is **74988 signals / 2548 traded / +0.5378R**, not T0's 75,953 / 2,595 / +0.5481R. The arms are compared to THIS `off` and never to that one -- all arms share one archive, one commit and one window.

| arm | what it is |
|---|---|
| `off` | HEAD. `_grade_pa` -> `_grade_for_levels` -> the first-with-trend `B` floor. |
| `s_promote` | R18's sentence: the incumbent chain UNCHANGED, plus any alert-only `C` whose downgrade count says S is floored to tradeable too. Arrival order can no longer cap an S because it is no longer the only road to `B`. |
| `gate` | Arrival order spent as ELIGIBILITY -- exactly the rows the `B` floor promotes -- and the downgrade count decides what they are. |
| `credit` | Arrival order spent as a -1 CREDIT inside the count, the same shape as the confluence +1. Every tradeable signal regraded. |
| `credit_all` | `credit`, also regrading the `_grade_pa` vetoes. The REACH control. |

## 0. Reachability, checked before any threshold was read

`CLAUDE.md` standing rule 3: a rung that trips under 1% or over 85% of the population it can act on is a finding about the rung. Four rules in this project have already turned out to be branches that could never fire.

| rung | population | n | fires | share |
|---|---|---:|---:|---:|
| the `B` floor (arrival order) | every signal | 74988 | 1689 | 2.25% |
| the `B` floor | signals it can reach (non-`X`) | 5502 | 1689 | **30.7%** |
| the `B` floor | the traded book | 2548 | 1689 | **66.3%** |
| `s_promote`'s new rung | the alert-only `C` rows it can act on | 2954 | 289 | **9.8%** |

Both rungs are squarely in range. The `B` floor is the dominant selector of the traded book -- **66.3% of it** -- which is the fact R18 is about.

And the rows `s_promote` reaches are not junk: the 289 alert-only `C` rows whose downgrade count says **S** simulate at **+0.6173R** in the `off` book itself, against the traded book's **+0.5378R**. That is the preview, not the result -- promoting them changes what fires afterwards, and section 2 is the real run.

## 1. HELD-OUT FIRST -- the 100 blind cards of 2026-08-28

`research/marks/probe_s_sweep_2026-08-28.jsonl`: 34 S days, 66 he refused, graded blind, never fitted on. Two readings of "fired", because `C` is alert-only in this engine (`backtest_week.Trade.counted`) and an alert still reaches Austin.

| arm | S recall (traded) | 95% CI | false fire | precision | gate | S recall (incl. `C`) | false fire |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`off`** | 18/34 = 52.9% | [36.7%, 68.5%] | 32/66 = 48.5% | 36.0% | +0.045 | 18/34 = 52.9% | 35/66 = 53.0% |
| `s_promote` | 18/34 = 52.9% | [36.7%, 68.5%] | 32/66 = 48.5% | 36.0% | +0.045 | 18/34 = 52.9% | 35/66 = 53.0% |
| `gate` | 17/34 = 50.0% | [34.1%, 65.9%] | 27/66 = 40.9% | 38.6% | +0.091 | 17/34 = 50.0% | 33/66 = 50.0% |
| `credit` | 18/34 = 52.9% | [36.7%, 68.5%] | 30/66 = 45.5% | 37.5% | +0.075 | 18/34 = 52.9% | 34/66 = 51.5% |
| `credit_all` | 33/34 = 97.1% | [85.1%, 99.5%] | 61/66 = 92.4% | 35.1% | +0.046 | 34/34 = 100.0% | 63/66 = 95.5% |

Gate = S recall - false-fire rate. `2` of the 100 cards have no archived bars and are counted as misses in every arm alike.

### The error bar that matters here: the SAME 34 cards, paired

A Wilson interval per arm treats two scorings of one sample as two samples. The information is in the discordant pairs. Two-sided exact binomial:

**taking the trade**

| arm vs `off` | S days gained | S days lost | net | p |
|---|---:|---:|---:|---:|
| `s_promote` | 0 | 0 | +0 | 1.000 |
| `gate` | 0 | 1 | -1 | 1.000 |
| `credit` | 0 | 0 | +0 | 1.000 |
| `credit_all` | 15 | 0 | +15 | 0.000 |

**counting `C` alerts**

| arm vs `off` | S days gained | S days lost | net | p |
|---|---:|---:|---:|---:|
| `s_promote` | 0 | 0 | +0 | 1.000 |
| `gate` | 0 | 1 | -1 | 1.000 |
| `credit` | 0 | 0 | +0 | 1.000 |
| `credit_all` | 16 | 0 | +16 | 0.000 |

The S days each arm gains that the incumbent misses:

- `s_promote`: _none_
- `gate`: _none_
- `credit`: _none_
- `credit_all`: `ARM_2024-10-28`, `CRM_2026-02-11`, `MSFT_2025-12-30`, `IWM_2026-05-01`, `QQQ_2025-09-16`, `ACHR_2026-02-05`, `HOOD_2024-11-06`, `MSTR_2025-08-26`, `PLTR_2025-07-01`, `QQQ_2025-09-23`, `PLTR_2025-12-11`, `AMZN_2025-09-10`, `BABA_2026-06-12`, `PLTR_2024-09-20`, `MSTR_2026-07-17`

### The 40 engine vetoes he graded himself

`research/marks/probe_master_2026-08-29.jsonl` lane `vetoes` -- 5 S / 4 A / 4 C / 27 no. Every one was a veto by construction, so recall on them starts at 0 and the 27 "no" rows are the false-fire cost of any lift.

| arm | fired on his 5 S | his 4 A | his 4 C | false fire on his 27 no |
|---|---:|---:|---:|---:|
| `off` | 0/5 | 0/4 | 0/4 | 2/27 = 7.4% |
| `s_promote` | 0/5 | 0/4 | 0/4 | 3/27 = 11.1% |
| `gate` | 0/5 | 0/4 | 0/4 | 2/27 = 7.4% |
| `credit` | 0/5 | 0/4 | 0/4 | 3/27 = 11.1% |
| `credit_all` | 5/5 | 4/4 | 4/4 | 25/27 = 92.6% |

## 2. The two-year book, with its own error bar

`backtest_2y.py`, one run per arm against the same `data_archive/`. The bar is a 10,000-sample percentile bootstrap 95% CI of mean R. **Read the bar before the point estimate**: every A/B this project has run moves less than its own bar.

| arm | traded | mean R | 95% CI | +/- bar | delta vs `off` | inside bar? | win | median R | total R | PF | months green |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| `off` | 2548 | +0.5378 | [+0.4472, +0.6292] | 0.0910 | +0.0000 | -- | 43.0% | -1.0000 | +1370.2 | 1.9496 | 25/25 |
| `s_promote` | 2865 | +0.5453 | [+0.4581, +0.6321] | 0.0870 | +0.0075 | yes -- **null** | 42.6% | -1.0000 | +1562.2 | 1.9553 | 25/25 |
| `gate` | 1364 | +0.4829 | [+0.3541, +0.6186] | 0.1322 | -0.0549 | yes -- **null** | 40.0% | -1.0000 | +658.7 | 1.8130 | 23/25 |
| `credit` | 2413 | +0.6013 | [+0.5029, +0.7052] | 0.1011 | +0.0635 | yes -- **null** | 43.0% | -1.0000 | +1450.9 | 2.0628 | 24/25 |
| `credit_all` | _NOT RUN_ | | | | | | | | | | |

Traded grade mix per arm:

| arm | A+ | A | B | C |
|---|---:|---:|---:|---:|
| `off` | 7 | 143 | 2398 | 0 |
| `s_promote` | 7 | 145 | 2713 | 0 |
| `gate` | 208 | 558 | 598 | 0 |
| `credit` | 1074 | 1339 | 0 | 0 |

Traded rows by HIS ladder (`sgrade`, the downgrade count attached to every row):

| arm | S | A | C |
|---|---:|---:|---:|
| `off` | 340 | 564 | 1644 |
| `s_promote` | 635 | 569 | 1661 |
| `gate` | 346 | 615 | 403 |
| `credit` | 630 | 1146 | 637 |

## 3. What this means for the routing switch

**The switch stays where it is.** `DIRECTION.md`'s condition -- routing stays legacy until a ladder beats the incumbent's held-out recall -- is met by no arm that keeps both signals. The two arms that REPLACE the incumbent grade with the count (`gate`, `credit`) reproduce W1's finding and the pre-ratification T11 finding for a third time: `gate` loses an S day and 46% of the book, `credit` holds recall and loses 5% of the book, and neither gains a single S day the incumbent misses.

**`credit_all` is not a fourth candidate, it is the reachability finding.** It reaches 33/34 = 97.1% by firing on **61/66 = 92.4%** of the days Austin REFUSED, and on **25 of his 27 explicit no verdicts**. `CLAUDE.md` standing rule 3 in the flesh: a rung that trips on more than nine days in ten is a finding about the rung. Its recall-minus-false-fire score (**+0.046**) is indistinguishable from the incumbent's (**+0.045**).

### But R18's sentence is about OPPORTUNITIES, and recall cannot see them

Austin: *"don't let it cap you of S opportunities"*. Held-out recall is a DAY-level metric -- a day counts once however many entries the engine takes on it -- so an arm that finds a SECOND S setup on a day it already trades scores exactly zero. That is what `s_promote` does, and it is why its recall is unchanged while its book is not.

| arm | entries on his 34 S days | entries on his 66 refused days | traded book | traded rows his count calls S |
|---|---:|---:|---:|---:|
| `off` | 31 | 54 | 2548 | 340 |
| `s_promote` | 33 | 56 | 2865 | 635 |
| `gate` | 29 | 44 | 1364 | 346 |
| `credit` | 31 | 50 | 2413 | 630 |
| `credit_all` | 143 | 232 | _not run_ | _not run_ |

**The cap is real, and lifting it is nearly free.** In the `off` book **289** alert-only `C` rows carry a downgrade count of **S** -- setups Austin's own ladder calls clean that never reach him as a trade, because they were not the first with-trend signal of the day. `s_promote` opens a second road to `B` for exactly those: the traded book goes **2548 -> 2865** (+317), the traded rows his ladder calls S go **340 -> 635** (+295, nearly double), total R goes **+1370.2 -> +1562.2**, every month stays green, and mean R moves **+0.0075R inside a +/-0.0870R bar**. On the held-out cards it takes 2 more entries on his S days and 2 more on days he refused -- four rows, which is nothing in either direction.

So the honest two-part answer:

1. **As a REPLACEMENT for the grader -- no.** Nothing here beats 18/34 = 52.9%, and the routing switch stays legacy. The same conclusion W1 and T11 reached, now reproduced on the ratified engine.
2. **As an ADDITION -- the constraint R18 names is currently VIOLATED, and `s_promote` is the one-flag fix.** Today arrival order does cap S opportunities: 289 of them over two years. Removing the cap costs nothing measurable and is his own ratified sentence. It is not a recall win and this report does not dress it as one. Whether "nothing measurable moved" is a reason to ship a rule he asked for or a reason not to bother is his call, not this track's.

## 4. Caveats, stated where the numbers are

- **The window is this worktree's archive** (ends 2026-08-10, 500 sessions back), not T0's (ends 2026-08-21). Arms are comparable to each other and to the `off` arm in this file; they are NOT comparable to T0's published 2,595 / +0.5481R.
- **`s_promote` is not a strict superset of `off`.** Promoting an alert-only `C` to `B` bypasses `_min_viable_stop` (the tight-stop skip applies only to `C`), so a row that was skipped can now be accepted, increment `_dir_fired`, and take `arrival_first` away from a later signal. The paired table in section 1 is the measurement of whether that costs an S day; nothing here assumes it does not.
- **Every money number in section 2 is a NULL.** `s_promote` +0.0075R (bar 0.0870), `credit` +0.0635R (bar 0.1011), `gate` -0.0549R (bar 0.1322). Not one arm's mean-R move clears its own bootstrap bar. Read the trade COUNTS and the month greenness, which are counts and not estimates; do not read the mean-R ranking.
- **`credit_all` has no book.** A book is a full two-year replay and this box was shared with several other tracks' backtests. `credit_all` is reported on held-out recall and reachability only and no money number is claimed for it. Regenerate it with `ARRIVAL_LADDER=credit_all python backtest_2y.py --out research/_t14_book_credit_all.json` and re-run this script.
- **No options, contracts, spreads or futures.** Every number is the underlying in R.
- **The 52.5% figure in the brief is a different measurement** -- it is W1's majority-class "always say X" baseline on 59 hand-graded `B` rows (`research/w1_sac_ladder_ab.md` s2), not a recall. The recall incumbent this track is scored against is `off`'s **18/34 = 52.9%** on the 100 blind cards, which is the **52.9%** DIRECTION.md publishes.
- **Nothing ships.** `ARRIVAL_LADDER` defaults to `"off"`; `research/test_t14_arrival_ladder.py` asserts that, asserts the S-safety invariant (no arm may lower a grade via arrival order), and asserts every rung is reachable.

