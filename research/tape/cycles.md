# loop cycles

| date | label | flag | decision | $/day a->b | green months a->b | H1 | H2 | trades | off book | on book | script |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-05 | the 1R first-target rule | MIN_PT1_R | hold | -9.0 -> 29.0 | 12 -> 12 | pass | fail | 767 | book_MIN_PT1_R_off.json.gz | book_MIN_PT1_R_on.json.gz | research/loop_cycle.py |
<!-- L2 referee repair 2026-09-05: two RULE84_DECIDED rows removed here. Both priced the unfiltered 28-symbol pool (loop_cycle.py did not apply loop.json's universe.row_filter) and the second was a duplicate append of the first. See research/l2_referee.md and the corrected row appended below by the fixed script. -->
| 2026-09-05 | the 84% re-entry as decided on the call | RULE84_DECIDED | hold | -52.0 -> -57.0 | 11 -> 11 | fail | pass | 769 | book_RULE84_DECIDED_off.json.gz | book_RULE84_DECIDED_on.json.gz | research/loop_cycle.py |
| 2026-09-05 | the one-candle-rule entry only when the retest candle is strong | OCR_RETEST_DISPLACEMENT | hold | -52.0 -> -58.0 | 11 -> 10 | fail | pass | 764 | book_OCR_RETEST_DISPLACEMENT_off.json.gz | book_OCR_RETEST_DISPLACEMENT_on.json.gz | research/loop_cycle.py |
| 2026-09-05 | the 15-minute structure trend test | TREND_DEF | hold | -52.0 -> -61.0 | 11 -> 10 | fail | pass | 768 | book_TREND_DEF_off.json.gz | book_TREND_DEF_on.json.gz | research/loop_cycle.py |
<!-- L4 repair 2026-09-05: a second, byte-identical TREND_DEF row (dropped) came from re-running --stage gate --dry-run just to re-print the same output, not a second experiment; it pushed consecutive_holds to 5 and tripped a false "stop" -- see loop_state.json's repair note. -->
