"""g75_trendfilter_lib.py -- one definition of "how much is this day trending",
in a hindsight flavour and several causal ones, so the two can never be mixed up.

BACKGROUND. Of seven measurable properties tested against Austin's 30 yes/no
answers on research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl, only
"session trendiness" separated them: 0.145 on his yes-days vs 0.072 on his
no-days, p=0.014 (research/g74_verdict.md section 4). That number is the Kaufman
efficiency ratio of the WHOLE 09:30-11:00 session -- research/t21_card_filter.py
::_efficiency_ratio, which t21 is explicit is a card-selection statistic and
"must NEVER be wired into detection ... that would be look-ahead".

So the number that predicts him is not tradeable. Everything in this module
exists to answer one question: how much of it survives being computed only from
bars that exist BEFORE the trade.

ER = |last close - first close| / sum(|close[i] - close[i-1]|).
1.0 is a straight line; ~0.0 is pure chop. It is the same arithmetic at every
timescale; only the bars change.

Nothing here is imported by engine code. Read-only on data_archive.
"""
from __future__ import annotations

import csv
import os
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVE = os.path.join(ROOT, "data_archive")


def er(vals) -> float | None:
    """Kaufman efficiency ratio of a close series."""
    if vals is None or len(vals) < 3:
        return None
    path = sum(abs(vals[i] - vals[i - 1]) for i in range(1, len(vals)))
    if path <= 0:
        return None
    return abs(vals[-1] - vals[0]) / path


@lru_cache(maxsize=4096)
def bars(symbol: str, day: str):
    """All archived 1m bars for one symbol-day, 04:00 onward, as
    (hhmm, o, h, l, c) tuples. () when the day is not archived."""
    p = os.path.join(ARCHIVE, symbol, f"{day}.csv")
    if not os.path.exists(p):
        return ()
    out = []
    with open(p) as fh:
        for r in csv.DictReader(fh):
            t = r["Datetime"][11:16]
            try:
                out.append((t, float(r["Open"]), float(r["High"]),
                            float(r["Low"]), float(r["Close"])))
            except (TypeError, ValueError):
                continue
    return tuple(out)


def window(symbol: str, day: str, lo: str, hi: str):
    """Bars with lo <= HH:MM < hi."""
    return [b for b in bars(symbol, day) if lo <= b[0] < hi]


@lru_cache(maxsize=64)
def sessions(symbol: str):
    d = os.path.join(ARCHIVE, symbol)
    if not os.path.isdir(d):
        return ()
    return tuple(sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv")))


def prior_days(symbol: str, day: str, n: int):
    """The n archived sessions immediately before `day`, oldest first."""
    s = sessions(symbol)
    try:
        i = s.index(day)
    except ValueError:
        return []
    return list(s[max(0, i - n):i])


# --------------------------------------------------------------- hindsight
def er_session(symbol: str, day: str):
    """THE NUMBER FROM THE FINDING. ER of 09:30-11:00 closes -- the whole chart
    Austin was shown, including every bar after the entry. Hindsight. Never
    tradeable. Reproduces t21_card_filter.features()['er_session']."""
    w = window(symbol, day, "09:30", "11:00")
    return er([b[4] for b in w])


# ------------------------------------------------------- causal, at 09:29
def er_pm(symbol: str, day: str, lo="04:00"):
    """ER of the premarket, `lo`-09:29. Known at 09:29."""
    w = window(symbol, day, lo, "09:30")
    return er([b[4] for b in w])


def er_prior_window(symbol: str, day: str):
    """ER of YESTERDAY's 09:30-11:00 -- the identical statistic, one day late.
    Known at 09:29."""
    p = prior_days(symbol, day, 1)
    if not p:
        return None
    return er_session(symbol, p[0])


def er_prior_n_window(symbol: str, day: str, n=5):
    """Mean of the prior n sessions' 09:30-11:00 ER. Known at 09:29."""
    vals = [er_session(symbol, d) for d in prior_days(symbol, day, n)]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def er_daily(symbol: str, day: str, n=10):
    """Kaufman ER on the DAILY chart: net move over the prior n RTH closes
    divided by the sum of the day-to-day moves. 'Is this stock trending at all',
    the swing-chart read. Known at 09:29."""
    closes = []
    for d in prior_days(symbol, day, n + 1):
        w = window(symbol, d, "09:30", "16:00")
        if w:
            closes.append(w[-1][4])
    return er(closes)


def gap_atr(symbol: str, day: str):
    """|today's 09:30 open - yesterday's RTH close| / yesterday's RTH range.
    Known at 09:30:00, i.e. before any 1m bar has closed."""
    p = prior_days(symbol, day, 1)
    w = window(symbol, day, "09:30", "11:00")
    if not p or not w:
        return None
    pw = window(symbol, p[0], "09:30", "16:00")
    if not pw:
        return None
    rng = max(b[2] for b in pw) - min(b[3] for b in pw)
    if rng <= 0:
        return None
    return abs(w[0][1] - pw[-1][4]) / rng


def er_prior_late(symbol: str, day: str):
    """ER of yesterday's LAST hour, 15:00-16:00 -- was the tape trending into
    the close. Known at 09:29."""
    p = prior_days(symbol, day, 1)
    if not p:
        return None
    return er([b[4] for b in window(symbol, p[0], "15:00", "16:00")])


# ------------------------------------- causal, but later than 09:29
def er_or(symbol: str, day: str, hi="09:45"):
    """ER of the opening range 09:30-`hi`. Known at `hi`, not at 09:29."""
    return er([b[4] for b in window(symbol, day, "09:30", hi)])


def er_to(symbol: str, day: str, et: str):
    """ER of 09:30 up to and including the bar `et`. Known at that minute --
    this is the strictly causal twin of er_session."""
    w = [b for b in bars(symbol, day) if "09:30" <= b[0] <= et]
    return er([b[4] for b in w])


CAUSAL_0929 = {
    "pm_er_full": lambda s, d, et: er_pm(s, d, "04:00"),
    "pm_er_0800": lambda s, d, et: er_pm(s, d, "08:00"),
    "pm_er_0900": lambda s, d, et: er_pm(s, d, "09:00"),
    "prior_day_window_er": lambda s, d, et: er_prior_window(s, d),
    "prior5_window_er": lambda s, d, et: er_prior_n_window(s, d, 5),
    "prior_late_er": lambda s, d, et: er_prior_late(s, d),
    "daily_er_10": lambda s, d, et: er_daily(s, d, 10),
    "daily_er_20": lambda s, d, et: er_daily(s, d, 20),
    "gap_over_prior_range": lambda s, d, et: gap_atr(s, d),
}
CAUSAL_LATER = {
    "or_er_0945": lambda s, d, et: er_or(s, d, "09:45"),
    "or_er_1000": lambda s, d, et: er_or(s, d, "10:00"),
    "er_up_to_entry": lambda s, d, et: er_to(s, d, et) if et else None,
}
HINDSIGHT = {"er_session_0930_1100": lambda s, d, et: er_session(s, d)}
