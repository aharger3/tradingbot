# g182 — B3 (bug B-01): the S/A ladder round trip

What is different now: `research/t70_test1_score.LADDER` is fixed so it scores
the CURRENT engine correctly, and `research/test_downgrade_grader.py` passes;
`signal_runner.SAC_TIER`'s half of the same bug is **deferred** — fixing it
collides with a different, already-shipped, already-passing design decision,
not just a stale mapping.

## Root cause (both halves, one commit)

`394bcfe0` ("Retire A+ and route the live path on his S grade instead")
changed what `_grade_pa`'s `CLEAR_FOR_APLUS` promotion writes — the full-stack
promotion that used to write `TradeGrade.A_PLUS` now writes `TradeGrade.A`,
and the old `TradeGrade.A` rung (his A, "clear of levels" but not full stack)
shifted down to nothing but `TradeGrade.B`. The engine's own alphabet moved:
**`A` is now the top tier, `B` is the middle one** — where before A+/A/B were
three distinct rungs.

Two other tables translate his S/A/C onto that alphabet and neither moved
with it:

- `t70_test1_score.LADDER` (engine tier -> his grade), used to score the
  CURRENT engine's live output against 100 held-out symbol-days.
- `signal_runner.DOWNGRADE_TIER` (his grade -> engine tier), the R3
  `ENABLE_DOWNGRADE_GRADER` arm.
- `signal_runner.SAC_TIER` (his grade -> engine tier), the W1
  `ENABLE_SAC_LADDER` arm.

`DOWNGRADE_TIER` was already correct and untouched by 394bcfe0 (`{"S": "A",
"A": "B", "C": "C"}` — S on the new top tier, A one rung down). Only `LADDER`
was stale, still reading engine `A` as his `A` (the PRE-394bcfe0 meaning) —
so scoring the live engine against the 100-card held-out set silently
under-counted every `S` day the engine fires as an `A`, and
`test_downgrade_grader.py`'s round trip (leg 3) failed on exactly that.

## Fixed: `research/t70_test1_score.py`

```
LADDER = {"A+": "S", "A": "S", "B": "A", "C": "C", None: "X"}
```

`A+` stays for old data (logs/replays written before 2026-08-30); `A` now
joins it as his `S` (the current top tier); `B` alone is his `A`. Comment and
`COL_LABEL` updated to match. `DOWNGRADE_TIER` needed no change.

Verified: `python research/test_downgrade_grader.py` -> rc=0 (was rc=1 at
line 133). `python research/regression_gate.py` and
`python research/test_runner_stop.py` both still pass — this is a read-only
scoring-file fix (`t70_test1_score.py` never writes to the engine), so no
engine behaviour, live or backtested, moved.

## Deferred: `signal_runner.SAC_TIER` — changes behaviour, not shipped

`SAC_TIER = {"S": "A", "A": "A", "C": "C", "X": "X"}` still collapses his S
and his A onto the SAME engine letter `A`, and `test_sac_ladder.py`'s round
trip still fails (now on the `A` leg: `('A', 'A', 'S')` — his A -> engine A
-> LADDER says S, since `A` is now legitimately his S's tier too).

This is not a stale-mapping oversight like `LADDER` was. It is a real,
already-documented, already-shipped design tradeoff (`signal_runner.py`
comment above `SAC_TIER`, and the docstring on `_sac_ladder_grade`): the SAC
ladder (`ENABLE_SAC_LADDER`) is built to **kill `B` entirely** — its whole
point is that no signal it grades ever carries the letter `B` again
(`test_sac_ladder.py::test_default_off_and_no_b`, currently passing, asserts
exactly this). Once `A+` is retired, the engine's tradeable alphabet is only
`A` (top) / `B` (mid) / `C` (bottom) — three rungs for three concepts (S, A,
C). Refusing `B` leaves only two rungs (`A`, `C`) for those three concepts,
so **S and A cannot both get a distinct, real engine letter without either
using `B` or inventing a letter that isn't a real grade.**

Both ways out are proven, not assumed — I ran each and measured the
consequence rather than eyeballing it:

1. **Use `B` for his A** (`SAC_TIER = {"S": "A", "A": "B", "C": "C", "X":
   "X"}`, i.e. copy `DOWNGRADE_TIER`). Round trip passes, but it directly
   contradicts `test_sac_ladder.py::test_default_off_and_no_b`
   (`"B" not in set(sr.SAC_TIER.values())`) — a currently-passing test that
   exists specifically because Austin's 2026-08-28 instruction was "B is not
   supposed to be a trade... revisit B trades and mold them into those
   grades or 'x' kill them." Un-killing B to fix a round trip un-does the
   whole flag.
2. **Give his S a synthetic letter** (e.g. revert to the pre-394bcfe0 value
   `"A+"`, which `SAC_TIER` values never pass through `TradeGrade()`
   construction, unlike `DOWNGRADE_TIER`, so it would not crash). This
   satisfies the round trip AND the no-`B` rule. But `_calibration_grade`
   calls `_sac_ladder_grade` (which sets `sig["grade"]` from `SAC_TIER`)
   **before** the `S_GATE`, `RULE_710_ENABLED`, and `RETEST_REQUIRED` checks
   (`signal_runner.py:2733` vs `2737`/`2746`/`2756`), and all three gate on
   `sig["grade"] in ("A", "B")`. Writing `"A+"` for his S makes those three
   gates silently stop applying to S-graded signals under
   `ENABLE_SAC_LADDER=1` — today they apply, because S and A currently share
   the literal string `"A"`. That is a real change to what the ON arm
   trades, not a label fix, even though `ENABLE_SAC_LADDER` ships OFF and
   nothing schedules it on.

Both routes change behaviour beyond the round-trip bug itself, so per this
row's instruction this half is **not shipped**. `SAC_TIER` is left exactly as
it was (still failing `test_sac_ladder.py`'s round trip on the his-A leg).

**For whoever turns this on next:** the durable fix is almost certainly to
stop reading `sig["grade"]` for S vs A under the SAC arm and read
`sig["sac_grade"]` instead — the untranslated letter `_sac_ladder_grade`
already writes alongside `grade` for exactly this reason (see its own
docstring: "S and his A are no longer distinguishable through sig['grade']
alone, which is why `_sac_ladder_grade` writes the untranslated letter to
`sig['sac_grade']` too"). That means moving the `S_GATE`/`RULE_710_ENABLED`/
`RETEST_REQUIRED` checks (or a `sac_grade`-aware variant of them) to read
`sac_grade` when `ENABLE_SAC_LADDER` is on — a real code change to three live
gates' semantics, which is Austin's call, not a bug fix.

## Status: partial

- `research/test_downgrade_grader.py`: fixed, rc=0.
- `research/test_sac_ladder.py`: still fails (round trip, his-A leg) —
  deferred, see above.
- `python research/regression_gate.py` and
  `python research/test_runner_stop.py`: both pass, unaffected.

---

# g182 — B3 (bug B-02): the r3 report's stale, retired third mapping

What is different now: `research/r3_downgrade_grader_ab.py`'s generated report text no longer
claims a THIRD, retired ladder mapping for `signal_runner.DOWNGRADE_TIER` (`` `S -> A+` ``); the
two real ladders (`SAC_TIER`, `DOWNGRADE_TIER`) are untouched. This bug's headline symptom is the
same design conflict B-01 above already found and left deferred (`SAC_TIER['A']` vs
`DOWNGRADE_TIER['A']`) — this entry does not re-litigate that; it fixes the one genuinely stale,
zero-risk piece B-01 did not touch, and confirms the collapse itself is still correctly refused.

## Confirmed and fixed: stale third mapping in r3 prose

Failing input (before, confirmed by grep before editing):
`research/r3_downgrade_grader_ab.py` stated in its report body that
`signal_runner.DOWNGRADE_TIER` is `` `S -> A+`, `A -> B`, `C -> C` `` and that `_grade_pa` "can
only ever emit `A+/B/C/X`". Both describe the pre-2026-08-30 alphabet. `signal_runner.py`'s own
dated comment (line ~784) records A+ retired 2026-08-30; the real, current `DOWNGRADE_TIER` is
`{"S": "A", "A": "B", "C": "C"}` and `_grade_pa`'s alphabet is `A/B/C/X`. This stale prose is
exactly the "third version (S -> A+) that no longer exists" the ticket named.

Fix: updated the two prose lines in `research/r3_downgrade_grader_ab.py` (docstring line ~17,
report body lines ~462-466) to state the real mapping and alphabet, with the retirement date
noted inline. Zero behaviour change — the file only builds a Markdown report string; it is not
imported by any engine or backtest path.

Test: `research/test_g182_b02_ladder_prose.py` (new) — asserts the stale substrings (`"S -> A+"`,
`"A+/B/C"`) are gone and the prose states the real `DOWNGRADE_TIER` mapping verbatim. Verified
failing before this edit by inspection (`grep -n "A+/B/C\|S -> A+" research/r3_downgrade_grader_ab.py`
matched three lines pre-edit), passing after.

Verify gate: `python research/regression_gate.py && python research/test_runner_stop.py` — both
exit 0 (no engine module touched).

## Reconfirmed deferred: do not collapse `SAC_TIER` and `DOWNGRADE_TIER`

Reproduces exactly as the ticket states:

```
python -c "import signal_runner as sr; print(sr.SAC_TIER['A'], sr.DOWNGRADE_TIER['A'])"
A B
```

B-01 above already priced both directions of "fixing" this (giving `SAC_TIER` a `DOWNGRADE_TIER`-
shaped mapping un-kills `B`, contradicting `test_sac_ladder.py`'s no-`B` assertion; giving `S` a
synthetic top letter silently stops three live gates from applying to S-graded signals under
`ENABLE_SAC_LADDER=1`) and left it unshipped. Independently re-checked here from the
`DOWNGRADE_TIER` side: `_grade_trade`'s neutral-hour cap (`if htf_bias == "neutral" and base ==
TradeGrade.A: return TradeGrade.B`, signal_runner.py ~2608) only fires because
`DOWNGRADE_TIER["A"]` is NOT `"A"` — collapsing the two ladders would silently disable that cap
too. Both flags (`ENABLE_SAC_LADDER`, `ENABLE_DOWNGRADE_GRADER`) ship `False` by default and
neither is flipped by this ticket, so today's live signal counts and trade behaviour are
unaffected — but a unification would change what either flag does the moment it is turned on,
which this row says not to ship. No change made to `signal_runner.py`.

## Status: partial

- `research/r3_downgrade_grader_ab.py` stale prose: fixed, `research/test_g182_b02_ladder_prose.py`
  passes.
- Ladder collapse (`SAC_TIER` vs `DOWNGRADE_TIER`): reconfirmed deferred, same conclusion as B-01,
  not shipped.
- `python research/regression_gate.py` and `python research/test_runner_stop.py`: both pass,
  unaffected.

---

# g182 — B3 (bug B-03): HTF_BIAS_VETO blocker note named the wrong flag

What is different now: `live_scanner.py`'s item-4 blocker note (lines ~79-91) names
`omen_bot.HTF_BIAS_VETO` (default ON — the flag that actually grades traded backtest rows
down to D) instead of `HTF_BIAS_GATE` (an unrelated flag in `signal_runner.py`, default
OFF, that has nothing to do with this veto). No runtime code changed.

## Confirmed and fixed: stale/wrong flag name in the blocker note

Failing input: the note said `` `HTF_BIAS_GATE` defaults OFF in both paths, so today this
changes nothing on its own``. `HTF_BIAS_GATE` is real but lives in `signal_runner.py`
(a daily-candle trend cap on counter-trend signals, default OFF) — a different mechanism
from the one this note is actually about. The veto that gates the top grades off `htf_bias`
is `omen_bot.HTF_BIAS_VETO` (`omen_bot.py:29`, default ON), and in the 2-year backtest,
where a real bias is computed (99.2% of rows via polygon_feed), it grades 1,699 of 4,022
traded rows (42.2%, `aligned=='against'`) down to D
(`research/bt2y_trades_retest_on.json`). The note's *conclusion* — that this changes nothing
live today — was still correct, but for the wrong reason: it is because live_scanner's
yfinance fallback hardcodes `htf_bias=None` on every symbol, and `HTF_BIAS_VETO`'s `opposed`
check (`omen_bot.py:255`) requires `htf_bias in ('bullish', 'bearish')`, not because
`HTF_BIAS_GATE` defaults off (that flag was never in the loop here at all).

Fix: corrected the note to name `HTF_BIAS_VETO`, state the 42.2% traded-row figure, and
attribute the live no-op to the hardcoded `None` bias and the `opposed` check's guard.
`HTF_BIAS_VETO`'s default (ON) and `omen_bot.py:255`'s guard are untouched — this is a
doc-only correction inside a comment block. Live signal counts and backtest grades are
byte-identical before and after.

Test: `research/test_g182_b3_htf_bias_veto_note.py` (new) — asserts `omen_bot.HTF_BIAS_VETO`
defaults `True`, and that the item-4 note names `HTF_BIAS_VETO` and states the 42.2% figure
(and, if it mentions `HTF_BIAS_GATE` at all, that it is flagged as a different/unrelated
flag). Fails on the pre-fix note (wrong flag name, no 42.2% figure), passes on the
corrected one — 2 passed.

Verify gate: `python research/regression_gate.py && python research/test_runner_stop.py` —
both PASS, unaffected (comment-only change, no engine module's runtime behaviour moved).

## Status: done

- `live_scanner.py` blocker note: fixed, names the correct flag and figure.
- `research/test_g182_b3_htf_bias_veto_note.py`: 2 passed.
- `python research/regression_gate.py` and `python research/test_runner_stop.py`: both
  pass, unaffected — no behaviour change shipped.

---

# g182 — B3 (bug B-04): ticket 23's true HTF-flag timeline

What is different now: `spec0b_levels_check.py`'s line-60 assertion (and its comment block)
matches the shipped `HTF_BIAS_VETO` default (ON) instead of a default that only ever shipped
for part of one day; `Projects/omen-rulebook.md` in the vault carries a dated correction that
reconciles ticket 23. No engine module changed.

## Confirmed: the timeline in the ticket

- Unflagged, unconditional D-veto before 2026-08-27.
- `fdc8e090` (08-27): introduces `HTF_BIAS_VETO` with default `'0'`.
- `71f39851` (08-27): flips the default to `'1'` (measured: lifting it buys 1.7%, not
  3,525 — not worth the cost).
- `f959cff5` (08-28): corrects the docstring to say "SHIPPED DEFAULT" (it had been
  misreporting the opposite).
- `d0a38dc9` (09-03, "OMEN 8.0 R4"): adds `HTF_GRADE_VETO`, default OFF, in `omen_bot.py` /
  `signal_runner.py`, plus `test_htf_grade_veto_default.py`.
- `git merge-base --is-ancestor d0a38dc9 HEAD` -> yes, it IS an ancestor of the current tree.
- But `grep -c HTF_GRADE_VETO omen_bot.py` -> `0`, `grep -c HTF_GRADE_VETO signal_runner.py`
  -> `0`, and `test_htf_grade_veto_default.py` does not exist in the working tree.
- `python test_htf_bias_veto_default.py` -> all checks pass, asserting the ON default.
- `omen-rulebook.md:855` says "Deleted 2026-08-28" for `HTF_BIAS_VETO` (true for the earlier,
  pre-veto-existing episode it describes), but the R4 paragraph directly under it (dated
  2026-09-03) and the AUGUR paragraph under that already flagged the same contradiction and
  filed it as ticket 23 rather than resolve it.

Conclusion: `d0a38dc9`'s fix genuinely landed and is a real ancestor commit, but its
`omen_bot.py`/`signal_runner.py` hunks and its test are not in the working tree today — dropped
by the 2026-09-03 history rewrite that CLAUDE.md documents for a different reason (the
`>100MB` books being stripped from history). It was not "never reached main" (it did) and it
was not a deliberate revert (no revert commit exists) — the rewrite dropped it as a side effect.
The flag shipping today, and correct as shipped, is `HTF_BIAS_VETO`, default ON
(`os.getenv("HTF_BIAS_VETO", "1")`, `omen_bot.py:29`), matching the W12 (`f959cff5`) docstring.

## Fixed: `spec0b_levels_check.py`

Line 60 asserted `g_opp == TradeGrade.A_PLUS` under the comment "veto OFF by default" — that
comment described `d0a38dc9`'s vanished default, not the shipped one, and the assertion crashed
every run (`AssertionError: TradeGrade.X`) since `d0a38dc9` never took effect in this tree.
Corrected to assert `g_opp == TradeGrade.D` (the ON-default hard veto), added the mirror check
that `HTF_BIAS_VETO=0` lifts it back to PA-alone grading, and rewrote the section's comment
block to name the real timeline instead of the vanished one. Section 4's comment was also
inaccurate independent of ON/OFF (detect_signals() never filters rows by grade — a D-graded row
still appears with its downgraded grade, or gets rescued back up by the separate, already-
shipped T10 `X_LIFT` arm; nothing removes the row); corrected without changing the assertion,
which already held.

Test: this file's own failing-before/passing-after run. Before: `python spec0b_levels_check.py`
-> `AssertionError: TradeGrade.X` at line 60. After: `python spec0b_levels_check.py` -> "All
SPEC0-gap checks passed."

## Deferred: not re-adding `HTF_GRADE_VETO`'s default-OFF behavior

Restoring `d0a38dc9`'s fix (flipping the veto's shipped default to OFF) would change live
signal counts and trade behaviour beyond this bug: `HTF_BIAS_VETO` grades 1,699 of 4,022 traded
rows (42.2%) down to D in the 2-year backtest (`research/bt2y_trades_retest_on.json`, cited in
this same file's B-03 entry). Per this row's instruction, that is out of scope here — this
entry is a documentation/test reconciliation only, and ships no behaviour change.

Vault: `Projects/omen-rulebook.md`'s "Higher-timeframe bias is not a rule, so it is not a veto"
section gets a dated correction (2026-09-05) reconciling the W12-vs-R4 conflict its own AUGUR
paragraph had already flagged and filed as ticket 23 — filed there, not resolved here, per this
same row's earlier convention.

## Status: done

- `spec0b_levels_check.py`: fixed, `python spec0b_levels_check.py` -> "All SPEC0-gap checks
  passed."
- `omen-rulebook.md` (vault): ticket 23 reconciled with a dated correction, no ruling changed.
- `python research/regression_gate.py` and `python research/test_runner_stop.py`: both pass,
  unaffected — no engine module's runtime behaviour moved.

---

# g182 — B3 (bug B-05, ticket 19): the two "-1R" counts measure different columns

What is different now: `stop_rule.py` gains `per_fill_r_multiple`, the missing per-fill
R-multiple helper (against the trade's ORIGINAL entry/risk, same convention as
`stop_fill_price`/`disaster_stop_price`), and its module docstring now reconciles ticket 19
by name; `CLAUDE.md`'s "0 of 2,216 losses" line now says which column that is. No engine
module's runtime behaviour changed — this is an additive helper plus documentation.

## Confirmed: neither number was wrong, the column was undocumented

- bbcfd5cf's "70 of 4,022 traded rows worse than -1.000R" (53 after
  `signal_runner.min_risk_floor`'s size gate, worst -1.3333R, MARA 2025-12-15 put) is the
  **per-fill** column: each fill's price against that trade's ORIGINAL `entry`/`risk`. No
  function in the codebase computed this — it existed only as an ad hoc calculation in
  whatever script produced bbcfd5cf's number.
- ece08845's "0 rows worse than -1.000R" is the **blended trade-level** column,
  `backtest_week.py`'s `row["r"] = round(t.pnl / RISK_DOLLARS, 3)` — it nets every scale-out
  fill's P&L against the eventual stop-out's, so a trade can read >= -1.000R blended even
  when its stop leg alone breached the clamp.
- `bt2y_trades_retest_on.json` carries only the blended `r` column, so bbcfd5cf's 70 cannot
  be re-derived from it after the fact — the per-leg fills are gone by the time `r` is
  written. That book was also built 2026-09-02, before `ece08845`, so reading its blended
  "0" as post-fix confirmation is wrong regardless of column: it is the pre-fix engine's
  blended number, which already read 0 (the clamp firing on one leg is routinely absorbed
  by another leg's gain in the blended sum).
- Verified directly against `bt2y_trades_retest_on.json`: traded 4,022; blended `r < -1.0` =
  0; `r == -1.0` = 1,448; losses (`r<0`) = 2,216 — matching CLAUDE.md's "0 of 2,216" exactly,
  confirming it already read the blended column correctly, just without naming it.

## Fixed: `stop_rule.py`

Added `per_fill_r_multiple(fill_price, entry, risk, long)` — the per-fill R-multiple against
original risk, symmetric to `stop_fill_price`/`disaster_stop_price`'s existing convention
(risk taken from the caller, never re-based on a moved stop). It has no caller yet in any
shipped rig (purely additive), so nothing's live signal counts or trade behaviour moved.
Module docstring gets a dated ("Ticket 19 (B-05), reconciled 2026-09-05") section stating
both columns' numbers side by side and which script/file produced each.

`CLAUDE.md`'s "Rules that hold everywhere" bullet now says the "0 of 2,216" figure is the
blended column, cites the 70-of-4,022 per-fill figure as the same book's other column, and
states the rule going forward: every -1R claim names its column.

## Test: `research/test_g182_b05_per_fill_r.py` (new)

Before: `stop_rule.per_fill_r_multiple` does not exist -> `AttributeError`, both tests fail.
After: 2 passed — asserts the per-fill number matches `stop_fill_price`'s own clamp math
(a fill clamped to -1.25R per-fill reads -1.25R via the new function), and constructs a
worked two-leg trade where the per-fill column reads worse than -1.000R while the blended
column (computed the same way `backtest_week.py` does) reads >= -1.000R — reproducing, in
miniature, exactly the discrepancy ticket 19 named.

Verify gate: `python research/regression_gate.py && python research/test_runner_stop.py` —
both PASS, unaffected (new helper function is unused by any existing caller; docstring/
CLAUDE.md are documentation-only).

## Status: done

- `stop_rule.py`: `per_fill_r_multiple` added, docstring reconciles ticket 19.
- `CLAUDE.md`: "0 of 2,216" line now names its column and cites the per-fill figure.
- `research/test_g182_b05_per_fill_r.py`: 2 passed (fails before, per `AttributeError`
  reproduced above; passes after).
- `python research/regression_gate.py` and `python research/test_runner_stop.py`: both pass,
  unaffected — no engine module's runtime behaviour moved.

---

# g182 — B3 (bug B-06): position_sizer's local, unmeasured 0.5 delta default

What is different now: `position_sizer.compute_plan`'s `assumed_delta` default now imports
`options_sizer.DEFAULT_DELTA` (0.42, the measured value) instead of a separate, local, never-
measured `0.5` — the same "ATM ~= 0.5, assumed, never measured" constant `options_sizer.py`
already fixed for itself at OMEN 8.0 R6 (`research/g95_delta_fix.py`), left un-synced in this
second module.

## Confirmed

Failing input, reproduced before editing:
```
python -c "import position_sizer as p; print(p.compute_plan(stock_entry=100.0, stock_stop=99.58, direction='call').contracts_estimated, p.compute_plan(stock_entry=100.0, stock_stop=99.58, direction='call', assumed_delta=0.42).contracts_estimated)"
47 56
```
Every caller (`grep -rn "compute_plan(" .` across `signal_runner.py`, `position_sizer.py`'s own
`__main__`, and every worktree copy) calls `compute_plan` with no `assumed_delta` argument, so
every one of them was silently taking the wrong default — the same 0.42/0.5 = 0.84 under-sizing
ratio `options_sizer.py`'s R6 comment already prices, reproduced here in a second module.

**Scope check before fixing:** `grep -rn "position_sizer\|contracts_estimated"` shows
`position_sizer.compute_plan` has no live-order caller — `paper_trader.py` and `broker/base.py`
both route sizing through `options_sizer.py` (already correct at 0.42 since R6). `compute_plan`
is called only from `signal_runner.py`'s `process_candles` (a console-print path) and
`discord_bot.py` (a Discord embed's "~Contracts" field). Fixing the default therefore corrects a
**displayed estimate only** — it does not change which signals fire, which orders `paper_trader`
places, or any sizing an actual position is opened at. This is in scope to ship per this row's
instruction (no live signal count or trade behaviour moves).

## Fixed: `position_sizer.py`

- Added `from options_sizer import DEFAULT_DELTA` (one-way import; `options_sizer.py` imports
  nothing from `position_sizer.py`, so no circular import).
- `compute_plan(..., assumed_delta: float = 0.5, ...)` -> `assumed_delta: float = DEFAULT_DELTA`.
- Updated the two remaining "ATM ~0.5" mentions (the `format_discord()` embed string and the
  `compute_plan` docstring) to name the shared constant instead of a hardcoded 0.5, so the
  printed/embedded text and the actual default stay in sync going forward.
- Added a dated comment (B-06, OMEN 9.0 B3, 2026-09-05) at the constants block recording why the
  import exists and that this module has no live-order path.

## Test: `test_position_sizer_delta.py` (new, repo root — matches `test_options_sizer_delta.py`'s
existing sibling convention, plain asserts, no pytest)

Before: `compute_plan.__signature__`'s `assumed_delta` default is `0.5`; the ticket's exact
failing input prints `47 56` (default and explicit-0.42 disagree). After: default is `0.42`
(`inspect.signature` check); the same failing input's default call now equals the explicit-0.42
call, both `56`; and the default no longer reproduces the stale `47`-contract figure. 3 passed.

Verify gate: `python research/regression_gate.py && python research/test_runner_stop.py` — both
PASS, unaffected (`position_sizer.py` is not imported by either gate script, and no gated engine
module was touched).

## Status: done

- `position_sizer.py`: fixed, default `assumed_delta` now `options_sizer.DEFAULT_DELTA` (0.42).
- `test_position_sizer_delta.py`: 3 passed (47/56 mismatch reproduced pre-fix, matches post-fix).
- `python research/regression_gate.py` and `python research/test_runner_stop.py`: both pass,
  unaffected — no live signal count or trade behaviour moved (display-only estimate, no
  live-order caller of this module).

---

# g182 — B3 (bug B-07): `_min_viable_stop`'s hardcoded 0.5 delta on the live fire gate

What is different now: nothing shipped to `signal_runner.py` — confirmed the bug, wrote a
failing-before test proving it, then measured that the correct fix moves which signals fire on
the regression corpus, so per this row's instruction it is **deferred**, not shipped.

## Confirmed: the exact failing input from the ticket

`signal_runner.py`'s `_min_viable_stop` (the hard gate on the fire path, called at the two sites
inside `_route`'s x-lift check and its C-grade tight-stop check) estimated premium risk with a
second, un-synced copy of the same stale constant B-06 above already fixed in `position_sizer.py`:

```
premium_risk = stock_risk * 0.5  # ATM delta ~= 0.5 estimate
```

against `options_sizer.DEFAULT_DELTA = 0.42` (measured at OMEN 8.0 R6, `research/g95_delta_fix.py`).
Reproduced the ticket's exact input, entry=100.00, stop=99.58 (stock_risk=0.42, risk_pct=0.0042,
below the 0.005 arm so the premium-risk branch alone decides it): at 0.5, premium_risk=$0.21 >=
$0.20 -> the gate says viable and the signal fires; at the measured 0.42, premium_risk=$0.1764 <
$0.20 -> not viable, correctly rejected. Every caller checked (`grep -n "_min_viable_stop"
signal_runner.py`): exactly two call sites, both inside `signal_runner.py` itself (the x-lift
stop guard and the C-grade tight-stop check in `_route`) — no other module calls this function.

## Test: `research/test_min_viable_stop_delta.py` (new)

Constructs a `SignalRunner` with empty `self.candles` (so the STOP_RANGE_MULT human-proof guard
no-ops and the premium-risk branch alone decides), calls `_min_viable_stop(100.00, 99.58, "long")`
and asserts it returns `False`. Before the fix: fails (`AssertionError`, returns `True` — the
hardcoded 0.5 admits the signal the gate exists to reject). Confirmed failing pre-fix by running
it against the current shipped code.

## Measured: applying the fix changes which signals fire — deferred per this row's instruction

Applied the one-line fix (`premium_risk = stock_risk * options_sizer.DEFAULT_DELTA`, plus the
matching `import options_sizer`) and re-ran `research/regression_gate.py` (159 marks,
`austin_marks_v2.jsonl`) before and after, same commit otherwise:

| | S fired | A fired | any_signal |
|---|---:|---:|---:|
| shipped (0.5, current) | 25 | 17 | 80 |
| fixed (0.42) | 23 | 15 | 80 |

No baseline-fired mark went silent either way (gate still PASSes both times), but 2 fewer S
fires and 2 fewer A fires on this 159-mark corpus is a real change to which signals the live fire
path admits — not confined to the ticket's single synthetic input. This is the tight-stop gate
tightening exactly as intended (fewer marginal, under-priced-risk signals get through), but it is
a change to live signal counts and trade behaviour beyond the bug itself, which this row's
instruction says not to ship without pricing the recall change on the full book first. Reverted
`signal_runner.py` to the shipped 0.5 (`git checkout -- signal_runner.py`); confirmed
`regression_gate.py` reads back to the pre-fix baseline (any_signal 80, s_grade 25, A 17).

**Next step for whoever re-runs this:** re-run `research/g154_rule_*`-style selection-arm pricing
(H1/H2 split, S recall on the 100-card deck, precision, $/day one-trade-a-day) with the 0.42 fix
applied, the same way F5/O1 price a selection change, before shipping it — this is a gate-strictness
change, not a display-only fix like B-06's twin.

## Status: partial

- `signal_runner.py`: **not changed** — fix confirmed correct but deferred (changes live signal
  counts: S 25->23, A 17->15 on the 159-mark regression corpus).
- `research/test_min_viable_stop_delta.py`: new, fails against the shipped (unfixed) code by
  design — documents the confirmed bug and its exact failing input for whoever prices and ships
  the fix.
- `python research/regression_gate.py` and `python research/test_runner_stop.py`: both pass on
  the unmodified, shipped `signal_runner.py` — no engine behaviour moved by this entry.

---

# g182 — B3 (bug B-08): the verify gate runs 2 of 59 tracked tests

What is different now: `test_universe_single_source.py` now passes and is wired into
both gates (`CLAUDE.md`'s `verify:` line and `research/daily_run.cmd`). Root cause was
three private ticker-list literals duplicating `universe.INDEX_POOL`
(`["QQQ","SPY","IWM"]`) instead of importing it — `research/g83_futures_arm.py:68
INDEX_POOL`, `research/g83_sizing.py:91 INDEX_SYMS`, `research/g83_verify_2.py:43
INDEX_POOL` — exactly the drift class this test exists to catch, and exactly the
evidence the bug ticket named.

## Fixed

All three now `from universe import INDEX_POOL` (`g83_sizing.py` aliases it `as
INDEX_SYMS` so its call sites are untouched; `g83_verify_2.py` gained `sys.path.insert(0,
str(ROOT))` since it had none before). The values were already identical to
`universe.INDEX_POOL` (list order matched in `g83_futures_arm.py`, set membership
matched in the other two), so this is a pure source-of-truth fix with no behaviour
change: confirmed by an import smoke test on all three files (no module-level code runs
beyond imports — each guards its work behind `if __name__ == "__main__"`).

Verified: `python research/test_universe_single_source.py` -> rc=0 (was rc=1, "3 private
symbol list(s)"). `python research/regression_gate.py` and `python
research/test_runner_stop.py` both still rc=0 — untouched by this change.

Added `python research/test_universe_single_source.py` to `CLAUDE.md`'s `verify:` line
and a new "universe single-source gate" section to `research/daily_run.cmd` (runs
alongside `regression_gate.py`, non-fatal to the deck build, same pattern) so this
specific drift class cannot reappear silently.

## Deferred: the other 13 red test files — changes behaviour, not shipped

The bug ticket lists 14 red test files and says the gate should run them all. This entry
fixes and gates the one test whose failure was itself named as B-08's evidence and whose
fix is a pure import swap. The other 13
(`test_austin_tier.py`, `test_rule_710.py`, `test_detect_wide.py`,
`research/test_downgrade_grader.py`, `research/test_sac_ladder.py`,
`research/test_entry_scratch.py`, `research/test_onwatch_fill.py`,
`research/test_paper_trader_stop.py`, `research/test_published_numbers.py`,
`research/test_rule84_source.py`, `research/test_structural_floor.py`,
`research/test_master_homework_page.py`, `research/test_omen_test1_page.py`) each fail on
a distinct behavioural claim (a stop-fill floor, a flag's OFF-arm byte-identity, an
FVG/FLAG routing branch, a ladder round-trip, a silent-day fixture, two browser-driven
page tests) rather than sharing B-08's root cause. Several look like they still assert a
retired `-1.25R` floor CLAUDE.md already says the shipped path does not have; others may
be real, unfixed bugs. Deciding "shipped vs. retired" for each is exactly the judgement
call this row's own fix sketch asks to make one at a time, and several of those calls
change what the live engine asserts (stop floor, retest default, FVG/FLAG routing) —
outside B-08's scope and risking the "changes behaviour beyond the bug itself" case this
batch is told to defer. They stay red and un-gated pending their own root-cause
diagnosis; naming them here means "14 red tests, gate runs 2" is not silently called
closed at "13 red tests, gate runs 3".

## Status: partial

- `research/test_universe_single_source.py`: fixed, rc=0, now gated.
- The other 13 named test files: still red, still ungated — deferred, see above.
- `python research/regression_gate.py` and `python research/test_runner_stop.py`: both
  pass, unaffected.

---

# g182 — B3 (bug B-09): `run_daily.ps1` never passes `--back` to `archive_1m.py`

What is different now: `run_daily.ps1`'s nightly `archive_1m.py` call now asks for
`--back 1` (today plus yesterday) instead of the bare default — `data_archive/`
growth is no longer structurally impossible on this Polygon plan.

## Confirmed

`archive_1m.py:57` defaults `end = date.today()` when `--date` is omitted, and
`--back` (also omitted) is `0`, so the day list is exactly `[today]`. The module's own
docstring on `archive_day` says Polygon 403s the CURRENT day on this plan ("an
unattended job must ask for completed sessions"). `run_daily.ps1:32` called
`archive_1m.py` with no flags at all, so every nightly run since the plan changed
asked for the one day guaranteed to fail:

```
python -c "import polygon_feed; print(len(polygon_feed.fetch_day('AAPL','2026-09-04')))"
959 bars
python -c "import polygon_feed; polygon_feed.fetch_day('AAPL','2026-09-05')"
HTTPError: 403 Client Error: Forbidden.
```

Yesterday (a completed session) fetches fine; today 403s exactly as the docstring
predicts. `grep -rn "archive_1m.py"` across the repo (excluding worktrees) shows only
two callers: `run_daily.ps1` (the broken one) and `run_omen6_forward.ps1`, which
already passes `--back 5` and was never bitten by this. The bug is entirely in the
caller, not in `archive_1m.py` — the function all callers route through
(`archive_day`, called from `main()`'s day loop) already handles `--back` correctly.

## Fixed: `run_daily.ps1`

Line 32: `archive_1m.py` -> `archive_1m.py --back 1`. This asks for today (still
403s, logged and skipped per-symbol, harmless) plus yesterday's now-completed
session, so the nightly run actually banks one new day into `data_archive/` per
run instead of zero.

## Test: `research/test_g182_b09_archive_back.py` (new)

Parses `run_daily.ps1`'s `archive_1m.py` invocation line and asserts a `--back N`
flag with `N >= 1` is present. Before: no `--back` flag at all -> `AssertionError`
(reproduced above, confirmed failing pre-fix). After: 2 passed.

## Scope check: data-archiving pipeline only, no engine module touched

`archive_1m.py` writes CSVs into `data_archive/` for later backtests; it is not
imported by `live_scanner.py`, `signal_runner.py`, `omen_bot.py`, or any live-fire
path. Changing how many days it is asked to fetch cannot move a live signal count
or a trade decision — it only changes how much historical data gets banked for
future backtests. No shared module edited (only `run_daily.ps1` and this new test).

Verify gate: `python research/regression_gate.py && python research/test_runner_stop.py`
— both PASS, unaffected.

## Status: done

- `run_daily.ps1`: fixed, now calls `archive_1m.py --back 1`.
- `research/test_g182_b09_archive_back.py`: 2 passed (fails before, `AssertionError`
  reproduced above; passes after).
- `python research/regression_gate.py` and `python research/test_runner_stop.py`: both
  pass, unaffected — no engine module's runtime behaviour moved.

---

# g182 — B3 (bug B-10): the daily run no longer trusts a pull it hasn't smoke-tested

What is different now: `run_daily.ps1` pulls, then smoke-tests that
`live_scanner` still imports, and only proceeds to launch it if that passes;
a pull that breaks the tree is rolled back to the previous commit so the day
scans on yesterday's known-good code instead of dying silently. Root-caused
in a single new function, `pull_guard.run_guarded_pull`, which is the one
place the pull-then-run logic now lives (only caller today: `run_daily.ps1`
line 26).

## Root cause

`run_daily.ps1` ran `git pull --rebase --autostash` at line 26 and
`live_scanner.py` at line 29 with nothing between them. On 2026-09-03 the
pull brought in an `omen_bot.py` with a stray U+2014 em-dash that Python
can't parse; the entire daily pass died — scanner and archiver both
(`journal/scanner-2026-09-03.log`, 80 lines against ~8,000 on a normal day):

```
File "…\omen_bot.py", line 219
    opposed trend — D when HTF_BIAS_VETO=1 (default 0 — P16/W3, the veto
SyntaxError: invalid character '—' (U+2014)
```

An unattended job that self-updates from `main` with no syntax check between
the pull and the run has no floor under it.

## Fix

New `pull_guard.py` at repo root, `run_guarded_pull(python_exe, smoke_module,
cwd)`: records `HEAD` before pulling, runs `git pull --rebase --autostash`,
then `python -c "import live_scanner"`. If that import fails, `git reset
--hard` back to the pre-pull commit and report the rollback; otherwise leave
the pull in place. `run_daily.ps1:26` now calls `& $python pull_guard.py
$python` instead of running `git pull` directly.

## Test: `research/test_pull_guard.py`

Builds a throwaway local git remote + clone, reproduces the exact failure
mode (a second commit with invalid, unparseable Python landing via pull),
and asserts:
- `test_guarded_pull_rolls_back_a_broken_commit` — after the guard runs,
  `HEAD` is back at the last good commit and `import live_scanner` succeeds.
- `test_guarded_pull_leaves_a_good_pull_alone` — a pull that stays valid
  Python is left in place, `HEAD` at the new commit.

Both fail without `pull_guard.py` (the module doesn't exist — reproducing
the pre-fix state, no guard at all) and both pass with it:

```
$ python research/test_pull_guard.py
...
OK: pull_guard rolls back a broken pull, leaves a good one alone
```

## Scope check: ops-only, no engine module touched

`pull_guard.py` only shells out to `git` and does an import smoke test; it
never imports `signal_runner`, `omen_bot`, or `live_scanner`'s internals, and
changes no signal-generation or trade logic. `run_daily.ps1` is not on the
do-not-edit list (`live_scanner.py`, `signal_runner.py`, `omen_bot.py`,
`paper_trader.py`, `broker/*`, `notify_ntfy.py`,
`research/daily_fetch.py`, `research/daily_homework.py`).

Verify gate: `python research/regression_gate.py && python
research/test_runner_stop.py` — both PASS, unaffected.

## Status: done

- `pull_guard.py`: new, root-cause fix.
- `run_daily.ps1`: line 26 now routes through `pull_guard.py` instead of a
  bare `git pull`.
- `research/test_pull_guard.py`: 2 tests, both fail before (`pull_guard`
  doesn't exist) and pass after.
- `python research/regression_gate.py` and `python research/test_runner_stop.py`:
  both pass, unaffected — no engine module's runtime behaviour moved.
