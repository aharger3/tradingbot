# T4 — `no_break_retest` geometry fix (omen-3.8)

**Goal.** `no_break_retest` is the single biggest S-recall lever: 27 of 77 S marks
(35%) are misses where `detect_break_retest` (`omen_bot.py`) returned falsy for
every reference level (`research/miss_autopsy.md`). This row fixes the geometry
test itself — not its tolerance — and re-runs the gate.

## Diagnosis — why the retest never registers

`research/t5_wide_probe.py` already proved the tolerance knob
(`retest_tol_mult` / `DETECT_WIDE`) is the wrong lever: widening the retest
proximity band roughly doubles fired-S (10→14/77) but halves precision
(38.5%→19.4%) and finds **zero new distinct S marks after dedup**. So the
blocker is structural, not "price stopped a hair short of the level."

Instrumenting the FSM (`research/t4_diag.py`) over the 27 S×`no_break_retest`
marks shows the furthest state reached per mark, at the marked bar, against the
level the classifier offers:

| baseline blocker | S marks | meaning |
|---|---:|---|
| `stalled_at_seek_retest` | 14 | broke → left → **never came back to tag** (no-return break — genuine, LEAVE step was added to filter exactly this) |
| `stalled_at_seek_leave`  | 6  | broke but never fully cleared the level |
| `stalled_at_seek_break`  | 5  | **no break registered in the 12-bar window** |
| `cur_not_through_level`  | 1  | confirm candle not back through |
| `confirm_gap_too_stale`  | 1  | retest too far from confirm |

The recoverable marks are the `stalled_at_seek_break` / late-`seek_retest`
group, and the root cause is the **12-bar window**, not the retest touch test.
Two failure shapes, both confirmed on the candles (`research/t4_recover_diag.py`):

1. **Break early, retest/confirm late.** The break is early in the session and
   the retest lands 10+ bars later. At the entry (confirm) bar the break has
   scrolled out of the 12-bar window, so the FSM starts in `seek_break` over a
   window that no longer contains the break and stalls with an empty sequence.
   - `PLTR 2025-09-18 i=14` (PMH=172.0 long): break @j2, leave @j3, retest @j13
     — the retest is **11 bars after the break**. A 12-bar window ending at the
     confirm bar cannot hold both; `win12` stalls at `seek_break` (empty seq),
     `win20` completes `break→leave→retest@13→confirm`, gap 0.
2. **Recent-window eps swallows the early break.** Even when the break is
    within ~12 bars, the `eps = 0.10 × avg_rng` is recomputed over the recent
    (often wider) window, so a modest early break fails `close > level + eps` and
    no `seek_break` ever latches.
   - `IWM 2026-05-28 i=46` (ORhi=289.88 long): the 20-bar window sees
     `break@15 → leave@17 → retest@19 → confirm` (gap 0); the 12-bar window,
     with its larger recent `avg_rng`, registers no break at all.

The 14 `stalled_at_seek_retest` marks are **not** recovered by this fix and should
not be — they are no-return breaks (price broke and ran without retesting),
which is exactly the chop/no-return class the LEAVE step was added to reject
(`omen_bot.py` docstring; `test_break_retest.py` `no_return` / `short_no_return`).
Reaching those needs a different setup, not a wider window.

## The fix (geometry, not tolerance)

When the tight caller-requested window (default 12 bars / 3-bar confirm gap)
finds **no** valid sequence, `detect_break_retest` retries **once** over a wider
window + confirm gap (`BR_WIDE_WINDOW=20`, `BR_WIDE_GAP=6`). New module constants
in `omen_bot.py`; the retry lives at the bottom of `detect_break_retest`:

```python
note = _pass(window, max_confirm_gap)
if note is None and (BR_WIDE_WINDOW > window or BR_WIDE_GAP > max_confirm_gap):
    note = _pass(BR_WIDE_WINDOW, BR_WIDE_GAP)
return note
```

Why this shape and not a simpler primary widening:

- **Strict superset for detection.** A bar the tight window already fires is
  returned unchanged, so the retry can only *add* fires, never replace one.
  `research/t4_final_sweep.py` confirms: widening the *primary* window (16/20/24)
  **regresses** — it latches onto an earlier break and shifts/suppresses a
  fire, dropping `HOOD|2025-02-24|16`. The fallback drops nothing.
- **Tolerance untouched.** `retest_tol_mult` / `DETECT_WIDE` is left exactly as
  is (shipped OFF). The retry passes the caller's `retest_tol_mult` through, so
  the exact-touch test (0.0) is preserved on both passes.
- **Tagged.** A fire completed by the wide pass is tagged `| WIN20/G6` in the
  note so the entry log / A-B can separate fallback fires from tight ones.
- **Tests unchanged.** `test_break_retest.py` and `test_detect_wide.py` pass
  byte-for-byte: every existing case either fires on the tight pass (no retry)
  or has no retest at all (the retry over the same short array cannot invent
  one).

## Recovered marks (named, for T5 to cite)

Four S any-signal marks recovered, three as full fired entries:

| mark | side / level | why 12-bar missed | how 20-bar completes |
|---|---|---|---|
| `IWM\|2026-05-28\|46` (fired) | long / ORhi 289.88 | early break swallowed by recent-window eps; `seek_break` empty | break@15→leave@17→retest@19, confirm gap 0 |
| `PLTR\|2025-09-18\|14` (fired) | long / PMH 172.0 | retest 11 bars after the break — outside any 12-bar window | break@2→leave@3→retest@13→confirm, gap 0 |
| `QQQ\|2025-12-05\|35` (fired) | long / ORhi 626.67 | at the mark bar the 12-bar window has lost the break | 20-bar re-arms a fire at bar 35 (retest@15, gap 4≤6) that clears grade/dedupe where the earlier bar-33 fire did not |
| `PLTR\|2024-10-23\|21` (sig-only) | — | same early-break/late-retest shape | captured as a signal (skip-grade) — +1 any-signal, not a fired entry |

Three more non-S marks also newly signalled (any-signal, not gated):
`AMZN|2025-08-14|18` (X), `MARA|2024-09-09|38` (X), `MARA|2025-07-30|30` (A).

## Results

`research/regression_gate.py` → **exit 0** (PASS). No baseline-fired mark went
silent. New fires: any_signal +7, s_grade +3.

`python research/t4_engine_recall.py` (fresh, after the code change):

| metric | before | after |
|---|---|---|
| **S any-signal recall** | **27/77** | **30/77** |
| S fired (entries) | 10/77 | 13/77 |
| S raw-signal | 29/77 | 35/77 |
| precision | 25/65 = 38.5% | 34/92 = 37.0% |

(The regression gate's `any_signal` set — fired OR any captured signal — goes
27→31 for S; the +4 vs the printed `any-sig` +3 is `QQQ|2025-12-05|35`, which is
a fired entry whose bar is deduped out of the captured-signal stream. Both
metrics rise; the printed `any-sig` line is the one the done-when references.)

Precision edges down ~1.5pp (38.5%→37.0%) because the wider fallback pass fires
more entries on marked days generally; recall is the gated objective and the
regression gate protects the existing fired set.

## What was NOT changed
- `retest_tol_mult` / `DETECT_WIDE` — untouched (benched path).
- The LEAVE step and the adverse-wick / eps-buffer rules — unchanged on both
  passes.
- No new dependency, no caller changed; `signal_runner.py` calls
  `detect_break_retest` with defaults as before.
