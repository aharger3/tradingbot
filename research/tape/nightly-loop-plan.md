# nightly loop plan (burn-0919, row omen-nightly-loop)

1. Already exists (built by nucleus-tick, 2026-09-17, commit history on main): `research/nightly_loop.py`
   pops the top non-`_example` entry off `research/tape/loop_queue.json`, runs `loop_cycle.py --config
   research/tape/loop.json --flag ... --on ... --label ... --stage all`, applies the existing no-regression
   gate inside `loop_cycle.py`, appends one line to `research/tape/nightly.md`, never raises past main()
   (catches exceptions, always writes a row, always exits 0).
2. Already exists: `research/nightly_loop.cmd` (thin trigger, logs to `journal/nightly-loop-<date>.log`,
   `exit /b 0` unconditionally) and `research/tape/loop_queue.json` (`[]`-equivalent: one `_example`-keyed
   row only, which `is_real()` skips — no live-trading flag seeded).
3. Already exists: `research/tape/nightly.md` has its header + one `empty` receipt line from 2026-09-17.
4. What was missing (the actual gap this row closes): the Windows scheduled task `OmenNightlyLoop` was
   never registered — nucleus-tick's build agent is permanently banned from calling schtasks/Register-
   ScheduledTask (nucleus-tick-prompt.md), so the row shipped file-only and left a human/interactive step.
5. What I add: register `OmenNightlyLoop` (weekdays 20:00, `cmd.exe /c research\nightly_loop.cmd`,
   WorkingDirectory the repo root, LogonType Interactive, UserId aharg, StartWhenAvailable=True) — same
   shape as the sibling `OmenDailyHomework` task already on this box.
6. Then run `research\nightly_loop.cmd` once by hand to prove the registered path still works end to end
   and add a fresh receipt line.
7. Risk: `loop_queue.json` is still empty (by design — never seed a live-trading flag), so every night
   until Austin queues a real `{flag,on,label}` candidate, the task will write an `empty` row and do
   nothing else. That is correct behavior, not a bug, but it means the loop will not actually loop until
   a candidate is queued.
8. Risk: `loop_state.json` shows `consecutive_holds: 1` — four more holds in a row (real candidates) stops
   the loop per SWARM.md; that stop condition is unaffected by this row.
9. No trading code touched. `signal_runner.py` untouched. No `--allow-drift`, no live order anywhere in
   this file or `nightly_loop.py`/`loop_cycle.py`.
10. Done = `schtasks /query /tn OmenNightlyLoop` exits 0 AND `research/tape/nightly.md` and
    `research/tape/loop_queue.json` are non-empty (both already true; task registration is the only
    remaining gap).
