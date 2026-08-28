# W4 handoff — Corpus holds no S-marked Austin material

**Written 2026-08-28 by the W4/W5 agent. The source-mining agent should read this and
then DELETE THIS FILE.** It exists only because `Specs/omen6-h2-master-spec.md` §3 W4
step 2 says to write the miss down for whoever mines sources next.

Austin's instruction, verbatim:

> "Try Corpus first for S-marked trade images, S-marked transcripts, or S-marked
> understanding of videos. If you can't find any of that in Corpus, flag it somewhere in
> the instructions for a different agent to read... If you can't find it in Corpus, then
> start looking at Discord, Circle, YouTube."

Corpus was searched first. **It holds none.** The rest of W4 continued into Discord /
Circle / YouTube and is reported in `research/w4_recall_sources.md`.

## What was searched

Every `research/corpus_*` artifact on disk — 138 files. Profiled by schema (key sets),
by `speaker` / `author` / `class` / `source` field, and by grep for any field name
containing `grade`, `tier`, `verdict`, `mark`, `austin`, `rating`, `score` or `quality`.

| artifact | rows | what it actually holds | Austin grades? |
|---|---:|---|---|
| `corpus_index.jsonl` | 5,460 | quotes mined from rule docs and source files; `speaker` is **Scarface/jdub 2,453 · Hayden 417 · Mar 130**, `class: TRADER_SAID` | no |
| `corpus_instances.jsonl` | 10,379 | Discord alert messages; `author` is **Jdub / MambaTrades / community**; exactly **1** row authored by Austin, a `trading-floor` message at `minute_i` 228 (13:53 ET, outside the 09:30–11:00 window) | no |
| `corpus_entries.jsonl` / `_v2` / `_joined` / `_normalized` | 2,882 / 8,837 | setups extracted from **YouTube captions by a local model** (`source: yt_caption*`, `model: qwen3.5:4b`) | no — model-inferred |
| `corpus_frames.jsonl` | 1,830 | vision reads of video frames, same model | no — model-inferred |
| `corpus_setup_map` / `_setup_rules` / `_rule_candidates` | 972 / 712 / 185 | label normalisation and rule aggregation over the above | no |
| `corpus_misses.jsonl` / `corpus_miss_autopsy.jsonl` | 300 / 10,263 | why the engine missed each community alert; `author` is the community member who posted it | no |
| `corpus_engine_*.jsonl` (12 files) | — | the **only** corpus files with a `grade` field, and it is the ENGINE's `A+/A/B/C/X` letter. `research/marks/LEDGER.md` already excludes these by name as engine output | no |
| `corpus_tl_*`, `corpus_trendline_fires_*` (≈60 files) | — | trendline detector fires, per symbol | no |
| `corpus_bar_coverage*.md`, `corpus_chain.log`, `corpus_rebuild.log` | — | coverage and build logs | no |

`research/corpus_recall.md`, `corpus_miss_autopsy.md` and `corpus_instances.md` all say
the same thing in prose. `corpus_miss_autopsy.md` is explicit:

> "Corpus instances are **alerts from Discord**, not Austin's own graded setups, so there
> is no S/A/X tier."

## The one exception, and it is already counted

`research/corpus_recovery.md` describes 176 genuinely Austin-graded rows mined out of old
Claude session transcripts. They were written to **`research/recovered_reviews.jsonl`**,
which is already one of the nine mark corpora and already in
`research/build_deck.py::LEGACY_MARK_FILES`. Nothing new there.

Worth knowing anyway: 135 of those 176 rows are flagged `align: "unmatched"` and were
never merged into `austin_marks_v7.jsonl`. `research/marks/LEDGER.md` counts **47 S-tier
symbol-days that exist only in that unmatched set**, deliberately excluded for cause (no
bar index, no verified alignment, mined from prose). They are real Austin S judgements at
a coarse grain. If anyone wants more S material cheaply, re-aligning those 47 is the
highest-value unclaimed job in the repo — and it needs zero new grading.

## What Corpus is missing, structurally

Corpus was built to mine **other traders'** language, because that is what the rulebook
was reverse-engineered from. It was never pointed at Austin's own messages. Two Discord
channels holding Austin's own posts — `post-your-gains.json` (123 messages) and
`questions.json` (31) — are **not in the corpus channel list at all**
(`corpus_instances.md` names scarface-alerts, jdub-alerts, trading-floor, trade-feedback,
swing-ideas, futures-alerts, backtesting, options-trade-reviews, pre-market-live,
futures-trade-reviews). That gap is what W4 mined next.

**Delete this file once you have read it.**
