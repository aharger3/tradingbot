# SCALE_PLAN cycle 11 (2026-09-20) was a no-op

**Cause.** `loop_queue.json` queued `{"flag": "SCALE_PLAN", "on": "blind_2r"}`
(commit `d459eee2`) -- matching every other queue entry's convention (env
var == Python attribute name) and `book_stamp.py`'s `FLAG_SOURCES` entry for
it. But `backtest_week.py` never reads bare `SCALE_PLAN`: it reads
`OMEN_SCALE_PLAN` (legacy fallback `OMEN_LADDER_MODE`, default `"B"` ->
`"hod_then_runner_be"`) at `backtest_week.py:202-208` -- it and
`OMEN_SSCORE_SIZING` are the only two `FLAG_SOURCES` flags whose real env var
carries an `OMEN_` prefix; every sibling reads its own bare name
(`ENTRY_FLOOR_STOP:51`, `DEDUPE_MODE:130`, `LADDER_RUNNER_GUARD:228`).
`loop_cycle.build_book()` (`loop_cycle.py:266-296`) set `env["SCALE_PLAN"] =
"blind_2r"` exactly as told; nothing ever reads that key, so the ON arm
silently rebuilt the OFF arm's book.

**Evidence.** Both books stamp `backtest_week.SCALE_PLAN:
"hod_then_runner_be"` (shipped default) and share `book_id
d5ba41a41d65e1e4`: `research/tape/book_SCALE_PLAN_{off,on}.json.gz`
(4055/127574 both). `book_stamp.py:64-66` already names this shape of hole
for the four-rung ladder flags -- different cause (missing rungs), same
symptom.
**Correct flags.** `research/r2_referee_pass2.py:124` sets
`os.environ["OMEN_SCALE_PLAN"] = "none"` and asserts `bw.SCALE_PLAN is None`
(`:131`) -- the F1-era "blind 2R (current behavior)" path
(`backtest_week.py:171`). Correct queue entry: `{"flag": "OMEN_SCALE_PLAN",
"on": "none"}`, not `SCALE_PLAN`/`blind_2r` (a truthy, non-`"four_rung"`
string just falls into the same generic ladder branch as the shipped
default, `backtest_week.py:1359,1516` -- there was never a live `"blind_2r"`
value).

**Guard.** `stage_build`'s OFF-vs-baseline check can't catch this: it only
proves OFF reproduces the baseline, never compares ON against OFF. Added to
`stage_gate()`: ON `book_id == ` OFF `book_id` forces `decision = "noop"` --
never `"ship"`, no `shipped_flags.record_ship()`, ntfy reads `NO-OP (ON book
== OFF book -- flag not wired)`. Test: `research/test_loop_cycle_noop_guard.py`.
