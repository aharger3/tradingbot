# bar_coverage

Per-mark archive coverage for `research/austin_marks_v2.jsonl` (159 marks).

- Usable (archived RTH bars, entry_i in range): 105
- Dropped (no archive file): 54
- Dropped (entry_i out of range): 0

A mark is dropped iff its symbol/day has no `data_archive/<SYMBOL>/<DAY>.csv` or entry_i >= number of RTH bars. T3 feature computation skips and counts every dropped mark.

| symbol | day | entry_i | tier | has_rth_bars | n_rth | drop_reason |
|---|---|---|---|---|---|---|
| HOOD | 2025-08-04 | 40 | A | True | 596 |  |
| SOFI | 2026-03-11 | 63 | A | True | 595 |  |
| QQQ | 2025-06-25 | 48 | A | True | 594 |  |
| SPY | 2026-01-08 | 42 | X | True | 612 |  |
| MSFT | 2026-02-11 | 20 | A | True | 610 |  |
| QQQ | 2025-02-26 | 28 | S | True | 617 |  |
| SPY | 2026-02-09 | 24 | A | True | 612 |  |
| HOOD | 2026-05-19 | 19 | A | True | 530 |  |
| META | 2025-09-23 | 9 | A | True | 454 |  |
| NVDA | 2024-11-19 | 18 | A | True | 630 |  |
| COIN | 2025-10-21 | 8 | S | True | 500 |  |
| IWM | 2026-07-24 | 29 | S | False | 0 | no_archive_file |
| QQQ | 2025-06-24 | 15 | S | True | 586 |  |
| META | 2026-06-10 | 18 | X | True | 597 |  |
| SPY | 2024-10-22 | 41 | A | True | 553 |  |
| MARA | 2025-08-18 | 23 | X | True | 537 |  |
| IWM | 2024-04-03 | 13 | S | False | 0 | no_archive_file |
| IWM | 2024-04-03 | 73 | S | False | 0 | no_archive_file |
| AMZN | 2025-08-14 | 18 | X | True | 574 |  |
| CRM | 2025-07-02 | 17 | A | False | 0 | no_archive_file |
| MARA | 2025-04-02 | 14 | A | False | 0 | no_archive_file |
| BABA | 2025-07-22 | 20 | S | True | 504 |  |
| TSM | 2025-10-07 | 74 | A | True | 490 |  |
| QQQ | 2024-12-23 | 47 | A | True | 562 |  |
| CRM | 2026-05-07 | 18 | X | True | 513 |  |
| IWM | 2025-12-01 | 11 | S | False | 0 | no_archive_file |
| SPY | 2026-03-25 | 10 | X | True | 613 |  |
| AMD | 2026-04-21 | 35 | A | True | 594 |  |
| GOOGL | 2025-08-07 | 18 | S | True | 523 |  |
| QQQ | 2024-05-08 | 8 | S | False | 0 | no_archive_file |
| HOOD | 2025-03-04 | 44 | S | False | 0 | no_archive_file |
| INTC | 2025-06-05 | 10 | X | False | 0 | no_archive_file |
| QQQ | 2024-03-05 | 11 | A | False | 0 | no_archive_file |
| QQQ | 2024-03-05 | 21 | S | False | 0 | no_archive_file |
| QQQ | 2025-03-17 | 16 | S | True | 592 |  |
| SPY | 2024-04-03 | 9 | S | False | 0 | no_archive_file |
| GOOG | 2025-06-10 | 21 | A | False | 0 | no_archive_file |
| QQQ | 2026-02-11 | 32 | S | True | 607 |  |
| QQQ | 2026-02-11 | 45 | S | True | 607 |  |
| SPY | 2025-02-21 | 18 | X | True | 574 |  |
| IWM | 2025-09-05 | 12 | S | False | 0 | no_archive_file |
| IWM | 2025-09-05 | 51 | A | False | 0 | no_archive_file |
| QQQ | 2025-12-05 | 27 | S | True | 584 |  |
| QQQ | 2025-12-05 | 35 | S | True | 584 |  |
| CRM | 2025-06-02 | 27 | S | False | 0 | no_archive_file |
| QQQ | 2025-03-18 | 13 | S | True | 583 |  |
| SPY | 2025-06-02 | 40 | A | True | 580 |  |
| QQQ | 2024-01-04 | 41 | S | False | 0 | no_archive_file |
| MSFT | 2026-01-20 | 12 | S | True | 547 |  |
| IWM | 2024-02-28 | 9 | S | False | 0 | no_archive_file |
| IWM | 2024-02-28 | 18 | A | False | 0 | no_archive_file |
| AMZN | 2026-07-17 | 7 | A | False | 0 | no_archive_file |
| COIN | 2026-03-04 | 43 | A | True | 586 |  |
| MU | 2025-11-07 | 22 | S | True | 555 |  |
| QQQ | 2025-01-16 | 23 | S | True | 593 |  |
| QQQ | 2025-12-30 | 24 | S | True | 583 |  |
| GOOG | 2025-12-08 | 58 | X | False | 0 | no_archive_file |
| TSLA | 2026-02-18 | 42 | S | True | 614 |  |
| QQQ | 2024-10-03 | 18 | S | True | 598 |  |
| UBER | 2026-06-09 | 11 | A | True | 447 |  |
| NVDA | 2024-11-18 | 10 | S | True | 630 |  |
| QQQ | 2025-05-16 | 63 | A | True | 630 |  |
| IWM | 2025-04-10 | 16 | S | False | 0 | no_archive_file |
| MARA | 2025-05-14 | 23 | X | False | 0 | no_archive_file |
| GOOGL | 2024-09-03 | 10 | A | True | 520 |  |
| ORCL | 2025-11-03 | 17 | S | True | 556 |  |
| ORCL | 2025-03-28 | 12 | S | False | 0 | no_archive_file |
| IWM | 2025-10-21 | 9 | S | False | 0 | no_archive_file |
| HOOD | 2025-02-24 | 16 | A | False | 0 | no_archive_file |
| QQQ | 2024-08-23 | 36 | S | True | 526 |  |
| UBER | 2025-09-11 | 15 | S | True | 424 |  |
| GOOGL | 2024-10-15 | 32 | S | True | 470 |  |
| NVDA | 2024-12-16 | 12 | A | True | 630 |  |
| MSFT | 2025-03-04 | 13 | S | True | 513 |  |
| QQQ | 2025-01-10 | 13 | S | True | 536 |  |
| TSLA | 2024-03-27 | 13 | S | False | 0 | no_archive_file |
| QQQ | 2026-03-04 | 42 | S | True | 621 |  |
| MARA | 2026-07-09 | 19 | S | True | 518 |  |
| CRM | 2025-11-18 | 16 | A | True | 411 |  |
| NVDA | 2024-12-30 | 34 | A | True | 630 |  |
| MU | 2026-01-28 | 13 | S | True | 630 |  |
| SPY | 2025-09-25 | 45 | A | True | 576 |  |
| HOOD | 2026-04-13 | 16 | S | True | 621 |  |
| SPY | 2025-02-20 | 35 | A | True | 537 |  |
| TSM | 2026-05-29 | 23 | S | True | 520 |  |
| GOOG | 2026-02-23 | 19 | X | False | 0 | no_archive_file |
| MARA | 2026-07-17 | 13 | A | False | 0 | no_archive_file |
| SPY | 2024-02-22 | 25 | A | False | 0 | no_archive_file |
| UBER | 2026-01-06 | 22 | A | True | 462 |  |
| SPY | 2025-11-05 | 52 | A | True | 614 |  |
| QQQ | 2024-02-01 | 44 | X | False | 0 | no_archive_file |
| SPY | 2026-03-03 | 17 | S | True | 624 |  |
| IWM | 2024-03-22 | 24 | S | False | 0 | no_archive_file |
| SPY | 2025-03-18 | 13 | S | True | 583 |  |
| PLTR | 2024-10-23 | 21 | S | True | 603 |  |
| QQQ | 2026-07-09 | 11 | S | True | 595 |  |
| ORCL | 2026-06-09 | 8 | A | True | 594 |  |
| SPY | 2026-05-05 | 10 | A | True | 619 |  |
| AMD | 2026-05-14 | 25 | A | True | 549 |  |
| HOOD | 2026-02-05 | 40 | S | True | 629 |  |
| TSLA | 2024-12-03 | 8 | A | True | 617 |  |
| IWM | 2024-08-22 | 27 | S | False | 0 | no_archive_file |
| COIN | 2025-12-01 | 11 | A | True | 565 |  |
| QQQ | 2024-01-30 | 35 | X | False | 0 | no_archive_file |
| ORCL | 2025-07-08 | 7 | S | False | 0 | no_archive_file |
| TSLA | 2024-06-24 | 9 | S | False | 0 | no_archive_file |
| UBER | 2026-07-06 | 12 | S | True | 491 |  |
| QQQ | 2026-03-06 | 47 | X | True | 611 |  |
| MARA | 2025-07-30 | 30 | A | True | 614 |  |
| MARA | 2024-09-09 | 38 | X | False | 0 | no_archive_file |
| IWM | 2026-06-24 | 28 | A | False | 0 | no_archive_file |
| MARA | 2024-10-18 | 11 | S | False | 0 | no_archive_file |
| HOOD | 2026-07-07 | 37 | A | True | 548 |  |
| TSLA | 2024-02-05 | 16 | A | False | 0 | no_archive_file |
| MU | 2025-12-08 | 12 | X | True | 583 |  |
| UBER | 2025-07-31 | 48 | A | True | 468 |  |
| PLTR | 2026-03-31 | 23 | S | True | 565 |  |
| IWM | 2026-05-28 | 46 | S | False | 0 | no_archive_file |
| MARA | 2024-12-17 | 49 | S | False | 0 | no_archive_file |
| SPY | 2025-12-02 | 14 | X | True | 602 |  |
| AMD | 2025-06-05 | 6 | S | True | 605 |  |
| IWM | 2024-08-01 | 44 | A | False | 0 | no_archive_file |
| QQQ | 2024-03-15 | 11 | S | False | 0 | no_archive_file |
| MSFT | 2026-06-10 | 17 | A | True | 621 |  |
| UBER | 2025-02-07 | 22 | S | False | 0 | no_archive_file |
| CRM | 2025-09-26 | 12 | A | True | 407 |  |
| PLTR | 2025-09-18 | 14 | S | True | 586 |  |
| SOFI | 2024-10-30 | 16 | S | False | 0 | no_archive_file |
| QQQ | 2025-01-28 | 40 | A | True | 595 |  |
| QQQ | 2024-12-16 | 28 | S | True | 575 |  |
| MARA | 2026-07-20 | 11 | A | False | 0 | no_archive_file |
| SOFI | 2026-05-20 | 55 | A | True | 576 |  |
| NVDA | 2025-03-25 | 25 | A | True | 627 |  |
| COIN | 2025-06-26 | 18 | S | False | 0 | no_archive_file |
| TSLA | 2024-01-12 | 18 | X | False | 0 | no_archive_file |
| QQQ | 2025-05-07 | 31 | A | True | 581 |  |
| HOOD | 2025-12-29 | 12 | X | True | 495 |  |
| ORCL | 2025-09-17 | 11 | A | True | 580 |  |
| AMD | 2026-03-04 | 9 | A | True | 596 |  |
| AMZN | 2026-04-10 | 74 | A | True | 553 |  |
| UBER | 2025-08-13 | 25 | S | True | 453 |  |
| IWM | 2025-12-04 | 56 | S | False | 0 | no_archive_file |
| IWM | 2024-09-24 | 35 | X | False | 0 | no_archive_file |
| IWM | 2024-09-24 | 53 | X | False | 0 | no_archive_file |
| HOOD | 2026-07-10 | 23 | S | True | 547 |  |
| SPY | 2025-07-01 | 41 | A | True | 556 |  |
| GOOG | 2025-04-04 | 26 | A | False | 0 | no_archive_file |
| SPY | 2024-06-11 | 23 | S | False | 0 | no_archive_file |
| SPY | 2026-03-02 | 24 | S | True | 606 |  |
| COIN | 2026-04-09 | 30 | S | True | 562 |  |
| SPY | 2026-03-05 | 56 | S | True | 612 |  |
| NVDA | 2026-05-21 | 10 | A | True | 630 |  |
| MSFT | 2025-03-20 | 28 | S | True | 431 |  |
| BABA | 2025-12-26 | 36 | A | True | 439 |  |
| QQQ | 2025-07-01 | 72 | X | True | 567 |  |
| SPY | 2025-11-19 | 9 | S | True | 630 |  |
| SPY | 2024-09-19 | 19 | S | True | 562 |  |
| QQQ | 2025-02-25 | 16 | S | True | 612 |  |
| QQQ | 2025-02-25 | 53 | A | True | 612 |  |
