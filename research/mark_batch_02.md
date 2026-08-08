# OMEN mark batch 02 — the next 60 charts to grade

**Split: 40 S-miss bars + 20 unmarked engine entries = 60 cards.**

This batch grows Austin's labelled corpus (159 marks today; every effect measured
on it is underpowered) by handing him 60 charts ready to grade with no setup.
Open `research/mark_batch_02.html` in a browser — it is fully self-contained
(no external script or stylesheet; inline `<style>` + `<script>` only).

## What is in the batch

**S-miss bars (40).** Every S mark in `research/miss_autopsy.jsonl` whose
`miss_reason` is **not** `detected`, most recent first, capped at 40. These are
bars where the engine was blind — it produced no entry within ±2 bars — so
Austin's grade on the same bar is the label that teaches the engine. His S here
is the truth the detection rules are missing. The `miss_reason` is printed on
each of these cards, so grading doubles as a check on the T2 autopsy.

**Unmarked engine entries (20).** Drawn from `research/engine_entries.jsonl`
(written by omen-3.6). These are engine entries that fired on a day Austin
marked *something* but at a bar Austin did **not** mark — the false positives.
His X on them is worth as much as his S: a confirmed non-entry is as informative
as a confirmed entry. We take the first 20 (file order, deduped by
symbol/day/bar) after dropping bars Austin already marked.

Reason mix across the 40 S-misses (a sanity read on T2):

| miss_reason        | count |
|--------------------|------|
| no_break_retest    | 18   |
| vetoed_htf         | 8    |
| fired_wrong_bar    | 6    |
| no_reference_level | 4    |
| vetoed_stop_too_tight | 2 |
| consolidation_early_return | 1 |
| vetoed_candle_colour | 1  |

## How each card is drawn

Reuses `build_review_artifact.py`'s template and level-colouring unchanged; only
the data source changes. Bars come from `data_archive/<SYMBOL>/<DAY>.csv`,
windowed to ~40 bars before and 30 after `entry_i`, with the entry bar marked
(white outline + ▲). Levels are coloured by type and reconstructed exactly as
`t4_engine_recall` feeds the engine:

- **premarket H/L** (amber dashed) — 04:00–09:29 same-day extended hours
- **prev-day H/L** (violet dashed) — prior archived trading day's RTH extremes
- **opening-range H/L** (sky dashed) — first 5 RTH candles (09:30–09:34)

For the unmarked engine entries the card also shows the engine's own
entry / stop / 2R-target lines. For S-misses the engine never fired, so only the
entry-bar marker and structure levels are shown (no fabricated stop/target).

Each card carries **symbol, date, time-of-day from `entry_i`**, and — for the
S-misses — the `miss_reason`. **Austin's existing tier is not printed** (nor is
the engine's B/C grade on the false positives): grades are collected blind or
they are worthless as labels.

## How to return grades

**One grade per card: S / A / X.** Return a list of 60 rows
(`day symbol time-of-day → S|A|X`) in the card order shown.
