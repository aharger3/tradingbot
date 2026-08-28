"""build_s_cards.py -- the S-accuracy sweep. One question, 100 times.

Austin, 2026-08-28: "we must lay it out where we focus on S TRADE ACCURACY."
And the shape he asked for, verbatim: "the 6 levels i watch to 11am, unmarked
entry, type the minute of the s entry candle if there is one, addl comment if
needed" / "100, see how it feels".

So the card is deliberately NOT a deck card. A deck card shows the engine's
proposed entry and stop and asks him to grade it -- which measures whether he
agrees with a trade the engine already found. This measures the thing that is
actually broken: whether the DAY is an S day at all, judged with nothing on the
chart but the six levels he really watches. The engine's answer is never in the
markup; it lives in the manifest.

Selection is build_deck.pick() unchanged -- half engine-fire days, half silent
days, shuffled, and never a symbol-day he has already judged in ANY corpus.
That last clause is his: "i never want to see stock repeats of stocks i have
already graded, beacuse how is that worth my time?"

    python research/build_s_cards.py                      # 100 cards
    python research/build_s_cards.py --n 20 --seed 3      # a smoke run

Output: research/decks/<name>.html + <name>-manifest.jsonl (the answer key,
which stays OUT of the HTML).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import probe_chart
import probe_page
from build_deck import DECKS_DIR, candle_dict, marked_card_ids, pick

LEVEL_KEYS = ("pdh", "pdl", "pmh", "pml", "orh", "orl")


def render_card(c: dict) -> str:
    cid = "%s_%s" % (c["symbol"], c["day"])
    candles = [candle_dict(x) for x in c["candles"]]
    levels = {k: (round(c[k], 2) if c.get(k) is not None else None)
              for k in LEVEL_KEYS}
    # marks=[] is the whole point: the entry is unmarked. Do not pass c["fires"]
    # into anything that reaches the page.
    svg = probe_chart.render(candles, levels, marks=[],
                             label="%s 09:30-11:00" % c["symbol"])
    qs = "".join([
        probe_page.question(
            "s", "Is this an S day?",
            "Zero downgrades, the trade you would actually take. "
            "One tap. If it is not an S, say so and move on.",
            [("s", "S day"), ("no", "Not S")], required=True),
        probe_page.question(
            "min", "The minute of the S entry candle",
            "Only if you said S. Type it as HH:MM, e.g. 09:47.",
            [], required=False, note_placeholder="09:47"),
        probe_page.question(
            "why", "Anything worth saying", "Optional. Skip it unless it matters.",
            [], required=False, note_placeholder="optional"),
    ])
    export = json.dumps({"symbol": c["symbol"], "date": c["day"]}, sort_keys=True)
    return ('<article class="card" data-cid="%s" data-grade="none" data-done="0" '
            "data-export='%s'>"
            '<header class="card-h"><span class="sym">%s</span>'
            '<span class="ord">%s</span></header>%s%s</article>'
            % (cid, export, c["symbol"], "&nbsp;", svg, qs))


def build(cards: list, name: str) -> tuple[str, str]:
    os.makedirs(DECKS_DIR, exist_ok=True)
    body = "".join(render_card(c) for c in cards)
    html = probe_page.shell(
        title="S Accuracy Sweep",
        eyebrow="OMEN &middot; homework",
        h1="Is this an S day?",
        lede="Six levels, 09:30 to 11:00, entry unmarked. One tap per card. "
             "If it is an S, type the minute of the entry candle. "
             "Saves as you go &mdash; close it and come back.",
        cards_html=body,
        footer_html="%d cards. None of them is a symbol-day you have graded "
                    "before. The engine's own answer is not on this page."
                    % len(cards),
        deck_id=name)
    path = os.path.join(DECKS_DIR, name + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    man = os.path.join(DECKS_DIR, name + "-manifest.jsonl")
    with open(man, "w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps({"card_id": "%s_%s" % (c["symbol"], c["day"]),
                                "symbol": c["symbol"], "date": c["day"],
                                "deck": name,
                                "engine_fires_that_day": c["fires"]},
                               sort_keys=True) + "\n")
    return path, man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="omen-s-accuracy-100")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--max-probe", type=int, default=2500)
    a = ap.parse_args()

    cards, nf, ns, probed, nseen = pick(a.n, a.seed, a.max_probe)
    path, man = build(cards, a.name)

    ids = ["%s_%s" % (c["symbol"], c["day"]) for c in cards]
    assert len(set(ids)) == len(ids), "duplicate card_id inside the sweep"
    repeats = set(ids) & marked_card_ids()
    assert not repeats, "sweep repeats already-judged days: %s" % sorted(repeats)
    blob = open(path, encoding="utf-8").read()
    # The engine's answer must not be inferable from the page.
    assert "engine_fires" not in blob, "answer key leaked into the HTML"
    assert 'class="entry"' not in blob and "STOP" not in blob, \
        "an entry or stop was drawn -- the entry must be unmarked"

    print("Wrote %s" % path)
    print("       %s  (answer key -- not served)" % man)
    print("  cards=%d  engine-fire=%d  engine-silent=%d" % (len(cards), nf, ns))
    print("  probed=%d days  excluded %d already-judged symbol-days" % (probed, nseen))
    print("  size=%.1f MB" % (len(blob.encode("utf-8")) / 1e6))


if __name__ == "__main__":
    main()
