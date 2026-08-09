# T3 — consolidation early-return removal

`signal_runner.SignalRunner.detect_signals` hard-skipped any bar whose PDH/PDL/
OR-high/OR-low all sat within 0.5% of their mean (`_is_consolidation` → `return []`),
abandoning the bar before any setup was tested. Austin's ruling
(OMEN-CONSOLIDATED.md, settled input #2, 2026-08-07): clustered levels are NOT a
no-trade gate — one level broken and retested cleanly is enough to trade.

## Change

- `signal_runner.py`: removed the `_is_consolidation` early-return gate in
  `detect_signals` (and the now-orphaned `_is_consolidation` method, whose only
  caller was that gate). Clustered bars now flow into the normal B&R / OB / FVG
  loops against whichever single level the bar actually breaks and retests, and
  fall through to "no signal" only if none of them fire.
- `research/miss_autopsy.py`: mirrored the change in `classify_no_detection`
  (the inline consolidation branch is gone); `consolidation_early_return` stays
  in the reason vocabulary for the before/after comparison but is now
  structurally 0 (like `not_armed_84`).

## Effect

The 12 marks the classifier previously killed as `consolidation_early_return`
(4 S / 5 A / 3 X) are reclassified by the normal per-setup logic — most to
`no_break_retest` / `no_reference_level`, a few now produce a signal. No
baseline-fired mark went silent (`research/regression_gate.py` PASS); any-signal
recall rose 60 → 64 (+4 new fires), S-grade fired recall unchanged at 10/77.

consolidation_early_return: 12 -> 0
