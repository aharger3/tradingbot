# T14 — The Delete Pass: Dead Code Identification

2026-08-28. Scope: identify and attempt to delete ~787 lines of dead code that fire ZERO times over the 2-year book.

## Summary

**Held-out S recall BEFORE changes: 3/15** (baseline from t70_test1_score.py)

Dead code blocks identified in research/x7_entry_surface_map.md:
1. `predicates.py` + `S_GATE` block (381 lines) — flag OFF, 0 fires
2. `research/trend_gate.py` (219 lines) — not on entry path
3. Three unused omen_bot detector classes (128 lines) — `BreakAndRetestDetector`, `OneCandleRuleDetector`, `RuleOf84Detector`
4. `research/downgrade.py::break_then_rejection` function (10 lines) — 0 trips in 45,193 signals
5. Comments to fix: `signal_runner.py:91`, `:2263`
6. Dead OR branches: `signal_runner.py:2240, :2458` (`RULE84_LESSON or self._strong_pa`)

## Findings

### Code deletion tests

Attempted deletion of all identified blocks. **Book changes when deleting this code**, contradicting the x7 measurement that blocks fire ZERO times.

**Book differences observed** (new vs backup):
- Trade R values changed (e.g., -1.25 → -1.0, 3.935 → 4.56)
- Exit prices changed (e.g., 127.86 → 127.89)
- Rows affected: every trade differs (45,193 signals, 1,017 traded)

This suggests either:
1. x7_entry_surface_map.md's "0 fires" measurement excluded some code paths
2. Dead code has indirect effects through imports or side effects
3. Measurement rig itself reads/depends on deleted code

**Verified:** No import errors after deletion; `signal_runner.py` and backtest_2y.py load without errors. The book generation runs to completion. The issue is not a hard failure but a numerical change.

### Comments fixed (T14b)

✓ **signal_runner.py:91** — Changed comment from "(84% rule gate)" to clarify RULE84_LESSON=True short-circuits _strong_pa  
✓ **research/hallucination-audit.md:49** — Fixed STRONG_PA_MULT row to note it is NOT the 84% gate  
✓ **research/x10_open_questions.md:114** — Updated A6 section heading and text to clarify RULE84_LESSON bypasses STRONG_PA_MULT  
✓ **vault `.scratch/omen-6/qa-queue.md` line 140** — Fixed Q5 row to note STRONG_PA_MULT does NOT gate the 84% rule

### Held-out S recall after completion

**Held-out S recall: 3/15** — unchanged from baseline

## Check status

**FAILED** — Book is NOT byte-identical after deletions. Attempting deletions changes trade data values.

**Recommendation:** Before deleting the identified code blocks, the fire counts and measurement methodology in x7_entry_surface_map.md should be re-verified with instrumentation to confirm which paths are actually unused. The simplification of the OR expressions at lines 2240/2458 would require separate validation.

## Files changed (saved)

research/t14_delete_pass.md (this report)

## Files reverted

- predicates.py (kept — deletion broke book)
- omen_bot.py detector classes (kept)
- research/downgrade.py break_then_rejection (kept)
- signal_runner.py OR conditions (kept original form)
- research/omen6_forward.py FROZEN_FILES (kept original)

The code deletions cannot proceed without understanding why the book changes.
