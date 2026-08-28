"""X2 -- the -1.25R floor, every tranche, every rig.

`CLAUDE.md`, "Rules that hold everywhere":

    Stops trigger on the candle CLOSE, fill at that close, floored at -1.25R.
    Wicks stop nothing out.

Austin, 2026-08-28: *"still think some stops are going past 1r need to fix
that"*, and on the floor: *"it just stops losers from running past 1-1.25."*

Three properties, one file. Written red-first for X2; see
`research/x2_stop_floor_audit.md` for what each one caught.

1. **The break-even stop may not fill at the ORIGINAL stop's price.**
   `paper_trader.PaperPosition.exit_for` moves the runner's stop to the entry
   once Rule 6's break-even scale fires, and then returned `self.stop_premium`
   -- the premium at the ORIGINAL stock stop -- when that break-even stop
   triggered. The runner's stop was at break-even and the fill was booked a full
   1R below it. RED before the fix at `paper_trader.py:153`.

2. **No `exit_lab` policy may book worse than -1.25R, including on a gap.**
   `research/test_runner_stop.py` already covers the trail and the HOD bar; this
   adds the case those two do not have -- a single bar that closes 5R through
   the stop, i.e. the gap Austin is describing. GREEN today; it is a regression
   pin, not a bug report.

3. **`backtest_week`'s realised loss is capped at exactly -1.000R, and that is a
   FILL CONVENTION, not a measurement.** The shipped rig triggers on the close
   and then fills at `t.stop`, so the -1.25R floor is unreachable there and the
   book's left tail is a point mass. This is a CHARACTERIZATION test: it is
   green today and it exists so that changing the convention has to be
   deliberate. `research/x2_stop_floor_audit.py --tape` prices what the
   convention hides (474 booked stop-outs, 96.6% of which closed past 1R).

Run:

    python research/test_x2_stop_floor.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backtest_week as bw                                    # noqa: E402
import paper_trader                                           # noqa: E402
from options_sizer import OptionsPlan                         # noqa: E402
from paper_trader import PaperBook                            # noqa: E402
from research import exit_lab as xl                           # noqa: E402
import stop_rule                                             # noqa: E402

EPS = 1e-9

# Same plan `research/test_paper_trader_stop.py` uses, so the two files cannot
# drift apart on what a TSLA call costs.
# entry 440.00, stop 439.30 (risk 0.70 = 1R), target 441.40.
CALL_PLAN = OptionsPlan(
    symbol="TSLA", direction="call", expiration="2026-06-10", strike=440.0,
    entry_premium=2.00, stop_premium=1.65, target_premium=2.70, contracts=5,
    max_loss=175.0, max_reward=350.0,
    stock_entry=440.0, stock_stop=439.3, stock_target=441.4,
    quote_source="estimated_delta", occ_symbol="TSLA260610C00440000",
)

# entry 850.00, stop 852.50 (risk 2.50 = 1R), target 845.00.
PUT_PLAN = OptionsPlan(
    symbol="NVDA", direction="put", expiration="2026-06-10", strike=850.0,
    entry_premium=3.00, stop_premium=2.50, target_premium=4.00, contracts=4,
    max_loss=200.0, max_reward=400.0,
    stock_entry=850.0, stock_stop=852.5, stock_target=845.0,
    quote_source="estimated_delta", occ_symbol="NVDA260610P00850000",
)


def _book():
    return PaperBook(ledger_path=Path(tempfile.mkdtemp()) / "paper-trades.jsonl")


def _bar(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c, "v": 1000}


# ---------------------------------------------------------------------------
# 1. the break-even stop must not fill at the original stop's price
# ---------------------------------------------------------------------------

def check_be_stop_fill(failures, rows):
    """A stop that has been moved to break-even does not fill 1R below it.

    Rule 6 scales 50% out at +1R and raises the runner's stop to the entry
    price. Returning the plan's `stop_premium` when that raised stop triggered
    booked a full 1R loss on a stop that was never 1R away: the exact shape of
    Austin's complaint, in the live path rather than the backtest.

    X2 fixed it to `entry_premium`. **T11 (2026-08-28) superseded that**: the
    settled rule is out at market on the triggering CLOSE, floored at -1.25R of
    the ORIGINAL risk, so the runner books the close's own R -- between 0R and
    -1.25R -- not a flat 0R. `entry_premium` was still a resting-order fill; it
    was right only for a close landing exactly on break-even. This check now
    asserts the close fill and, unchanged, that it is never the ORIGINAL stop's
    premium, which is the bug X2 found.
    """
    orig = paper_trader.RULE6_ENABLED
    paper_trader.RULE6_ENABLED = True
    try:
        for name, plan, be_bar, stop_bar in (
            # call: BE scale at 440.00 + 0.70 = 440.70, runner stop -> 440.00
            ("call", CALL_PLAN,
             dict(high=440.75, low=440.20, close=440.30),
             dict(high=440.30, low=439.50, close=439.60)),
            # put: BE scale at 850.00 - 2.50 = 847.50, runner stop -> 850.00
            ("put", PUT_PLAN,
             dict(high=849.80, low=847.40, close=849.00),
             dict(high=851.00, low=849.00, close=850.60)),
        ):
            book = _book()
            book.open_from_plan(plan, ts="09:35:00")
            pos = book.open_positions[0]
            evs = book.mark(plan.symbol, ts="09:40:00", **be_bar)
            if not evs or evs[0]["outcome"] != "be_scale":
                failures.append(
                    "  be_stop_fill/%s: break-even scale did not fire (got %s)"
                    % (name, [e["outcome"] for e in evs]))
                continue
            evs = book.mark(plan.symbol, ts="09:41:00", **stop_bar)
            if not evs or evs[0]["outcome"] != "stop":
                failures.append(
                    "  be_stop_fill/%s: runner did not stop on a close through "
                    "break-even (got %s)" % (name, [e["outcome"] for e in evs]))
                continue
            got = evs[0]["exit_premium"]
            close = stop_bar["close"]
            long = plan.direction == "call"
            srisk = abs(plan.stock_entry - plan.stock_stop)
            prem_risk = plan.entry_premium - plan.stop_premium
            fill_stock = stop_rule.stop_fill_price(
                close, plan.stock_entry, srisk, long)
            moved = ((plan.stock_entry - fill_stock) if long
                     else (fill_stock - plan.stock_entry))
            want = max(plan.entry_premium - moved / srisk * prem_risk, 0.05)
            got_r = (got - plan.entry_premium) / prem_risk
            rows.append(("be stop fill (%s)" % name,
                         "%.4f = %+.4fR (entry %.2f, orig stop %.2f)"
                         % (got, got_r, plan.entry_premium, plan.stop_premium)))
            if abs(got - want) > EPS:
                failures.append(
                    "  be_stop_fill/%s: runner filled at %.4f, expected %.4f -- "
                    "the triggering close (stock %.2f) mapped through the plan's "
                    "own delta and floored at -%.2fR of the ORIGINAL risk "
                    "(paper_trader.PaperPosition._stop_fill_premium)."
                    % (name, got, want, close, xl.MAX_LOSS_R))
            # X2's finding, still asserted: the runner must never fill at the
            # ORIGINAL stop's premium when its stop had been raised to break-even.
            if abs(got - plan.stop_premium) <= EPS:
                failures.append(
                    "  be_stop_fill/%s: runner filled at the ORIGINAL stop's "
                    "premium %.2f on a stop resting at break-even (stock %.2f) "
                    "-- a full 1R loss on a 0R stop (paper_trader.py:153)."
                    % (name, plan.stop_premium, pos.stock_entry))
            # ...and the runner's loss is bounded by the floor, both sides.
            pnl = evs[0]["pnl"]
            rows.append(("be stop runner P&L (%s)" % name,
                         "%.2f (%+.4fR)" % (pnl, got_r)))
            if got_r < -xl.MAX_LOSS_R - EPS or got_r > EPS:
                failures.append(
                    "  be_stop_fill/%s: runner booked %+.4fR on a break-even "
                    "stop; it must sit in [-%.2fR, 0R]."
                    % (name, got_r, xl.MAX_LOSS_R))
    finally:
        paper_trader.RULE6_ENABLED = orig


# ---------------------------------------------------------------------------
# 2. a gap straight through the stop still floors at -1.25R
# ---------------------------------------------------------------------------

def _gap_day(side="L"):
    """20 quiet bars, entry at bar 10, then one bar that closes 5R past the stop.

    entry 100.00 / stop 99.00 (long) so 1R = 1.00. Bar 11 closes at 94.00,
    which is -6.00R unfloored. No policy may book worse than -1.25R.
    """
    bars = []
    for _ in range(11):
        bars.append(_bar(100.0, 100.2, 99.8, 100.0))
    if side == "L":
        bars.append(_bar(99.9, 99.95, 93.8, 94.00))   # 11: gap-down close
    else:
        bars.append(_bar(100.1, 106.2, 100.05, 106.00))
    for _ in range(20):
        bars.append(_bar(94.0, 94.2, 93.8, 94.0) if side == "L"
                    else _bar(106.0, 106.2, 105.8, 106.0))
    return bars


def check_gap_through_stop(failures, rows):
    policies = {
        "flat_2r": xl.flat_2r,
        "hod_only": xl.hod_only,
        "30_30_30_10": xl.policy_30_30_30_10,
        "50_20_20_10": xl.policy_50_20_20_10,
    }
    for side, entry, stop in (("L", 100.0, 99.0), ("S", 100.0, 101.0)):
        bars = _gap_day(side)
        for name, fn in policies.items():
            r = fn(bars, 10, entry, stop, side)
            rows.append(("gap through stop %s %s" % (side, name), "%+.4fR" % r))
            if r < -xl.MAX_LOSS_R - 1e-6:
                failures.append(
                    "  gap_through_stop/%s/%s booked %+.4fR, past the -%.2fR "
                    "floor" % (side, name, r, xl.MAX_LOSS_R))


# ---------------------------------------------------------------------------
# 3. characterization: backtest_week's loss is exactly -1.000R, by convention
# ---------------------------------------------------------------------------

def check_backtest_fill_convention(failures, rows):
    """A stop-out priced AT `t.stop` is exactly -1.000R -- the arithmetic only.

    This was the shipped convention until T11 (2026-08-28) and the reason the
    -1.25R floor was unreachable. `backtest_week` now fills at the triggering
    CLOSE via `_stop_fill_px`, so it no longer *produces* this row; what stays
    true, and is what this pins, is that `SimTrade.pnl` maps an exit AT the stop
    to exactly -1R, so any R past -1.000 in the book is genuine overshoot and
    not a denominator bug. The live assertion that the fill moved is
    `research/t11_stop_fill_fix.py`.
    """
    for direction, entry, stop, crater in (("call", 100.0, 99.0, 94.0),
                                           ("put", 100.0, 101.0, 106.0)):
        t = bw.SimTrade(
            symbol="TEST", day="2026-01-02", signal_type="break_and_retest",
            direction=direction, grade="B", status="fired", entry_time="09:40:00",
            entry=entry, stop=stop, target=entry + 2 * (entry - stop) * (
                1 if direction == "call" else 1),
        )
        # the engine's own assignment on a stop-out (backtest_week.py:416/611)
        t.outcome, t.exit_price = "loss", t.stop
        r = t.pnl / bw.RISK_DOLLARS
        rows.append(("backtest_week stop-out R (%s)" % direction, "%+.4fR" % r))
        if abs(r + 1.0) > 1e-9:
            failures.append(
                "  backtest_fill_convention/%s: booked %+.4fR, expected exactly "
                "-1.0000R" % (direction, r))
        # and the bar that actually triggered it closed at `crater`; that fill
        # is what the shipped rig declines to book.
        risk = abs(entry - stop)
        sgn = 1.0 if direction == "call" else -1.0
        close_r = sgn * (crater - entry) / risk
        rows.append(("  same bar, filled at its close", "%+.4fR" % close_r))
        if close_r > -1.0:
            failures.append(
                "  backtest_fill_convention/%s: the crater bar is not past 1R, "
                "the fixture is wrong" % direction)


# ---------------------------------------------------------------------------

CHECKS = (
    ("break-even stop fills at break-even", check_be_stop_fill),
    ("a gap through the stop floors at -1.25R", check_gap_through_stop),
    ("backtest_week's stop fill convention", check_backtest_fill_convention),
)


def main():
    failures, rows = [], []
    for label, fn in CHECKS:
        rows.append(("-- %s" % label, ""))
        fn(failures, rows)
    width = max(len(a) for a, _ in rows)
    for a, b in rows:
        print("%-*s  %s" % (width, a, b))
    print()
    if failures:
        print("X2 stop-floor selftest FAILED (%d):" % len(failures))
        for f in failures:
            print(f)
        return 1
    print("X2 stop-floor selftest ok: %d assertions, "
          "a break-even stop never fills at the ORIGINAL stop's premium, "
          "gaps floor at -1.25R, an exit AT t.stop is exactly -1.000R" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
