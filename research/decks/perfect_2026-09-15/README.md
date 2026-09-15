# perfect_2026-09-15 -- 3 no-questions break-and-retest cards

Austin, 2026-09-15: "propose 3 S trades -- the really top trades where you say 'look at this, I have no questions, it's a perfect break-retest' -- and I can say yes on all of them."

Never a backtest run for this: reads the honest active baseline book only (`research/tape/baseline_2026-09-13.json.gz`, fill=close, his day policy) and the archive's own bars (`g80_ordertype_grid.day_pack`). No mark file touched.

## Selection filter

1. `setup == break_and_retest` (BR or BR+OCR)
2. `sgrade == S` (engine grade, Austin's S/A/C classifier ladder)
3. entry (`et`) between 09:35 and 10:30 ET
4. core-11 symbol (`tier == core`)
5. `status == fired` and `traded == true`
6. `out == win` and realized R >= +2
7. first scale point (the row's own PT1, `target`) >= 1R from entry
8. bar-level, read off the archive: the level's first close-through that day (the FIRST break) followed by a single retest that never closes back through the level a second time (no whipsaw)

## Candidates that passed every step

| step | passed |
|---|---|
| all baseline signals | 127574 |
| setup = break-and-retest (BR/BR+OCR) | 120195 |
| engine grade S | 13196 |
| entry 09:35-10:30 ET | 8328 |
| core-11 symbol | 3781 |
| fired and traded | 335 |
| win, realized R >= +2 | 9 |
| PT1 (first scale) >= 1R from entry | 9 |
| clean single retest (no whipsaw close back through the level) | 7 |

9 rows pass steps 1-7. Bar-level inspection (step 8) drops 2 of them for a genuine second leg, not a defect in the count:

- **AAPL 2026-02-23** (PDH, level PDH) -- closes back through the level multiple times between the break and the entry (a real round-trip, not one retest); kept out, not silently dropped.
- **AMD 2024-09-25** (pivot high, level not-his: pivot high @09:45) -- closes back through the level multiple times between the break and the entry (a real round-trip, not one retest); kept out, not silently dropped.

The remaining 7 clean rows: NVDA 2024-10-17, TSLA 2024-10-08, TSLA 2025-05-19, AMZN 2026-02-11, AMD 2025-05-07, AMD 2025-06-24, GOOGL 2026-03-11. The 3 shipped are the ones where the break bar, the retest bar and the entry bar are three distinct candles (so the chart tells break -> retest -> entry, not two labels stacked on one candle), preferring different symbols and different months over the other 4 (which repeat a symbol or fold the retest onto the entry bar).

## The 3 shipped

| id | entry | R | level | why |
|---|---|---|---|---|
| NVDA_2024-10-17 | 09:47 ET | +2.76 | pivot high @09:40 | gap-fade pivot high @09:40 breaks, one clean hammer retest bar at 09:46 within 11% of 1R of the level, entry 09:47, straight to +2.76R with no whipsaw. |
| AMD_2025-05-07 | 09:58 ET | +4.99 | OR low | OR low breaks at 09:49, an 8-bar orderly pullback closes within 6% of 1R of the level at 09:57 and never re-crosses it, entry 09:58 for +4.99R -- the cleanest R of the nine candidates. |
| GOOGL_2026-03-11 | 10:03 ET | +3.03 | pivot high @09:53 | pivot high @09:53 breaks at 09:58, an immediate one-bar retest at 09:59 holds 13% of 1R above the level, a 3-bar base, entry 10:03 for +3.03R. |

PNGs: `research/decks/perfect_2026-09-15/1_NVDA_2024-10-17.png`, `2_AMD_2025-05-07.png`, `3_GOOGL_2026-03-11.png`. Manifest: `research/decks/perfect_2026-09-15/manifest.json`. Builder: `research/build_perfect_deck_2026-09-15.py`.
