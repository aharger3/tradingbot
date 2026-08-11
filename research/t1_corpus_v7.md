# T1 — Corpus v7 Consolidation Report

**Date:** 2026-08-11
**Source:** `research/austin_marks_v7.jsonl`

## Source file merge statistics

| Source file | Rows read | Rows new | Tiers overwritten | Notes preserved |
|---|---|---|---|---|
| marks_clean | 117 | 0 | 0 | 0 |
| blind_marks_all | 117 | 0 | 0 | 0 |
| austin_marks_v2 | 159 | 0 | 0 | 0 |
| austin_marks_v3 | 184 | 0 | 7 | 1 |
| austin_marks_v4 | 184 | 0 | 17 | 15 |
| austin_marks_v5 | 214 | 0 | 2 | 4 |
| austin_marks_v6 | 228 | 0 | 4 | 0 |
| mark_batch_02 | 60 | 0 | 10 | 8 |
| mark_batch_03 | 29 | 0 | 9 | 0 |
| mark_batch_04 | 35 | 0 | 1 | 1 |
| batch05 (new) | 80 | 80 | 0 | 0 |
| **Total** | **1407** | **80** | **50** | **29** |

## Summary

- **Total rows in v7:** 420
- **noted_marks:** 159
- **batch05 rows:** 80 (S:2, A:8, C:1, X:69)
- **Sources not found:** `research/omen40_marks.jsonl` — skipped (not present in research directory)

## Merge rules applied

1. **Deduplication by `id`** — all 420 rows have unique ids.
2. **Tier overwrite by batch priority:** batch05 > mark_batch_04 > mark_batch_03 > mark_batch_02 > v6 > v5 > v4 > v3 > v2 > blind_marks_all > marks_clean
3. **Never drop a note** — when two sources had different notes for the same id, they were concatenated with ` | `.
4. **Preserve setup** when any source has one; `"none"` and `null` treated as no setup.

## Verdict

**v7 OK — 420 rows, 159 noted. All 80 batch05 rows present with correct tier assignments.**