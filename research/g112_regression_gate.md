---
date: 2026-09-03
row: S3
status: done
---

# S3 — fix regression_gate.py's silent 16-day red

## What the row asked

`research/regression_gate.py` was reported to have dropped 6 `s_grade` marks and exited FAIL
since `5e3677ea` (2026-08-11), unnoticed. Fix it, and make its result land somewhere that
cannot go silently red again.

## The gate already passes — and the fix is already in history, dated before this row

Ran it fresh on current HEAD (`36c8cd27`):

```
baseline: any_signal 75, s_grade 5
current:  any_signal 80, s_grade 25
new fires (not a failure): any_signal +5, s_grade +20
PASS: no baseline-fired mark went silent.
```

**PASS, exit 0.** Traced why: the gate (`current_sets()` in `regression_gate.py`) replays
detection through `t4_engine_recall.CaptureRunner._route`. Commit `34a41413` (2026-08-30,
"The router fix that every recall number rests on was never committed") found that
`CaptureRunner._route` — the shared harness `regression_gate.py`, T0, T1 and every recall
number since `5e3677ea` all run through — was a hand-written copy that never called
`super()._route()`, so every routing gate the real engine grew after `5e3677ea` was inert in
this specific harness. That fix landed 2026-08-30, five days before this spec was written,
and it is what restored the dropped marks: the harness was scoring a frozen, stale copy of
the router, not the shipped one.

**Confirmed this is real, not baseline manipulation:**
- `research/baseline_3.8.json` has not been touched since `8d8dc8db` (OMEN 7.0 wave 1),
  which predates the router fix, `RETEST_REQUIRED`, the retest-gate change, and everything
  else that has landed since — nobody re-locked it to a weaker target.
- `research/austin_marks_v2.jsonl` (the 159-mark join target) has one commit in its entire
  history (`7cc471d1`, omen-3.6) and has never been edited since — nobody shrank the
  denominator.

So there was no live regression left to fix in the gate's own logic. What was actually
missing, and is this row's real deliverable, is visibility: **nothing ever ran
`regression_gate.py` automatically.** It only ran by hand, which is exactly how a 16-day red
went unnoticed in the first place — the fix that resolved it was found by accident during
unrelated recall work, not by this gate raising an alarm.

## What was changed

`research/daily_run.cmd` (the weekday-16:15 `OmenDailyHomework` scheduled task) now runs
`python research/regression_gate.py` after the deck build and writes `REGRESSION GATE: PASS`
or `REGRESSION GATE: FAIL -- ...` into that day's `journal/daily-<day>.log`, non-fatal to the
deck build (a detection regression is a finding to surface, not a fetch/build failure worth
blocking Austin's homework over). One block, reversible. No live-trading code touched, no
outward-facing behavior added — this is a local scheduled task writing to a local log file,
same as the fetch/build steps already in it.

## Adversarial instruction: did the fix pass by dropping marks?

No. Checked directly (not just re-asserted): `research/baseline_3.8.json`'s
`n_marks: 159` matches `research/austin_marks_v2.jsonl`'s current 159 rows exactly, and
neither file has been modified since well before the router fix landed. The PASS is earned
by the engine now correctly running its own shipped router in this harness, not by shrinking
what's being measured.

## Adversarial pass

A separate agent, instructed to refute and default to refuted when uncertain, independently
re-ran the gate, re-read commit `34a41413`'s diff, re-checked both files' git history by
commit date (not just log order), and re-read the new `daily_run.cmd` block for batch-script
control-flow bugs. Verdict: **CONFIRMED** on all four claims — same PASS and numbers on a
fresh run, the router-delegation fix is real and dated before this row, neither
`baseline_3.8.json` nor `austin_marks_v2.jsonl` was touched after that fix, and the new
`daily_run.cmd` block is syntactically clean and non-fatal (no `exit /b 1` on gate failure).

It also surfaced a real gap: `research/daily_run_1105.cmd` (AUGUR's 11:05 blind pass, a
second daily scheduled entry point added since `daily_run.cmd` was written) had no gate
check at all — the same blind spot in miniature, one path logging it while the other stays
silent. Fixed in the same commit: same non-fatal, log-only block added there too, placed
before `deliver_homework.py` so it never reaches the phone push.

## verify

`python research/regression_gate.py; test $? -eq 0` — exit 0, confirmed above.

## plain

The 16-day-silent test that checks whether the trading engine forgot how to spot Austin's
setups was already fixed by accident last week — this just makes sure nobody has to find
that out by accident again, by running it every day and writing the result down.
