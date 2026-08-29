# T22 — Adjudication of OMEN 7.1

Read every track. Pick the stack. Name what is inside its own error bar. Name the overlap
risk. This file decides nothing about a ratified item (R1–R33); those are Austin's answers
and ship at his answer.

**The money gate is not reached and nothing in this wave brought it close.** Mean R is
**+0.5481** against a target of **2.0**; T5 replayed 47 causal exit arms and none beat the
shipped exit outside its own bar, and its non-causal ceiling says a *perfect* selector on
this exit reaches 2.0R on only **51.6%** of the book. Durability is **met** (25/25).
Recall moved for the first time in the project's history: **52.9% → 67.6%** on one lever.

---

## 1. What I verified myself, rather than quoting

| check | result |
|---|---|
| `python research/regression_gate.py` on `t0-ratified` (9edd2ba7) | **PASS**, exit 0. baseline any_signal 75 / s_grade 5, current 80 / 5. "no baseline-fired mark went silent." |
| all 21 track commits exist | yes, each isolated on its own worktree branch |
| anything merged | **nothing.** Zero track branches are merged into `t0-ratified` or `main` |
| which tracks descend from T0 (9edd2ba7) | **14 do. 7 do not:** T4 `9eeeea07`, T7 `a00cb6f1`, T16 `019c0f1d`, T17 `7aa0d99d`, T18 `2daf1252`, T19 `a586ed95`, T20 `49a48129` |

### The three FAIL gate reports are worktree artifacts, not regressions

T17, T18 and T19 all report the gate RED with 6 dropped `s_grade` marks (GOOGL 2024-10-15,
IWM ×3, QQQ 2025-02-25, UBER 2025-09-11). All three fork from `3da10552`, an old main that
predates T0. I ran the gate on `t0-ratified` myself: it passes. Those three FAILs describe a
stale base, and all three tracks are read-only reports that touch no engine file. **Dismissed.**
T16's gate was left PENDING and was never confirmed by anyone; its numbers are a post-hoc
sweep over T0's committed book, so the gate is not load-bearing for its finding.

### T4's baseline is the pre-ratification engine, and R7 is already satisfied

This is the one place a track's headline does not survive adjudication. T4 reports the index
count moving **18 → 127** and states it "re-ran against the ratified (post-T0) engine". Its
commit's parent is `3da10552`, not T0, and its own gate line reads `any_signal 75 → 75 (+0)`
where every T0-descended track reads `75 → 80`. It measured the **old** engine.

T0 already moved indices **18 → 137** as a side effect of the ratified table
(`t0_ratified_rebaseline.md:52`, and its own §115 says so in words). **T4's arm lands below
the count the shipped book already has.** R7 — *"Should be firing more…"* — is met at 7.6×
without T4's mechanism. T4's diagnosis (the price-scaled B&R min-risk floor benches 93–97% of
index D-grades) may still be correct and its mechanism is committed and default-OFF at no
risk, but **no decision may be taken on its numbers until it is re-run on the T0 base.**

---

## 2. The stack

Ordered by how safely each lands. Everything below ships ON unless stated.

### 2.1 T21 — card pre-filter, `reach ≤ 8.0R`, fire-half only · SHIP ON

The safest thing in the wave and the one that compounds. It is a homework instrument, not an
engine lever: it cannot move a book number, cannot move recall, and cannot interact with any
other item in this stack. It cuts his refusal rate 71.1% → 63.5% (+25.4 points, CI
[+5.3, +39.7], Fisher p = 0.0211) while keeping **94.4%** of the engine's cards on his
held-out S days and 88.5% of the cards he actually graded.

Honest: the same lift on the held-out lanes is **null** (+11.1 pts, CI [−22.1, +28.1],
p = 1.0), it rests on 26 positives, and the lower bound of the main effect is +5.3 points.
Ship anyway — the downside is bounded and measured (one S-day card, `SPCX_2026-06-25`), and
Austin's attention is the only input in this project that cannot be regenerated. Do **not**
ship the four-check fit that scores +41.1 points; it throws away 8 of his 18 S-day cards.

### 2.2 T10 — `X_LIFT=clean` · SHIP ON

**The only lever in 21 tracks that moves the governing metric.**

| | off | clean |
|---|---|---|
| held-out S recall | 18/34 = 52.9% | **23/34 = 67.6%** |
| gained / lost | — | **+5 / −0**, exact McNemar p = 0.031 |
| held-out precision | 36.0% | **40.4%** |
| recall − false-fire rate | +0.045 | **+0.161** |
| win rate | 42.8% | 46.7% |
| max drawdown | 32.43R | 27.68R |
| months green | 25/25 | 25/25 |
| mean R | +0.5378 | +0.4952 (**−0.0426 against ±0.1167 — null**) |

It is the only arm that raises recall **and** precision **and** win rate **and** lowers
drawdown, with a money move inside its own bar. Reject its siblings: `br` trips on 93.6% of
the vetoed pool (over method rule 3's 85% line — a finding about `_grade_pa`, not a
threshold), and `all` is the one arm whose money move is real and it is **negative**
(−0.1955R, outside ±0.1028) at 44 false fires.

Two caveats that must travel with it. Its window is 500 sessions ending **2026-08-10**, not
T0's 2026-08-21, so its `off` column (+0.5378R / 2,548) is not T0's published book and must
never be quoted against it. And **96.4% of what it promotes dies on `_min_viable_stop`** —
the lever is operating on 3.6% of its intended population, so its measured size will move
the day Austin answers the stop question. Ship it for the recall, not for the size.

### 2.3 T20 — loss halt in both paths · SHIP ON, because R31 says so

R31 is ratified with verdict `both` and T0 did not land it. Method rule 4 puts it in at his
answer. Its A/B is a **null result** (+0.0493 against ±0.1725, 28% of the bar) and that is
the price tag, not a veto. Durability holds 25/25.

But two things must be reported, not buried. It removes **902 trades, 34.8% of the book**,
and it fires on **53% of trading days** — which collides with **R20**, *"Quality over
quantity, but he wants to trade every day."* Both are his. Only he resolves it (blocker 7).
And its 53% was measured on the pre-T10 book; see §3.

### 2.4 T9 — `MIN_STOP_PCT = 0.08%` · SHIP ON, **scoped to exclude the one-candle rule**

Removes 4.4% of the book (115 rows) at **zero held-out S recall cost at every threshold
tested up to 0.15%** — 18/34 before and after. The removed group's median R is a flat −1.0;
its positive mean is carried by 3-to-5-cent-stop blowups (median removed stop **$0.17**,
minimum **$0.03**) that no real fill realizes. This is the same artifact class that inflated
T3's 84% slice (AMD 2025-11-07: a 2-cent stop booking +187.5R) and that produced W1's dead
`on_all` +7.4974R. Cutting it is worth more than the −0.0462R it costs on paper.

**Hard constraint:** it must not apply to `one_candle_rule` rows. R4 is ratified with verdict
`none` — *"no minimum stop distance on OCR, size to the stop"* — and a book-wide 0.08% floor
re-litigates it. T9 measured book-wide, so **T23 must re-measure the scoped version**; the
number above is the unscoped one. Do **not** ship the symbol-level wide-spread filter: it is
unreachable (all 28 traded symbols already sit inside Austin's own volume-filtered universe)
and there is no NBBO anywhere in this repo to grade it on.

### 2.5 Cleanups that carry no behaviour risk · SHIP

- **T13** — the short-side coverage fix to `spec2_grading_check.py`. Pure test coverage.
- **T19** — delete FVG and flag. Corpus-absent, already permanently disabled, R5 + R33.
  Record the reason with the deletion.
- **T3's code, with `RULE84_SOURCE` default OFF** (see §4). The one settled piece inside it —
  *"same stop unless a new stop makes more sense"*, never implemented before and now
  implemented with a tested literal reading — should be reachable independent of the flag.

---

## 3. Overlap risk — the thing this wave did not measure

Twelve lanes ran single-lever A/Bs and **zero combinations**, and
`research/p23_combined_arms.md` already watched a stack underperform its parts: P19 alone
scored gate +0.033 on TUNE and the P19+P20+P18 stack fell to **+0.007 on HOLD** while S
recall collapsed 5/14 → 1/14. That is the precedent and it is not hypothetical.

**Nothing in this wave has ever been run in combination, and the regression gate has never
been run on any merge of two track branches.** Every "PASS" above is a single branch against
T0. The specific interactions I can name:

1. **T10 × T20 is the sharpest.** T10 `clean` adds 28.9% more trades. More trades per day
   means the two-consecutive-loss halt trips **earlier and on more days**, and T20's 53%
   halt rate and −34.8% trade count were both measured on the pre-T10 book. Stacked, T20's
   cut is larger than measured and lands on rows T10 was added to capture. These two must be
   measured together or not shipped together.
2. **Three shrinking levers compound multiplicatively and none was measured against another.**
   T20 −34.8%, T9 −4.4%, and (if it were shipped) T2 −24%. Against T10's +28.9% on a 2,595-row
   book, the naive composition lands near 2,080 trades — and it is naive precisely because
   T20 removes trades *chronologically*, so which trades T9 and T10 add changes which trades
   T20 kills.
3. **T2 × T3 pull opposite ways on the same funnel.** T2's strict OCR detector removes 518 of
   572 OCR trades and, by knock-on through `_arm_84`, 74 fewer 84% signals. T3's source
   rewrite widens the 84% rule 312 → 764. Both are default OFF here, which is the only reason
   this is not already a problem.
4. **T9 × T10 encode opposite philosophies about stop width on populations that touch.** T9
   adds a stop-width floor; T10's central finding is that an existing stop-width guard is
   what caps recall — 10 of Austin's 13 graded vetoes die on `_min_viable_stop`, at a median
   stop of **0.034% of price**, which is *below* T9's proposed 0.08% floor. They measured
   disjoint populations (T9 the traded book, T10 the blocked pool), so this is not yet a
   contradiction — but it becomes one the moment Austin loosens the stop guard, and both
   levers' sizes move on that one answer.
5. **T5, T6, T8, T11 are exit/instrument replays over a book that the stack changes.** Every
   one of their nulls was computed on the shipped selection. If T10 and T20 change which rows
   are in the book, those nulls do not automatically survive — they are refutations of the
   *family*, not of the numbers, and should be read that way.

**T23's obligation:** run the stack as one book, report each lever's *marginal* contribution
inside it, and treat any lever whose marginal sign flips against its solo sign as unshipped
until re-measured. Score held-out recall on the combined book — that is the number that
decides whether this wave was worth anything.

---

## 4. Rejected, and why

| item | why it does not enter |
|---|---|
| **T14 `gate` / `credit` / `credit_all` — the S/A/C routing switch** | Does not beat 52.5%. `gate` 50.0% and loses an S day and 46% of the book; `credit` ties at 52.9%; `credit_all` reaches 97.1% only by ceasing to refuse (92.4% false fire, it fires on 25 of his 27 explicit *no*s). **Third refutation** after W1 and pre-ratification T11. The switch stays legacy. |
| **T14 `s_promote`** | Every measurable axis is a wash — mean R +0.0075 inside ±0.0870, recall 18/34 → 18/34, +0/−0 held-out. It is not a measurement decision; it is Austin's, and R18 is his own sentence. Blocker 5. |
| **T10 `br`, `all`** | `br` 93.6% reachability (over the 85% line); `all` −0.1955R outside its bar, 44 false fires. |
| **T2 `OCR_STRICT` default ON** | Held-out recall does **not move** (18/34 both ways, same 16 misses) and mean R is null (+0.0095 ± 0.1314). Against that it deletes 624 trades including **147 he would grade S**. And its binding clause is one constant, `STRONG_PA_MULT = 1.5`, borrowed from the 84% rule's reclaim gate, which nobody has ever asked him about — the identical bug class R24 called out on the consolidation 0.5%. Land the flag OFF; the threshold is blocker 3. The detector finding (19 of his 20 refusals rejected) is real and is the best evidence in the wave that OCR is a *detection* problem. |
| **T3 `RULE84_SOURCE` default ON** | Recall flat, whole-book move +0.1713 inside ±0.1861, and the slice effect is materially a sizing artifact. It is also **inert**: `_grade_pa` carries an unconditional `if not candle.is_bullish: return D` ahead of any pattern check, so "no pattern needed" cannot fire. |
| **T5 — all 47 exit arms** | Zero beat the shipped exit outside their bar; 29 clear their bar and **every one moves down**. `hold_eod` tops the mean-R column at +0.5895 but is inside its bar *and* fails durability at 20/25 with a −47.92R month. Keep `SCALE_PLAN="hod_then_runner_be"`. |
| **T6 `FASTER_CUT`** | All four arms null on ratified fills (best +0.0148 against ±0.0429). The X board's refutation survives its own claimed bug fix. A confirmed refutation is a real result. |
| **T11 `BE_TRIGGER=mfe`** | Not a verdict — the 730-day run never finished; the committed numbers are a 60-day, 3-month window and its recall column (0/34) is a coverage artifact. Re-run before reading. |
| **T16 at 1.0% / 1.5%** | No held-out recall score at any threshold, and 1.0% discards 65 S-grade trades (1.5% discards 152). Land only the finding: **the shipped 0.5% is dead** (0.2% trip rate, under the 1% floor) — an authorless constant that has never applied to a day. R24 asked for the sweep, and the sweep's answer is that the knob is inert. |
| **T4 universal (all-symbol) ATR-scaled min risk** | Floods equities: tiny-stop trades 2.09% → 22.40%, equity mean R 0.786 → 0.508. Never ship this way. |
| **T4 index-scoped** | Not rejected on merit — **rejected as unadjudicable**. Its baseline is the pre-T0 engine and T0 already exceeded its result (137 > 127). Re-run on the T0 base; see §1. |
| **T8 non-ATM / 1DTE strikes** | Largest gap is +0.0037R against ±0.1604. Keep 0DTE ATM, on the tiebreak that it has the lowest min-tick-floor rate (6.0%). |
| **T7, T17** | No lever exists. T7's +0.0941R contract-vs-underlying gap is inside ±0.1298 *and* was measured on a 1,016-row book (its base predates T0), so it describes an engine that no longer exists. T17 correctly refused to fabricate a futures backtest. |
| **T12's "prefer the earlier candidate" arm** | The diagnostic is the strongest non-null finding in Group 3 — 51 of 60 engine-proposed entries he says are earlier (p = 3.1e-8), and at one bar the engine **already had the candidate and killed it with an X on 8 of 9 cards**. But the arm itself (prefer the earlier candidate when its Austin-ladder grade is equal or better, 218 rows = 8.4%) has **never been run**. It does not ship on a diagnostic. It is the first arm T23 should measure. |
| **T18's scaling findings** | Report, do not ship — corpus validation never authors a rule. Worth noting the money is already known: T5's `incumbent_nobe` prices removing the breakeven rung at −0.0035 ± 0.0104, i.e. **nothing**. Whichever way he resolves the contradiction, it costs nothing. |

---

## 5. Ratified items still unlanded after this wave

T0 deliberately did not land R7–R11, R19, R24, R28–R31, R33. This wave closed most of them by
measurement, but **R19 is still open and it is load-bearing.** R19 says *"relax candle-shape
grading to bullish/bearish price action"* — T13 answered the research half (no new formation
is corpus-validated; hammer, inverted-hammer/shooting-star and generic wick-rejection were
already coded) but did **not** relax the shared grader. `_grade_pa`'s unconditional
`if not candle.is_bullish: return D` is still there, and it is what makes T3's landed source
fix inert. R19 has no owner. T23 should take it.

Also noted from T13 and worth a future track, not this stack: `A+` trips **7 times in 75,953
signals (0.009%)**, under the 1% reachability floor, while B-grade wick-rejection runs 94.3%
of the traded book. And `live_scanner._tier()` promotes to TRADE only on `A+`. The live path
therefore trades almost nothing this book contains — DIRECTION.md's standing blocker, untouched
by all 21 tracks.

---

## 6. The gate verdict, undressed

- **Money — MISSED, and the wave went backwards on it.** +0.5481R against 2.0. Win rate 43.1%
  against 55%. T0's ratified landing cost −0.2860R against a ±0.1725 bar — real, not null.
  T5 established the ceiling: no exit policy reaches the gate, and a perfect non-causal
  selector on this exit keeps only 51.6% of the book at 2.0R. **The gate cannot be reached
  without discarding at least half the current book.** No exit work should be funded again.
- **Recall — MISSED, but moved for the first time.** 52.9% → 67.6% against a 90% target, on
  one lever (T10 `clean`), +5 S days gained and 0 lost. Every other track in the wave
  returned 18/34 with the same 16 misses card for card.
- **Durability — MET.** 25/25 months green, and it survives every arm in the stack.

One in three. The honest summary of OMEN 7.1 is: **the ratified table made the book bigger,
more durable and worse per trade; 21 tracks then found exactly one lever that moves the
metric the project says governs, and it is a lever whose own author says it is operating on
3.6% of its intended population because a stop-width guard is eating the rest.** The stop
question below is worth more than everything else in this file.

---

## 7. What only Austin can do, most valuable first

Deduplicated across all 21 tracks. Every item is an action, not a question.

1. **Settle where the stop goes.** Four tracks collide here and it caps the best lever in the
   wave. Sit with two charts — `MARA 2026-03-10 09:49` and `PLTR 2026-05-27 10:03`, both
   graded S, on both of which the engine's stop is the *same price as the entry* — plus the
   eleven stop widths in T10 §4, and answer three sentences: (a) does the level stop sit at
   the retested level, or one tolerance unit (25% of the previous candle's range) beyond it;
   (b) does R4's *"no minimum stop distance, size to the stop"* extend from the one-candle
   rule to break-and-retest and to the 84% re-entry, or stay OCR-only; (c) is a stop narrower
   than one typical one-minute candle ever a real order you would place, or is that day a
   skip. R4 and R15 are both yours and they collide on a four-cent stop.
2. **Pick the disaster-stop placement, −1R or −1.25R.** At −1R the resting order's price *is*
   the level stop's price, so a wick now takes you out and `stop_hit_on_close` — the rule you
   have settled five times — becomes unreachable; 1,462 of 1,468 losses exit at exactly the
   stop price. −1.25R keeps the close rule alive, halves the recoverable-trade kill (54
   trades / 242R versus 125 trades / 497R a year) and lifts win rate 42.8% → 46.0%, but costs
   one green month (24/25). Both numbers are yours. One line settles it.
3. **Grade eight side-by-side chart pairs, ten minutes.** QQQ 2026-06-29, META 2025-12-22,
   META 2025-09-18, NVDA 2026-02-05, NVDA 2025-09-29, INTC 2025-06-05, SPCX 2026-06-30,
   IREN 2026-06-03 — on each, the candle the engine took and the candle one bar earlier that
   it already had and threw away with an X. Answer "earlier / later / either" per pair. That
   decides an arm worth 218 traded rows (8.4% of the book).
4. **Answer one question on twelve OCR charts: "is this candle a strong PA entry?"** Six the
   strict detector keeps, six it deletes. The clause does 96% of the filtering, its entire
   content is one threshold on one candle, and that threshold (1.5×) was borrowed from a
   different rule and never put to you. 147 of your own S-graded trades hang on it.
5. **Strike out the levels you would never target.** For a handful of your graded cards,
   every level the engine can see beyond entry — PDH/PDL, premarket high/low, ORH/ORL, HOD/LOD,
   swing pivots, every whole dollar — circle the ones you would aim at. R9's *"if no level then
   default 2r"* fires on 0.00% of trades because the engine always finds nine; you draw five
   or six. Until you prune it, "level first" means "nearest of nine" and it measures as the
   worst exit arm tested.
6. **Say ship or don't on `ARRIVAL_LADDER=s_promote`.** Over two years there were 289 setups
   your own eight variables score S (zero net downgrades) that the engine only ever alerted
   on, never traded, because they were not the first with-trend signal of the day. Saying yes
   moves nothing measurable (mean R +0.0075 inside ±0.0870, recall unchanged, 25/25 green) —
   which is equally a reason to ship a rule you asked for and a reason not to bother. Your
   sentence was *"don't let it cap you of S opportunities."*
7. **Resolve the loss halt against "trade every day".** R31 puts the two-consecutive-loss halt
   in both paths, and it fires on **53% of trading days**, removing 34.8% of the book for a
   mean-R gain inside the error bar. R20 says quality over quantity *but you want to trade
   every day*. Say whether 53% is the rule you meant, or name a different trigger.
8. **Reply "8R" or "5R" for the card-filter dial.** 8R shows you 63 of every 90 candidate
   cards and costs 1 of 18 S-day cards; 5R shows you 53 and costs 3. 8R ships until you say
   otherwise. Separately: `BABA_2025-07-23` is a clean A-grade card the filter drops — if that
   one should have reached you, the threshold loosens rather than the filter coming off.
9. **Resolve the breakeven contradiction in your own corpus.** mastermind-1-0 says *"after
   first scale, can move stop to breakeven, then hold runner"*; the bread-and-butter bonus
   video says *"after my HOD scale, stop loss was still the same"* and *"only move stop when
   structure changes."* Same mentor, two sessions. Answer either way — it is measured at
   −0.0035R ± 0.0104, so it costs nothing whichever you pick.
10. **Buy a small block of ES/NQ 1-minute history** (weeks, not years — Databento or
    equivalent). Polygon has no futures product and `futures_feed.py` never archives. Nothing
    past a code-level check can start on futures or prop firms without it, and the funded-account
    side is already priced and waiting in `g4_prop_fit.md`.
11. **Log into the Tastytrade sandbox once** and confirm one live option quote returns through
    `broker/tastytrade.py`. Every options number in T7, T8 and `t2_options_tape.md` is
    Black-Scholes, never a real bid/ask, because Polygon's options snapshot 403s.
