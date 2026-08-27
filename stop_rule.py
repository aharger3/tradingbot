"""stop_rule.py — the one stop trigger, shared by the backtest and the live path.

CLAUDE.md, "Rules that hold everywhere":

    Stops trigger on the candle CLOSE, fill at that close, floored at -1.25R.
    Wicks stop nothing out. Austin settled this five times in one batch of marks.

`Trading-Bot-Rulesets.md`, Austin's Trading Rules clause 1 (167-171): *"Stop-outs
happen on the close, not the wick. A trade is stopped out only when a candle
closes beyond the stop level. A wick through the stop is not a stop-out."*

This is `backtest_week.py`'s omen-5.0 T4(a) trigger, lifted out so there is ONE
copy of the rule. It had two: the backtest's, which was right, and
`paper_trader.py::PaperPosition._check_stop`, which tested the bar's wick and had
never been handed a close at all — G11 (research/g11_live_scratch_scope.md,
section 3) found it had been mismarking every paper position since paper trading
started, always in the direction of cutting a trade the settled rule would have
let ride. A second copy is how that happened; this module exists so a third one
cannot appear quietly.

Scalars, not `Candle` objects: the backtest holds an `omen_bot.Candle`, the live
book holds loose floats off a DXLink bar. One predicate serves both, and this
module imports nothing, so the live path pays no backtest import cost for it.

**Targets are not stops.** A resting limit target fills on an intrabar TOUCH, and
so does Rule 6's break-even scale-out — both are limit orders that are simply
there when price arrives. Only the STOP trigger moved to the close. Callers keep
using the bar's high/low for those; there is deliberately no helper here for
them, because they were never in dispute.
"""


def stop_hit_on_close(close: float, level: float, long: bool) -> bool:
    """The settled rule: a stop triggers only when the bar CLOSES beyond it.

    The trigger moves to the close; the FILL does not. Austin's stop order still
    rests at the level, so both callers exit at the stop price (backtest_week:
    ``t.exit_price = t.stop``; paper_trader: the plan's precomputed
    ``stop_premium``). That is why neither needs the -1.25R floor as live code —
    filling at the level is -1.0R by construction, comfortably inside it.
    """
    return close <= level if long else close >= level


def stop_hit_on_wick(high: float, low: float, level: float, long: bool) -> bool:
    """The pre-omen-5.0 trigger: any wick through the level stops the trade out.

    WRONG per clause 1, and kept only so the old backtest numbers stay
    reproducible: it is reachable from `backtest_week.STOP_ON_CLOSE=0`, which is
    what `research/t4_stop_on_close.md`'s A/B was measured with. The live path
    must never call this — there is no env switch on the live side, on purpose.
    """
    return low <= level if long else high >= level
