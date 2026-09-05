# R2 referee — REFUTED

**Builder commit: `3ae279a0`** ("R2: reconcile ladder — biggest step swapping the flat exit
for the real scale-out-and-trail exit $4,569 -> -$981/day"), script
`research/g211_reconcile_ladder.py`, report `research/g211_reconcile_ladder.md`.
Referee code: `research/g211_reconcile_ladder.py` is never imported here —
`research/r2_referee.py` recomputes everything from the stamped books with its own
code. Raw output: `research/r2_referee_output.txt`.

Base check: `git merge-base --is-ancestor 1539dd7f HEAD` OK; HEAD = `origin/main` =
`3ae279a0`. Verify gate re-run by me at that commit: `regression_gate.py` PASS,
`test_runner_stop.py` PASS (70 checks), `test_universe_single_source.py` PASS
(29 symbols, no private lists). No mark file appears in `3ae279a0` or `2ccd43f6`.
No engine file touched. One change per row respected.

## Verdict

**REFUTED as a reconciliation ladder. The one claim I was told to refute — the
biggest step — survives and should be kept.**

The row's headline number reproduces exactly and its causal attribution holds up under
an independent paired re-derivation. But three of the nine rungs are not the change
they are labelled, the "reverse ladder" is the forward table printed upside-down, the
second of the two spec-mandated verify assertions is an arithmetic identity that cannot
fail, and four of nine books carry a stamp that names the wrong value for the very flag
that defines them. R3 must not quote steps 5–8 of this report as published.

---

## 1. The biggest-step claim — UPHELD

Re-derived from `reconcile_fwd_1_add_C_grades.json.gz` and
`reconcile_fwd_2_swap_exit_shipped_ladder.json.gz` with my own statistics code.
Unit: every traded signal in the book (`status=="fired"`), $1,000 risk/trade,
$/day = sum(pnl) ÷ unique days in the book. Fill: `next_open` both sides.
Exit: blind 2R → shipped scale-out ladder.

| | trades | win | mean R (95% CI) | avg win | avg loss | green | $/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| step 1 · next_open / blind 2R | 14,327 | 38.6% | +0.1592 ±0.0238 | +1.9835 | −0.9965 | 24/25 | **$4,569.49** |
| step 2 · next_open / shipped ladder | 14,332 | 42.4% | −0.0342 ±0.0217 | +1.0312 | −0.8274 | 7/25 | **−$980.93** |

**Delta = −$5,550.42/day.** The report says −$5,550. Reproduces.

It is the biggest adjacent move in the ladder by a wide margin — every other adjacent
delta is +$1,909, +$14, +$209, −$53, $0, +$234, +$570. The next-largest *drop* is
−$53. And it survives the halves, which the report does not report:

| | H1 (day < 2025-09-01) | H2 (day ≥ 2025-09-01) |
|---|---:|---:|
| step 1 | n=5,766 · $4,082/day | n=8,561 · $5,051/day |
| step 2 | n=5,769 · −$193/day | n=8,563 · −$1,759/day |
| delta | **−$4,276/day** | **−$6,810/day** |

In both halves it is the largest single drop by more than an order of magnitude over
any other negative step. Every cell above clears 30 trades and 12 months.

**And it is genuinely one change.** I paired the two books on
(symbol, day, minute, direction, setup), shifting SIM A's minute by +1 because SIM A
stamps a `next_open` trade with the *signal* bar's minute while SIM B stamps it with
the *fill* bar's minute:

- 13,227 of 13,228 keys matched.
- **Entry price identical on 13,227 of 13,227** — the fill did not move.
- Stop price identical on 13,226 of 13,227 — the risk denominator did not move.
- Per-fill R worse than −1.000R: 1 in step 1, 1 in step 2 — the two rigs' different
  stop machinery (`g90._walk`'s close-only structural stop vs the shipped disaster
  stop) produces no material difference in the downside floor, so the delta really is
  the target/management model and not a smuggled second change.

Paired mean R change: **−0.1972R per trade**, decomposing as:

- trades the flat 2R exit **won** (5,164): +1.9853R → +0.8583R → **−0.4400R/trade**
- trades the flat 2R exit **lost** (8,063): −0.9969R → −0.5987R → **+0.2428R/trade**

So the ladder pays for itself on the loss side and then gives back more than twice as
much on the win side. In plain English, and this is the sentence worth keeping: **the
scale-out ladder cuts the losers roughly in half, but it cuts the winners by more than
half again, and the winners were carrying the book.**

## 2. Step 7 is not a window change — REFUTED

The report labels step 7 `window_500_to_498` and, in plain English for Austin,
"trimming two days off the front and back of the test period". It credits that
trimming with **+$234/day and four extra green months (7/25 → 11/25)**.

That is wrong, and it is wrong in the direction that flatters the book.

Step 7 does not restrict step 6's population to a shorter window. It **throws step 6's
simulation away and substitutes rows lifted wholesale out of
`research/bt2y_trades_retest_on.json`** — a different book, built 2026-09-02 at commit
`a89e90e2`, on a different engine, with `LOSS_HALT` applied. The substitution is visible
in the file itself: steps 0–6 carry this script's row schema
(`entry_time`, `side`=put/call), steps 7–8 carry the foreign book's schema
(`et`, `dir`, `sgrade`, `tripped`, `vol_regime`, `side`='S').

Measured, over the 497 days the two windows share:

- **78.2%** of step 7's trades also exist in step 6's own simulation. 2,028 of step 7's
  trades do not exist in step 6 at all; 6,285 of step 6's do not exist in step 7.
- Concrete: on 2024-09-18 step 6 books ACHR 09:36, AMD 10:33, AMD 10:57, AVGO 10:38;
  step 7 books AMD 10:08, AVGO 09:42, AVGO 10:56, TSM 09:46. Same day, different
  signals.

**The honest window-only number.** Restricting step 6's own book to step 7's window:

| | trades | mean R | green | $/day |
|---|---:|---:|---:|---:|
| step 6 (500 sessions) | 13,374 | −0.0303 | 7/25 | −$811.56 |
| step 6 restricted to step 7's 498-session window | 13,307 | −0.0300 | **7/25** | **−$802.96** |
| step 7 as published | 10,156 | −0.0283 | 11/25 | −$577.85 |

**The window is worth +$8.61/day and zero extra green months.** The report's +$234/day
and +4 green months are 96% substrate swap. This breaks SWARM law 5 ("Never A/B two
books built on different days or bases") and one-change-per-step at the same time, and
step 8 inherits it — the entire core-11 endpoint (−$8/day) is computed on the foreign
book, not on this row's own simulation.

## 3. The second verify assertion is an identity — REFUTED

The spec's verify: *"last row reproduces `research/bt2y_trades_retest_on.json`'s $/day
within 1%."* The intent is to prove the ladder **arrives** at the shipped book by
construction from step 0.

`g211_reconcile_ladder.py:488` builds step 7's population as
`filt_pool(retest_fired_all, full_set)`. I checked: all 28 symbols in
`bt2y_trades_retest_on.json` are inside the 29-symbol full pool, so that filter is the
**identity function**. Step 7's population *is* the retest book's fired rows. The
assertion then compares `sum(pnl)/498` of that set against `sum(pnl)/498` of the same
set. It reports "$-675.25 vs $-675.25 — WITHIN 1%". It could not have reported anything
else. **The ladder's arrival at the shipped book is assumed, not demonstrated.** There
is an unexplained −$811.56 → −$577.85 discontinuity at step 6→7 sitting exactly where
the proof was supposed to be.

The **first** verify assertion is real and I re-ran it independently: step 0's book vs
`research/tape/fillarms_next_open_full29.json.gz`, tuple-for-tuple on
(sym, day, entry_time, entry, r) — **7,857/7,857 identical on full29, 3,629/3,629
identical on core11**. That one passes. (Noting for R3 that R1 itself was refereed
`refuted` at `cb45ffa2`; step 0 faithfully reproduces a refuted row's book.)

## 4. The reverse ladder is the forward ladder relabelled — REFUTED

`g211_reconcile_ladder.py:511`:
`REV = [(8 - n, name, kept, pop, ...) for (n, name, kept, pop, ...) in FWD]`.

Same objects, renumbered. I compared `book_id` fingerprints: **9 of 9 reverse books
hold byte-identical trade sets to their forward twin.** The spec asked for the reverse
order because per-step attribution in a ladder is path-dependent, and applying the same
eight changes in the opposite order from the same start is the only way to see whether
the attribution moves. As delivered the reverse table carries zero information, nine
duplicate `.json.gz` files are committed, and the referee check "do fwd and rev agree
on which step is biggest" is vacuous — they cannot disagree.

**Path-dependence of the biggest-step claim is therefore untested.** The claim survives
on the forward path and on both halves of it; it has not been tested on a second
ordering.

## 5. The stamps misreport the flags that define the books — REFUTED

`write_step_book` calls `book_stamp.stamp()` in the **main** process, which never set
`ENTRY_FILL` or `OMEN_SCALE_PLAN` — the worker processes did.

| book | meta says | stamp says |
|---|---|---|
| fwd_0, fwd_1 | fill `next_open`, exit `blind_2R` | `entry_fill.ENTRY_FILL='close'`, `backtest_week.SCALE_PLAN='hod_then_runner_be'` |
| fwd_2, fwd_3 | fill `next_open` | `entry_fill.ENTRY_FILL='close'` |
| fwd_7, fwd_8 | rows from a 2026-09-02 book at commit `a89e90e2` | commit `2ccd43f6` |

**Not one stamped flag differs between the step-1 and step-2 books** — the stamp cannot
distinguish the two books whose difference is this row's entire headline. The stamp
commit `2ccd43f6` is an ancestor of `3ae279a0` (OK), but every book records
`dirty_py_count: 1` at build time and the report does not disclose the dirty tree.

## 6. Smaller defects

- **Halves absent.** The no-regression gate is defined on H1/H2 and the report has
  neither. Derived above and in `research/r2_referee_output.txt` for every step; every
  per-half cell clears 30 trades and 12 months, so no "not enough" applies.
- **The −$284/day endpoint is never reached or addressed.** The row is titled
  "$569 → −$284". The report explains the *start* drift ($2,660 vs $569) at length and
  says nothing about the *end*: the ladder finishes at −$578/day (full 29) and
  −$8/day (core 11). The spec's second honest rig is still unreconciled.
- **Step 5's size gate is a post-hoc row filter, not the shipped gate.** The formula
  `max(0.10, 0.0015 × entry)` matches `signal_runner.min_risk_floor`'s default exactly,
  but the shipped engine applies it at signal time; here it deletes 1,344 rows the
  engine actually fired. Worth −$53/day, so it does not change any conclusion, but
  "apply the size gate" is not what step 5 does.
- **Step 6 is a declared no-op** — `fwd_5` and `fwd_6` share `book_id 448a93ca7b75`.
  Disclosed in the report, correctly. That is the right handling.
- **Row count off by one.** `fwd_1` holds 14,328 rows; the table prints 14,327 (one row
  has `r: null`). Cosmetic.
- **Plain English:** the report's prose is readable, but the step-7 sentence is plain
  English *and* wrong, which is the worst combination for anything Austin reads.

## What R3 can safely use

1. The step 1 → step 2 finding, with the paired decomposition in §1. Confirmed
   independently, holds on both halves, one variable, 13,227 matched trades.
2. Steps 0–4 as published — own simulation, one variable each, numbers reproduce.
3. **Not** steps 5–8 as attributed, **not** the reverse table, **not** the step-7
   green-month jump, and **not** the claim that the ladder reconciles to the shipped
   book.

Nothing is deleted. The books stay in `research/tape/` as evidence, mislabelled rungs
included, and this page records why steps 5–8 cannot be quoted.
