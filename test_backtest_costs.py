"""Self-check for backtest_week's trading-cost model. Run: python test_backtest_costs.py"""
import backtest_week as bw
from backtest_week import SimTrade, RISK_DOLLARS


def T(entry, stop, exit_price, direction="call"):
    return SimTrade(
        symbol="MNQ", day="2026-09-27", signal_type="break_retest",
        direction=direction, grade="A", status="fired", entry_time="09:40:00",
        entry=entry, stop=stop, target=exit_price, outcome="win",
        exit_price=exit_price,
    )


# A clean 1R winner (gross, before costs) nets LESS than 1R once commission +
# slippage are charged -- the whole point of trading_cost_usd().
t = T(entry=100.0, stop=99.0, exit_price=101.0)
gross_r = t._pnl_gross / RISK_DOLLARS
net_r = t.pnl / RISK_DOLLARS
assert abs(gross_r - 1.0) < 1e-9, f"gross should be exactly 1R, got {gross_r}"
assert net_r < 1.0, f"a 1R winner must net less than 1R after costs, got {net_r}"
assert abs((t._pnl_gross - t.pnl) - bw.trading_cost_usd()) < 1e-9, (
    "the gap between gross and net pnl must be exactly one round trip's cost")
print(f"1R winner nets {net_r:.5f}R after costs (gross 1.0R): OK")

# The cost model itself: COMMISSION_RT_USD + 2 sides x SLIPPAGE_TICKS_PER_SIDE
# ticks x MNQ_TICK_VALUE_USD (v2/s12-paper-harness.md:54: $1.24 RT + 1 tick/side).
expected = bw.COMMISSION_RT_USD + bw.SLIPPAGE_TICKS_PER_SIDE * 2 * bw.MNQ_TICK_VALUE_USD
assert abs(bw.trading_cost_usd() - expected) < 1e-9, (
    f"trading_cost_usd() should be {expected}, got {bw.trading_cost_usd()}")
print("trading_cost_usd() == commission + round-trip slippage: OK")

# A trade that never filled (risk == 0) pays no cost -- nothing was entered.
scratch = T(entry=100.0, stop=100.0, exit_price=100.0)
assert scratch.pnl == scratch._pnl_gross == 0.0, "an unfilled trade must pay no cost"
print("unfilled trade (risk == 0) pays no cost: OK")

print("all backtest cost checks passed")
