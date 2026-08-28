"""The no-repeat guarantee, as a check that fails if it regresses.

Every hole found in _judgement_key() gets a row here. The guarantee is the only
thing standing between Austin and re-grading a day he already judged, and it has
now failed three times in three different ways.

    python research/test_no_repeat_guarantee.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from build_deck import (_judgement_key, marked_card_ids,  # noqa: E402
                        seen_card_ids, served_card_ids)

# (row, expected key or None, what broke when this was missing)
CASES = [
    ({"symbol": "TSLA", "day": "2024-01-08", "tier": "A"}, "TSLA_2024-01-08",
     "plain graded row"),
    ({"symbol": "BABA", "day": "2024-12-12", "_no_trade": True}, "BABA_2024-12-12",
     "_no_trade is a judgement -- 143 rows were invisible until 2026-08-28"),
    ({"card_id": "cal_QQQ_2026-06-29_b10", "grade": "S"}, "QQQ_2026-06-29",
     "prefixed card_id parsed to garbage (OMEN Test 1)"),
    ({"card_id": "sr_NVDA_2025-04-10", "grade": None,
      "answers": {"s_call": "s"}}, "NVDA_2025-04-10",
     "a probe answer is a judgement even with grade=None"),
    ({"symbol": "MSFT", "day": "2025-12-30", "grade": "none"}, "MSFT_2025-12-30",
     'grade "none" is an explicit refusal, not a blank'),
    ({"symbol": "AMD", "day": "2025-01-28"}, None,
     "no grade, no answers, no refusal -> not a judgement"),
    ({"symbol": "AMD", "day": "2025-01-28", "answers": {}}, None,
     "an empty answers dict is not an answer"),
]

fails = 0
for row, want, why in CASES:
    got = _judgement_key(row)
    ok = got == want
    fails += not ok
    print("%-4s %-22s %s" % ("ok" if ok else "FAIL", got, why))
    if not ok:
        print("       expected %r, got %r for %r" % (want, got, row))

# The pool must never shrink. 959 is the count after the _no_trade fix.
pool = marked_card_ids()
FLOOR = 959
if len(pool) < FLOOR:
    print("FAIL exclusion pool shrank: %d < %d -- a corpus stopped being read"
          % (len(pool), FLOOR))
    fails += 1
else:
    print("ok   exclusion pool %d symbol-days (floor %d)" % (len(pool), FLOOR))

# Being served a card spends his attention even when he never graded it. 499
# symbol-days were served and never exported back, and all of them were eligible
# for a new deck until 2026-08-28.
SERVED_FLOOR, SEEN_FLOOR = 724, 1458
served, seen = served_card_ids(), seen_card_ids()
for name, got, floor in (("served", len(served), SERVED_FLOOR),
                         ("seen (judged|served)", len(seen), SEEN_FLOOR)):
    if got < floor:
        print("FAIL %s pool shrank: %d < %d" % (name, got, floor))
        fails += 1
    else:
        print("ok   %s pool %d (floor %d)" % (name, got, floor))

# A rebuild must not read the manifest it is about to overwrite, or the pool
# empties and the deck comes out with nothing in it.
_own = os.path.join(HERE, "decks", "omen-s-accuracy-100-manifest.jsonl")
if os.path.exists(_own):
    if len(seen_card_ids(_own)) >= len(seen):
        print("FAIL a deck does not exclude its own manifest -- rebuilds self-block")
        fails += 1
    else:
        print("ok   a deck excludes its own manifest (%d -> %d)"
              % (len(seen), len(seen_card_ids(_own))))

if not seen >= pool:
    print("FAIL seen_card_ids() does not contain every judged day")
    fails += 1
else:
    print("ok   seen_card_ids() is a superset of marked_card_ids()")

print()
print("FAILED %d" % fails if fails else "all %d checks pass" % (len(CASES) + 5))
sys.exit(1 if fails else 0)
