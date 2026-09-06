"""H1: the s-blind daily deck deals one card per SYMBOL, not one per S signal,
and every S bar for that symbol lands on the one chart it gets.

Rebuilds the 2026-09-03 s-blind deck (research core pool) with the current
default (``per_signal=False``), EXCLUDING the deck's own manifest (this is a
rebuild of that exact deck, so it must not read the manifest it is about to
overwrite -- H1 referee, OMEN 10.0, defect 2). It checks:

  - one card per symbol, never more than one per symbol (no per-signal splits)
  - of the 11 CORE_SYMBOLS, 6 (TSLA, NVDA, META, GOOGL, PLTR, SPY) are already
    marked in a mark corpus for 2026-09-03 independent of any deck manifest,
    so only 5 (AAPL, AMD, AMZN, MSFT, QQQ) were ever eligible for this deck --
    "11 cards" was not a reachable number even at dispatch (H1 referee, OMEN
    10.0, pass 3): this asserts the real eligible count, not a stale one.
  - the rebuild produces exactly one card per eligible symbol, 0 repeats
  - AMD's card is cut at its LAST S bar (86, 10:56), not its first (36) --
    the referee's own example (AMD 2026-09-03 has S bars at 36/63/64/82/86)
    now has all five on the tape shown, not one of five
    (H1 referee, OMEN 10.0, defect 1)
  - no card id collides with anything Austin has already judged or been
    served (``build_deck.marked_card_ids() | build_deck.served_card_ids()``)

Writes nothing under research/decks/ -- everything goes to a scratch dir that
is removed at the end, so the deck he actually graded
(research/decks/omen-daily-2026-09-03-s10.html) is never touched.

    python research/test_deck_one_per_symbol.py
"""
import shutil
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
REAL_MANIFEST = str(ROOT / "research" / "decks" /
                     ("omen-daily-%s-s10-manifest.jsonl" % DAY))


def main():
    scratch = Path(tempfile.mkdtemp(prefix="omen_deck_selftest_"))
    try:
        # Rebuild-of-self: exclude the deck's own manifest, exactly as
        # daily_homework.main() now does for a real rebuild.
        seen = deck.marked_card_ids() | deck.served_card_ids(
            exclude=REAL_MANIFEST)
        already = {sym for sym in universe.CORE_SYMBOLS
                   if "%s_%s" % (sym, DAY) in seen}
        eligible_syms = sorted(set(universe.CORE_SYMBOLS) - already)
        assert already == {"TSLA", "NVDA", "META", "GOOGL", "PLTR", "SPY"}, (
            "expected exactly these 6 CORE_SYMBOLS already marked for %s "
            "independent of the s10 manifest, got %r -- if this changed, a "
            "new mark corpus landed and the eligible set below must move "
            "with it" % (DAY, sorted(already)))
        assert eligible_syms == ["AAPL", "AMD", "AMZN", "MSFT", "QQQ"], (
            "expected AAPL/AMD/AMZN/MSFT/QQQ eligible for %s, got %r"
            % (DAY, eligible_syms))

        cards, stats = dh.sblind_collect(DAY, universe.CORE_SYMBOLS,
                                          per_signal=False,
                                          exclude_manifest=REAL_MANIFEST)

        assert len(cards) == len(eligible_syms), (
            "expected %d cards for %s (one per eligible symbol), got %d"
            % (len(eligible_syms), DAY, len(cards)))

        cids = [c["cid"] for c in cards]
        assert len(cids) == len(set(cids)), "deck repeats a card id: %r" % cids
        syms = [c["symbol"] for c in cards]
        assert len(syms) == len(set(syms)), (
            "per-symbol deck dealt a symbol more than once: %r" % syms)
        assert sorted(syms) == eligible_syms, (
            "deck symbols %r do not match the eligible set %r"
            % (sorted(syms), eligible_syms))

        repeats = [cid for cid in cids if cid in seen]
        assert not repeats, "deck re-serves already-judged/served cards: %r" % repeats

        # Defect 1: AMD's card is cut at its LAST S bar, so every S bar it
        # had that morning (36/63/64/82/86) sits on the tape shown.
        amd = next(c for c in cards if c["symbol"] == "AMD")
        assert amd["cut_i"] == 86, (
            "AMD should cut at its last S bar (86, 10:56); got %d (%s) -- "
            "all-S-bars-on-one-chart is not holding"
            % (amd["cut_i"], amd["cut_t"]))
        # Sanity: never wrote under the real decks dir.
        real_deck = ROOT / "research" / "decks" / (
            "omen-daily-%s-s10.html" % DAY)
        assert real_deck.exists(), "sanity check missing: %s" % real_deck
        real_manifest = Path(REAL_MANIFEST)
        assert real_manifest.exists(), (
            "sanity check missing backfilled manifest: %s" % real_manifest)

        # A day with eligible symbols still deals one card per symbol, no
        # repeats -- checked on the six-symbol demo pool (2026-09-04, none of
        # it marked/served).
        demo_day = "2026-09-04"
        demo_syms = ["TSLA", "AMZN", "QQQ", "SPY", "NVDA", "MU"]
        demo_seen = {sym for sym in demo_syms
                     if "%s_%s" % (sym, demo_day) in seen}
        demo_cards, _ = dh.sblind_collect(demo_day, demo_syms, per_signal=False)
        demo_syms_out = [c["symbol"] for c in demo_cards]
        assert len(demo_syms_out) == len(set(demo_syms_out)), (
            "per-symbol deck dealt a symbol more than once: %r" % demo_syms_out)
        assert not (set(demo_syms_out) & demo_seen), (
            "demo deck re-served an already-seen symbol: %r"
            % (set(demo_syms_out) & demo_seen))
        if demo_cards:
            html = dh.sblind_card_html(demo_cards[0], 1, len(demo_cards))
            (scratch / "sample_card.html").write_text(html, encoding="utf-8")

        print("PASS -- %s s-blind deck rebuild (per_signal=False, own "
              "manifest excluded): %d eligible symbols %r, 0 repeats, AMD "
              "cut at its last S bar (86); %s demo deck: %d cards, one per "
              "symbol, 0 repeats" % (DAY, len(eligible_syms), eligible_syms,
                                     demo_day, len(demo_cards)))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
