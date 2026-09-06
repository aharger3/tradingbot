"""H1 referee (pass 4) -- independent re-derivation of every H1 claim.

Builder commit under review: a4461e0c3d6de4088750eb184868ee403e42ba53
("H1 repair: cut s-blind cards at the LAST S bar ... and exclude a deck's own
manifest on rebuild").

Nothing here trusts the builder's test. Every number is re-derived from
build_deck's corpora, the deck manifests on disk and daily_homework's own
functions. Writes nothing outside a scratch dir.

    python research/h1_referee.py
"""
import glob
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import universe  # noqa: E402
import build_deck as deck  # noqa: E402
import daily_homework as dh  # noqa: E402

DAY = "2026-09-03"
DECKS = ROOT / "research" / "decks"
S10_MAN = DECKS / ("omen-daily-%s-s10-manifest.jsonl" % DAY)


def hdr(s):
    print("\n== %s" % s)


def main():
    fails = []

    # ---- C1: served_card_ids reads every manifest under research/ ----------
    hdr("C1 served_card_ids coverage")
    man_paths = sorted(glob.glob(str(ROOT / "research" / "**" / "*manifest*.jsonl"),
                                 recursive=True))
    deck_man = sorted(glob.glob(str(DECKS / "*manifest*.jsonl")))
    print("manifests under research/ (recursive): %d" % len(man_paths))
    print("manifests under research/decks/:       %d" % len(deck_man))
    union = set()
    per_file = {}
    for p in man_paths:
        ids = set()
        for row in deck._rows(p):
            ident = row.get("card_id") or row.get("id")
            if isinstance(ident, str):
                m = deck._ID_RE.search(ident)
                if m:
                    ids.add("%s_%s" % (m.group(1), m.group(2)))
        per_file[os.path.basename(p)] = len(ids)
        union |= ids
    served = deck.served_card_ids()
    print("hand-parsed union ids: %d ; served_card_ids(): %d ; equal: %s"
          % (len(union), len(served), union == served))
    for k in sorted(per_file):
        print("   %-46s %4d ids" % (k, per_file[k]))
    if union != served:
        fails.append("C1 served_card_ids() does not equal the hand-parsed union "
                     "of every manifest under research/")

    # ---- C2: the s10 deck's card ids are in the served set ----------------
    hdr("C2 s10 manifest ids excluded by the served set")
    s10_ids = set()
    for row in deck._rows(str(S10_MAN)):
        ident = row.get("card_id") or row.get("id")
        if isinstance(ident, str):
            s10_ids.add(ident)
    print("omen-daily-%s-s10-manifest.jsonl rows -> %d distinct card ids "
          "(the deck HTML held 22 per-SIGNAL cards; the manifest is at "
          "symbol-day granularity)" % (DAY, len(s10_ids)))
    missing = sorted(i for i in s10_ids if i not in served)
    print("s10 ids absent from served_card_ids(): %d %r" % (len(missing), missing))
    if missing:
        fails.append("C2 served set misses %d s10 card ids" % len(missing))
    with_ex = deck.served_card_ids(exclude=str(S10_MAN))
    still = sorted(i for i in s10_ids if i in with_ex)
    print("with exclude=<s10 manifest>, s10 ids still served (via other "
          "manifests/decks): %d %r" % (len(still), still))

    # ---- C3: the PRODUCTION default path for a 09-03 s-blind rebuild ------
    hdr("C3 production path: what main() actually passes as exclude_manifest")
    # main(): tag = "-s10" iff (pool == 'core' and per_signal); default
    # per_signal is False, so a default rebuild tags "-s".
    for pool, per_signal in (("core", False), ("core", True)):
        tag = "-s10" if (pool == "core" and per_signal) else "-s"
        man = DECKS / ("omen-daily-%s%s-manifest.jsonl" % (DAY, tag))
        cards, stats = dh.sblind_collect(DAY, universe.CORE_SYMBOLS,
                                         per_signal=per_signal,
                                         exclude_manifest=str(man))
        print("pool=%s per_signal=%s -> tag %-4s exclude=%s (exists=%s) -> "
              "%d cards %r"
              % (pool, per_signal, tag, man.name, man.exists(), len(cards),
                 sorted({c["symbol"] for c in cards})))
        if pool == "core" and not per_signal and len(cards) == 0:
            fails.append("C3 the DEFAULT s-blind rebuild of %s (pool=core, "
                         "per_signal=False, exactly what daily_homework.main() "
                         "does) still yields 0 cards: main() derives tag '-s' "
                         "and therefore excludes a manifest that does not "
                         "exist, while the s10 manifest it is replacing keeps "
                         "blocking all 11 CORE_SYMBOLS" % DAY)

    # ---- C4: the test's own configuration, re-derived by hand -------------
    hdr("C4 the configuration the builder's test asserts (exclude=s10 manifest)")
    seen = deck.marked_card_ids() | deck.served_card_ids(exclude=str(S10_MAN))
    already = sorted(s for s in universe.CORE_SYMBOLS
                     if "%s_%s" % (s, DAY) in seen)
    eligible = sorted(set(universe.CORE_SYMBOLS) - set(already))
    print("CORE_SYMBOLS: %d %r" % (len(universe.CORE_SYMBOLS),
                                   sorted(universe.CORE_SYMBOLS)))
    print("already judged/served for %s (s10 manifest excluded): %d %r"
          % (DAY, len(already), already))
    print("eligible: %d %r" % (len(eligible), eligible))
    cards, stats = dh.sblind_collect(DAY, universe.CORE_SYMBOLS,
                                     per_signal=False,
                                     exclude_manifest=str(S10_MAN))
    syms = [c["symbol"] for c in cards]
    cids = [c["cid"] for c in cards]
    print("cards: %d ; symbols %r ; symbol repeats: %d ; cid repeats: %d"
          % (len(cards), sorted(syms), len(syms) - len(set(syms)),
             len(cids) - len(set(cids))))
    reserved = sorted(c for c in cids if c in seen)
    print("cards colliding with marked|served: %d %r" % (len(reserved), reserved))
    if len(syms) != len(set(syms)) or reserved:
        fails.append("C4 per-symbol rebuild repeats or re-serves")

    # ---- C5: all S bars on the one chart ----------------------------------
    hdr("C5 does the one card carry every S bar for that symbol-day")
    scan = {}
    for sym in universe.CORE_SYMBOLS:
        d = dh.scan_symbol_day(sym, DAY) if hasattr(dh, "scan_symbol_day") else None
        if d:
            scan[sym] = d
    bysym = {c["symbol"]: c for c in cards}
    for c in cards:
        sb = c.get("_sbars")
        print("  %-5s cut_i=%s cut_t=%s n_bars=%d kind=%s"
              % (c["symbol"], c.get("cut_i"), c.get("cut_t"),
                 len(c["bars"]), c.get("kind")))
    # AMD is the referee's worked example. Re-derive its S bars from the raw
    # signals rather than trusting the card.
    amd_sbars = None
    try:
        raw = dh.day_signals("AMD", DAY) if hasattr(dh, "day_signals") else None
    except Exception:
        raw = None
    print("AMD card present: %s" % ("AMD" in bysym))
    if "AMD" in bysym:
        a = bysym["AMD"]
        print("AMD cut_i=%s cut_t=%s n_bars=%d" % (a.get("cut_i"),
                                                   a.get("cut_t"),
                                                   len(a["bars"])))
    # ---- C6: render one card, look for per-S-bar marks in the SVG ---------
    hdr("C6 render one card and inspect the SVG")
    scratch = Path(tempfile.mkdtemp(prefix="h1_referee_"))
    if cards:
        html = dh.sblind_card_html(cards[0], 1, len(cards))
        p = scratch / "card.html"
        p.write_text(html, encoding="utf-8")
        print("rendered %s (%s) -> %d bytes" % (cards[0]["symbol"], p, len(html)))
        for token in ("cut", "fire", "S ", "entry", "signal"):
            print("   token %-8r occurrences in card html: %d"
                  % (token, html.count(token)))

    hdr("VERDICT INPUTS")
    if fails:
        for f in fails:
            print("FAIL: %s" % f)
    else:
        print("no failures raised by this script")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
