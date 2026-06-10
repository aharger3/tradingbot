"""Paper-trading simulation for Vanquish signals.

No real orders. When --paper is set on live_scanner, every fired signal opens a
simulated options position here. Each scan marks open positions against the
latest candle and closes them at the stock-side stop or 2R target, logging
realized P&L to journal/paper-trades.jsonl.

Exit pricing uses the plan's precomputed stop_premium / target_premium (which
already bake in the delta estimate), so the sim needs no live option quotes.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from options_sizer import OptionsPlan


def _now_et_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class PaperPosition:
    symbol: str
    direction: str          # "call" | "put"
    strike: float
    expiration: str
    contracts: int
    entry_premium: float
    stop_premium: float
    target_premium: float
    stock_entry: float
    stock_stop: float
    stock_target: float
    occ_symbol: str
    opened_at: str

    def exit_for(self, high: float, low: float) -> Optional[tuple]:
        """Return (exit_premium, outcome) if this candle hits stop or target, else None.

        Stop checked before target: if a single candle straddles both, assume the
        worst case (stop) — conservative, matches real fill risk on fast moves.
        """
        if self.direction == "call":
            if low <= self.stock_stop:
                return self.stop_premium, "stop"
            if high >= self.stock_target:
                return self.target_premium, "target"
        else:  # put
            if high >= self.stock_stop:
                return self.stop_premium, "stop"
            if low <= self.stock_target:
                return self.target_premium, "target"
        return None

    def realized_pnl(self, exit_premium: float) -> float:
        return round((exit_premium - self.entry_premium) * 100 * self.contracts, 2)


class PaperBook:
    """Holds open paper positions and appends OPEN/CLOSE events to a JSONL ledger."""

    def __init__(self, ledger_path: Optional[Path] = None):
        self.ledger_path = ledger_path or (Path(__file__).parent / "journal" / "paper-trades.jsonl")
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.open_positions: List[PaperPosition] = []
        self.realized_total = 0.0

    def _log(self, event: dict) -> None:
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def open_from_plan(self, plan: OptionsPlan, ts: Optional[str] = None) -> PaperPosition:
        pos = PaperPosition(
            symbol=plan.symbol,
            direction=plan.direction,
            strike=plan.strike,
            expiration=plan.expiration,
            contracts=plan.contracts,
            entry_premium=plan.entry_premium,
            stop_premium=plan.stop_premium,
            target_premium=plan.target_premium,
            stock_entry=plan.stock_entry,
            stock_stop=plan.stock_stop,
            stock_target=plan.stock_target,
            occ_symbol=plan.occ_symbol,
            opened_at=ts or _now_et_iso(),
        )
        self.open_positions.append(pos)
        self._log({"event": "OPEN", "ts": pos.opened_at, **asdict(pos)})
        return pos

    def mark(self, symbol: str, high: float, low: float, ts: Optional[str] = None) -> List[dict]:
        """Mark open positions for `symbol` against a candle's high/low. Close any hit.

        Returns list of close-event dicts (empty if none closed).
        """
        ts = ts or _now_et_iso()
        closed = []
        still_open = []
        for pos in self.open_positions:
            if pos.symbol != symbol.upper():
                still_open.append(pos)
                continue
            hit = pos.exit_for(high, low)
            if hit is None:
                still_open.append(pos)
                continue
            exit_premium, outcome = hit
            pnl = pos.realized_pnl(exit_premium)
            self.realized_total = round(self.realized_total + pnl, 2)
            ev = {
                "event": "CLOSE", "ts": ts, "symbol": pos.symbol,
                "direction": pos.direction, "strike": pos.strike,
                "outcome": outcome, "exit_premium": exit_premium,
                "entry_premium": pos.entry_premium, "contracts": pos.contracts,
                "pnl": pnl, "opened_at": pos.opened_at,
            }
            self._log(ev)
            closed.append(ev)
        self.open_positions = still_open
        return closed

    def summary(self) -> str:
        return (f"[PAPER] open={len(self.open_positions)}  "
                f"realized P&L=${self.realized_total:.2f}")


if __name__ == "__main__":
    # Self-test: open a call, walk it to target, then a put to stop. No market needed.
    import tempfile, os
    tmp = Path(tempfile.mkdtemp()) / "paper-trades.jsonl"
    book = PaperBook(ledger_path=tmp)

    call_plan = OptionsPlan(
        symbol="TSLA", direction="call", expiration="2026-06-10", strike=440.0,
        entry_premium=2.00, stop_premium=1.65, target_premium=2.70, contracts=5,
        max_loss=175.0, max_reward=350.0,
        stock_entry=440.0, stock_stop=439.3, stock_target=441.4,
        quote_source="estimated_delta", occ_symbol="TSLA260610C00440000",
    )
    book.open_from_plan(call_plan, ts="09:35:00")
    assert len(book.open_positions) == 1
    # candle that doesn't hit either level
    assert book.mark("TSLA", high=440.8, low=440.1, ts="09:36:00") == []
    # candle that hits target
    closed = book.mark("TSLA", high=441.5, low=440.5, ts="09:40:00")
    assert len(closed) == 1 and closed[0]["outcome"] == "target", closed
    assert closed[0]["pnl"] == round((2.70 - 2.00) * 100 * 5, 2), closed

    put_plan = OptionsPlan(
        symbol="NVDA", direction="put", expiration="2026-06-10", strike=850.0,
        entry_premium=3.00, stop_premium=2.50, target_premium=4.00, contracts=4,
        max_loss=200.0, max_reward=400.0,
        stock_entry=850.0, stock_stop=852.5, stock_target=845.0,
        quote_source="estimated_delta", occ_symbol="NVDA260610P00850000",
    )
    book.open_from_plan(put_plan, ts="10:00:00")
    closed = book.mark("NVDA", high=853.0, low=849.0, ts="10:05:00")
    assert len(closed) == 1 and closed[0]["outcome"] == "stop", closed
    assert closed[0]["pnl"] == round((2.50 - 3.00) * 100 * 4, 2), closed

    print("paper_trader self-test passed")
    print(book.summary())
    os.remove(tmp)
