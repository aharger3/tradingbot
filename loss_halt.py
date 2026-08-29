"""R31 — the two-consecutive-loss halt, in BOTH paths.

Austin, `research/marks/probe_master_2026-08-29.jsonl`, verdict `both`:
the loss halt belongs in the backtest AND in the live path. T0 landed 27 of the
33 ratified answers and did not land this one; T23 lands it.

THE RULE
--------
Inside one trading DAY, once **two trades in a row have closed at a loss**, no
new entry is taken for the rest of that day. Open positions keep managing —
this stops new risk, it does not flatten the book. A win or a scratch resets the
counter to zero.

The halt is **account-wide**, not per-symbol. That is the whole point of it: two
losses in a row is a statement about the trader, not about NVDA.

CAUSAL, NOT THE POST-PROCESS APPROXIMATION
------------------------------------------
`research/t20_loss_halt_postprocess.py` measured this rule by sorting a day's
rows by ENTRY time and incrementing the counter with each row's eventual
outcome. That is one bar of look-ahead: at the moment you would place trade #3
you do not yet know that trade #2 is going to lose — you only know it once it
has closed.

This module counts on the **exit**. A candidate entry at bar `i` is blocked only
by losses that had already CLOSED at or before bar `i`. So the rule can be
placed by a human in real time, and the live path and the backtest run the same
rule. The two readings do not have to agree, and where they differ this one is
the one that could have been traded.

A blocked trade never happened, so it never contributes to the loss streak
either — the sequence is rebuilt as the day is walked, not read off the
unhalted book.

Standing note (T22): the halt fires on roughly half of all trading days and
removes about a third of the book, which collides with R20 — *"quality over
quantity, but he wants to trade every day."* Both sentences are his. The
collision is `austin_blockers` item 7 in `research/t22_adjudication.md`; the
rule ships at his ratified answer until he names a different trigger.
"""
from __future__ import annotations

import os

# R31. Two in a row, and the day is done.
HALT_AFTER_CONSECUTIVE_LOSSES = int(os.getenv("LOSS_HALT_N", "2"))

# Ships ON — R31 is ratified and ships at his answer (method rule 4).
# LOSS_HALT=0 restores the pre-T23 book for a leave-one-out arm.
LOSS_HALT = os.getenv("LOSS_HALT", "1").strip().lower() not in ("0", "false", "off", "no")


def halt_day(rows, entry_key, exit_key, loss_key, n=None):
    """Walk one day's traded rows in entry order and return the blocked ones.

    ``rows``      — the day's TRADED rows, any order.
    ``entry_key`` — row -> a sortable moment the entry is placed.
    ``exit_key``  — row -> the same scale, the moment the trade closes.
    ``loss_key``  — row -> True if the trade closed at a loss.

    Returns the subset of ``rows`` that the halt blocks, as a list. A row is
    blocked when, at its own entry moment, at least ``n`` already-closed trades
    that were themselves TAKEN have lost in an unbroken run.
    """
    if n is None:
        n = HALT_AFTER_CONSECUTIVE_LOSSES
    if n <= 0:
        return []

    taken = sorted(rows, key=entry_key)
    blocked, pending, streak = [], [], 0
    # `pending` holds trades that are taken and still open, as (exit, is_loss),
    # kept sorted so the counter can be advanced to any entry moment.
    for row in taken:
        at = entry_key(row)
        while pending and pending[0][0] <= at:
            _x, lost = pending.pop(0)
            streak = streak + 1 if lost else 0
        if streak >= n:
            blocked.append(row)
            continue                       # a blocked trade never happened
        pending.append((exit_key(row), bool(loss_key(row))))
        pending.sort(key=lambda p: p[0])
    return blocked


def apply_to_book(rows, *, day_key=lambda r: r["day"]):
    """Mark a whole two-year book in place. Returns the number blocked.

    Operates on `backtest_2y.py` row dicts: a blocked row keeps every measured
    field (so the report can still show what it would have done) but is flipped
    to ``traded=False``, ``status="halted"`` and tagged in ``reason``, which is
    what every downstream stat filters on.
    """
    if not LOSS_HALT:
        return 0
    by_day = {}
    for r in rows:
        if r.get("status") == "fired" and r.get("traded"):
            by_day.setdefault(day_key(r), []).append(r)

    n = 0
    for day_rows in by_day.values():
        for r in halt_day(day_rows,
                          entry_key=lambda x: (x.get("entry_i", 0), x.get("et", ""), x.get("sym", "")),
                          exit_key=lambda x: (x.get("entry_i", 0) + x.get("bars", 0),
                                              x.get("et", ""), x.get("sym", "")),
                          loss_key=lambda x: x.get("out") == "loss"):
            r["traded"] = False
            r["status"] = "halted"
            r["halted"] = True
            r["reason"] = (r.get("reason", "") + " [halt: %d consecutive losses]"
                           % HALT_AFTER_CONSECUTIVE_LOSSES).strip()
            n += 1
    return n
