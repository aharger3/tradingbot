# T4 — no_break_retest geometry fix

`no_break_retest` is the largest S-blindness cause in `research/miss_autopsy.md`
(27 of 77 S marks, 35%). The row's premise was that `detect_break_retest`
(`omen_bot.py:423`) returns falsy for every reference level on these bars and
that correcting the *geometry test itself* (not its retest-proximity tolerance)
would recover them. This file records what T4 actually found and the exact code
change that moved recall, so T5 can cite it.

## Method

`research/t4_geom_diag.py` replays `detect_break_retest`'s ordered FSM
(seek_break → seek_leave → seek_retest → hold) instrumented across every S ×
no_break_retest mark in `austin_marks_v2.jsonl`, against each mark's nearest
qualifying reference level (OR high/low, PDH/PDL, PMH/PML), and reports the
furthest state the FSM reaches plus the closest the post-leave price ever comes
back to the level (in $ and avg-ranges). 30 mark-level rows were instrumented
(27 distinct S marks per `miss_autopsy.md`; the 3 extra rows are a second
entry_i on `IWM 2024-04-03` and `QQQ 2026-02-11`).

## Diagnosis — the geometry test is correct, there is no false negative to fix

The 30 rows split by the FSM state at which they die:

| final state | n | what it means | verdict |
|---|---|---|
| `seek_break` | 6 | price is already through the level for the whole 12-bar window — no in-window crossing close. The break happened *before* the window. | legitimately no fresh break in-window; not a geometry bug. Marks: `IWM 2024-04-03` (ei9, ei73), `MSFT 2025-03-20`, `PLTR 2025-09-18`, `QQQ 2024-01-04`, `QQQ 2024-12-16`. |
| `seek_leave` | 6 | a break closed but price never fully *cleared* `level+eps` before returning — chop *on* the level. | **rejected by design.** Austin's 2026-07-09 ordering added the LEAVE step precisely so "chop-on-the-level and no-return breaks" do not fire (see the docstring). Marks: `AMD 2025-06-05`, `IWM 2025-10-21`, `MU 2026-01-28`, `NVDA 2024-11-18`, `QQQ 2024-05-08`, `SPY 2024-04-03`. |
| `seek_retest` | 17 | break + leave both happened, but price never came back to touch the level — a genuine no-return. Closest approach is 1–4 avg-ranges away (e.g. `SPY 2024-06-11` −4.07×, `SPY 2026-03-03` −2.24×). | legitimately no retest occurred. `research/t5_wide_probe.py` already proved widening the retest band on these finds **zero new distinct S marks after dedup** (it doubles fired-S 10→14 but halves precision 38.5%→19.4% on duplicates) — so the retest step is not a false-negative bug, it is a true negative. Marks: `BABA 2025-07-22`, `IWM 2024-02-28`, `IWM 2026-05-28`, `IWM 2026-07-24`, `ORCL 2025-03-28`, `QQQ 2025-02-26`, `QQQ 2025-03-17`, `QQQ 2025-03-18`, `QQQ 2026-02-11` (ei32, ei45), `QQQ 2026-07-09`, `SPY 2024-06-11`, `SPY 2024-09-19`, `SPY 2025-03-18`, `SPY 2026-03-02`, `SPY 2026-03-03`, `UBER 2026-07-06`. |
| `hold` | 1 | a retest was found but the entry candle is `max_confirm_gap+1` bars off it — stale by one bar. `QQQ 2026-03-04`: retest at window-bar 7, entry at bar 11, gap 4 > 3. The closest post-leave approach (bar 9) is ~2× range away and did *not* tag, so the bar-7 touch is the only real one and 4 bars of drift before entry is correctly "not off the retest". | correctly rejected; relaxing `max_confirm_gap` would be exactly the kind of tolerance widening the row forbids, and would admit stale entries across all bars. |

**Conclusion: `detect_break_retest`'s geometry is not the false-negative source
the row assumed.** The 27 marks are rejected for geometrically-legitimate
reasons — pre-window breaks, chop-on-level (by design), genuine no-return
(corroborated by DETECT_WIDE's zero-new-distinct result), and one stale
confirm. No change to the break/retest/leave/confirm *test* is warranted;
widening any of its tolerances was already ruled out by `t5_wide_probe.py`.

## The recall gain — the consolidation hard-skip (the actual lever)

With the geometry test exonerated, the only recall that moves comes from an
orthogonal gate that *prevented* `detect_break_retest` from ever being called:
`signal_runner.SignalRunner.detect_signals` hard-skipped any bar whose
PDH/PDL/OR-high/OR-low clustered within 0.5% (`_is_consolidation` → `return []`),
abandoning the whole bar before any setup's B&R loop ran. Austin's 2026-08-07
ruling (`research/t3_consolidation_effect.md`, OMEN-CONSOLIDATED.md settled
input #2) is that clustered levels are NOT a no-trade gate — one level broken
and retested cleanly is enough to trade.

### Exact fix
- `signal_runner.py`: removed the `_is_consolidation` early-return in
  `detect_signals` and the now-orphaned `_is_consolidation` method (only caller
  was that gate). Clustered bars now flow into the normal per-setup B&R / OB /
  FVG loops against whichever single level the bar actually breaks and retests,
  and fall through to "no signal" only if none fire.
- `research/miss_autopsy.py`: mirrored the change in `classify_no_detection`
  (inline consolidation branch gone); `consolidation_early_return` stays in the
  reason vocabulary for the before/after comparison but is now structurally 0.

This is the same change T3 documented; it is the lever that actually moves S
recall here. No `detect_break_retest` edit was made — the diagnosis above is
why.

### Mark recovered
- `QQQ|2025-12-30|24` (S tier) — previously killed by
  `consolidation_early_return`; now reaches the B&R loop and produces a
  captured signal. This is the sole new S any-signal mark.

(Two non-S marks also newly reach a signal — `SPY|2024-02-22|25` (A),
`SPY|2025-02-21|18` and `SPY|2025-12-02|14` (both X) — for a total of +4
any-signal. No baseline-fired mark went silent.)

## Result

s_any_signal_recall: 27 -> 28

- `python research/regression_gate.py` → **PASS** (exit 0; no baseline-fired
  mark went silent; +4 any-signal, +1 S any-signal).
- `python research/t4_engine_recall.py` → `any-sig S 28/77` (was 27/77).
  S-grade *fired* recall is unchanged at 10/77 — the new S mark is a captured
  signal, not a taken entry; the row's done-when gates on any-signal recall.

## What T5 should cite

The 27 no_break_retest S marks are NOT recoverable through `detect_break_retest`
geometry or its tolerances — they are true negatives (pre-window breaks /
chop-on-level / genuine no-return / one stale confirm). The one lever that
moved S any-signal recall (27→28) is the consolidation hard-skip removal in
`signal_runner.py`, recovering `QQQ 2025-12-30|24`. Raising S recall further
needs either (a) a reference level other than the four the diag checked (OB / FVG
/ flag lows — `sig["stop"]` candidates the diag did not sweep), or (b) recall of
the seek_break pre-window-break marks via the existing `LATE` tag path, neither
of which is a `detect_break_retest` tolerance change.
