# g201 refuter #2 — F9 / MID25: the arithmetic reproduces, the headline does not survive

**What is different now:** MID25's numbers reproduce to the dollar, but a paired bootstrap over the
498 sessions puts the MID25-minus-CLOSE gap at **+$62.4/day with a 95% interval of
[−$46.8, +$170.4]** — an interval that contains zero — and once you account for MID25 being the
**best of 3 arms in this row and the best of ~53 entry/fill arms priced on this same book**, and
for the fact that **no half was held out** (H1 on its own picks MID50, not MID25), the claim
"MID25 pays $100/day vs the shipped $34/day" is a point estimate with no confidence behind it, not
a measured $66/day improvement. **Verdict: REFUTED as stated.** A weaker claim survives and is
stated at the bottom.

Fill: signal-bar CLOSE for the CLOSE arms; a strictly-after-signal resting-limit touch
(`g80_ordertype_grid.limit_touch`, fill at the limit unless the bar opened through it) for MID25 /
MID50 / MID75; exits through `G.run_trade` → `backtest_week._ladder_bar` → `stop_rule`; size-gated
on `signal_runner.min_risk_floor`; 1R = $1,000; book `research/bt2y_trades_retest_on.json`
(498 sessions, 8,227 candidates); one-trade-a-day = first sizeable candidate of the day.
Script: `research/g201_refute2.py` → `research/g201_refute2.json`.

---

## 1. The claim reproduces exactly — that is not in dispute

| arm | $/day | H1 | H2 | days traded |
|---|---:|---:|---:|---:|
| CLOSE (g158's control: the book's own recorded pnl) | **$33.9** | $135.7 | −$67.8 | 498 |
| **CLOSE_RT** (same control, re-priced through `G.run_trade`) | $37.3 | $139.5 | −$64.9 | 498 |
| MID25 | **$99.7** | $164.3 | $35.2 | 497 |
| MID50 | $90.3 | $179.8 | $0.8 | 490 |
| MID75 | −$46.9 | $22.5 | −$116.3 | 449 |

g158's $100 / $34 / $90 all reproduce. The 86% mid-fillable figure (7,096 / 8,227) reproduces.
Nothing below is a coding objection.

**One small book-keeping fault:** g158's CLOSE arm reads each row's pnl straight out of the book,
while its MID arms are re-priced through `G.run_trade`. Those are two different replays. Running
CLOSE through the same replay as the MID arms moves it $33.9 → $37.3/day (+$3.4/day, 95% CI
[+$1.3, +$5.8]). Small, but it means the published table did not compare like with like. Every
number below uses **CLOSE_RT**, the like-for-like control.

---

## 2. Sampling error: the interval on the gap contains zero

Paired bootstrap, 10,000 resamples of whole sessions (a session with no pick contributes $0 and
stays in the draw — `g80.day_ci`'s convention):

| comparison | mean gap $/day | 95% CI | P(gap ≤ 0) |
|---|---:|---|---:|
| MID25 − CLOSE (g158's own headline pair) | +$65.8 | **[−$43.4, +$174.3]** | **11.8%** |
| MID25 − CLOSE_RT (like-for-like) | +$62.4 | **[−$46.8, +$170.4]** | **12.9%** |
| MID50 − CLOSE_RT | +$53.0 | [−$103.9, +$209.4] | 25.0% |
| CLOSE_RT − CLOSE (the book-keeping fault above) | +$3.4 | [+$1.3, +$5.8] | 0.06% |

The one difference in that table that is statistically distinguishable from zero is the accounting
artifact. The headline is not. This is the same error-bar problem `CLAUDE.md` already names:
every A/B in this engine moves less than the day-level noise.

---

## 3. Multiplicity: MID25 is the best of 3 here and the best of ~53 on this book

Within this row, three fractions were tried and the best was published. Bootstrapping the
**maximum** of the three arms' gaps over CLOSE_RT — the statistic that was actually reported —
gives **+$62.4/day, 95% CI [−$29.7, +$206.8], P(max ≤ 0) = 7.1%**. Selecting the winner of three
and quoting its unadjusted number overstates it.

The family is much larger than three. Entry/fill arms priced on this same 2-year book before F9:

| row | arms |
|---|---:|
| `g80_ordertype_grid.py` (BOOK, A, A2, B, C, D, E) | 7 |
| `g87_retest_tol.py` (`g87_retest_tol.json` arm list) | 31 |
| `g88_level_limit.py` | 5 |
| `g90_fill_arms.py` (5 arms + close control, `RETEST_WINDOW` swept 6/12/24) | 6 |
| `g158_mid_candle_arms.py` | 4 |
| **total** | **~53** |

At ~53 arms on 498 sessions with a per-arm P(gap ≤ 0) around 12%, finding one arm at this
magnitude is what the search itself produces. The morning report already drew this exact
conclusion for the rule-mining family — *"with 25 candidates tried the expected number of noise
winners is ~5.6"* — and F9 sits in a family twice that size.

---

## 4. H1 selected the arm; no half validated it

MID25 was chosen after both halves were on screen. Run the split honestly — let **H1 alone** pick
the fraction, then read H2 as the held-out half:

| arm | H1 gap vs CLOSE_RT | H2 gap vs CLOSE_RT | P(H2 gap ≤ 0) |
|---|---:|---:|---:|
| MID25 | +$24.7 [−$140.6, +$191.7] | +$100.1 [−$33.8, +$239.2] | 7.2% |
| MID50 | +$40.3 [−$183.0, +$272.4] | +$65.6 [−$144.2, +$278.9] | 27.3% |
| MID75 | −$117.1 [−$340.1, +$112.7] | −$51.4 [−$307.9, +$224.0] | 84.2% |

**H1 on its own picks MID50** ($179.8/day on H1, against MID25's $164.3). Its held-out H2 gap is
+$65.6/day with a 27% chance of being ≤ 0 — no validation. MID25 only becomes the winner once H2
is read, so **MID25's "both halves positive" is a selection credential, not a validation** — the
identical fault the morning report caught in the S_CLASSIFIER v0 refutation.

Note also that on H1 alone — 250 sessions — MID25's advantage is **+$24.7/day**, not $66. The
headline is carried by H2.

---

## 5. Concentration: the mean is a tail statistic, though the direction is not

Daily gap (MID25 − CLOSE_RT), 498 sessions, 355 of them differing:

| statistic | value |
|---|---:|
| net gap | $31,068 (+$62.4/day) |
| positive / negative differing days | 208 / 147 |
| median gap on differing days | +$246 |
| largest single day | 2025-02-06, +$5,521 (17.8% of the net gap) |
| top 5 positive days' share of the net gap | **72.2%** |
| top 20 positive days' share of the net gap | **208%** |
| net gap after dropping the top 5 positive days | +$17.5/day |
| net gap after dropping the top 20 positive days | **−$70.2/day** |

Twenty sessions out of 498 — 4% of the book — flip the sign of the whole result. **In fairness to
the claim, a symmetric trim does not:** trimming both tails equally leaves +$66.3/day (1% each
tail), +$65.4 (2.5%), **+$61.5 (5%)**, and a two-sided sign test on the 355 differing days is
p = 0.0014. So the *direction* is broad-based; it is the *magnitude* — the thing the claim is
about — that lives in a handful of sessions and in an interval that contains zero.

---

## 6. Where the gain comes from, and why the row's own family contradicts itself

Splitting the gap by whether the two arms picked the **same** candidate that day:

| component | days | $/day |
|---|---:|---:|
| **fill** (same candidate, better price) | 368 | **+$97.4** (95% CI [+$23.4, +$173.1]) |
| **selection** (MID25 skipped an unfilled candidate, day's pick moved) | 129 | **−$35.6** |
| MID25's fillability filter applied to CLOSE prices ("SELECT_ONLY" arm) | — | **−$24.8/day**, vs CLOSE_RT's +$37.3 |

So the reshuffle is a **cost**, not the source of the gain — and a matched null (drop candidates at
random at MID25's own 7.5% skip rate, book CLOSE prices; 1,000 draws) never reaches $100/day
(mean $34.0, p95 $60.8, max $85.0, P(null ≥ MID25) = 0.000). **The gain is not manufactured by the
day-picking mechanism.** That part of g158 stands — but see §8: the gain is not the *price* either.
It is the **later entry bar**, which drags `intrabar_stop` onto that bar's extreme. Refuter #3's
0%-back placebo (a limit resting at the close price itself, filled strictly after the signal bar)
pays **$105/day** — more than MID25.

What does not stand is that the fill gain is a stable quantity. Priced per candidate, paired on the
signals where both arms filled:

| arm | n | arm mean R | CLOSE_RT mean R | paired diff | one-trade-a-day $/day |
|---|---:|---:|---:|---:|---:|
| MID25 | 7,609 | +0.0287 | −0.1247 | **+0.1534R** [+0.128, +0.181] | **+$99.7** |
| MID50 | 7,076 | +0.3704 | −0.2118 | **+0.5822R** [+0.403, +0.824] | +$90.3 |
| MID75 | 6,397 | +0.8672 | −0.2883 | **+1.1555R** [+0.845, +1.541] | **−$46.9** |

**Per-trade R rises monotonically with depth while money goes negative.** The arm with by far the
biggest per-trade edge (MID75, +1.16R) is the arm that loses $47/day. Two metrics on the same
family pointing in opposite directions means neither is measuring an edge. The mechanism is the one
`CLAUDE.md` already names: resting deeper toward the level with the structural stop unchanged
**shrinks the risk denominator** — MID25's median risk is **$0.406 against CLOSE_RT's $0.540**
(−25%), and 9.1% of MID25 fills sit under a 10-cent risk against CLOSE_RT's 4.9% — so the 2R target
moves 25% closer and R inflates without the trade being better. `min_risk_floor` gates the worst of
it; it does not remove the tilt.

---

## 7. "One of the two is wrong" is a false dichotomy

The claim asserts F9 contradicts g90's R2 ruling. It does not. They are different arms measured
different ways:

| | g90 R2 `mid_candle` | g158 MID25/50/75 |
|---|---|---|
| price | the confirm bar's **geometric midpoint** — above the close as often as below, so a **worse** price roughly half the time | 25/50/75% of the bar's range **back from the close toward the level** — better than the close **by construction** |
| window | 12 bars | to the 11:00 cutoff |
| stop | book stop, **no `intrabar_stop`** | `intrabar_stop` applied |
| exits | blind 2R, `LADDER_MODE=None` | shipped ladder (`hod_then_runner_be`) |
| book | `bt2y_trades.json` (stale, different commit) | `bt2y_trades_retest_on.json` |
| set | 925 traded signals, grade ≠ C, reentry excluded | 8,227 candidates incl. 4,205 halted rows |
| unit | **paired per-trade mean R** | **unpaired one-trade-a-day $/day** |

g90's finding ("mid pays 0.2458R less than close on the 80% where it is reachable") and g158's
finding ("a limit strictly better than the close pays more") are both what you would expect from
their own definitions. **Neither is wrong; the two were never measuring the same arm.** The
reconciliation is arithmetic, not a contradiction to be adjudicated — and it is worth noting that
g90's 20%-never-returns and g158's 7.5%-never-fills differ for the same reason (a 12-bar window
against a full session, and a midpoint against a below-the-close limit).

---

## 8. Verdict

**REFUTED as stated.** Specifically:

1. **"MID25 pays $100/day vs the shipped $34/day"** — reproduces as a point estimate, but the gap's
   95% interval is [−$47, +$170] and P(gap ≤ 0) = 12.9%. It is not a measured improvement.
2. **"Best of the mid-candle arms"** — it is the best of 3 here and the best of ~53 entry/fill arms
   on this book; the best-of-3 statistic's own interval, [−$30, +$207], contains zero.
3. **Both halves positive** — H1 alone picks MID50, not MID25. Nothing was held out.
4. **"This contradicts g90 R2; one of the two is wrong"** — false. Different price, window, stop,
   exits, book, signal set and metric.

**The one thing that looked like it survived, and does not.** On the 368 sessions where both arms
pick the same candidate, MID25 beats CLOSE_RT by +$97.4/day, 95% CI [+$23.4, +$173.1], sign test
p = 0.0014 — a broad-based, sign-stable difference that my own matched null cannot manufacture. I
had that written down as a surviving directional finding about entry price. **It is not one.** That
comparison confounds the price with the *bar*: MID25 enters on a **later** bar than CLOSE, and
`intrabar_stop` then re-anchors the stop to that later bar's extreme. Refuter #3's placebo isolates
it — a limit resting at **0%** of the bar's range, i.e. at the very close price CLOSE already pays,
scored the same strictly-after-signal way, pays **$105/day, more than MID25's $100**, and the "25%
back toward the level" price improvement is worth **−$4.8/day, 95% CI [−$107.8, +$95.8]**
(`research/g201_refute3.md`). The deferred entry bar is the whole effect; the price is nothing.
That is the same mechanism my §6 reads off the risk denominator (median risk $0.406 vs $0.540) from
the other side, and it is consistent with refuter #1's finding that $73 of the $100 is leakage
(`research/g201_refute1.md`). **All three refuters land on REFUTED independently. Nothing here is
shippable, and no weaker version of the claim stands.**

---

Reads only. No engine file edited, no mark file opened, nothing shipped.
