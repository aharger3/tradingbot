# F1 Part 7: Marks Comments Extraction

Extracted comments from part 7 file group into `research/g150_marks_comments_part7.jsonl`.

## Summary

- **Rows written**: 329
- **Rows with comment > 3 chars**: 203 (61.7%)

## Grade Distribution

| grade | count |
|-------|-------|
| S     | 10    |
| A     | 1     |
| none  | 318   |

## Source File Distribution

| source file | count |
|-------------|-------|
| probe_master_2026-08-29.jsonl | 123 |
| probe_s_sweep_2026-08-28.jsonl | 100 |
| probe_master_homework_2026-08-26.jsonl | 51 |
| probe_g71_homework_s3_2026-08-29_complete.jsonl | 30 |
| probe_g71_homework_s3_2026-08-29.jsonl | 25 |
| **Total** | **329** |

## Notes

- Exact duplicates deduped (none found across these files)
- Comments concatenated from: note, notes dict values, comment, review, why, answers[*] text
- Optional fields (entry_t, stop, target) included when present (none present in this subset)
- Grade values cleaned: `null` → `"none"`
- Symbol and day fields may be null for some records (e.g., fact-checking probes)
