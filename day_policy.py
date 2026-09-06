"""L5 (2026-09-05) -- the day policy Austin ratified on the 09-05 call:
"up to 3 S fires a day; stop after a win or after 2 losses"
(`CLAUDE.md`'s THE LANE section; `omen-rulebook.md`'s 2026-09-05 decided
answer). This module enforces it CAUSALLY on a built two-year book, the
same way `loss_halt.py` enforces R31's two-consecutive-loss halt -- and
for the same reason loss_halt.py gives for rejecting the naive approach
(its own docstring: "you do not yet know that trade #2 is going to lose
-- you only know it once it has closed").

WHY THIS IS NOT THE SAME NUMBER `research/loop_cycle.py::up_to_3_rows`
ALREADY COMPUTES. That function is the loop's MEASUREMENT lens: given a
book, sort a day's taken rows by entry time (`et`) and immediately read
each one's own final `pnl` to decide whether the day continues. That
commits exactly the one-bar-of-look-ahead loss_halt.py's docstring
describes: if two signals both enter before either has closed (two
different symbols, overlapping intraday), a live trader would not yet
know signal #1 was a winner at the moment #2 is entered, so #2 should
still count as a live, in-flight pick, not be discarded because #1
"already" won by the time the book is read back top to bottom. This
module answers the causal version of the question: walk entries in
ENTRY order, only credit a stop condition once the relevant trade has
actually CLOSED, and mark every entry the real day policy would never
have reached.

WHAT THIS DOES NOT TOUCH. Signal generation, `DEDUPE_FIRES_ONLY`'s
suppression windows, and grading are unchanged -- this is a pure
post-build pass over a already-simulated book's fired+traded rows,
exactly the shape `loss_halt.apply_to_book` already ships in this file's
sibling. A row this blocks keeps every measured field (so a report can
still show what it would have done) and is flipped to `traded=False`,
`status="day_policy_halt"` -- a status this module OWNS, distinct from
`loss_halt.py`'s `"halted"`, so `backtest_2y.py`'s own halt count and
this one never get confused for each other.

OFF unless `signal_runner.DAY_POLICY == "3fires_stop_win_or_2loss"` (default
stays `"first3"`, unchanged -- L5 lands this OFF). `apply_to_book` is the
one call site, invoked from `backtest_2y.py` right after
`loss_halt.apply_to_book(rows)`, same pattern, same place.
"""
from __future__ import annotations

import signal_runner

MAX_FIRES = 3
LOSS_STOP = 2


def day_policy_day(rows, entry_key, exit_key, is_win_key, is_loss_key):
    """Walk one day's TAKEN candidate rows (any order) and return the ones
    the day policy would have blocked, causally: a candidate is blocked
    only once an already-CLOSED taken trade has shown a win, or two
    already-closed taken trades have lost, or three trades are already
    taken outright (that check needs no closure -- a 4th entry is blocked
    the instant it would be a 4th, whether or not #1-3 have closed)."""
    taken_sorted = sorted(rows, key=entry_key)
    blocked, pending = [], []
    taken = wins_closed = losses_closed = 0
    for row in taken_sorted:
        at = entry_key(row)
        while pending and pending[0][0] <= at:
            _exit_at, is_win, is_loss = pending.pop(0)
            if is_win:
                wins_closed += 1
            if is_loss:
                losses_closed += 1
        if wins_closed >= 1 or losses_closed >= LOSS_STOP or taken >= MAX_FIRES:
            blocked.append(row)
            continue                       # a blocked trade never happened
        taken += 1
        pending.append((exit_key(row), bool(is_win_key(row)), bool(is_loss_key(row))))
        pending.sort(key=lambda p: p[0])
    return blocked


def apply_to_book(rows, *, day_key=lambda r: r["day"]):
    """Mark a whole two-year book in place. Returns the number blocked.

    No-op unless `signal_runner.DAY_POLICY == "3fires_stop_win_or_2loss"`.
    Operates on `backtest_2y.py` row dicts, same contract as
    `loss_halt.apply_to_book`.
    """
    if signal_runner.DAY_POLICY != "3fires_stop_win_or_2loss":
        return 0

    by_day = {}
    for r in rows:
        if r.get("status") == "fired" and r.get("traded"):
            by_day.setdefault(day_key(r), []).append(r)

    n = 0
    for day_rows in by_day.values():
        for r in day_policy_day(
                day_rows,
                entry_key=lambda x: (x.get("entry_i", 0), x.get("et", ""), x.get("sym", "")),
                exit_key=lambda x: (x.get("entry_i", 0) + x.get("bars", 0),
                                     x.get("et", ""), x.get("sym", "")),
                is_win_key=lambda x: x.get("out") == "win",
                is_loss_key=lambda x: x.get("out") == "loss"):
            r["traded"] = False
            r["status"] = "day_policy_halt"
            r["day_policy_halt"] = True
            r["reason"] = (r.get("reason", "")
                           + " [day policy: stop after win or 2 losses]").strip()
            n += 1
    return n
