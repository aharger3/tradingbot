# research/tape/ — stamped books and the loop's own ledger

Every book in this directory is stamped (`research/book_stamp.py`): commit, dirty
flag, every behaviour-changing engine flag's effective value, the date, the
session window and the script that built it. Never A/B two books built on
different days or from different bases (SWARM.md law 5).

## loop_cycle

`research/loop_cycle.py` is the one program every Phase-L row runs to ship or
hold a flag under the no-regression gate. Full contract in the script's own
docstring; this section documents `loop.json`'s fields for whoever fills them
in next (R3 first, then each L-row).

Copy `research/tape/loop.example.json` to `research/tape/loop.json` and edit:

| field | meaning |
|---|---|
| `baseline_book` | path to the stamped book (`.json` or `.json.gz`) the loop currently ships from. `--stage build`'s OFF arm must fingerprint-match this book (`book_stamp.book_id`) or the cycle is `blocked` — the code landing changed something even with the flag at its default. |
| `unit` | which trade-set arithmetic the gate reads: `every_signal` (every traded signal), `first_of_day` (the day's first fired-and-traded candidate), or `up_to_3_stop_win_or_2loss` (his day policy: up to 3 fires, stop after a win or the second loss). Whichever one is the loop's baseline unit — set once, by R3, not per row. |
| `rebuild.script` | the builder to run as a subprocess, e.g. `backtest_2y.py`. |
| `rebuild.args` | its CLI args, e.g. `["--days", "730"]`. `--out PATH` is appended automatically. |
| `rebuild.env` | env vars the rebuild always needs set (rare — most flags are the one under test, passed via `--flag`/`--on`). |
| `halves_boundary` | the ISO date (`"2025-09-01"`) splitting H1/H2 for the gate. Never move this without re-running every prior cycle's numbers. |
| `targets.dollars_per_day` | the loop's stop condition, part 1 — `$500` (Austin's bar). |
| `targets.avg_win_over_avg_loss` | the loop's stop condition, part 2 — `2.0` (his 2:1 ask). The third target, every month green, is checked directly off `months_green == months` and is not a separate config field. |
| `gate.max_dollar_drop_pct` | the no-regression gate's ceiling on a $/day fall — `5.0` (SWARM.md law 2: "minor declines fine, not major"). Green months may never fall, on either half, regardless of this number. |

### Running a cycle

```
python research/loop_cycle.py --config research/tape/loop.json \
    --flag SOME_ENV_FLAG --on 1 --label "plain English name" --stage build
      # (run this one in the background — it rebuilds two books)
python research/loop_cycle.py --config research/tape/loop.json \
    --flag SOME_ENV_FLAG --on 1 --label "plain English name" --stage gate
```

or both in one call with `--stage all`. `--dry-run` suppresses the ntfy push
(use it for a rehearsal); `--smoke` runs both arms at `--days 15` to prove the
plumbing without ever building a full two-year book in this row.

Every gate call appends one row to `cycles.md` and updates `loop_state.json`
(cycle count, consecutive holds, whether the loop's target is met, and the
`stop` flag the dispatcher reads). Logs for every rebuild land in
`research/tape/logs/` (gitignored — the books and the cycle ledger are the
record, not the console output).

### Files this directory accumulates

- `book_<flag>_off.json.gz` / `book_<flag>_on.json.gz` — one pair per cycle, stamped.
- `cycles.md` — one row per cycle: date, label, flag, decision, $/day and
  green-months before/after, whether each half had enough sample, trade
  count, the two book paths, the script.
- `loop_state.json` — `{cycle_count, consecutive_holds, target_met, stop,
  stop_reason, history: [...]}`.
- `logs/` — one log per rebuild subprocess (gitignored).
