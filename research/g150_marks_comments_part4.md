# F1 Part 4: Comments extraction from marks_clean.jsonl + deck/probe files

Extracted all prose fields (note, notes, comment, review, why, management, answers text) from marks_clean.jsonl and five probe/deck mark files into structured rows with schema: symbol, day, source_file, card_id, grade, comment, entry_t/stop/target (if present).

## Summary

- **Total rows written**: 333
- **Rows with comment > 3 chars**: 151 (45.3%)
- **Rows with comment > 40 chars**: 90 (27.0%)
- **Deduplicated exact duplicates**: 0

## Breakdown by grade

| Grade | Total | With comment > 3 chars |
|-------|-------|------------------------|
| S | 93 | 56 |
| A | 94 | 60 |
| C | 3 | 3 |
| none | 143 | 32 |

## Breakdown by source file

| Source | Total | With comment > 3 chars |
|--------|-------|------------------------|
| marks_clean | 117 | 72 |
| deck_marks_index_2026-08-19 | 97 | 20 |
| deck_marks_tsla_2026-08-20 | 87 | 35 |
| probe_autopsy_2026-08-23 | 15 | 13 |
| probe_head2head_2026-08-24 | 9 | 8 |
| probe_trade_anatomy_2026-09-01 | 8 | 3 |

## Reconciliation

All 333 rows from source files are unique; no deduplication needed. Prose fields concatenated include: note, management (from marks_clean), and standard fields from probe files. Timing and price fields (entry_t, stop, target) included from marks_clean where present; probe files have no timing/price data in this extraction.

File paths verified:
- research/marks_clean.jsonl ✓
- research/marks/deck_marks_index_2026-08-19.jsonl ✓
- research/marks/deck_marks_tsla_2026-08-20.jsonl ✓
- research/marks/probe_autopsy_2026-08-23.jsonl ✓
- research/marks/probe_head2head_2026-08-24.jsonl ✓
- research/marks/probe_trade_anatomy_2026-09-01.jsonl ✓
