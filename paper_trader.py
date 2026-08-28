"""Paper-trading simulation for Omen signals.

No real orders. When --paper is set on live_scanner, every fired signal opens a
simulated options position here. Each scan marks open positions against the
latest candle and closes them at the stock-side stop or 2R target, logging
realized P&L to journal/paper-trades.jsonl.

Exit pricing uses the plan's precomputed target_premium and, for a stop, the
triggering close mapped through the plan's own delta (`_stop_fill_premium`,
floored at -1.25R via `stop_rule.stop_fill_price`) — so the sim needs no live
option quotes. Until T11 (2026-08-28) a stop booked the plan's `stop_premium`,
i.e. exactly -1.000R however far the bar had already run past the level.

Rule 6 (Austin 2026-07-10): if RULE6_ENABLED, scale 50% at breakeven (1R) and
move the runner's stop to entry. The runner continues to the original 2R target.

Stops trigger on the candle CLOSE (`stop_rule.stop_hit_on_close`, the same
predicate backtest_week.py's STOP_ON_CLOSE path uses). Until G11 this module
tested the bar's WICK and was never handed a close at all, so it had been
mismarking every paper position since paper trading started — see stop_rule.py.
Targets and the Rule 6 break-even scale are limit orders and still fill on an
intrabar TOUCH; only the stop moved.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from options_sizer import OptionsPlan
from stop_rule import stop_hit_on_close, stop_fill_price


# ---- Rule 6: Position Management ----
RULE6_ENABLED = False       # toggle for live paper trading
RULE6_SCALE_PCT = 0.5       # scale out 50% at breakeven
RULE6_BE_MULT = 1.0         # breakeven at 1R (entry +/- 1R risk)


def _now_et_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")


def _calc_breakeven(
    direction: str,
    entry: float,
    stop: float,
    target: float,
) -> float:
    """Stock-side breakeven scale level: entry + 1R * direction."""
    risk = abs(entry - stop)
    if risk == 0:
        return entry
    if direction == "call":
        return entry + RULE6_BE_MULT * risk
    else:
        return entry - RULE6_BE_MULT * risk


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
    grade: str = "?"
    setup: str = "?"
    # Rule 6: breakeven scaling
    be_scale_level: float = 0.0   # stock price where 50% is scaled out
    be_exit_price: float = 0.0    # actual exit price when BE was hit
    runner_stop: float = 0.0      # stop for the runner after BE taken (raised to entry)
    be_taken: bool = False        # whether breakeven scale already fired

    def _stop_fill_premium(self, close: float) -> float:
        """T11. The premium a close-triggered stop books, floored at -1.25R.

        The bar closed beyond the stop, so the position is out at market on that
        close — not at the plan's precomputed `stop_premium`, which is exactly
        -1.000R by construction and is what made the -1.25R floor unreachable in
        every rig (research/x2_stop_floor_audit.md; on the archived tape 96.6% of
        stop-outs were triggered by a bar that had already closed past 1R).

        The stock-side fill comes from the ONE shared clamp,
        `stop_rule.stop_fill_price`, anchored on the ORIGINAL entry and the
        ORIGINAL `abs(stock_entry - stock_stop)` — so a runner whose stop was
        raised to break-even still floors at -1.25R of the whole trade, not of
        some re-based fraction.

        That stock price becomes a premium through the plan's OWN delta map: the
        plan already priced `stock_stop` at `stop_premium`, so
        `premium_risk / stock_risk` is the delta it was built with and reusing it
        keeps the sim consistent with the sizer instead of inventing a second
        one. Linear, which is what `options_sizer` assumes; there is no options
        tape in this repo to do better. Clamped at $0.05 for the same reason
        `options_sizer.py:227` clamps `stop_premium` there — a long option's loss
        is bounded by its premium, so this can only ever make a fill less bad.
        """
        srisk = abs(self.stock_entry - self.stock_stop)
        prem_risk = self.entry_premium - self.stop_premium
        if srisk <= 0 or prem_risk <= 0:
            return self.stop_premium
        long = self.direction == "call"
        fill = stop_fill_price(close, self.stock_entry, srisk, long)
        moved = (self.stock_entry - fill) if long else (fill - self.stock_entry)
        return max(self.entry_premium - moved / srisk * prem_risk, 0.05)

    def _check_stop(self, close: float) -> Optional[tuple]:
        """Check if stop was hit. Returns (exit_premium, outcome) or None.

        The CLOSE is the trigger — a wick through the level stops nothing out —
        and since T11 it is the FILL as well, via `_stop_fill_premium` above.
        """
        if stop_hit_on_close(close, self.stock_stop, self.direction == "call"):
            return self._stop_fill_premium(close), "stop"
        return None

    def _check_target(self, high: float, low: float) -> Optional[tuple]:
        """Check if target was hit. Returns (exit_premium, outcome) or None.

        Wick-based on purpose: a target is a resting limit order and fills on any
        intrabar touch. backtest_week.py:606 does the same (`c.high >= t.target`).
        """
        if self.direction == "call":
            if high >= self.stock_target:
                return self.target_premium, "target"
        else:
            if low <= self.stock_target:
                return self.target_premium, "target"
        return None

    def _check_breakeven(self, high: float, low: float) -> Optional[float]:
        """Check if breakeven scale level was hit. Returns exit_price or None.

        Wick-based on purpose, same as the target: the Rule 6 scale is a limit
        order sitting at +1R, not a stop. backtest_week.py:593-595 triggers it on
        `c.high`/`c.low` too. Only the RUNNER's raised stop below is close-based.
        """
        if self.be_scale_level == 0.0 or self.be_taken:
            return None
        if self.direction == "call":
            if high >= self.be_scale_level:
                return self.be_scale_level
        else:
            if low <= self.be_scale_level:
                return self.be_scale_level
        return None

    def exit_for(self, high: float, low: float, close: float) -> Optional[tuple]:
        """Return (exit_premium, outcome) if this candle hits stop or target, else None.

        With Rule 6 enabled: BE scale checked before stop/target on same bar.
        Stop checked before target: if a single candle straddles both, assume the
        worst case (stop) — conservative, matches real fill risk on fast moves.
        """
        # If Rule 6 is disabled or BE already taken — use original binary logic
        if not RULE6_ENABLED:
            return self._check_stop(close) or self._check_target(high, low)

        # ---- Rule 6 path ----
        be_price = self._check_breakeven(high, low)

        if not self.be_taken and be_price is not None:
            # Position scales at breakeven on this candle — the two-stage
            # match is the caller's responsibility (PaperBook.mark handles it).
            # We return None here; the caller calls back in the same turn.
            self.be_taken = True
            self.be_exit_price = be_price
            self.runner_stop = self.stock_entry
            # Fake event: caller handles split via a separate BE event
            return (self.entry_premium, "be_scale")

        if self.be_taken:
            # Runner path: use runner_stop (raised to entry/breakeven). Still a
            # STOP, so still close-triggered — backtest_week.py:602 runs the
            # runner through the same `_stop_hit`.
            long = self.direction == "call"
            if stop_hit_on_close(close, self.runner_stop, long):
                # X2 found this returning `stop_premium` — a full 1R loss booked
                # on a stop resting at break-even, 0R away. T11 replaces X2's
                # `entry_premium` (right for a close exactly AT break-even, still
                # a resting-order fill for any close past it) with the one shared
                # convention: out at market on this close, floored at -1.25R of
                # the ORIGINAL risk. At close == stock_entry the two agree.
                return self._stop_fill_premium(close), "stop"
            if (high >= self.stock_target) if long else (low <= self.stock_target):
                return self.target_premium, "target"
            return None

        # Pre-BE path: original stop/target logic, but also check BE
        hit = self._check_stop(close)
        if hit:
            return hit
        hit = self._check_target(high, low)
        if hit:
            return hit
        return None

    def realized_pnl(self, exit_premium: float) -> float:
        return round((exit_premium - self.entry_premium) * 100 * self.contracts, 2)

    def scale_realized_pnl(self) -> float:
        """P&L from the BE-scaled portion (50% at breakeven price)."""
        if not self.be_taken or self.be_exit_price == 0.0:
            return 0.0
        scale_contracts = max(int(self.contracts * RULE6_SCALE_PCT), 1)
        # Stock-side breakeven → premium move proportional: use entry premium
        return 0.0  # breakeven scale = 0 P&L on that half

    def runner_realized_pnl(self, exit_premium: float) -> float:
        """P&L for the runner portion (remaining contracts after BE scale)."""
        if not self.be_taken:
            return self.realized_pnl(exit_premium)
        run_contracts = self.contracts - max(int(self.contracts * RULE6_SCALE_PCT), 1)
        if run_contracts <= 0:
            return 0.0
        return round((exit_premium - self.entry_premium) * 100 * run_contracts, 2)


class PaperBook:
    """Holds open paper positions and appends OPEN/CLOSE events to a JSONL ledger."""

    def __init__(self, ledger_path: Optional[Path] = None):
        self.ledger_path = ledger_path or (Path(__file__).parent / "journal" / "paper-trades.jsonl")
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.open_positions: List[PaperPosition] = []
        self.realized_total = 0.0

    def _log(self, event: dict) -> None:
        ts = event.get("ts", "")
        if len(ts) == 8 and ":" in ts:  # HH:MM:SS — no date
            today_et = (datetime.now(timezone.utc) - timedelta(hours=4)).strftime("%Y-%m-%d")
            event = {**event, "ts": f"{today_et} {ts}"}
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def open_from_plan(self, plan: OptionsPlan, ts: Optional[str] = None, grade: str = "?", setup: str = "?") -> PaperPosition:
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
            grade=grade, setup=setup,
        )
        if RULE6_ENABLED:
            pos.be_scale_level = _calc_breakeven(
                pos.direction, pos.stock_entry, pos.stock_stop, pos.stock_target)
        self.open_positions.append(pos)
        self._log({"event": "OPEN", "ts": pos.opened_at, **asdict(pos)})
        return pos

    def mark(self, symbol: str, high: float, low: float, close: float,
             ts: Optional[str] = None) -> List[dict]:
        """Mark open positions for `symbol` against one candle. Close any hit.

        `close` is required, not defaulted: the stop rule needs it, and a default
        would let a caller silently fall back to the wick trigger this exists to
        remove. Targets and the Rule 6 scale still read high/low.

        With Rule 6 enabled: BE scales are handled first (50% partial close at
        breakeven), then the runner is checked against the raised stop and original target.

        Returns list of close-event dicts (empty if none closed).
        """
        ts = ts or _now_et_iso()
        closed = []
        still_open = []
        for pos in self.open_positions:
            if pos.symbol != symbol.upper():
                still_open.append(pos)
                continue

            if RULE6_ENABLED and not pos.be_taken:
                # Check breakeven BEFORE stop/target
                be_price = pos._check_breakeven(high, low)
                if be_price is not None:
                    pos.be_taken = True
                    pos.be_exit_price = be_price
                    pos.runner_stop = pos.stock_entry
                    scale_ct = max(int(pos.contracts * RULE6_SCALE_PCT), 1)
                    run_ct = pos.contracts - scale_ct
                    # Scale event: log 50% close at breakeven
                    be_pnl = 0.0  # breakeven
                    self.realized_total = round(self.realized_total + be_pnl, 2)
                    ev = {
                        "event": "BE_SCALE", "ts": ts, "symbol": pos.symbol,
                        "direction": pos.direction, "strike": pos.strike,
                        "outcome": "be_scale", "be_exit": be_price,
                        "scale_contracts": scale_ct, "runner_contracts": run_ct,
                        "be_pnl": be_pnl, "opened_at": pos.opened_at,
                        "grade": pos.grade, "setup": pos.setup,
                    }
                    self._log(ev)
                    closed.append(ev)
                    if run_ct <= 0:
                        # All contracts scaled out
                        continue

            # Check stop/target (runner path if BE taken)
            hit = pos.exit_for(high, low, close)
            if hit is None:
                still_open.append(pos)
                continue
            exit_premium, outcome = hit

            if pos.be_taken:
                # Runner path: calculate P&L on remaining contracts only
                run_ct = pos.contracts - max(int(pos.contracts * RULE6_SCALE_PCT), 1)
                pnl = pos.runner_realized_pnl(exit_premium)
            else:
                run_ct = pos.contracts
                pnl = pos.realized_pnl(exit_premium)

            self.realized_total = round(self.realized_total + pnl, 2)
            ev = {
                "event": "CLOSE", "ts": ts, "symbol": pos.symbol,
                "direction": pos.direction, "strike": pos.strike,
                "outcome": outcome, "exit_premium": exit_premium,
                "entry_premium": pos.entry_premium,
                "contracts": run_ct, "total_contracts": pos.contracts,
                "pnl": pnl, "opened_at": pos.opened_at,
                "grade": pos.grade, "setup": pos.setup, "stock_entry": pos.stock_entry,
                "stock_target": pos.stock_target, "stock_stop": pos.stock_stop,
            }
            if pos.be_taken:
                ev["be_scaled"] = True
                ev["be_exit_price"] = pos.be_exit_price
            self._log(ev)
            closed.append(ev)
        self.open_positions = still_open
        return closed

    def summary(self) -> str:
        return (f"[PAPER] open={len(self.open_positions)}  "
                f"realized P&L=${self.realized_total:.2f}")


if __name__ == "__main__":
    # Self-test: open a call, walk it to BE scale then target. No market needed.
    # Stop cases are close-based (G11); research/test_paper_trader_stop.py is the
    # full grid, this is just the smoke test.
    # Note: this block runs as __main__, so RULE6_ENABLED is rebound directly.
    # `import paper_trader` here would make a SECOND module object and toggle a
    # flag nothing in this process reads (which is what it used to do).
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
    assert book.mark("TSLA", high=440.8, low=440.1, close=440.4, ts="09:36:00") == []
    # a WICK through the stop (439.3) that closes back above it is not a stop-out
    assert book.mark("TSLA", high=440.6, low=438.9, close=440.1, ts="09:37:00") == []
    assert len(book.open_positions) == 1
    # Rule 6 test when enabled
    orig = RULE6_ENABLED
    RULE6_ENABLED = True
    # Open a new position with Rule 6
    book2 = PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "pt2.jsonl")
    book2.open_from_plan(call_plan, ts="09:35:00")
    assert book2.open_positions[0].be_scale_level > 0
    # Candle hits breakeven (entry + 1R = 440.0 + 0.7 = 440.7 but stop=439.3, R=0.7, BE=440.7)
    evs = book2.mark("TSLA", high=441.0, low=440.3, close=440.8, ts="09:40:00")
    assert len(evs) == 1 and evs[0]["event"] == "BE_SCALE", evs
    # Next candle hits target
    evs = book2.mark("TSLA", high=441.5, low=440.5, close=441.2, ts="09:41:00")
    assert len(evs) == 1 and evs[0]["outcome"] == "target", evs
    RULE6_ENABLED = orig

    put_plan = OptionsPlan(
        symbol="NVDA", direction="put", expiration="2026-06-10", strike=850.0,
        entry_premium=3.00, stop_premium=2.50, target_premium=4.00, contracts=4,
        max_loss=200.0, max_reward=400.0,
        stock_entry=850.0, stock_stop=852.5, stock_target=845.0,
        quote_source="estimated_delta", occ_symbol="NVDA260610P00850000",
    )
    book.open_from_plan(put_plan, ts="10:00:00")
    # wick above the 852.5 stop, close back below it -> still open
    assert book.mark("NVDA", high=853.0, low=849.0, close=850.2, ts="10:05:00") == []
    # closes above the stop -> stopped out, filled at THAT CLOSE (T11), not at
    # the plan's stop premium. 852.90 is 2.90 above the 850.00 entry on a 2.50
    # stock risk = 1.16R, inside the -1.25R floor, so the premium is
    # 3.00 - 1.16*0.50 = 2.42 and the loss is -1.16R, not a flat -1.00R.
    closed = book.mark("NVDA", high=853.0, low=849.0, close=852.9, ts="10:06:00")
    assert len(closed) == 1 and closed[0]["outcome"] == "stop", closed
    assert abs(closed[0]["exit_premium"] - 2.42) < 1e-9, closed
    assert closed[0]["pnl"] == round((2.42 - 3.00) * 100 * 4, 2), closed
    # and the floor really is live on this path: a close 2R past the stop books
    # -1.25R, not -2R.
    book3 = PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "pt3.jsonl")
    book3.open_from_plan(put_plan, ts="10:00:00")
    far = book3.mark("NVDA", high=856.0, low=849.0, close=855.0, ts="10:06:00")
    assert len(far) == 1 and far[0]["outcome"] == "stop", far
    assert abs(far[0]["pnl"] / put_plan.max_loss + 1.25) < 1e-9, far

    print("paper_trader self-test passed")
    print(book.summary())
    os.remove(tmp)
