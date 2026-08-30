"""entry_fill.py — the ONE entry fill, the way `stop_rule.py` is the one stop fill.

**THE DEFAULT CHANGED ON 2026-08-30. The entry is now the signal minute's CLOSE.**
Every dollar figure published before that date was priced at a fill nobody could
have sent, and one environment variable puts it back:

    ENTRY_FILL=published python backtest_2y.py     # the old, unobtainable book

Why this module exists, in one paragraph. `signal_runner.fill_price` booked the
entry at ``min(max(level, candle.low), candle.high)`` — the LEVEL, clamped into
the signal bar's own range. But the engine is bar-close driven: the signal does
not exist until that minute closes, so on most trades the book paid a price the
minute had already traded before there was anything to react to. Held fixed on
the same 3,841 trades, changing only the price paid, mean R goes **+0.698 →
+0.022**. `research/g80_lookahead_refute.md` did the counting:

  * **2,067 of 3,841 (53.8%, $1,504,056)** are filled at the bar's own low (long)
    or high (short) with **the level outside the bar entirely** — a resting order
    there would not have filled at a worse price, **it would not have filled**.
  * Of the 1,769 genuinely at the level, the level had already been touched on an
    EARLIER minute in 96.9% of traced cases — the order was long since filled and
    holding a different position.
  * **Only 105 trades — 2.3% of the book, $111,556 — are obtainable at the
    book's price.**

That is the same failure shape as the stop fill in `research/x2_stop_floor_audit.md`:
a fill convention forked across rigs, nobody owned it, and it flattered every
number downstream. So it gets the same cure — ONE function, one module, imports
nothing, and every rig routes through it. Do not re-implement an entry price
anywhere else.

THE FIVE MODES
--------------

``published``    The old clamp. Kept ONLY so every pre-2026-08-30 number stays
                 reproducible. **Unobtainable** — see the 105-of-4,508 count
                 above and `research/g80_lookahead_refute.md`. Never a default,
                 never a recommendation, never quoted without the word
                 "unobtainable" next to it.
``close``        The signal minute's close: the price he can actually see at the
                 instant the signal exists. **THE DEFAULT.**
``next_open``    The next minute's open — what a robot reacting to a closed bar
                 really pays.
``chase_once``   A limit at the level resting for ONE bar, then a market order at
                 the following open if it did not fill.
``limit_level``  A limit at the level resting from the bar AFTER the signal until
                 11:00. **A no-fill is a NO TRADE, not a free option**: the result
                 comes back ``filled=False`` with a reason so callers COUNT the
                 missed day instead of quietly skipping it.

The measured grid, one trade a day (`research/g80_ordertype_grid.md`): control
$683/day (not obtainable), chase-once $68, market-at-close $48, three-bar limit
$46, next open $33. **The last four are a four-way tie — every 95% range straddles
zero — and no winner may be picked out of that block on money.** They are here so
the question is expressible, not because one of them is chosen.

THE LOOK-AHEAD RULE, AND IT HAS ALREADY BEEN BROKEN ONCE
--------------------------------------------------------
An order cannot rest before the order exists. The first attempt at the resting-limit
arm let it rest early: **5,472 of 5,714 fills landed ahead of the signal bar, median
3 minutes early**, which turned a +$92/day arm into a fabricated -$252/day
(`research/g80_lookahead_refute.md`). ``future_bars`` therefore means bars STRICTLY
AFTER the signal bar, it is asserted rather than trusted, and a violation raises
`LookAheadError` instead of returning a number. The signal bar itself is never
scanned for a limit fill, no matter how far through the level it traded.

Bars are duck-typed on ``.open/.high/.low/.close`` plus ``.timestamp``, which is
what `omen_bot.Candle` and the live DXLink bars both already are. Unlike
`stop_rule`, scalars would not do: three of the five modes are statements about a
SEQUENCE of bars.
"""

from __future__ import annotations

import os

ENTRY_FILLS = ("published", "close", "next_open", "chase_once", "limit_level")

# THE DEFAULT FLIP. `published` was the shipped behaviour until 2026-08-30 and is
# a price nobody can pay; leaving a default there is the failure this module
# exists to end. One env var restores it for reproducing an old number.
ENTRY_FILL = os.getenv("ENTRY_FILL", "close").strip().lower()
if ENTRY_FILL not in ENTRY_FILLS:
    raise ValueError("ENTRY_FILL must be one of %s, got %r"
                     % (", ".join(ENTRY_FILLS), ENTRY_FILL))

# Austin does not trade past 11:00 (SESSION_END), so a resting entry order that
# has not filled by then is not a trade he would have taken. Same string shape as
# `signal_runner.SESSION_END`; kept local because this module imports nothing.
ENTRY_LIMIT_EXPIRE = os.getenv("ENTRY_LIMIT_EXPIRE", "11:00:00").strip()

# The modes that are statements about bars the signal bar cannot see.
FORWARD_MODES = ("next_open", "chase_once", "limit_level")


class LookAheadError(AssertionError):
    """A fill was asked for on a bar at or before the signal bar.

    An AssertionError subclass on purpose: this is never a recoverable
    condition, it is a measurement that would be a fiction."""


class EntryFill(tuple):
    """What the entry cost, or why there is no trade.

    ``price``       the price paid, or None when nothing filled
    ``filled``      did an order actually fill
    ``bar_offset``  bars after the signal bar (0 = the signal bar itself), or None
    ``mode``        which of the five produced this
    ``reason``      plain English; on a no-fill this is what a caller reports

    Falsey when unfilled, so ``if not fill: missed.append(...)`` is the natural
    spelling and a no-fill cannot be mistaken for a trade at price None."""

    __slots__ = ()

    def __new__(cls, price, filled, bar_offset, mode, reason):
        return tuple.__new__(cls, (price, filled, bar_offset, mode, reason))

    price = property(lambda s: s[0])
    filled = property(lambda s: s[1])
    bar_offset = property(lambda s: s[2])
    mode = property(lambda s: s[3])
    reason = property(lambda s: s[4])

    def __bool__(self):
        return bool(self[1])

    def __repr__(self):
        if not self.filled:
            return "EntryFill(NO TRADE, %s: %s)" % (self.mode, self.reason)
        return "EntryFill(%.4f, %s, +%s bars)" % (self.price, self.mode,
                                                  self.bar_offset)


def _hhmmss(ts) -> str:
    """"HH:MM:SS" out of whatever shape a bar carries its stamp in.

    A deliberate 10-line copy of `signal_runner.bar_time` rather than an import:
    this module imports nothing so the live path pays no backtest import cost,
    the same reason `stop_rule` holds no `Candle`. Returns "" when it cannot
    parse — and for the forward modes an unparseable stamp is fatal, not
    permissive, because causality is exactly what cannot be assumed here."""
    if not ts:
        return ""
    s = str(ts)
    if "T" in s:
        s = s.split("T", 1)[1]
    elif " " in s:
        s = s.split(" ", 1)[1]
    s = s[:8]
    if len(s) == 5:
        s += ":00"
    return s if len(s) == 8 and s[2] == ":" else ""


def _assert_causal(candle, future_bars, mode):
    """Every bar in ``future_bars`` must be stamped strictly after the signal bar.

    This is the assert the -$252/day arm did not have. It raises rather than
    filtering: silently dropping the offending bars would leave a number that
    looks fine and is not."""
    sig_t = _hhmmss(getattr(candle, "timestamp", None))
    if not sig_t:
        raise LookAheadError(
            "%s needs to prove the order rested AFTER the signal, and the signal "
            "bar carries no usable timestamp (%r). Refusing to guess."
            % (mode, getattr(candle, "timestamp", None)))
    for k, b in enumerate(future_bars):
        bt = _hhmmss(getattr(b, "timestamp", None))
        if not bt:
            raise LookAheadError(
                "%s: future bar %d carries no usable timestamp (%r), so it cannot "
                "be shown to come after the signal at %s."
                % (mode, k, getattr(b, "timestamp", None), sig_t))
        if bt <= sig_t:
            raise LookAheadError(
                "%s: future bar %d is stamped %s, at or BEFORE the signal bar at "
                "%s. An order cannot rest before it exists — this is the exact "
                "bug that fabricated -$252/day (research/g80_lookahead_refute.md)."
                % (mode, k, bt, sig_t))


def _limit_fill(level, bar, is_long):
    """Does a resting limit at ``level`` fill on this bar, and at what price?

    A buy limit fills when the bar trades DOWN to it, and at the OPEN when the
    bar opened through it — a resting order takes the better price, never a
    worse one. Same reasoning as a profit target filling on touch
    (`stop_rule`'s "Targets are not stops"): a limit is simply there when price
    arrives. Returns None when the bar never reached it."""
    if is_long:
        if bar.low <= level:
            return min(level, bar.open)
        return None
    if bar.high >= level:
        return max(level, bar.open)
    return None


def entry_fill_price(level, candle, is_long, close_is_bad_fill=False,
                     mode=None, future_bars=(), expire_at=None) -> EntryFill:
    """THE one entry price. Every rig routes through this; nothing re-implements it.

    ``level``               the level the setup broke/retested — where a resting
                            order would sit. May be None (then only ``close`` and
                            the market modes are meaningful).
    ``candle``              the SIGNAL bar: the minute whose close created the
                            signal. Never scanned for a limit fill.
    ``is_long``             direction.
    ``close_is_bad_fill``   ONLY ``published`` reads it. The caller's own
                            fill-quality verdict — `signal_runner`'s
                            ``bar_extreme_veto`` OR the ON WATCH session-extreme
                            test. It is passed in rather than recomputed here so
                            ``published`` reproduces the old book exactly and
                            this module keeps importing nothing.
    ``future_bars``         bars STRICTLY AFTER the signal bar, in order. Required
                            by the three forward modes; asserted, not trusted.
    ``expire_at``           "HH:MM:SS" the resting limit dies at (default 11:00).

    Returns an `EntryFill`. **Check ``.filled``.** An unfilled result is a NO
    TRADE — count the missed day, do not skip it silently and do not treat the
    day as free.
    """
    m = (mode or ENTRY_FILL).strip().lower()
    if m not in ENTRY_FILLS:
        raise ValueError("ENTRY_FILL must be one of %s, got %r"
                         % (", ".join(ENTRY_FILLS), m))

    if candle is None:
        # No bar at all: there is nothing to price against. The old
        # `fill_price` returned the bare level here; keep that, flagged.
        return EntryFill(level, level is not None, 0, m, "no signal bar; level as given")

    # ---- the two modes that resolve on the signal bar itself --------------
    if m == "close":
        return EntryFill(candle.close, True, 0, m, "market at the signal minute's close")

    if m == "published":
        # THE UNOBTAINABLE FILL. Reproduced byte-for-byte and kept only so
        # pre-2026-08-30 numbers still regenerate. 105 of 4,508 trades are
        # genuinely gettable at this price (research/g80_lookahead_refute.md).
        if level is None:
            return EntryFill(candle.close, True, 0, m, "no level; the close")
        if not close_is_bad_fill:
            return EntryFill(candle.close, True, 0, m, "the close (fill-quality gate clear)")
        px = min(max(level, candle.low), candle.high)
        return EntryFill(px, True, 0, m,
                         "the level clamped into the signal bar's range — UNOBTAINABLE")

    # ---- everything below needs bars the signal bar could not see ---------
    bars = list(future_bars or ())
    _assert_causal(candle, bars, m)

    if m == "next_open":
        if not bars:
            return EntryFill(None, False, None, m,
                             "no minute after the signal (session ended) — NO TRADE")
        return EntryFill(bars[0].open, True, 1, m, "market at the next minute's open")

    if level is None:
        # A limit needs a level to rest at. Refuse rather than invent one.
        return EntryFill(None, False, None, m,
                         "no level to rest a limit at — NO TRADE")

    if m == "chase_once":
        if not bars:
            return EntryFill(None, False, None, m,
                             "no minute after the signal to rest the limit in — NO TRADE")
        px = _limit_fill(level, bars[0], is_long)
        if px is not None:
            return EntryFill(px, True, 1, m, "limit filled on the bar after the signal")
        if len(bars) < 2:
            return EntryFill(None, False, None, m,
                             "limit unfilled and no bar left to chase into — NO TRADE")
        return EntryFill(bars[1].open, True, 2, m,
                         "limit missed; market at the following open")

    # m == "limit_level" — rests from the bar AFTER the signal, expires 11:00.
    exp = (expire_at or ENTRY_LIMIT_EXPIRE)
    for k, b in enumerate(bars):
        if _hhmmss(getattr(b, "timestamp", None)) >= exp:
            return EntryFill(None, False, None, m,
                             "limit at %.4f never traded before %s — NO TRADE"
                             % (level, exp))
        px = _limit_fill(level, b, is_long)
        if px is not None:
            return EntryFill(px, True, k + 1, m,
                             "resting limit filled %d bar(s) after the signal" % (k + 1))
    return EntryFill(None, False, None, m,
                     "limit at %.4f never traded before the session ran out — NO TRADE"
                     % level)


def needs_future_bars(mode=None) -> bool:
    """True when this mode cannot be priced from the signal bar alone.

    `signal_runner` is fed a strict PREFIX of the session (``candles[:i+1]``),
    on purpose — that is what makes look-ahead structurally impossible inside
    the engine. So it cannot resolve the forward modes itself; `backtest_week`
    re-prices those entries once, at the trade-creation site, with the bars that
    come after. Callers use this to know which of them owns the price."""
    return (mode or ENTRY_FILL).strip().lower() in FORWARD_MODES
