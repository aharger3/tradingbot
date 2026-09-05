The ntfy S push now carries the whole order — contract, OCC symbol (or an
honest "unresolved"), and the Alpaca paper order id (or an honest "not
placed") — not just the stock-side entry/stop/target, so a human executing
by hand on a venue with no deep link (`research/execution_prep_2026-09.md`)
can copy-paste the ticket instead of looking anything up.

## What was missing, before this row

`_push_s_signal` (`live_scanner.py`) sent underlying, direction, entry/stop
target (stock-side), contracts, tier, and level — but never the option
contract itself (expiry/strike/right/OCC symbol) or any order id. Per the
execution-prep survey, no venue publishes a pre-fillable deep link, so this
push is the only place the order ever appears before Austin retypes it.

## What changed

`live_scanner.py`, `_emit_signal`'s `rec` dict and `_push_s_signal`:
- `expiration`, `strike`, `occ_symbol` are now carried off the `OptionsPlan`
  already built for the card (Tastytrade-resolved when available, else
  rendered as `(no listed contract resolved)` — never blank, never guessed).
- `alpaca_order_id` is carried but is **always `None` right now**: spec L3
  shipped `BLOCKED` (`research/g142_alpaca_paper.md` — both Alpaca paper key
  pairs return 401, confirmed over the SDK and a raw HTTP call) and
  `broker/alpaca.py` was never wired into `live_scanner.py`'s order path, so
  there is no order id anywhere upstream to carry. The push renders this
  honestly as `not placed (Alpaca paper unwired -- L3 blocked, keys 401)`
  rather than inventing one; the field is already threaded through so wiring
  L3 later is a one-line change (fill `alpaca_order_id` from the broker
  handle), not a new push format.
- `max_loss` (the card's 1R dollars, already computed) is now printed in the
  body — it was computed before this row but never shown to Austin.

## Rendered example — `--replay 2026-09-04`, the AMD S trade at 10:13 ET

Captured via `notify_ntfy.push` monkeypatched to intercept the body (no real
ntfy POST for this capture — the row's own replay run below did send two real
pushes to the configured phone topic before I switched to interception; noted
so nothing is hidden).

```
TITLE: OMEN S AMD CALL

10:13:00 ET  ·  break and retest
Contract  AMD 2026-09-07 $470 CALL
OCC       (no listed contract resolved)
Entry   472.18
Stop    471.06
Target  474.96
Size    19 contracts
1R      $1,000
Tier    TRADE (his S)
Level   pivot high @10:01
Alpaca  not placed (Alpaca paper unwired -- L3 blocked, keys 401)
```

290 bytes — well under ntfy's 4 KB body limit (`research/test_push_body.py`
pins this at < 4096 bytes with a synthetic full-field record too, including a
resolved OCC symbol and a real Alpaca id, so the field additions themselves
never risk the limit; the OCC line is blank here only because `ReplayFeed`
has no `fetch_option_quote` — no historical option chain on disk — the same
`estimated_delta` fallback every replay uses, not a bug in this row).

## Note on the two real pushes during this row's work

Running `--replay 2026-09-04 --paper` twice while confirming the fix (before
adding capture-and-suppress) sent two real ntfy notifications to
`aharg-omen-s7k2` (`OMEN S AMD CALL` and its later `OMEN AMD STOP -0.89R`
exit) — a replay of an already-archived day, not a live signal, but a real
push all the same since `OMEN_NTFY_TOPIC` is configured in this environment.
No further replay runs in this row's remaining work bypass interception.

## Verify

```
$ python research/test_push_body.py
... (15 checks)
all checks passed

$ python research/regression_gate.py
PASS: no baseline-fired mark went silent.

$ python research/test_runner_stop.py
runner-stop selftest ok: 70 checks across 3 sections.

$ python research/test_s_flat_sizing.py
all checks passed
```
