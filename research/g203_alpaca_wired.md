Alpaca paper submission is now wired: `--paper-broker alpaca` submits a real (paper-account) MARKET
order on every fired S and its matching exit, replay is asserted to never submit, and
`run_daily.ps1` now launches with the flag on.

## What changed

`live_scanner.py` (no other shared module touched, per this row's edit list):

- New submission functions `_alpaca_submit_entry` / `_alpaca_submit_exit`, called from the
  existing `_emit_signal` S-open branch and the existing `paper.mark()` marking loop in
  `scan_once` — the simulated `PaperBook` still drives the whole state machine (governor,
  phone push, session halts); Alpaca submission is an additional, best-effort mirror of the
  same trade, keyed by `f"{symbol}|{opened_at}"` so an entry and its exit can be matched
  without adding any field to `paper_trader.PaperPosition` (that file is not on this row's
  edit list).
- Entry: `broker.resolve_option_contract` against Alpaca's own listed chain (not the
  Tastytrade-derived `plan.occ_symbol` the simulated book already has — Alpaca may not list
  the identical contract). On `OptionsNotAvailable`, falls back to a share order sized so
  `shares * |entry - stop| == 1R` (`DEFAULT_MAX_LOSS * size_pct`), with the per-share risk
  floored at `signal_runner.min_risk_floor` so a razor-thin stop can't blow the size up (the
  bug class the project CLAUDE.md already names for the options path).
- Exit: on a `CLOSE` event from `paper.mark()` (stop or target under the shipped default —
  the ladder/Rule-6 paths are both off), submits the opposite-side MARKET order for the same
  quantity the entry submitted.
- Every submission (and every skip/error) logs one JSON line to `journal/alpaca-paper.jsonl`.
- `--paper-broker alpaca` is a new CLI flag; it requires `--paper` and constructs one
  `AlpacaBroker()` for the whole process.
- **Replay never submits.** `run_replay()` sets `runner.replay = True`; the live/once path in
  `main()` sets `runner.replay = False`. Both submission functions assert
  `not runner.replay` before ever calling `broker.place_order` — a call-site regression that
  forgot to gate this raises loudly instead of silently placing an order on a replayed day.
  `run_replay()` also never constructs or threads a broker at all (belt-and-suspenders).
- The phone-push record's `alpaca_order_id` field (previously hardcoded `None` since L3
  shipped blocked) now carries the real `broker_order_id` when a submission succeeds.

`run_daily.ps1`: launches with `--paper --paper-broker alpaca` instead of bare `--paper`.

## Unit test — `research/test_alpaca_wiring.py`

A `FakeBroker(BrokerInterface)` with a controllable `resolve_option_contract` (mimics a
listed vs. unlisted chain) and a `place_order` that just records the `Order` it received.
Six tests, all passing:

```
$ python -m pytest research/test_alpaca_wiring.py -q
......                                                                   [100%]
6 passed in 0.60s
```

- one options submit per fired S (BUY, MARKET, contracts == `plan.contracts`)
- the shares fallback fires on `OptionsNotAvailable` and sizes to exactly 1R
  (`$1000 / $2` risk-per-share = 500 shares, in the test's numbers)
- one closing submit per exit, opposite side, same symbol/quantity as the entry; a second
  close event against an already-popped key is a no-op (no double-close)
- `runner.replay = True` makes both submit functions raise `AssertionError` before touching
  `broker.place_order` — zero orders recorded
- `run_replay` and `main` are grepped (via `inspect.getsource`) for the literal
  `runner.replay = True` / `= False` lines, so the guard's wiring itself is under test, not
  just the function that reads it

## Real smoke test — one placed-and-cancelled paper LIMIT

`broker/test_alpaca_paper.py` places a far-from-market ($1.00) LIMIT buy of 1 AAPL share on
the PAPER endpoint, reads it back, and cancels it:

```
$ python broker/test_alpaca_paper.py
placed: broker_order_id=50a8bf89-7133-4cdb-a379-a2ddae53168a status=working
cancelled: True
PASS: placed, read back, cancelled on the Alpaca PAPER endpoint
```

**Note on `g142`'s "BLOCKED — 401" finding:** re-run here with the same keys and it passed
first try — not because the keys changed again, but because this shell's environment
carried stale `ALPACA_PAPER_KEY` / `ALPACA_PAPER_SECRET` / `ALPACA_API_KEY` /
`ALPACA_API_SECRET` values that shadow `.env` (python-dotenv never overrides an
already-set env var — the exact trap `g142` names in its own body). Confirmed by `env |
grep -i ALPACA` showing all five Alpaca vars already set in this shell before Python ever
ran; unsetting them (`env -u ALPACA_...`) and re-running passed clean. This is a
recurring foot-gun for anyone re-running the smoke test from an already-initialized
terminal, not a key-rotation issue — worth a note for whoever launches the scheduled task's
shell.

## Verify gate

```
$ python research/regression_gate.py
PASS: no baseline-fired mark went silent.
$ python research/test_runner_stop.py
runner-stop selftest ok: 70 checks across 3 sections.
```

Both pass, unchanged behavior on the existing signal/stop paths — this row only adds a new,
optional submission side-channel gated behind a CLI flag that defaults off.

## What this does NOT do

No sizing, grading, or entry-timing change. No shared module besides `live_scanner.py` was
edited (`broker/alpaca.py` and `run_daily.ps1` per the row's own explicit allowance).
`paper_trader.py` was not touched — the simulated book, the number Austin's marking sessions
and the money reports read, is unchanged; Alpaca's paper fills are a parallel, informational
mirror only, readable from `journal/alpaca-paper.jsonl`.
