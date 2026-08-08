# engine_recall

Detection: `signal_runner.SignalRunner.detect_signals` (replayed bar-by-bar; see footer).

## Recall by tier — fired entries (all marks; +/-2 bars)
- **S: 13/77** detected
- **A: 9/60** detected
- **X: 6/22** detected

Precision: **34/92 = 37.0%** of engine entries on marked days land on a marked bar.

Denominators: join target `research/austin_marks_v2.jsonl` has 77 S / 60 A / 22 X (159, post-dedup). The spec's 78/60/24 are the pre-dedup `austin_verdicts.json` (162); the 3 collapsed rows are exact symbol|day|entry_i twins, so the detected counts are identical vs that base: S 13/78, A 9/60, X 6/24.

## Verdict
- Fired S recall is **13/77 = 17%**. The engine does not take the trades Austin grades S.
- Even the generous upper bound — ANY captured signal, ANY grade (incl. D-skips), every bar — is only S 35/77 = 45%. The engine produces NO signal at ~55% of S bars. (No-dedupe fired-only is also just S 14/77.)
- Of the 1466 signals the engine produces (raw, every bar), 1140 are downgraded to D and only 285 fire — mostly tight-stop kills (e.g. an S at the OR high with stop $0.22 on a $537 stock). A filter problem sits on top, but it is secondary: even counting every fired bar, S recall is 14/77 = 18%.
- This is a **detection problem, not a filter problem**. No gate on the trades the engine already takes can recover setups it never sees. The next version has to widen what the engine detects (level vocabulary / break-and-retest geometry), not tune what it filters.

## Recall — any signal, any grade (detection vs filtering)
- S: 30/77, A: 22/60, X: 13/22 — marks with ANY engine signal (incl. D/tight-stop skips, deduped) within +/-2 bars.
- S: 35/77, A: 30/60, X: 17/22 — same but counting EVERY captured signal bar (no dedupe; the true upper bound on 'the engine produced a signal here').
- No-dedupe FIRED only: S 14/77, A 10/60, X 9/22.
- Raw captured signal status mix: {'skipped_d': 1140, 'fired': 285, 'skipped_tight': 41}
- Raw captured signal grade mix: {'X': 1140, 'B': 57, 'C': 266, 'A+': 1, 'A': 2}

## Recall — testable marks only (archive present; isolates detection/filter from the 54 no-archive misses)
- Fired: S 13/77, A 9/60, X 6/22
- Any signal (deduped): S 30/77, A 22/60, X 13/22
- Any signal (raw, upper bound): S 35/77, A 30/60, X 17/22

## Precision detail
- Engine entries on marked days: **92**
- Landing on a marked bar: **34** (tier mix — matched mark's tier: S 18, A 9, X 7)
- Matched engine-entry grade mix: {'B': 24, 'C': 10}
- Engine entries on marked days Austin did NOT mark: **58**

## Method
- Marks: `research/austin_marks_v2.jsonl` (159 marks, 151 distinct symbol|day).
- Bars: `data_archive/<SYMBOL>/<DAY>.csv` RTH 1-min; 54 marks have no archive (engine cannot run -> counted as recall misses in the all-marks column; isolated in the testable-only column).
- Marked days with no archived bars: 0 (of 151).
- Replay: for each bar i in 5..N, `runner.candles = candles[:i+1]`; `runner.detect_signals()`. *Fired* entries = A+/A/B, or C with a viable stop (D and tight-stop-C are skipped by `SignalRunner._route`, captured separately for the any-signal column). One entry per setup idea per 30-bar window (backtest_week.DEDUPE_BARS); entry cutoff 11:00:00 (all marks fall before it).
- Level inputs reconstructed from the archive: PDH/PDL from the prior archived day, PMH/PML from the same day's 04:00-09:29 bars, HTF bias from prior days' close-vs-SMA20. 84% re-entries are not armed (need a stopped prior trade's state).
- A mark is *detected* if any engine entry bar is within +/-2 of the mark's entry_i.

Raw dumps: `research/engine_entries.jsonl` (92 fired entries, deduped) and `research/engine_signals.jsonl` (265 deduped all-grade signals; the raw per-bar capture is recomputed in-process for the mixes above) across all replayed days.
