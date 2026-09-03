"""g77_wrongchart_extract.py -- pull every book signal for the 30 graded cards.

Reads research/bt2y_trades.json (137 MB) once and writes a small cache holding
EVERY signal the engine had on each of the 30 graded symbol-days, plus a
book-wide census of how often a graded-card day carried a traded signal that
was not the card.

Read-only on the mark file and on the book. Writes only its own cache.
"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BOOK = os.path.join(HERE, "bt2y_trades.json")
MARKS = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")
MANIFEST = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")
OUT = os.path.join(HERE, "g77_wrongchart_signals.json")

KEEP = ("sym", "day", "setup", "setup_label", "dir", "grade", "status", "traded",
        "alert", "et", "entry", "stop", "target", "exit", "out", "pnl", "r",
        "entry_i", "level", "level_name", "level_px", "sgrade", "tripped",
        "confluence", "downgrades", "s", "tags", "stop_pct", "seq", "reason")


def main():
    marks = [json.loads(l) for l in open(MARKS, encoding="utf-8") if l.strip()]
    manifest = {m["card_id"]: m for m in
                (json.loads(l) for l in open(MANIFEST, encoding="utf-8") if l.strip())}
    want = {(m["symbol"], m["date"]) for m in marks}
    print("cards=%d  manifest=%d  distinct symbol-days=%d"
          % (len(marks), len(manifest), len(want)))

    book = json.load(open(BOOK, encoding="utf-8"))
    rows = book["trades"]
    print("book: %d signals, %d traded" % (len(rows), sum(1 for r in rows if r["traded"])))

    per_day = defaultdict(list)
    # book-wide: traded-signal census per symbol-day (cheap, one pass)
    traded_per_day = defaultdict(int)
    sig_per_day = defaultdict(int)
    for r in rows:
        k = (r["sym"], r["day"])
        sig_per_day[k] += 1
        if r["traded"]:
            traded_per_day[k] += 1
        if k in want:
            per_day[k].append({f: r.get(f) for f in KEEP})

    for k in per_day:
        per_day[k].sort(key=lambda r: (r.get("et") or "", r.get("entry_i") or 0))

    out = {
        "cards": marks,
        "manifest": manifest,
        "signals": {"%s|%s" % k: v for k, v in per_day.items()},
        "book_meta": book["meta"],
        "traded_per_day_hist": {},
    }
    hist = defaultdict(int)
    for k, n in traded_per_day.items():
        hist[n] += 1
    hist[0] = len(sig_per_day) - len(traded_per_day)
    out["traded_per_day_hist"] = dict(sorted(hist.items()))
    out["n_symbol_days"] = len(sig_per_day)
    json.dump(out, open(OUT, "w", encoding="utf-8"), separators=(",", ":"))
    print("wrote %s" % OUT)
    print("traded signals per symbol-day, book-wide: %s" % out["traded_per_day_hist"])


if __name__ == "__main__":
    main()
