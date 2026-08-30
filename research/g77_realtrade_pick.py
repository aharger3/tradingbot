"""g77_realtrade_pick.py -- the one rule for "which signal is this chart about".

A precision deck asks "does the engine pick good trades?". That question is only
answerable if the card IS a trade the engine took. The g71 homework builder picked
its representative signal by BELIEF -- Austin-ladder S, fewest downgrades, earliest
minute (research/g71_homework_build.py:288-313) -- and never read `traded`. 25 of
its 30 cards were signals the engine refused, and on 10 more of those days it had
booked a different signal on the same chart.

This module holds the replacement rule and the guard that makes the old failure
loud instead of silent. `research/g75_deck2_build.py::candidate_days` already
implements the same rule inline; this is the shared, importable version.

    day_trade(rows)       -> the signal the engine really took on that symbol-day
    guard(cards, ...)     -> raise unless every card is a booked trade
"""
from __future__ import annotations


def booked(rows):
    """Every signal on this symbol-day the engine actually put money on."""
    return [r for r in rows if r.get("traded")]


def day_trade(rows):
    """The signal a card about this symbol-day must be built from, or None.

    The engine's FIRST booked trade of the session on that symbol. That is the
    row the one-trade-a-day book books (research/g72_suppress_price.py::oneaday_rows
    sorts on (day, et, sym) and takes the first), so it is the trade a card is
    allowed to claim. None means the engine refused this whole chart -- such a day
    cannot measure whether the engine trades well and does not belong in a
    precision deck at all.
    """
    b = booked(rows)
    if not b:
        return None
    return min(b, key=lambda r: r.get("et") or "99:99")


def role_guard(cards, label="deck"):
    """Refuse to publish a deck whose cards mislabel their own role.

    G8.2 (research/g82_deck_fix.md): a card must be role "traded" (the
    engine's own booked trade that session) or role "silent" (the engine
    booked nothing that session) -- never a signal it set aside for a
    different trade. `cards` is the list of card dicts a deck builder is about
    to serve, each carrying `role` and `rep` (the book row the card is built
    from). This re-derives the consistency check from `rep["traded"]` rather
    than trusting the label, so a future selection bug is loud, not silent --
    the way `guard` below was loud for the untraded-only failure mode this
    replaces.
    """
    bad = []
    for c in cards:
        role = c.get("role")
        traded = bool(c.get("rep", {}).get("traded"))
        if role not in ("traded", "silent"):
            bad.append((c, "role missing/unknown: %r" % (role,)))
        elif role == "traded" and not traded:
            bad.append((c, "role='traded' but the book row was never booked"))
        elif role == "silent" and traded:
            bad.append((c, "role='silent' but the book row WAS booked"))
    if bad:
        raise AssertionError(
            "%s: %d of %d card(s) failed the role/traded consistency check -- "
            "%s..." % (label, len(bad), len(cards),
                      "; ".join("%s %s (%s)" % (c.get("symbol"), c.get("day"), why)
                                for c, why in bad[:5])))
    return len(cards) - len(bad)


def guard(cards, allow_untraded=False, label="deck"):
    """Refuse to publish a precision deck whose cards are not booked trades.

    `cards` is an iterable of the book rows the deck was built from. Nothing
    warned when 25 of 30 g71 cards were refusals; this is that warning.
    """
    bad = [c for c in cards if not c.get("traded")]
    if bad and not allow_untraded:
        raise AssertionError(
            "%s: %d of %d cards are signals the engine REFUSED to trade "
            "(%s...). A deck of trades the engine will not take cannot measure "
            "whether the engine trades well. Pass allow_untraded=True only if "
            "the deck is deliberately about nominations, and say so on the page."
            % (label, len(bad), len(list(cards)),
               ", ".join("%s %s %s" % (c.get("sym"), c.get("day"), c.get("et"))
                         for c in bad[:3])))
    return len(bad)
