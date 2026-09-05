"""H1 referee: re-derive every number in the H1 report from scratch.

Builder commit: 57f2fbd2 ("H1: one card per symbol -- 09-03 deck 5 eligible
cards, 0 repeats").

Checks, in order:
  1. served_card_ids() -- how many manifest FILES it reads, how many ids, and
     whether the 2026-09-03 s-blind deck he actually graded
     (research/decks/omen-daily-2026-09-03-s10.html) is represented in it.
  2. the 2026-09-03 rebuild with per_signal=False: card count, one-per-symbol,
     overlap against marked_card_ids() | served_card_ids(), and WHICH of the
     two sets does the excluding.
  3. the production path: which scheduled runner builds the deck he grades and
     what per_signal value it passes.
  4. all S bars of a symbol on its one chart: render a real card and count the
     cut lines in the SVG against the symbol's S bars.

    python research/h1_referee.py
"""
import glob
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import universe  # noqa: E402
import build_deck as deck  # noqa: E402
import daily_homework as dh  # noqa: E402

DAY = "2026-09-03"
L = []


def say(s=""):
    print(s)
    L.append(s)


def main():
    # ---- 1. served_card_ids coverage -------------------------------------
    files = sorted(glob.glob(os.path.join(ROOT, "research", "**",
                                          "*manifest*.jsonl"), recursive=True))
    deckdir_manifests = [f for f in files
                         if os.path.basename(os.path.dirname(f)) == "decks"]
    served = deck.served_card_ids()
    marked = deck.marked_card_ids()
    say("1. served_card_ids(): %d manifest files repo-wide, %d of them under "
        "research/decks/, %d served symbol-days"
        % (len(files), len(deckdir_manifests), len(served)))
    say("   marked_card_ids(): %d judged symbol-days" % len(marked))

    # Is the 09-03 s-blind deck he graded in the served set at all?
    html = (ROOT / "research" / "decks"
            / ("omen-daily-%s-s10.html" % DAY)).read_text(encoding="utf-8",
                                                          errors="replace")
    cids = re.findall(r'data-cid="([^"]+)"', html)
    deck_syms = sorted({c.split("_")[0] for c in cids})
    say("   decks/omen-daily-%s-s10.html: %d cards, %d distinct symbols"
        % (DAY, len(cids), len(deck_syms)))
    manifest = ROOT / "research" / "decks" / ("omen-daily-%s-s10-manifest.jsonl" % DAY)
    say("   its manifest exists: %s" % manifest.exists())
    served_from_deck = [s for s in deck_syms if "%s_%s" % (s, DAY) in served]
    marked_from_deck = [s for s in deck_syms if "%s_%s" % (s, DAY) in marked]
    say("   of those %d symbols, served_card_ids() excludes %d %r"
        % (len(deck_syms), len(served_from_deck), served_from_deck))
    say("   of those %d symbols, marked_card_ids() excludes %d %r"
        % (len(deck_syms), len(marked_from_deck), marked_from_deck))
    missed = [s for s in deck_syms
              if "%s_%s" % (s, DAY) not in (served | marked)]
    say("   SERVED BUT STILL ELIGIBLE (the hole H1 was to close): %d %r"
        % (len(missed), missed))

    # ---- 2. the rebuild ---------------------------------------------------
    seen = marked | served
    core = list(universe.CORE_SYMBOLS)
    already = sorted(s for s in core if "%s_%s" % (s, DAY) in seen)
    cards, stats = dh.sblind_collect(DAY, core, per_signal=False)
    syms = [c["symbol"] for c in cards]
    ids = [c["cid"] for c in cards]
    say()
    say("2. rebuild %s, CORE_SYMBOLS (%d), per_signal=False" % (DAY, len(core)))
    say("   already marked/served: %d %r" % (len(already), already))
    say("   cards: %d %r" % (len(cards), sorted(syms)))
    say("   one card per symbol: %s" % (len(syms) == len(set(syms))))
    say("   repeats against marked|served: %d"
        % len([i for i in ids if i in seen]))
    say("   spec's verify line asks for 11 cards; got %d" % len(cards))

    # ---- 3. the production path ------------------------------------------
    say()
    txt1615 = (ROOT / "research" / "daily_run.cmd").read_text(encoding="utf-8",
                                                              errors="replace")
    txt1105 = (ROOT / "research" / "daily_run_1105.cmd").read_text(
        encoding="utf-8", errors="replace")
    call1615 = [l.strip() for l in txt1615.splitlines()
                if "daily_homework.py" in l]
    call1105 = [l.strip() for l in txt1105.splitlines()
                if "daily_homework.py" in l]
    say("3. daily_run.cmd (16:15 reveal)  -> %r" % call1615)
    say("   daily_run_1105.cmd (the deck he grades) -> %r" % call1105)
    say("   11:05 runner still passes --per-signal: %s"
        % any("--per-signal" in c for c in call1105))

    # ---- 4. all S bars on the one chart ----------------------------------
    say()
    hit = None
    for c in cards:
        sb = [i for i, _f in dh.s_bars(c["signals"])
              if i is not None and i <= c["cut_i"]]
        if len(sb) > 1:
            hit = (c, sb)
            break
    if hit is None:
        say("4. no rebuilt card has more than one S bar on its SHOWN tape.")
        say("   Reason: classify() returns the FIRST S bar and sblind_collect")
        say("   truncates bars[:cut_i+1], so later S bars are cut off screen.")
        for c in cards:
            allsb = [i for i, _f in dh.s_bars(c["signals"]) if i is not None]
            if len(allsb) > 1:
                say("   %s: S bars in the full 09:30-11:00 tape %r, card cut_i "
                    "= %d, bars shown = %d -- %d S bar(s) NOT on the chart"
                    % (c["symbol"], allsb, c["cut_i"], len(c["bars"]),
                       len([i for i in allsb if i > c["cut_i"]])))
    else:
        c, sb = hit
        h = dh.sblind_card_html(c, 1, len(cards))
        cuts = re.findall(r'class="cut"', h)
        say("4. %s: %d S bars on the shown tape %r, cut markers in the SVG: %d"
            % (c["symbol"], len(sb), sb, len(cuts)))
        say("   card cut_i = %d (last S bar = %d)" % (c["cut_i"], max(sb)))


if __name__ == "__main__":
    main()
