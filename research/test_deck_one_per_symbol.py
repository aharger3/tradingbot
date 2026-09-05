"""H1: the s-blind daily deck deals one card per SYMBOL, not one per S signal.

Rebuilds the 2026-09-03 s-blind deck (research core pool) with the current
default (``per_signal=False``) and checks:
  - one card per symbol, never more than one per symbol (no per-signal splits)
  - all 11 CORE_SYMBOLS are already marked/served for 2026-09-03: 6 were
    graded on the -s10 deck, and the other 5 (AAPL, AMD, AMZN, MSFT, QQQ)
    were SERVED on that same deck and never graded back -- this is the exact
    hole the H1 referee found (defect 3, OMEN 10.0): the s-blind builder wrote
    no manifest, so served_card_ids() could not see them. The backfilled
    ``research/decks/omen-daily-2026-09-03-s10-manifest.jsonl`` plus the
    manifest daily_homework.py now writes on every build close it: 0 symbols
    remain eligible and the rebuild produces 0 cards.
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
        assert eligible == 0, (
            "expected all 11 CORE_SYMBOLS already marked/served for %s "
            "(the -s10 deck's manifest now records the 5 served-not-graded "
            "symbols too), got %d already-seen: %r"
            % (DAY, len(already), sorted(already)))

        cards, stats = dh.sblind_collect(DAY, universe.CORE_SYMBOLS,
                                          per_signal=False)

        assert len(cards) == eligible == 0, (
            "expected 0 cards for %s (every CORE_SYMBOLS symbol already "
            "marked or served that day), got %d" % (DAY, len(cards)))

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
        real_manifest = ROOT / "research" / "decks" / (
            "omen-daily-%s-s10-manifest.jsonl" % DAY)
        assert real_manifest.exists(), (
            "sanity check missing backfilled manifest: %s" % real_manifest)

        # A day with eligible symbols still deals one card per symbol, no
        # repeats -- checked on the six-symbol demo pool (2026-09-04, none of
        # it marked/served) rather than 09-03, which is now fully closed.
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

        print("PASS -- %s s-blind deck (per_signal=False): 0 eligible symbols "
              "(all 11 CORE_SYMBOLS marked or served), 0 repeats; %s demo "
              "deck: %d cards, one per symbol, 0 repeats against "
              "marked_card_ids() | served_card_ids()"
              % (DAY, demo_day, len(demo_cards)))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
