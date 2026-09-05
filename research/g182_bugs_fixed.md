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
