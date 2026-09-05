# F1 Part 3: Extracted Comments from recovered_reviews.jsonl

**Source file:** research/recovered_reviews.jsonl  
**Output file:** research/g150_marks_comments_part3.jsonl  
**Date:** 2026-09-05

## Summary

Total rows processed: 176  
Rows after dedup: 176  
Rows with comment over 3 chars: 173

## Grade Breakdown

| Grade | Count |
|-------|-------|
| S     | 57    |
| A     | 39    |
| C     | 24    |
| B     | 14    |
| X     | 42    |
| **Total** | **176** |

## Notes

- No duplicate rows found (all 176 unique)
- 3 rows have comments of exactly 1 character ("?") - these are short by design
- All prose fields concatenated: note, align_reason (when present)
- No entry_t, stop, or target fields present in source
- Card IDs generated from source 'id' field where present, or symbol_day format otherwise
