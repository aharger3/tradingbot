---
title: Trade Journal
description: Daily signal tracking + execution log for alpha feedback
---

# Trade Journal

| Date | Time | Symbol | Signal Type | Direction | Entry Premium | Your Execution | Result (W/L/Scratch) | Notes | Missed Signals |
|---|---|---|---|---|---|---|---|---|---|
| 2026-05-27 | 10:51 | META | ONE_CANDLE_RULE | CALL | $13.59 | — | — | Did not run bot this morning | — |
| 2026-05-27 | ~10:51 | META | REENTRY_84_RULE | CALL | $13.59 | — | — | Did not run bot this morning | — |
| 2026-05-28 | — | — | — | — | — | — | — | 0 signals in 9:30-11 window | Any you caught? |

## Instructions

**After each 9:30-11 ET trading window:**
1. Copy bot signals from Discord into this journal (Date, Time, Symbol, Signal Type, Entry Premium)
2. If you executed: log Your Execution price + Result
3. If missed opportunity: note in "Missed Signals" column
4. End-of-day: review what fired, what you caught, what you missed
5. Feedback to Claude: which misses were obvious? which false positives?

**Result codes:**
- W = Won (hit target)
- L = Lost (hit stop)
- Scratch = Closed flat
- — = Not executed or still open

