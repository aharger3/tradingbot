# Corpus recovery — 176 graded rows the corpus never ingested

A sweep of all 164 past Claude sessions on 2026-08-11 found **176 graded rows** in two
review formats no corpus loader had ever matched: a pipe table
(`11 | SOFI | 2026-07-16 | break_and_retest | put | engine=hidden | loss | R=-1.00 | you=C | <note>`)
and a bracket form (`[backtest-UBER-2026-02-11-1] tier=X bot=A result=win setup=reentry_84_rule disagree note="..."`).
They grade **the engine's own entries** — each carries the engine grade it was shown
(`engine=B`, `engine=A+`, `engine=hidden`) and the outcome (`win` / `loss` / `scratch`,
sometimes `R=`) — but they carry no bar index, so grading was at the
(symbol, day, setup, direction) level.

## Where the rows came from

Four Claude sessions produced them. All 176 are embedded verbatim in
`specs/omen-5.0.md` (T12) and written to `research/recovered_reviews.jsonl`.

| source_session | rows | aligned exact | S marks |
|----------------|------|---------------|---------|
| `07b1def7`     | 56   | 9             | 20      |
| `6824c7b7`     | 49   | 13            | 13      |
| `6e026b88`     | 37   | 11            | 12      |
| `f593f4f3`     | 34   | 9             | 12      |
| **total**      | **176** | **42**     | **57**  |

## How they were recovered

Per the T12 method, no level-touch fallback was used. Each row was aligned by
replaying `SignalRunner.detect_signals()` over that symbol+day and taking the fire
that matches on **setup, direction, engine grade and outcome** — an exact
identification, not an inference. A unique match gets `align: "exact"`; an ambiguous
or missing match gets `align: "unmatched"` and is written out but **not** merged.

The engine replayed is the **post-T3/T4/T10/T11 engine** (session window inside the
detector, close-based stop-outs, displacement gate, pivot levels, level retirement).
So an unmatched row is often telling us the *old* engine fired somewhere the new one
does not — a finding about the change, not a defect in the row.

## Counts

```
recovered_rows: 176
aligned_exact: 42
aligned_unmatched: 134
merged_into_v7: 41
recovered_s_marks: 57
```

42 rows aligned exactly; 1 of those already existed in `research/austin_marks_v7.jsonl`
under the same id and was not duplicated, so **41** new rows were merged into v7 under
`batch: "recovered"`. Every merged row carries `align: "exact"` and its `source_session`,
so any bad row can be traced and pulled later. v7 now holds 479 unique ids with no
duplicates.

Of the 134 unmatched rows, 125 are on days where this engine takes no trade at all and
9 are on days where it trades but not that setup+direction — the shape of the T3/T4/T10/T11
changes, which removed the fires the reviewed cards were built from. Those rows keep
their notes and tiers in `recovered_reviews.jsonl` and can be re-aligned against any
future engine by re-running the alignment script.

**57 of the 176 recovered rows are tier S** — more S than the usable corpus held before
this recovery. 8 of those S marks were among the 41 merged into v7.
