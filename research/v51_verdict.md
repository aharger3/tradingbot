# omen-5.1 verdict

*Synthesised from six research artifacts, 2026-08-13.*

---

## 1. The honest EV

The old headline — **+0.914R** per trade — was the most optimistic corner of the table: in-sample, optimistically filled, uncapped runner. The honest cell strips all three assumptions at once: pessimistic fill, 2R cap, out-of-sample quarter only. The result is **+0.370R** (95% CI [+0.223, +0.517], 319 trades, 53.9% win rate). The confidence interval sits entirely above zero. **The edge survived its own worst case.**

The full eight-cell table and the per-assumption breakdown are in `research/t51_ev_honest.md`. Two asterisks apply: the OOS quarter is not a true holdout (the rules were written while these days existed), and the archive is missing the final month for 12 symbols. Both push the truth *higher*, not lower — the fuller book scores the same cell at +0.422R. So 0.370R is a floor, not a point estimate.

## 2. What the fill fix cost

**Zero trades flipped.** Across 1017 traded trades, win rate is 55.0% and EV is +0.873R in both the optimistic and pessimistic fill arms. The reason (from `research/t51_fill.md`) is that the tie was already resolved as a loss before the flag existed: the stop is tested before every profit rung in both exit paths, so a bar that touched a target and closed beyond the stop was already booking the loss. The pessimistic rule moved 26 fills in the full simulated book, but none of them were on a traded signal.

Against Austin's 55% gate: the pessimistic win rate is **55.0%** — sitting right on the gate, not above it. The backtest win rate has never cleared 55% under honest assumptions. Every cell in the honest-EV table (optimistic or pessimistic, capped or uncapped, in-sample or out-of-sample) reports a win rate between 53.9% and 55.4%. The 55% gate is not a safety margin the engine clears; it is the ceiling.

## 3. The new S rate and precision

The S-bar analysis in `research/t51_s_bar.md` reports **0.23 S-signal fires per day** at **21.43% precision**. Against Austin's expectation of **1–3 S bars per day**, the engine is firing at roughly 10–20% of the lower bound. The precision means roughly one in five S-signal fires is a real S-level bar by the manual daily-check definition.

The earlier memory note from T6 identified 3.5 single S bars/day in raw bar-level detection — but those are *candidates*, not what the engine fires on. The gap between raw S-bar detection (~3.5/day) and fired S signals (0.23/day) is where the grading and routing gates sit. The engine sees plausible S structure most days; it just doesn't route those as S trades.

## 4. Why the index pool is silent

The diagnosis in `research/t51_index_funnel.md` is definitive: **Detection is not the problem.** Levels form on 100% of index cells and a break-and-retest or order-block setup forms on 96.7% (1451/1500). The killer is the `_SKIP_GRADES` D-grade gate, taking 1419 of those 1451 signal-days (97.8%). The dominant mechanism is the **price-scaled tight-stop D-rule**: a setup whose entry-to-stop distance is under 0.15% of price is skipped. For high-priced indices (QQQ $568, SPY $637), that threshold is 85–96 cents — and index-level retests are tighter than that on most bars. TSLA clears it three times as often because it's cheaper and wider-ranging.

The fix is **gate tuning, not new level geometry**. `loss_is_upstream_of_gates: no`. The existing level-detection code finds index structure fine; the grading rules just bench it. This is grading/stop-distance work — doable within the current build, not forced into a 5.2 architecture.

## 5. The eye-match baseline

The engine was replayed against 475 of Austin's manual marks (362 unique symbol/day pairs) from `austin_marks_v7.jsonl`. Results from `research/t51_eye_match.md`:

- **Exact agreement: 2.32%** (11/475) — the engine's tier matches Austin's grade exactly.
- **Cohen's kappa: 0.0106** — effectively random agreement vs chance.
- **S recall: 3/139** — of Austin's 139 S marks, the engine called only 3 S within ±2 bars.
- **Under-grade rate: 28.63%** — Austin says S, engine says C/X/no-fire.
- **Over-grade rate: 0.42%** — engine says S, Austin says C/X.

This is the baseline that the graded day decks will be scored against. Any future change to the grading pipeline can be measured against this agreement matrix.

## 6. What 5.1 changed vs 5.0

The head-to-head comparison in `research/t51_vs_t50.md` ran both builds over the same 500-day, 29-symbol window. The two arms join perfectly trade-for-trade:

- **added:** 0
- **dropped:** 0
- **regraded:** 301 (56 S+→S from the deleted S+ rank, 245 C→A from the loosened displacement clause)
- **re-outcomed:** 0

The P&L delta is **$0**. Both arms book the same 1017 trades at the same outcomes (+0.873R, 55.0% win rate). The only change was classification: the S+ rank was deleted and the displacement clause was softened, so 301 trades got new tier labels. The fill rule (pessimistic mode) also moved nothing because the stop already won the tie. omen-5.1 was a classification change, not a selection change.

## 7. What Austin has to do next

**Grade the two day decks.** The index deck (`research/omen-5.1-index-day-deck.html`) has 60 cards (30 QQQ days, 30 SPY days). The TSLA deck (`research/omen-5.1-tsla-day-deck.html`) has 60 cards. Mark each card as S/A/C/X/no-trade by your eye. The graded results will be the ground-truth comparison for the eye-match baseline above — raising it from 2.32% exact agreement to a number you can trust.

---

```
verdict_ev_r: 0.370
verdict_win_rate: 53.9
verdict_s_per_day: 0.23
verdict_edge_survives: yes
verdict_next_action: Grade research/omen-5.1-index-day-deck.html (60 cards) and research/omen-5.1-tsla-day-deck.html (60 cards) — mark each day as S/A/C/X/no-trade by eye.
```