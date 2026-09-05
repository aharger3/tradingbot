"""Live-path stop selftest for paper_trader.py (G11's wick bug).

CLAUDE.md, "Rules that hold everywhere" (updated 2026-09-03 -- max loss is
-1R hard, no -1.25R clamp; the level stop triggers on CLOSE and the disaster
stop rests at exactly 1R and fills on an intrabar TOUCH):

    Stops trigger on the candle CLOSE, fill at that close, floored at -1.000R.
    Wicks stop nothing out on the LEVEL stop; the disaster stop is the one
    order that reacts to a touch, and it sits exactly on the level stop here.

`backtest_week.py` has obeyed that since omen-5.0 T4(a) (`STOP_ON_CLOSE`).
`paper_trader.py` did not: `PaperPosition._check_stop` tested the bar's WICK
(`low <= stock_stop` / `high >= stock_stop`) and had never been handed a close
at all, so every paper position since paper trading started was marked on the
wrong trigger -- always in the direction of cutting a trade the settled rule
would have let ride (research/g11_live_scratch_scope.md, section 3).

What this file pins, on synthetic bars, no market and no archive needed:

  1. a bar that wicks through the stop and closes back on the good side does
     NOT close the position -- calls and puts (this is the case that was red)
  2. a bar that CLOSES beyond the stop does close it, at the stop premium
  3. the target is still a resting limit order: an intrabar TOUCH fills it,
     exactly as backtest_week does it. Only the stop moved to the close.
  4. Rule 6's runner stop is close-based too, and its break-even scale-out is
     still a touch (backtest_week.py:593-602 draws the same line)
  5. a stop-out never books worse than -1.000R (DISASTER_STOP_R)

  6. the live path calls the SHARED predicate in `stop_rule.py`, not a private
     second copy of the rule -- the copy is how the divergence happened

Run:

    python research/test_paper_trader_stop.py
"""

from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import paper_trader                                          # noqa: E402
import stop_rule                                             # noqa: E402
from options_sizer import OptionsPlan                         # noqa: E402
from paper_trader import PaperBook                            # noqa: E402

import stop_rule                                              # noqa: E402

# Austin, 2026-09-03: -1R hard, no -1.25R clamp. `stop_rule.MAX_LOSS_R` (1.25)
# only survives for `research/exit_lab.py`, a lab module with no disaster
# stop; the live path (`paper_trader._stop_fill_premium`) passes
# `DISASTER_STOP_R` as the floor, not `MAX_LOSS_R` -- this test must match
# that call, not the old constant, or every "close mapped through delta"
# expectation below is computed against the wrong floor.
MAX_LOSS_R = stop_rule.DISASTER_STOP_R  # 1.0, matches paper_trader's real floor
EPS = 1e-9

# A call: entry 440.00, stop 439.30 (risk 0.70), target 441.40.
CALL_PLAN = OptionsPlan(
    symbol="TSLA", direction="call", expiration="2026-06-10", strike=440.0,
    entry_premium=2.00, stop_premium=1.65, target_premium=2.70, contracts=5,
    max_loss=175.0, max_reward=350.0,
    stock_entry=440.0, stock_stop=439.3, stock_target=441.4,
    quote_source="estimated_delta", occ_symbol="TSLA260610C00440000",
)

# A put: entry 850.00, stop 852.50 (risk 2.50), target 845.00.
PUT_PLAN = OptionsPlan(
    symbol="NVDA", direction="put", expiration="2026-06-10", strike=850.0,
    entry_premium=3.00, stop_premium=2.50, target_premium=4.00, contracts=4,
    max_loss=200.0, max_reward=400.0,
    stock_entry=850.0, stock_stop=852.5, stock_target=845.0,
    quote_source="estimated_delta", occ_symbol="NVDA260610P00850000",
)


def _book():
    return PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "paper-trades.jsonl")


def _mark(plan, high, low, close):
    """Open one position from `plan`, mark it against one bar, return events."""
    book = _book()
    book.open_from_plan(plan, ts="09:35:00")
    return book, book.mark(plan.symbol, high=high, low=low, close=close,
                           ts="09:36:00")


# name -> (plan, high, low, close, expected outcome or None for "still open")
CASES = [
    # 1. the wick bug. Low/high is well through the stop, the close never is.
    ("call: wick through the stop, closes above it",
     CALL_PLAN, 440.60, 438.90, 440.10, None),
    ("put: wick through the stop, closes below it",
     PUT_PLAN, 853.40, 849.50, 850.20, None),
    # the hairline: the wick is exactly ON the stop, the close is not
    ("call: wick sits exactly on the stop",
     CALL_PLAN, 440.50, 439.30, 440.00, None),
    ("put: wick sits exactly on the stop",
     PUT_PLAN, 852.50, 849.80, 850.00, None),

    # 2. a close beyond the stop is a stop-out
    ("call: closes below the stop",
     CALL_PLAN, 440.20, 439.00, 439.10, "stop"),
    ("put: closes above the stop",
     PUT_PLAN, 853.00, 849.90, 852.90, "stop"),
    ("call: closes exactly on the stop",
     CALL_PLAN, 440.20, 439.00, 439.30, "stop"),
    ("put: closes exactly on the stop",
     PUT_PLAN, 853.00, 849.90, 852.50, "stop"),

    # 3. the target is a resting limit: an intrabar touch still fills it, even
    #    on a bar that closes back below the level.
    ("call: target touched on the wick only",
     CALL_PLAN, 441.50, 440.10, 440.30, "target"),
    ("put: target touched on the wick only",
     PUT_PLAN, 850.20, 844.90, 849.80, "target"),

    # the same-bar straddle: wick through the stop AND through the target, and
    # the close is beyond the stop -> the stop wins (paper_trader has always
    # taken the conservative arm; backtest_week's PESSIMISTIC_FILL agrees).
    ("call: bar straddles both, closes below the stop",
     CALL_PLAN, 441.50, 439.00, 439.20, "stop"),
    ("put: bar straddles both, closes above the stop",
     PUT_PLAN, 853.00, 844.90, 852.80, "stop"),

    # a quiet bar touches nothing
    ("call: quiet bar", CALL_PLAN, 440.80, 440.10, 440.40, None),
    ("put: quiet bar", PUT_PLAN, 850.60, 849.20, 849.90, None),
]


def check_cases(failures, rows):
    for name, plan, high, low, close, want in CASES:
        book, evs = _mark(plan, high, low, close)
        got = evs[0]["outcome"] if evs else None
        rows.append((name, got or "open"))
        if got != want:
            failures.append(
                f"  {name}: outcome {got or 'open'!r}, expected "
                f"{want or 'open'!r} (bar h={high} l={low} c={close}, "
                f"stop={plan.stock_stop})")
            continue
        if got == "stop":
            # 5. the -1.000R floor (DISASTER_STOP_R). T11 (2026-08-28) introduced
            #    the close-mapped fill; the 2026-09-03 ruling then dropped the
            #    floor `paper_trader._stop_fill_premium` passes from MAX_LOSS_R
            #    (1.25, exit_lab-only) to DISASTER_STOP_R (1.0). The fill is the
            #    triggering CLOSE mapped through the plan's own delta, floored
            #    at -1.000R --
            #    it is no longer the plan's precomputed stop_premium, which was
            #    exactly -1.000R however far the bar had already run past the
            #    level. So the floor now BINDS on the premium side; assert both
            #    that it holds and that the fill is the close, not the level.
            pnl = evs[0]["pnl"]
            if pnl < -MAX_LOSS_R * plan.max_loss - EPS:
                failures.append(
                    f"  {name}: booked ${pnl:.2f} on a 1R of ${plan.max_loss:.2f} "
                    f"= {pnl / plan.max_loss:+.2f}R, floor is -{MAX_LOSS_R:.2f}R")
            long = plan.direction == "call"
            srisk = abs(plan.stock_entry - plan.stock_stop)
            prem_risk = plan.entry_premium - plan.stop_premium
            fill_stock = stop_rule.stop_fill_price(
                close, plan.stock_entry, srisk, long, MAX_LOSS_R)
            moved = ((plan.stock_entry - fill_stock) if long
                     else (fill_stock - plan.stock_entry))
            want_prem = max(plan.entry_premium - moved / srisk * prem_risk, 0.05)
            if abs(evs[0]["exit_premium"] - want_prem) > 1e-6:
                failures.append(
                    f"  {name}: filled at {evs[0]['exit_premium']}, expected "
                    f"{want_prem:.4f} -- the close ({close}) mapped through the "
                    f"plan's delta and floored at -{MAX_LOSS_R:.2f}R")
            if evs[0]["exit_premium"] > plan.stop_premium + 1e-9:
                failures.append(
                    f"  {name}: filled at {evs[0]['exit_premium']}, BETTER than "
                    f"the stop premium {plan.stop_premium} on a bar that closed "
                    f"beyond the stop -- the close fill can only be worse")
        if not evs and book.open_positions == []:
            failures.append(f"  {name}: position vanished without an event")


def check_rule6_runner(failures, rows):
    """Rule 6 is off by default; its runner stop must still be close-based.

    backtest_week.py:593-602 is the reference: the break-even SCALE fires on a
    touch (it is a limit order, like the target), the runner's raised stop then
    fires on the CLOSE via the same `_stop_hit`.
    """
    orig = paper_trader.RULE6_ENABLED
    paper_trader.RULE6_ENABLED = True
    try:
        # break-even for the call sits at entry + 1R = 440.00 + 0.70 = 440.70
        book = _book()
        book.open_from_plan(CALL_PLAN, ts="09:35:00")
        pos = book.open_positions[0]
        if abs(pos.be_scale_level - 440.70) > 0.01:
            failures.append(
                f"  rule6: break-even level {pos.be_scale_level}, expected 440.70")
            return
        # the scale is a touch: this bar only wicks up to it
        evs = book.mark("TSLA", high=440.75, low=440.20, close=440.30, ts="09:40:00")
        rows.append(("rule6: BE scale fills on a touch",
                     evs[0]["outcome"] if evs else "open"))
        if not evs or evs[0]["outcome"] != "be_scale":
            failures.append(
                "  rule6: break-even scale did not fire on an intrabar touch "
                f"(got {[e['outcome'] for e in evs]})")
            return
        # runner stop is now entry (440.00). A wick through it is not an exit.
        evs = book.mark("TSLA", high=440.60, low=439.50, close=440.20, ts="09:41:00")
        rows.append(("rule6: runner wick through break-even",
                     evs[0]["outcome"] if evs else "open"))
        if evs:
            failures.append(
                f"  rule6: runner closed {evs[0]['outcome']!r} on a bar that only "
                "WICKED through the break-even stop")
        # ...but a close through it is.
        evs = book.mark("TSLA", high=440.30, low=439.50, close=439.60, ts="09:42:00")
        rows.append(("rule6: runner closes through break-even",
                     evs[0]["outcome"] if evs else "open"))
        if not evs or evs[0]["outcome"] != "stop":
            failures.append(
                "  rule6: runner survived a bar that CLOSED through the "
                f"break-even stop (got {[e['outcome'] for e in evs]})")
    finally:
        paper_trader.RULE6_ENABLED = orig


def check_single_source(failures, rows):
    """6. One rule, one function. Two copies is how this bug happened."""
    shared = getattr(paper_trader, "stop_hit_on_close", None)
    ok = shared is stop_rule.stop_hit_on_close
    rows.append(("live path uses stop_rule.stop_hit_on_close", "yes" if ok else "NO"))
    if not ok:
        failures.append(
            "  paper_trader does not use stop_rule.stop_hit_on_close -- the "
            "live path is keeping its own copy of the stop rule again")


def main():
    failures = []
    rows = []
    check_cases(failures, rows)
    check_rule6_runner(failures, rows)
    check_single_source(failures, rows)

    width = max(len(n) for n, _ in rows)
    for name, got in rows:
        print(f"{name:<{width}}  {got}")

    if failures:
        print()
        print(f"PAPER-TRADER STOP SELFTEST FAILED: {len(failures)} problem(s).")
        print("\n".join(failures))
        sys.exit(1)

    print()
    print(f"paper-trader stop selftest ok: {len(rows)} checks, wicks stop "
          f"nothing out, targets still fill on a touch, losses floored at "
          f"-{MAX_LOSS_R:.2f}R")


if __name__ == "__main__":
    main()
