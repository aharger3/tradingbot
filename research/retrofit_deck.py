"""Upgrade an already-built OMEN day deck (5.1) to the 5.2 marking UI.

Pulls DAY_DATA / PRIOR_LEVELS / CARD_IDS straight out of the old HTML and
re-renders it through deck_ui.py, so no engine re-run or data reload is needed.

    python research/retrofit_deck.py research/omen-5.1-tsla-day-deck.html \
        research/omen-5.2-tsla-day-deck.html "TSLA - 60 days"
"""
from __future__ import annotations

import json
import re
import sys

import deck_ui


def _grab(html: str, var: str):
    m = re.search(r"^var %s = (.*);\s*$" % var, html, re.M)
    if not m:
        raise SystemExit("could not find `var %s = ...;` in the source deck" % var)
    return json.loads(m.group(1))


def _label(html: str) -> str:
    m = re.search(r'id="deckLabel">([^<]*)<', html)
    return m.group(1) if m else ""


def retrofit(src: str, dst: str, label: str | None = None,
             levels_path: str | None = None) -> None:
    with open(src, encoding="utf-8") as f:
        html = f.read()

    day_data = _grab(html, "DAY_DATA")
    prior = _grab(html, "PRIOR_LEVELS")

    # Fold in PMH/PML and 5-min ORH/ORL from build_levels.py, keeping the
    # PDH/PDL already baked into the deck when the levels file lacks them.
    if levels_path:
        with open(levels_path, encoding="utf-8") as f:
            extra = json.load(f)
        for cid, lv in extra.items():
            base = prior.get(cid) or {}
            merged = dict(base)
            for k, v in (lv or {}).items():
                if v is not None:
                    merged[k] = v
            prior[cid] = merged
    card_ids = _grab(html, "CARD_IDS")
    label = label or _label(html)

    cards = []
    for cid in card_ids:
        symbol = cid[: cid.rindex("_")]
        cards.append(deck_ui.render_card(cid, symbol))

    out = deck_ui.HTML_HEAD.replace("__LABEL__", label)
    out = out.replace("__TOTAL__", str(len(card_ids)))
    out += "\n".join(cards)

    script = deck_ui.HTML_SCRIPT_PREAMBLE
    script = script.replace("__DAY_DATA__", json.dumps(day_data))
    script = script.replace("__PRIOR_LEVELS__", json.dumps(prior))
    script = script.replace("__CARD_IDS__", json.dumps(card_ids))
    script = script.replace("__SETUPS__", json.dumps(deck_ui.SETUPS))
    out += script

    with open(dst, "w", encoding="utf-8") as f:
        f.write(out)
    print("Wrote %s (%d cards, label=%r)" % (dst, len(card_ids), label))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    retrofit(sys.argv[1], sys.argv[2],
             sys.argv[3] if len(sys.argv) > 3 else None,
             sys.argv[4] if len(sys.argv) > 4 else None)
