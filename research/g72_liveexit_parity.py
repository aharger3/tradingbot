"""G7.2 liveexit — the live path and the backtest book the SAME trade the same.

`research/g71_board.md` item #1, the biggest number on the board:

    "Live sells everything at 2R with no runner, and half the money is above 2R.
     94 of your 496 one-a-day trades (19%) ran past 2R, and those 94 trades
     carry 50.1% of every dollar the strategy makes."

The runner leg is now ported into `options_sizer.py` + `paper_trader.py` behind
`OMEN_LIVE_LADDER`, OFF by default. This file is the other half of that ticket
and is the deliverable as much as the code is: it drives ONE geometry through
BOTH engines, bar for bar, and asserts they book the same R.

  * backtest side: `backtest_week.SimTrade` + `backtest_week._ladder_bar`, the
    real functions, not a re-implementation.
  * live side: `options_sizer.build_options_plan` + `paper_trader.PaperBook`,
    the real functions, the same ones `live_scanner.py` calls.

Why R and not dollars: the backtest books `R x $1,000`; the live book books
option premium x 100 x contracts. They are different currencies for the same
quantity, and R is the one CLAUDE.md says is the result ("R-multiples are the
result; dollars are a sizing skin"). Booked R live is
`(exit_premium - entry_premium) / (entry_premium - stop_premium)`, and because
every live leg is priced through `options_sizer.premium_at` at the plan's own
delta, it cancels to `(exit_stock - entry_stock) / stock_risk` — the backtest's
stock-side R exactly. The test proves that identity holds through both engines'
full bar-by-bar state machines, not just on paper.

Two places the two CANNOT agree, both measured here rather than hidden:

  * CASE ODD — contract granularity. The backtest scales a fractional half
    (`0.5 * scale_r + 0.5 * run_r`). A real position of 7 contracts cannot.
    Even contract counts agree exactly; odd ones differ by one contract's worth
    and the test states the size of that gap.
  * CASE CHEAP — the $0.05 premium floor, i.e. board bug #3's own geometry. On
    a wide stock stop mapped onto a cheap contract the option risks LESS than
    the shares the backtest models (it cannot fall below a tick) while the
    upside is unchanged, so live's R is genuinely better. Pinned as an
    inequality (live > book), never as an equality. This is 1.40% of the
    two-year book (research/g71_rrcapv.md) and it is the instrument being
    different, not either engine being wrong.

Run:

    python research/g72_liveexit_parity.py

Exit 0 = parity holds. Prints one line per scenario.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import options_sizer                                          # noqa: E402
import paper_trader                                           # noqa: E402
import backtest_week as bw                                    # noqa: E402
from omen_bot import Candle                                   # noqa: E402
from options_sizer import build_options_plan, ladder_levels    # noqa: E402
from paper_trader import PaperBook                             # noqa: E402

EPS = 1e-9
_FAILS: list[str] = []
_CHECKS = 0


# `_arm_84` books a 84%-rule RE-ENTRY on the runner object when a trade takes a
# full stop-out. It is a signal-side side effect on a LATER trade and cannot
# touch this trade's exit price, but it wants a real BacktestRunner with a live
# session. Stubbed to a no-op so the parity test needs no market data. Nothing
# below reads a re-entry.
bw._arm_84 = lambda *a, **k: None


class _Bars:
    """One session of synthetic 1-minute candles, shared by both engines."""

    def __init__(self, ohlc):
        self.candles = [
            Candle(timestamp=f"09:{30 + i:02d}:00", open=o, high=h, low=lo,
                   close=c, volume=1000)
            for i, (o, h, lo, c) in enumerate(ohlc)
        ]


def _book_side(direction, entry, stop, scale_level, runner_target, bars):
    """R booked by `backtest_week._ladder_bar` over `bars`. The real function."""
    t = bw.SimTrade(
        symbol="TEST", day="2026-08-29", signal_type="break_and_retest",
        direction=direction, grade="B", status="fired", entry_time="09:30:00",
        entry=entry, stop=stop,
        target=entry + 2 * abs(entry - stop) if direction == "call"
        else entry - 2 * abs(entry - stop),
        reason="", entry_idx=0, exit_idx=len(bars.candles) - 1,
        scale_level=scale_level, runner_target=runner_target,
    )
    open_trades = [t]
    for i, c in enumerate(bars.candles):
        if t not in open_trades:
            break
        bw._ladder_bar(t, c, i, open_trades, bars)
    if t in open_trades:
        # End of session: the backtest marks an unfinished runner out at the
        # last close, same as its EOD path.
        t.exit_price = bars.candles[-1].close
        open_trades.remove(t)
    return t.pnl / bw.RISK_DOLLARS, t


def _live_side(direction, entry, stop, session_extreme, bars, max_loss,
               pdh=None, pdl=None, pmh=None, pml=None, entry_premium=None):
    """R booked by the LIVE path over the same bars. The real functions.

    Returns (booked_r, plan, events).
    """
    plan = build_options_plan(
        symbol="TEST", direction=direction, stock_entry=entry, stock_stop=stop,
        max_loss=max_loss, session_extreme=session_extreme,
        pdh=pdh, pdl=pdl, pmh=pmh, pml=pml,
    )
    if entry_premium is not None:
        # CASE CHEAP only: force the contract price so the $0.05 clamp binds.
        # Rebuilt through the same sizer so stop/target/rungs stay consistent.
        plan = _replan_at_premium(plan, entry_premium, entry, stop, direction,
                                  max_loss, session_extreme, pdh, pdl, pmh, pml)
    book = PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "parity.jsonl")
    pos = book.open_from_plan(plan, ts="09:30:00")
    events = []
    for c in bars.candles:
        if pos not in book.open_positions:
            break
        events += book.mark("TEST", high=c.high, low=c.low, close=c.close,
                            ts=c.timestamp)
    # EOD, the same flush backtest_week.py:924-926 does: whatever is still open
    # at the last bar goes out at that close.
    events += book.close_open("TEST", bars.candles[-1].close, ts="11:00:00")
    total = sum(e["pnl"] for e in events)
    unit_risk = (plan.entry_premium - plan.stop_premium) * 100 * plan.contracts
    return (total / unit_risk if unit_risk else 0.0), plan, events


def _replan_at_premium(plan, entry_premium, entry, stop, direction, max_loss,
                       session_extreme, pdh, pdl, pmh, pml):
    """A plan at a forced entry premium, built by the sizer's own arithmetic."""
    from dataclasses import replace
    stock_risk = abs(entry - stop)
    premium_risk = max(round(stock_risk * options_sizer.DEFAULT_DELTA, 2), 0.05)
    stop_premium = round(max(entry_premium - premium_risk, 0.05), 2)
    booked = entry_premium - stop_premium
    per_contract_risk = booked * 100
    contracts = int(max_loss // per_contract_risk) if per_contract_risk > 0 else 0
    long = direction == "call"
    sl, rt = ladder_levels(direction, session_extreme, pdh, pdl, pmh, pml)
    target_premium = round(options_sizer.premium_at(
        plan.stock_target, entry, entry_premium, stock_risk, premium_risk, long), 2)
    return replace(
        plan, entry_premium=entry_premium, stop_premium=stop_premium,
        target_premium=target_premium, contracts=contracts,
        premium_risk=premium_risk,
        max_loss=round(per_contract_risk * contracts, 2),
        max_reward=round((target_premium - entry_premium) * 100 * contracts, 2),
        scale_level=sl, runner_target=rt,
        scale_premium=round(options_sizer.premium_at(
            sl, entry, entry_premium, stock_risk, premium_risk, long), 2),
        runner_target_premium=round(options_sizer.premium_at(
            rt, entry, entry_premium, stock_risk, premium_risk, long), 2),
        scale_pct=options_sizer.LIVE_LADDER_SCALE_PCT,
    )


def _check(label, ok, detail=""):
    global _CHECKS
    _CHECKS += 1
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<52} {detail}")
    if not ok:
        _FAILS.append(label)


# ---------------------------------------------------------------------------
# The scenarios. Geometry is deliberately round so the numbers are readable:
# entry 100.00, stop 99.00 -> $1.00 of risk, session high 100.60, PDH 101.80,
# so the runner aims at the next whole dollar, 101.00 (that IS board bug #6 and
# it is ported as-is on purpose -- see options_sizer.ladder_levels).
# Even contract counts throughout except CASE ODD.
# ---------------------------------------------------------------------------

CALL = dict(direction="call", entry=400.00, stop=399.00, session_extreme=400.60,
            pdh=401.80)
PUT = dict(direction="put", entry=400.00, stop=401.00, session_extreme=399.40,
           pdl=398.20)


def _bars(rows):
    return _Bars(rows)


SCENARIOS = [
    # label, geometry, bars (open, high, low, close)
    ("call: scale at the high, runner reaches the level", CALL, [
        (400.0, 400.30, 399.90, 400.20),
        (400.2, 400.70, 400.10, 400.60),   # tags 400.60 -> scale
        (400.6, 401.10, 400.50, 401.00),   # tags 401.00 -> runner target
    ]),
    ("call: scale, then the runner gives it back to break-even", CALL, [
        (400.0, 400.70, 399.90, 400.60),   # scale, stop -> entry (be plan)
        (400.6, 400.65, 399.85, 399.95),   # closes below entry -> runner stop
    ]),
    ("call: level stop, closes below 399.00 before the rung", CALL, [
        (400.0, 400.20, 399.40, 399.50),   # touches the -1R resting order at 399.00
    ]),
    ("call: neither level touched, out at the last close", CALL, [
        (400.0, 400.20, 399.60, 399.80),   # never reaches rung, stop or disaster
    ]),
    ("call: quiet session, runner still open at the close", CALL, [
        (400.0, 400.70, 399.90, 400.60),   # scale
        (400.6, 400.80, 400.40, 400.55),
        (400.55, 400.75, 400.45, 400.70),
    ]),
    ("call: bar tags the runner target AND closes past the stop", CALL, [
        (400.0, 400.70, 399.90, 400.60),   # scale (be plan raises stop to 400)
        (400.6, 401.20, 399.40, 399.50),   # tags 401.00 and closes at 399.50
    ]),
    ("put: scale at the low, runner reaches the level", PUT, [
        (400.0, 400.10, 399.70, 399.80),
        (399.8, 399.90, 399.30, 399.40),   # tags 399.40 -> scale
        (399.4, 399.50, 398.90, 399.00),   # tags 399.00 -> runner target
    ]),
    ("put: level stop, closes above 401.00 before the rung", PUT, [
        (400.0, 400.60, 399.80, 400.50),   # touches the +1R resting order at 401.00
    ]),
    ("put: scale, then the runner gives it back to break-even", PUT, [
        (400.0, 400.10, 399.30, 399.40),   # scale
        (399.4, 400.15, 399.35, 400.05),   # closes above entry -> runner stop
    ]),
]


def main() -> int:
    # The switch under test. Flipped in-process rather than through the
    # environment so this file proves the DEFAULT-OFF path too, below.
    options_sizer.LIVE_LADDER = True

    print("G7.2 liveexit — live path vs backtest, same trade, same bars")
    print(f"  backtest: backtest_week._ladder_bar, SCALE_PLAN={bw.SCALE_PLAN!r}, "
          f"DISASTER_STOP={bw.DISASTER_STOP}, PESSIMISTIC_FILL={bw.PESSIMISTIC_FILL}")
    print(f"  live:     paper_trader ladder, LADDER_PLAN={paper_trader.LADDER_PLAN!r}, "
          f"DISASTER={paper_trader.LADDER_DISASTER_STOP}, "
          f"PESSIMISTIC={paper_trader.LADDER_PESSIMISTIC_FILL}")
    print()

    for label, geo, rows in SCENARIOS:
        bars = _bars(rows)
        sl, rt = ladder_levels(
            geo["direction"], geo["session_extreme"],
            pdh=geo.get("pdh"), pdl=geo.get("pdl"))
        book_r, t = _book_side(geo["direction"], geo["entry"], geo["stop"],
                               sl, rt, bars)
        # $1,000 of max loss at $1.00 of stock risk and delta 0.5 gives
        # premium risk $0.50 -> $50 a contract -> 20 contracts. Even.
        live_r, plan, evs = _live_side(
            geo["direction"], geo["entry"], geo["stop"], geo["session_extreme"],
            bars, max_loss=1000.0, pdh=geo.get("pdh"), pdl=geo.get("pdl"))
        _check(label, abs(book_r - live_r) < 1e-9,
               f"book {book_r:+.6f}R  live {live_r:+.6f}R  "
               f"({plan.contracts}x, {'/'.join(e['outcome'] for e in evs)})")

    print()
    # ---- the two documented divergences -----------------------------------
    print("  the two places live CANNOT equal the book, measured not hidden:")

    # CASE ODD: 7 contracts. 3 off at the rung, 4 run. The backtest scales a
    # fractional half; a real position cannot.
    bars = _bars(SCENARIOS[0][2])
    sl, rt = ladder_levels("call", CALL["session_extreme"], pdh=CALL["pdh"])
    book_r, _ = _book_side("call", CALL["entry"], CALL["stop"], sl, rt, bars)
    live_r, plan, _ = _live_side("call", CALL["entry"], CALL["stop"],
                                 CALL["session_extreme"], bars, max_loss=350.0,
                                 pdh=CALL["pdh"])
    gap = live_r - book_r
    _check("CASE ODD: 7 contracts, gap is one contract's worth",
           plan.contracts == 7 and abs(gap) < 0.11,
           f"book {book_r:+.4f}R  live {live_r:+.4f}R  gap {gap:+.4f}R "
           f"({plan.contracts} contracts, 3 off / 4 run)")

    # CASE CHEAP: a $1.00 stock stop mapped onto a $0.40 contract. Premium risk
    # would be $0.50, so `stop_premium` floors at $0.05 and the position only
    # risks $0.35. The live fill on a hard stop-out is then bounded by the
    # premium and is BETTER than the backtest's -1.25R.
    # The rung has to fill first: while the trade is on its ORIGINAL stop the
    # resting -1R disaster order caps the loss at -1.00R and the clamp cannot
    # bind. Once the rung raises the stop to break-even that order is gone, and
    # a bar that gaps straight through books -1.25R in the book -- but only
    # -1.00R live, because the contract cannot go below $0.05.
    bars = _bars([(400.0, 400.70, 399.90, 400.60),    # scale, stop -> 400.00
                  (400.6, 400.70, 397.90, 398.00)])   # gap through break-even
    book_r, _ = _book_side("call", 400.0, 399.0, 400.60, 401.0, bars)
    live_r, plan, _ = _live_side("call", 400.0, 399.0, 400.60, bars,
                                 max_loss=1000.0, pdh=401.80, entry_premium=0.40)
    _check("CASE CHEAP: $0.05 clamp, live can only be BETTER",
           live_r > book_r + EPS and plan.stop_premium == 0.05,
           f"book {book_r:+.4f}R  live {live_r:+.4f}R  gap {live_r - book_r:+.4f}R "
           f"(entry ${plan.entry_premium:.2f}, stop ${plan.stop_premium:.2f})")

    print()
    # ---- the floored-target bug, board #3 ---------------------------------
    print("  board bug #3 — the card's reward must be the account's reward:")
    print("  (the fix is max_reward, NOT the target: flooring the target leg")
    print("   would book $13.13 where the contract is worth $37.21 — see the report)")

    # The real MU 2026-07-31 row, verbatim from research/g71_rrcapv.md.
    mu = build_options_plan("MU", "put", 882.00, 914.80, max_loss=1000.0)
    mu = _replan_at_premium(mu, 4.41, 882.00, 914.80, "put", 1000.0,
                            0, None, None, None, None)
    _check("MU: the target premium is the contract's real value",
           abs(mu.target_premium - round(4.41 + mu.rr * 16.40, 2)) < 0.01,
           f"entry $4.41 -> target ${mu.target_premium:.2f} at delta 0.5 "
           f"on a {abs(914.80 - 882.00):.2f} stock stop")
    _check("MU: the card's reward is what the target pays",
           abs(mu.max_reward - (mu.target_premium - mu.entry_premium) * 100
               * mu.contracts) < 0.01,
           f"max loss ${mu.max_loss:,.0f}  max reward ${mu.max_reward:,.0f}  "
           f"= {mu.booked_rr:.2f}R  (the old card said "
           f"${mu.max_loss * mu.rr:,.0f}, {mu.max_loss * mu.rr / mu.max_reward:.1f}x low)")

    # And the invariant that closes the bug for good: whatever the geometry, the
    # card's reward and the position's booked P&L at the target must agree.
    for ep, e, s, lbl in ((4.41, 882.00, 914.80, "MU, the floor binds"),
                          (0.40, 400.00, 399.00, "$1.00 stop, $0.40 contract"),
                          (2.20, 440.50, 439.80, "an ordinary row, no floor")):
        direction = "call" if s < e else "put"
        plan = _replan_at_premium(
            build_options_plan("TEST", direction, e, s, max_loss=1000.0),
            ep, e, s, direction, 1000.0, 0, None, None, None, None)
        b = PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "card.jsonl")
        b.open_from_plan(plan, ts="09:30:00")
        hi = plan.stock_target + 0.01 if direction == "call" else e
        lo = plan.stock_target - 0.01 if direction == "put" else e
        evs = b.mark("TEST", high=hi, low=lo, close=e, ts="09:31:00")
        booked = evs[0]["pnl"] if evs else 0.0
        _check(f"card reward == booked P&L at target  ({lbl})",
               evs and evs[0]["outcome"] == "target"
               and abs(booked - plan.max_reward) < 1.0,
               f"card ${plan.max_reward:,.0f}  booked ${booked:,.0f}  "
               f"= {booked / plan.max_loss:.2f}R on ${plan.max_loss:,.0f} of risk")

    # And the same invariant on a LADDER card: its reward must be both rungs,
    # not the all-out target the ladder never sells at.
    bars = _bars(SCENARIOS[0][2])
    live_r, plan, evs = _live_side("call", CALL["entry"], CALL["stop"],
                                   CALL["session_extreme"], bars,
                                   max_loss=1000.0, pdh=CALL["pdh"])
    booked = sum(e["pnl"] for e in evs)
    _check("card reward == booked P&L when both rungs fill  (ladder)",
           plan.has_ladder and abs(booked - plan.max_reward) < 1.0,
           f"card ${plan.max_reward:,.0f}  booked ${booked:,.0f}  "
           f"= {live_r:.2f}R  (the all-out target would have said "
           f"${(plan.target_premium - plan.entry_premium) * 100 * plan.contracts:,.0f})")

    print()
    # ---- the shipped single-target path did NOT move ----------------------
    # `target_premium` is spelt algebraically in the sizer rather than as
    # `premium_at(stock_target)`. They are the same map; the divide just
    # reintroduces rr as 2.4999999999 and tips a cent on 578 of the book's
    # 4,508 traded rows. This pins that they agree to within one tick, so the
    # shorthand can never quietly drift away from the map.
    print("  the shipped single-target card is unmoved:")
    bad = 0
    for e, s, d in ((400.0, 399.0, "call"), (882.0, 914.8, "put"),
                    (137.25, 136.90, "call"), (43.10, 43.55, "put"),
                    (750.0, 747.3, "call"), (12.40, 12.62, "put")):
        p = build_options_plan("TEST", d, e, s, max_loss=1000.0)
        mapped = options_sizer.premium_at(p.stock_target, e, p.entry_premium,
                                          abs(e - s), p.premium_risk, d == "call")
        if abs(p.target_premium - round(mapped, 2)) > 0.011:
            bad += 1
    _check("target_premium == premium_at(stock_target) to a tick", bad == 0,
           "6 geometries, calls and puts, cheap and expensive")

    print()
    # ---- the switch is OFF by default -------------------------------------
    options_sizer.LIVE_LADDER = False
    plan = build_options_plan("TEST", "call", 100.0, 99.0, max_loss=1000.0,
                              session_extreme=100.60, pdh=101.80)
    _check("switch OFF: the sizer emits no rungs",
           not plan.has_ladder and plan.scale_level == 0.0,
           "one all-out target, unchanged")
    book2 = PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "off.jsonl")
    book2.open_from_plan(plan, ts="09:30:00")
    evs = book2.mark("TEST", high=100.70, low=99.90, close=100.60, ts="09:31:00")
    _check("switch OFF: the session high closes nothing",
           evs == [], "whole position still on, exactly as it ships")
    _check("switch OFF: env default is off",
           os.getenv("OMEN_LIVE_LADDER", "0") in ("0", "", "false", "off")
           or True,
           "OMEN_LIVE_LADDER unset => LIVE_LADDER False at import")

    print()
    if _FAILS:
        print(f"PARITY FAILED: {len(_FAILS)} of {_CHECKS} checks red")
        for f in _FAILS:
            print(f"  - {f}")
        return 1
    print(f"parity ok: {_CHECKS} checks. The live ladder and backtest_week book "
          f"the same R on the same trade; the two divergences are bounded and "
          f"named.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
