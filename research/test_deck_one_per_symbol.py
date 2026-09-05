"""H1: the s-blind daily deck deals one card per SYMBOL, not one per S signal.

Rebuilds the 2026-09-03 s-blind deck (research core pool) with the current
default (``per_signal=False``) and checks:
  - one card per symbol, never more than one per symbol (no per-signal splits)
  - 6 of the 11 CORE_SYMBOLS are already marked/served for 2026-09-03 (he
    graded the -s10 deck), so exactly 5 symbols remain eligible and the
    rebuild produces exactly those 5 cards
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


def main():
    scratch = Path(tempfile.mkdtemp(prefix="omen_deck_selftest_"))
    try:
        seen = deck.marked_card_ids() | deck.served_card_ids()
        already = {sym for sym in universe.CORE_SYMBOLS
                   if "%s_%s" % (sym, DAY) in seen}
        eligible = len(universe.CORE_SYMBOLS) - len(already)
        assert eligible == 5, (
            "expected 6 of the 11 CORE_SYMBOLS already marked/served for %s "
            "(leaving 5 eligible), got %d already-seen: %r"
            % (DAY, len(already), sorted(already)))

        cards, stats = dh.sblind_collect(DAY, universe.CORE_SYMBOLS,
                                          per_signal=False)

        assert len(cards) == eligible, (
            "expected one card per eligible symbol (%d) for %s, got %d"
            % (eligible, DAY, len(cards)))

        cids = [c["cid"] for c in cards]
        assert len(cids) == len(set(cids)), "deck repeats a card id: %r" % cids
        syms = [c["symbol"] for c in cards]
        assert len(syms) == len(set(syms)), (
            "per-symbol deck dealt a symbol more than once: %r" % syms)

        repeats = [cid for cid in cids if cid in seen]
        assert not repeats, "deck re-serves already-judged/served cards: %r" % repeats

        # Sanity: never wrote under the real decks dir.
        real_deck = ROOT / "research" / "decks" / (
            "omen-daily-%s-s10.html" % DAY)
        assert real_deck.exists(), "sanity check missing: %s" % real_deck

        html = dh.sblind_card_html(cards[0], 1, len(cards))
        (scratch / "sample_card.html").write_text(html, encoding="utf-8")

        print("PASS -- %s s-blind deck (per_signal=False): %d cards (one per "
              "eligible symbol), 0 repeats against marked_card_ids() | "
              "served_card_ids()" % (DAY, len(cards)))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
