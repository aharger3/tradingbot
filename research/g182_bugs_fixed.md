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
