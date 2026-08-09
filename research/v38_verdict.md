# v38_verdict — omen-3.8 T6

Read-only synthesis of `research/t3_consolidation_effect.md`,
`research/t4_geometry_fix.md`, `research/engine_recall.md` (fresh re-run of
`research/t4_engine_recall.py`), `research/baseline_3.8.json`, and the final
`research/regression_gate.py` output. **No number here was recomputed and no
backtest was run.** Every figure is quoted from those files; the gate's exit
code is the only new fact and it is quoted verbatim. Flags confirmed OFF at
write time: `signal_runner.DETECT_WIDE = False`, `signal_runner.RULE_710_ENABLED
= False` (T5's state preserved — Rule 7/10 still not armed).

The three grep-able lines, in the form the row requires:

    s_grade_recall: 10/77
    any_signal_recall: 28/77
    gate exit code: 0

---

## 1. Final recall vs the T0 baseline

The T0 baseline (`research/baseline_3.8.json`, the locked state from PR#15) is
**S-grade fired 10/77** and **any-signal S 27/77** (with by_tier S = {fired 10,
any_signal 27, total 77}). The fresh `t4_engine_recall.py` re-run reports:

| metric | T0 baseline | final (this run) | delta |
|---|---|---|---|
| S-grade fired recall | 10/77 = 13.0% | **10/77 = 13.0%** | 0 — flat |
| any-signal S recall (deduped) | 27/77 = 35.1% | **28/77 = 36.4%** | +1 |
| fired A / X | 6/60, 6/22 | 6/60, 6/22 | 0 — flat |
| any-signal A / X | 22/60, 11/22 | 23/60, 13/22 | +1, +2 |

**S-grade fired recall is unchanged at 10/77.** T2–T5 moved zero S setups from
"engine sees it but won't take it" to "engine takes it." The one new S any-signal
mark — `QQQ|2025-12-30|24` — is a *captured* signal, not a *fired* entry
(`research/t4_geometry_fix.md`, "Result"): the consolidation hard-skip removal let
the bar reach the B&R loop, but the signal it produces there is not an A+/A/B/C-
viable entry the engine would take.

**The +1 to S any-signal recall is the consolidation removal, not the geometry
fix.** `research/t4_geometry_fix.md` instrumented `detect_break_retest`'s ordered
FSM across all 27 no_break_retest S marks and exonerated the geometry test: the
27 split into 6 pre-window breaks (`seek_break`), 6 chop-on-level
(`seek_leave`, rejected by Austin's 2026-07-09 LEAVE step by design), 17 genuine
no-return (`seek_retest`, corroborated by `t5_wide_probe.py` finding zero new
distinct S marks after dedup), and 1 stale confirm (`hold`). "No change to the
break/retest/leave/confirm test is warranted." The lever that actually moved S
any-signal recall is orthogonal — `research/t3_consolidation_effect.md`'s removal
of the `_is_consolidation` early-return in `signal_runner.detect_signals`, which
had abandoned the whole bar before any setup's B&R loop ran. That change
reclassified the 12 `consolidation_early_return` marks (4 S / 5 A / 3 X) into the
normal per-setup logic and recovered `QQQ|2025-12-30|24` as the sole new S
any-signal mark. `consolidation_early_return` is now structurally 0.

So the T2–T5 delta against T0 is exactly what T3/T4 documented: **+4 any-signal
(27→28 S, 22→23 A, 11→13 X = 60→64 total), +0 fired.** No S mark crossed from
detected to taken.

---

## 2. Final precision vs the T0 baseline

The T0 baseline locked precision at **25/65 = 38.5%** (`baseline_3.8.json`:
`precision_detail {matched: 25, engine_entries_on_marked_days: 65}`). The fresh
re-run reports **25/66 = 37.9%** (`research/engine_recall.md`).

The matched count is unchanged at 25; the denominator rose by one (65 → 66) —
the consolidation removal produced one additional engine entry on a marked day
that does not land within ±2 bars of any mark (an unmarked entry). Precision
therefore **fell by 0.6pp (38.5% → 37.9%)**, entirely from a wider denominator
with no new matches. This is the expected, mild cost of the T3 gate removal
documented in `t3_consolidation_effect.md` ("most reclassify to
no_break_retest / no_reference_level, a few now produce a signal") and is not a
regression in the gate's sense: the gate protects *fired marks*, not the
precision ratio, and precision is not a gated quantity. The precision floor the
project cares about — "do not arm `DETECT_WIDE` because it halves precision
(38.5%→19.4%)" (`v37_verdict.md` §2) — is intact; this run is within 0.6pp of
the T0 number and an order of magnitude above the 19.4% the widening would cost.

---

## 3. Zero baseline-fired marks regressed — the gate's own output

Final `python research/regression_gate.py` (exit code **0**), quoted verbatim:

```
baseline: any_signal 60, s_grade 10
current:  any_signal 64, s_grade 10
new fires (not a failure): any_signal +4, s_grade +0
by_tier: {'A': {'fired': 6, 'any_signal': 23, 'total': 60}, 'X': {'fired': 6, 'any_signal': 13, 'total': 22}, 'S': {'fired': 10, 'any_signal': 28, 'total': 77}}

PASS: no baseline-fired mark went silent.
```

**Explicit confirmation: zero baseline-fired marks regressed.** The gate diffs
the current fired/detected sets against the two locked sets in
`baseline_3.8.json` and fails only if a previously-fired mark goes silent. Here
`dropped_any` and `dropped_s` are both empty — the gate prints `PASS: no
baseline-fired mark went silent` and exits 0. Every mark the T0 engine fired on
or signalled within ±2 bars, the T6 engine still fires on or signals; the
T2–T5 changes only *added* detections (`any_signal +4, s_grade +0`, explicitly
"not a failure"). The four new any-signal marks are the consolidation removal's
reclassified bars (`t3_consolidation_effect.md`: +4 any-signal); none displaced a
baseline fire.

---

## 4. Is the 27/77 → 40%-gate distance closed enough to revisit DETECT_WIDE?

**No.** Per CLAUDE.md the standing bar is "no new gate until recall clears 40%",
and `v37_verdict.md` §5 frames `DETECT_WIDE` as dead at this recall level
("even if every S bar the engine detects also fired, recall would be 35% — under
40%").

Final any-signal S recall is **28/77 = 36.4%**. Clearing the 40% gate needs
**31/77 = 40.3%** — **three more S marks** than the engine currently produces any
signal for. The T2–T5 work closed the gap by **one** mark (27→28). At this
cadence the 40% bar is not in reach, and the ceiling that matters is still below
it: the *fired* metric the gate actually protects is flat at **10/77 = 13.0%**,
and the one new any-signal S mark is a captured signal the engine will not take
as an entry (`t4_geometry_fix.md`, "Result").

Three facts from T4 rule out the obvious lever:

1. **The retest-as-zone widening is already disproven.**
   `research/t5_wide_probe.py` (cited in `t4_geometry_fix.md`) found that widening
   the retest band on the 17 genuine no-return S marks recovers **zero new
   distinct S marks after dedup** — it doubles fired-S 10→14 but halves precision
   38.5%→19.4% on duplicates. `DETECT_WIDE` was the test of that idea and it
   failed (`v37_verdict.md` §2). Re-arming it would re-pay that cost for no new
   recall.

2. **The `no_break_retest` 27 are true negatives, not a geometry bug.**
   `t4_geometry_fix.md`'s FSM diagnosis shows they are pre-window breaks (6),
   chop-on-level by design (6), genuine no-return (17), and one stale confirm (1).
   "No change to the break/retest/leave/confirm test is warranted." A tolerance
   tweak on `detect_break_retest` cannot recover them.

3. **The only lever that moved recall is already pulled.** The consolidation
   hard-skip removal (`t3_consolidation_effect.md`) is the sole source of the +4
   any-signal / +1 S any-signal, and it is landed. There is no second gate of the
   same kind left to remove without re-introducing a trade-quality rule Austin
   deliberately set.

**Recommendation (do not arm):** do not revisit `DETECT_WIDE` or any new filter
this version. The 40% gate is not closed (28/77, three short), the fired metric
is flat at 10/77, and both candidate widening levers are already disproven or
exhausted. The path `t4_geometry_fix.md` names for the *next* increment is not a
filter — it is detection of reference levels the diag did not sweep (OB / FVG /
flag lows as `sig["stop"]` candidates) and recovery of the 6 pre-window-break
marks via the existing `LATE` tag path. Both are new detection vocabulary, not
`DETECT_WIDE` and not a precision filter, and neither is armed here.

---

## FOR AUSTIN
1. Final S recall is 10/77 fired (flat vs T0), 28/77 any-signal (+1 vs T0's 27/77) — the one new S is a signal the engine sees but won't take.
2. The +1 came from removing the consolidation hard-skip (T3), not the geometry fix (T4) — the 27 no_break_retest S marks are true negatives, not a bug.
3. Precision 25/66 = 37.9% vs T0's 25/65 = 38.5% — down 0.6pp from one new unmarked entry; still ~2× the 19.4% DETECT_WIDE would cost.
4. Regression gate exit 0: "PASS: no baseline-fired mark went silent." Zero T0 fires regressed; the +4 any-signal / +0 s_grade are additions, not losses.
5. Do not arm DETECT_WIDE or any new filter: any-signal S is 28/77 = 36.4%, three marks short of the 40% gate, and both widening levers are already disproven/exhausted.
6. Both flags stay OFF as T5 left them — DETECT_WIDE=False, RULE_710_ENABLED=False.
