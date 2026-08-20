"""Compute the levels Austin actually watches, per deck card, from the archive.

    PDH / PDL — prior regular-session high / low
    PMH / PML — premarket high / low, 04:00 up to 09:30 on the day itself
    ORH / ORL — 5-minute opening range, 09:30 through 09:34 inclusive

Run on the Windows box (that's where data_archive lives):

    python research/build_levels.py research/t51_deck_levels.json

Output: {"TSLA_2026-05-14": {"pdh":.., "pdl":.., "pmh":.., "pml":.., "orh":.., "orl":..}, ...}
covering every card_id in the deck manifest. Copy the JSON to whatever machine
is rebuilding the decks; retrofit_deck.py folds it into PRIOR_LEVELS.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVE = os.path.join(ROOT, "data_archive")
MANIFEST = os.path.join(HERE, "t51_day_deck_manifest.jsonl")

RTH_START, RTH_END = "09:30", "16:00"
OR_END = "09:35"          # exclusive — 09:30,31,32,33,34 = the 5-minute range


def _hhmm(ts: str) -> str:
    return ts[11:16] if "T" in ts else ts[:5]


def _rows(symbol: str, day: str) -> list[dict]:
    path = os.path.join(ARCHIVE, symbol, day + ".csv")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out.append({"t": _hhmm(r["Datetime"]),
                            "h": float(r["High"]), "l": float(r["Low"])})
            except (KeyError, ValueError):
                continue
    return out


def _hi_lo(rows, lo_t, hi_t):
    """max High / min Low over rows with lo_t <= HH:MM < hi_t."""
    sel = [r for r in rows if lo_t <= r["t"] < hi_t]
    if not sel:
        return None, None
    return (round(max(r["h"] for r in sel), 2),
            round(min(r["l"] for r in sel), 2))


def _prev_day(symbol: str, day: str) -> str | None:
    days = sorted(os.path.basename(p)[:-4]
                  for p in glob.glob(os.path.join(ARCHIVE, symbol, "*.csv")))
    if day not in days:
        return None
    i = days.index(day)
    return days[i - 1] if i > 0 else None


def levels_for(symbol: str, day: str) -> dict:
    rows = _rows(symbol, day)
    pmh, pml = _hi_lo(rows, "00:00", RTH_START)          # premarket, today
    orh, orl = _hi_lo(rows, RTH_START, OR_END)           # 5-min opening range

    pdh = pdl = None
    prev = _prev_day(symbol, day)
    if prev:
        pdh, pdl = _hi_lo(_rows(symbol, prev), RTH_START, RTH_END)

    return {"pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
            "orh": orh, "orl": orl}


def main(out_path: str) -> None:
    cards = []
    with open(MANIFEST, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                cards.append((r["card_id"], r["symbol"], r["date"]))

    out = {}
    missing = []
    for cid, symbol, day in cards:
        lv = levels_for(symbol, day)
        out[cid] = lv
        if lv["pmh"] is None or lv["orh"] is None:
            missing.append(cid)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, sort_keys=True)
    print("Wrote %s (%d cards)" % (out_path, len(out)))
    if missing:
        print("  %d cards missing premarket or opening-range data: %s"
              % (len(missing), ", ".join(missing[:8])))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else os.path.join(HERE, "t51_deck_levels.json"))
