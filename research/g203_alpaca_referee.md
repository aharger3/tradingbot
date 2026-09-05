# g203 — adversarial referee of W3 (commit `61c15363`)

**One sentence: all five of W3's safety claims hold — the Alpaca wiring can only reach the paper
endpoint, replay cannot submit, a fired S submits exactly one order, `run_daily.ps1` carries the
flag, and no credential is printed or committed — but the referee found four real defects around
the edges, one of which can kill the whole scanner for a day.**

Verdict: **NOT refuted.** Referee: wave 2, 2026-09-05. Probe script:
`research/g203_referee_probe.py` (committed with this file). The shipped test
`research/test_alpaca_wiring.py` calls the two submit functions *directly*, so it cannot see
whether the call sites in `_emit_signal` / `scan_once` are gated correctly; the probe drives the
real `_emit_signal` with a fake broker and counts orders, which is the only way to answer claim 3.

---

## The five claims

| # | claim | verdict | how it was checked |
|---|---|---|---|
| 1 | no code path can reach `api.alpaca.markets` | **HOLDS** | grep + live introspection of the constructed client |
| 2 | `--replay` cannot submit | **HOLDS** | the assert, argument ordering in `main()`, 6/6 shipped tests, probe case 5 |
| 3 | a fired S under `--paper-broker alpaca` submits exactly one order | **HOLDS** | probe cases 1–4 through the real `_emit_signal` |
| 4 | `run_daily.ps1` launches with the flag | **HOLDS** | the file, plus the scheduled task that runs it |
| 5 | no credential printed or committed | **HOLDS** | diff scan, `.gitignore`, `_redact()` in `broker/alpaca.py` |

### 1. The live endpoint is unreachable

`broker/alpaca.py:96` is the only place a trading client is built, and `paper=True` is a Python
literal, never a variable. In `alpaca-py` 0.44.0, `TradingClient.__init__` picks
`url_override if url_override else BaseURL.TRADING_PAPER if paper else BaseURL.TRADING_LIVE` —
`url_override` is not passed, and there is no environment override on that branch. Proven, not
argued, on the exact interpreter `run_daily.ps1` uses
(`C:\Users\aharg\AppData\Local\Programs\Python\Python313\python.exe`):

```
constructed OK; client base_url = BaseURL.TRADING_PAPER      # = https://paper-api.alpaca.markets
                                                             # TRADING_LIVE = https://api.alpaca.markets
```

The only hits for the live host anywhere in the working tree are:

| where | what it is | reachable? |
|---|---|---|
| `_alp.py` (repo root, **untracked**) | wave-1 credential debug: a `GET /v2/account` against both hosts | no — not committed, not imported, not launched by anything |
| `research/t7_real_contracts.py:308` | `data.alpaca.markets` — the market **data** host, a bars GET | different host, read-only, no order path |
| `.claude/worktrees/**` | stale agent worktree copies of the two files above | not the working tree |

`_alp.py` also prints the first 6 characters of the key. It is a scratch file, not committed, and
nothing runs it — **recommend deleting `_alp.py` and `_alp2.py`** so a future grep of this claim
comes back clean.

### 2. Replay cannot submit — three independent barriers

1. `main()` does `sys.exit(run_replay(...))` at line 1595, **before** the broker is constructed at
   line 1645. `--replay --paper-broker alpaca` never builds a broker at all.
2. `run_replay()` sets `runner.replay = True` and passes `regime_detector=None` with no `broker=`
   argument, so `scan_once` runs with `broker=None` and both call sites are skipped.
3. Both `_alpaca_submit_entry` and `_alpaca_submit_exit` open with
   `assert not getattr(runner, "replay", False)` — and it **raises loudly** rather than silently
   skipping, so a call-site regression crashes instead of quietly placing an order. Probe case 5
   confirms the AssertionError propagates out of `_emit_signal` with `broker.orders == []`.

`python research/test_alpaca_wiring.py` → **6/6 passed**.

### 3. Exactly one order per fired S

`research/g203_referee_probe.py`, driving the real `_emit_signal`:

| case | result |
|---|---|
| `sac_grade="S"`, options resolve | **1 order**, quantity = `plan.contracts`, symbol = Alpaca's own resolved contract (not `plan.occ_symbol`) |
| `sac_grade="A"` | 0 orders (`_tier` → WATCH, the paper branch never runs) |
| `sac_grade="C"` | 0 orders |
| `broker=None` (no flag) | 0 orders, `_emit_signal` still returns True |
| `place_order` raises | swallowed, does not propagate, sim book unaffected |
| `runner.replay=True` | raises, 0 orders |

Two further guards make a duplicate hard: `scan_once` dedupes on `seen_signal_keys` before
`_emit_signal` is reached, and the order carries
`idempotency_key = f"{symbol}-{ts}-{direction}-entry"`, which `broker/alpaca.py` passes to Alpaca as
`client_order_id` — Alpaca rejects a repeat of one.

**Scope nuance, not a defect:** an 84% re-entry is TRADE tier *regardless of grade*
(`_tier`, line 1103), so a re-entry with `sac_grade="C"` also submits (probe case 6 confirms:
1 order). That is the engine's long-standing re-entry exemption, not something W3 introduced —
but "only a fired S submits" is not literally true, and the ledger will show it.

### 4. The launcher

`run_daily.ps1` line 36: `& $python live_scanner.py --paper --paper-broker alpaca`. The scheduled
task **`OmenSignalBot` [Ready]** runs that file — so Monday's 09:25 ET start is the flagged path.
`main()` also refuses `--paper-broker alpaca` without `--paper` (exit 1), and `choices=["alpaca"]`
means no other venue can be named.

### 5. No credential printed or committed

- The `61c15363` diff contains no key-shaped literal (scanned for `APCA-API`, `PK…`, `AK…`,
  `api_key=`, `secret_key=`). Only 4 files changed; `.env` is not among them and is gitignored.
- Keys live in machine-scope environment variables and `.env`, read once in `AlpacaBroker.__init__`.
- `_redact()` strips the key and secret out of every exception message before it can reach a log
  line, and `place_order` wraps its failure as `RuntimeError(_redact(...))`, which is what
  `_alpaca_submit_entry` truncates into the ledger. The ledger holds symbols, quantities, order ids
  and statuses — nothing secret.
- The printed lines (`🔷 ALPACA BUY 3x … -> <order id>`) go to `journal/scanner-<date>.log`, which
  **is** a tracked path. Order ids only; no credential.

---

## Four defects found (none refute the claims)

| # | severity | defect |
|---|---|---|
| D1 | **high (availability)** | `broker = AlpacaBroker()` in `main()` (line 1650) is **unguarded**. If the SDK is missing or the keys are absent, the constructor raises and the scanner dies at startup — **no signals at all that day**, instead of falling back to sim-only. It will not fire on this box (alpaca-py 0.44.0 is installed on Python313 and both keys are machine-scope), but the daily pass now has a new single point of failure. Fix: wrap in try/except, print the failure, and continue with `broker = None`. |
| D2 | medium (latent) | `_alpaca_submit_exit` sells `entry_rec["quantity"]` — the **full** entry size — but a `CLOSE` event that follows a `SCALE` carries only the runner leg in `ev["contracts"]`. Probe case 7: CLOSE says 1, the exit order sends 3. Latent only because the ladder is off by default (`OMEN_LIVE_LADDER=0`, `RULE6_ENABLED=False`); turning it on over-sells at the paper broker. |
| D3 | medium (latent) | `scan_once` mirrors only `event == "CLOSE"`. `SCALE` and `BE_SCALE` are not mirrored, so under a ladder the Alpaca position stays full while the sim book scales out. Same root cause as D2. |
| D4 | low | The replay guard is an `assert`, which `python -O` strips. `run_replay` never constructs a broker, so this is belt-and-suspenders — but a `raise RuntimeError` costs nothing and cannot be optimised away. |

Housekeeping: `journal/alpaca-paper.jsonl` is **not** gitignored, so tomorrow's ledger will show up
as untracked and can be committed by accident. It carries no secret, but it is a runtime artifact.

## What I would change before Monday

One line, D1: make the broker construction fail-soft so a broker outage cannot cost a whole
trading day of signals.
