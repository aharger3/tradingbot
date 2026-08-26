# Mark archaeology ledger

Answers `.scratch/omen-6/issues/01-mark-archaeology.md`. Built 2026-08-22 by reading
every file under `C:\Users\aharg\Desktop\Projects\tradingbot` (working tree + full
git history) and `C:\Users\aharg\Austin's Vault\Projects\OMEN.md` + neighbours.
Read-only — no source files were modified.

## How human marks were separated from engine output

A row counts as an **Austin mark** only if it was produced by a documented human
grading pass — a deck export, a `mark_batch_*_grades` file, or a verdict/tier
file whose companion `.md` report describes a grading session. The tell:
these schemas carry `note`, `setup`/`kind`, `source_session` or `miss_reason`,
and their `tier`/`grade` field is populated from a human return (`S`/`A`/`C`/`X`/`none`,
occasionally `B`), not from the signal detector.

Excluded as **engine-produced, not human**: any file whose `grade` field comes
from `SignalRunner`/backtest replay — these use the engine's own `A+`/`A`/`B`/`C`/`X`
letter grade and travel with engine-only columns (`alert_only`, `pnl`,
`exit_price`, `scale_level`, `minute_i`, `quote_source`, `stop_width_pct`).
Confirmed by `signal_runner.py:659`: `sig["austin_tier"] = None` always — the
engine has no mapping into Austin's S/A/C/X ladder, so any file where `grade`
and `austin_tier` both vary independently is a hybrid (engine grade + a *looked-up*
historical Austin tier, not a fresh judgment). Excluded files, all engine-side:
`research/corpus_engine_*.jsonl`, `research/engine_entries*.jsonl`,
`research/engine_signals*.jsonl`, `research/84rule_trades.json`,
`research/rule84_candidates.jsonl`, `research/t51_fill_flip.jsonl`,
`research/*_charts.json` / `f2f1_runs/charts_*.json`, `backtest_charts*.json`,
`journal/signal_log_*.jsonl` (live bot telemetry; its `austin_tier` is a static
per-symbol lookup — e.g. every IWM/AVGO/NVDA row in `signal_log_2026-08-18.jsonl`
carries `austin_tier: "C"` regardless of setup, not a fresh grade),
`research/decks/_retired/omen-5.2-blind-key.json` (backtest answer key, `A+/A/B/C`
scale, built to be revealed *after* a blind grading pass — not the grading itself).

## Artifact inventory — human marks

### The two-file pool the ticket already knew about

| path | added | rows | schema (keys) | OMEN version |
|---|---|---|---|---|
| `research/marks/deck_marks_index_2026-08-19.jsonl` | 2026-08-19 | 97 | `card_id,type,symbol,date,day_type,grade,n_trades,notes,reason_none,setup,trade_no,entry_i,entry_p,entry_t,exit_i,exit_p,exit_t,stop_i,stop_p,stop_t,side,r_multiple,source` | omen-5.2 T1 |
| `research/marks/deck_marks_tsla_2026-08-20.jsonl` | 2026-08-20 | 87 | (same schema) | omen-5.2 T1 |

Each file mixes two row `type`s: `day` (one grade per symbol-day) and `trade`
(execution detail — entry/stop/exit bar+price — for the subset of days Austin
would actually trade). **184 raw rows = 120 day-grades + 64 trade-details.**
The 64 trade rows are not separate judgments — they hang off an already-counted
`day` row (same `card_id`). Distinct judgments in this pool = **120**.

- Grade distribution (120 day rows): **S 28 · A 27 · C 3 · none 61 · blank 1**
- Rows carrying an entry bar: 37 (index) + 27 (tsla) = 64 trade rows, all with `entry_i`
- Per symbol: QQQ 30 days, SPY 30 days, TSLA 60 days
- Date range: 2026-05-14 → 2026-08-10

### The scattered pool — `research/*.jsonl` (never moved into `research/marks/`)

Progressive versions of one corpus, each superseding the last by `id`-level merge.
**`austin_marks_v7.jsonl` is the terminal file** — every earlier version's rows
are contained inside it (verified: all 117 `marks_clean` triples, all 14
`derived_marks_v1` ids, and every batch file's rows are present in v7 by
`symbol|day|entry_i` or `id`). Reporting the full lineage per the ticket, but
**only v7's 479 rows should count toward any total** — the others are the same
judgments at an earlier merge state.

| path | added | rows | grade field | OMEN version / origin | grade dist (S/A/C/X, `austin_tier` falls back to `tier`) |
|---|---|---|---|---|---|
| `research/austin_verdicts.json` | 2026-08-06 | 162 (159 distinct triples, 2 dup-marked) | `verdict` | pre-3.9 raw capture; source of v2 | S 77·A 60·X 22 (after dedup) |
| `research/austin_marks_v2.jsonl` | 2026-08-06 | 159 | `tier` | dedup of verdicts.json | S 77·A 60·X 22 |
| `research/austin_marks_v3.jsonl` | 2026-08-09 | 184 | `tier` | omen-3.9 T3 (+batch02, 25 new + 7 overwrites) | S 77·A 71·X 36 |
| `research/austin_marks_v4.jsonl` | 2026-08-09 | 184 | `tier`/`austin_tier` | omen-4.0 T1 (29-regrade merge, overwrite-only) | S 65·A 77·X 39·C 3 |
| `research/austin_marks_v5.jsonl` | 2026-08-09 | 214 | `tier`/`austin_tier` | omen-4.0 T4 (+35-card batch04, 30 new) | S 64·A 80·X 64·C 6 |
| `research/austin_marks_v6.jsonl` | 2026-08-10 | 228 | `tier`/`austin_tier` | omen-4.0 T5 (+14 note-derived) | S 71·A 81·X 67·C 7 |
| **`research/austin_marks_v7.jsonl`** | 2026-08-11 | **479** | `austin_tier` | omen-5.0 T1 (+batch05, 80 new) → T2 (+18 derived) → recovery pass (+41 from old sessions) | **S 139·A 172·X 148·C 16·B 3·blank 1** |

Companion source/derivation files (all fully contained in v7 — listed for
provenance, not added to totals):

| path | added | rows | role |
|---|---|---|---|
| `research/blind_marks_all.jsonl` | 2026-08-05 | 260 (117 marked, 143 `_no_trade`) | pre-3.9 base layer; 117 marked triples all present in v7 |
| `research/marks_clean.jsonl` | 2026-08-05 | 117 | marked-only subset of blind_marks_all; 100% in v7 |
| `research/mark_batch_02_grades.jsonl` | 2026-08-09 | 60 | omen-3.9; S 35·A 11·X 14; "40 S-miss bars + 20 unmarked engine entries," 25 new keys + 7 overwrites into v3 |
| `research/mark_batch_03_regrades.jsonl` | 2026-08-10 | **29** | omen-4.0 T1 — **this is the "29 regraded marks" the ticket names**; S 13·A 9·X 4·C 3 |
| `research/mark_batch_04_grades.jsonl` | 2026-08-10 | **35** | omen-4.0 — **this is the "35-card batch (2026-08-10)" the ticket names**; S 4·A 3·X 25·C 3; no `entry_i` (id-linked to existing rows) |
| `research/derived_marks_v1.jsonl` | 2026-08-10 | 14 | omen-4.0 T5, mined from batch-04 note text; S 8·A 1·X 3·C 2; 100% present in v6/v7 |
| `research/derived_marks_v2.jsonl` | 2026-08-11 | 18 | omen-5.0 T2 — **this is the "~18 note-derived entry bars" the ticket names**; S 10·A 8; 4 more candidates were dropped for colliding with existing v7 ids (**the "4 derived marks that collided with v7 rows" the ticket names**) |

**The "80-graded-card batch (2026-08-11)"** the ticket names is `batch05` inside
the omen-5.0 T1 merge (S 2·A 8·C 1·X 69) — merged straight into v7, never saved
as a standalone file (source was `~/Desktop/projects/omen-marks/batch05_{rule84,ocr,br}.json`,
external to this repo and **no longer present on disk** — that folder is gone,
consistent with `Projects/OMEN.md` line 47-51 saying its two decks were "copied
into" `research/marks/` and consolidated; not a data loss, just a moved/retired
scratch path).

**The "v5"/"v7" mark tables** the ticket names are exactly `austin_marks_v5.jsonl`
and `austin_marks_v7.jsonl` above.

### A third, coarser-grain pool — `research/recovered_reviews.jsonl`

| path | added | rows | schema | OMEN version |
|---|---|---|---|---|
| `research/recovered_reviews.jsonl` | 2026-08-11 | 176 | `symbol,day,setup,direction,austin_tier,engine,engine_outcome,result,R,note,source_session,align,align_reason,id,entry_i(42 only),entry_time(42 only)` | omen-5.0 T12 |

Mined from 4 old Claude session transcripts (pipe-table and bracket-note review
formats no corpus loader had ever matched). Graded at **(symbol, day, setup,
direction)**, not a bar index — coarser grain than every other pool. 42 rows
were aligned exactly to a real engine replay; 1 already existed in v7, so **41
new rows merged into v7** (already counted above, `batch: "recovered"`). The
remaining **134 rows are `align: "unmatched"`** (this repo's own methodology
declined to merge them — 125 are on days the current engine takes no trade at
all, 9 are on days it trades a different setup/direction). Grade dist, all 176:
S 57·X 42·C 24·A 39·B 14. Grade dist, the 134/135* unmatched: S 48·X 30·C 16·A 29·B 11.

\* 134 rows carry `align != "exact"`; one further exact-match row was a
duplicate of an id already in v7 and also isn't newly counted — net 135 rows
of recovered_reviews sit outside v7.

### Not marks yet / not resolvable

| path | status |
|---|---|
| `research/decks/omen-5.3-mixed-manifest.jsonl` (60 rows, added 2026-08-21) | **Ungraded.** Card manifest for the current/next deck (omen-5.3). No grade field — `Projects/omen-decks.md` "Next build step" confirms grading + export hasn't happened. Not counted. |
| `research/decks/_retired/omen-5.2-blind-key.json` (100 rows) | Engine-generated backtest answer key for the retired 5.2 blind deck (`A+/A/B/C` scale), meant to be revealed *after* grading — no matching graded-output file exists anywhere in the repo or vault. The blind-deck exercise appears never to have been completed/exported. Not counted, flagged as unresolved. |
| `research/decks/_retired/mark_batch_02.html`, `omen-5.1-fill-cards.html`, `omen-5.2-blind-deck.html`, `omen-5.2-entry-deck.html` | Blank card templates; marks (if any were ever taken) lived only in browser `localStorage`, never serialized into the HTML or exported to a jsonl found anywhere. Not recoverable from this repo. |
| `specs/omen-5.0.md` (T12, cited by `research/corpus_recovery.md` as holding all 176 recovered rows "embedded verbatim") | **Path does not exist** in this repo, in git history (`git log --all -- '*omen-5.0*'` returns nothing), or anywhere under the vault. Not blocking — the same 176 rows are captured byte-for-byte in `research/recovered_reviews.jsonl`, which is on disk. |

## Git history sweep

`git log --all --diff-filter=D --name-only -- research/ 'research/*mark*' 'research/*deck*' 'research/*corpus*' 'research/*austin*'`
found **no deleted mark-data files** — only three deleted deck-*generator scripts*
(`research/retrofit_deck.py`, `research/t51_build_deck.py`,
`research/t6_build_decks.py`, all removed in commit `6a6bb2d2`, 2026-08-21,
superseded by `research/build_deck.py`). `research/marks/` itself has exactly
one commit in its history (`f2818b71`, 2026-08-20, both files added together,
never touched again). **Every mark-bearing file found above is tracked, present,
and clean in the current working tree** — nothing had to be recovered from a
blob. Deck HTML is gitignored going forward but no deck HTML holding marks was
ever committed-then-deleted; the committed HTML in `_retired/` is unmarked
template shells (see above).

## Vault sweep

`Projects/OMEN.md` cites every batch above in prose/tables but embeds no
standalone graded-card table of its own — its numbers (159, 184, 214, 228, 420,
479, 60, 100, 120) all trace to the files inventoried here. `Projects/omen-decks.md`
states **"~500 historical marks"** use the S/A/C ladder (consistent with
479 + 120 - overlap ≈ 599, see below) and contains one operationally important
fact: **the deck builder's no-repeat guarantee (`marked_card_ids()`) only reads
`research/marks/*.jsonl`** — it does not know about `austin_marks_v7.jsonl` or
any scattered file, so a future deck could re-ask Austin to grade a symbol-day
he already judged in the old corpus. `Projects/omen-5.2-verdict.md` was checked
and contains analysis of the 5.2 marks, no additional raw mark rows.

## Overlap / joins

- **v7 (bar-level, 386 distinct symbol-days) ∩ canon (day-level, 120 distinct
  symbol-days): only 2 shared symbol-days** — `(QQQ, 2026-07-09)` and
  `(TSLA, 2026-07-09)`. These two pools are almost entirely disjoint: v7 is the
  2024–2026 accumulated bar-level entry corpus across 30 symbols; canon is the
  Aug 2026 QQQ/SPY/TSLA day-card deck.
- **v7 (117 marks_clean triples) ∩ austin_verdicts/v2 (159 triples): 0 overlap**
  — confirmed independently by `research/regrade_audit.md`'s own failed
  re-grade attempt (162 input verdicts, 0 matched against `blind_marks_all`)
  and by direct triple comparison here. Two genuinely separate origin pools
  that both landed inside v7.
- **recovered_reviews unmatched-135 (133 distinct symbol-days) ∩ (v7 ∪ canon):
  only 3 shared symbol-days** (2 vs v7, 1 vs canon) — ~130 are new symbol-days
  not graded anywhere else, but at the coarser (symbol,day,setup,direction)
  grain and explicitly flagged `unmatched` by the project's own alignment pass.

## Deduplicated totals

**High-confidence pool** (bar-level v7 + day-level canon, both from documented,
completed grading passes):

| | count |
|---|---|
| v7 distinct judgments (bar-level, `id`-deduped) | 479 |
| canon distinct judgments (day-level, `card_id`-deduped) | 120 |
| **Additive union (different grain, not truly overlapping)** | **599** |
| Shared symbol-days between the two (informational, not double-counted-away — a day-grade and a bar-level entry on the same day are complementary, not duplicates) | 2 |

**→ Deduplicated total distinct Austin judgements on record: 599** (479
bar-level entries + 120 day-grades). If a stricter same-day dedup is wanted
(collapsing the 2 shared symbol-days to one judgment each), **597**.

**→ Distinct symbol-days judged (any grain, v7 ∪ canon): 504** (386 + 120 − 2).

Adding the 135 low-confidence coarse-grain `recovered_reviews` rows (not
bar-indexed, not re-verified against the current engine) pushes distinct
symbol-days to **634** and total judgment-rows to **734** — reported for
completeness, not recommended as the working number (see confidence note below).

## S-grade day count — the number the 90%-recall gate needs

| pool | distinct S symbol-days |
|---|---|
| `austin_marks_v7.jsonl` (bar-level, `austin_tier`/`tier`=S) | 127 |
| canon `research/marks/*.jsonl` (day-level, `grade`=S) | 28 |
| overlap between the two | 1 |
| **High-confidence union** | **154** |
| + `recovered_reviews.jsonl` unmatched-135, S-tier, not already in the union | +47 |
| **If low-confidence rows included** | **201** |

**Answer: 154 distinct S-grade symbol-days, high confidence.** This uses only
rows from a documented, completed, bar-or-day-level grading session
(`austin_marks_v7.jsonl` + the two canon deck files). It excludes the 47
S-tier symbol-days sitting only in `recovered_reviews.jsonl`'s unmatched-135,
because that file's own build report (`research/corpus_recovery.md`) already
declined to merge them into the working corpus for cause: no bar index, no
verified alignment to the current engine (most are on days this engine takes
no trade at all), and origin is pattern-mined old chat transcripts rather than
a fresh look at a chart. Treat 154 as the number to gate on; treat 201 as an
upper bound that would need a re-grading pass (or at minimum a manual spot
audit) before being trusted.

## Date range and per-symbol breakdown (high-confidence pool: v7 ∪ canon)

**Date range: 2024-01-02 → 2026-08-10** (v7 alone runs 2024-01-02 → 2026-08-04;
canon adds 2026-05-14 → 2026-08-10, mostly non-overlapping with v7's window).

| symbol | distinct days |
|---|---|
| TSLA | 81 |
| QQQ | 65 |
| SPY | 56 |
| NVDA | 20 |
| AAPL | 19 |
| IWM | 18 |
| MSFT | 18 |
| MSTR | 17 |
| PLTR | 15 |
| MARA | 15 |
| COIN | 14 |
| MU | 14 |
| AMD | 12 |
| HOOD | 12 |
| META | 12 |
| GOOGL | 11 |
| AVGO | 10 |
| SOFI | 10 |
| SPCX | 10 |
| ORCL | 10 |
| UBER | 9 |
| INTC | 8 |
| CRM | 8 |
| GOOG | 7 |
| AMZN | 7 |
| BABA | 6 |
| NFLX | 6 |
| IREN | 5 |
| DIA | 5 |
| TSM | 4 |

30 distinct symbols carry at least one mark. TSLA/QQQ/SPY dominate because they
are both v7's most-marked names and the entirety of the canon deck pool.


---

## `probe_master_homework_2026-08-26.jsonl` — 51 rows, added 2026-08-26

The OMEN master homework, graded away from this machine and pasted back into the
session. **The paste is the only copy** — nothing landed in `~/Downloads`, so there is
no file to reconcile against. Four sections in one file, distinguished by card-id prefix:

| prefix | section | rows |
|---|---|---:|
| `cal_` | grader calibration — which tripped downgrade does he reject | 12 |
| `au_` | silent-day autopsy — what made it a trade | 5 |
| `h2_` | head-to-head — days he refused that the engine graded S | 9 |
| `sr_` | S-recall — is there an S entry on this day at all | 25 |

`sr_` rows carry `grade: null` by design: the question is "is there an S here", answered
in `answers.s_call`, and several `no` answers still name a specific bar and letter in
`notes.s_call` ("10:02 A trade because overextended"). Those notes are judgements about
bars the corpus has no card for — do not discard them when parsing.

**Two symbol-days were asked twice inside this one document**: QQQ 2026-07-20 and
QQQ 2026-07-24 each appear as both a `cal_` and an `au_` card. `build_deck.marked_card_ids()`
guards against re-asking a day judged in a *previous* corpus; it does not deduplicate
across the sections of a document being built. Austin noticed before we did. Tracked as
G12; until it is fixed, every multi-section instrument can repeat itself.
