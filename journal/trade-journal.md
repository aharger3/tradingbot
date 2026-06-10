---
title: Trade Journal
description: Daily signal tracking + execution log for alpha feedback
---

# Trade Journal

| Date | Time | Symbol | Signal Type | Direction | Entry Premium | Your Execution | Result (W/L/Scratch) | Notes | Missed Signals |
|---|---|---|---|---|---|---|---|---|---|
| 2026-05-27 | 10:51 | META | ONE_CANDLE_RULE | CALL ❌ | $13.59 | — | WRONG | Bot fired CALL — should have been PUT. Direction inverted. See Known Issues. | — |
| 2026-05-27 | ~10:51 | META | REENTRY_84_RULE | CALL ❌ | $13.59 | — | WRONG | Bot fired CALL — should have been PUT. Direction inverted. See Known Issues. | — |
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

## Known Issues

### Put-side logic needs separate tuning (flagged 2026-06-10)
The **2026-05-27 META 10:51 signal was wrong**: bot emitted CALL when the
correct read was PUT. Call-side and put-side detection in
`signal_runner.detect_signals()` are mirror images, but the put-side
(B&R short / OneCandle short / 84% short re-entry) is **unvalidated and
mis-firing direction**. Do NOT trust put signals yet.

TODO:
- Tune put-side thresholds independently from call-side (don't assume symmetry).
- Backtest 2026-05-27 META window to confirm corrected PUT trigger.
- Until validated, treat live PUT cards as informational only.

