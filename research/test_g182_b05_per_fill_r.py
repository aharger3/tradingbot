"""B3 B-05 (ticket 19): stop_rule had no per-fill R-multiple helper, so bbcfd5cf's
"70 of 4,022 rows worse than -1.000R" (per-fill against original risk) could never
be reconciled against ece08845's "0 rows" (the blended trade-level `r` column) --
the two numbers measure different columns and only one of them existed in code.

Before this fix: `stop_rule.per_fill_r_multiple` does not exist -> AttributeError.
After: it returns the per-fill R-multiple against the trade's ORIGINAL risk,
independent of the blended `t.pnl / RISK_DOLLARS` column `backtest_week.py` writes.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stop_rule


def test_per_fill_r_multiple_exists_and_is_per_leg():
    # Long trade: entry 100, original risk 2 (stop at 98).
    entry, risk = 100.0, 2.0

    # A fill exactly at the level stop -> exactly -1.000R.
    assert math.isclose(stop_rule.per_fill_r_multiple(98.0, entry, risk, long=True), -1.0)

    # A fill worse than the level (close-triggered slippage) -> worse than -1R,
    # e.g. clamped by MAX_LOSS_R=1.25 at 95.5 -> -1.25R. This is the number
    # bbcfd5cf's "70 of 4,022" audit counted per fill.
    clamped = stop_rule.stop_fill_price(94.0, entry, risk, long=True)
    assert math.isclose(clamped, entry - stop_rule.MAX_LOSS_R * risk)  # 95.5
    assert math.isclose(
        stop_rule.per_fill_r_multiple(clamped, entry, risk, long=True), -1.25
    )

    # A short trade, symmetric.
    entry_s, risk_s = 50.0, 1.0
    assert math.isclose(
        stop_rule.per_fill_r_multiple(51.0, entry_s, risk_s, long=False), -1.0
    )

    # Zero-width risk has no ratio to compute -- matches stop_fill_price's own
    # risk<=0 short-circuit (returns the input unchanged rather than dividing).
    assert stop_rule.per_fill_r_multiple(999.0, entry, 0.0, long=True) == 0.0


def test_per_fill_column_is_independent_of_blended_column():
    """The blended `r` a book writes (sum of every fill's P&L / RISK_DOLLARS)
    can sit at -1.000R or better even when one leg, taken alone, breached it --
    this is exactly why the blended column cannot reconstruct bbcfd5cf's count.
    """
    entry, risk = 100.0, 2.0
    RISK_DOLLARS = 1000.0

    # Leg 1: a scale-out fills favorably, +0.5R = +$500.
    leg1_pnl = 0.5 * RISK_DOLLARS
    # Leg 2 (the stop leg): fills at -1.25R on its own original-risk basis.
    leg2_fill = stop_rule.stop_fill_price(94.0, entry, risk, long=True)  # 95.5
    leg2_r = stop_rule.per_fill_r_multiple(leg2_fill, entry, risk, long=True)
    assert math.isclose(leg2_r, -1.25)

    # Blended trade-level r, the column backtest_week.py writes as row["r"]:
    # nets leg1's dollar gain against leg2's dollar loss on the remaining size.
    leg2_pnl = leg2_r * (RISK_DOLLARS * 0.5)  # remaining half-size runner
    blended_r = round((leg1_pnl + leg2_pnl) / RISK_DOLLARS, 3)

    # The stop leg alone breached -1.000R (per_fill_r_multiple says -1.25), but
    # the blended trade-level number does not -- confirming the two columns
    # are genuinely different questions, not two measurements of one number.
    assert leg2_r < -1.0
    assert blended_r >= -1.0
