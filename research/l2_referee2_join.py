"""l2_referee2_join.py -- referee pass 2: the one claim pass 1 left unchecked.

The row's own spec deliverable is "how many originals were S vs A". The builder
reported it off a nearest-match join (symbol, day, level price within 2 cents)
and called the counts approximate. This re-does the join on a tighter key that
the book actually carries:

  a re-entry row's `level_px` IS the original entry price
  (`level_name == "not-his: prior entry (84%)"`, `level_tf == "1m failed entry"`),

so the original is the traded, stopped-out (`out == "loss"`) row on the same
symbol and day whose own `entry` equals that `level_px` to a cent and whose
`et` precedes the re-entry's. Grade read off `sgrade` (Austin's ladder, the
same column `_sgrade_84` computes at the arm point), falling back to `grade`.

    python research/l2_referee2_join.py
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from pathlib import Path

TAPE = Path(__file__).resolve().parent.parent / "research" / "tape"


def load(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)["trades"]


def join(rows, label, tier=None):
    if tier:
        rows = [r for r in rows if r.get("tier") == tier]
    by_day = {}
    for r in rows:
        by_day.setdefault((r.get("sym"), r.get("day")), []).append(r)
    counts, unmatched = Counter(), 0
    for r in rows:
        if r.get("setup") != "reentry_84_rule":
            continue
        lp, et = r.get("level_px"), r.get("et") or ""
        best = None
        for o in by_day.get((r.get("sym"), r.get("day")), []):
            if o is r or o.get("setup") == "reentry_84_rule":
                continue
            if not o.get("traded") or o.get("out") != "loss":
                continue
            if o.get("entry") is None or lp is None:
                continue
            if abs(o["entry"] - lp) > 0.01:
                continue
            if (o.get("et") or "") >= et:
                continue
            if best is None or (o.get("et") or "") > (best.get("et") or ""):
                best = o
        if best is None:
            unmatched += 1
        else:
            counts[best.get("sgrade") or best.get("grade") or "?"] += 1
    total = sum(counts.values()) + unmatched
    print("%-22s rows %4d | originals S %3d  A %3d  C %3d  other %2d | unmatched %3d"
          % (label, total, counts["S"], counts["A"], counts["C"],
             sum(v for k, v in counts.items() if k not in ("S", "A", "C")), unmatched))
    return counts, unmatched


def main():
    off = load(TAPE / "book_RULE84_DECIDED_off.json.gz")
    on = load(TAPE / "book_RULE84_DECIDED_on.json.gz")
    print("== any-status 84%-rule rows, original graded by tight join ==")
    join(off, "OFF full pool")
    join(on, "ON  full pool")
    join(off, "OFF core-11", tier="core")
    join(on, "ON  core-11", tier="core")
    print("\n== fired-only ==")
    join([r for r in off if r.get("status") == "fired" or r.get("setup") != "reentry_84_rule"],
         "OFF full pool (fired)")
    join([r for r in on if r.get("status") == "fired" or r.get("setup") != "reentry_84_rule"],
         "ON  full pool (fired)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
