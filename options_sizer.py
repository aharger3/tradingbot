"""Options-native signal output: strike, expiration, premium-based entry/stop/target.

Workflow:
  1. Stock signal fires → stock_entry, stock_stop, direction
  2. Pick nearest expiration (0DTE if early in day, else next trading day)
  3. Pick nearest ATM strike (round to symbol's increment)
  4. Fetch live option mid from Tastytrade DXLink (real-time)
  5. Estimate stop premium = entry_premium - (stock_risk × delta_estimate)
  6. Contracts = floor(max_loss / ((entry - stop) × 100))
"""

import math
import os
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional, Literal, List
from zoneinfo import ZoneInfo

import black_scholes as bs

_ET = ZoneInfo("America/New_York")


CONTRACT_MULTIPLIER = 100
DEFAULT_MAX_LOSS = 1000.0
# G7.2 target25, 2026-08-29: re-measured on the current book
# (research/g72_target25_report.md) after the reject-suppression fix changed
# what "the current book" even is (2,437 -> 4,508 traded rows). Aiming 2.5R
# instead of 2R is still real there too: +$33/trade, 95% paired CI
# [+$9, +$56], same 25/25 green months, 102/105 green weeks either way.
# Austin's standing instruction is to take a measured edge without asking.
# This is the ONLY live exit lever this repo has (research/g71_board.md #1:
# "live sells the whole position at 2R with no runner" -- the runner itself
# is a separate, unmade change; this is the target the whole position exits
# at today). 5R (+$62/trade, CI touches zero [-$0, +$122]) does not clear its
# own bar on this book either -- not taken, per the ticket's own scope.
DEFAULT_RR = 2.5
DEFAULT_DELTA = 0.5  # ATM ≈ 0.5

# ---- T2: ENABLE_CONTRACT_R -- the real pricer, DEFAULT OFF -------------------
# `DEFAULT_DELTA = 0.5` is a flat linear delta and it was the entire options
# model in this repo. It cannot express convexity (a winning 0DTE call's delta
# climbs toward 1.0, so the runner earns MORE than the underlying move) or theta
# (the same contract bleeds while it waits). Austin's runner thesis is a bet that
# the first beats the second; a constant makes that bet unmeasurable.
#
# ON, `premium_risk` comes from repricing the contract at the stop with
# `black_scholes`, instead of `stock_risk * 0.5`. OFF, this file behaves exactly
# as it did before T2 -- the flag is checked in one place, `atm_delta()`, and its
# OFF branch returns `DEFAULT_DELTA` before touching the pricer.
#
# The 2-year book (`research/g3_arm_ow1.json`, from `backtest_2y.py`) does not
# import this module at all, so the book cannot move either way. That is asserted
# in `research/t2_options_tape.py --selfcheck` and re-proved by regenerating the
# book, not merely argued. See `research/t2_options_tape.md`.
ENABLE_CONTRACT_R = os.getenv("ENABLE_CONTRACT_R", "0") not in ("0", "", "false", "off")


# ---- G7.2 liveexit: the RUNNER LEG, ported from the backtest. DEFAULT OFF ----
#
# `research/g71_board.md` #1, the biggest single item on the board:
#
#     "Live sells everything at 2R with no runner, and half the money is above
#      2R. 94 of your 496 one-a-day trades (19%) ran past 2R, and those 94
#      trades carry 50.1% of every dollar the strategy makes."
#
# The backtest has scaled out at the session high and let a runner go since F1
# (`backtest_week.py::_ladder_bar`, SCALE_PLAN="hod_then_runner_be"). The live
# path never grew the leg: `build_options_plan` emits one target and
# `paper_trader` closes the WHOLE position on it (research/g71_rrcapv.md).
#
# This block is that exit, ported. It is OFF by default and Austin has not said
# to turn it on -- board §"WHAT ONLY AUSTIN CAN DECIDE" #5 is exactly the
# question of whether the live card shows two rungs. Turn it on with
# OMEN_LIVE_LADDER=1 and nothing else; leave it alone otherwise.
#
# What the switch buys, on the same trade, is proved rather than asserted:
# `research/g72_liveexit_parity.py` drives one geometry through
# `backtest_week._ladder_bar` and through `paper_trader.PaperBook.mark` bar for
# bar and asserts the two book the same R to 1e-9.
LIVE_LADDER = os.getenv("OMEN_LIVE_LADDER", "0") not in ("0", "", "false", "off")

# Mirrors backtest_week.SCALE_PLAN. "hod_then_runner_be" is the backtest's
# shipped default: the first rung also raises the runner's stop to break-even.
# "hod_then_runner" leaves the runner on the original stop.
LIVE_LADDER_PLAN = os.getenv("OMEN_LIVE_LADDER_PLAN", "hod_then_runner_be").strip().lower()

# Fraction taken off at the first rung. backtest_week bills the ladder as
# `0.5 * scale_r + 0.5 * run_r` (backtest_week.py::SimTrade.pnl), so 0.5 is not
# a tunable here -- it is the number the parity test pins.
LIVE_LADDER_SCALE_PCT = 0.5


def premium_at(stock_price: float, stock_entry: float, entry_premium: float,
               stock_risk: float, premium_risk: float, long: bool) -> float:
    """The ONE stock-price -> premium map. Every leg of the card goes through it.

    The plan already prices `stock_entry` at `entry_premium` and the stop
    distance `stock_risk` at `premium_risk`, so `premium_risk / stock_risk` IS
    the delta this plan was built with. Reusing it -- rather than inventing a
    second delta at exit time -- is what makes the live book and the backtest
    book the same R on the same trade: booked R is
    `(premium_at(P) - entry_premium) / premium_risk`, which cancels to
    `(P - stock_entry) / stock_risk`, the backtest's stock-side R exactly.

    Linear, which is what this whole module assumes (`DEFAULT_DELTA = 0.5`);
    there is no options tape in this repo to do better, and ENABLE_CONTRACT_R
    is the flag that replaces the assumption when one exists.

    Clamped at $0.05: a long option's loss is bounded by its premium. That
    clamp is the ONE place live can diverge from the backtest, and only ever in
    live's favour -- it can make a fill less bad, never worse. It binds when
    `entry_premium < 0.05 + 1.25 * premium_risk`, i.e. on a wide stock stop
    mapped onto a cheap contract. `research/g72_liveexit_parity.py` pins that
    direction as an inequality instead of pretending it does not exist.
    """
    if stock_risk <= 0 or premium_risk <= 0:
        return entry_premium
    moved = (stock_price - stock_entry) if long else (stock_entry - stock_price)
    return max(entry_premium + moved / stock_risk * premium_risk, 0.05)


def _plan_reward(entry_premium: float, target_premium: float,
                 scale_premium: float, runner_target_premium: float,
                 scale_pct: float, contracts: int, has_ladder: bool) -> float:
    """Dollars this plan pays if every rung it names is reached.

    G7.2 liveexit (board #3). One target -> the target. Two rungs -> both rungs,
    at the contract split the book will actually use.
    """
    if not has_ladder:
        return round((target_premium - entry_premium) * CONTRACT_MULTIPLIER
                     * contracts, 2)
    scale_ct = ladder_scale_contracts(contracts, scale_pct)
    run_ct = contracts - scale_ct
    return round(((scale_premium - entry_premium) * scale_ct
                  + (runner_target_premium - entry_premium) * run_ct)
                 * CONTRACT_MULTIPLIER, 2)


def ladder_scale_contracts(contracts: int, scale_pct: float) -> int:
    """How many contracts come off at the first rung. ONE definition.

    The backtest bills the ladder as `0.5 * scale_r + 0.5 * run_r` -- a
    fractional half, which a real position cannot do. This is the one place the
    live book cannot match it exactly, and it is contract granularity, not a
    rule difference: on an EVEN count the two are identical.
    `max(..., 1)` follows Rule 6's existing convention -- on a single contract
    you take the one off at the high (Austin: "you always take something off at
    HOD") and there is no runner. The sizer needs this to state the card's
    reward honestly and `paper_trader` needs it to fill the rung; they must not
    each have their own copy.
    """
    if contracts <= 0:
        return 0
    return min(max(int(contracts * scale_pct), 1), contracts)


def ladder_levels(direction: str, session_extreme: float,
                  pdh: Optional[float] = None, pdl: Optional[float] = None,
                  pmh: Optional[float] = None, pml: Optional[float] = None):
    """(scale_level, runner_target) -- the same two numbers backtest_week builds.

    Line for line `backtest_week.py:880-893`: the scale rung is the session
    extreme AS OF THE ENTRY BAR (the caller supplies it; computing it from
    later bars would be look-ahead), and the runner aims at the first key level
    beyond that rung -- previous day's high/low, pre-market high/low, else the
    next whole dollar.

    Known and NOT fixed here: board bug #6, "the runner can never aim more than
    $1 past the session high", which bites on 2,135 of 2,437 trades. That is a
    separate item with its own owner (`research/g71_faraway.py`); porting the
    rule means porting it as it is, warts included, or the parity test is
    measuring my opinion instead of the book.
    """
    if session_extreme <= 0:
        return 0.0, 0.0
    if direction == "call":
        scale_level = session_extreme
        cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]
        cands.append(math.floor(scale_level) + 1.0)   # next psych whole $
        return scale_level, min(cands)
    scale_level = session_extreme
    cands = [x for x in (pdl, pml) if x is not None and x < scale_level]
    cands.append(math.ceil(scale_level) - 1.0)
    return scale_level, max(cands)


def atm_delta(direction: str, spot: float, strike: float,
              iv: Optional[float] = None,
              minutes_to_expiry: Optional[float] = None) -> float:
    """Delta for the sizer. `DEFAULT_DELTA` unless ENABLE_CONTRACT_R is on.

    `iv` is annualised. `minutes_to_expiry` is RTH minutes (390 per session,
    252 sessions per year). Both are required for the pricer -- there is no
    options tape in this repo, so an IV has to be handed in by the caller and
    there is no safe default to invent. Without them the flag degrades to
    `DEFAULT_DELTA` rather than guessing.
    """
    if not ENABLE_CONTRACT_R:
        return DEFAULT_DELTA
    if not iv or not minutes_to_expiry or minutes_to_expiry <= 0 or spot <= 0:
        return DEFAULT_DELTA
    T = minutes_to_expiry / (390.0 * 252.0)
    return abs(bs.delta(spot, strike, T, iv, call=(direction == "call")))

# Grade → fraction of max loss to risk (SPEC2). C = alert-only, D = filtered upstream.
# "X" is the skip grade (T5 rename); "D" kept as its old letter — both 0%.
# "A+" is kept the same way (2026-08-30, A+ retired -- A is now the top grade
# and sized at 0.8, its own long-standing size) for old data still carrying
# the letter; nothing produces a fresh "A+" signal any more.
GRADE_SIZE_PCT = {"A+": 1.0, "A": 0.8, "B": 0.6, "C": 0.4, "X": 0.0, "D": 0.0}

# Per-symbol strike increment (USD)
# Initial-guess only — fetch_option_snapshot queries ±$5 range and picks closest
# actual contract, so this matters mostly for fallback estimation mode.
STRIKE_INCREMENT = {
    "TSLA": 5.0,   # $433
    "NVDA": 2.5,   # $215
    "AAPL": 2.5,   # $308
    "AMD": 5.0,    # $504
    "MSFT": 5.0,   # $415
    "GOOG": 2.5,   # $385
    "META": 5.0,   # $611
    "AMZN": 2.5,   # $265
    "PLTR": 1.0,   # $137
    "SPY": 1.0,    # $750
    "QQQ": 1.0,    # $729
}


@dataclass
class OptionsPlan:
    """Concrete options trade card for Discord."""
    symbol: str
    direction: Literal["call", "put"]
    expiration: str            # "YYYY-MM-DD"
    strike: float
    entry_premium: float
    stop_premium: float
    target_premium: float
    contracts: int
    max_loss: float
    max_reward: float
    # Reference stock levels for context
    stock_entry: float
    stock_stop: float
    stock_target: float
    # Quote quality
    quote_source: str  # "tastytrade_dxlink_realtime" or "estimated_delta"
    occ_symbol: str
    bid_ask_spread: float = 0.0
    option_warnings: List[str] = field(default_factory=list)
    rr: float = DEFAULT_RR  # G7.2 target25: label must track DEFAULT_RR, never hardcode "2R"
    # ---- G7.2 liveexit: the runner leg. All zero unless LIVE_LADDER is on ----
    # `scale_level` is the session extreme as of the entry bar, `runner_target`
    # the first key level beyond it (options_sizer.ladder_levels, which is
    # backtest_week.py:880-893). Zero means "no ladder on this plan" and
    # paper_trader falls straight back to the single all-out target.
    scale_level: float = 0.0
    runner_target: float = 0.0
    scale_premium: float = 0.0
    runner_target_premium: float = 0.0
    scale_pct: float = 0.0
    # G7.2 liveexit (board #3): the delta-implied premium move over the stock
    # stop distance, BEFORE the $0.05 floor. This is the delta this plan was
    # built with, and it is what `premium_at` needs to price any leg. It is NOT
    # `entry_premium - stop_premium` -- those differ exactly when the floor
    # binds, and that difference is the whole of board bug #3.
    premium_risk: float = 0.0

    @property
    def has_ladder(self) -> bool:
        return self.scale_level > 0.0 and self.runner_target > 0.0

    @property
    def booked_rr(self) -> float:
        """The reward:risk this card ACTUALLY pays, not the `rr` it aimed at.

        Equal to `rr` on 98.6% of rows. Bigger whenever the $0.05 floor bound,
        because the loss is capped by the premium while the gain is not.
        """
        risk = self.entry_premium - self.stop_premium
        return (self.target_premium - self.entry_premium) / risk if risk > 0 else 0.0

    def format_discord(self) -> str:
        arrow = "↑" if self.direction == "call" else "↓"
        right = "CALL" if self.direction == "call" else "PUT"
        dte = self._dte_label()
        lines = (
            f"**{self.symbol} {dte} ${self.strike:g} {right}** {arrow}\n"
            f"Expiration: {self.expiration}\n"
            f"Strike:     ${self.strike:g} (ATM)\n"
            f"Entry:      ${self.entry_premium:.2f}\n"
            f"Stop:       ${self.stop_premium:.2f}  (sell if drops here)\n"
        )
        if self.has_ladder:
            # G7.2 liveexit: two rungs, the same two the backtest books.
            lines += (
                f"Scale 1:    ${self.scale_premium:.2f}  "
                f"(sell {self.scale_pct:.0%} at the session high, ${self.scale_level:.2f})\n"
                f"Runner:     ${self.runner_target_premium:.2f}  "
                f"(the rest runs to ${self.runner_target:.2f})\n"
            )
        else:
            # G7.2 liveexit (board #3): say the ratio the target ACTUALLY pays.
            # "sell all at 2.5R" next to a target worth 7.5R was the card lying
            # to itself; on the 98.6% of rows where the floor never binds these
            # two are the same number and the card reads exactly as it always did.
            r_label = (f"{self.rr:g}R" if abs(self.booked_rr - self.rr) < 0.05
                       else f"{self.booked_rr:.1f}R — the $0.05 stop floor caps "
                            f"the loss, so this pays more than {self.rr:g}R")
            lines += f"Target:     ${self.target_premium:.2f}  (sell all at {r_label})\n"
        lines += (
            f"Contracts:  {self.contracts}  → max loss ${self.max_loss:.0f} / max reward ${self.max_reward:.0f}\n"
            f"Stock ref:  entry ${self.stock_entry:.2f} | stop ${self.stock_stop:.2f} | target ${self.stock_target:.2f}\n"
            f"Quote: {self.quote_source}"
        )
        if self.bid_ask_spread > 0:
            lines += f"\nSpread:     ${self.bid_ask_spread:.2f}"
        if self.option_warnings:
            lines += f"\n⚠ {', '.join(self.option_warnings)}"
        return lines

    def _dte_label(self) -> str:
        try:
            exp = datetime.strptime(self.expiration, "%Y-%m-%d").date()
            days = (exp - date.today()).days
            if days == 0:
                return "0DTE"
            return f"{days}DTE"
        except Exception:
            return ""


# OPUS-SPEC #6: Scarface contract selection (2026-07-12)
# Scarface buys the FIRST OTM strike on the nearest WEEKLY (Friday) expiry, not
# nearest-ATM 0DTE. Prior: nearest_strike + nearest_expiration always. Change:
# toggle routes strike/expiry through first_otm_strike/weekly_expiration.
# Default OFF: ATM/0DTE is the measured baseline; flip after a live premium
# comparison (OTM weekly = lower delta, cheaper premium, different sizing).
SCARFACE_CONTRACT = False  # True = first OTM strike + nearest Friday expiration


def nearest_strike(stock_price: float, symbol: str) -> float:
    inc = STRIKE_INCREMENT.get(symbol.upper(), 2.5)
    return round(stock_price / inc) * inc


def first_otm_strike(stock_price: float, symbol: str, direction: str) -> float:
    """OPUS-SPEC #6: first strike strictly beyond spot in the trade direction."""
    inc = STRIKE_INCREMENT.get(symbol.upper(), 2.5)
    base = round(stock_price / inc) * inc
    if direction == "call":
        return base + inc if base <= stock_price else base
    return base - inc if base >= stock_price else base


def weekly_expiration(now: Optional[datetime] = None) -> str:
    """OPUS-SPEC #6: nearest Friday (this week's weekly; today if Friday)."""
    if now is None:
        # T13: was `utcnow() - timedelta(hours=4)`, hardcoded EDT, wrong Nov-Mar.
        now = datetime.now(_ET)
    d = now.date()
    return (d + timedelta(days=(4 - d.weekday()) % 7)).isoformat()


def nearest_expiration(now: Optional[datetime] = None) -> str:
    """Pick 0DTE if before 14:30 ET, else next trading day.

    Note: NOT all symbols have daily expirations. TSLA & NVDA do.
    For others, you may get a 404 on snapshot — fallback handled in caller.
    """
    if now is None:
        # T13: was `utcnow() - timedelta(hours=4)`, hardcoded EDT, wrong Nov-Mar.
        now = datetime.now(_ET)
    today = now.date()
    # Before 14:30 ET, use today (0DTE has plenty of value left)
    cutoff = time(14, 30)
    if now.time() < cutoff and today.weekday() < 5:
        return today.isoformat()
    # Otherwise next weekday
    next_day = today + timedelta(days=1)
    while next_day.weekday() >= 5:  # skip weekend
        next_day += timedelta(days=1)
    return next_day.isoformat()


def build_options_plan(
    symbol: str,
    direction: Literal["call", "put"],
    stock_entry: float,
    stock_stop: float,
    tasty_feed=None,            # TastytradeFeed instance, optional (preferred)
    max_loss: float = DEFAULT_MAX_LOSS,
    rr: float = DEFAULT_RR,
    delta_estimate: float = DEFAULT_DELTA,
    expiration: Optional[str] = None,
    strike: Optional[float] = None,
    iv: Optional[float] = None,               # T2: annualised, ENABLE_CONTRACT_R only
    minutes_to_expiry: Optional[float] = None,  # T2: RTH minutes, 390 per session
    # G7.2 liveexit: the runner leg's inputs. All optional, all ignored unless
    # LIVE_LADDER is on AND `session_extreme` is supplied -- so `live_scanner.py`
    # (which does not pass them) keeps the exact single-target card it has today.
    session_extreme: Optional[float] = None,  # session HOD (call) / LOD (put) AS OF the entry bar
    pdh: Optional[float] = None,
    pdl: Optional[float] = None,
    pmh: Optional[float] = None,
    pml: Optional[float] = None,
) -> OptionsPlan:
    """Build full options trade card.

    Premium sources (priority): Tastytrade (real-time) > delta estimate.

    T2: with `ENABLE_CONTRACT_R` on AND `iv` / `minutes_to_expiry` supplied, the
    premium risk is a full Black-Scholes reprice at the stock stop instead of
    `stock_risk * 0.5`. Off (the default), or with either input missing, the
    arithmetic below is bit-for-bit what it was before T2.
    """
    # 1. Stock-side risk/reward
    if direction == "call":
        if stock_stop >= stock_entry:
            raise ValueError(f"Call stop ({stock_stop}) must be below entry ({stock_entry})")
        stock_risk = stock_entry - stock_stop
        stock_target = stock_entry + rr * stock_risk
    else:
        if stock_stop <= stock_entry:
            raise ValueError(f"Put stop ({stock_stop}) must be above entry ({stock_entry})")
        stock_risk = stock_stop - stock_entry
        stock_target = stock_entry - rr * stock_risk

    # 2. Strike + expiration (OPUS-SPEC #6: Scarface = first OTM weekly)
    if strike is None:
        strike = (first_otm_strike(stock_entry, symbol, direction) if SCARFACE_CONTRACT
                  else nearest_strike(stock_entry, symbol))
    if expiration is None:
        expiration = weekly_expiration() if SCARFACE_CONTRACT else nearest_expiration()

    # 3. Entry premium: Tastytrade (real-time) > delta estimate
    quote_source = "estimated_delta"
    entry_premium = None
    occ_symbol = ""
    bid_ask_spread = 0.0
    option_warnings = []
    if tasty_feed is not None:
        try:
            snap = tasty_feed.fetch_option_quote(symbol, expiration, strike, direction)
            if snap and snap.get("mid"):
                entry_premium = snap["mid"]
                quote_source = "tastytrade_dxlink_realtime"
                occ_symbol = snap.get("occ_symbol", "")
                if snap.get("strike"):
                    strike = snap["strike"]
                # Spread check
                bid = snap.get("bid", 0) or 0
                ask = snap.get("ask", 0) or 0
                if bid and ask:
                    bid_ask_spread = round(ask - bid, 2)
                    if bid_ask_spread > 0.50:
                        option_warnings.append("wide spread")
        except Exception as e:
            print(f"  tasty quote failed: {e}")

    if entry_premium is None:
        # Fallback: rough ATM 0DTE estimate.
        entry_premium = max(round(stock_entry * 0.005, 2), 0.50)

    # Post-premium filters
    if entry_premium < 0.20:
        option_warnings.append("too cheap")
    if occ_symbol and occ_symbol.startswith(" "):
        option_warnings.append("no liquidity")

    # 4. Stop + target in PREMIUM terms
    # Stop = entry - (stock_risk × delta × multiplier)
    # Premium moves roughly delta × stock_move (per share, no multiplier)
    premium_risk = round(stock_risk * delta_estimate, 2)
    if ENABLE_CONTRACT_R and iv and minutes_to_expiry and minutes_to_expiry > 0:
        # The premium actually lost when the underlying reaches the stop, priced
        # rather than approximated. Strictly SMALLER than delta*stock_risk,
        # because a long option is convex: the loss decelerates on the way down.
        _T = minutes_to_expiry / (390.0 * 252.0)
        _call = direction == "call"
        _p0 = bs.price(stock_entry, strike, _T, iv, call=_call)
        _pstop = bs.price(stock_stop, strike, _T, iv, call=_call)
        premium_risk = round(max(_p0 - _pstop, 0.0), 2)
        delta_estimate = atm_delta(direction, stock_entry, strike, iv, minutes_to_expiry)
        quote_source += "+bs_premium_risk"
    if premium_risk < 0.05:
        premium_risk = 0.05  # min tick guard

    _long = direction == "call"
    # G7.2 liveexit, 2026-08-29 -- THE $0.05 FLOOR BUG (board #3).
    #
    # THREE numbers used to be built three different ways here, and they did not
    # agree with each other:
    #
    #   stop_premium   floored at $0.05  -- a long option cannot be worth less
    #                                       than a tick, so this one is right
    #   target_premium raw arithmetic    -- entry + rr * premium_risk
    #   max_reward     a third formula   -- per_contract_risk * contracts * rr,
    #                                       which assumes reward and risk are
    #                                       symmetric in R, and they are NOT
    #                                       once the floor has bound
    #
    # `research/g71_rrcapv.md` measured the damage: on 34 of 2,437 traded rows
    # (1.40%) the floor binds, and 33 of them book MORE than `rr` -- worst MU
    # 2026-07-31, $6,560 booked on $872 of risk (7.52R) while `plan.max_reward`
    # said $1,744. The card under-reported the reward by 3.8x.
    #
    # All three now come out of ONE function, `premium_at()`, with ONE floor.
    # That is what "floor both legs the same way" has to mean here: the same map
    # and the same $0.05 clamp on both sides. The clamp only ever BINDS on the
    # downside, because that is the only side a premium can fall to zero on --
    # which is exactly why the reward:risk on those 34 rows is genuinely better
    # than `rr` and is not a bug to be removed.
    #
    # What must NOT be done, and was checked before it was not done: flooring
    # the TARGET leg the same arithmetic way. The exit TRIGGER is the stock
    # target (`stock_target`, unchanged by any of this, and `paper_trader`
    # fires on it), so the only thing a floored target changes is the premium
    # booked when that stock price arrives. On the MU row the contract is worth
    # $37.21 at 816.40 on a 0.5 delta; a floored target would book $13.13 --
    # a $2,408-a-contract gain thrown away for the sake of a tidier ratio.
    # `research/g72_liveexit_report.md` carries that arithmetic.
    stop_premium = round(max(entry_premium - premium_risk, 0.05), 2)
    # This IS `premium_at(stock_target, ...)`: the map's ratio is
    # `(stock_target - stock_entry) / stock_risk`, which is `rr` exactly. Spelt
    # algebraically because computing it through the division reintroduces `rr`
    # as 2.4999999999 and tips the cent rounding on 578 of the book's 4,508
    # traded rows by $0.01 -- a shipped price moving for no reason at all.
    # Nothing else here needs the divide, so nothing else pays for it.
    target_premium = round(entry_premium + (rr * premium_risk), 2)

    # 5. Contracts
    per_contract_risk = (entry_premium - stop_premium) * CONTRACT_MULTIPLIER
    contracts = int(max_loss // per_contract_risk) if per_contract_risk > 0 else 0

    # 6. G7.2 liveexit: the ladder rungs, priced through the SAME delta map as
    #    the stop and target legs. Off unless the switch is on and the caller
    #    handed in the entry bar's session extreme -- there is no way to guess
    #    it here, and guessing it from the current price would be look-ahead.
    scale_level = runner_target = 0.0
    scale_premium = runner_target_premium = 0.0
    scale_pct = 0.0
    if LIVE_LADDER and session_extreme:
        scale_level, runner_target = ladder_levels(
            direction, session_extreme, pdh=pdh, pdl=pdl, pmh=pmh, pml=pml)
        # The rung has to be BEYOND entry to be a scale-out; a session extreme
        # already behind us is not one. backtest_week never builds that case
        # (the entry bar's own high is >= the entry price by construction), but
        # a live caller can, so it degrades to "no ladder" rather than to a
        # rung that fills instantly.
        _beyond = (scale_level > stock_entry) if _long else (scale_level < stock_entry)
        _ordered = (runner_target > scale_level) if _long else (runner_target < scale_level)
        if _beyond and _ordered:
            scale_pct = LIVE_LADDER_SCALE_PCT
            scale_premium = round(premium_at(
                scale_level, stock_entry, entry_premium,
                stock_risk, premium_risk, _long), 2)
            runner_target_premium = round(premium_at(
                runner_target, stock_entry, entry_premium,
                stock_risk, premium_risk, _long), 2)
        else:
            scale_level = runner_target = 0.0

    return OptionsPlan(
        symbol=symbol.upper(),
        direction=direction,
        expiration=expiration,
        strike=strike,
        entry_premium=entry_premium,
        stop_premium=stop_premium,
        target_premium=target_premium,
        contracts=contracts,
        max_loss=round(per_contract_risk * contracts, 2),
        # G7.2 liveexit (board #3). Was `per_contract_risk * contracts * rr`,
        # which is `max_loss * rr` -- an identity, not a measurement. It could
        # only ever return `rr` and it disagreed with the target it sat next to
        # by up to 3.8x. This is the reward the card's OWN PLAN actually pays:
        # with a ladder that is both rungs, not the all-out target the ladder
        # never sells at. Quoting the all-out number on a two-rung card would
        # be the same lie in a new place.
        max_reward=_plan_reward(entry_premium, target_premium, scale_premium,
                                runner_target_premium, scale_pct, contracts,
                                scale_level > 0.0 and runner_target > 0.0),
        premium_risk=premium_risk,
        stock_entry=round(stock_entry, 2),
        stock_stop=round(stock_stop, 2),
        stock_target=round(stock_target, 2),
        quote_source=quote_source,
        occ_symbol=occ_symbol,
        bid_ask_spread=bid_ask_spread,
        option_warnings=option_warnings,
        rr=rr,
        scale_level=scale_level,
        runner_target=runner_target,
        scale_premium=scale_premium,
        runner_target_premium=runner_target_premium,
        scale_pct=scale_pct,
    )


if __name__ == "__main__":
    # Test without Tastytrade (estimation only)
    plan = build_options_plan(
        symbol="TSLA",
        direction="call",
        stock_entry=440.50,
        stock_stop=439.80,
    )
    print(plan.format_discord())
    print()
    plan_put = build_options_plan(
        symbol="NVDA",
        direction="put",
        stock_entry=850.00,
        stock_stop=852.50,
    )
    print(plan_put.format_discord())


# ---------------------------------------------------------------------------
# Futures (Omen futures mode) — SPEC15
# ---------------------------------------------------------------------------

@dataclass
class FuturesPlan:
    """Concrete futures trade card for Discord. Price-level stops, no premium."""
    contract: str              # "ES", "NQ", "RTY"
    direction: Literal["long", "short"]
    entry: float
    stop: float
    target: float
    contracts: int
    point_value: float
    max_loss: float
    max_reward: float
    rr: float = DEFAULT_RR  # G7.2 target25: label must track DEFAULT_RR, never hardcode "2R"

    def format_discord(self) -> str:
        arrow = "↑" if self.direction == "long" else "↓"
        return (
            f"**{self.contract} {self.direction.upper()}** {arrow} (futures)\n"
            f"Entry:      {self.entry:g}\n"
            f"Stop:       {self.stop:g}  ({abs(self.entry - self.stop):g} pts)\n"
            f"Target:     {self.target:g}  ({self.rr:g}R)\n"
            f"Contracts:  {self.contracts}  → max loss ${self.max_loss:.0f} / max reward ${self.max_reward:.0f}\n"
            f"Point val:  ${self.point_value:.0f}/pt per contract"
        )


def build_futures_plan(
    contract: str,
    direction: Literal["long", "short"],
    entry: float,
    stop: float,
    grade: str = "A",
    max_loss: float = DEFAULT_MAX_LOSS,
    rr: float = DEFAULT_RR,
) -> FuturesPlan:
    """Size a futures trade: contracts = floor(grade-scaled max loss / $risk per contract).

    ES $50/pt, NQ $20/pt, RTY $50/pt. Same A-D grade scaling as options
    (C sizes at 40% but stays alert-only upstream; D never reaches here).
    """
    from futures_feed import POINT_VALUE, TICK_SIZE

    contract = contract.upper()
    point_value = POINT_VALUE[contract]
    tick = TICK_SIZE[contract]

    if direction == "long":
        if stop >= entry:
            raise ValueError(f"Long stop ({stop}) must be below entry ({entry})")
        risk_pts = entry - stop
        target = entry + rr * risk_pts
    else:
        if stop <= entry:
            raise ValueError(f"Short stop ({stop}) must be above entry ({entry})")
        risk_pts = stop - entry
        target = entry - rr * risk_pts

    if risk_pts < tick:
        raise ValueError(f"Stop distance {risk_pts} under one tick ({tick})")

    budget = max_loss * GRADE_SIZE_PCT.get(grade, 0.0)
    per_contract_risk = risk_pts * point_value
    contracts = int(budget // per_contract_risk)

    return FuturesPlan(
        contract=contract,
        direction=direction,
        entry=entry,
        stop=stop,
        target=round(target / tick) * tick,
        contracts=contracts,
        point_value=point_value,
        max_loss=round(per_contract_risk * contracts, 2),
        max_reward=round(per_contract_risk * contracts * rr, 2),
        rr=rr,
    )
