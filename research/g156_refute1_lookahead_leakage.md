# g156 refuter #1 — S classifier v0 (lookahead / leakage lens) — REFUTED

**What is different now:** the F7 claim's +$13.51/day reproduces to the cent and its predicate
reads no bar past the entry, but the number is 12 day-picks out of 498, half of it is one
Thursday in November, its 95% bootstrap CI straddles zero, an information-free random drop of
the same size clears the same "both halves positive" gate 22.2% of the time — and, decisively,
the shipped `S_CLASSIFIER` gate cannot produce this number at all, because X-grading a row
releases the dedupe suppression window that a fired row would have claimed.

Base `f8740f80`. Everything below: `research/bt2y_trades_retest_on.json`, 498 sessions, entry =
signal bar CLOSE, stops via `stop_rule.stop_fill_price`, size-gated on
`omen_metrics._row_is_sizeable`, 1R = $1,000, one-trade-a-day unit
(`research/omen_metrics.first_of_day_arm`). Script:
`research/g156_refute1_lookahead_leakage.py` → `research/g156_refute1_lookahead_leakage.json`.

## T1 — reproduction: exact

| split | baseline $/day | v0 $/day | Δ $/day | claim |
|---|---:|---:|---:|---:|
| whole book | $33.93 | $47.44 | **+$13.51** | +$13.51 ✓ |
| H1 (< 2025-09-01, 249 d) | $135.71 | $144.27 | +$8.55 | +$8.56 ✓ |
| H2 (≥ 2025-09-01, 249 d) | −$67.85 | −$49.39 | +$18.46 | +$18.46 ✓ |

`python research/g154_rule_or-break-without-retest.py` regenerates its own `.md`/`.json`
byte-identically to the committed copies (`git status` clean afterwards). Precision 30.5%
(18/59) both arms, recall 44.1%/44.1% and 49.0%→48.7%, candidates/day 16.52 — all reproduce.
The arithmetic is not in dispute.

## T0 — my lens: no lookahead in the predicate

`research/downgrade.no_retest` → `_break_bar` (scans `j` in `[i-30, i]`) → `_retest_bar` (scans
`j` in `(break, i]`). Instrumented with an index-recording list wrapper over 6 level/direction
combinations at signal bar `i = 40`: **max bar index read = 40 = i. `reads_past_entry_bar:
false`.** The `no_retest` flag is computable at the signal bar close. Clean. The claim does not
fail on bar-level lookahead.

It fails on the other two leakages.

## Leakage #1 (structural, fatal) — the measured arm is not the shipped flag

The offline arm is a **pure DROP from the arrival stream**: `candidate_arm()` removes matching
rows from `_candidate_stream(rows)` and takes the next survivor. The shipped gate does something
different — `signal_runner.py:2735-2743` sets `sig["grade"] = TradeGrade.X.value`, which falls
through to `self._log_record(sig, status="skipped", skip_reason="X grade (skip)")`.

`backtest_week.py:1400`: `claims = sig.get("status") == "fired" or not DEDUPE_FIRES_ONLY`
(`DEDUPE_FIRES_ONLY` default 1). A skipped row **does not claim or extend the suppression
window**. So under the real flag, every OR-break the classifier kills *releases* the dedupe
window it used to hold, and candidates on the same `(signal_type, direction, level name)` that
the book never recorded become rows. Those rows are not in `bt2y_trades_retest_on.json` at all —
`backtest_week` `continue`s before appending them — so the offline measurement is structurally
blind to them and cannot be corrected after the fact.

This is the same failure CLAUDE.md already prices for `g93`: *"A selection arm cannot model
`backtest_week.DEDUPE_FIRES_ONLY` … capping one to C **releases** it and previously-suppressed
candidates on the same level become rows. Any C-cap gate in this engine adds candidates as well
as removing them."* An X-cap gate does so more strongly, not less. g93 forecast $36/day and
14.2 cand/day; the real book printed $25 and 16.5. **+$13.51/day is a forecast of the same kind,
and it is attached to shipped code as if it were a measurement.** The report's own line
"candidates/day unchanged 16.52" is exactly the quantity the shipped flag would change.

## Leakage #2 (selection) — H2 was a selection criterion, not a held-out half

The report states the selection rule in its own words: *"of the 17 candidates that were never
even formal F5 survivors, only one improves `$/day` in **both halves**."* The candidate was
picked **because** H2 was positive. H2 is therefore in-sample and carries no out-of-sample
weight. Across the F5 corpus, 3 of the 14 candidates that report both deltas already print both
halves positive (`or-break-without-retest`, `scratch-exit-direction-match`,
`stop-placement-routed` — the latter two both refuted in F6), against 25 candidates measured in
total.

## T2 — the effect is 12 days, and half of it is one day

| | |
|---|---:|
| day-picks that change hands | **12 / 498 (2.41%)** |
| total Δ over the book | +$6,729 |
| share from the single best day (2025-11-20) | **50.1%** |
| share from the top 3 days | 55.7% |
| Δ $/day with 2025-11-20 removed | **+$6.75** |
| bootstrap 95% CI on Δ $/day (2,000 day-resamples) | **[−$3.34, +$34.68]** |
| bootstrap P(Δ ≤ 0) | 0.0595 |

The five biggest swaps:

| day | baseline pick | v0 pick | Δ |
|---|---|---|---:|
| 2025-11-20 | META 09:43 −$1,000 | IWM 09:46 +$2,370 | **+$3,370** |
| 2025-06-17 | PLTR 09:44 −$1,000 | AMD 09:46 +$953 | +$1,953 |
| 2025-06-30 | GOOGL 09:44 +$574 | COIN 10:20 −$1,000 | −$1,574 |
| 2024-10-01 | IWM 09:40 −$185 | BABA 09:45 +$910 | +$1,095 |
| 2026-02-27 | IWM 09:40 +$9 | BABA 09:47 +$1,080 | +$1,071 |

H2's headline +$18.46/day is **$13.54/day from 2025-11-20 alone**; the other 248 H2 sessions are
worth +$4.94/day. The "both halves positive" property that selected this candidate rests, on the
H2 side, on one session.

## T3 — placebo: an information-free drop clears the same gate

Matched per-day random drop: on each session, remove the same *number* of sizeable stream rows
the arm removes, chosen uniformly at random, then take the first survivor. 2,000 trials, seed
20260905.

| | |
|---|---:|
| P(placebo Δ ≥ +$13.51/day) | **0.0695** |
| P(placebo H1 > 0 **and** H2 > 0) — the selection gate | **0.2220** |
| P(placebo H1 > 0) | 0.4185 |
| P(placebo H2 > 0) | 0.5275 |
| placebo median Δ | −$1.48/day |
| placebo 95th percentile Δ | +$15.40/day |

Noise with no information about the setup passes the "improves in both halves" test 1 time in
4.5, and beats the claim's own headline 1 time in 14. Applied to 25 candidates, the expected
number of pure-noise "both halves positive" candidates is ≈ 5.6 — the corpus produced 3. The
selection procedure that chose `or-break-without-retest` is producing **fewer** both-half-positive
candidates than chance would.

## Verdict — REFUTED

1. No bar-level lookahead — the one thing the claim gets right on my lens.
2. The shipped `S_CLASSIFIER` gate X-grades rather than drops, releasing dedupe suppression that
   the offline arm assumes is still held; the +$13.51/day therefore describes a book that the
   flag would not produce, and this exact modelling error already cost the project once (g93).
3. H2 was used to select, so "both halves positive" is not validation.
4. 12 of 498 days, 50.1% of the gain in one session, CI [−$3.34, +$34.68] straddling zero, and a
   22.2% null pass rate on the selection gate.

The report's own headline — *"an honest zero: precision flat at 30.5%, recall −0.3pp"* — is the
part that survives. The +$13.51/day sitting beside it does not, and should not travel with the
flag.
