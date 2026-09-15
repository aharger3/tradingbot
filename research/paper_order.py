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
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from research.candidates_writer import candidates_path  # noqa: E402

_ALPACA_LEDGER = ROOT / "journal" / "alpaca-paper.jsonl"


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


def book_order(candidate_id: str, arm: str = "austin") -> dict:
    """Book a paper order for `candidate_id` on Alpaca's paper endpoint,
    sized to the candidate's own risk (1R = its max_loss, falling back to
    DEFAULT_MAX_LOSS -- same floor rule as live_scanner's fallback branch:
    `shares * |entry - stop| == 1R`, floored by `signal_runner.min_risk_floor`
    so a razor-thin stop can't blow the size up). Raises on failure; the
    caller (the stage-manager's shell-out) sees a nonzero exit."""
    cand = _find_candidate(candidate_id)
    if cand is None:
        raise RuntimeError(f"no candidate {candidate_id!r} in "
                            f"journal/candidates_{candidate_id.split('_')[1] if '_' in candidate_id else '?'}.json")

    from broker.alpaca import AlpacaBroker
    from broker.base import Order, OrderSide, OrderType
    from options_sizer import DEFAULT_MAX_LOSS
    from signal_runner import min_risk_floor

    broker = AlpacaBroker()
    _assert_paper_endpoint(broker)

    entry, stop = cand["entry"], cand["stop"]
    max_loss = cand.get("max_loss") or DEFAULT_MAX_LOSS
    risk_per_share = max(abs(entry - stop), min_risk_floor(entry))
    qty = int(max_loss / risk_per_share) if risk_per_share > 0 else 0
    if qty <= 0:
        rec = {"event": "entry_skip", "candidate_id": candidate_id, "arm": arm,
               "symbol": cand["symbol"], "reason": "zero-quantity after sizing"}
        _log(rec)
        return rec

    side = OrderSide.BUY if cand["direction"] == "call" else OrderSide.SELL
    idem = f"{cand['symbol']}-{candidate_id}-austin-entry"
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
              "error": str(e)[:200]})
        raise

    rec = {
        "event": "entry", "ts": cand["ts"], "symbol": cand["symbol"],
        "direction": cand["direction"], "order_symbol": order.symbol,
        "side": order.side.value, "quantity": order.quantity,
        "broker_order_id": handle.broker_order_id,
        "status": handle.status.value, "idempotency_key": idem,
        "arm": arm, "candidate_id": candidate_id, "max_loss": max_loss,
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
        rec = book_order(args.id, arm=args.arm)
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: {e}")
        return 1
    print(f"BOOKED: {rec}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
