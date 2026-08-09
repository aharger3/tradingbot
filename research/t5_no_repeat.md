# t5_no_repeat — the no-repeat idea-key rule, measured (not armed)

**Source row:** omen-3.9 T5. **Flag:** `signal_runner.ENFORCE_NO_REPEAT` (default
**OFF**). **Harness:** `research/t5_no_repeat_effect.py`.

## What the rule does

T4 built `idea_key(sig) = (symbol, direction, level NAME)` and used it inside
`compute_austin_tier`'s clause 3 ("first S of this idea today") as a *reported*
field. T5 turns that same identity into an actual routing decision:

- The runner keeps a per-session `self._fired_ideas` set of the `idea_key` of
  **every signal it accepts**.
- When `ENFORCE_NO_REPEAT` is **True** and a new signal's `idea_key` is already
  in that set, the signal is skipped with `sig["reason"] += " [skip: repeat
  idea]"` — i.e. the engine no longer takes the same trade a second time.
- `SignalType.REENTRY_84_RULE` is the one exemption: the armed 84% re-entry *is*
  by definition the sanctioned second bite at the same idea, so it is always
  allowed through.
- When the flag is **False** the set is still maintained (clause 3 and the
  report read it) but nothing is skipped — so shipped behaviour is
  byte-identical to today, which is what `research/regression_gate.py` proves.

## The measurement

`t5_no_repeat_effect.py` replays the 159 v2 marks twice through the engine's
real `_route` — once with the flag off (today), once with it forced True
in-process — and diffs the two. The flag-off fired set reproduces the
regression gate's locked `fired_entry_marks` exactly (22 marks hit, matching
`baseline_3.8.json`), so the diff is against the true production baseline, not
a toy.

    repeat_entries_suppressed: 1
    baseline_marks_lost: 0

- **1 engine entry** (of 66 the engine takes across the marked days) is a
  same-idea duplicate the rule would drop.
- **0 baseline-fired marks** go silent: the one suppressed entry lands on no
  marked trade within ±2 bars. Lost marks by tier: `{}` (no S, no A, no X).

## Is it safe to flip?

**Yes.** Arming `ENFORCE_NO_REPEAT` would suppress exactly one duplicate
engine entry and lose **zero** of the trades Austin currently takes — not one
of the 22 fired marks (10 of them S-tier) disappears. The rule's only effect in
this corpus is to silence a repeat fire on an idea that already fired, which is
the noise it is meant to silence. The 84% re-entry exemption means the second
bite Austin *does* want can never be collateral.

The flag still ships OFF because arming it is Austin's call, but the data says
flipping it to True is free here: no marked trade is the price.

## Method

- Marks: `research/austin_marks_v2.jsonl` (159, the v2 set T1 settled).
- Bars + levels: `data_archive/<SYMBOL>/<DAY>.csv` RTH 1-min, reconstructed
  via `t4_engine_recall` (PDH/PDL from the prior archived day, PMH/PML from
  the same day's 04:00–09:29 bars, HTF bias from prior close-vs-SMA20) — the
  same structure `live_scanner` would feed the engine.
- Replay: for each bar `i` in 5..N before the 11:00 cutoff,
  `runner.candles = candles[:i+1]`; `runner.detect_signals()`. Fired entries
  = accepted by `_route` (grade not skip, C-with-viable-stop or B+), then
  production-deduped one-per-setup-idea per 30-bar window
  (`backtest_week.DEDUPE_BARS`). `_fired_ideas` persists across bars within a
  day (one runner per day), mirroring a live session.
- `repeat_entries_suppressed` = fired entries present with the flag off but
  absent with it on (no-repeat only ever removes; the script asserts the
  on-set is a subset of the off-set).
- `baseline_marks_lost` = marks with a fired entry within ±2 bars today that
  have **no** fired entry within ±2 bars with the rule on.
- The 84% re-entry is not armed in a detection-only replay (it needs a stopped
  prior trade's state), so it never fires here; it is named only to document
  the one exemption the rule carries.
