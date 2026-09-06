"""v3_referee_pass2b.py -- the two sensitivities pass 2 adds to row V3.

(1) X-only cells in the precision DENOMINATOR. `marks_pool` folds X into the
    "none" bucket while its own docstring calls X "a refusal AIMED AT THE
    ENGINE ... not a day-level grade", and CLAUDE.md says outright "X is not a
    grade". g215 nonetheless counts X-only symbol-days as graded-not-S. How
    much of the headline is that choice?

(2) The recall DENOMINATOR (347 bar-backed S days) is not scoped to the book.
    An S day outside the book's session window, or on a symbol the book never
    covers, is a day the engine could not have fired on at any setting. How
    many of the 347 are reachable?

    python research/v3_referee_pass2b.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import v3_referee_pass2 as rf  # noqa: E402  my own pass-2 code, not the builder's


def main():
    rows, meta = rf.load_book(rf.BOOK)
    sessions = meta.get("sessions") or len({r["day"] for r in rows})
    pool = rf.build_pool(use_ninth=True)
    s_all = {k for k, v in pool.items() if v["grade"] == "S"}
    bar_s = {k for k in s_all if pool[k]["has_bars"]}

    u1 = rf.unit1_keys(rows)
    u2 = rf.unit2_keys(rows)

    def x_only(k):
        return set(pool[k]["raw"]) == {"X"}

    print("=== (1) X-only cells in the precision denominator ===")
    for keys, label in ((u1, "unit1 one-a-day"), (u2, "unit2 all-fires")):
        graded = [k for k in keys if k in pool]
        xo = [k for k in graded if x_only(k)]
        s = sum(1 for k in graded if pool[k]["grade"] == "S")
        keep = rf.cell(s, len(graded))
        drop = rf.cell(s, len(graded) - len(xo))
        print("  %-16s X-only=%-4d  as published %s   X-only dropped %s"
              % (label, len(xo), keep, drop))

    print("\n=== (2) is the 347-day recall denominator reachable? ===")
    book_days = {r["day"] for r in rows}
    book_syms = {r["sym"] for r in rows}
    lo, hi = min(book_days), max(book_days)
    in_window = {k for k in bar_s if lo <= k.split("_", 1)[1] <= hi}
    in_univ = {k for k in bar_s if k.split("_", 1)[0] in book_syms}
    reach = {k for k in bar_s
             if k.split("_", 1)[0] in book_syms and k.split("_", 1)[1] in book_days}
    print("  bar-backed S days                     : %d" % len(bar_s))
    print("  ... inside the book window %s..%s : %d" % (lo, hi, len(in_window)))
    print("  ... on a symbol the book covers (%d)  : %d" % (len(book_syms), len(in_univ)))
    print("  ... on a session the book actually has: %d  <- reachable denominator"
          % len(reach))
    u2set = set(u2)
    print("  recall as published : %s" % rf.cell(len(bar_s & u2set), len(bar_s)))
    print("  recall, reachable   : %s" % rf.cell(len(reach & u2set), len(reach)))
    u1set = set(u1)
    print("  unit1 recall published: %s" % rf.cell(len(bar_s & u1set), len(bar_s)))
    print("  unit1 recall reachable: %s" % rf.cell(len(reach & u1set), len(reach)))
    print("  (sessions in book: %d)" % sessions)


if __name__ == "__main__":
    main()
