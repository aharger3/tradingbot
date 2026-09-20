# t61 -- precision A/B of queued flags (2026-09-20)

Rig: `research/t61_onwatch_ab.py --compare`, 120 graded day-cards
(`t60_baseline.load_day_cards`), Austin's S/A/C/none ladder -- the rig does not
expose the engine's own A+/A/B/C/X ladder (see reading #2). Precision here is
card-level: fired days graded S / all fired days -- a different unit from the
pick-level 30.5% (18/59) bar in `g215_precision.md` (one-trade-a-day arm, full
500-day book), so don't average the two. Each flag run vs the current default,
one process per value (env var read once at import).

| flag | value tested | S-day recall | precision (fired&S/fired) | fires/day | false fires |
|---|---|---:|---:|---:|---:|
| (current default) | -- | 18/28 (64.3%) | 18/79 (22.8%) | 1.62 | 42/61 |
| HTF_BIAS_GATE | 1 (default 0) | 18/28 (64.3%) | 18/79 (22.8%) | 1.62 | 42/61 |
| OCR_STRICT | 1 (default 0) | 18/28 (64.3%) | 18/79 (22.8%) | 1.53 | 42/61 |
| COUNTER_TREND_CAP | 1 (default 0) | 18/28 (64.3%) | 18/79 (22.8%) | 1.62 | 42/61 |
| BNR_DISPLACEMENT_GATE | 0 (default 1) | 18/28 (64.3%) | 18/79 (22.8%) | 1.62 | 42/61 |
| ENTRY_FLOOR_STOP | 1 (default absent) | 18/28 (64.3%) | 18/79 (22.8%) | 1.62 | 42/61 |

## Reading

1. None of the five queued flags move S-day recall, card precision, or false
   fires on the 120-card corpus -- every A vs B pair is identical at the day level.
2. HTF_BIAS_GATE, COUNTER_TREND_CAP and BNR_DISPLACEMENT_GATE only touch the
   engine's grade cap/veto on entries `run_day` already returns; t61 counts
   fire/no-fire per day, not grade, so a downgrade-not-delete is invisible to it.
3. OCR_STRICT is the one flag with any measurable effect: -11 raw signals
   (195->184, fires/day 1.62->1.53), all "extra" fires on days that already had
   one -- no day flips fired/unfired, so recall, precision and false fires hold.
4. ENTRY_FLOOR_STOP is not wired into `signal_runner.py` (grep confirms); it's a
   `backtest_week.py` stop-widening policy consumed after entry (the g88 money
   rig), so t61 -- which only calls `signal_runner`/`run_day`, never
   `backtest_week` -- cannot see it. The row above is a no-op sanity check.
5. Verdict: none of the five moves precision above 30.5% by this rig. OCR_STRICT
   is the only real signal (fewer fires, same recall -- worth pricing for $/day
   on the money rig); the grade-cap flags and ENTRY_FLOOR_STOP are noise or
   out-of-scope for a detection A/B and belong to a money/grade rig instead.
