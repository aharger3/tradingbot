# F1 Part 2: blind_marks_all.jsonl → g150_marks_comments

Mined comments from `research/blind_marks_all.jsonl` into structured rows with symbol, day, source_file, card_id, grade, comment text, and timing/price fields.

## Summary

| Metric | Value |
|--------|-------|
| Total rows written | 260 |
| Rows with comment > 3 chars | 112 |
| Deduped exact duplicates | 0 |
| Source file | `research/blind_marks_all.jsonl` |

## Grade Distribution

| Grade | Count |
|-------|-------|
| S     | 50    |
| A     | 67    |
| none  | 143   |
| **Total** | **260** |

## Comment Fields Concatenated

- `note` (primary prose)
- `management` (secondary prose)
- No `answers` field in this corpus

## Pricing/Timing Fields

All rows include:
- `entry_t` (entry time if present)
- `stop` (stop level if present)
- `target` (target level if present)

## Output Schema

```json
{
  "symbol": "string",
  "day": "YYYY-MM-DD",
  "source_file": "research/blind_marks_all.jsonl",
  "card_id": "SYMBOL-YYYY-MM-DD",
  "grade": "S|A|none",
  "comment": "concatenated prose",
  "entry_t": "HH:MM" (optional),
  "stop": float (optional),
  "target": float (optional)
}
```

## Reconciliation

File: `research/blind_marks_all.jsonl` — 260 rows, all parsed and written to output with no modifications to mark corpora.
