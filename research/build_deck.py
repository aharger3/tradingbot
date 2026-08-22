"""build_deck.py — THE OMEN deck generator. There is no other one.

Standard (settled 2026-08-21, Projects/omen-decks.md):
  * 60 cards per deck. Never 100, never 200 — a deck Austin can finish in a sitting.
  * Mixed: half days the engine fires on, half it is silent on, shuffled, with no
    tell in the card as to which is which.
  * Card = grade (S/A/C/none + legend) + trade type + entry + stop. No R:R.
  * Never repeats a symbol-day Austin has already judged, in ANY mark corpus --
    research/marks/*.jsonl plus the older files listed in LEGACY_MARK_FILES.
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


# Every artifact carrying a human judgement, per research/marks/LEDGER.md (OMEN 6
# ticket 01). research/marks/*.jsonl is globbed on top of this, so new deck
# exports are picked up automatically; these are the older corpora that live
# OUTSIDE that directory and were invisible to the guard until 2026-08-22.
#
# Deliberately NOT here: decks/*-manifest.jsonl and decks/_retired/*-key.json
# (engine answer keys, not Austin's judgements).
LEGACY_MARK_FILES = [
    "austin_marks_v7.jsonl",      # terminal file; v2-v6 are fully contained in it
    "blind_marks_all.jsonl",
    "marks_clean.jsonl",
    "mark_batch_02_grades.jsonl",
    "mark_batch_03_regrades.jsonl",
    "mark_batch_04_grades.jsonl",
    "derived_marks_v1.jsonl",
    "derived_marks_v2.jsonl",
    "recovered_reviews.jsonl",
    "austin_verdicts.json",       # a JSON list, not jsonl
]

# The schemas disagree. Canonical day-cards carry card_id/symbol/date; the older
# bar-level corpora carry id/symbol/day; one batch carries only `id`. The join is
# always symbol + date.
_GRADE_KEYS = ("austin_tier", "tier", "austin_grade", "grade", "verdict")


def _judgement_key(row: dict) -> str | None:
    """Normalise any mark row to ``SYMBOL_YYYY-MM-DD``, or None if it isn't a judgement.

    A row counts as a judgement when it carries a non-empty human grade. Note
    that ``grade: "none"`` IS a judgement -- an explicit refusal to trade the day
    -- so it must exclude the day from future decks. Rows with no grade at all
    (e.g. the unmarked remainder of blind_marks_all.jsonl) are not judgements and
    do not exclude anything.
    """
    if not any(str(row.get(k, "")).strip() for k in _GRADE_KEYS):
        return None
    symbol = row.get("symbol")
    day = row.get("date") or row.get("day")
    if not (symbol and day):
        # mark_batch_04_grades.jsonl carries only `id`; card_id/id are
        # SYMBOL_YYYY-MM-DD or SYMBOL_YYYY-MM-DD_ENTRYIDX.
        ident = row.get("card_id") or row.get("id") or row.get("card")
        if not ident:
            return None
        parts = str(ident).split("_")
        if len(parts) < 2:
            return None
        symbol, day = parts[0], parts[1]
    return "%s_%s" % (symbol, day)


def _rows(path: str):
    """Yield dict rows from a .jsonl or a .json list."""
    if not os.path.exists(path):
        return
    if path.endswith(".json"):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except ValueError:
            return
        for row in data if isinstance(data, list) else data.values():
            if isinstance(row, dict):
                yield row
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def mark_sources() -> list[str]:
    """Every path the no-repeat guard reads. Order is stable for reporting."""
    return sorted(glob.glob(os.path.join(MARKS_DIR, "*.jsonl"))) + [
        os.path.join(HERE, name) for name in LEGACY_MARK_FILES
    ]


def marked_card_ids(per_source: dict | None = None) -> set[str]:
    """Every symbol-day Austin has already judged, across EVERY mark corpus.

    This is the no-repeats guarantee. A deck that re-asks a day he already
    answered wastes the only scarce input in this project.

    Until 2026-08-22 this globbed research/marks/ alone and was blind to the 386
    symbol-days in austin_marks_v7.jsonl and the standalone batches -- see OMEN 6
    ticket 15. Pass ``per_source`` (a dict) to have it filled with
    ``{path: n_keys}`` for reporting.
    """
    seen: set[str] = set()
    for path in mark_sources():
        found = {k for k in (_judgement_key(r) for r in _rows(path)) if k}
        if per_source is not None:
            per_source[path] = len(found)
        seen |= found
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
    per_source: dict[str, int] = {}
    seen = marked_card_ids(per_source)
    full = universe()
    pool = [(s, d) for s, d in full if "%s_%s" % (s, d) not in seen]
    print("no-repeat guard: %d judged symbol-days across %d sources; "
          "pool %d -> %d archived days"
          % (len(seen), len(per_source), len(full), len(pool)))
    for path, cnt in sorted(per_source.items(), key=lambda kv: -kv[1]):
        if cnt:
            print("    %5d  %s" % (cnt, os.path.relpath(path, ROOT)))
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
    # Checked against EVERY mark corpus, not just research/marks/ -- ticket 15.
    repeats = set(ids) & marked_card_ids()
    assert not repeats, "deck repeats already-judged days: %s" % sorted(repeats)

    print("Wrote %s" % path)
    print("  cards=%d  fire=%d  silent=%d" % (len(cards), nf, ns))
    print("  probed=%d days  excluded %d already-judged symbol-days" % (probed, nseen))


if __name__ == "__main__":
    main()
