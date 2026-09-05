# g202 — O2 referee (commit 0a0dfaad)

O2's four flags (DAY_POLICY, ENTRY_WINDOW_END, FIRE_A_WHEN_NO_S, VETO_1D) all default to
today's pre-O2 behaviour: NOT REFUTED.

## What was checked

1. `git diff 0a0dfaad~1 0a0dfaad -- signal_runner.py live_scanner.py` — every changed line,
   read by eye (no `--replay` run; the pre-O2 commit's replay loop hangs, per the task).
2. `research/test_day_policy_flags.py` — 27 checks, all pass (flag parsing/validation,
   `select_day_trades()` selection semantics, live_scanner subprocess wiring).
3. `.env` grepped for the four new keys and for `MAX_TRADES_PER_DAY`/`CONSECUTIVE_LOSS_HALT` —
   confirms the deployed `.env` never sets any of the four new vars, and pins
   `MAX_TRADES_PER_DAY=3`/`CONSECUTIVE_LOSS_HALT=2` (the pre-O2 shipped values).
4. `_load_env_file` — confirmed it only fills a key not already in `os.environ`, so the
   comment's claim ("an 'if unset' override would never fire against a real .env") holds.

## Per-flag default-resolves-to-pre-O2 check

| flag | default | pre-O2 behaviour | resolves? |
|---|---|---|---|
| `DAY_POLICY` | `"first3"` | `max_signals_per_day=3`, `CONSECUTIVE_LOSS_HALT=2` (unchanged) | yes — `if _LIVE_DAY_POLICY == "one_and_done"` never trips at default, so `max_trades`/`max_losses` fall through to the same `MAX_TRADES_PER_DAY`/`CONSECUTIVE_LOSS_HALT` env reads as before |
| `ENTRY_WINDOW_END` | `"11:00"` | `ENTRY_CUTOFF` default `"11:00"` gated entries | yes — `_effective_cutoff = min(ENTRY_CUTOFF, ENTRY_WINDOW_END)` = `min("11:00","11:00")` = `"11:00"`, identical to the old direct `ENTRY_CUTOFF` check |
| `FIRE_A_WHEN_NO_S` | `False` | A-tier never fired | yes — read-only; `select_day_trades()` (the only consumer) is not called anywhere in the live entry path (`grep` for callers outside `research/g16*` returns none) |
| `VETO_1D` | `False` | no daily-trend veto | yes — same: read-only, only consumer is the uncalled `select_day_trades()` |

## Env-var parse audit (inversion check)

- `DAY_POLICY = os.getenv("DAY_POLICY", "first3").strip().lower()`, validated against
  `("first3", "one_and_done")` — no inversion, empty/unset -> `"first3"`.
- `ENTRY_WINDOW_END = os.getenv("ENTRY_WINDOW_END", "11:00").strip()`, validated against
  `("09:45", "11:00")` — no inversion.
- `FIRE_A_WHEN_NO_S = os.getenv("FIRE_A_WHEN_NO_S", "0").strip().lower() in (...)` — standard
  truthy-string parse, unset -> `"0"` -> `False`. No inversion.
- `VETO_1D` — same pattern as `FIRE_A_WHEN_NO_S`. No inversion.

None of the four parses can flip a default true; all fall through to the documented pre-O2
value when unset.

## select_day_trades wiring

`grep -rn "select_day_trades" --include="*.py" .` (excluding `research/g16*`) returns no
callers — the function exists in `signal_runner.py` but is not invoked from
`live_scanner.py`'s live entry path, `signal_runner.py`'s own `SignalRunner`, `omen_bot.py`,
or `paper_trader.py`. `FIRE_A_WHEN_NO_S`/`VETO_1D` are therefore genuinely inert on live
entries at any setting, matching the code comments' claim.

## Test run

`research/test_day_policy_flags.py`: 27/27 PASS — flag parsing + validation (10),
`select_day_trades()` semantics (10), live_scanner subprocess wiring under `env={}` and
`DAY_POLICY=one_and_done` (7).

## Verdict

**refuted = false.** Every changed line in the diff is a flag read (or a comment), each
default resolves to the pre-O2 shipped behaviour (`DAY_POLICY=first3`,
`ENTRY_WINDOW_END=11:00` behaving identically to the old `ENTRY_CUTOFF` check,
`FIRE_A_WHEN_NO_S=0`/`VETO_1D=0` both genuinely unwired), the deployed `.env` does not set any
of the four, and `test_day_policy_flags.py` passes 27/27.
