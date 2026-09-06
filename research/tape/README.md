# research/tape/ — stamped books and the loop's own ledger

## the tape (T1)

`research/build_tape.py` &rarr; `research/tape/omen-tape.html`. Extends
`research/build_bt2y_report.py`'s facet engine (imports `encode()`, `FACETS`,
`book_of()`, the whole client-side script) rather than forking it; run
`python research/build_tape.py` to rebuild after any of the books below
change, and `python research/test_tape.py` to verify it.

**What it opens on:** the page's default filters reproduce R3's baseline
exactly — core-11 pool, honest close fill, his day policy (up to 3 trades a
day, stop after the first win or the second loss). That is **769 trades,
-$52/day, mean R -0.0335, 11 of 25 months green** — the same numbers in
`research/tape/loop.json`'s `baseline_figures.whole`, asserted to the dollar
by `research/test_tape.py`. Clear a filter and you widen the pool or switch
unit; nothing else changes the default.

### What every filter reads

| filter | reads |
|---|---|
| Book / flag variant (`source`) | which stamped book a row came from: `baseline` (the R3 book), or `L1_on`…`L5_on` (each Phase-L flag's ON arm — every OFF arm equals the baseline exactly, so "off" is just `source=baseline`). |
| Fill mode (`fillmode`) | `close` (the honest fill, `entry_fill.ENTRY_FILL=close`) or `phantom` (`ENTRY_FILL=published` — the void back-dated fill every pre-2026-08-30 dollar figure used; kept as a column, never a target). `next_open`/`limit_level`/`mid_candle`/`chase_once`/`as_booked` are **not** in this filter — see "the fill-mode study" below. |
| Pool (`lane`) | core-11 / index-3 (QQQ, SPY, IWM) / full — a signal can sit in more than one, so this is multi-select like Tags. |
| Day policy (`policy`) | `every_signal` (every fired-and-traded-or-halted core-11 candidate), `first_of_day` (the day's first), `up_to_3` (his day policy) — computed by `research/loop_cycle.up_to_3_rows` / `research/g72_suppress_price.oneaday_rows`, imported, not re-derived. Scoped to core-11 only, matching `loop.json`'s `universe.row_filter`: a non-core row never carries a policy tag, so combining a wide pool with a policy filter shows only the core-11 rows inside it. |
| Symbol, setup (`setup`/`confluence`), both grade ladders (`sgrade`, `grade`), month (`ym`), week (`wk`), weekday (`dow`), entry-time bucket (`slot`), level (`level`/`level_name`), asset class, watchlist tier, Fired/filtered (`book`/`status`) | unchanged from `build_bt2y_report.py` — every field already on a trade row. |
| Exit model (`exitmodel`) | one value today: `ladder (hod_then_runner_be)` — every book in this directory ships the scale-out ladder; no flat-2R book has been built here yet. |
| Instrument (`instrument`) | one value today: `shares (T2 not landed)` — `research/g213_instruments.md` has not landed; this facet keeps its place in the rail so the layout does not move when it does. |

### What is scoped out of the row-level engine, and why

- **`status == "skipped_d"`** (the engine's own downgrade filter — 106,217 of
  the baseline's 127,513 raw signals) is dropped from every source. That
  candidate-by-candidate autopsy already exists
  (`research/build_probes.py`'s silent-day probe); keeping it here would
  multiply the page's size ~6x for a dimension this page does not analyze.
- **Comparison sources** (phantom fill, every Phase-L flag's ON arm) keep
  only traded + halted rows, not the full candidate firehose — they exist to
  be priced at the trade level, not explored candidate-by-candidate. Only
  the default `baseline`/`close` source keeps the richer fired /
  tight-stop-skip / filtered breakdown.
- **The fill-mode study** (`research/tape/fillarms_*.json.gz` — R1's
  `as_booked`/`chase_once`/`close`/`limit_level`/`mid_candle`/`next_open`
  arms, core-11 and full-29) is a **separate table below the main tape**,
  not merged into the filter rail. Those 12 books were built off a
  different, dirty commit lineage (`57f2fbd2…`/`c7d52853…`, never the
  baseline's `29e4abc6`) on a different trade schema entirely
  (`entry_time`/`fill_mode`/`austin_tier`, no month/week/pool/tags). Merging
  them would either forge fields the replay never recorded or imply a
  same-day A/B against the baseline that SWARM.md's law 5 forbids. The table
  ranks the 12 combinations only against each other.
- **A genuine near-duplicate in the source data**, found while building this
  page: the replay can fire two differently-named pivots that sit at the
  identical price in the same minute (e.g. ACHR 2025-01-07 10:39, "pivot low
  @10:18" and "pivot low @10:24", both $11.13, priced identically) — a real
  arrival-order property of `signal_runner.py` (a level's identity is its
  name, not the price it converges to), not a page defect. 127 such pairs
  exist across the merged sources. This page's own "no repeats" self-check
  (`research/build_tape.check_no_repeats`, run at build time and asserted by
  `research/test_tape.py`) treats them as distinct rows — they differ in
  `level_name`, a real recorded field — because collapsing them would change
  which candidate a day's 2nd/3rd arrival is under his day policy, silently
  moving R3's already-published $-52/day number. Fixing the underlying
  engine dedupe is a second change this row does not own; flagged
  separately, not fixed here.

### No-repeat guarantee

One row per (source, fill mode, symbol, day, entry minute, direction,
entry, stop, pnl, status, level name) among traded rows — a
construction-integrity check on this page's own book-merging, not an audit
of the replay engine. `research/test_tape.py` fails the build above zero.

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
- `instruments_2026-09-05.json.gz` — T2, `research/g213_instruments.py`. Re-prices
  the R3 baseline's `up_to_3_stop_win_or_2loss` unit (core-11 only) in three
  instruments: shares (the baseline's own `pnl`), futures micros (SPY→MES,
  QQQ→MNQ, tick-rounded, integer-sized, $0.62/side commission; single names
  are `n/a`), and options (nearest-expiry ATM contract, real Polygon 1-minute
  bars where the wall-clock-bounded fetch reached them, a 0.42-delta model
  everywhere else — every row's `options.instrument_source` says which).
  Keyed by `research.g72_suppress_price.idkey`. Report: `research/g213_instruments.md`.
  Hand-check: `research/g213_verify.py` → `research/g213_verify.md`.
