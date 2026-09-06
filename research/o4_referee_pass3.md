# O4 referee — pass 3 (the loop controller, after the repair)

**Builder commit under review: `add86484`** ("O4 repair: guard state/cycles.md writes behind
--dry-run, strip ambient env for OFF arm"). Refereed at HEAD `0f6a826a`, with
`add86484` an ancestor. Earlier passes, untouched by this page:
`research/o4_referee.md` (pass 1, `27e7e04a`, upheld with one defect) and
`research/o4_referee_pass2.md` (pass 2, `3ace41cb`, refuted on two defects plus one
finding). Pass-3 code: **`research/o4_referee_pass3.py`** — 52 checks, the gate, the
halves split, the day-policy unit and the DAY_POLICY pricing all retyped from SWARM.md
and CLAUDE.md rather than imported from `loop_cycle`.

**Verdict: UPHELD.** Both pass-2 defects are genuinely repaired, reproduced here twice —
once against a fake engine in a scratch tape directory, once live against the real
`research/tape/loop.json` and the real ledger. Every gate cell, unit, boundary, blocked
path, push string and stamp re-derives. Two residuals and one carried finding are filed
below; none of them blocks the row, and one of them is explicitly outside it.

**52 checks, 50 pass.** The two failures are the documentation checks in
§Residual-1 — deliberately written as failing assertions so the next pass sees them.

---

## DEFECT-1 (pass 2) — `--dry-run` wrote the ledger and moved the stop counter — **FIXED**

`stage_gate` now computes the whole state block on an in-memory copy and puts
`STATE_JSON.write_text` and `append_cycle_row` inside the same `if not dry_run:` block as
the ntfy push. Verified two ways.

**Scratch, with synthetic books** (`o4_referee_pass3.py::check_dry_run`, state seeded at
`cycle_count` 7 / `consecutive_holds` 3):

| | `--dry-run` | live |
|---|---|---|
| `loop_state.json` MD5 | unchanged | changed |
| `cycles.md` MD5 | unchanged | one row appended |
| on-disk `cycle_count` | 7 | 8 |
| on-disk `consecutive_holds` | 3 | 0 |
| `notify_ntfy.push` calls | 0 | 1 |
| decision JSON printed | yes | yes |

The dry run still prints the full decision — the thing the two production corruptions were
reaching for — while changing nothing.

**Live, against the real files.** Built a throwaway 15-day pair with the repaired code and
ran a real `--stage gate --dry-run` on `research/tape/loop.json`:

```
BEFORE  ca067f517d0bbf2b9d87d4991ae71dae  research/tape/cycles.md
        e73b0d04b502c73493ed5a8a4a11ec7a  research/tape/loop_state.json
AFTER   ca067f517d0bbf2b9d87d4991ae71dae  research/tape/cycles.md
        e73b0d04b502c73493ed5a8a4a11ec7a  research/tape/loop_state.json
```

Byte-identical. The gate printed `"decision": "hold"`, `"cycle": 6`,
`"consecutive_holds": 1` — a preview, written nowhere. Logs:
`research/tape/logs/o4ref3_smoke.log` and `o4ref3_gate_dry.log` (that directory is
gitignored). The two scratch books were deleted; nothing was committed from them.

## DEFECT-2 (passes 1 and 2) — the OFF arm never unset the flag — **FIXED**

`build_book` now treats an override value of `None` as "delete this key from the
subprocess environment", and `stage_build` passes `{flag: None}` for the OFF arm.
Exercised end to end against a stub engine that reports back what it saw
(`check_off_arm_env`): with `PLANTED_O4_FLAG=1` exported in the ambient shell — the exact
worst case pass 1 named, an ambient value equal to `--on`'s —

| arm | value the build subprocess saw |
|---|---|
| OFF | `<absent>` |
| ON | `1` |

Two things worth stating because they bound the fix. The pop happens **after**
`env.update(rebuild_cfg["env"])`, so a flag a future config deliberately pins in
`rebuild.env` would also be stripped from the OFF arm — that fails safe, because the
OFF-vs-baseline `book_id` assertion would then block. And nothing in the engine path reads
a `.env` file (`grep -rn "load_dotenv"` finds only `broker/test_alpaca_paper.py`), so
popping the key really does reach the default.

**The books already on the tape are not retroactively suspect.** `book_DAY_POLICY_off`
stamps `signal_runner.DAY_POLICY: first3`, and at its build commit `5e8b5b89` the code
default was `os.getenv("DAY_POLICY", "first3")`. The OFF arm was clean; the ON arm stamps
`3fires_stop_win_or_2loss`. No re-run is owed.

## FINDING-3 (pass 2, carried) — cycle 5 shipped on a delta of exactly zero — **still open, correctly deferred**

Reproduced from scratch with a retyped unit and retyped monthly buckets: the
`up_to_3_stop_win_or_2loss` unit selects the **identical 769 rows** from both DAY_POLICY
arms, even though the underlying core-11 books differ by **1,909 traded rows OFF vs 814
ON**. The pricing unit already implements the flag under test, so the "ship" measured
nothing. The builder left it flagged rather than fixed, and that is the right call under
one-change-per-row: fixing it means redefining either the unit or the experiment. It is a
`loop.json` / measurement-design question for whoever revisits DAY_POLICY, not a bug in
this controller.

*Unit / fill / exit for those figures:* `up_to_3_stop_win_or_2loss` on the core-11 slice,
honest **close** entry fill, shipped engine exit (1R hard stop filled on the intrabar
touch, `SCALE_PLAN=hod_then_runner_be`, LOSS_HALT on). Books
`research/tape/book_DAY_POLICY_{off,on}.json.gz`, script `research/o4_referee_pass3.py`.
769 trades over 25 months — above the 30-trade / 12-month floor, so the "zero delta" is a
verdict, not a small-sample shrug.

---

## What re-derived (independently, this pass)

**The gate.** Eighteen hand cases through `loop_cycle.half_verdict` and through a gate
retyped from SWARM.md law 2; all eighteen agree. A fall of more than 5% fails (94.9 against
100); exactly 5% passes; any rise passes however large; green months falling by one fails
on its own with dollars flat; a negative baseline reads "the loss may not get more than 5%
worse" (−100 → −104.9 passes, −105.1 fails); a zero baseline requires ≥ 0. Both halves are
scored independently and `ship` needs `enough` and `pass` on both.

**Sample floor.** 29 trades or 11 months on the BEFORE side gives `enough: False,
pass: None`; exactly 30 and exactly 12 are enough.

**The boundary.** A session dated **2025-09-01 lands in H2**; `half_n_days` agrees with
`split_halves` on the same rows.

**The three units,** against CLAUDE.md's day policy and the spec's day-policy row (*up to
3 S fires; stop after a win or after 2 losses*): stops after the first win; stops after the
second loss; a win after one loss ends the day; caps at three; `first_of_day` takes the
day's earliest candidate; `every_signal` takes every traded row. A zero-P&L scratch burns
one of the three slots — named as behaviour, not faulted, same as pass 2.

**The OFF-arm equality path.** A planted mismatch returns
`{"decision": "blocked", …}` — **blocked, not hold** — carrying both real `book_stamp`
ids, never builds the ON arm, and `main()` exits 1.

**The push.** One `notify_ntfy.push` in the file, inside `if not dry_run:`. The line
carries the plain-English label and no flag name, no ticket id, no CLI jargon:
*"[OMEN] cycle 8: a plain english label — shipped. $/day 62.0 → 62.0, green months
26 → 26."*

**Smoke.** Re-run live on the repaired code: `--stage build --smoke` exits 0 and invokes
`backtest_2y.py --days 15` for **both** arms (two occurrences in
`research/tape/logs/o4ref3_smoke.log`), printing the skip of the OFF==baseline `book_id`
check.

**The ledger row.** `-52.0 -> -52.0`, `11 -> 11`, 769 trades all reproduce from the two
stamped books under retyped arithmetic.

**Stamps.** Both DAY_POLICY books carry commit `5e8b5b89`, `dirty_engine_py: []`,
`dirty_py_count: 0`, `built_at`, the window 2024-09-04..2026-09-04 / 499 sessions, and the
flag under test itself (`signal_runner.DAY_POLICY`). `5e8b5b89` is an ancestor of
`add86484`.

**Housekeeping.** `git show --stat add86484` = **one file**, `research/loop_cycle.py`,
+29/−6: one change. No mark corpus in the diff or in `git status`.
`research/test_loop_gate.py` 27/27. Verify gate green at HEAD: `regression_gate.py` PASS,
`test_runner_stop.py` 70 checks across 3 sections, universe single-source ok (29 symbols,
25 backtested).

---

## Residuals (filed, not blocking)

**Residual-1 — the `--dry-run` documentation is now wrong.** `main()` still advertises
`--dry-run` as `help="suppress the ntfy push"`, and the module docstring still lists
"appends one row to cycles.md, updates loop_state.json … pushes one ntfy line (unless
`--dry-run`)", which reads as the guard applying to the push alone. That sentence is
exactly what led pass 2 to the defect in the first place. Two lines of prose; this row's
code is correct, its description is not.

**Residual-2 — the ledger is still not idempotent on a live re-run.** Pass 2 offered two
fixes: guard the writes, or key the append on (flag, off `book_id`, on `book_id`). The
builder took the first. A second **non**-dry `--stage gate` on the same book pair still
appends a second row and still moves `consecutive_holds` — reproduced
(`RESIDUAL: a second live gate of the same pair appends a SECOND ledger row`). Of the two
corruptions `loop_state.json`'s `_repair_note` records, the L4 one was a `--dry-run` and is
now prevented; the L2 one is described only as "a byte-identical re-append", so it is not
established that the repair covers it. Idempotency is a second change and belongs in its
own row.

**Residual-3 (carried from pass 1) — the sample floor is applied to the BEFORE arm only.**
An ON arm with under 30 trades still receives a verdict. Largely masked in practice,
because a book thin enough to fall under the floor also loses green months and fails on
that leg, but it is not guarded.
