# G7.2 / stoptest — the runner-stop safety test, wired into `verify:`

Austin: a safety test (`research/test_runner_stop.py`) was reported red since Friday, 12 of 64
checks failing, and nothing ran it — the `verify:` line only ran the recall gate. This is the
same failure mode CLAUDE.md already calls out for the recall gate itself (RED 16 days,
`5e3677ea` → G12, nobody noticed).

## What I found

Running `python research/test_runner_stop.py` directly on the current `main` (`a0997963`), in a
clean shell, in both Git Bash and PowerShell, three separate times: **exit 0, 18 of 18 laddered
checks green, all 34 stop-placement checks green.** I could not reproduce "red" or "12 of 64"
against the code as it sits on disk right now. `signal_runner.py`'s `STOP_PLACEMENT`/
`STOP_FILL_ORDER` defaults (`entry_bar` / `as_booked`), `stop_rule.MAX_LOSS_R` (1.25), and
`research/exit_lab.py`'s floor/close-trigger logic all match what the test expects. Whatever
produced the red run is not reproducible from a fresh process against the committed code, so I
am not treating it as a live regression to chase further — I checked git history for every file
this test touches (`signal_runner.py`, `research/exit_lab.py`, `stop_rule.py`) back through
Friday and nothing in that history explains a 12-check failure that isn't present now.

**What IS a real bug, independent of whether the test happened to be red just now:** the
test's own "the shipped default must be `entry_bar`/`as_booked`" check
(`placement_failures()` in `research/test_runner_stop.py`) used to read `signal_runner.py`'s
module-level `STOP_PLACEMENT`/`STOP_FILL_ORDER` constants via a plain **in-process**
`import signal_runner as sr`. Every other check in this file is careful to drive those two
env vars in an isolated child process so ambient shell state can't touch it — this one check
was the exception, and it trusted whatever the CURRENT process's environment happened to be.

Demonstrated: with `STOP_PLACEMENT=broken_level STOP_FILL_ORDER=market_on_close` set in the
shell (exactly what several other `research/g71_*`/`t24_*` scripts export for their own A/B
arms), the in-process read picks up that ambient value —

```
$ STOP_PLACEMENT=broken_level STOP_FILL_ORDER=market_on_close python -c "
import signal_runner as sr
print(sr.STOP_PLACEMENT, sr.STOP_FILL_ORDER)"
broken_level market_on_close
```

— so the old check would have printed **"shipped default STOP_PLACEMENT is 'broken_level',
must be 'entry_bar'"** and failed the whole test, even though nothing about the actual shipped
code had changed: someone just had a leftover env var set in the shell that ran it. That is a
believable, concrete way for this exact test to go red without a real regression — a stale
assumption (trust the current process's environment) standing in for the real question (what
does `signal_runner.py` ship as its default when nothing overrides it).

## The fix

`research/test_runner_stop.py`: added `_shipped_default_probe()`, which runs the same
subprocess driver every placement case already uses, but with `STOP_PLACEMENT` and
`STOP_FILL_ORDER` explicitly popped from the child's environment — so it reads the literal
`os.getenv(..., "entry_bar")` / `os.getenv(..., "as_booked")` fallback in `signal_runner.py`,
never whatever the invoking shell or a prior import happened to leave lying around. The two
"must be" assertions now check that probe's result instead of an in-process `import`.

Verified the fix does what it's for: with the same polluted environment above, the test now
still passes (correctly reports the shipped default as `entry_bar` regardless of the shell),
and every placement/floor/wick/break-even case is unchanged — 18 of 18 laddered checks, 34 of
34 placement checks, still green.

## `verify:` line

`CLAUDE.md` now runs both gates: `python research/regression_gate.py && python
research/test_runner_stop.py`. Confirmed both pass in sequence (recall gate ~14s,
runner-stop selftest ~2s, well inside the Stop hook's 180s budget).

## What this is worth

Not a dollar number — it is insurance. The same silent-gate failure mode cost 16 days on the
recall check before anyone noticed; this closes the second-known instance of it before it costs
anything. No trade, grade, or fill changed.

Script: none new beyond the edited test itself — the polluted-env repro above is a one-line
inline check, not a committed rig, and it isn't a number this project publishes.
