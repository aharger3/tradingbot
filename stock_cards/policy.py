"""Which detected candidates become cards. Pure functions, declared before any forward data.

Order of checks (the first that fails is the logged reason):
  dup        already seen today (same symbol, day, signal minute, side)
  window     signal bar outside 09:35-10:58 ET
  ineligible not status 'fired' with tag [clean]  (ELIGIBILITY_NOTE in config.py)
  stale      the decision bar closed more than STALE_SECONDS ago (a late bar; the 2-minute tap clock would be unfair)
  cap        MAX_CARDS_PER_DAY already used today
  gap        the previous card's signal bar closed less than MIN_GAP_MINUTES earlier (so he is never asked twice in a row)
  repeat     a card on the same symbol and side went out less than REPEAT_MINUTES earlier (the engine re-fires one level)
Chronological first-come: the first eligible candidates each morning get a card, at least MIN_GAP_MINUTES apart, six at most. Nothing about the card is
chosen by outcome, grade, or score; every candidate (carded or not) is logged so any null can be rebuilt.
"""
from __future__ import annotations

from datetime import datetime

from .config import (ELIGIBLE_STATUS, ELIGIBLE_TAG, ET, MAX_CARDS_PER_DAY, MIN_GAP_MINUTES, REPEAT_MINUTES, STALE_SECONDS,
                      WEEKDAYS, WINDOW_FIRST, WINDOW_LAST)


def schedule_ok(now: datetime) -> tuple[bool, str]:
    et = now.astimezone(ET)
    if et.weekday() in WEEKDAYS:
        return True, "ok"
    return False, f"{et:%A} is outside the Mon-Thu schedule"


def in_window(sig_t: str) -> bool:
    return WINDOW_FIRST <= sig_t <= WINDOW_LAST


def eligible(c: dict) -> bool:
    return c.get("status") == ELIGIBLE_STATUS and ELIGIBLE_TAG in (c.get("tags") or [])


def decide(c: dict, now: datetime, n_sent_today: int, seen: set, *, cap: int = MAX_CARDS_PER_DAY,
           stale_s: float = STALE_SECONDS, prev_cards: list | None = None, gap_min: float = MIN_GAP_MINUTES,
           repeat_min: float = REPEAT_MINUTES) -> str:
    """'send' or the reason it is not a card. `prev_cards` = today's cards so far, oldest first."""
    if c["key"] in seen:
        return "dup"
    if not in_window(c["sig_t"]):
        return "window"
    if not eligible(c):
        return "ineligible"
    close = datetime.fromisoformat(c["sig_close_ts"])
    if (now - close).total_seconds() > stale_s:
        return "stale"
    if n_sent_today >= cap:
        return "cap"
    prev = prev_cards or []
    if prev and (close - datetime.fromisoformat(prev[-1]["sig_close_ts"])).total_seconds() < gap_min * 60:
        return "gap"
    for p in prev:
        if p["sym"] == c["sym"] and p["side"] == c["side"] and                 abs((close - datetime.fromisoformat(p["sig_close_ts"])).total_seconds()) < repeat_min * 60:
            return "repeat"
    return "send"
