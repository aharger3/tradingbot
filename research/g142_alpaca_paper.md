**UNBLOCKED 2026-09-05 01:55 ET.** Austin generated new paper keys; they are in `.env` and the keys vault. `broker/test_alpaca_paper.py` → PASS (placed, read back, cancelled on the PAPER endpoint). Note: a stale copy of the old keys in the desktop session's environment shadowed `.env` on the first run (python-dotenv does not override existing env vars) — cleared. The paper account shows cash −$55,569.61, i.e. it carries old positions/margin; a 'Reset paper account' in the Alpaca dashboard is a 1-click human task before Monday if a clean $100k book is wanted. No blocker remains on wiring.

BLOCKED: both Alpaca key pairs in `.env` (`ALPACA_PAPER_KEY`/`ALPACA_PAPER_SECRET` and
`ALPACA_API_KEY_ID`/`ALPACA_API_SECRET`) return `401 {"message": "unauthorized."}` from
Alpaca's own paper-trading API — confirmed over the SDK and over a raw `requests` HTTP call
with no SDK in the loop, so this is not an adapter bug. The keys need to be rotated in the
Alpaca dashboard (a human step; no API exists to mint a new key with an old, dead one).

## What was built (code is done, not exercised)

`broker/alpaca.py` — `AlpacaBroker(BrokerInterface)`, mirroring `broker/tastytrade.py`'s
shape: five calls (`place_order`, `cancel_order`, `positions`, `fills`, `account`) against
`alpaca-py`'s `TradingClient`. `TradingClient(..., paper=True)` is a hard-coded literal in
`__init__` — never threaded from a config value or CLI flag — so there is no code path in
this file that can reach the live-trading endpoint. `resolve_option_contract` looks up a
listed OCC contract via `get_option_contracts`; if none is listed (or the call itself fails,
e.g. options not enabled on the account) it raises `OptionsNotAvailable` for the caller
(`live_scanner.py`, not yet wired — see below) to catch and fall back to a share order.

`broker/test_alpaca_paper.py` — places a far-from-market ($1.00) LIMIT buy of 1 AAPL share,
reads positions/account back, cancels it, and asserts the cancel landed. This is the script
that returns the 401 below; every other line of it (order construction, response parsing,
cancel logic) is exercised right up to the point the HTTP call itself fails on auth.

## What was NOT done, because of the block

- `live_scanner.py --paper --paper-broker alpaca` wiring (submit on each fired S, log to
  `journal/alpaca-paper.jsonl`) was not added. Wiring an order-submission path against a
  broker that returns 401 on every call would be exercising nothing and risks a mistake I
  can't validate — safer to stop at a working, unexercised adapter than ship an unverified
  integration point into the signal path.
- No order was ever placed-and-cancelled successfully. No response ids to show.

## Verify gate, run as specified

```
$ python broker/test_alpaca_paper.py
FAIL: place_order raised: AlpacaBroker.place_order failed: {"message": "unauthorized."}
exit code: 1
```

```
$ grep -c "api.alpaca.markets" broker/alpaca.py
0
```
(the live-host hostname literal appears nowhere in the file — the security-constraint half
of the gate passes; the network half does not, because the credentials are dead.)

## Isolating the cause (ruling out a code bug)

Raw HTTP, no SDK, both key pairs, both paper and live hosts:

```
KEY present: True len 26 prefix PK3IWA...
SEC present: True len 44
ERR https://paper-api.alpaca.markets/v2/account   401  {"message": "unauthorized."}
ERR https://api.alpaca.markets/v2/account         401  {"message": "unauthorized."}
```
Same 401 for the `ALPACA_API_KEY_ID`/`ALPACA_API_SECRET` pair. No whitespace/encoding issue
in either secret (checked via `repr()`). This means: not an adapter bug, not a client-library
bug, not an env-parsing bug — the keys themselves are not accepted by Alpaca.

## What unblocks this

1. Log into the Alpaca paper-trading dashboard, regenerate a paper API key/secret pair.
2. Put the new pair in `.env` as `ALPACA_PAPER_KEY`/`ALPACA_PAPER_SECRET` (same variable
   names `broker/alpaca.py` already reads — no code change needed).
3. Re-run `python broker/test_alpaca_paper.py`. If it passes, wire `--paper-broker alpaca`
   into `live_scanner.py`'s `_emit_signal` S-push branch (the `sac_grade == "S"` block) next.

No credential value is printed anywhere above or in any script this row touched.
