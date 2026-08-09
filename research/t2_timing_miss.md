# t2_timing_miss (omen-3.9 T2)

The `timing_miss` reason: the engine fired on a symbol-day but took a later, worse bar when a qualifying entry existed earlier. For every mark where the engine fired outside the +/-2 tolerance, the bars between the mark and the engine's nearest later fired entry are replayed through the engine's own `detect_break_retest` / `detect_order_block_setup` (via `classify_no_detection` — detection is not reimplemented). If any earlier bar than the engine's would itself have produced a signal, the mark is `timing_miss`; otherwise it stays `fired_wrong_bar`. `timing_miss` is checked before `fired_wrong_bar` and takes precedence.

## Counts

- timing_miss (all tiers): 6
- timing_miss S: 4
- fired_wrong_bar (all tiers): 11
- fired_wrong_bar S: 6

timing_miss_S: 4

## S marks reclassified from fired_wrong_bar to timing_miss

| symbol | day | entry_i | detail |
|---|---|---:|---|
| COIN | 2025-10-21 | 8 | engine fired later at bar 31 but bar 23 (8 bar(s) earlier) would have produced a signal; mark at bar 8, engine fired at [31, 62] |
| MARA | 2024-12-17 | 49 | engine fired later at bar 78 but bar 76 (2 bar(s) earlier) would have produced a signal; mark at bar 49, engine fired at [78] |
| ORCL | 2025-11-03 | 17 | engine fired later at bar 30 but bar 25 (5 bar(s) earlier) would have produced a signal; mark at bar 17, engine fired at [30] |
| TSLA | 2024-06-24 | 9 | engine fired later at bar 14 but bar 13 (1 bar(s) earlier) would have produced a signal; mark at bar 9, engine fired at [14] |

