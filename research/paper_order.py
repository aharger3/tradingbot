"""OMEN 10.0 V5: books (or passes) Austin's own paper order for one candidate.

Arm B of V5 (`omen-10-0-spec.md`, "Phase V addendum"). The stage-manager (a
different repo/session, NOT this one -- see docs/rows/v5-contract.md) deals
each candidate from journal/candidates_<day>.json as an AskUserQuestion card.
When Austin taps **S** it shells out to this CLI to book the same paper
order the engine would have; when he taps **pass** (or the 10:35 cutoff
passes with no answer) it shells out with `--pass` to record that instead.

    python research/paper_order.py --arm austin --id AAPL_2026-09-14_0944
    python research/paper_order.py --arm austin --pass AAPL_2026-09-14_0944

Idempotent: booking the same id twice refuses the second call (checked
against journal/alpaca-paper.jsonl, not local state -- this process starts
fresh on every invocation). `--arm` is required and today only `austin` is
accepted; `engine` bookings happen inline in live_scanner.py, never here.

Paper only. Before any submit this asserts the constructed AlpacaBroker's
underlying client base URL names the paper endpoint -- belt-and-suspenders
on top of broker/alpaca.py's own hard-coded `paper=True` (SWARM.md: "NEVER a
live order").

V6 (docs/rows/v5-contract.md addendum, Austin 2026-09-16): `--entry-rule`
picks the order this arm books, same switch and same default as
`live_scanner._alpaca_submit_entry` -- "close" (MARKET, pre-V6 behaviour) or
"g88" (LIMIT at the setup's own level, default for this paper arm; see
`_g88_level_price`'s docstring for the exact measured rule and its source,
research/g88_level_limit.py / research/g88_level_limit.md). Never a market
order under g88.

One structural difference from the engine arm: this is a one-shot CLI, shelled
out to once per tap and then it exits -- there is no later moment in THIS
process to cancel a resting limit that never filled by the research's 11:00 ET
cutoff (`live_scanner.ENTRY_CUTOFF`; only the always-running scan loop can do
that, for its own "engine" orders -- see `_alpaca_cancel_stale_g88_entries`
there). This CLI relies on the order's own DAY time-in-force (`broker/base.py`
`Order.time_in_force` default) as the broker-side backstop instead: Alpaca
expires an unfilled DAY order at the close of that trading day on its own, no
extra code needed here, even though that is later than the research's 11:00 ET
cutoff. A closer-to-11:00 cancel for this arm needs a process that outlives
one CLI invocation, which is the stage-manager's territory, not this repo's
(docs/rows/v5-contract.md: "No card-dealing, no AskUserQuestion call, no
cron -- the stage-manager's job, out of this repo").
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from research.candidates_writer import candidates_path  # noqa: E402

_ALPACA_LEDGER = ROOT / "journal" / "alpaca-paper.jsonl"

# Same switch, same default and same research citation as
# live_scanner.PAPER_ENTRY_RULE -- kept as two module constants rather than a
# shared import because the two files already don't share any code path for
# order construction (paper_order.py is a standalone CLI); duplicating one
# os.getenv() call is cheaper than a new shared module for it.
PAPER_ENTRY_RULE = os.getenv("PAPER_ENTRY_RULE", "g88")


def _g88_level_price(cand: dict) -> float:
    """The g88 resting-limit price for one candidate -- same rule as
    live_scanner._g88_level_price, applied to a candidates_<day>.json row
    instead of a live `sig` dict. That file's schema (docs/rows/v5-contract.md
    section 1) carries `entry`/`stop` but no separate `level_price` field, so
    this always takes the `stop` branch of the shipped fallback
    (`t.level_price or t.stop`, backtest_2y.py) -- for break-and-retest
    (BNR_STOP_MODE="level", signal_runner.py) the level IS the stop, so this
    is exact, not an approximation, for the setup this arm sees today."""
    return cand.get("level_price") or cand["stop"]


def _assert_paper_endpoint(broker) -> None:
    """Refuse to place a single order unless the broker's own client names
    the paper endpoint. broker/alpaca.py already hard-codes `paper=True`
    (the only thing that can construct a client in that file); this is a
    second, independent check at the call site per the row's own law."""
    base_url = str(getattr(broker._client, "_base_url", ""))
    if "paper" not in base_url.lower():
        raise RuntimeError(
            f"refusing to submit: Alpaca client base URL does not name "
            f"paper ({base_url!r}). This must never place a live order."
        )


def _load_ledger_rows() -> list[dict]:
    if not _ALPACA_LEDGER.exists():
        return []
    rows = []
    with _ALPACA_LEDGER.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _already_booked(candidate_id: str) -> bool:
    for r in _load_ledger_rows():
        if r.get("candidate_id") == candidate_id and r.get("event") in ("entry", "pass"):
            return True
    return False


def _log(event: dict) -> None:
    _ALPACA_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with _ALPACA_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _find_candidate(candidate_id: str) -> dict | None:
    # candidate id is "<SYMBOL>_<YYYY-MM-DD>_<HHMM>" -- the day is embedded.
    parts = candidate_id.split("_")
    if len(parts) < 3:
        return None
    day = parts[1]
    path = candidates_path(day)
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    for c in doc.get("candidates", []):
        if c["id"] == candidate_id:
            return c
    return None


def record_pass(candidate_id: str, arm: str = "austin") -> dict:
    rec = {"event": "pass", "candidate_id": candidate_id, "arm": arm}
    _log(rec)
    return rec


def book_order(candidate_id: str, arm: str = "austin", entry_rule: str | None = None) -> dict:
    """Book a paper order for `candidate_id` on Alpaca's paper endpoint,
    sized to the candidate's own risk (1R = its max_loss, falling back to
    DEFAULT_MAX_LOSS) by `options_sizer.size_share_qty` -- the same formula
    `live_scanner._alpaca_submit_entry` uses for Arm A, capped at 25% of the
    paper account's own equity, shares of the underlying only (V5b,
    docs/rows/v5-contract.md). Raises on failure; the caller (the
    stage-manager's shell-out) sees a nonzero exit.

    `entry_rule` ("close" or "g88", default PAPER_ENTRY_RULE) picks the order
    type -- see the module docstring. Sizing is unchanged either way: risk is
    always priced off the candidate's own `entry`/`stop`, because those
    describe Austin's own tap, not the order sent to Alpaca."""
    cand = _find_candidate(candidate_id)
    if cand is None:
        raise RuntimeError(f"no candidate {candidate_id!r} in "
                            f"journal/candidates_{candidate_id.split('_')[1] if '_' in candidate_id else '?'}.json")

    from broker.alpaca import AlpacaBroker
    from broker.base import Order, OrderSide, OrderType
    from options_sizer import DEFAULT_MAX_LOSS, size_share_qty

    entry_rule = entry_rule or PAPER_ENTRY_RULE
    assert entry_rule in ("close", "g88"), f"unknown entry_rule {entry_rule!r}"

    broker = AlpacaBroker()
    _assert_paper_endpoint(broker)

    entry, stop = cand["entry"], cand["stop"]
    max_loss = cand.get("max_loss") or DEFAULT_MAX_LOSS
    account = broker.account()
    qty = size_share_qty(entry, stop, account.equity, max_loss=max_loss)
    if qty <= 0:
        rec = {"event": "entry_skip", "candidate_id": candidate_id, "arm": arm,
               "symbol": cand["symbol"], "entry_rule": entry_rule,
               "reason": "zero-quantity after sizing"}
        _log(rec)
        return rec

    side = OrderSide.BUY if cand["direction"] == "call" else OrderSide.SELL
    idem = f"{cand['symbol']}-{candidate_id}-austin-entry"
    if entry_rule == "g88":
        order = Order(symbol=cand["symbol"], side=side, quantity=qty,
                      order_type=OrderType.LIMIT,
                      limit_price=_g88_level_price(cand),
                      idempotency_key=idem)
    else:
        order = Order(symbol=cand["symbol"], side=side, quantity=qty,
                      order_type=OrderType.MARKET, idempotency_key=idem)
    try:
        handle = broker.place_order(order)
    except Exception as e:  # noqa: BLE001
        # A rejected tap must leave a trace. live_scanner's engine path logs
        # entry_error on the same failure; without this, Austin taps S, Alpaca
        # rejects (e.g. insufficient buying power -- see the 2026-09-12 row in
        # journal/alpaca-paper.jsonl) and the card vanishes from both arms with
        # nothing to count at verdict time.
        _log({"event": "entry_error", "ts": cand["ts"], "symbol": cand["symbol"],
              "direction": cand["direction"], "order_symbol": order.symbol,
              "quantity": qty, "arm": arm, "candidate_id": candidate_id,
              "entry_rule": entry_rule, "error": str(e)[:200]})
        raise

    rec = {
        "event": "entry", "ts": cand["ts"], "symbol": cand["symbol"],
        "direction": cand["direction"], "order_symbol": order.symbol,
        "side": order.side.value, "quantity": order.quantity,
        "broker_order_id": handle.broker_order_id,
        "status": handle.status.value, "idempotency_key": idem,
        "arm": arm, "candidate_id": candidate_id, "max_loss": max_loss,
        "entry_rule": entry_rule,
    }
    _log(rec)
    return rec


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--arm", required=True, choices=["austin"],
                    help="Only 'austin' books here -- engine bookings happen "
                         "inline in live_scanner.py.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", metavar="CANDIDATE_ID", help="book a paper order for this candidate")
    g.add_argument("--pass", dest="pass_id", metavar="CANDIDATE_ID", help="record a pass for this candidate")
    p.add_argument("--entry-rule", choices=["close", "g88"], default=None,
                    help="Order type for --id (default: $PAPER_ENTRY_RULE, "
                         "else 'g88'). Ignored by --pass -- a pass never "
                         "places an order. See the module docstring.")
    args = p.parse_args()

    candidate_id = args.id or args.pass_id
    if _already_booked(candidate_id):
        # Exit 2 == "already handled, do not retry". Exit 1 == "failed, a
        # human/retry may still be wanted". The stage-manager must be able to
        # tell an idempotent refusal from a broker hiccup that dropped a card.
        print(f"REFUSED: {candidate_id} is already booked (entry or pass already logged).")
        return 2

    if args.pass_id:
        rec = record_pass(args.pass_id, arm=args.arm)
        print(f"PASS logged: {rec}")
        return 0

    try:
        rec = book_order(args.id, arm=args.arm, entry_rule=args.entry_rule)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: {e}")
        return 1
    print(f"BOOKED: {rec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
