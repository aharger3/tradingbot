# Target Autopsy (omen-3.4 / T4) — BLOCKED

> **Status: NOT DONE.** This task could not be executed. Its two required inputs
> do not exist on this checkout, so the classifier cannot be run and no bucket
> counts can be produced. This file is a blocker record, not a result. It does
> **not** satisfy the done-when (no four bucket counts, no `PRECEDENCE` winner).

## What T4 requires

Per the task spec, T4 must — for every mark in `research/marks_clean.jsonl` —
compute the level node set at its entry bar **using `research/levels.py`**,
classify each target into exactly one of `at_level` / `at_2R` / `both` /
`open_air`, and report bucket distribution, the level-vs-2R precedence, the
target-to-nearest-node distance distribution, and the rr distribution.

Both inputs are T2/T3 outputs that have **not been produced** in this
environment. T1 (the only prior omen-3.4 artifact present, `omen34_inputs.md`)
inventoried the pre-existing repo assets and explicitly did not list either
file, because they are downstream deliverables, not pre-existing assets.

## Evidence — inputs are absent

Checked on `/home/runner/work/loop-ci/loop-ci/work`, branch `main`,
2026-08-05:

- `research/marks_clean.jsonl` — **MISSING.**
  `wc -l` errors (`No such file or directory`). Not in the working tree and not
  in git history (`git log --all --oneline -- '*marks_clean*'` → empty).
  Its upstream source is also absent: T1 lists the hand-marked corpus
  `research/blind_marks_all.jsonl` under MISSING — "The only `.jsonl` files
  under `research/` are `archive_gaps.jsonl` and `discord_extracted/*.jsonl`,
  none of which is a hand-marked trade corpus." (`archive_gaps.jsonl` parses to
  0 lines on this checkout.)
- `research/levels.py` — **MISSING.**
  No `levels.py` exists under the repo (`find . -name 'levels.py'` → empty;
  the only filesystem hits are unrelated Google Cloud SDK modules). T1 also
  lists the predicate module `predicates.py` under MISSING: "No predicate
  module exists under any name on this checkout."

## Why I did not substitute the engine trade population

The engine trade population `backtest_charts_12mo.json` (974 records, the
POPULATION_N source per T1) does carry `entry, stop, target, exit_price,
entry_i, candles, levels`. It is tempting to treat those records as "marks"
and build a level module on the fly. I did **not** do this, for two reasons
that make the result unfaithful rather than merely incomplete:

1. **Wrong question.** T4's question is *"what rule is HE actually using"* —
   the trader's hand-marked targets (the spec's headline row: "usually 2R,
   HOD/LOD and whole psychological numbers, as well as longer timeframe levels
   and pivot structures"). Engine records are algorithm-generated signals whose
   `target` is computed by the engine's own target rule. Classifying engine
   targets against level nodes would re-discover the **engine's** target rule,
   not the trader's hand rule — a category error that produces a misleading
   PRECEDENCE answer.

2. **No node taxonomy to compute against.** The engine `levels` field carries
   only six unweighted S/R types (`PDH, PDL, PMH, PML, ORH, ORL` — confirmed by
   parsing record 0). T4 requires nodes with a **type and a weight**, where
   `at_level` is defined against "a node of weight >= 2.0" and the trader's
   stated target types include HOD/LOD, whole psychological numbers, HTF
   levels, and pivot structures — none of which are present in the engine
   `levels` dict. `research/levels.py` (T3) is the module that would compute
   this weighted, typed node set at the entry bar; without T3's spec, any node
   scheme I invent would make the precedence verdict an artifact of my scheme,
   not of the data. The repo's own level code (`spec0b_levels_check.py`,
   `signal_runner.py`) likewise carries no node-weight concept.

Inventing `marks_clean.jsonl` and `levels.py` here would silently fold T2 and
T3 into T4 under undefined specs, and the resulting `PRECEDENCE` section would
be fabrication rather than measurement. The task instruction is explicit that
a false "done" is worse than an admitted failure.

## Bucket counts

Not produced. With `research/marks_clean.jsonl` absent there is no line count
to sum to, and no marks to classify. Per the task rule ("if any mark is
unclassifiable, fail loudly and say which"), the failure here is louder: there
are zero marks to classify because the corpus itself is missing.

- `at_level`: N/A
- `at_2R`: N/A
- `both`: N/A
- `open_air`: N/A
- Sum: N/A (cannot equal the line count of a file that does not exist)

## PRECEDENCE

**Not determined.** Determining which rule wins when a level and 2R disagree
requires (a) the marks corpus and (b) the level node set at each entry bar,
both of which are missing (see above). Naming a winner without them would be
invented, so this section deliberately states no precedence.

## What unblocks T4

Run the upstream omen-3.4 tasks first:

1. **T2** — produce `research/marks_clean.jsonl` from a marks corpus. The
   hand-marked corpus (`blind_marks_all.jsonl`) is MISSING per T1 and must be
   sourced or the spec must be formally redirected to a defined proxy corpus
   (engine population or other) — that redirect is a spec decision, not
   something T4 can make on its own.
2. **T3** — produce `research/levels.py`: a module that, given a mark's entry
   bar and 1-min candles, returns the typed, weighted level node set (HOD/LOD,
   psychological/round numbers, HTF levels, pivot structures) with weights so
   that "node of weight >= 2.0" is well-defined.

Once `marks_clean.jsonl` and `levels.py` exist, T4 is mechanical: load each
mark, call `levels.py` for the entry-bar node set, compute ATR_1m and R from
the mark's entry/stop, classify into `at_2R` (within 0.25R of 2.0R) /
`at_level` (within `max(2 ticks, 0.30·ATR_1m)` of a weight>=2.0 node) /
`both` / `open_air`, then write the bucket, precedence, distance, and rr
distributions here.
