# engine_recall

Detection: `signal_runner.SignalRunner.detect_signals` (replayed bar-by-bar; see footer).

## Recall by tier — fired entries (all marks; +/-2 bars)
- **S: 4/77** detected
- **A: 3/60** detected
- **X: 1/22** detected

Precision: **10/33 = 30.3%** of engine entries on marked days land on a marked bar.

Denominators: join target `research/austin_marks_v2.jsonl` has 77 S / 60 A / 22 X (159, post-dedup). The spec's 78/60/24 are the pre-dedup `austin_verdicts.json` (162); the 3 collapsed rows are exact symbol|day|entry_i twins, so the detected counts are identical vs that base: S 4/78, A 3/60, X 1/24.

## Verdict
- Fired S recall is **4/77 = 5%**. The engine does not take the trades Austin grades S.
- Even the generous upper bound — ANY captured signal, ANY grade (incl. D-skips), every bar — is only S 19/77 = 25%. The engine produces NO signal at ~75% of S bars. (No-dedupe fired-only is also just S 4/77.)
- Of the 516 signals the engine produces (raw, every bar), 442 are downgraded to D and only 58 fire — mostly tight-stop kills (e.g. an S at the OR high with stop $0.22 on a $537 stock). A filter problem sits on top, but it is secondary: even counting every fired bar, S recall is 4/77 = 5%.
- This is a **detection problem, not a filter problem**. No gate on the trades the engine already takes can recover setups it never sees. The next version has to widen what the engine detects (level vocabulary / break-and-retest geometry), not tune what it filters.

## Recall — any signal, any grade (detection vs filtering)
- S: 18/77, A: 15/60, X: 4/22 — marks with ANY engine signal (incl. D/tight-stop skips, deduped) within +/-2 bars.
- S: 19/77, A: 17/60, X: 6/22 — same but counting EVERY captured signal bar (no dedupe; the true upper bound on 'the engine produced a signal here').
- No-dedupe FIRED only: S 4/77, A 3/60, X 2/22.
- Raw captured signal status mix: {'skipped_d': 442, 'fired': 58, 'skipped_tight': 16}
- Raw captured signal grade mix: {'D': 442, 'B': 20, 'C': 54}

## Recall — testable marks only (archive present; isolates detection/filter from the 54 no-archive misses)
- Fired: S 4/48, A 3/45, X 1/12
- Any signal (deduped): S 18/48, A 15/45, X 4/12
- Any signal (raw, upper bound): S 19/48, A 17/45, X 6/12

## Precision detail
- Engine entries on marked days: **33**
- Landing on a marked bar: **10** (tier mix — matched mark's tier: S 4, A 4, X 2)
- Matched engine-entry grade mix: {'B': 7, 'C': 3}
- Engine entries on marked days Austin did NOT mark: **23**

## Method
- Marks: `research/austin_marks_v2.jsonl` (159 marks, 151 distinct symbol|day).
- Bars: `data_archive/<SYMBOL>/<DAY>.csv` RTH 1-min; 54 marks have no archive (engine cannot run -> counted as recall misses in the all-marks column; isolated in the testable-only column).
- Marked days with no archived bars: 49 (of 151).
- Replay: for each bar i in 5..N, `runner.candles = candles[:i+1]`; `runner.detect_signals()`. *Fired* entries = A+/A/B, or C with a viable stop (D and tight-stop-C are skipped by `SignalRunner._route`, captured separately for the any-signal column). One entry per setup idea per 30-bar window (backtest_week.DEDUPE_BARS); entry cutoff 11:00:00 (all marks fall before it).
- Level inputs reconstructed from the archive: PDH/PDL from the prior archived day, PMH/PML from the same day's 04:00-09:29 bars, HTF bias from prior days' close-vs-SMA20. 84% re-entries are not armed (need a stopped prior trade's state).
- A mark is *detected* if any engine entry bar is within +/-2 of the mark's entry_i.

Raw dumps: `research/engine_entries.jsonl` (33 fired entries, deduped) and `research/engine_signals.jsonl` (157 deduped all-grade signals; the raw per-bar capture is recomputed in-process for the mixes above) across all replayed days.
