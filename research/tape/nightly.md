# nightly loop receipts

| date | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id |
|---|---|---|---|---|---|
| 2026-09-17 | - | empty | - | - | - |
| 2026-09-19 | - | empty | - | - | - |
| 2026-09-19 | BNR_DISPLACEMENT_GATE | ship | -52.0 -> -54.0 | 11 -> 11 | d5ba41a41d65e1e4 -> baafa4455388dedb |
| 2026-09-20 | SCALE_PLAN | ship | -52.0 -> -52.0 | 11 -> 11 | d5ba41a41d65e1e4 -> d5ba41a41d65e1e4 |
<!-- O4 repair 2026-09-20: the row above is corrected below, not edited in place (research/tape/scale_plan_noop.md). off_book_id == on_book_id was the tell -- SCALE_PLAN never reached backtest_week.py (it reads OMEN_SCALE_PLAN); the ON arm rebuilt the OFF arm's book. stage_gate() now records this shape as "noop", never "ship". -->
| 2026-09-20 | SCALE_PLAN | noop (correction: ON book_id == OFF book_id, flag not wired -- see comment above) | -52.0 -> -52.0 | 11 -> 11 | d5ba41a41d65e1e4 -> d5ba41a41d65e1e4 |
