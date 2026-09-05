# loop cycles

| date | label | flag | decision | $/day a->b | green months a->b | H1 | H2 | trades | off book | on book | script |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-05 | the 1R first-target rule | MIN_PT1_R | hold | -9.0 -> 29.0 | 12 -> 12 | pass | fail | 767 | book_MIN_PT1_R_off.json.gz | book_MIN_PT1_R_on.json.gz | research/loop_cycle.py |
<!-- L2 referee repair 2026-09-05: two RULE84_DECIDED rows removed here. Both priced the unfiltered 28-symbol pool (loop_cycle.py did not apply loop.json's universe.row_filter) and the second was a duplicate append of the first. See research/l2_referee.md and the corrected row appended below by the fixed script. -->
| 2026-09-05 | the 84% re-entry as decided on the call | RULE84_DECIDED | hold | -52.0 -> -57.0 | 11 -> 11 | fail | pass | 769 | book_RULE84_DECIDED_off.json.gz | book_RULE84_DECIDED_on.json.gz | research/loop_cycle.py |
