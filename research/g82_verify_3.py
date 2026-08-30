"""g82_verify_3.py -- adversarial recompute of the G8.2 deck-selection claims.

Independent of research/g77_wrongchart_counterfactual.py. Everything here is
re-derived from two static files:

    research/decks/g71-homework-s3-manifest.jsonl  (the 30 cards Austin graded)
    research/bt2y_trades.json                      (the two-year book)

Read-only. Writes nothing, builds no deck, opens no mark file for writing.

Checks, in order:
  1. the 30 served cards split into traded / traded-something-else / silent
  2. book-wide: how often the engine's own FIRST booked trade is S-graded
  3. how many 84%-rule symbol-days have the engine's first trade as an S signal
  4. the no-repeat guarantee on a fresh 10-slate pick: intersect the picked
     card ids with build_deck.marked_card_ids() and with the served manifest
  5. the stated quota: does each bucket's traded count land on the target
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

BOOK = os.path.join(HERE, "bt2y_trades.json")
MANIFEST = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")

# The book spells the 84% rule "reentry_84_rule". Getting this key wrong makes
# two 84% cards compare equal as None==None, so compare raw setup strings below.
SETUP_OF = {"break_and_retest": "BR", "one_candle_rule": "OCR",
            "reentry_84_rule": "84"}


def first_booked(rows):
    """The engine's own first booked trade of that session, or None."""
    b = [r for r in rows if r.get("traded")]
    if not b:
        return None
    return min(b, key=lambda r: r.get("et") or "99:99")


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    by_day = defaultdict(list)
    for r in book["trades"]:
        by_day[(r["sym"], r["day"])].append(r)
    print("book: %d rows, %d symbol-days" % (len(book["trades"]), len(by_day)))

    # ---- 1. the 30 served cards
    cards = [json.loads(l) for l in open(MANIFEST, encoding="utf-8") if l.strip()]
    split = Counter()
    detail = []
    for c in cards:
        rows = by_day[(c["symbol"], c["date"])]
        real = first_booked(rows)
        if real is None:
            k = "silent-refusal"
        elif real.get("et") == c.get("et") and \
                SETUP_OF.get(real.get("setup")) == SETUP_OF.get(c.get("engine_setup")):
            k = "traded"
        else:
            k = "traded-something-else"
        split[k] += 1
        detail.append((c["symbol"], c["date"], k, c.get("traded"),
                       c.get("et"), real.get("et") if real else None))
    print("\n1. the 30 cards Austin already graded:")
    for k in ("traded", "traded-something-else", "silent-refusal"):
        print("   %-22s %2d" % (k, split[k]))
    print("   total                  %2d" % sum(split.values()))
    # cross-check against the card's own `traded` flag
    flag = Counter(bool(c.get("traded")) for c in cards)
    print("   manifest `traded` flag: True %d / False %d"
          % (flag[True], flag[False]))

    # ---- 2. book-wide: is the engine's own first trade S-graded?
    firsts = [first_booked(rows) for rows in by_day.values()]
    firsts = [f for f in firsts if f is not None]
    n_s = sum(1 for f in firsts if f.get("sgrade") == "S")
    n_not = len(firsts) - n_s
    print("\n2. book-wide first booked trade of each traded session:")
    print("   sessions the engine traded at all: %d" % len(firsts))
    print("   first trade IS S-graded:           %d" % n_s)
    print("   first trade is NOT S-graded:       %d  (%.1f%%)"
          % (n_not, 100.0 * n_not / len(firsts)))

    # ---- 3. per-bucket traded candidates (first trade is an S of that setup)
    print("\n3. traded-role raw candidates per bucket (first booked trade is S):")
    per_bucket = Counter()
    for rows in by_day.values():
        f = first_booked(rows)
        if f is None or f.get("sgrade") != "S":
            continue
        b = SETUP_OF.get(f.get("setup"))
        if b:
            per_bucket[b] += 1
    for b in ("84", "OCR", "BR"):
        print("   %-3s %d" % (b, per_bucket[b]))

    # ---- 4/5. a fresh pick, no-repeat + quota
    import build_deck as bd
    import g71_homework_build as hb
    print("\n4. fresh 10-slate pick (dry run, nothing written):")
    slates, seen, stats, census, _lv = hb.pick(10, 71)
    picked = [c for row in slates for c in row]
    ids = {"%s_%s" % (c["symbol"], c["day"]) for c in picked}
    judged = bd.marked_card_ids()
    served = bd.served_card_ids(MANIFEST)
    print("   picked %d cards, %d distinct symbol-days" % (len(picked), len(ids)))
    print("   judged corpus: %d symbol-days; served-in-manifest: %d"
          % (len(judged), len(served)))
    print("   INTERSECTION with judged corpus:   %d  %s"
          % (len(ids & judged), sorted(ids & judged)[:10]))
    print("   INTERSECTION with served manifest: %d  %s"
          % (len(ids & served), sorted(ids & served)[:10]))

    print("\n5. quota per bucket (stated frac %.2f):" % hb.TRADED_QUOTA_FRAC)
    bad = 0
    for b in hb.BUCKETS:
        s = stats[b]
        got = s["role_counts"].get("traded", 0)
        tgt = s["target_traded"]
        over = got > tgt
        bad += over
        print("   %-3s traded %d / target %d / total picked %d%s"
              % (b, got, tgt, sum(s["role_counts"].values()),
                 "   ** OVER QUOTA **" if over else ""))

    # role truth, re-derived
    wrong = [c for c in picked
             if (c["role"] == "traded") != (first_booked(by_day[(c["symbol"], c["day"])]) is not None
                                            and first_booked(by_day[(c["symbol"], c["day"])]).get("et") == c["rep"].get("et"))]
    print("\n6. role re-derived independently: %d card(s) whose role is wrong" % len(wrong))
    for c in wrong[:5]:
        print("   %s %s role=%s" % (c["symbol"], c["day"], c["role"]))

    fail = bool(ids & judged) or bool(ids & served) or bad or wrong
    print("\nVERDICT: %s" % ("PROBLEM FOUND" if fail else "all checks clean"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
