"""test_t21_card_filter.py -- the T21 card pre-filter, pinned.

Austin: "you know better not to give me old trades that don't fit my system."
This file exists so that sentence stays enforced. It asserts three things:

  1. His 90 verdicts still read the way T21 read them (26 graded / 64 refused).
     If someone re-interprets the lanes, this fails loudly rather than silently
     re-scoring the filter against a different label set.
  2. The filter's published numbers still reproduce.
  3. research/build_deck.py ACTUALLY applies it -- a deck built through pick()
     contains no card the filter would drop. This is the wiring assertion; the
     filter is worthless if the deck generator forgets to call it.

    python research/test_t21_card_filter.py

Never writes a mark file.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t21_card_filter as F  # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  -- " + detail) if detail else ""))
    if not cond:
        FAILED.append(name)


def main():
    rows = F.load_labels()
    for r in rows:
        r["_f"] = F.features(r["symbol"], r["day"], r["et"])

    print("\n-- his label set, probe_master_2026-08-29.jsonl (READ ONLY)")
    check("90 card verdicts in the four card lanes", len(rows) == 90, str(len(rows)))
    check("all 90 have archive bars",
          all(r["_f"] is not None for r in rows),
          str([r["card_id"] for r in rows if r["_f"] is None]))
    keep = sum(r["keep"] for r in rows)
    check("26 graded / 64 refused", (keep, len(rows) - keep) == (26, 64),
          "%d / %d" % (keep, len(rows) - keep))
    per = {}
    for r in rows:
        per.setdefault(r["lane"], [0, 0])[0 if r["keep"] else 1] += 1
    check("vetoes 13 keep / 27 reject", per["vetoes"] == [13, 27], str(per["vetoes"]))
    check("runner 10 keep /  5 reject", per["runner"] == [10, 5], str(per["runner"]))
    check("rare    0 keep / 20 reject", per["rare"] == [0, 20], str(per["rare"]))
    check("index   3 keep / 12 reject", per["index"] == [3, 12], str(per["index"]))

    print("\n-- reachability of every check (method rule 3)")
    # The window check is DEAD on engine-proposed cards by construction: the
    # engine's own 11:00 entry cutoff already enforces it. It is kept as a
    # structural assertion for hand-added cards, and pinned here as dead so
    # nobody re-tunes a threshold that cannot fire.
    trips = {c: sum(1 for r in rows if c in F.verdict(r["_f"], F.DEFAULT, (c,))[1])
             for c in F.ALL_CHECKS}
    check("window trips 0/90 -- DEAD by construction, not a tunable",
          trips["window"] == 0, str(trips["window"]))
    for c in ("chop", "reach", "displacement"):
        check("%s is reachable and not saturated (1%%-85%%)" % c,
              0.01 <= trips[c] / len(rows) <= 0.85,
              "%d/90 = %.1f%%" % (trips[c], 100 * trips[c] / len(rows)))

    print("\n-- published numbers (research/t21_card-selection.md)")
    s = F.score(rows, F.DEFAULT)
    check("38 of 90 cards pass", s["tp"] + s["fp"] == 38, str(s["tp"] + s["fp"]))
    check("20 of his 26 graded cards survive (76.9% recall)", s["tp"] == 20, str(s["tp"]))
    check("18 of his 64 refusals slip through", s["fp"] == 18, str(s["fp"]))
    d, lo, hi = F.newcombe_diff(s["tp"], s["tp"] + s["fp"], s["fn"], s["tn"] + s["fn"])
    check("effect +41.1 points, 95%% CI excludes zero",
          abs(100 * d - 41.1) < 0.15 and lo > 0,
          "%+.1f pts [%+.1f, %+.1f]" % (100 * d, 100 * lo, 100 * hi))
    p = F.fisher_exact(s["tp"], s["fp"], s["fn"], s["tn"])
    check("Fisher exact p < 0.001", p < 0.001, "p=%.6f" % p)

    held = [r for r in rows if r["lane"] in ("rare", "index")]
    h = F.score(held, F.DEFAULT)
    check("held-out lanes: every graded card survives (3/3)",
          h["tp"] == 3 and h["fn"] == 0, "tp=%d fn=%d" % (h["tp"], h["fn"]))
    check("held-out lanes: 21 of 32 refusals dropped", h["tn"] == 21, str(h["tn"]))

    print("\n-- a whole-session card is judged on chop alone")
    # The silent half of a mixed deck has no proposed entry. If the
    # entry-anchored checks were applied to it, every silent day would be
    # dropped and the deck would lose its recall half entirely.
    sil = F.features("SPY", "2024-12-16", None)
    check("session card carries entry_anchored=False",
          sil is not None and sil["entry_anchored"] is False)
    check("session card is judged on chop only",
          F.verdict(sil, F.DEFAULT)[1] in ([], ["chop"]),
          str(F.verdict(sil, F.DEFAULT)[1]))

    print("\n-- the spec's three dead criteria stay documented as dead")
    ent = [r for r in rows if r["_f"]["entry_anchored"]]
    P = [r for r in ent if r["keep"]]
    N = [r for r in ent if not r["keep"]]
    for label, fn in (("nearest-level distance", lambda f: -f["level_dist_atr"]),
                      ("RR to the nearest level", lambda f: f["rr_near"])):
        a = F._auc([fn(r["_f"]) for r in P], [fn(r["_f"]) for r in N])
        check("%s is still at chance (AUC within 0.06 of 0.5)" % label,
              abs(a - 0.5) < 0.06, "AUC %.3f" % a)

    print("\n-- build_deck.pick() actually applies the filter")
    import build_deck
    check("build_deck imports the filter",
          getattr(build_deck, "card_filter", None) is F)
    cards, nfire, nsilent, probed, _seen = build_deck.pick(
        4, seed=21, max_probe=30, prefilter=True)
    check("pick() returned cards", len(cards) > 0, "%d cards" % len(cards))
    bad = []
    for c in cards:
        et = c.get("prefilter", {}).get("et") if c.get("prefilter") else None
        if not F.card_ok(c["symbol"], c["day"], et):
            bad.append("%s_%s" % (c["symbol"], c["day"]))
    check("every card in the deck passes the filter", not bad, str(bad))
    check("every card records why it passed",
          all(c.get("prefilter") is not None for c in cards))

    print("\n%s  (%d checks failed)"
          % ("ALL GREEN" if not FAILED else "RED: " + ", ".join(FAILED), len(FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
