"""l2_referee3_join.py -- the originals S/A/C table for row L2, re-derived on an
EXACT key instead of the report's nearest-match join.

research/l2_rule84_decided.md publishes the split of 84%-rule re-entries by the
grade of the original stopped-out trade, and warns the join is approximate
("nearest match by price and time, no stored link"). It is not approximate: the
84% row carries `level_name = "not-his: prior entry (84%)"` and
`level_px = <the original entry price>`, so the original is the same-symbol,
same-day, EARLIER row whose own `entry` equals that `level_px`. This script uses
that key and reports how many 84% rows it resolves, then the S/A/C split of the
originals in both arms.

The row's spec deliverable is "how many originals were S vs A" -- that is what
this prints.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"


def load(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)["trades"]


def join(rows, statuses=None):
    """{84% row -> the original row it names}, on the exact level_px key."""
    by_sym_day = {}
    for r in rows:
        by_sym_day.setdefault((r["sym"], r["day"]), []).append(r)
    pairs, unresolved, ambiguous = [], 0, 0
    for r in rows:
        if r.get("setup") != "reentry_84_rule":
            continue
        if statuses and r.get("status") not in statuses:
            continue
        lvl, et = r.get("level_px"), (r.get("et") or "")
        cands = [q for q in by_sym_day[(r["sym"], r["day"])]
                 if q.get("setup") != "reentry_84_rule"
                 and (q.get("et") or "") < et
                 and q.get("entry") is not None
                 and abs(float(q["entry"]) - float(lvl)) < 0.005]
        if not cands:
            unresolved += 1
            continue
        # nearest in time before the reclaim
        cands.sort(key=lambda q: q.get("et") or "")
        if len({round(float(q["entry"]), 2) for q in cands}) > 1:
            ambiguous += 1
        pairs.append((r, cands[-1]))
    return pairs, unresolved, ambiguous


def split(pairs, key="sgrade"):
    return Counter((o.get(key) or "?") for _, o in pairs)


def main():
    off = load(TAPE / "book_RULE84_DECIDED_off.json.gz")
    on = load(TAPE / "book_RULE84_DECIDED_on.json.gz")
    print("exact-key join on level_px == the original row's entry\n")
    for label, rows in (("OFF", off), ("ON", on)):
        for scope, sts in (("all statuses", None), ("fired only", {"fired"})):
            pairs, un, amb = join(rows, sts)
            sg = split(pairs, "sgrade")
            lg = split(pairs, "grade")
            n84 = len([r for r in rows if r.get("setup") == "reentry_84_rule"
                       and (sts is None or r.get("status") in sts)])
            print("%-3s %-12s 84%% rows %4d | resolved %4d | unresolved %3d | "
                  "ambiguous %2d" % (label, scope, n84, len(pairs), un, amb))
            print("      original on Austin's ladder (sgrade): S %d  A %d  C %d  other %s"
                  % (sg.get("S", 0), sg.get("A", 0), sg.get("C", 0),
                     {k: v for k, v in sg.items() if k not in ("S", "A", "C")}))
            print("      original on the legacy ladder (grade): %s"
                  % dict(sorted(lg.items())))
        print()

    # the arm gate's own claim: under the flag, no original outside S/A arms one
    pairs_on, un_on, _ = join(on, None)
    bad = [(r["sym"], r["day"], r.get("et"), o.get("sgrade"))
           for r, o in pairs_on if o.get("sgrade") not in ("S", "A")]
    print("ON-arm 84%% rows whose resolved original is NOT S or A: %d of %d resolved"
          % (len(bad), len(pairs_on)))
    for b in bad[:15]:
        print("   %s %s %s -> original sgrade %s" % b)
    print("\nNOTE the book's `sgrade` column is downgrade.score at the row's own "
          "entry; backtest_week._sgrade_84 re-scores the stopped trade at arm time "
          "with the runner's then-current htf_bias, so a small residue of "
          "disagreement is expected and is not by itself a gate failure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
