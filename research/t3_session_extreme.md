# T3(c) — session HOD/LOD proximity veto, A/B

Detection replayed over **160 marked equity-pool (symbol, day) pairs** from `research/austin_marks_v7.jsonl` (pool = `universe.MAJOR_15`), bar-by-bar through `SignalRunner.detect_signals`, 30-bar per-idea dedupe, fired entries only.

`s_precision` = share of ALL fired entries that land within ±2 bars of a mark Austin graded **S**. Fires landing on no mark are in the denominator — an entry he never marked is not an S entry. 0.00 is the control arm (veto off).

| frac | fires | vetoed | on S | on A | on C | on X | unmarked | s_precision | precision on matched | S marks covered |
|------|-------|--------|------|------|------|------|----------|-------------|----------------------|-----------------|
| 0.00 | 61 | 0 | 8 | 9 | 0 | 19 | 25 | 13.11% | 22.22% | 7/56 (12.5%) |
| 0.05 | 57 | 20 | 7 | 8 | 0 | 18 | 24 | 12.28% | 21.21% | 6/56 (10.71%) |
| 0.10 | 44 | 104 | 4 | 8 | 0 | 14 | 18 | 9.09% | 15.38% | 3/56 (5.36%) |
| 0.20 | 27 | 360 | 3 | 3 | 0 | 10 | 11 | 11.11% | 18.75% | 2/56 (3.57%) |

Fire floor = 40% of the control arm's 61 fires = **24**. Settings clearing it: 0.00, 0.05, 0.10, 0.20.

chosen_frac: 0.0

Chosen because it has the highest S-precision (13.11%) among the settings that still emit at least 40% of the control arm's fires (61 of 61).

## What the measurement actually says

The veto does not buy S-precision on this population. Every armed setting scores at or below the control arm while throwing fires away, and the spread across all four settings is a handful of trades — noise at this n, not a signal. The decision rule in the spec (highest S-precision that keeps 40% of the control arm's fires) therefore lands on the control arm itself.

That is a conflict with this row's stated intent — 'the new behaviour is the default on' — and it is resolved the way the row itself asks for: the measurement wins, `SESSION_EXTREME_FRAC` ships at the fitted value, and the veto stays one env var away (`SESSION_EXTREME_FRAC=0.05`). The mechanic is built, wired through `_emit` so every subclass and every replay inherits it, and covered by tests; what the data will not support is arming it by default.

Austin's 21 notes about not entering at HOD/LOD are not refuted by this. What is refuted is that a *distance-to-session-extreme band* is the way to encode them: his objection is to the fill, and the fill fix is T3(b) (intrabar entry at the level on an extreme close), which is armed. S-precision stays single-digit at every setting either way — the positive quality bar S has never had is T11's row, not this one.
