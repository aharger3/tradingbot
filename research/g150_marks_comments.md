# g150: Merged Comments Corpus

Merged all `research/g150_marks_comments_part*.jsonl` files into one.

## Summary

- Total rows read from parts: 2,730
- Exact duplicates (symbol, day, source_file, card_id, comment): 55
- Final unique rows: 2,675
- Rows with non-empty comment: 1,521
- Comments over 40 characters: 896

## By Source

| source_file | count |
|---|---:|
| austin_marks_v7.jsonl | 479 |
| recovered_reviews.jsonl | 176 |
| research/blind_marks_all.jsonl | 260 |
| marks_clean | 220 |
| austin_verdicts.json | 158 |
| probe_omen_test1_2026-08-27.jsonl | 100 |
| probe_s_sweep_2026-08-28.jsonl | 100 |
| v2 | 159 |
| probe_master_2026-08-29.jsonl | 123 |
| probe_g84_all_in_one_STANDING154_2026-09-01.jsonl | 139 |
| deck_marks_index_2026-08-19 | 97 |
| deck_marks_tsla_2026-08-20 | 87 |
| batch05 | 80 |
| mark_batch_02_grades.jsonl | 60 |
| deck_marks_h2_3lane_2026-08-28.jsonl | 59 |
| probe_master_homework_2026-08-26.jsonl | 51 |
| mark_batch_04_grades.jsonl | 35 |
| probe_g71_homework_s3_2026-08-29_complete.jsonl | 30 |
| v3 | 25 |
| probe_g71_homework_s3_2026-08-29.jsonl | 25 |
| rule_ballot_batch02.jsonl | 28 |
| mark_batch_03_regrades.jsonl | 29 |
| probe_autopsy_2026-08-23 | 15 |
| derived_marks_v1.jsonl | 14 |
| derived_marks_v2.jsonl | 18 |
| rule_ballot_batch01.jsonl | 20 |
| v5 | 30 |
| v6 | 9 |
| probe_head2head_2026-08-24 | 9 |
| probe_trade_anatomy_2026-09-01 | 8 |
| regrade_confirm_2026-09-03.jsonl | 2 |
| (empty source_file) | 18 |
| **Total** | **2,675** |

## By Grade

| grade | count |
|---|---:|
| S | 491 |
| A | 526 |
| C | 72 |
| B | 14 |
| X | 319 |
| none | 767 |
| (empty/blank) | 486 |
| **Total** | **2,675** |

## Check Script

Verify with `python research/g150_check.py`
