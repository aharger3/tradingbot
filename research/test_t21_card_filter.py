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

    print("\n-- reachability at the SHIPPED config (method rule 3)")
    # Three of the four checks are OFF at the shipped thresholds and that is a
    # measured decision, not an oversight: each of them buys a point or two of
    # lift by throwing away Austin's S days (see --tradeoff). They are pinned
    # here as off so nobody "fixes" a branch that was switched off on purpose,
    # and so nobody tunes a threshold that cannot fire.
    trips = {c: sum(1 for r in rows if c in F.verdict(r["_f"], F.DEFAULT, (c,))[1])
             for c in F.ALL_CHECKS}
    for c in ("window", "chop", "displacement"):
        check("%s is OFF at the shipped config (0 trips, deliberate)" % c,
              trips[c] == 0, "%d trips" % trips[c])
    check("reach is the only live check, and is reachable (1%-85%)",
          0.01 <= trips["reach"] / len(rows) <= 0.85,
          "%d/90 = %.1f%%" % (trips["reach"], 100 * trips["reach"] / len(rows)))
    # ...but each switched-off check must still WORK, or the switch is a lie.
    loud = dict(F.DEFAULT, min_er_session=0.05, min_impulse_atr=1.2)
    for c, want in (("chop", 19), ("displacement", 15)):
        n = sum(1 for r in rows if c in F.verdict(r["_f"], loud, (c,))[1])
        check("%s still fires when switched on (%d trips)" % (c, want), n == want,
              "%d trips" % n)

    print("\n-- published numbers (research/t21_card-selection.md)")
    s = F.score(rows, F.DEFAULT)
    check("63 of 90 cards pass", s["tp"] + s["fp"] == 63, str(s["tp"] + s["fp"]))
    check("23 of his 26 graded cards survive (88.5% recall)", s["tp"] == 23, str(s["tp"]))
    check("40 of his 64 refusals slip through", s["fp"] == 40, str(s["fp"]))
    d, lo, hi = F.newcombe_diff(s["tp"], s["tp"] + s["fp"], s["fn"], s["tn"] + s["fn"])
    check("effect +25.4 points, 95% CI excludes zero",
          abs(100 * d - 25.4) < 0.15 and lo > 0,
          "%+.1f pts [%+.1f, %+.1f]" % (100 * d, 100 * lo, 100 * hi))
    p = F.fisher_exact(s["tp"], s["fp"], s["fn"], s["tn"])
    check("Fisher exact p = 0.0211", abs(p - 0.0211) < 0.0005, "p=%.6f" % p)

    held = [r for r in rows if r["lane"] in ("rare", "index")]
    h = F.score(held, F.DEFAULT)
    check("held-out lanes: every graded card survives (3/3)",
          h["tp"] == 3 and h["fn"] == 0, "tp=%d fn=%d" % (h["tp"], h["fn"]))
    hd, hlo, hhi = F.newcombe_diff(h["tp"], h["tp"] + h["fp"], h["fn"], h["tn"] + h["fn"])
    check("held-out lift is NULL and the report says so",
          hlo <= 0 <= hhi, "%+.1f pts [%+.1f, %+.1f]" % (100 * hd, 100 * hlo, 100 * hhi))

    print("\n-- a whole-session card passes untouched")
    # The silent half of a mixed deck has no proposed entry. Filtering it on
    # chop alone is NULL on the 100-card S sweep (+3.6 pts, p=0.82) and throws
    # away 9 of his 34 S days. Pure cost -- so those cards pass through.
    check("FILTER_SESSION_CARDS is off", F.FILTER_SESSION_CARDS is False)
    sil = F.features("SPY", "2024-12-16", None)
    check("session card carries entry_anchored=False",
          sil is not None and sil["entry_anchored"] is False)
    check("session card passes unconditionally",
          F.verdict(sil, F.DEFAULT) == (True, []), str(F.verdict(sil, F.DEFAULT)))
    check("the rejected arm still works when switched on",
          F.verdict(dict(sil, er_session=0.0),
                    dict(F.DEFAULT, min_er_session=0.05),
                    filter_session=True)[1] == ["chop"])

    print("\n-- the spec's three dead criteria stay documented as dead")
    ent = [r for r in rows if r["_f"]["entry_anchored"]]
    P = [r for r in ent if r["keep"]]
    N = [r for r in ent if not r["keep"]]
    for label, fn in (("nearest-level distance", lambda f: -f["level_dist_atr"]),
                      ("RR to the nearest level", lambda f: f["rr_near"])):
        a = F._auc([fn(r["_f"]) for r in P], [fn(r["_f"]) for r in N])
        check("%s is still at chance (AUC within 0.06 of 0.5)" % label,
              abs(a - 0.5) < 0.06, "AUC %.3f" % a)

    print("\n-- the governing cost: his held-out S days (method rule 2)")
    # probe_s_sweep_2026-08-28.jsonl shares no card with probe_master and was
    # never fitted on. Those cards are the ones a filtered fire-half deck has to
    # keep: a config that cuts refusals by throwing away his S days is not an
    # improvement.
    #
    # THE DENOMINATOR MOVES WITH THE ENGINE. T21 measured 18 of 34 on the T0
    # engine; T23 shipped X_LIFT=clean and the engine now fires on 23 of the 34
    # (that is the whole point of the lever). This test pins the RATIO the
    # filter has to hold, not the engine's recall -- research/t23_stack.md owns
    # that number and t23_heldout.json is where it is measured.
    sdays = F.s_day_engine_cards()
    check("the engine fires on at least 18 of his 34 held-out S days",
          len(sdays) >= 18, "%d/34" % len(sdays))
    kept = sum(1 for r in sdays if F.verdict(r["_f"], F.DEFAULT)[0])
    check("shipped config keeps >=90% of them",
          kept >= 0.90 * len(sdays), "%d/%d = %.1f%%"
          % (kept, len(sdays), 100 * kept / len(sdays)))
    four = {"late_window": "11:00", "min_er_session": 0.05,
            "max_reach_r": 8.0, "min_impulse_atr": 1.2}
    k4 = sum(1 for r in sdays if F.verdict(r["_f"], four)[0])
    check("the rejected four-check fit keeps materially fewer -- why it is not shipped",
          k4 < 0.90 * len(sdays), "%d/%d" % (k4, len(sdays)))

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
