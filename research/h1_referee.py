"""H1 referee, pass 2 -- re-derive every claim in the H1 repair (1f26cf73).

Nothing here trusts the builder's report or the builder's own test. Run:

    python research/h1_referee.py

Checks:
  1  served_card_ids(): manifest files vs ids, and whether the 09-03 -s10 deck's
     own card ids are excluded.
  2  the 2026-09-03 s-blind rebuild: cards, one-per-symbol, repeats.
  3  all S bars on the one chart -- render the card and look at the SVG.
  4  rerun safety: does a deck's own manifest block its own rebuild?
"""
import glob
import json
import os
import re
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import universe            # noqa: E402
import build_deck as deck  # noqa: E402
import daily_homework as dh  # noqa: E402

DAY = "2026-09-03"
DECKS = ROOT / "research" / "decks"


def check1():
    print("=== 1. served_card_ids() coverage ===")
    allman = sorted(glob.glob(str(ROOT / "research" / "**" / "*manifest*.jsonl"),
                              recursive=True))
    deckman = sorted(glob.glob(str(DECKS / "*manifest*.jsonl")))
    served = deck.served_card_ids()
    print("manifest files under research/      : %d" % len(allman))
    print("manifest files under research/decks/: %d" % len(deckman))
    for p in deckman:
        rows = sum(1 for _ in open(p, encoding="utf-8") if _.strip())
        print("   %-52s %4d rows" % (os.path.basename(p), rows))
    print("served symbol-days total            : %d" % len(served))

    # every id the -s10 deck he graded actually holds, straight out of the HTML
    html = (DECKS / ("omen-daily-%s-s10.html" % DAY)).read_text(encoding="utf-8")
    cids = re.findall(r'data-cid="([^"]+)"', html)
    syms = sorted({c.split("_")[0] for c in cids})
    print("cards in omen-daily-%s-s10.html: %d over %d symbols"
          % (DAY, len(cids), len(syms)))
    missing = [c for c in cids
               if "%s_%s" % (c.split("_")[0], DAY) not in served]
    print("card ids NOT excluded by served set : %d %s"
          % (len(missing), sorted({m.split('_')[0] for m in missing})))
    return len(cids), len(missing), syms


def check2(syms):
    print()
    print("=== 2. the %s rebuild (per_signal=False) ===" % DAY)
    seen = deck.marked_card_ids() | deck.served_card_ids()
    marked = {s for s in universe.CORE_SYMBOLS
              if "%s_%s" % (s, DAY) in deck.marked_card_ids()}
    servd = {s for s in universe.CORE_SYMBOLS
             if "%s_%s" % (s, DAY) in deck.served_card_ids()}
    eligible = [s for s in universe.CORE_SYMBOLS if "%s_%s" % (s, DAY) not in seen]
    print("CORE_SYMBOLS       : %d %s" % (len(universe.CORE_SYMBOLS),
                                          list(universe.CORE_SYMBOLS)))
    print("graded that day    : %d %s" % (len(marked), sorted(marked)))
    print("served that day    : %d %s" % (len(servd), sorted(servd)))
    print("eligible           : %d %s" % (len(eligible), eligible))
    cards, stats = dh.sblind_collect(DAY, universe.CORE_SYMBOLS, per_signal=False)
    out = [c["symbol"] for c in cards]
    print("rebuild cards      : %d %s" % (len(cards), out))
    print("repeats vs seen    : %d"
          % sum(1 for c in cards if c["cid"] in seen))
    print("symbol dealt twice : %s" % ("yes" if len(out) != len(set(out)) else "no"))
    return len(cards), len(eligible)


def check3():
    print()
    print("=== 3. all S bars on the one chart? ===")
    rows = []
    for sym in ("AMD", "AMZN", "META"):
        bars, levels, trades = dh.day_signals(sym, DAY, cut=dh.BLIND_END)
        if not bars:
            print("  %s: no bars" % sym)
            continue
        at = {c.timestamp[:5]: i for i, c in enumerate(bars)}
        sigs = [dict(dh._sig_row(t), i=at.get(t.entry_time[:5])) for t in trades]
        sbars = [i for i, _f in dh.s_bars(sigs)]
        kind, cut = dh.classify(sigs)
        if cut is None:
            print("  %s: no S bar" % sym)
            continue
        card = {"symbol": sym, "day": DAY, "kind": kind, "silent": False,
                "cid": "%s_%s" % (sym, DAY), "cut_i": cut,
                "cut_t": bars[cut].timestamp[:5],
                "bars": [{"t": c.timestamp, "o": c.open, "h": c.high,
                          "l": c.low, "c": c.close} for c in bars][:cut + 1],
                "levels": levels, "signals": sigs}
        html = dh.sblind_card_html(card, 1, 1)
        on_tape = [i for i in sbars if i <= cut]
        rows.append((sym, sbars, cut, len(on_tape), len(sbars) - len(on_tape)))
        print("  %-5s S bars %-22s cut at %-4d on tape %d  cut off %d"
              % (sym, sbars, cut, len(on_tape), len(sbars) - len(on_tape)))
    # does the rendered SVG carry any per-S-bar cut mark at all?
    if rows:
        marks = len(re.findall(r'class="[^"]*cut[^"]*"', html))
        print("  cut-line elements in the rendered SVG of the last card: %d" % marks)
    return rows


def check4():
    print()
    print("=== 4. rerun safety: does a deck's own manifest block its rebuild? ===")
    tmpdir = ROOT / "research" / "_h1_referee_tmp"
    tmpdir.mkdir(exist_ok=True)
    man = tmpdir / "h1refereeprobe-manifest.jsonl"
    day = "2026-09-04"
    syms = ["TSLA", "AMZN", "QQQ", "SPY", "NVDA", "MU"]
    try:
        before, _ = dh.sblind_collect(day, syms, per_signal=False)
        b = [c["symbol"] for c in before]
        print("  first build  : %d cards %s" % (len(b), b))
        with open(man, "w", encoding="utf-8") as f:
            for c in before:
                f.write(json.dumps({"card_id": "%s_%s" % (c["symbol"], day)}) + "\n")
        after, _ = dh.sblind_collect(day, syms, per_signal=False)
        a = [c["symbol"] for c in after]
        print("  rebuild after its own manifest was written: %d cards %s"
              % (len(a), a))
        return len(b), len(a)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    n_cids, n_missing, syms = check1()
    n_cards, n_elig = check2(syms)
    rows = check3()
    b, a = check4()
    print()
    print("SUMMARY: %d cards in the graded deck, %d of them still eligible; "
          "rebuild %d cards (%d eligible symbols); S bars off the chart on "
          "%d symbols; rerun %d -> %d cards"
          % (n_cids, n_missing, n_cards, n_elig,
             sum(1 for r in rows if r[4] > 0), b, a))
