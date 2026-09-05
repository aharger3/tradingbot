# L1 referee — REFUTED (the numbers), decision upheld

Row **L1**, the 1R first-target rule (`MIN_PT1_R`). Builder commits **e073b94a** (code, flag
lands OFF) and **842b3f3c** (the books, the gate, `research/l1_min_pt1_r.md`). Referee script:
`research/l1_referee.py` — every figure below is re-derived from the two stamped books with
arithmetic written out longhand in that file; nothing is taken from the builder's own gate
output. Base check at start: `origin/main` = HEAD = `842b3f3c`, `1539dd7f` is an ancestor.

**Verdict: refuted.** The *decision* (hold, default stays OFF) is correct and survives every
way I sliced it. **Every published number is measured on the wrong universe**, and the
write-up names a universe it did not use.

---

## 1. The universe defect — the reason this is refuted

`research/l1_min_pt1_r.md` states, in the sentence that qualifies every dollar in the row:

> universe = `CORE_SYMBOLS` (11 symbols, rows with `tier=='core'`)

It is not. `research/loop_cycle.py::stage_gate` reads `cfg["unit"]`, `cfg["halves_boundary"]`,
`cfg["gate"]` and `cfg["targets"]` from `research/tape/loop.json` and **never reads
`cfg["universe"]`**. There is no `tier == "core"` filter anywhere in `loop_cycle.py`. The gate
therefore ran on all **28 symbols** in the book (`tier` counts in the OFF book: core 54,186 /
experimental 62,450 / other 10,877 rows).

`research/tape/loop.json`'s own `_comment` had already flagged this as a prerequisite the
loop controller did not yet meet:

> Two items the loop controller still needs before cycle 1 … (1) `universe` — the settled
> universe is CORE_SYMBOLS, so the unit function must run on rows with tier == "core"
> (loop_cycle.py reads the whole 29-symbol book today)

Cycle 1 ran anyway. The proof is arithmetic: my full-29 re-derivation reproduces the
builder's table to the dollar, and my core-11 re-derivation reproduces **R3's own
`baseline_figures` block in `loop.json`** to the dollar. Same book (`book_id`
`2c39ced2697c26cc` on both), two different universes, two different tables.

| unit = up_to_3_stop_win_or_2loss · fill = close · exit = shipped 1R hard stop + `hod_then_runner_be` · 499 sessions 2024-09-04..2026-09-04 · script `research/l1_referee.py` | trades | $/day | mean R | green | months |
|---|---:|---:|---:|---:|---:|
| **core-11** (loop.json `universe.row_filter`, what R3 measured) OFF | 769 | **−$52** | −0.0335 | 11 | 25 |
| **core-11** ON (`MIN_PT1_R=1.0`) | 751 | **−$29** | −0.0195 | 11 | 25 |
| core-11 H1 (…2025-08-31) OFF | 382 | $9 | 0.0057 | 6 | 12 |
| core-11 H1 ON | 368 | $107 | 0.0721 | 7 | 12 |
| core-11 H2 (2025-09-01…) OFF | 387 | −$111 | −0.0722 | 5 | 13 |
| core-11 H2 ON | 383 | −$164 | −0.1076 | 4 | 13 |
| **full-29** (what `loop_cycle.py` actually gated on) OFF | 773 | −$9 | −0.0059 | 12 | 25 |
| **full-29** ON | 767 | **$29** | 0.0188 | 12 | 25 |
| full-29 H1 OFF / ON | 378 / 377 | $72 / $201 | 0.0472 / 0.1322 | 8 / **9** | 12 |
| full-29 H2 OFF / ON | 395 / 390 | −$89 / −$141 | −0.0567 / −0.0908 | 4 / **3** | 13 |

The full-29 block matches `research/l1_min_pt1_r.md`, `research/tape/cycles.md` and
`research/tape/loop_state.json` exactly, so the builder's arithmetic is sound — it is the
population that is wrong.

What actually changes when the universe is corrected:

- The headline flips sign. On core-11 the ON arm **never turns positive**: −$52/day → −$29/day,
  a smaller loss, not a profit. The published "−$9 → $29" is a full-29 figure.
- Whole-book green months are **11 → 11**, not 12 → 12.
- H1 is **6 → 7** green, not 8 → 9. H2 is **5 → 4**, not 4 → 3.
- Trade counts are 769/751, not 773/767; `cycles.md`'s trade column (767) is a full-29 count.
- Fires/day is 1.541 → 1.505, not the published 1.549 → 1.537.

**The decision is unaffected.** On core-11 H2 fails on both criteria — green months fall 5 → 4
*and* $/day gets worse than 5% (−$111 → −$164) — so the no-regression gate holds the change
either way. Default OFF is right. (Minor: the write-up says H2 fails "regardless of the dollar
move"; on both universes H2 fails the dollar test too, so the framing understates the fail.)

The fix belongs to the loop controller (`loop_cycle.py`, row O4), not to the flag: one
`row_filter` in `stage_gate`. Until it lands, **every cycle row in `research/tape/cycles.md`
is a full-29 number wearing a core-11 label**, and cycle 1's row should be re-run or annotated.

## 2. The X_LIFT ordering hole — the gate cannot see 2,439 traded rows

In `signal_runner._route` the gate is written as:

```
if MIN_PT1_R > 0 and sig.get("grade") not in _SKIP_GRADES:
    ...
self._apply_x_lift(sig)
```

`_SKIP_GRADES = ("X", "D")`, and `X_LIFT` is `"clean"` by default (stamped in both books). So
an X-graded signal that `_apply_x_lift` promotes back to `B` is **never tested by the RR
gate** — the gate has already returned by the time the lift happens. In the ON book that is
**4,384 x-lifted rows, 2,439 of them traded** (1,180 on core-11), and **0** of the 4,384 carry
the `MIN_PT1_R` skip tag. The rule is silently not applied to that population.

This is the known bug class in `research/omen-rules-unreachable-in-code`, and the codebase
already carries the warning 25 lines below this very gate, on `S_CLASSIFIER`:

> Placed AFTER `_apply_x_lift` on purpose: X_LIFT exists to rescue X-graded rows, and a drop
> applied before it would just get lifted straight back to B, which is exactly what the first
> version of this gate did.

`MIN_PT1_R` is placed on the wrong side of the same line. I did not price how many of the
2,439 would fail the RR test — the books do not carry the session extreme, so that needs an
engine re-run, not a query. The exposure is exact; the cost is untested.

## 3. What I checked and could NOT break

- **Book identity.** OFF `book_id` `2c39ced2697c26cc` **equals** the R3 baseline's
  (`research/tape/loop.json`, `baseline_2026-09-05.json.gz`). The `_emit` wrapper refactor
  (10 call sites rerouted to attach `session_hi`/`session_lo`) changed nothing on the default
  path — the fingerprint is byte-for-byte the baseline's, and neither key appears in the book
  rows. ON `book_id` `04b7f4f9778fc72a`.
- **Stamp diff, OFF vs ON:** exactly one flag, `signal_runner.MIN_PT1_R` `0.0 → 1.0`. Everything
  else that differs is bookkeeping (`built_at`, `out`, `rows`, `book_id`). Both stamps carry
  commit `e073b94a`, `dirty_py_count: 0`, `dirty_engine_py: []`, window 2024-09-04..2026-09-04,
  499 sessions. `e073b94a` is an ancestor of the row's commit `842b3f3c`.
- **Semantics vs the rulebook.** `research/omen_recall.py "RR gate first scale point HOD LOD 1R
  from entry"` returns, dated 2026-09-05: *"**RR gate: first scale point (HOD/LOD) must be >= 1R
  from entry.** Because: 'we dont want to get in on a candle close of HOD/LOD because thats
  always our first scale point, then the RR is shot.'"* The spec's settled table says the same
  and adds "skip the signal unless …". The code skips (`status="skipped"`, returns) rather than
  capping to C — correct; a capped C still trades. The measured point is right too: the gate
  reads `max(c.high for c in self.candles)` / `min(c.low …)` at emit time, and
  `backtest_week.py:1386` sets `runner.candles = candles[:i + 1]` immediately before
  `detect_signals()`, so it is *identically* the expression `backtest_week.py:1479/1484` uses
  for `scale_level` under `SCALE_PLAN=hod_then_runner_be` — LADDER PT1. The risk denominator is
  also right on this book: at `ENTRY_FILL="close"`, `sig["entry"]` already is the fill price
  (`entry_fill.py:236`), so nothing is re-priced after the gate. **Caveat, not a defect here:**
  under `SCALE_PLAN="four_rung"` PT1 comes from `levels_ladder.build_rungs` and need not equal
  the session extreme, so the gate would then measure a point the ladder does not scale at.
- **Default matches the decision.** `MIN_PT1_R = float(os.getenv("MIN_PT1_R", "0") or "0")` —
  OFF, and the decision is hold. Registered in `research/book_stamp.py` `FLAG_SOURCES`
  (line 92) and present in both stamps.
- **The uncommitted ad hoc query.** The write-up publishes "9,283 / 1,082 / −0.065R" and says
  outright it is "not committed as a script", which is a SWARM law-5 violation. Re-derived it
  myself: **9,283** ON-book rows tagged (core-11: 3,914); **1,082** of them traded in the OFF
  book (core-11: 475); mean **−0.0647R**; win 47.2% of all rows / 47.4% of decided ones. The
  numbers hold. The script now exists as `research/l1_referee.py`.
- **Sample size.** Every cell carrying a verdict clears the floor: core-11 whole 769/751 over
  25 months, H1 382/368 over 12, H2 387/383 over 13. No cell under 30 trades or 12 months is
  given a verdict anywhere in the write-up or here.
- **One change per row.** `git show --stat e073b94a` = `signal_runner.py` + `research/book_stamp.py`
  (one flag). `git show --stat 842b3f3c` = the write-up, two stamped books, `cycles.md`,
  `loop_state.json`. No engine file outside the row's scope.
- **No mark file touched** in either commit, and `git status` is clean apart from this
  referee's own two files.
- **Verify gate, run by me at `842b3f3c`:** `research/regression_gate.py` PASS (no
  baseline-fired mark went silent; any_signal 75→80, s_grade 5→25);
  `research/test_runner_stop.py` ok, 70 checks; `research/test_universe_single_source.py` ok,
  29 symbols, no private lists. All exit 0.
- **Plain English.** `cycles.md`'s label column reads "the 1R first-target rule" and the ntfy
  line format is "[OMEN] cycle 1: the 1R first-target rule — held. $/day … green months …" —
  no flag names, no ticket ids. That part is fine (the numbers in it are the full-29 ones).

## 4. Second-order note, not a defect

Dropping a signal releases the dedupe suppression window (`DEDUPE_FIRES_ONLY`: only a *fired*
signal claims it), so the ON book has **more** rows than the OFF book — 131,530 vs 127,513,
+4,017. `CLAUDE.md` warns about exactly this ("Any C-cap gate in this engine adds candidates as
well as removing them"). The write-up gestures at it ("backfilled by the next arrival-order
candidate") without naming the mechanism or the +4,017. It does not change the verdict, but any
reading of "the gate removes 9,283 signals" should be read as "removes 9,283 and creates 4,017".

## What the next agent should do

1. Add the `universe.row_filter` to `loop_cycle.py::stage_gate` (row O4's change, one line),
   re-run `--stage gate` on the two books already committed here, and correct
   `research/tape/cycles.md`, `research/tape/loop_state.json` and `research/l1_min_pt1_r.md`
   to the core-11 column above. No rebuild is needed — the books are stamped and correct.
2. Move the `MIN_PT1_R` block below `self._apply_x_lift(sig)` in `signal_runner._route`, then
   re-measure. That is a second change and belongs to its own row.
