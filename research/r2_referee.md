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

---

# R2 referee — PASS 2 — REFUTED (kept)

**Builder commit under review: `15a729ce`** ("R2 repair: fix step-7/8 substrate swap, drop
fake reverse ladder, fix stamp bug, add H1/H2 split — biggest step unchanged
($4,569 -> -$981/day)"), repairing `3ae279a0` after pass 1 (`b746e45e`, above).
Script `research/g211_reconcile_ladder.py`, report `research/g211_reconcile_ladder.md`.

Referee code: `research/r2_referee_pass2.py` (pass 1's `research/r2_referee.py` is
untouched). Raw output: `research/r2_referee_pass2_output.txt`. New stamped book:
`research/tape/r2ref_simd_next_open_blind2r_real_engine.json.gz`.

Base check: `git merge-base --is-ancestor 1539dd7f HEAD` OK; HEAD = `origin/main` =
`15a729ce`; HEAD is an ancestor of `origin/main`. Verify gate re-run by me at that
commit — `regression_gate.py` PASS, `test_runner_stop.py` PASS (70 checks),
`test_universe_single_source.py` PASS (29 symbols, 25 backtested, no private lists),
exit 0. `git show --stat 15a729ce` touches no mark corpus and no engine file; one
change per row respected.

## Verdict

**REFUTED. The repair fixed steps 7 and 8, the reverse ladder and the stamp block, and
every one of those fixes reproduces under my own code. But the row's headline — the one
sentence the spec asks for and the one Austin would read — is still wrong, and the H1/H2
table added to defend it publishes a different step's numbers.**

Plain English, one line: *the row says the scale-out-and-trail exit is what costs the
money; four fifths of that cost is actually the difference between the old measuring
rig and the real engine, and only one fifth is the exit.*

Every book stays. The measured ladder rungs 0–8 are sound as arithmetic and reproduce to
the cent; it is the causal label on the biggest rung that does not survive.

---

## 1. What the repair fixed — CONFIRMED

Re-derived off the committed books with my own statistics code (`stats()` in
`research/r2_referee_pass2.py`; nothing imported from the builder's script). Unit for
every row: every traded signal in the book (`status=="fired"`), $1,000 risk/trade,
$/day = sum(pnl) ÷ distinct trading days in the population, script
`research/g211_reconcile_ladder.py`. Fill and exit named per row in the report's table.

| step | fill | exit | pool | trades | mean R (95% CI) | green | $/day (mine) | report |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 0 | next_open | blind 2R | full29 | 7,857 | +0.1690 ±0.0322 | 23/25 | $2,660.29 | $2,660 |
| 1 | next_open | blind 2R | full29 | 14,327 | +0.1592 ±0.0238 | 24/25 | $4,569.49 | $4,569 |
| 2 | next_open | shipped ladder | full29 | 14,332 | −0.0342 ±0.0217 | 7/25 | −$980.93 | −$981 |
| 3 | next_open | shipped ladder | full29 | 14,731 | −0.0328 ±0.0216 | 7/25 | −$966.93 | −$967 |
| 4 | close | shipped ladder | full29 | 14,718 | −0.0257 ±0.0207 | 7/25 | −$758.42 | −$758 |
| 5 | close | shipped ladder | full29 | 13,374 | −0.0303 ±0.0218 | 7/25 | −$811.56 | −$812 |
| 6 | close | shipped ladder | full29 | 13,374 | −0.0303 ±0.0218 | 7/25 | −$811.56 | −$812 |
| 7 | close | shipped ladder | full29 | 13,307 | −0.0300 ±0.0219 | 7/25 | −$802.96 | −$803 |
| 8 | close | shipped ladder | core11 | 5,788 | −0.0075 ±0.0327 | 12/25 | −$87.65 | −$87 |

Every cell reproduces. Specifically fixed since pass 1:

- **Step 7 is now a real window filter.** No row of `research/bt2y_trades_retest_on.json`
  survives in it; it is step 4's own SIM C population restricted to that book's dates.
  Worth **+$8.60/day and zero extra green months** (7/25 → 7/25) — which is pass 1's
  independently computed honest figure (+$8.61) to the cent, and not the fabricated
  +$234/day and 7/25 → 11/25 of `3ae279a0`. Step 8 now derives from it.
- **Reverse ladder removed**, the 9 duplicate `.json.gz` deleted, and path-dependence
  declared **untested** rather than answered. Correct handling of a check that cannot be
  run inside one change. Because the reverse table no longer exists, the referee check
  "do fwd and rev agree on which step is biggest" has no answer — the report says so.
- **Stamp block now discriminates.** Diffing `fwd_1` against `fwd_2` key by key, exactly
  **one** flag differs: `backtest_week.SCALE_PLAN: None -> 'hod_then_runner_be'`. Before
  the repair not a single flag differed. Stamp commit on all nine books is `b746e45e`,
  an ancestor of `15a729ce` — allowed. `dirty_py_count: 1`, `dirty_engine_py: []`,
  disclosed in the report.
- **Verify assertion 1 re-run by me independently**: step 0 vs
  `research/tape/fillarms_next_open_full29.json.gz`, tuple-for-tuple on
  (sym, day, entry_time, entry, r) — **7,857/7,857 on full29, 3,629/3,629 on core11**.
  MATCH.
- **Disclosures added and accurate**: the dirty tree, the title-vs-endpoint gap
  (−$803/day full29, −$87/day core11, neither is −$284/day), and the 14,327-vs-14,328
  row count (one candidate row with a null `r`) — I confirmed all three.

## 2. DEFECT — the biggest step is still two changes, and the label names the smaller one

This is the row's whole deliverable and it does not hold.

`fwd_1` was **not** produced by the shipped engine on a flat target. Its rows come from
`g90_fill_arms._walk` (`research/g90_fill_arms.py`): a stop that triggers only on a
**close** beyond the level and then fills **at the level**, no disaster stop, no
`stop_rule.stop_fill_price()`, and a scratch at the last close. `fwd_2`'s rows come from
`backtest_week.simulate_day`. Step 1 → step 2 therefore swaps the exit ladder **and the
entire trade-management substrate** in one move.

**SIM D** holds the substrate at step 2's value and the exit at step 1's: the real
`backtest_week.simulate_day`, `ENTRY_FILL=next_open`, `OMEN_SCALE_PLAN=none`
(backtest_week's own blind-2R target, its line ~1447), same window `2024-09-04`→
`2026-09-04`, same 29 symbols, 84% re-entries excluded, every grade. It lands on
**14,332 rows — the same count as `fwd_2`** — so SIM D → `fwd_2` is a single-flag
comparison (`SCALE_PLAN`), which is what the step claimed to be all along.

Unit for all three rows: every traded signal, $1,000 risk/trade, next_open fill,
25 months, script `research/r2_referee_pass2.py`.

| | trades | win | mean R (95% CI) | avg win | avg loss | green | $/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| `fwd_1` — g90 `_walk` arm, blind 2R | 14,327 | 38.6% | +0.1592 ±0.0238 | +1.9835 | −0.9965 | 24/25 | **$4,569.49** |
| **SIM D** — real engine, blind 2R | 14,332 | 33.4% | +0.0052 ±0.0231 | +1.9837 | −0.9973 | 12/25 | **$149.80** |
| `fwd_2` — real engine, shipped ladder | 14,332 | 42.4% | −0.0342 ±0.0217 | +1.0312 | −0.8274 | 7/25 | **−$980.93** |

- **substrate leg (`fwd_1` → SIM D): −$4,419.69/day — 79.6% of the step.**
- **ladder leg (SIM D → `fwd_2`): −$1,130.73/day — 20.4% of the step.**

Both legs hold in both halves (midpoint 2025-09-03, 13 months and ≥5,794 trades each
side): SIM D reads H1 $775.11, H2 −$473.02, so the ladder leg is −$994.18/day in H1 and
−$1,266.73/day in H2, and the substrate leg is −$3,286.90/day in H1 and −$5,547.95/day
in H2.

Note the mechanism, because it is the diagnosis: avg win (+1.9835 vs +1.9837) and avg
loss (−0.9965 vs −0.9973) are **identical** between `fwd_1` and SIM D — the two rigs
agree on what a win and a loss pay. What moves is the **win rate, 38.6% → 33.4%**: the
real engine's intrabar disaster stop and pessimistic same-bar handling convert about one
trade in twenty from a 2R win into a −1R loss. Pass 1 checked the downside **floor** and
correctly found it unchanged, then concluded the delta "really is the target/management
model"; the floor was the wrong statistic — the outcome **mix** is where the substrate
lives.

Consequence for the report: the sentence under "The step that costs the most money" —
*"switching from a flat double-your-money exit to the real scale-out-and-trail exit …
a swing of $-5,550/day"* — over-attributes the exit by **4.9×**. The salvageable,
single-variable finding for R3 is: **the shipped scale-out-and-trail exit costs
$1,131/day against a flat 2R target on the same 14,332 trades, same next_open fill,
same engine, both halves negative** (`research/r2_referee_pass2.py`).

## 3. DEFECT — the repaired H1/H2 table is a different step's numbers

The report prints, for the biggest step, before = H1 **$-85** / H2 **$-1,518**, after =
H1 −$219 / H2 −$1,740, and concludes "the drop holds in both halves". The halves
computed from the two books themselves:

| step | H1 $/day | H2 $/day |
|---|---:|---:|
| step 1 (the real "before") | **$4,062.01** (n=5,794, 13mo) | **$5,074.93** (n=8,533, 13mo) |
| step 2 (the "after") | −$219.07 (n=5,797, 13mo) | −$1,739.75 (n=8,535, 13mo) |
| step 7 | **−$85.43** (n=5,341, 12mo) | **−$1,517.59** (n=7,966, 13mo) |

The published "before" column is **step 7's**. Cause, in
`research/g211_reconcile_ladder.py`:

```
for (n0, name0, dd0), (n1, name1, dd1) in zip(fwd_dd, fwd_dd[1:]):
    ...
    biggest = (delta, n1, name1, dd0, dd1)      # n0 is NOT captured
delta, n1, name1, dd0, dd1 = biggest            # n1 -> 2
...
kept0, pop0 = by_n[n0]                          # n0 leaks from the loop == 7
```

`n0` is the loop variable left over from the final iteration (the 7→8 pair), so the
"before" halves are read out of step 7's book. The H1 figure is wrong by a factor of 32
($-85 published vs $4,062 actual). The *direction* of the conclusion survives — the drop
is larger in both halves than advertised — but the numbers printed under it are not the
numbers they are labelled, and this table was the specific repair pass 1 asked for.
Pass 1 had already published the correct halves ($4,082 / $5,051 on a fixed 2025-09-01
split); the repair replaced them with the wrong step's.

## 4. DEFECT — "add C grades" is a row filter where re-simulation was required

The referee brief asks whether a filtered step could have needed re-simulation.
It could, and here it does. `backtest_week.py` ~line 1400:

```
claims = sig.get("status") == "fired" or not DEDUPE_FIRES_ONLY
```

The suppression claim is **grade-blind** — a C-grade fire opens and extends the window
that hides the next candidate on the same idea. `DEDUPE_MODE='level'` so the window is
`DEDUPE_CONTIG = 2` bars. Steps 0 and 1 differ only by a post-hoc `grade != "C"` row
filter, which cannot release anything the C fires suppressed.

Quantified: I captured every candidate's (bar index, dedupe key, status, grade) during
SIM D and replayed `simulate_day`'s dedupe loop offline both ways
(`dedupe_replay()` in `research/r2_referee_pass2.py`):

- C fires claiming, as simulated: 14,826 survivors, of which **8,266 non-C**.
- C fires gated off, as a real no-C engine run: 8,648 survivors, all non-C.
- **382 additional non-C signals (+4.6%) fire in a genuine C-gated run** and appear in
  no book this row wrote.

So step 0 → step 1's **+$1,909/day** is the value of *deleting rows*, not the engine's
answer to "run without C grades". It is the smaller of the two undisclosed
filter-vs-simulate problems (the report's "Filtered, not simulated" section names the
grade filter but not this consequence, which CLAUDE.md warns about by name), and 4.6% is
unlikely to flip the sign — but the step is mislabelled the same way step 7 was in
`3ae279a0`.

## 5. Verify assertion 2 — still fails, and its explanation is asserted, not measured

Re-run independently: step 7's unsized population (step 4's SIM C rows inside
`research/bt2y_trades_retest_on.json`'s window) = **−$750.17/day** over 14,647 rows
vs that book's own **−$675.25/day** (sum of pnl over fired rows ÷ 498 sessions) —
**11.1% apart, DOES NOT RECONCILE within 1%.** My numbers match the builder's exactly,
and the check is now genuine rather than the identity `3ae279a0` ran; the spec's
fallback ("say which step will not reconcile and why") is satisfied in form.

The report's *why* — `LOSS_HALT` — is mechanically real: `loss_halt.apply_to_book` is
called only from `backtest_2y.py:284`, never from `simulate_day`, so this row's
simulations genuinely never apply it, and `retest_on`'s own meta records 4,205 halted
against ~15,000 fired, i.e. the halt removed ~28% of its fired rows and its book reads
the less negative of the two — the right direction. But the two books also differ by
commit and engine, so "any residual gap is that halt" is an unmeasured attribution, and
I could not close it without a fourth run. Treat the endpoint as unreconciled.

Related stamp-fidelity note: the reconcile books stamp `loss_halt.LOSS_HALT: true`,
`backtest_week.DISASTER_STOP: true`, `STOP_ON_CLOSE: true`, `PESSIMISTIC_FILL: true` —
none of which ran on `fwd_0`/`fwd_1`'s rows or in this script at all. The stamp records
what the modules held, not what the book's own code path used. That is precisely the
blind spot that let defect §2 pass two reviews.

## 6. Sample sizes — all above the floor

Every published step: 5,788–14,731 trades over 25 months. Every half: 5,341–8,535 trades
over 12–13 months. No cell in the report is under 30 trades or 12 months, so the report's
"not enough" annotation correctly never fires. Every mean-R difference I report above is
larger than its own 95% interval (the largest interval on any row is ±0.0327R, and the
substrate and ladder legs move −0.1540R and −0.0394R per trade respectively — the ladder
leg is the only one close to its interval, so read the ladder leg as "about −$1,100/day,
not precisely −$1,131").

## 7. Standard checks

- **Dollar figures name fill / exit / unit / script** — yes in the repaired report, and
  in every table above.
- **Books stamped** — nine reconcile books, all with commit `b746e45e` (ancestor of
  `15a729ce`), all flags, date, window, script. Tree dirty (1 non-engine .py) at build
  time and the report says so.
- **One change per row** — `git show --stat 15a729ce`: the row's script, its report, nine
  updated books, nine deleted reverse books. No engine file.
- **No mark file touched** — none in `git show --stat 15a729ce`; working tree clean of
  tracked modifications when I ran the gate.
- **Verify gate green at `15a729ce`** — run by me, exit 0.
- **Plain English** — the report's prose reads well; the "step that costs the most money"
  sentence is plain English and wrong, which is the failure mode pass 1 flagged on step 7
  and which has now moved to the headline.

## What R3 can and cannot use

1. **Use**: steps 0, 3, 4, 5, 6, 7, 8 as arithmetic, and step 7's honest +$8.60/day.
2. **Use**: the ladder's own price — **−$1,131/day, 14,332 trades, one flag
   (`SCALE_PLAN`), both halves negative**, book
   `research/tape/r2ref_simd_next_open_blind2r_real_engine.json.gz`.
3. **Do not use**: "the exit ladder costs $5,550/day"; the H1/H2 table under it; the
   +$1,909/day for adding C grades as an engine result; or any claim that the ladder
   reconciles to the shipped book.
4. **Still open**: path-dependence of the ladder (needs the fourth simulation the row
   correctly declined to run), and the residual 11.1% to `bt2y_trades_retest_on.json`.

Nothing is deleted. Every book from `15a729ce` stays in `research/tape/`, and SIM D is
added beside them as the control that was missing.
