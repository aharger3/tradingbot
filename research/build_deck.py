"""build_deck.py — THE OMEN deck generator. There is no other one.

Standard (settled 2026-08-21, Projects/omen-decks.md):
  * 60 cards per deck. Never 100, never 200 — a deck Austin can finish in a sitting.
  * Mixed: half days the engine fires on, half it is silent on, shuffled, with no
    tell in the card as to which is which.
  * Card = grade (S/A/C/none + legend) + trade type + entry + stop. No R:R.
  * Never repeats a card_id that already appears in research/marks/*.jsonl.
  * Front-end comes from deck_ui.py. This file supplies data only.

    python research/build_deck.py                       # default mixed deck
    python research/build_deck.py --name omen-5.3-mixed --n 60 --seed 7

Output: research/decks/<name>.html and research/decks/<name>-manifest.jsonl
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import deck_ui
from research.t4_engine_recall import run_day, rth_candles, prior_day_levels

ARCHIVE = os.path.join(ROOT, "data_archive")
MARKS_DIR = os.path.join(HERE, "marks")
DECKS_DIR = os.path.join(HERE, "decks")

SESSION_START = "09:30"
SESSION_END = "11:00"


def marked_card_ids() -> set[str]:
    """Every card_id Austin has already graded, across every mark file ever exported.

    This is the no-repeats guarantee. A deck that re-asks a day he already
    answered wastes the only scarce input in this project.
    """
    seen: set[str] = set()
    for path in sorted(glob.glob(os.path.join(MARKS_DIR, "*.jsonl"))):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    cid = json.loads(line).get("card_id")
                except ValueError:
                    continue
                if cid:
                    seen.add(cid)
    return seen


def universe() -> list[tuple[str, str]]:
    """(symbol, day) for every archived trading day."""
    out = []
    for sym in sorted(os.listdir(ARCHIVE)):
        d = os.path.join(ARCHIVE, sym)
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, "*.csv")):
            out.append((sym, os.path.basename(f)[:-4]))
    return out


def session_candles(symbol: str, day: str) -> list:
    candles = rth_candles(symbol, day)
    if not candles:
        return []
    out = []
    for c in candles:
        t = c.timestamp[11:16] if "T" in c.timestamp else c.timestamp[:5]
        if SESSION_START <= t < SESSION_END:
            out.append(c)
    return out


def candle_dict(c) -> dict:
    return {"t": c.timestamp, "o": round(c.open, 2), "h": round(c.high, 2),
            "l": round(c.low, 2), "c": round(c.close, 2), "v": int(c.volume)}


def fire_count(symbol: str, day: str) -> int:
    try:
        entries, _sigs, _raw = run_day(symbol, day)
    except Exception:
        return 0
    return 0 if entries is None else len(entries)


def pick(n: int, seed: int, max_probe: int):
    """Half fire days, half silent days, drawn at random, never already marked."""
    want = n // 2
    seen = marked_card_ids()
    pool = [(s, d) for s, d in universe() if "%s_%s" % (s, d) not in seen]
    rng = random.Random(seed)
    rng.shuffle(pool)

    fire, silent = [], []
    probed = 0
    for sym, day in pool:
        if len(fire) >= want and len(silent) >= want:
            break
        if probed >= max_probe:
            break
        candles = session_candles(sym, day)
        if len(candles) < 60:
            continue
        probed += 1
        n_fires = fire_count(sym, day)
        bucket = fire if n_fires > 0 else silent
        if len(bucket) >= want:
            continue
        pdh, pdl, _o, _c = prior_day_levels(sym, day)
        bucket.append({"symbol": sym, "day": day, "candles": candles,
                       "pdh": pdh, "pdl": pdl, "fires": n_fires})
        if probed % 25 == 0:
            print("  probed %d  fire=%d silent=%d" % (probed, len(fire), len(silent)))

    cards = fire + silent
    rng.shuffle(cards)          # no positional tell
    return cards, len(fire), len(silent), probed, len(seen)


def write_deck(cards, name: str, label: str) -> str:
    os.makedirs(DECKS_DIR, exist_ok=True)
    day_data, prior, card_ids, htmls = {}, {}, [], []
    for c in cards:
        cid = "%s_%s" % (c["symbol"], c["day"])
        card_ids.append(cid)
        day_data[cid] = [candle_dict(x) for x in c["candles"]]
        prior[cid] = {"pdh": round(c["pdh"], 2) if c["pdh"] else None,
                      "pdl": round(c["pdl"], 2) if c["pdl"] else None}
        htmls.append(deck_ui.render_card(cid, c["symbol"]))

    out = deck_ui.HTML_HEAD.replace("__LABEL__", label).replace("__TOTAL__", str(len(card_ids)))
    out += "\n".join(htmls)
    script = deck_ui.HTML_SCRIPT_PREAMBLE
    script = script.replace("__DAY_DATA__", json.dumps(day_data))
    script = script.replace("__PRIOR_LEVELS__", json.dumps(prior))
    script = script.replace("__CARD_IDS__", json.dumps(card_ids))
    script = script.replace("__SETUPS__", json.dumps(deck_ui.SETUPS))
    script = script.replace("__DECK_ID__", name)
    out += script

    path = os.path.join(DECKS_DIR, name + ".html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)

    # The answer key stays OUT of the HTML — the deck must not tell him which
    # days the engine saw.
    man = os.path.join(DECKS_DIR, name + "-manifest.jsonl")
    with open(man, "w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps({"card_id": "%s_%s" % (c["symbol"], c["day"]),
                                "symbol": c["symbol"], "date": c["day"],
                                "deck": name,
                                "engine_fires_that_day": c["fires"]},
                               sort_keys=True) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="omen-5.3-mixed")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--max-probe", type=int, default=1200)
    ap.add_argument("--label", default=None)
    a = ap.parse_args()

    if a.n > 60:
        raise SystemExit("deck standard caps a deck at 60 cards (asked for %d)" % a.n)

    cards, nf, ns, probed, nseen = pick(a.n, a.seed, a.max_probe)
    label = a.label or ("mixed — %d cards, engine-fire days and silent days shuffled" % len(cards))
    path = write_deck(cards, a.name, label)

    ids = ["%s_%s" % (c["symbol"], c["day"]) for c in cards]
    assert len(set(ids)) == len(ids), "duplicate card_id inside the deck"
    assert not (set(ids) & marked_card_ids()), "deck repeats an already-marked day"

    print("Wrote %s" % path)
    print("  cards=%d  fire=%d  silent=%d" % (len(cards), nf, ns))
    print("  probed=%d days  excluded %d already-marked card_ids" % (probed, nseen))


if __name__ == "__main__":
    main()
