"""H1 referee, PASS 3. Independent re-derivation -- shares no code with pass 2's
research/h1_referee.py, and trusts neither the builder's report nor its self-test
(research/test_deck_one_per_symbol.py).

Builder commit under review: 1f26cf73 (on top of 57f2fbd2).
Write-up: research/h1_referee_pass3.md. Passes 1-2: research/h1_referee.md.

Run:  python research/h1_referee_pass3.py
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import universe          # noqa: E402
import build_deck as deck  # noqa: E402
import daily_homework as dh  # noqa: E402

DAY = "2026-09-03"
DECKS = ROOT / "research" / "decks"
S10 = DECKS / "omen-daily-2026-09-03-s10.html"
S10_MAN = DECKS / "omen-daily-2026-09-03-s10-manifest.jsonl"


def chk(name, ok, detail=""):
    print("%-58s %s %s" % (name, "OK  " if ok else "FAIL", detail))
    return ok


def main():
    fails = []

    # ---- 1. served_card_ids() coverage: every manifest under research/ ----
    pat = os.path.join(str(ROOT / "research"), "**", "*manifest*.jsonl")
    files = sorted(glob.glob(pat, recursive=True))
    deck_files = [f for f in files if os.sep + "decks" + os.sep in f]
    served = deck.served_card_ids()
    print("manifest files found under research/: %d (of which under decks/: %d)"
          % (len(files), len(deck_files)))
    for f in files:
        n = sum(1 for _ in open(f, encoding="utf-8") if _.strip())
        print("   %-60s %4d rows" % (os.path.relpath(f, ROOT), n))
    print("served_card_ids(): %d distinct symbol-days" % len(served))

    # every deck manifest's own ids must be inside served
    missing = []
    for f in files:
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            ident = row.get("card_id") or row.get("id")
            if isinstance(ident, str):
                m = re.search(r"(?:^|_)([A-Z][A-Z0-9.\-]{0,7})_(\d{4}-\d{2}-\d{2})(?:_|$)",
                              ident)
                if m and "%s_%s" % (m.group(1), m.group(2)) not in served:
                    missing.append((os.path.basename(f), ident))
    fails.append(not chk("every manifest row is in served_card_ids()",
                         not missing, str(missing[:5])))

    # ---- 2. the 22 card ids of the s10 deck are excluded by served ----
    html = S10.read_text(encoding="utf-8", errors="replace")
    cids = sorted(set(re.findall(r'data-cid="([^"]+)"', html)))
    norm = sorted({"%s_%s" % (c.split("_")[0], c.split("_")[1]) for c in cids})
    not_served = [c for c in norm if c not in served]
    print("s10 deck: %d card ids -> %d distinct symbol-days" % (len(cids), len(norm)))
    fails.append(not chk("all s10 symbol-days excluded by served_card_ids()",
                         not not_served, str(not_served)))

    # ---- 3. rebuild 09-03 with the current default, count cards + repeats ----
    seen = deck.marked_card_ids() | deck.served_card_ids()
    cards, stats = dh.sblind_collect(DAY, universe.CORE_SYMBOLS, per_signal=False)
    repeats = [c["cid"] for c in cards if c["cid"] in seen]
    syms = [c["symbol"] for c in cards]
    print("09-03 rebuild (per_signal=False): %d cards, %d repeats, "
          "%d distinct symbols, suppressed-as-seen=%d"
          % (len(cards), len(repeats), len(set(syms)), len(stats["repeats"])))
    fails.append(not chk("09-03 rebuild has 0 repeats", not repeats, str(repeats)))
    fails.append(not chk("09-03 rebuild: one card per symbol",
                         len(syms) == len(set(syms)), str(syms)))
    # the spec's own verify line said 11 cards. Record what it actually is.
    chk("SPEC LINE: 09-03 rebuild has 11 cards", len(cards) == 11,
        "actual=%d (the backfilled s10 manifest marks all 11 as served)"
        % len(cards))

    # ---- 4. would the rebuild deal 11 cards if the s10 manifest is ignored? ----
    served_wo = deck.served_card_ids(exclude=str(S10_MAN))
    seen_wo = deck.marked_card_ids() | served_wo
    elig_wo = [s for s in universe.CORE_SYMBOLS
               if "%s_%s" % (s, DAY) not in seen_wo]
    print("ignoring the s10 manifest: %d of 11 CORE_SYMBOLS eligible on %s: %r"
          % (len(elig_wo), DAY, elig_wo))

    # ---- 5. ALL S BARS ON ONE CHART (spec clause 2) ----
    # Pick a symbol-day with more than one S bar and check the card's tape
    # reaches the LAST S bar, and that every S bar is drawn on the SVG.
    probe_day = DAY
    worst = None
    for sym in universe.CORE_SYMBOLS:
        bars, levels, trades = dh.day_signals(sym, probe_day, cut=dh.BLIND_END)
        if not bars:
            continue
        sigs = [dict(dh._sig_row(t),
                     i={c.timestamp[:5]: k for k, c in enumerate(bars)}.get(
                         t.entry_time[:5])) for t in trades]
        sb = dh.s_bars(sigs)
        if len(sb) > 1 and (worst is None or len(sb) > worst[1]):
            worst = (sym, len(sb), [i for i, _ in sb], sigs, bars)
    if worst is None:
        chk("found a multi-S-bar symbol-day to probe", False, "none on " + probe_day)
        fails.append(True)
    else:
        sym, n, idxs, sigs, bars = worst
        kind, cut = dh.classify(sigs)
        print("%s %s: S bars at %r, classify() cut=%s (kind=%s)"
              % (sym, probe_day, idxs, cut, kind))
        ok = cut == max(idxs)
        fails.append(not chk("card tape reaches the LAST S bar (all S on chart)",
                             ok, "cut=%s last_S=%s -> tape is bars[:%s+1], "
                                 "S bars after the cut are NOT drawn"
                                 % (cut, max(idxs), cut)))

    # ---- 6. render the card and look at the SVG ----
    if worst is not None:
        sym, n, idxs, sigs, bars = worst
        kind, cut = dh.classify(sigs)
        card = {"symbol": sym, "day": probe_day, "kind": kind, "silent": False,
                "cid": "%s_%s" % (sym, probe_day), "cut_i": cut,
                "cut_t": bars[cut].timestamp[:5],
                "bars": [{"t": c.timestamp, "o": c.open, "h": c.high,
                          "l": c.low, "c": c.close} for c in bars][:cut + 1],
                "levels": dh.day_signals(sym, probe_day, cut=dh.BLIND_END)[1],
                "signals": sigs}
        html = dh.sblind_card_html(card, 1, 1)
        out = ROOT / "research" / "h1_referee_card.html"
        out.write_text(html, encoding="utf-8")
        drawn = len(re.findall(r'<rect|<line', html))
        print("rendered %s card -> %s (%d bars on tape of %d in session; "
              "S bars %r, only %d of %d on the chart)"
              % (sym, out.name, len(card["bars"]), len(bars), idxs,
                 sum(1 for i in idxs if i <= cut), len(idxs)))
        fails.append(not chk("SVG shows every S bar of the symbol-day",
                             all(i <= cut for i in idxs),
                             "S bars %r beyond the tape end (%d)"
                             % ([i for i in idxs if i > cut], cut)))

    print()
    print("REFEREE VERDICT: %s (%d failed checks)"
          % ("REFUTED" if any(fails) else "UPHELD", sum(1 for f in fails if f)))
    return 1 if any(fails) else 0


if __name__ == "__main__":
    sys.exit(main())
