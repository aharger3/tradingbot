# The free 278, run — every graded day you own, through the real engine

You picked this over grading more cards, and it cost 3½ minutes of compute per arm.
Five arms ran at once, so the whole thing took under four minutes wall-clock.

Script: `research/g83_recall278.py` → `research/g83_recall278.json`.
Grades: `research/marks_pool.py` (the canonical one-grade-per-symbol-day view, nine
spellings of "S", all 24 corpora, read-only).
Engine: the shipped router. The script refuses to print a number if
`t4_engine_recall.CaptureRunner._route` is not delegating to `signal_runner.SignalRunner._route`
— that was the hand-written photocopy fixed in `145d564e`, and it flattered recall by exactly
one day in every direction it ever moved.

**Money: this pass moves no dollars.** Nothing here is wired into anything. Distance to your
$397-a-day bar is unchanged by it. What it does is make the accuracy number steerable — before
today it was ±15.7 points, which is wide enough that a real 10-point improvement had a 2-in-3
chance of looking like nothing.

---

## 1. The headline: the engine is not blind. It is undiscriminating.

**It produces a signal on 97.4% of the days you graded S — and on 97.6% of the days you
looked at and refused.** Those two are the same number. Detection is not the problem and
has not been the problem for a while.

| | days | engine takes a trade | 95% band |
|---|---:|---:|---|
| Days you graded **S** | 303 | **59.1%** (179) | 53.5 – 64.5 |
| Days you **refused** | 542 | **50.6%** (274) | 46.4 – 54.7 |
| Days you graded A | 228 | 49.1% (112) | 42.7 – 55.6 |
| Days you graded C | 58 | 65.5% (38) | 52.7 – 76.4 |

**Separation — how much more often it trades your S days than your refusals — is
+8.5 points, 95% band 1.5 to 15.4.** It clears zero, and only just. Precision is 39.5%:
of every 100 days it trades out of this pile, 40 are days you called S and 60 are days
you refused.

Against the 90% gate: **30.9 points short**, and the odds of seeing 179 of 303 if the true
rate were 90% are about 1 in 10⁴⁴.

It fires on your **C** days more often than your **A** days. Whatever it is sorting on, it
is not your grade.

*Legacy ladder, side by side and never mixed in: of the entries it takes on your S days,
205 are graded B, 83 C, 3 A, and **zero A+**. The live scanner promotes to TRADE only on A+.
The live path would trade none of this.*

---

## 2. What the bigger sample bought

| | 34 cards (every earlier number) | 303 S days (today) |
|---|---:|---:|
| How tight the answer is | **±15.7 points** | **±5.5 points** |
| Chance of spotting a real 10-point improvement, paired | 0.33 | **0.996** |

**Cross-check that the pipeline is honest:** scored on the same 100 blind cards, this run
returns **22 of 34** — byte-for-byte the number `research/g72_recall278_t0_rerun.json`
published on 29 August after the router fix, not the 23 of 34 the photocopy used to report.
The pipeline reproduces the standing figure before it is trusted with a new one.

One number moved and it is worth saying out loud: the pool is **303** bar-backed S days, not
278. The 278 came from `research/g71_samplesize_corpus.json`; the canonical reader adds the
ninth spelling of "S" and last night's 30 cards. Same conclusion, 25 more days of it.

---

## 3. By setup — this is where it goes wrong, and it is not close

Your own labels off the mark rows (492 days carry one), against the three families you name.

| the setup **you** named | your S days | engine trades the day | engine trades **that same setup** |
|---|---:|---:|---:|
| Break-and-retest | 111 | 65.8% | **64.0%** |
| One-candle rule | 61 | 41.0% | **9.8%** |
| The 84% re-entry | 15 | 73.3% | **0.0%** |

**On the fifteen S days you called an 84% re-entry, the engine fires on eleven of them and
not once as an 84% re-entry.** On your one-candle-rule days it names the same setup 6 times
in 61. It is reaching your days by firing break-and-retest at a different idea, and then a
per-setup win rate gets computed off that.

The engine's own attribution agrees: of the 303 S days, it fires break-and-retest on 171
(56.4%) and the one-candle rule on 17 (5.6%). The 9.3-to-1 detection imbalance
`DIRECTION.md` lists as an open bug is worse than 9-to-1 at the point of firing.

**Caveat, and it is a real one.** Inside the setup-labelled slice the separation goes
*negative* — on your labelled break-and-retest days the engine trades 65.8% of your S days
and **80.7%** of your refusals. Do not read that as a finding on its own, because the
labelled and unlabelled refusal days are visibly different populations: the engine trades
**80.7%** of labelled refusals and only **44.6%** of unlabelled ones. A card only carries a
setup label if it came off a deck or a probe, and decks are built around setups — so the
labelled refusals are enriched in days that had a live setup on them, which is exactly the
thing the engine trades. The **pooled** +8.5 points is the clean number. The per-setup
**recall** column above is clean too, because its denominator is your grade, not the
engine's behaviour. The false-fire column inside that slice is not, and is quoted here only
to explain why it must not be used.

---

## 4. By entry minute

Two different questions, so two tables.

**When the engine fires, on all 303 S days and all 542 refusals:**

| window | fires on your S days | fires on your refusals | separation |
|---|---:|---:|---:|
| 09:30 – 09:45 | 16.5% | 7.6% | **+8.9** (95%: 4.4 to 13.9) |
| 09:45 – 10:15 | 35.0% | 28.0% | +6.9 (95%: 0.5 to 13.5) |
| 10:15 – 11:00 | 20.1% | 26.2% | **−6.1** (95%: −11.7 to −0.1) |

**The last 45 minutes of the window are actively backwards** — the engine trades your
refusals there more often than your S days, and that crosses zero on the wrong side. The
open is where the little discrimination it has actually lives.

**When you said the entry was** (85 S days carry a stated minute):

| your stated window | your S days | engine trades the day |
|---|---:|---:|
| 09:30 – 09:45 | 36 | 47.2% |
| 09:45 – 10:15 | 44 | 47.7% |
| 10:15 – 11:00 | 5 | 20.0% |
| no minute stated | 218 | 64.2% |

On the S days where you actually wrote down a minute, recall is **47%, not 59%.** Those are
the days you looked at hardest. The same selection caveat as §3 applies to the refusal side
of this split, so only the recall column is quoted.

---

## 5. Index versus equity

| pool | your S days | engine trades them | your refusals | engine trades those | separation |
|---|---:|---:|---:|---:|---:|
| Equity | 148 | 65.5% | 324 | 55.2% | +10.3 |
| Index (SPY/QQQ/IWM) | 78 | **41.0%** | 78 | 23.1% | **+17.9** |
| Other | 77 | 64.9% | 140 | 55.0% | +9.9 |

**46 of the 124 S days it misses are QQQ (22), IWM (13) and SPY (11).** The index pool is
where recall is worst and where discrimination is best — it says no far more often, and
when it says yes it is right more often. That is the shape of a gate set too tight rather
than a detector that cannot see.

---

## 6. The four comparisons that were decided on 34 cards, re-run on 303

Paired: the same days, both arms, exact McNemar on the days that disagree.

The left column is the number this repo actually recorded on the 34 cards
(`research/g71_scanners_recall_*.json`), not a paraphrase of anyone's verdict. Those files
were scored on the photocopy router, which is why base reads 23 there and 22 here.

| turn this off | what 34 cards showed | on 303 S days + 542 refusals | does the conclusion hold? |
|---|---|---|---|
| **Higher-timeframe veto** | S recall 23→24 of 34 (+3 pts), precision 39.7% → 37.5% | recall **59.1% → 65.7%** (+6.6, p < 0.001) but refusals **50.6% → 62.4%** (+11.8, p < 0.001). Separation **+8.5 → +3.3**, and the band now straddles zero (−3.5 to 9.9). | **Direction holds, verdict flips.** On 34 cards this looked like a cheap +3 points of recall. It is not cheap: turning the veto off buys recall by trading more of everything, and it costs most of the only discrimination the engine has. |
| **Pivot levels** | S recall 23→18 of 34 (−15 pts), precision 39.7% → 47.4% | recall **59.1% → 49.5%** (−9.6, p < 0.001), refusals **50.6% → 34.3%** (−16.2, p < 0.001). Separation **+8.5 → +15.2** (8.3 to 22.0), precision 39.5% → 44.6%. | **Direction holds, verdict flips — and this is the headline.** The 15-point recall cost is real and shrinks to 9.6. But on 66 refusal cards nobody could see the 16-point false-fire move underneath it. Pivot levels buy recall by firing on more days of both kinds, and on this measurement the engine is a **better judge of your days without them**. |
| **X-lift** | S recall 23→18 of 34 (−15 pts), precision 39.7% → 35.3% | recall **59.1% → 41.6%** (−17.5, p < 0.001), refusals **50.6% → 45.2%** (−5.4, p < 0.001). Separation **+8.5 → −3.6**. | **Holds, and gets stronger.** X-lift is the one arm that buys recall faster than it buys false fires. Without it the engine is worse than a coin flip at telling your S days from your refusals. |
| **Minimum stop %** | S recall 23→23 of 34, precision unchanged | recall 59.1% → 60.1% (3 days, McNemar p = 0.25). Separation +8.5 → +8.6. | **Holds.** A genuine tie, now on 303 days instead of 34 — the difference between "we could not see it" and "it is not there." |

**The headline is the pivot row.** Pivot levels have been carried as a recall win worth 15
points. On the full pile they are a *volume* win: they add 29 S days and 88 refusal days,
and the engine's ability to tell the two apart gets 6.7 points worse. Every recall direction
the 34-card sample gave survives. Every quality read it gave was underpowered — 66 refusal
cards cannot see a 16-point move in false fires.

Before anything is changed on the back of it: turning pivot levels off deletes 117 traded
days from this pile. It has not been priced. `backtest_2y.py` is the rig that decides whether
a better judge is a better book, and it has not been run on this arm.

Discordance and power, for the record: pivot ψ = 0.096, X-lift ψ = 0.175, HTF veto ψ = 0.066,
min-stop ψ = 0.010. At X-lift's discordance the paired test now has 0.99 power to see a
10-point move. At 34 cards it had 0.33.

---

## 7. What I did not do

- **No dollars.** Firing on a day is not trading it profitably. Every arm above changes which
  days get traded, and none of them has been priced through `backtest_2y.py`. Turning pivot
  levels off looks like a better *judge* and could easily be a worse *book* — 88 fewer refusal
  days traded is also 88 fewer trades, and this rig has no P&L in it at all.
- **No engine change.** `measure, then wire`. Nothing in `signal_runner.py` was touched.
- **No new grading.** Every judgement read was already on disk. No mark file was opened for
  writing; `git status` is clean of any change under `research/marks/`.
- **The other 10 arms.** `g72_recall_*` already carries level-vocabulary arms (HOD/LOD pairing,
  OR levels, six-level mode) on 1,096 days. They were not re-run here; they were already on
  the big pile.

## 8. Reproducing it

```
python research/g83_recall278.py            # five arms in parallel, ~4 min wall
python research/g83_recall278.py --reuse    # re-score the saved replays, instant
```

Per-arm replays land in `research/_g83_arms/arm_<name>.json` (regenerable, not tracked).
The scored output is `research/g83_recall278.json` and every rate in it carries a Wilson 95%
interval; every gap between two groups carries a Newcombe interval. 1,145 days replayed per
arm, **0 replay errors** in all five.
