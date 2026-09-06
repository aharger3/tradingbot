"""L3 referee pass 4, follow-on: WHERE do the 11 added break-and-retest rows
come from? The repair's report calls them "break-and-retest rows the dedupe-
release mechanism lets in". There is a competing explanation that needs ruling
out: the unit (up to 3 fires a day, stop after a win or 2 losses) picks a
DIFFERENT set of already-existing rows once the day's one-candle-rule row is
gone. If every added row already exists in the OFF book as a fired-and-traded
row, nothing was "released" by the engine's dedupe -- the unit simply reached
further down a day it already had.

Also checks STRONG_PA_MULT == OCR_STRONG_PA_MULT (the spec parenthetical names
the former; the code uses the latter).

Usage: python research/l3_referee4_added.py
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAPE = ROOT / "research" / "tape"
BOUNDARY = "2025-09-01"


def load(p):
    with gzip.open(str(p), "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def core11(rows):
    return [r for r in rows if r.get("tier") == "core"]


def unit_rows(rows):
    byday = defaultdict(list)
    for r in rows:
        st = r.get("status")
        if (st == "fired" and r.get("traded")) or st == "halted":
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        losses = 0
        for n, r in enumerate(sorted(byday[day],
                                     key=lambda x: (x.get("et") or "", x.get("sym") or ""))):
            if n >= 3:
                break
            out.append(r)
            p = r.get("pnl", 0.0)
            if p > 0:
                break
            if p < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


def key(r):
    return (r["sym"], r["day"], r.get("et"), r.get("dir"), r.get("setup"))


def main():
    _, off_all = load(TAPE / "book_OCR_RETEST_DISPLACEMENT_off.json.gz")
    _, on_all = load(TAPE / "book_OCR_RETEST_DISPLACEMENT_on.json.gz")
    off_rows, on_rows = core11(off_all), core11(on_all)

    uo, un = unit_rows(off_rows), unit_rows(on_rows)
    ko, kn = {key(r): r for r in uo}, {key(r): r for r in un}
    added = [kn[k] for k in sorted(kn.keys() - ko.keys())]

    # every core-11 row in the OFF book, by key, whatever its status
    off_by_key = defaultdict(list)
    for r in off_rows:
        off_by_key[key(r)].append(r)

    detail, already_present, truly_new = [], 0, 0
    for r in added:
        twins = off_by_key.get(key(r), [])
        present_traded = [t for t in twins if t.get("status") == "fired" and t.get("traded")]
        same_pnl = [t for t in present_traded if round(t.get("pnl", 0.0), 2) == round(r.get("pnl", 0.0), 2)]
        if present_traded:
            already_present += 1
        else:
            truly_new += 1
        detail.append({
            "sym": r["sym"], "day": r["day"], "et": r.get("et"), "setup": r.get("setup"),
            "pnl_on": round(r.get("pnl", 0.0)),
            "off_twins": len(twins),
            "off_twin_statuses": sorted({("%s/traded=%s" % (t.get("status"), bool(t.get("traded"))))
                                         for t in twins}),
            "exists_in_off_as_fired_and_traded": bool(present_traded),
            "same_pnl_in_off": bool(same_pnl),
        })

    # what did that day look like in each arm?
    days = sorted({r["day"] for r in added})
    day_view = {}
    for d in days:
        day_view[d] = {
            "off_unit": [(x.get("et"), x["sym"], x.get("setup"), round(x.get("pnl", 0.0)))
                         for x in uo if x["day"] == d],
            "on_unit": [(x.get("et"), x["sym"], x.get("setup"), round(x.get("pnl", 0.0)))
                        for x in un if x["day"] == d],
            "off_candidates": len([x for x in off_rows if x["day"] == d
                                   and ((x.get("status") == "fired" and x.get("traded"))
                                        or x.get("status") == "halted")]),
            "on_candidates": len([x for x in on_rows if x["day"] == d
                                  and ((x.get("status") == "fired" and x.get("traded"))
                                       or x.get("status") == "halted")]),
        }

    sys.path.insert(0, str(ROOT))
    import signal_runner as sr
    import omen_bot as ob

    out = {
        "added_rows": len(added),
        "added_already_in_off_book_as_fired_and_traded": already_present,
        "added_absent_from_off_book": truly_new,
        "verdict_on_the_reports_cause": (
            "unit reselection, not dedupe release" if truly_new == 0 else
            "at least some rows are genuinely new to the ON book"),
        "detail": detail,
        "days": day_view,
        "strong_pa_mult": {"signal_runner.STRONG_PA_MULT": getattr(sr, "STRONG_PA_MULT", None),
                           "omen_bot.OCR_STRONG_PA_MULT": ob.OCR_STRONG_PA_MULT,
                           "equal": getattr(sr, "STRONG_PA_MULT", None) == ob.OCR_STRONG_PA_MULT},
        "flag_default": sr.OCR_RETEST_DISPLACEMENT,
        "ocr_strict_default": sr.OCR_STRICT,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
