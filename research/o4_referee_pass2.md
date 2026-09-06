# O4 referee — pass 2 (the loop controller)

**Builder commit: `8ecb043e`** ("O4: loop controller -- gate tests 27/27, smoke ok"),
later touched by `d317ff43` (L2: apply `universe.row_filter`). Refereed at HEAD
`ccd7fa06`. Pass 1 is `research/o4_referee.md` / `o4_referee.py` (commit `27e7e04a`) and
is untouched by this page. Pass-2 code: `research/o4_referee_pass2.py`, which retypes
the gate, the halves split and the day-policy unit from SWARM.md rather than importing
loop_cycle's versions, and re-prices a real book pair from scratch.

**Verdict: REFUTED.** Not the arithmetic — every gate cell, every unit and every figure
in the ledger reproduces exactly from independent code. Refuted on two counts:

1. the builder's re-dispatch report asserts pass 1's defect "was subsequently repaired
   by other rows (`d317ff43`, `5e8b5b89`)". **It was not.** It is open at HEAD.
2. a second, previously unnamed controller defect: `--dry-run` writes the ledger and
   moves the loop's stop counter. It has already fired twice in production and both
   times was patched by hand in the data, not in the code.

---

## DEFECT-1 (new) — `--dry-run` is not a dry run, and it drives the loop's stop switch

`loop_cycle.py::stage_gate` writes the state file and appends the ledger row **before**
the push guard:

```
    STATE_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")
    append_cycle_row(...)
    if not dry_run:
        notify_ntfy.push("OMEN loop", line)
```

`--dry-run` is documented in `main()` as "suppress the ntfy push", and that is all it
does. So `--stage gate --dry-run` — the obvious way to re-inspect a decision's JSON —
silently appends a duplicate row to `research/tape/cycles.md`, increments `cycle_count`,
and moves `consecutive_holds`, the counter `MAX_CONSECUTIVE_HOLDS = 5` uses to tell the
dispatcher **stop the loop**.

Demonstrated against scratch copies; the live ledger was verified untouched before and
after (7 table lines, `cycle_count` 5):

| | before | after one `--stage gate --dry-run` |
|---|---:|---:|
| DAY_POLICY rows in `cycles.md` | 0 | 1 |
| `cycle_count` | 7 | 8 |
| `consecutive_holds` | 3 | 0 |

Not hypothetical. `research/tape/loop_state.json`'s own `_repair_note` records it firing
twice on 2026-09-05: an L2 duplicate append, and an L4 duplicate that "pushed
`consecutive_holds` to 5 and tripped a false 'stop' the loop dispatcher would have read
as real". Both were repaired **in the data, by hand**. The code path is unchanged, so
the next agent who re-runs a gate to look at its output corrupts the ledger again. The
builder's own smoke run hit it too — the commit message says it "wrote and then cleaned
up the ledger/state".

**Fix (one function, not made here):** put the same `dry_run` guard around
`STATE_JSON.write_text` and `append_cycle_row`, or make the ledger append idempotent on
(flag, off `book_id`, on `book_id`).

## DEFECT-2 (pass 1's, still open) — the OFF arm never unsets the flag

`build_book()` does `env = dict(os.environ)` and only ever *adds* keys, and
`stage_build` calls `build_book({}, off_path, …)` — the flag name never reaches the
builder at all. If the flag under test is already set in the ambient shell, the OFF arm
builds with the flag **on**, and the module docstring's *"the OFF arm (flag left at its
current default -- env simply unset)"* is false. Pass 1 named this on `27e7e04a`.

The builder's report says it "was subsequently repaired by other rows (`d317ff43` L2
repair applying `universe.row_filter`, `5e8b5b89` L5 repair)". Checked directly:

- `d317ff43` adds 21 lines to `loop_cycle.py` — the `apply_universe_filter` helper.
  Nothing environmental.
- `5e8b5b89` touches `day_policy.py` only, 1 file.
- `git diff 8ecb043e..HEAD -- research/loop_cycle.py | grep -E '^[+-].*(env|os\.environ)'`
  returns **nothing**. Not one environment line has changed since the build.

The defect stands. Its worst case is the one pass 1 named: an ambient value equal to
`--on`'s value makes both arms the same book, the gate compares a book to itself, both
halves pass, and the cycle reports **ship** for a change that was never measured.
`--smoke` skips the `book_id` assertion that would otherwise catch the mismatched case.

## FINDING-3 — cycle 5 shipped a change whose measured delta is exactly zero

Not strictly O4's (the unit came from `loop.json`), but it is what the controller
recorded and no page says it. Cycle 5 graded `DAY_POLICY` on the unit
`up_to_3_stop_win_or_2loss` — which *is* the day policy, applied in post-processing by
`loop_cycle.up_to_3_rows`. On the core-11 slice the arms differ enormously (**1,909
traded rows OFF vs 814 ON**, a 1,095-trade gap), but the priced unit selects the
**identical 769 rows** from both books: whole, H1 and H2 match to the cent. The "ship"
rests on a delta of exactly zero — safe, since a no-op cannot regress, but it measures
nothing, and `loop_cycle` does not warn when the pricing unit already implements the
flag under test.

*Unit / fill / exit for those figures: `up_to_3_stop_win_or_2loss` on the core-11 slice,
honest `close` entry fill, shipped engine exit (1R hard stop on the intrabar touch,
`SCALE_PLAN=hod_then_runner_be`, LOSS_HALT on). Script `research/o4_referee_pass2.py`,
books `research/tape/book_DAY_POLICY_{off,on}.json.gz`. 769 trades over 25 months —
above the 30-trade / 12-month floor in every slice.*

---

## What held

**The gate.** Sixteen hand-built cases through both `loop_cycle.half_verdict` and an
independent implementation written from SWARM.md law 2; all sixteen agree. A fall of
more than 5% fails (94.9 vs 100), exactly 5% passes, any rise passes however large. A
negative baseline reads "the loss may not get more than 5% worse" (−100 → −104.9 passes,
−105.1 fails); a zero baseline requires ≥ 0. Green months falling by one fails on its
own with dollars flat. **Both halves are scored independently** and `ship` requires both
`enough` and both `pass`.

**Sample floor.** 29 trades or 11 months on the BEFORE side gives `enough: False,
pass: None`; exactly 30 / exactly 12 is enough. (Caveat, unchanged from pass 1: the floor
is applied to the BEFORE arm only.)

**The boundary.** A session dated **2025-09-01 lands in H2**, and `half_n_days` agrees
with the split. On the real book 248 H1 + 251 H2 = 499 = the book's own
`meta["sessions"]`, so the whole row and the halves share a denominator even after the
core-11 row filter — the docstring's SESSION-COUNT CAVEAT did not bite here either.

**The three units,** against the day policy as CLAUDE.md and the spec state it (*first
good setup of the day, stop if it wins*; up to 3 fires, stop after a win or two losses):
`every_signal` = every traded row; `first_of_day` = the earliest candidate each day;
`up_to_3_stop_win_or_2loss` stops after the first win, stops after the second loss, caps
at three. Two behaviours named rather than faulted: a zero-P&L scratch burns one of the
three slots, and `halted` rows sit in the candidate pool (inherited deliberately from
`g72_suppress_price.oneaday_rows`).

**The OFF-arm equality path.** It compares genuine `book_stamp` ids
(`meta["stamp"]["book_id"]`, falling back to `book_stamp.book_id(rows)`), the fingerprint
is a real function of the trades, and a mismatch returns `{"decision": "blocked", …}` —
**blocked, not hold** — never builds the ON arm, and exits non-zero. Live proof:
`loop.json`'s `baseline_book_id` `2c39ced2697c26cc` matches the baseline on disk and the
`DAY_POLICY` OFF arm reproduces it exactly.

**The push.** One `notify_ntfy.push` in the whole file, inside `if not dry_run:`. The
line interpolates the plain-English `label`, never `flag`, and carries no flag name, no
ticket id and no CLI jargon: *"[OMEN] cycle 5: up to three trades a day, stop after a win
or two losses — shipped. $/day -52.0 -> -52.0, green months 11 -> 11."* (The `(repair)`
suffix on cycle 5's label is the one wart Austin would see.)

**Smoke.** No 15-day log from the builder survived — `research/tape/logs/` is gitignored
and it was cleaned up. So this pass ran it again: `--stage build --smoke` on a dummy flag
exits 0, builds **both** arms with `backtest_2y.py --days 15` (28 symbols, 10 sessions
2026-08-20..2026-09-04), and prints the skip of the OFF==baseline `book_id` check. The
claim reproduces. The scratch books were deleted; the log stays in the gitignored
`logs/` as `o4ref_smoke.log`.

**The real pair, re-priced from scratch.** `book_DAY_POLICY_{off,on}.json.gz`, core-11
filter retyped, day-policy unit retyped, monthly buckets retyped. Every slice matches
`loop_cycle.compute_all` to the cent, and every cell of the ledger row it wrote —
`ship`, `-52.0 -> -52.0`, `11 -> 11`, 769 trades — reproduces.

**Housekeeping.** `git show --stat 8ecb043e` = 5 files (the program, its test, the config
template, a README section, one `.gitignore` line): one change. No mark corpus appears in
that diff or in `git status`. Both tape books carry a full stamp — commit `5e8b5b89`,
`dirty_engine_py: []`, `dirty_py_count: 0`, every engine flag including `DAY_POLICY`,
window 2024-09-04..2026-09-04, 499 sessions — and that commit is an ancestor of HEAD.
`research/test_loop_gate.py` is 27/27. Verify gate green at HEAD: `regression_gate.py`
PASS, `test_runner_stop.py` 70 checks, universe single-source ok.
