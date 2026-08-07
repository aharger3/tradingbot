# omen-3.6 verdict

Written 2026-08-07 from the six files T1-T6 produced. **No number here was recomputed** — every
figure is quoted from `research/austin_marks_v2.md`, `research/bar_coverage.md`,
`research/mark_features.md`, `research/engine_recall.md`, `research/s_gate_spec.md`.

**T7 was not run and will not be.** The 3.6 run (GitHub Actions `31122686346`) was cancelled at
1h28m partway through T7; PR #9 carried T1-T6 and was merged 2026-08-07. T7 was a ~90-minute
12-month A/B of a gate whose own pre-registered keep-rate gap is +12.5pp with a 95% CI of
[-20.7, +45.5]. Running it produces a number no decision can rest on. The rows below answer the
version's question without it.

---

## 1. Did the gate move the backtest?

Not measured, and deliberately so — see above. What *is* measured is that the gate could not have
mattered much: it filters the trades the engine already takes, and those trades overlap Austin's
S marks at **4 of 77**.

The gate itself, from `research/s_gate_spec.md`:

- Predicate: `displacement >= 0.888`
- S kept 62.5% (30/48), X kept 50.0% (6/12), A kept 53.3% (21/45)
- S − X = **+12.5pp, CI [-20.7, +45.5]**; S − A = **+9.2pp, CI [-11.5, +29.2]**

Both intervals span zero by a wide margin. The floor (4pp / d=0.15) is cleared only by the point
estimate.

## 2. Is that number trustworthy?

No. `research/s_gate_spec.md` ranks 16 features on two contrasts — 32 tests. **Every single
BH-FDR-adjusted p is ≈ 1.0** on S-vs-X, and the best on S-vs-A is `entry_i` at 0.0586. The
minimum detectable effect at these arms is **45.2pp (S-vs-X) and 29.1pp (S-vs-A)** for booleans,
0.90d and 0.58d for continuous features. Nothing short of an enormous effect could have been
detected, and nothing was.

Six of sixteen features **reverse sign between the two contrasts** — including
`is_break_and_retest`, `new_session_high`, and `is_84_reentry_opportunity`. A feature that points
one way against X and the other way against A is not measuring setup quality.

**Read this as: at n=105 usable marks, no feature in the current vector distinguishes Austin's S
from his A or his X.** That is a statement about sample size and feature vocabulary, not proof
that his eye is arbitrary.

## 3. Does the engine find Austin's S setups at all?

**No. This is the finding of the version.**

From `research/engine_recall.md`:

| measure | S | A | X |
|---|---|---|---|
| **fired** entries within ±2 bars | **4/77 (5%)** | 3/60 | 1/22 |
| any signal, any grade, deduped | 18/77 | 15/60 | 4/22 |
| any signal, raw upper bound | **19/77 (25%)** | 17/60 | 6/22 |

The engine emits **no signal of any grade at roughly 75% of the bars Austin marks S.** Of the 516
raw signals it does produce on marked days, 442 are graded D and 58 fire.

Precision: 33 engine entries on marked days, **10 land on a marked bar** (30.3%); 23 are entries
Austin did not mark at all.

So the answer to "picking better among the trades it takes, or finding trades it currently
misses?" is unambiguous: **finding trades it misses.** A filter cannot recover a setup that was
never detected. Every gate-shaped version after this one is premature until recall moves.

## 4. Are we closer to an edge?

No movement. The baseline stands at **+0.146R / 38.0% WR over 1,289 trades**
(`backtest_metrics_full.json`), against a 33.333% breakeven — **+4.67 WR points, CI spanning
zero** per the standing economics note. 3.6 changed no shipped behaviour: `S_GATE` is a module
global in `signal_runner.py` defaulting to **False**, so live grading is byte-identical to before.

What 3.6 *did* buy is worth more than a null A/B: a reusable feature pipeline
(`research/mark_features.py`), a recall harness (`research/t4_engine_recall.py`), and the 5%
number that redirects the whole project.

## 5. The one change to make next

**Instrument the miss, then widen detection.** For each S mark, record which stage of
`SignalRunner.detect_signals` failed to produce a signal:

- the `_is_consolidation` early-return (all four key levels within 0.5% → the whole bar is skipped
  and nothing is ever logged)
- no reference level near price at all (`level_pairs` is OR / PDH-PDL / PMH-PML, plus an
  `HODLOD_PAIR` that requires ≥43 bars and a ≥30-bar-old extreme)
- `detect_break_retest` found no ordered break→leave→return→confirm
- a signal *was* produced and then vetoed — by HTF bias, by candle colour, or by one of the stop
  width rules

That is one measurement run, and it names which single thing to change instead of guessing.

**Also broken, fix it first:** T2 did not do its job. `research/bar_coverage.md` reports **54 of
159 marks dropped, all `no_archive_file`** (49 distinct symbol-days). T2's own prose instructed a
`polygon_feed.fetch_day()` backfill and an `IWM` addition to `archive_1m.py`'s `SYMBOLS`; neither
happened. Every statistic above therefore rests on **48 S marks, not 77**. Backfilling those days
is the cheapest sample-size increase available and costs nothing but Polygon calls that cache to
disk.

---

## FOR AUSTIN

- The engine does not see your trades. It fires on **4 of 77** setups you graded S — 5%. Counting
  every signal it produces at any grade, still only 25%.
- So this was never a grading problem first. It is a **detection** problem. Filtering better among
  trades it already takes cannot reach setups it never noticed.
- The S gate we fit is a null: keep-rate gap +12.5pp with a CI of [-20.7, +45.5]. It ships **OFF**
  and nothing about live behaviour changed.
- No feature we measured tells your S from your A from your X. At 105 marks, only an effect larger
  than 45 percentage points would have shown up. That is a sample-size verdict, not a verdict on
  your eye.
- A third of your marks (54) had no price data at all, because the backfill row silently skipped
  itself. Your real sample was 48, not 77.
- Next: measure *why* the engine goes silent on your S bars, fix that one thing, re-measure recall.
