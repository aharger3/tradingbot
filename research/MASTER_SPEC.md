# OMEN — THE MASTER SPEC

**2026-09-03.** Supersedes `OMEN-MASTER-SPEC.md` (2026-09-02) and `research/g92_master_spec.md`.
Everything in those two documents that did not survive an independent recheck has been **deleted, not
hedged**. Every number here names its fill, its denominator and the committed script that made it.

---

## 0. THE ANSWER, ON ONE PAGE

**What fires today:** the first size-gated candidate of the session. It fires on 498 of 498 sessions
and books **$34/day**. Live, a different gate is running — `sac_grade == "S"` — and it fires **0.18
times a day** and is worth **$14/day** laddered. That is the single largest gap between what we
publish and what the machine does.

**What should fire:** the same first candidate, minus two vetoes, both of which are rules he already
dictated and the repo already half-encodes:

1. **The gave-it-back veto.** If a bar *closed back through the level* between the break leg and the
   entry, it is not a break-and-retest. `downgrade.break_then_rejection` was written to catch exactly
   this and **cannot fire — 0 trips in 127,152 rows, and 0 rows even satisfy its precondition.** The
   geometry it misses is present on **1,126 of 3,773 traded break-and-retest rows (29.8%)**.
2. **The chase veto.** `downgrade.chase` already computes it correctly and nothing acts on it. It
   trips on 165 of 498 first-of-day rows, and those rows book −0.0412R against +0.1709R for the rest.

**What it targets:** four priced rungs and one that has no price. PT1 = session HOD/LOD (his answer,
2026-09-02). PT2 = nearest named level beyond it. PT3 = 2R. PT4 = 4R or the next level beyond. **PT5
is 20% of the position with no target at all** — a trailing stop marked at 11:00 — because **11.0% of
trades run past 5R and their conditional mean excursion is 6.40R**, and any price you put on that
tranche is a tax on the only part of the book that pays.

**What it is worth**, all on the same unit (one trade a day, first size-gated candidate, $/day over
all 498 sessions, honest close entry fill):

| | trades/day | $/day | ladder win | months green | max DD |
|---|---:|---:|---:|---:|---:|
| shipped exit, today | 1.00 | **$34** | 46.5% (book fill) | 12/25 | −$20,438 |
| + the ladder | 1.00 | **$101** | 39.8% | 12/25 | −$20,438 |
| + the gave-it-back veto | 1.00 | **$139** | — | **16/25** | −$17,718 |
| + the chase veto | 1.00 | **$173** | 40.9% | **17/25** | −$16,808 |
| the live gate as it runs now | 0.18 | $14 | — | 12/25 | −$7,274 |
| his bar | — | **$397** | — | 25/25 | — |

**$173/day is 44% of his bar and it is all bug-fixing** — no new model, no new signal, no fitted
threshold. It is in-sample on the book the defects were found in, and it must be re-priced once the
stop model below is fixed.

**What is still broken, in one sentence each:**

- **The ruler.** The book's stops fill on a **wick, at the level, at exactly −1.000R**. The close
  rule and the −1.25R floor that CLAUDE.md calls settled are both unreachable, and the `verify:` gate
  tests a module the book never runs. Every dollar in this document is measured pessimistically.
- **The classifier.** The engine's own eight-variable grade is **33.0% precise against a 28.5% base
  rate**. It does not contain what his eye contains, and three of its eight variables are inert or
  wrong-signed.
- **The live route.** It has never been observed working: one trade in the paper book's entire life,
  and today `bars_fetched: 0`.

**His read — "the rules make sense, the engine is misfiring" — is right about the machine and wrong
about the lateness.** The engine is not late: 402 of 444 first-of-day entries fire before 09:45, and
every arm that waits loses money. But it is misfiring: two of his eight grading variables are branches
that cannot be true, a wrong-signed third sits inside the grade live trades on, and the live gate and
the live exit are not the ones any published number describes.

---

## 1. THE BOOK, THE UNIT, AND THE RULER

**The book:** `research/bt2y_trades_retest_on.json` — 498 sessions (2024-09-03 → 2026-09-02), 28
symbols, **127,152 signal rows, 10,830 fired, 4,022 fired-and-traded, 4,205 halted**. Entry fills at
the bar **close**; `meta.entry_misses = 0`. Of every row the engine considered: `skipped_d` 105,876
(83.3%), fired 8.5%, `skipped_tight_stop` 6,241 (4.9%), halted 3.3%. Of the 4,022 traded rows the
legacy grade is **B on 3,959 (98.4%) and A on 63 (1.6%)** — zero A+, zero C. A five-letter ladder
that emits one letter.

**The unit, and there is only one.** One trade a day: the **first size-gated candidate** of the
session, substituting the next candidate when one is vetoed. 6,889 candidates clear
`signal_runner.min_risk_floor` across the 498 sessions, and 498 of 498 sessions have a first one.
**`$/day` divides by all 498 sessions**, so a day you sit out earns $0.

> The 2026-09-02 spec quoted the same quantity as both **$38** and **$34**, and the same ladder as
> both **$109** and **$101**, because one section divided by 444 rows and another by 498 sessions.
> The 444-row dollar figures are deleted. Where a rig prints per-444 (`g97`, `g99`, `g101`), it is
> used for *structure* — survival curves, rung distances — never for a dollar headline.

**The ruler is wrong, and it is wrong in our favour to fix.** `backtest_week.DISASTER_STOP` is on
with `DISASTER_R = 1.0`, and `stop_rule.disaster_stop_price(entry, risk, long, 1.0)` is
algebraically `t.stop` itself, because 1R *is* `|entry − stop|`. So the "disaster" order rests **at
the level stop**, fills on a **wick touch**, and is tested before the close check on every bar.
Measured consequence on the book: **min `r` = −1.000 exactly; 0 of 4,022 traded rows below −1.0; 0
between −1.25 and −1.0; all 1,448 full losses exit within a half-cent of the stop.** CLAUDE.md's
headline rule — *"stops trigger on the CLOSE, wicks stop nothing out, floored at −1.25R"* — is a
branch that cannot be true. This is the same defect `research/x2_stop_floor_audit.md` fixed on
2026-08-28, re-created by the disaster stop shipped 2026-08-29.

The `verify:` gate cannot see it: `research/test_runner_stop.py` imports only `research/exit_lab.py`,
which contains **zero** occurrences of `disaster` and fills stops solely from the bar close. It prints
*"stop-outs floored at −1.25R, wick-only days never stopped out"* and passes, on a code path the book
never takes.

**Priced once, on the recommended ladder, 444 rows, only the stop model differing:** as published
**$97/day**; under the pure close rule **$187/day, 44.8% win, 15/25 green, DD −$13,089, worst R
−1.250** (the floor becomes reachable). Wicks no longer stopping trades out more than pays for the
deeper losses. **Every figure in this document is therefore a floor, not a ceiling** — and no figure
can be trusted to the dollar until the ruler is settled (§6, bug 1).

---

## 2. WHAT FIRES

### 2.1 Do not wait for the open

His answer to "what tells you at 9:45 whether the day will trend" is *"how the open behaved"*, and it
is right — and unavailable. Implemented causally in `g101.open_state` (opening range = 09:30–09:44,
then read the closes to the entry bar; trend / chop / inside; own tape only, no lookahead), it
produces a read on **42 of 444 first-of-day rows (9.5%)**, because **402 of 444 (90.5%) fire before
09:45**. Only 8 rows carry a full trend read.

Waiting for it costs money and costs runners. Ladder $/day: first-of-day **$101**; first at/after
09:45 **−$19**; 09:50 **−$35**; 10:00 **−$131**. Runner rate decays monotonically with arrival —
23.5% first-of-day, 21.6% for 09:45–09:59 (n=1,964), 18.0% for 10:00–10:29 (n=2,450), 9.5% for
10:30+ (n=1,241).

**Ship `open_state` as a stamped field on every signal starting now. Gate on nothing.** It becomes
usable the day there are hundreds of rows where the read exists, and nothing in this design gets us
there. It is not a failed idea; it is an unmeasurable one on this book.

### 2.2 The gave-it-back veto — the biggest single move measured

`omen_bot.detect_break_retest` resets a failed break to step 1 **only while in state `seek_leave`**.
Once the machine reaches `seek_retest`/`hold`, a bar that *closes back through the level* never resets
it — it just updates `retest_idx`. So price chopping straight back through the level after the leave
leg still fires as a clean break-and-retest: **3,746 of 10,267 traced fired B&R rows (36.5%)** carry a
wrong-side close after the leave bar; **1,126 of 3,773 traded rows (29.8%)** do.

The downgrade variable written to catch this, `break_then_rejection`, is **structurally unreachable**.
`downgrade._break_bar` returns the *most recent* bar that closed through the level; any later close
back through would itself have been returned as the break bar. The function can only be true if the
**entry bar closes on the pre-break side**, which the detector forbids. **0 trips in 127,152 rows, and
0 rows satisfy the precondition.** The same root kills `stale_retest`: the retest is the very next bar
on 2,220 of 3,773 traded rows, so `(retest − break) > 10` essentially cannot hold — **6 trips in 4,022
traded rows**. Two of the eight variables in his own grading vocabulary are inert, and they die on the
same line.

**Priced** (`research/g107_gave_it_back_veto.py`; tolerance is the FSM's own eps, no fitted
parameter): veto the day's first candidate when a bar closed back through the level between the leave
bar and the entry, and take the next one. **$101 → $139/day, 12/25 → 16/25 green months, DD −$20,438 →
−$17,718, at the same 1.00 trades/day and the same 23.5% runner rate.** 104 of 498 first candidates
are vetoed (20.9%); 497 of 498 days still trade.

### 2.3 The chase veto

`downgrade.chase` is causal — verified: every window in `downgrade.py` ends at `i+1`, and there is no
forward index anywhere in the file — and nothing acts on it. On 498 first-of-day rows it trips 165
times (33.1%) and those rows pay **−0.0412R against +0.1709R** for the rest. Stacked on the
gave-it-back veto: **$173/day, 40.9% win, 17/25 green, −$16,808 DD, 27.4% runner**, with 496 of 498
days still traded.

Honesty about its provenance: chase is the winner of an unstated ~20-slice scan in `g104` and carries
**no significance test**. What justifies shipping it anyway is that it is not a fitted threshold — it
is his own word for the mistake, already implemented, already ratified, and it improves money, win
rate, drawdown, green months and runner rate simultaneously.

### 2.4 What the engine's own grade is worth as a classifier

`research/g109_sgrade_precision.py`, unit = judged symbol-day where the engine had a size-gated
candidate (**592 of them, 169 graded S — a 28.5% base rate**):

| the engine says | n | precision | recall |
|---|---:|---:|---:|
| `sgrade == S` | 109 | **33.0%** | 21.3% |
| `sgrade == A` | 140 | 27.1% | 22.5% |
| `sgrade == C` | 343 | 27.7% | 56.2% |

**The whole eight-variable ladder is worth +4.5 points of precision over guessing, and throws away
79% of his S days.** That is the classifier problem stated exactly, and it is not a bug — the model
does not contain what his eye contains.

It is also actively damaged. Same 498 first-of-day rows, ladder R when tripped vs clean:

| variable | trips | tripped | clean | |
|---|---:|---:|---:|---|
| `chase` | 165 (33.1%) | −0.0412 | +0.1709 | right-signed, strongest |
| `level_not_respected` | 312 (62.7%) | +0.0550 | +0.1772 | right-signed |
| `no_displacement` | 300 (60.2%) | +0.0514 | +0.1752 | right-signed |
| `counter_trend_not_respected` | **317 (63.7%)** | **+0.1926** | **−0.0604** | **wrong-signed** |
| `no_retest` | 35 (7.0%) | +0.1738 | +0.0951 | wrong-signed, small n |
| `ocr_not_respected` | 34 (6.8%) | +0.2184 | +0.0920 | wrong-signed, small n |
| `break_then_rejection` | **0 of 127,152** | — | — | **unreachable** |
| `stale_retest` | 6 of 4,022 traded | — | — | **near-unreachable** |

A variable that trips on two thirds of the book and grades backwards is inside the grade the live
process trades on. That is *why* the live S gate is worth $14/day.

---

## 3. WHAT IT TARGETS — THE LADDER, DERIVED

He delegated PT2–PT5 to us and told us to derive them from the corpus and the book. Here is the
derivation, on 444 size-gated first-of-day trades (`research/g97_mfe.py`, `research/g99_rung_recon.py`,
`research/g101_open_and_ladder.py`).

**The survival curve is the only real input.** Bar-ordered, MFE while still alive, before any stop:
0.5R **62.4%**, 1R **50.2%**, 2R **33.1%**, 3R **23.2%**, 4R **17.8%**, 5R **11.0%**. Conditional on
reaching 2R the mean excursion is **5.23R**; on 3R, **6.40R**. The book realises **+0.038R** per trade
while **+2.141R** (median +1.015R) was available while it was alive. **73.9% stop out before 11:00.**
The tail is fat and it is the entire edge.

**PT1 is his, and it is a scout, not a target.** HOD/LOD as of the entry bar sits a **median 0.495R**
away (mean 0.797R); it is 2R or further on only 9.2% of rows and already behind price on 3.2%. It pays
fast and small — exactly what a first scale should do.

**PT2 exists half the time, and when it exists it is a long way out.** The nearest named level
(PDH/PDL/PMH/PML) beyond PT1 is available on **220 of 444 rows (49.5%)** and sits at a **median
3.148R** when it does (sources: PDL 82, PDH 72, PMH 42, PML 24). So PT2 does not sit one step past PT1
— it skips clean over 2R half the time and is missing the other half. **That is why a 2R rung has to
sit between them, and why the ladder is four prices rather than a neat ascending list.** The level the
setup broke is not a candidate at all: it is behind price in the trade's direction on **0 of 444
rows**. "PT2 = the level" was an arithmetic impossibility.

**The shipped default:**

| rung | price | size | why |
|---|---|---:|---|
| PT1 | session HOD/LOD at the entry bar | 24% | his rule; median 0.495R, hit fast |
| PT2 | nearest PDH/PDL/PMH/PML beyond PT1 | 24% | exists on 220/444, median 3.148R |
| PT3 | 2R, snapped to a whole dollar or named level within 0.25R | 24% | 33.1% reach it |
| PT4 | the further of 4R and the next named level beyond PT3 | 8% | 17.8% reach 4R |
| **PT5** | **no price — trailing stop, marked at 11:00** | **20%** | 11.0% run past 5R, conditional mean 6.40R |

PT1–PT4 are 30/30/30/10 of the 80% that is priced. Rungs are built causally, sorted ascending in R,
and coalesced at a 0.20R minimum gap; a rung landing behind price is dropped and its weight
redistributed. **$101/day over 498 sessions, against the shipped exit's $34.**

**He asked for five rungs; the evidence supports five *pieces* and four *prices*.** Putting a price at
6R makes the ladder measurably worse, because a price caps the tail. The runner tranche is a dial and
it is monotonic: every 10 points added to it is worth roughly **+$8/day** and costs roughly one point
of win rate. 20% is where money improves and durability does not degrade. **Do not go past 60%** —
that is `flat 4R` wearing a ladder.

**And the exit the engine ships today does not have a runner at all.** Its "runner" rung lands
**inside** its own 2R rung on **303 of 444 rows (68.2%)**, median 1.300R, and its source is a whole
dollar on 389 of 444 (87.6%). `backtest_week` computes both and never compares them.

---

## 4. RUNNERS — THE TARGET CHANGES

His 2026-09-02 answer: *"Always scale, but we just want to identify winners that can run. Scouts are
good, but runners that can run is where the money's at."*

Define a runner as **MFE ≥ 3R before any stop**. There are **103 in 444 first-of-day trades (23.2%)**.

**Nothing the engine computes identifies one at entry time. Say it plainly.** The 2026-09-02 spec's
runner-feature table is **deleted**: it came from `research/_g100_runner_summary.json`, which has **no
committed script and is untracked**, and its top-ranked feature (`rangeb`) is **full-session
lookahead** — `backtest_2y.py:196-198` computes the day's whole high-low range and stamps it on every
trade of that day, and it is near-circular with the label besides. Same class: `dret`, `spy_trend`
(the SMA includes that day's close), `vol_regime` (terciles cut over the entire 2-year sample). Four
lookahead fields ride on all 127,152 rows, and two of them are inside the `g95` feature scan.

What survives is clean and small: the `disp` tag runs at 28.8% (n=73) and `chase` at 17.0% (n=165)
against a 23.2% base.

**One thing separates runners, and it is his label.** On the 592 judged symbol-days with a size-gated
candidate (`research/g103_what_its_worth.py`):

| | n | book $/trade | ladder $/trade | ladder win | **runner rate** |
|---|---:|---:|---:|---:|---:|
| he graded S | 169 | $36 | **$297** | 50.9% | **29.0%** |
| he did not | 423 | −$171 | −$170 | 33.6% | 16.3% |

Gaps: **+0.2065R** on the book fill (label-shuffle p=0.0142), **+0.4665R** on the ladder fill
(p<0.0001), and **+12.7 points of runner rate (p=0.0003)** — the largest effect in this repo. His eye
selects the trades that run, and the ladder is the only structure that pays for it. Neither works
alone.

*Denominator warning, and it is not a footnote:* judged symbol-days are not a random sample of
sessions — deck cards were often chosen **because** the engine fired. This is a within-judged-pool
comparison and an upper bound, not a forecast.

**So the classifier's target is not "is this an S". It is "will this one run", supervised by his 347 S
symbol-days**, because his S *is* a runner label wearing a grade's name. That reframing is his own,
and it is the only one the measurements support.

**There is no hindsight ceiling to chase.** `research/g95_is_the_oracle_real.py`: the real best-of-day
oracle pays $2,684/day ungated against a **null of $2,763** from random draws of the same candidate
pool — real is 97% of null and inside its range. Size-gated the oracle falls to **$2,422/day** (1,338
of 8,227 candidates fail `min_risk_floor`, the smallest risk denominator being **$0.02**; 81 of 498
oracle picks are sub-floor and carry 17.7% of the oracle dollars). Of 81 stamped features the best
day-selector is `dow = Wed`. **The oracle is max-of-N arithmetic, not a target.**

---

## 5. WHAT IT IS WORTH, AND WHERE THE CEILING IS

Same unit throughout: one trade a day, first size-gated candidate, $/day over all 498 sessions, honest
close entry fill, wick-touch stop (see §1 — this is the pessimistic ruler).

| | trades/day | $/day | win | months green | max DD |
|---|---:|---:|---:|---:|---:|
| today, shipped exit | 1.00 | $34 | 46.5% | 12/25 | −$20,438 |
| + ladder | 1.00 | $101 | 39.8% | 12/25 | −$20,438 |
| + gave-it-back veto | 1.00 | $139 | — | 16/25 | −$17,718 |
| **+ chase veto — shippable** | **1.00** | **$173** | **40.9%** | **17/25** | **−$16,808** |
| durability variant: chase drop-the-day + `sgrade` S-or-A | 0.33 | $79 | 41.6% | 16/25 | −$8,748 |
| ceiling: a perfect S classifier + the ladder | 0.28 | $111 | 56.1% | 17/24 | −$5,501 |
| his bar | — | $397 | — | 25/25 | — |

**Read the ceiling row carefully; it is the honest bad news.** On the **139 days** where he graded a
symbol-day S *and* the engine had a size-gated candidate, taking that S day and running the ladder
pays **$397 per traded day, 56.1% win, 17/24 months green, max drawdown −$5,501** — his bar exactly,
*per day traded*. Spread over all 498 sessions it is **$111/day**, because those days are 28% of the
calendar. Generously: 255 of 486 judged calendar days (52.5%) carry at least one S, so a perfect
classifier **with perfect recall** — the engine currently sees only 139 of those 255 — projects to
about **$203/day**.

**State it without burying it: this design's ceiling is roughly half his bar.** A perfect reproduction
of his eye, plus a perfect ladder, plus perfect recall, on one trade a day, lands near $203/day
against $397. A second S trade a day does not close it — the 169 judged S symbol-days pay $297/trade
against the first-of-day S's $397, so the second trade dilutes rather than doubles. Closing the gap
needs one of three things not yet on the table: more R per trade than this ladder extracts, a larger
universe of S-quality days than the detector surfaces, or the honest close-stop ruler of §1 turning
out to be worth what the single arm we priced says it is.

---

## 6. THE BUG LIST, RANKED BY MONEY AT STAKE

Each says whether it supports his *"the engine is misfiring"* read or contradicts it.

**1. The book's stop model is not the one anything claims. — supports (a measurement bug).**
`DISASTER_R = 1.0` collapses the disaster stop onto the level stop; every loss is exactly −1.000R by
construction; the close rule and the −1.25R floor are unreachable; the `verify:` gate tests
`research/exit_lab.py`, which has no disaster stop at all. **At stake: every dollar figure in the
repo.** The one arm priced both ways moved **$97 → $187/day** (444 rows). *This is a decision, not
only a fix: his R2 ballot says a disaster stop on touch is his rule — the finding is that at
`DISASTER_R = 1.0` "on touch" and "at the level" are the same price, so his close rule disappears.*

**2. `break_then_rejection` cannot fire, and the geometry it misses is on 29.8% of traded B&R rows. —
supports, loudly.** His own "it broke, then immediately gave it back", encoded as a branch that can
never be true. **Worth +$38/day** ($101 → $139) and +4 green months.

**3. Live trades a gate nobody had priced. — supports.** `live_scanner.py:588` trades only
`sac_grade == "S"`: 88 of 498 days, **0.18 trades/day, $14/day laddered** against $101 for taking
everything. It fires at a sixth of the rate he asked for. **−$87/day.**

**4. Live does not scale. — supports, and contradicts his own 2026-09-02 answer.**
`OMEN_LIVE_LADDER` defaults off (`options_sizer.py:81`); the live book's one trade reads
`"scaled": false`. **−$67/day** ($101 vs $34).

**5. Live and every published number grade differently. — supports.** `live_scanner.py:30` forces
`ENABLE_SAC_LADDER=1`; the book's 60-flag stamp contains no such key. **No live figure is comparable
to any backtest figure.**

**6. HTF bias is a hardcoded `None` live. — supports.** Tastytrade 401 → `_yf_daily_context` returns
bias `None` on every call; `journal/scanner-2026-09-01.log` logs `HTF unknown` **exactly 4,954 times**.
The backtest has a real bias on **126,198 of 127,152 rows (99.2%)**, so the bias demotions cannot fire
live: **live grades strictly looser than everything we publish.**

**7. A wrong-signed variable sits inside the live grade. — supports.**
`counter_trend_not_respected` trips on 317 of 498 first-of-day rows and marks better trades worse
(+0.1926R tripped vs −0.0604R clean), inside `SAC_LADDER_VARSET="shipped"`.

**8. `X_LIFT` bypasses `RETEST_REQUIRED` by line ordering. — supports.** All three C-caps are guarded
on `grade in ('A','B')` and run **before** `_apply_x_lift`, which lifts an X straight to B. Of the A/B
rows carrying `no_retest` that the cap should have caught, **903 of 903 are x-lifted** — not one
non-lifted row escaped; 468 were traded. X-lift is not marginal: **3,924 rows, all grade B, all
break-and-retest, 2,054 traded (51.1% of the traded book)**. Turning it off leaves the book fill
unchanged and costs the ladder ($101 → $75) while buying three green months — a durability/dollars
trade, not a defect on its own.

**9. The shipped exit's "runner" rung is not a runner. — supports.** Inside its own 2R rung on 303 of
444 rows; §3 replaces it.

**10. 84% re-entries bypass the S gate live. — supports.** `live_scanner._tier` returns TRADE for
`reentry_84_rule` **above** the `sac_grade` check, contradicting T-84 (*"84 percent rule can fire on S
A or C, but we only will trade S of course"*). **52 of 57 traded re-entries are non-S** (39 C, 13 A)
and they book +0.0914R, +$4,752. A correctness bug that currently pays: fix it by deciding, not by
reverting.

**11. `_bnr_displacement` looks at the wrong bars. — supports.** It reads `self.candles[-6:-1]`, a
fixed 5 bars before entry, while the rulebook defines displacement over the **break leg**. The break
bar is outside that window on **6,788 of 10,267 traced fired rows (66.1%)**, and it is not a
conservative miss: rows whose break is inside the window pay *worse*, and the `[disp]` tag rate is
*higher* when the break is unseen (24.6% vs 17.5%).

**12. Eleven gates carry a count of exactly zero. — supports (the repo's named bug class, at scale).**
`S_GATE`, `RULE_710`, `LEVEL_BLOCK_CAP`, `COUNTER_TREND_CAP`, `HTF_BIAS_GATE`, `LEVEL_RETIRE_TOUCHES`,
`ENFORCE_NO_REPEAT`, `NO_REPEAT_ENTRIES`, `SESSION_EXTREME_FRAC`, `ENABLE_SAC_LADDER` (book only) and
`ARRIVAL_LADDER` — all 0 of 127,152. The **only** C-cap with a pulse is `RETEST_REQUIRED` (1,786), and
bug 8 shows it misses 903. Separately: "don't enter at HOD/LOD" has two implementations and both are
dead (`HODLOD_PAIR = False` hardcoded, `SESSION_EXTREME_FRAC = 0.0`); `intrabar_stop` has been
unreachable since the honest-fill change (0 of 119,806 B&R rows have `stop != level_px`); and the
retired-setup gate guards setups no detector can emit.

**13. Two different rules are both called "confluence", 373× apart. — supports.** The engine's stamped
`sig['confluence']` (two setups on the same bar) fires 238 times; the book column `confluence` that
every SAC number divides by (`downgrade.has_confluence`) reads yes on 88,831. Any reader joining them
is joining two rules.

**14. Dead keys and mislabels. — supports, cheaply.** `TradeGrade.A_PLUS is A` and `D is X`, so the
strings `A+` and `D` cannot be produced: `GRADE_SIZE_PCT` has **6 keys and the live trade path can
reach exactly one** (0.8). `HIS_LADDER['A+'] = 'S'` is the only S in that map, so `his_grade()` can
never return S — and `test_his_ladder.py` asserts green on that unreachable value. 143 of 145
`MIN_STOP_PCT` skips are filed under `skipped_tight_stop`. 1,627 of 5,058 `[floor B:]` lifts are
re-capped to C on the same row (32.2%). `_attempts_84`'s key carries no symbol — harmless in the
backtest, live-only latent. `CONSECUTIVE_LOSS_HALT` is read, passed, printed and never used
(`day_ended` hardcodes 2). 264 repeat entries over 256 ideas (6.6% of traded rows) while the comment
in `_route` still claims no-repeat is on.

**15. `research/g100_*.py` does not exist. — neutral, and a rule violation.** The runner-feature table
it produced is unreproducible and its top feature is lookahead. Also: the book's own stamp carries
`dirty_py_count: 308`, so commit `a89e90e2` **does not identify the code that built it**.

**16. The live route has never been observed working. — supports.** One round trip in
`journal/paper-trades.jsonl` (TSLA 2026-09-01, put, grade A, stopped, −$783, `scaled: false`); today
`bars_fetched: 0`, `signals_fired_today: 0`, `last_error: rate limited`. Nothing in §7 can be verified
live until that is fixed, and no live number should be quoted until it has run a clean week.

**17. Roughly eleven `answers.*` keys are in no reader. — supports the "never lose a mark" rule.**
`real` (20), `regrade` (5), `wrong` (8), `eblock` (58), `emin` (58), `ballot` (16), `which_signal`
(12 — head-to-head judgements), `entry_minute` (6), `stop_pick` (6), `confirm` (4), `reject` (2).
(`is_s` (63) *is* read; `verdict` (36) is a rule ballot and correctly excluded.) The 2026-09-02 audit
found three of these and called it done — it was not. `marks_pool` needs an assertion that every
`answers.*` key seen in any corpus is either consumed or excluded with a reason.

### What contradicts him

**"Late entries."** The engine is not late. 402 of 444 first-of-day entries fire before 09:45, every
waiting arm loses money, and the runner rate falls monotonically with arrival. The old claim that the
engine is *"a median 24 minutes behind him"* is **deleted**, and so is the 2026-09-02 restatement
(*"median 1 bar, mean 9.4 bars, on 103 head-to-head pairs"* — the number 103 appears nowhere in
`g98`). The real figures: **46 usable pairs, 33 endorsed, median delta 0 bars, mean −9.4**; his minute
offers **+2.795R** against the engine's **+2.312R** and hits 2R 58.7% vs 43.5%, at **p = 0.1373 —
directional, not proven**, and it must be said that way every time it is cited.

What his marks actually show is an entry-*precision* problem inside the one setup he likes, not a
session-wide latency problem. The two need different fixes, and only the first is real.

**"The rules make sense."** Half. The rules as encoded do not separate his S — 33.0% precision against
a 28.5% base rate — and calling that a bug would send us hunting for a fix that does not exist. Fix
the bugs first because they are cheap and measured; then accept that the classifier has to be rebuilt
against a target it has never been trained on.

---

## 7. THE BUILD ORDER

Every step ships behind a flag, default OFF, with a test that counts trips on this book so a silent
drift fails the build.

1. **Settle the ruler.** Decide `DISASTER_R` (the two stops must be distinct prices or the close rule
   is dead), point `research/test_runner_stop.py` at `backtest_week`'s own bar loop instead of
   `research/exit_lab.py`, and rebuild the book. **Everything below re-prices after this.**
2. **`GAVE_IT_BACK_VETO`.** Implement it *inside* `detect_break_retest` as a state reset — so the FSM
   keeps hunting for a later clean break on the same level — not as a post-hoc filter over the
   existing book. The two are not the same arm, and the in-engine version may find *more* trades, not
   fewer. Test: 104 of 498 first-of-day candidates vetoed.
3. **`CHASE_VETO`.** Test: 165 of 498 trips.
4. **Ship the ladder live.** `OMEN_LIVE_LADDER=1` with the §3 rungs, PT5 unpriced. He has answered the
   question that flag was waiting on.
5. **Close the live/backtest divergence** — one grader, one process — and with it the live S gate
   (bug 3), the 84% bypass (bug 10) and the HTF bias (bug 6). Until this is done, no live number may
   be compared to any backtest number.
6. **Fix or drop `counter_trend_not_respected`**, then re-price `sgrade`.
7. **Write and commit `research/g100_runner_features.py`** with `rangeb`, `dret`, `spy_trend`,
   `spy_ret` and `vol_regime` struck, and re-run the runner scan clean.
8. **Then rebuild the classifier against the runner target**, supervised by his S labels — not against
   the grade.

**Done for this lane** is unchanged: fire 1–3 times a day, lift precision above 39.5% without losing
S-day recall, and carry one-trade-a-day past $397/day with every month green. Steps 1–5 reach
**$173/day on the pessimistic ruler** — the first honest checkpoint, not the finish.

---

## 8. WHAT ONLY HE CAN ANSWER

Four cards and one decision. Each buys the one thing nothing else can produce.

1. **What a runner looks like at entry.** 103 runner symbol-days paired blind with 103 matched
   non-runners — same setup family, same symbol pool, **chart cut at the entry bar** — one binary
   each: *"would you still be in this past 2R?"* This is the training label the classifier needs and
   it does not exist yet. Nothing the engine computes substitutes for it.
2. **Does the S label survive outside the judged pool?** 60 symbol-days drawn at random from sessions
   **the engine never fired on**, S / none, no engine annotation. Every number in §4 and §5's ceiling
   row is within-judged-pool; this is the only thing that turns an upper bound into a forecast.
3. **Where does the third piece come off when there is no level?** PT2 is missing on **224 of 444
   rows (50.5%)** and the ladder silently redistributes that weight today. 40 charts cut at the moment
   price reaches 2R, level map overlaid, one question: *where does the next scale go?*
4. **Is his entry minute really better?** 150 head-to-head pairs — his minute against the engine's,
   same tape, same day, entry minute only. `g98` is n=46 at p=0.137 and cannot settle it.
5. **The one decision, not a card:** the disaster stop currently rests **at the level**, so wicks stop
   you out and his close rule never fires. Should it sit **below** the level — a real second stop,
   with the close rule live and the −1.25R floor reachable — or is stopping on the touch what he
   wants? His R2 ballot says touch; the finding is that at `DISASTER_R = 1.0`, "touch" and "the level"
   are the same price, and one of his two rules disappears.

---

*Reproduce, do not quote: `research/g95_is_the_oracle_real.py`, `g96_does_his_S_predict.py`,
`g97_mfe.py`, `g98_his_minute_vs_engine.py`, `g99_rung_recon.py`, `g99_ladder_ab.py`,
`g101_open_and_ladder.py`, `g102_wait_for_the_open.py`, `g103_what_its_worth.py`,
`g104_gate_value.py`, `g105_fsm_trace.py`, `g106_break_bar_dead.py`, `g107_gave_it_back_veto.py`,
`g108_xlift_value.py`, `g109_sgrade_precision.py`. Verify gate green at time of writing:
`research/regression_gate.py` PASS, `research/test_runner_stop.py` PASS — subject to §1, which is
exactly the point.*

*Deleted from the 2026-09-02 spec because they did not survive recheck: the $38 and $109 per-444
dollar headlines; "113 corpus statements name HOD/LOD" (unreproducible — scans give 158 to 801
depending on the field set, and no definition of "statement" was given); the runner-feature table (no
committed script, top feature is lookahead); "median 1 bar, mean 9.4 bars, 103 head-to-head pairs";
"bugs #1–#4 are worth on the order of $150/day" (asserted, and its two components are not additive on
the same population); "the backtest has a real bias on 126,314/127,188 rows" (a denominator that is
not the book's row count); "`GRADE_SIZE_PCT` — 5 keys"; "entry named on 4 of 8" `answers.wrong` rows
(it is 5, plus an unmentioned `no_trade`); "244 extra entries over 240 ideas" (it is 264 over 256);
and the g96 citation carried in the brief (stale pre-repair pool — the finding survives and
strengthens: gap +0.1652R at p=0.0266 ungated, +0.2065R at p=0.0142 size-gated).*
