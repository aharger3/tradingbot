"""g77_realtrade_pick_test.py -- the guard fires on the deck that had the bug.

Does NOT rebuild any deck: rebuilding g71 would consume unjudged symbol-days and
overwrite a served manifest. It replays the two manifests that already exist
through the guard instead, and imports the patched builder to prove the wiring.

    python research/g77_realtrade_pick_test.py
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import g77_realtrade_pick as rp  # noqa: E402

G71 = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
G75 = os.path.join(HERE, "decks", "g75-deck2-manifest.jsonl")


def rows(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def main():
    ok = True

    g71 = rows(G71)
    try:
        rp.guard(g71, label="g71-homework-s3")
        print("FAIL  guard did not fire on the g71 deck (25 of 30 refusals)")
        ok = False
    except AssertionError as e:
        print("PASS  guard fires on the g71 deck: %s" % str(e).split("(")[0].strip())
    n_bad = rp.guard(g71, allow_untraded=True, label="g71")
    print("      --allow-untraded still builds it, and counts %d refusals of %d"
          % (n_bad, len(g71)))
    assert n_bad == 25, "expected 25 refused cards in the served g71 deck, got %d" % n_bad

    g75 = rows(G75)
    assert rp.guard(g75, label="g75-deck2") == 0
    print("PASS  guard passes the 39-card g75 deck (39 of 39 are booked trades)")

    # day_trade picks the day's first booked trade, and None when none was booked
    day = [{"et": "10:19", "traded": False}, {"et": "09:40", "traded": True},
           {"et": "10:22", "traded": True}]
    assert rp.day_trade(day)["et"] == "09:40"
    assert rp.day_trade([{"et": "09:40", "traded": False}]) is None
    print("PASS  day_trade takes the first booked trade, None when the engine refused")

    import g71_homework_build as hb  # noqa: F401
    assert hb.realtrade is rp
    print("PASS  g71_homework_build imports the guard")

    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
