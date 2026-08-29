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

`stop_fill_price` is the other half of the rule and lives here for the same
reason: the FILL convention had forked too. `research/exit_lab.py` booked the
close and floored it at -1.25R; `backtest_week.py` and `paper_trader.py` booked
the stop price, which is -1.000R by construction and made the floor dead code
in every shipped rig (research/x2_stop_floor_audit.md, 2026-08-28). One trigger,
one fill, one floor, one module.

**Targets are not stops.** A resting limit target fills on an intrabar TOUCH, and
so does Rule 6's break-even scale-out — both are limit orders that are simply
there when price arrives. Only the STOP trigger moved to the close. Callers keep
using the bar's high/low for those; there is deliberately no helper here for
them, because they were never in dispute.
"""


def stop_hit_on_close(close: float, level: float, long: bool) -> bool:
    """The settled rule: a stop triggers only when the bar CLOSES beyond it.

    The trigger only. What that trigger FILLS at is ``stop_fill_price`` below —
    the same close, floored at -1.25R. Until 2026-08-28 this docstring claimed
    the fill stayed at the level ("Austin's stop order still rests there"), and
    every caller obeyed it. `research/x2_stop_floor_audit.md` measured the price
    of that reading: 458 of the book's 474 stop-outs (96.6%) were triggered by a
    candle that had ALREADY closed past 1R — median -1.35R, worst -4.36R — and
    all 474 were booked as exactly -1.000R. The -1.25R floor CLAUDE.md states was
    therefore unreachable code. Austin, 2026-08-28: "fix stop out 1.25 max
    slippage this needs to be fixed now."
    """
    return close <= level if long else close >= level


# Austin's stated worst case, rule ballot batch 01 q1: "a 1m candle close below
# is exit, max slippage -1.25r which is 1.25k based on current position sizing."
MAX_LOSS_R = 1.25


def stop_fill_price(close: float, entry: float, risk: float, long: bool,
                    floor_r: float = MAX_LOSS_R) -> float:
    """The price a close-triggered stop actually books. ONE definition, all rigs.

    You are out at market once the bar closes beyond the stop, so the fill is
    that CLOSE — worse than the stop price by however far the bar ran — clamped
    so the realised loss can never exceed ``floor_r`` R.

    ``risk`` is the trade's ORIGINAL ``abs(entry - stop)`` and ``entry`` its
    ORIGINAL entry, always. Both are deliberately taken from the caller rather
    than from whichever stop fired: after a scale-out the runner's stop has
    moved (to break-even, or up a trail) and re-basing the denominator on it
    would quietly turn -1.25R of the WHOLE position into -1.25R of a fraction
    of it. The floor is a total-loss floor on the trade, not a slippage
    allowance per stop.

    Monotone and side-symmetric: on a long it can only raise the fill, on a
    short only lower it, so it never invents a better-than-close exit on the
    wrong side. ``risk <= 0`` (a zero-width stop) has no floor to compute, so
    the close is returned unchanged.
    """
    if risk <= 0:
        return close
    if long:
        return max(close, entry - floor_r * risk)
    return min(close, entry + floor_r * risk)


def stop_hit_on_wick(high: float, low: float, level: float, long: bool) -> bool:
    """The pre-omen-5.0 trigger: any wick through the level stops the trade out.

    WRONG per clause 1, and kept only so the old backtest numbers stay
    reproducible: it is reachable from `backtest_week.STOP_ON_CLOSE=0`, which is
    what `research/t4_stop_on_close.md`'s A/B was measured with. The live path
    must never call this — there is no env switch on the live side, on purpose.
    """
    return low <= level if long else high >= level


# ---------------------------------------------------------------------------
# R1 / R2 — the two-stop model (Austin, probe_master_2026-08-29)
# ---------------------------------------------------------------------------
#
# R1, `fact_stop_floor_is_fiction`, verdict `hard`:
#     "-1r is what we want max slippage -1.25"
#
# TWO numbers, both his, and they are not the same number:
#
#   * DISASTER_STOP_R = 1.0  — where the disaster stop RESTS. A live order
#     sitting at entry -/+ 1R that fills on an intrabar TOUCH. This is the loss
#     he plans for.
#   * MAX_LOSS_R = 1.25      — the OUTER BOUND. Nothing may book past it, ever.
#     It is what slippage on the resting order is allowed to cost, not a second
#     stop level.
#
# R2, `fact_two_stops`, verdict `both`:
#     "Level stop on the close, disaster stop on touch."
#
# So the wick rule is intact where it was always about: the LEVEL stop still
# triggers only on a close (`stop_hit_on_close`). The disaster stop is not a
# signal, it is a risk cap, and a cap that only checks closes is not a cap.
# The two coexist; whichever comes first on a bar ends the trade, and the
# disaster stop is tested FIRST because a bar that touched -1R and then closed
# further away was already out at -1R.
DISASTER_STOP_R = 1.0


def disaster_stop_price(entry: float, risk: float, long: bool,
                        stop_r: float = DISASTER_STOP_R) -> float:
    """Where the resting disaster-stop order sits: ``stop_r`` R from ENTRY.

    ``risk`` is the trade's ORIGINAL ``abs(entry - stop)``, for the same reason
    `stop_fill_price` insists on it: after a scale-out the runner's stop has
    moved, and re-basing the disaster stop on it would quietly turn -1R of the
    whole trade into -1R of a fraction of it."""
    return entry - stop_r * risk if long else entry + stop_r * risk


def disaster_stop_hit(high: float, low: float, price: float, long: bool) -> bool:
    """Did this bar TOUCH the resting disaster stop? Intrabar, wick included.

    Deliberately not `stop_hit_on_close`. A resting order is simply there when
    price arrives -- the same reason a limit target fills on a touch. Austin's
    "closes, not wicks" rule is about the LEVEL stop, which is a signal; this is
    a risk cap, and it is the one exception he named himself (verdict `both`)."""
    return low <= price if long else high >= price
