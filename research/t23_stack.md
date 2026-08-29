# T23 — the stack, re-run, and each lever's marginal contribution

**The money gate is not reached. Mean R is +0.5495 against a target of 2.0, and
the whole stack's move against T0's book is +0.0014R against a ±0.1231R bar — a
null result.** Win rate 43.06% → 49.50% and max drawdown 32.43R → 17.13R are the
two figures that moved materially, and durability holds at 25/25 months green.

Script: `research/t23_stack.py` · data: `research/t23_stack.json`,
`research/t23_heldout.json`, `research/_t23_heldout_noxlift.json` ·
book: `research/bt2y_trades.json` (500 sessions, 2024-08-21 → 2026-08-21, 28 symbols).

Everything below was run on this machine on 2026-08-29. Nothing is quoted from a
track report without being re-run here, and where a re-run disagrees with a
track's published number the re-run is the one printed and the difference is
named.

---

## 0. The rig reproduces T0 exactly

The `t0_base` arm — `X_LIFT=off  MIN_STOP_PCT=0  LOSS_HALT=0` — is the shipped
engine with all three T23 levers switched off. It returns:

| figure | T0 published | t0_base re-run here |
|---|---:|---:|
| signals | 75,953 | **75,953** |
| traded | 2,595 | **2,595** |
| mean R | +0.5481 | **+0.5481** |
| win rate | 43.06% | **43.06%** |
| total R | +1,422.33 | **+1,422.33** |
| max drawdown | 32.43R | **32.43R** |
| months green | 25/25 | **25/25** |

Every number to four decimal places. That matters more than it looks: seven of
the 21 track commits did not descend from T0 and several measured a window ending
2026-08-10 rather than 2026-08-21. This one does not have that problem, and every
arm below shares this exact base, this exact archive and this exact window.

---

## 1. What is in the stack

| lever | switch | ships |
|---|---|---|
| T10 · the targeted X lift | `X_LIFT=clean` | **ON** |
| T9 · the tight-RR floor (R30) | `MIN_STOP_PCT=0.08`, one-candle rule exempt | **ON** |
| T20 · the two-consecutive-loss halt (R31) | `LOSS_HALT=1`, both paths | **ON** |
| T21 · the deck pre-filter | `reach ≤ 8.0R`, fire-half only | **ON** (no book effect) |
| T13 · short-side test coverage | — | **ON** (no behaviour change) |
| T3 · "same stop unless a new stop makes more sense" | `RULE84_STOP_QUALIFIER` | reachable, **OFF** |
| T19 · FVG / flag | `RETIRED_SETUPS` | kept, corpus verdict recorded |

Two reconciliations, both named because they touch a ratified answer:

- **T9 is scoped off the one-candle rule.** R4's verdict is `none` — *"no minimum
  stop distance on OCR, size to the stop."* A book-wide floor would re-litigate
  it. T9's published −0.0462R cost is the **unscoped** number; scoped, the floor
  removes 48 rows before the halt, not 115, because most sub-0.08% stops in this
  book are OCR rows. The scoped cost is measured in §3.
- **T19's deletion was not taken.** T22 recommended deleting the FVG and flag
  detectors. R33's own text is *"**Keep** the retired-setup code, confirm
  FVG/flag against corpus or Scarface"*, and the RATIFIED table outranks an
  adjudication. T19's corpus verdict (neither setup is taught anywhere in the
  corpus) is recorded at the `RETIRED_SETUPS` site instead. Nothing routes either
  way.

---

## 2. Every published figure that moved

`t0_base` → `stack`, one archive, one window, one commit.

| figure | before (T0) | after (stack) | move |
|---|---:|---:|---|
| signals detected | 75,953 | 76,019 | +66 |
| **traded** | 2,595 | **2,437** | −158 |
| **mean R** | +0.5481 | **+0.5495** | **+0.0014 ± 0.1231 — NULL** |
| **win rate** | 43.06% | **49.50%** | **+6.44 pts** |
| total R | +1,422.33 | +1,339.09 | −83.24 |
| profit factor | 1.9732 | 2.1067 | +0.1335 |
| **max drawdown** | 32.43R | **17.13R** | **−15.30R (−47%)** |
| **months green** | 25/25 | **25/25** | unchanged — gate still MET |
| index (ETF) trades | 137 | 164 | +27 |
| break-and-retest | 1,704 | 1,935 | +231 |
| one-candle rule | 572 | 379 | −193 |
| 84% re-entry | 319 | 123 | −196 |
| his ladder: S rows traded | 348 | 298 | −50 |
| his ladder: A rows traded | 570 | 525 | −45 |
| his ladder: C rows traded | 1,677 | 1,614 | −63 |
| held-out S recall (harness) | 18/34 = 52.9% | **23/34 = 67.6%** | **+5 / −0** |
| held-out precision (harness) | 35.3% | 39.7% | +4.4 pts |
| held-out S recall (**traded book**) | 1/34 | 1/34 | **0** — see §4b |
| veto lane: his 5 S | 0/5 | 0/5 | 0 |
| veto lane: his 4 A | 0/4 | 0/4 | 0 |
| veto lane: false fire on his 27 no | 2 (7.4%) | 2 (7.4%) | 0 |

**Read the mean-R row as a null and the win-rate row as real.** They are not in
conflict: the stack removes 158 trades net, and the ones it removes are worse
than average, so the win rate and the drawdown improve while the average trade
does not move outside its own noise.

---

## 3. Marginal contribution inside the stack — nobody had done this here

Each lever gets a leave-one-out arm: the full stack with exactly that one lever
off. The number is what the lever is worth **inside the combination**, which is
not what it was worth alone against T0.

| lever | marginal mean R | its own 95% bar | verdict | solo (vs T0) | sign flip? |
|---|---:|---:|---|---:|---|
| T10 `X_LIFT=clean` | −0.0126 | ±0.1324 | **NULL** | −0.0426 | no |
| T9 `MIN_STOP_PCT=0.08` | −0.0004 | ±0.1184 | **NULL** | −0.0462 | no |
| T20 loss halt | +0.0458 | ±0.1117 | **NULL** | +0.0493 | no |

**No lever's marginal sign flipped against its solo sign.** That was the specific
failure `research/p23_combined_arms.md` recorded (P19 +0.033 alone, +0.007 in a
stack, S recall 5/14 → 1/14) and it did not repeat here. All three marginals are
inside their own bars, so none of them is a money lever, and none of them ever
claimed to be.

What each is actually worth, in figures that are counts rather than estimates:

| lever | traded | win rate | max DD | months green | total R |
|---|---:|---:|---:|---|---:|
| T10 `X_LIFT=clean` | **+496** | **+4.94 pts** | 24.90R → 17.13R | 25/25 → 25/25 | +248.1 |
| T9 `MIN_STOP_PCT` | −28 | −0.19 pts | 15.40R → 17.13R | 25/25 → 25/25 | −16.3 |
| T20 loss halt | **−857** | **+2.74 pts** | 31.17R → 17.13R | 25/25 → 25/25 | **−320.1** |

The sum of the three marginals is +0.0328R; the whole-stack move is +0.0014R. The
**−0.0314R gap is the interaction**, and it is the first time this project has
had a number for one.

### T20's price tag, stated plainly

The halt blocks **857 trades on 245 of 500 trading days (49.0%)**. Those 857
trades would have gone 332 win / 520 loss and booked **+320.1R**. So R31 gives up
19% of the book's realised return to buy +0.0458R of mean (inside its bar) and
+2.74 points of win rate. That is not an argument against it — it is Austin's
ratified answer and it ships at his answer, per method rule 4 — but it collides
head-on with R20, *"quality over quantity, but he wants to trade every day"*, and
only he can resolve that. It is blocker 6 below.

### T9's scoped cost is nearly nothing

Scoped off the one-candle rule, the 0.08% floor fires 48 times (the traded count
moves by 49, the extra one being knock-on) and the book ends 28 trades lighter, worth −0.0004R. T9's published −0.0462R was the unscoped,
book-wide version, which R4 forbids. **The scoped answer to T22's open question
is: the floor is close to free, and it costs zero held-out S recall.**

### T20 was implemented causally, and that is a change from how it was measured

`research/t20_loss_halt_postprocess.py` sorted a day's rows by ENTRY time and
advanced the loss counter with each row's eventual outcome — one bar of
look-ahead, because at the moment you would place trade #3 you do not yet know
trade #2 is going to lose. `loss_halt.py` advances the counter on the **exit**, so
a candidate entry is blocked only by losses that had already closed. The two
readings do not have to agree: T20 published 902 trades removed on 53% of days;
the causal rule removes 857 on 49.0%. Asserted by
`research/test_t23_loss_halt.py`.

---

## 4. Held-out recall, scored two ways

**Method rule 2 says recall governs.** It is scored twice on purpose, and the two
answers are very far apart.

### 4a. The harness — the number this project publishes

`research/t0_heldout_recall.py`, replaying each marked symbol-day through
`research/t4_engine_recall.run_day`:

| | X_LIFT=off | stack | move |
|---|---:|---:|---|
| S recall, `probe_s_sweep_2026-08-28` | 18/34 = 52.9% | **23/34 = 67.6%** | **+5 / −0** |
| precision on the same 100 cards | 35.3% | **39.7%** | +4.4 pts |
| false fire on his 66 refused days | 33 | 35 | +2 |
| unreplayable days | 0 | 0 | — |

The five S days gained are **ACHR 2026-02-05, ARM 2024-10-28, HOOD 2024-11-06,
PLTR 2025-07-01, QQQ 2025-09-23** — card for card the five T10 named, now
reproduced on the full 2024-08-21 → 2026-08-21 archive rather than T10's
truncated one. Zero S days were lost. Exact one-sided McNemar on (5, 0) is
p = 0.031.

Veto lane, `probe_master_2026-08-29`: **0 of his 5 S, 0 of his 4 A, 1 of his 4 C,
and 2 false fires on his 27 explicit "no" (7.4%)** — identical to T0. The lift
does not reach the vetoed pool, for the reason T10 found and this run does not
change: 10 of his 13 graded vetoes die on `_min_viable_stop` at a median stop of
0.034% of price.

### 4b. The traded book — and this is the finding

The same 34 cards, asked of `research/bt2y_trades.json` instead of the harness:

| step | S cards (34) | refused cards (66) |
|---|---:|---:|
| symbol is in the traded universe at all | 27 | 59 |
| the engine produced any signal that day | 25 | 44 |
| at least one signal cleared `_route` | **2** | 14 |
| a trade survived into the book | **1** | 11 |

**In the two-year book the engine trades 1 of the 34 days Austin graded S, and 11
of the 66 days he refused.** On his S days, 152 of the 159 signals it produced
grade `X`.

The gap to the harness has two causes and both are checkable:

1. **Five of the 23 harness hits are on ARM, MSTR and SMCI — symbols the book
   never trades.** They are outside `universe.py`'s backtested set. The harness
   replays any symbol with an archive.
2. **Of the 18 harness hits that ARE in the traded universe, the book fires on 2
   and trades 1.** `research/t4_engine_recall.CaptureRunner._route` is a
   hand-rolled copy of the base router that never calls `super()`.
   `backtest_week.BacktestRunner` had the identical bug; it was fixed in omen-5.0
   on 2026-08-12 with the comment *"every gate the base grew after it was written
   was therefore INERT in every backtest ever run."* **The recall harness was
   never given the same fix.** Every gate the base has grown since — the
   session-extreme veto, no-repeat, level retirement, and as of today
   `MIN_STOP_PCT` — is inert in the one rig that scores the governing metric.

This is the seventh instance of this bug class in this repo and the most
expensive one, because it sits under the number the whole project steers by. It
does **not** invalidate the +5/−0 move: both arms were scored on the same harness
and the comparison is internally valid. It does mean **67.6% is a statement about
`CaptureRunner`, not about the book Austin would trade.** Fixing it is the first
item T24 should take, and it is not a tuning job — it is deleting an override.

---

## 5. Reachability (method rule 3)

| gate | trip rate | verdict |
|---|---:|---|
| `X_LIFT=clean` condition true | 20,333 of 70,319 X rows = 28.9% (T10, and its 70,319 denominator reproduces here exactly) | inside 1–85%, a real threshold |
| `X_LIFT=clean` actually lifts a row | 745 of 76,019 signals | 745 rows carry `[x-lift:clean]` in the shipped book |
| `MIN_STOP_PCT` skips (scoped) | 48 of 3,343 accepted = 1.4% | just inside the 1% floor |
| loss halt blocks | 857 of 3,294 traded = 26.0%, on 49.0% of days | inside the band |
| loss halt, as a share of DAYS | 245 of 500 = 49.0% | inside the band, and it collides with R20 |

None of the three shipped levers is a finding about its own gate.

---

## 6. What did NOT run, and why

1. **No leave-one-out for T21, T13 or T19.** None of them touches the book by
   construction: T21 filters decks, T13 is test coverage, T19 changed no
   behaviour. There is nothing to A/B.
2. **`RULE84_STOP_QUALIFIER` was not measured alone.** It ships OFF for exactly
   that reason. Every number in `research/t3_rule84-from-source.md` is the
   four-clause `RULE84_SOURCE` composite; the qualifier by itself has never had an
   arm. Turning it on by default without one would be the thing this repo keeps
   getting burned by.
3. **No options, contracts, spreads or futures.** Every R here is the underlying.
   T7 and T8's contract numbers are Black-Scholes on prior-session sigma, never a
   quoted bid/ask, and nothing in this stack changes that.
4. **The live path was wired but not run.** `live_scanner._tier()` now consults an
   account-wide loss streak, and `research/test_t23_loss_halt.py` asserts the
   wiring, but no live session has executed it. Separately and unchanged by this
   stack: `_tier` still promotes to TRADE only on `A+`, which fires 7 times in
   76,019 signals (0.009%). **The live path still does not trade this book.**
5. **The four arm books (~67 MB each) are not committed.** `research/t23_stack.py`
   carries the exact environment for each arm in its `ARMS` table; each
   regenerates with one command in roughly twenty minutes. Every number read off
   them is in `research/t23_stack.json`, which is committed.
6. **No re-measurement of T5's exit family, T6's faster cuts, T8's strikes or
   T11's break-even on the new book.** Their nulls were computed on T0's
   selection; the stack changes the selection, so they are refutations of their
   families rather than numbers that automatically survive. T22 flagged this and
   it is still true.
7. **`ARRIVAL_LADDER=s_promote` was not shipped or measured here.** It is not a
   measurement decision — every axis is a wash — it is Austin's sentence. Blocker
   5 below.

---

## 7. What is still blocking the money gate, ranked

1. **Selection, and it is arithmetic.** T5 established the ceiling honestly: with
   the shipped exit, a **perfect non-causal selector reaches mean 2.0R on only
   51.6% of the book**. No causal selector beats a perfect one, so the gate cannot
   be reached without discarding at least half the current book. The stack
   discarded 6% and moved mean R by +0.0014.
2. **The stop-width guard caps the only lever that moved recall.** 96.4% of what
   `X_LIFT=clean` promotes dies on `_min_viable_stop`, and 10 of Austin's 13
   graded vetoes die there too, at a median stop of 0.034% of price. The measured
   +14.7 points of harness recall is what the lever achieves on 3.6% of its
   intended population. One answer from Austin moves T10, T9, T3 and T12 at once.
3. **The recall metric is measured on the wrong router** (§4b). Until
   `CaptureRunner` delegates, "67.6%" and "the book trades 1 of his 34 S days" are
   both true and only one of them is about the system.
4. **The live path does not trade this book.** `A+` fires 0.009% of the time. This
   outranks every gate for real money and all 22 tracks left it untouched.
5. **No exit work is left to fund.** 47 causal arms, zero beat the shipped exit
   outside its bar, 29 clear their bar and every one moves down.

---

## 8. Gate verdict

| gate | target | stack | verdict |
|---|---|---|---|
| **Money** | mean R ≥ 2.0, ≥55% win | **+0.5495, 49.50%** | **MISSED** — needs +1.4505R |
| **Recall** | fires on ≥90% of his unseen S days | **67.6%** harness / **1 of 34** book | **MISSED** |
| **Durability** | every month green | **25/25** | **MET** |

`python research/regression_gate.py` — **PASS**: any_signal 75 → 83, s_grade
5 → 13, no baseline-fired mark went silent.
