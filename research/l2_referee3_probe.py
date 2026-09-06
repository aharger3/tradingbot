"""l2_referee3_probe.py -- the three anomalies research/l2_referee3.py surfaced,
run down one at a time. Referee pass 3, row L2 (RULE84_DECIDED).

  A. two ON-arm 84% fires that the OFF arm does not have (a tightening that ADDS)
  B. the single ON fire whose reclaim gap (0.0600) exceeds 25% of the previous
     archived candle's range (0.0575)
  C. the 28 non-84% rows whose status flips halted<->fired between the arms
"""
from __future__ import annotations

import csv
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"
ARCH = ROOT / "data_archive"


def load(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def main():
    _, off = load(TAPE / "book_RULE84_DECIDED_off.json.gz")
    _, on = load(TAPE / "book_RULE84_DECIDED_on.json.gz")

    off84 = [r for r in off if r.get("setup") == "reentry_84_rule"]
    on84 = [r for r in on if r.get("setup") == "reentry_84_rule"]
    okeys = {(r["day"], r.get("et"), r.get("sym")) for r in off84 if r.get("status") == "fired"}
    nkeys = {(r["day"], r.get("et"), r.get("sym")) for r in on84 if r.get("status") == "fired"}

    print("A. ON fires absent from the OFF arm")
    for k in sorted(nkeys - okeys):
        r = next(x for x in on84 if (x["day"], x.get("et"), x.get("sym")) == k)
        print("   %s %s %s  entry %.2f level_px %s pnl %s traded=%s"
              % (k[0], k[1], k[2], r["entry"], r.get("level_px"), r.get("pnl"), r.get("traded")))
        print("     reason: %s" % r.get("reason"))
        print("     same symbol-day, OFF arm's 84%% rows:")
        for q in sorted([x for x in off84 if x["day"] == k[0] and x["sym"] == k[2]],
                        key=lambda x: x.get("et") or ""):
            print("       %s %-14s entry %.2f level_px %s | %s" %
                  (q.get("et"), q.get("status"), q["entry"], q.get("level_px"),
                   (q.get("reason") or "")[:90]))
        print("     same symbol-day, ON arm's 84%% rows:")
        for q in sorted([x for x in on84 if x["day"] == k[0] and x["sym"] == k[2]],
                        key=lambda x: x.get("et") or ""):
            print("       %s %-14s entry %.2f level_px %s | %s" %
                  (q.get("et"), q.get("status"), q["entry"], q.get("level_px"),
                   (q.get("reason") or "")[:90]))

    print("\nB. the one ON fire outside the tolerance -- rounding or a real breach?")
    tgt = ("2025-01-02", "10:59", "ORCL")
    r = next((x for x in on84 if (x["day"], x.get("et"), x.get("sym")) == tgt), None)
    if r:
        rows = list(csv.DictReader(open(ARCH / "ORCL" / "2025-01-02.csv", encoding="utf-8")))
        idx = next(i for i, b in enumerate(rows) if b["Datetime"][11:16] == "10:59")
        pb, cb = rows[idx - 1], rows[idx]
        rng = float(pb["High"]) - float(pb["Low"])
        print("   row entry %.4f level_px %.4f  archive close %.6f"
              % (r["entry"], r["level_px"], float(cb["Close"])))
        print("   prev bar %s H %s L %s -> range %.6f, 25%% = %.6f"
              % (pb["Datetime"][11:16], pb["High"], pb["Low"], rng, 0.25 * rng))
        print("   gap on the BOOK's rounded columns  = %.6f" % abs(r["entry"] - r["level_px"]))
        print("   gap on the ARCHIVE close vs level_px = %.6f"
              % abs(float(cb["Close"]) - r["level_px"]))
        print("   book columns are rounded to 2dp (entry %.2f, level_px %.2f); the "
              "engine compared unrounded floats, so a %.4f gap against a %.4f "
              "tolerance is inside the rounding band of +/-0.005 on each column."
              % (r["entry"], r["level_px"], abs(r["entry"] - r["level_px"]), 0.25 * rng))
        print("   reason: %s" % r.get("reason"))

    print("\nC. the 28 non-84% status flips -- account-wide halt cascade?")
    idx_o = {(x["day"], x.get("et"), x.get("sym"), x.get("setup")): x
             for x in off if x.get("setup") != "reentry_84_rule"}
    idx_n = {(x["day"], x.get("et"), x.get("sym"), x.get("setup")): x
             for x in on if x.get("setup") != "reentry_84_rule"}
    moved = [k for k in idx_o if k in idx_n and idx_o[k].get("status") != idx_n[k].get("status")]
    days = sorted({k[0] for k in moved})
    print("   %d rows on %d distinct days: %s" % (len(moved), len(days), days))
    for d in days:
        o84 = [x for x in off84 if x["day"] == d]
        n84 = [x for x in on84 if x["day"] == d]
        o_fired = [x for x in o84 if x.get("status") == "fired" and x.get("traded")]
        n_fired = [x for x in n84 if x.get("status") == "fired" and x.get("traded")]
        print("   %s: 84%% rows OFF %d (traded %d, syms %s) | ON %d (traded %d, syms %s)"
              % (d, len(o84), len(o_fired), sorted({x['sym'] for x in o_fired}),
                 len(n84), len(n_fired), sorted({x['sym'] for x in n_fired})))
    # every flip day must carry an 84% TRADED row that differs between arms --
    # that is the account-wide two-loss halt moving, on ANY symbol, not the flip
    # row's own symbol.
    explained = 0
    for d in days:
        o = sorted((x["et"], x["sym"], x["pnl"]) for x in off84
                   if x["day"] == d and x.get("status") == "fired" and x.get("traded"))
        n = sorted((x["et"], x["sym"], x["pnl"]) for x in on84
                   if x["day"] == d and x.get("status") == "fired" and x.get("traded"))
        if o != n:
            explained += 1
    print("   days where the 84%% traded set differs between arms: %d of %d"
          % (explained, len(days)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
