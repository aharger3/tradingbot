# g156 — S classifier v0 (OMEN 9.0, row F7)

**What is different now:** `signal_runner.py` has a new flag, `S_CLASSIFIER` (default OFF),
that drops an OR high/OR low break from the candidate stream when it never retested the level —
the single best candidate that survived to F5 without being formally refuted, out of 25 mined
from Austin's marks. **It does not clear the bar.** Zero of the 25 candidates measured in F5
(`research/g154_rule_*.py`) survived F6 refutation (`research/g155_rule_verdicts.md`: all 8
formal survivors refuted 3x independently each). Per the row's fallback instruction, v0 ships
this candidate anyway so the flag exists and is measured — not because it works.

## Which candidate, and why

Forward-selection on H1 (the only legitimate procedure here) found **nothing to add**: of the
17 candidates that were never even formal F5 survivors, only one improves `$/day` in *both*
halves — `or-break-without-retest` (H1 +$8.56/day, H2 +$18.46/day). Every other non-refuted
candidate either moves only one half positive (`cheap-stock-refusal` H1 +$10.60/H2 -$4.57,
`level-not-respected-refusal` H1 -$8.62/H2 +$58.53) or is a near-zero no-op
(`index-etf-avoid-unless-clear-htf`, `per-symbol-s-cap`, `forming-candle-entry-not-extreme`).
`or-break-without-retest` was excluded from F5's own survivor set only because bar-backed S
recall dipped 49.0%→48.7% — a 0.3-percentage-point miss, not a real failure — so it is the
correct pick for "best non-refuted candidate" and forward-selection stops there: nothing else
clears even that low a bar without cutting recall further.

Predicate (source: `research/g154_rule_or-break-without-retest.py`): **DROP** the candidate if
`stop_level_name in ("OR high", "OR low")` and `research/downgrade.no_retest(bars, i, level,
is_long)` is true — the level broke and price never came back to retest it. This is a genuine
drop from the arrival stream (the engine falls through to the next candidate that day), not a
grade cap: `RETEST_REQUIRED` (shipped default ON, 2026-09-02) already caps this same row to `C`,
and a `C` still trades (`_SKIP_GRADES = ("X", "D")` only). `S_CLASSIFIER` is the part
`RETEST_REQUIRED` does not do.

## Money, one-trade-a-day unit, size-gated (`bt2y_trades_retest_on.json`, 498 sessions, entry =
signal bar CLOSE, stops via `stop_rule.stop_fill_price`, 1R = $1,000)

| split | baseline $/day | v0 $/day | Δ $/day | mean R | win% | green months | max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| whole book | $33.93 | $47.44 | **+$13.51** | +0.047 | 46.9% | 13/25 | $21,405 |
| H1 (to 2025-09-01) | $135.71 | $144.27 | +$8.56 | +0.144 | 50.0% | 9/12 | $13,979 |
| H2 (from 2025-09-01) | −$67.85 | −$49.39 | +$18.46 | −0.049 | 43.8% | 4/13 | $21,405 |

Fires/day: **1.000 both arms** — this changes *which* candidate the one-trade-a-day unit picks
on affected days, not how many fire. Whole-book $/day is 12.0% of his $397/day bar (baseline was
8.5%).

## Precision, recall, fires — against the target (precision > 39.5%, no recall loss, fires 1–3/day)

| metric | baseline | v0 | target | met? |
|---|---:|---:|---:|---|
| precision (fired days graded S ÷ fired days graded at all) | 30.5% (18/59) | **30.5% (18/59)** | > 39.5% | **NO — flat, not just short** |
| S recall, 100-card probe (`probe_s_sweep_2026-08-28.jsonl`, 34 S) | 44.1% | 44.1% | no loss | yes |
| S recall, all bar-backed S days (`canonical_pool`, 345) | 49.0% | **48.7%** | no loss | **NO — 0.3pp below baseline** |
| fires/day | 1.000 | 1.000 | 1–3 | not applicable to this unit — see note below |
| candidates/day (raw arrival stream, whole pool) | 16.52 | 16.52 | — | unchanged; the drop only reorders which candidate a day's single pick lands on |

## The honest sentence

**v0 does not clear the bar.** Precision is exactly flat (30.5% → 30.5%, same 18 S days out of
the same 59 graded), so the flag buys $13.51/day on the whole book by changing which non-S day's
candidate gets picked, not by picking more S days — and it does that at a measurable, if small,
cost to bar-backed recall (49.0% → 48.7%). F5's own survivor criterion already said this: it was
not a survivor because of the recall dip, and F6 never even reached it because nothing
outperformed it enough to be a formal survivor in the first place. The three months of the
book's own comment corpus that this candidate is mined from do not contain enough distinguishing
signal to build an S classifier that fires 1–3 times a day above 39.5% precision. That gap is
still the project; this flag ships as a measured, honest zero, not a claimed win.

## Fires/day vs the 1–3 target — why they don't compare

The row's "fires 1–3/day, precision > 39.5%" target describes the *live* engine's raw arrival
stream (candidates/day = 16.52, of which 1–3 should be worth taking). `S_CLASSIFIER` operates
inside the one-trade-a-day backtest unit, which by construction already picks exactly one
candidate per day — it cannot be measured for "fires 1–3/day" without a live-stream replay,
which is out of this row's scope (Phase L/O own the live wiring). What this row *can* and does
measure honestly: does the classifier make the one pick better. It does not.

## What ships

`signal_runner.py`: `S_CLASSIFIER` env flag (default `"0"`/OFF, same parsing convention as
`RETEST_REQUIRED`), gate placed in `SignalRunner._route` after `_apply_x_lift` (placing it
before that call let the X-lift mechanism re-promote the drop straight back to B — the first
draft of this gate did exactly that and the test below caught it). `research/test_s_classifier.py`
— 4 assertions: default OFF; ON X-grades the real IWM 2024-10-01 09:40 OR-low no-retest
candidate (the same real day `research/test_retest_gate.py` uses to prove `RETEST_REQUIRED` is
reachable); ON leaves a real break-and-retest alone; OFF is byte-identical on an unaffected tape.

## Reproduce

```
python research/g154_rule_or-break-without-retest.py   # prints the money/precision/recall table
python research/test_s_classifier.py                   # 4 assertions, exits 0
python research/regression_gate.py && python research/test_runner_stop.py   # verify gate
```

Both verify-gate scripts pass with `S_CLASSIFIER` at its default (OFF); no baseline-fired mark
went silent.
