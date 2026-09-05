# g161 — the four O1 flags shipped, no new default

Nothing about what fires or what the book earns changed today: `DAY_POLICY`, `ENTRY_WINDOW_END`,
`FIRE_A_WHEN_NO_S` and `VETO_1D` now exist as read config in `signal_runner.py`/`live_scanner.py`,
each defaulting to exactly today's shipped behavior, because O1's adversarial pass **REFUTED**
shipping any grid arm — no arm, baseline included, was positive in both H1 and H2.

## Why no default moved

O1 (`research/g160_tweak_grid.py`) swept `DAY_POLICY x ENTRY_WINDOW x TIER_POLICY x VETO_1D` as a
16-arm grid, S_CLASSIFIER on/off, over `research/bt2y_trades_retest_on.json` (the shipped
`RETEST_REQUIRED=1` book). The row's own gate — "defaults = the grid winner ONLY if it improved
both halves and did not cut S recall" — was never met:

| arm | ev_r all | ev_r H1 | ev_r H2 | $/day | win% | green months/23-25 |
|---|---:|---:|---:|---:|---:|---:|
| baseline (`omen_metrics.first_of_day_arm`, shipped) | 0.034 | +0.136 | **−0.068** | $33.9 | — | 13/25 |
| best full-book grid arm (`one_and_done`, window=09:45, veto1d=on, tier=s_only) | 0.064 | +0.236 | **−0.062** | $11.2 | 51.1% | 15/23 |

Every arm in the grid, including the shipped baseline, is H2-negative. Shipping the "best" arm as
a new default would trade a proven H1 number for an unproven one and still lose money in H2 — the
row's own bar. Full arm table: `research/g160_tweak_grid.md` / `.json`.

## What shipped instead

Four flags, each validated and defaulting to today's behavior, plus a pure selection-arm helper
(`signal_runner.select_day_trades`) that reproduces `g160_tweak_grid.build_arm`'s exact semantics
so this grid can be re-run without a second copy of the selection logic:

| flag | default | matches | live wiring |
|---|---|---|---|
| `DAY_POLICY` | `first3` | `omen_bot.Session`'s shipped `max_signals_per_day=3` / halt-after-2-losses | `live_scanner.py`: `one_and_done` forces `max_trades=1, max_losses=1` outright (see note below); `first3` leaves `MAX_TRADES_PER_DAY`/`CONSECUTIVE_LOSS_HALT` exactly as before |
| `ENTRY_WINDOW_END` | `11:00` | `SESSION_END` / `ENTRY_CUTOFF`'s own default | `live_scanner.py`: effective cutoff = `min(ENTRY_CUTOFF, ENTRY_WINDOW_END)` — can only tighten, never loosen, the existing cutoff |
| `FIRE_A_WHEN_NO_S` | `0` | today's ladder wiring (`compute_austin_tier` is reported only) | **read-only**, stamped into `journal/scanner_status.json`'s `grading_arm` block; does not gate live entries |
| `VETO_1D` | `0` | today's ladder wiring (no live 1D veto) | **read-only**, same stamp; does not gate live entries |

`FIRE_A_WHEN_NO_S`/`VETO_1D` are intentionally not wired as a live entry gate. Two independent
reasons, both already on record: (1) `compute_austin_tier`'s S/A/C ladder is "reported only —
nothing below branches on it" (CLAUDE.md, "Two grade ladders"), and gating live entries on
`sgrade=='S'` was already priced negative (`research/r3_downgrade_grader_ab.md`: S recall +0,
false fires 29%→33%). (2) `VETO_1D` in the O1 grid is a documented **proxy** (`spy_trend` vs
candidate direction), not a real daily-timeframe filter, and no VETO_1D arm won both halves either.
Wiring either into production would be exactly the re-proposal CLAUDE.md already forbids. They are
read and reported (same pattern `live_scanner.py` already uses for `ENABLE_SAC_LADDER`/
`SAC_LADDER_VARSET`) so a live run can be labeled with the same arm tag `g160` uses, nothing more.

**Note on `DAY_POLICY=one_and_done`:** it overrides `max_trades`/`max_losses` to 1/1 outright,
not merely when those are otherwise unset — `.env` pins `MAX_TRADES_PER_DAY=3` /
`CONSECUTIVE_LOSS_HALT=2` unconditionally (`_load_env_file` only fills a key not already in
`os.environ`), so an "if unset" override would silently never fire against the real deployment.

## Verify

- `python research/test_day_policy_flags.py` — 24 checks, all PASS (flag parsing/validation,
  `select_day_trades()` semantics matched against `g160_tweak_grid.build_arm`, and `live_scanner`
  wiring for `max_trades`/`max_losses`/effective entry cutoff/reporting stamp).
- `python research/regression_gate.py && python research/test_runner_stop.py` — both green,
  unchanged from before this row (no baseline-fired mark went silent; the shipped stop path still
  books no worse than −1.000R).

## Files touched

- `signal_runner.py` — four flags (`DAY_POLICY`, `ENTRY_WINDOW_END`, `FIRE_A_WHEN_NO_S`,
  `VETO_1D`) + `select_day_trades()`.
- `live_scanner.py` — reads the four flags; wires `DAY_POLICY`/`ENTRY_WINDOW_END` into real
  session limits/entry cutoff; stamps `FIRE_A_WHEN_NO_S`/`VETO_1D` read-only into
  `scanner_status.json`.
- `research/test_day_policy_flags.py` — new test, gated by `verify:`.
- `research/g161_tweaks_shipped.md` — this file.
