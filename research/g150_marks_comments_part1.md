# F1 Part 1: Comments extraction from austin_marks_v7.jsonl

Extracted all prose fields (note, notes, comment, review, why, answers text) from austin_marks_v7.jsonl and emitted to research/g150_marks_comments_part1.jsonl with schema: symbol, day, source_file, card_id, grade, comment, entry_t/stop/target (if present).

## Summary

- **Total rows written**: 479
- **Rows with comment > 3 chars**: 218 (45.5%)

## Breakdown by grade

| Grade | Total | With comment > 3 chars |
|-------|-------|------------------------|
| S | 139 | 53 |
| A | 172 | 93 |
| C | 16 | 15 |
| B | 3 | 3 |
| X | 148 | 54 |
| (empty) | 1 | 0 |

## Breakdown by source file

| Source | Total | With comment > 3 chars |
|--------|-------|------------------------|
| v2 | 159 | 27 |
| marks_clean | 117 | 72 |
| batch05 | 80 | 40 |
| v3 | 25 | 7 |
| v5 | 30 | 13 |
| recovered_reviews.jsonl | 41 | 41 |
| v6 | 9 | 0 |
| (empty) | 18 | 18 |

## Notes

- No deduplicated rows (all 479 rows from source are unique)
- No entry_t, stop, or target fields present in source file
- Only "note" prose field exists in austin_marks_v7.jsonl (other prose fields like comment, review, why, answers not present in this file)
