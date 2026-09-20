# Corpus candidates -> loop flags (2026-09-19)

Source: `Desktop/Projects/omen-corpus/data/night/rule_candidates.jsonl` (16 rows,
`ops/night/rule_candidates.py`). `variables` there is a bare keyword match over
the compiled sentence (`_variables()` in that script: "reclaim" in text ->
`reclaim_tolerance`, no semantic link to any OMEN flag) -- so a candidate tagged
`reclaim_tolerance` is judged here on the RULE it states (does a reclaimed level
become tradeable structure?), not literally matched to `RULE84_RECLAIM_TOL`
(which only governs the 84%-rule stop-out re-entry, a different mechanism none
of these 16 candidates describe -- none mention a prior stop-out).

Checked against `research/tape/queue-plan.md` (the 84-flag audit: what's
already priced, excluded, or in the untested candidate pool) and
`research/tape/cycles.md` (what has actually been run, including the
RETEST_REQUIRED hold at -52 -> -87 on 2026-09-14).

Rule for "existing flag": the flag's own code must implement the candidate's
rule, cited by file:line -- not just be thematically adjacent.

| # | candidate (<=12 words) | maps to | flag / value | status |
|---|---|---|---|---|
| 1 | Weak candle closes below previous candle's low | needs code | n/a | See "needs code" spec below. |
| 2 | Break above a level, retest, continue higher | already priced | RETEST_REQUIRED (signal_runner.py:230) | cycles.md 2026-09-14: hold, -52.0 -> -87.0, H1 fail / H2 fail -- turning the retest requirement OFF was worse; shipped default (ON since 2026-09-02) already enforces "break, then retest, then go." |
| 3 | Reclaim above 410 with weekly higher-lows and daily gap | not testable | n/a | The engine's only level types are OR high/low, PDH/PDL, PMH/PML (signal_runner.py:1473) plus intraday pivots capped at a 30-bar/~30-min lookback (PIVOT_LOOKBACK, signal_runner.py:1494, "a swing from an hour ago is history"). No weekly-swing or daily-gap detector exists to evaluate the confluence this rule requires. |
| 4 | Reclaim of 360, resistance flipped into support | already priced | RETEST_REQUIRED (signal_runner.py:230) | Same cycle/verdict as row 2 -- a flipped level being reclaimed is exactly what the retest-required gate tests, independent of which specific price. |
| 5 | Break above previous day highs, retest continuation | already priced | RETEST_REQUIRED (signal_runner.py:230) | Same cycle/verdict as row 2. PDH is one of the six tracked levels (signal_runner.py:3154). |
| 6 | Break and retest premarket highs on HTF bias | existing flag | HTF_BIAS_GATE=1 (signal_runner.py:318, "daily-candle trend bias gate... only trade the daily trend") | Already queued in loop_queue.json (the "only trade with the daily-candle trend" row) -- not re-added here to avoid a duplicate run of the same flag. |
| 7 | Reclaim above the gap-fill high, bounce play | not testable | n/a | "Gap fill high" needs an overnight/opening-gap detector. The engine only has intrabar FVG gaps, and those are explicitly retired and excluded from tradeable (S-eligible) setups (RETIRED_SETUPS, signal_runner.py:1130; setup_is_s_eligible, signal_runner.py:1610-1613). PDL is tracked but is only context here, not the level actually being reclaimed. |
| 8 | Hammerstick candle confirms bullish retest entry | already priced | n/a (not flag-gated) | `_confirm_candle(long=True)` (signal_runner.py:91-99: lower wick >= body, close in top half) is exactly a bullish hammer-on-retest confirm, already applied unconditionally at BNR long entries (signal_runner.py:3276-3291, +2 grade points, "[hammer]" tag). Quantified pre-loop, 2026-07-11: hammer entries 42.4%W vs 33.8%W without. Always on, no toggle exists to A/B it further. |
| 9 | Reclaim with strength above 128 | existing flag | BNR_DISPLACEMENT_GATE=0 (signal_runner.py:179, default 1 -- requires a break-leg candle body >=1.5x the prior-10 average, i.e. "reclaim with strength," before the setup can grade above C) | Not yet queued. queue-plan.md's LAND C4 attempt to test this OFF was blocked purely on an archive-drift bug (cycles.md, 2026-09-13), fixed by LAND P the same day -- re-runnable now, and is queued below. |
| 10 | Reclaim above 640, prior all-time highs | not testable | n/a | "All-time highs" is not one of the engine's tracked levels (OR high/low, PDH/PDL, PMH/PML -- signal_runner.py:1473); no ATH or weekly-swing detector exists. |
| 11 | Undershoot then reclaim, push to all-time highs | not testable | n/a | Same reasoning as row 10. |
| 12 | Retest a level to the downside, bearish | already priced | RETEST_REQUIRED (signal_runner.py:230) | Same cycle/verdict as row 2 -- the short-side mirror of the same gate. |
| 13 | Hold above 740 toward premarket highs, daily gap | not testable | n/a | 740 is a discretionary number tied to "that full daily gap," which has no engine detector -- same gap-detection gap as rows 3 and 7. |
| 14 | Bullish above premarket highs, or pull back to PDH | already priced | RETEST_REQUIRED (signal_runner.py:230) | Same cycle/verdict as row 2. Both PMH and PDH are tracked levels (signal_runner.py:2200-2202, 3154-3156); the "hourly higher low" phrasing is Jdub's chart-reading commentary, not a distinct enforceable condition on this engine's 1-minute bars. |
| 15 | Previous day high break and retest, manage risk | already priced | RETEST_REQUIRED (signal_runner.py:230) | Same cycle/verdict as row 2. |
| 16 | Reclaim above previous day highs, swing higher | already priced | RETEST_REQUIRED (signal_runner.py:230) | Same cycle/verdict as row 2. Note: "swing trade" implies a multi-day hold this engine doesn't model (same-day exits only) -- only the entry trigger (PDH reclaim) was priced, not the hold duration. |

## Counts

- already priced: 8 (rows 2, 4, 5, 8, 12, 14, 15, 16)
- existing flag: 2 (rows 6, 9)
- needs code: 1 (row 1)
- not testable on the tape: 5 (rows 3, 7, 10, 11, 13)

## Needs-code candidate (spec row, not a build)

Row 1, "Weak candle closes below previous candle's low" (video 6sxCfeoGn8g,
Jdub, t=720s): add a short-side break-confirmation check requiring the
break/retest candle's close to sit below the PRIOR candle's low (mirror:
close above the prior candle's high for longs) before the setup can fire,
alongside the existing `_confirm_candle` hammer check at
`signal_runner.py:3554-3568` in the short break-and-retest block -- this is a
distinct, unimplemented confirmation pattern (`_confirm_candle` tests a
same-candle wick-rejection shape, not a close-through-the-prior-bar test), so
it needs its own flag (e.g. `PRIOR_LOW_CONFIRM`) rather than reusing one that
exists.

## Queued

Appended to `research/tape/loop_queue.json` (after the existing `_example`,
`HTF_BIAS_GATE`, `OCR_STRICT` entries):

- `BNR_DISPLACEMENT_GATE=0`, label "corpus: reclaim with strength above 128 (H8NxRPIx1V8)"

Row 6's match (`HTF_BIAS_GATE=1`) is already sitting in the queue under its
own label and was not duplicated.
