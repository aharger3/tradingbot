"""L3 referee, PASS 4 -- independent re-derivation of OCR_RETEST_DISPLACEMENT.

Written to REFUTE the row and its repair (builder commit 5a1e010f, prose-only;
flag landed 90dce640, refactor 03b2810c). Imports NOTHING from
research/loop_cycle.py, research/g72_suppress_price.py, research/book_stamp.py
or the three earlier referee scripts. The book fingerprint, the unit, the
statistics and the gate are all re-typed here from their written definitions,
so a bug shared by loop_cycle and the earlier referees cannot hide.

  unit  up_to_3_stop_win_or_2loss -- candidate pool = rows with status "fired"
        AND traded, plus rows with status "halted"; per day sorted by (et, sym),
        take up to 3, stop after the first winner or the second loser.
  fill  honest close (asserted off meta.entry_fill).
  exit  shipped engine (DISASTER_STOP_R=1.0 intrabar, SCALE_PLAN
        hod_then_runner_be, loss halt on) -- asserted off the stamp.
  slice core 11 (row field tier == "core", loop.json universe.row_filter).
  gate  green months may not fall AND $/day may not fall more than 5%
        (negative baseline: the loss may not get more than 5% worse); both
        halves, boundary 2025-09-01; under 30 trades or 12 months on the BEFORE
        side there is no verdict.

Checks, in order (all printed as JSON):
  1  provenance of all three books off their own stamps
  2  OFF == baseline (deep row equality + two independent fingerprints)
  3  stamp flag diff is exactly the one flag
  4  the gate, whole / H1 / H2, against research/tape/cycles.md's L3 row
  5  the one-candle-rule slice counts the report publishes
  6  the repair's delta decomposition (-$3,090 = +$2,899 / -$191)
  7  the repair's entry-delay claim (109 of 174, median +3, max +65),
     re-run under THREE row filters, not only the loose one
  8  sample-size floors per cell
  9  the report's stated floors (-$54.6 / +$8.5 / -$116.6)

Usage:  python research/l3_referee4.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAPE = ROOT / "research" / "tape"

BOUNDARY = "2025-09-01"
MAX_DROP_PCT = 5.0
MIN_TRADES = 30
MIN_MONTHS = 12
RISK = 1000.0


# --------------------------------------------------------------------- loading

def load(path):
    with gzip.open(str(path), "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def core11(rows):
    return [r for r in rows if r.get("tier") == "core"]


# ------------------------------------------------------------- fingerprinting

def bookstamp_id(rows):
    """book_stamp.book_id's documented format, re-typed (not imported)."""
    h = hashlib.sha256()
    for r in rows:
        h.update(("%s|%s|%s|%s|%.4f|%.4f|%.4f|%s|%s\n" % (
            r.get("sym"), r.get("day"), r.get("et"), r.get("dir"),
            r.get("entry", 0.0), r.get("stop", 0.0), r.get("pnl", 0.0),
            r.get("status"), r.get("traded"))).encode())
    return h.hexdigest()[:16]


def wide_fingerprint(rows):
    """A fingerprint over MORE fields than book_stamp's, so two books that
    differ only in a column book_stamp ignores cannot pass as identical."""
    h = hashlib.sha256()
    for r in rows:
        h.update(json.dumps(r, sort_keys=True, default=str).encode())
        h.update(b"\n")
    return h.hexdigest()[:16]


# ------------------------------------------------------------------ the unit

def unit_rows(rows):
    byday = defaultdict(list)
    for r in rows:
        st = r.get("status")
        if (st == "fired" and r.get("traded")) or st == "halted":
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        ordered = sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or ""))
        losses = 0
        for n, r in enumerate(ordered):
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


def month(r):
    return r["day"][:7]


def stats(rows, n_days):
    u = unit_rows(rows)
    if not u:
        return {"trades": 0, "total": 0, "per_day": 0, "months": 0, "months_green": 0}
    total = sum(r.get("pnl", 0.0) for r in u)
    bym = defaultdict(float)
    for r in u:
        bym[month(r)] += r.get("pnl", 0.0)
    wins = [r["pnl"] for r in u if r.get("pnl", 0.0) > 0]
    losses = [r["pnl"] for r in u if r.get("pnl", 0.0) < 0]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(losses) / len(losses)) if losses else 0.0
    return {
        "trades": len(u),
        "total": round(total),
        "per_day": round(total / n_days) if n_days else 0,
        "per_day_exact": round(total / n_days, 2) if n_days else 0.0,
        "mean_r_from_pnl": round(total / len(u) / RISK, 4),
        "win_pct": round(100.0 * len(wins) / len(u), 1),
        "months": len(bym),
        "months_green": sum(1 for v in bym.values() if v > 0),
        "avg_win": round(aw),
        "avg_loss": round(al),
        "n_days": n_days,
    }


def slices(meta, rows):
    days = sorted({r["day"] for r in rows if r.get("day")})
    n_whole = meta.get("sessions") or len(days)
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    return {"whole": stats(rows, n_whole),
            "h1": stats([r for r in rows if r.get("day", "") < BOUNDARY], n1),
            "h2": stats([r for r in rows if r.get("day", "") >= BOUNDARY], n2)}


def verdict(before, after):
    if before["trades"] < MIN_TRADES or before["months"] < MIN_MONTHS:
        return {"enough": False, "pass": None,
                "why": "under the 30-trade / 12-month floor on the BEFORE side"}
    b, a = before["per_day"], after["per_day"]
    floor = b * (1 - MAX_DROP_PCT / 100.0) if b > 0 else (
        b * (1 + MAX_DROP_PCT / 100.0) if b < 0 else 0)
    green_ok = after["months_green"] >= before["months_green"]
    return {"enough": True, "pass": bool(green_ok and a >= floor),
            "floor": round(floor, 2), "dollar_ok": bool(a >= floor), "green_ok": bool(green_ok),
            "per_day": "%d -> %d" % (b, a),
            "green": "%d -> %d" % (before["months_green"], after["months_green"])}


# -------------------------------------------------------------- cycles.md row

def cycles_l3_row():
    txt = (TAPE / "cycles.md").read_text(encoding="utf-8")
    for ln in txt.splitlines():
        if "OCR_RETEST_DISPLACEMENT" in ln and ln.startswith("|"):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            return {"raw": ln.strip(), "date": cells[0], "label": cells[1], "flag": cells[2],
                    "decision": cells[3], "per_day": cells[4], "green": cells[5],
                    "h1": cells[6], "h2": cells[7], "trades": cells[8]}
    return None


# ------------------------------------------------------- the OCR-only slices

def ocr_slice(rows):
    o = [r for r in rows if r.get("setup") == "one_candle_rule"]
    tr = [r for r in o if r.get("traded")]
    return {"detections": len(o), "traded": len(tr),
            "mean_r_traded": round(sum(r.get("r", 0.0) for r in tr) / len(tr), 4) if tr else None,
            "mean_r_traded_from_pnl": round(
                sum(r.get("pnl", 0.0) for r in tr) / len(tr) / RISK, 4) if tr else None}


# --------------------------------------------------- the entry-delay question

def first_ocr_by_symbol_day(rows, only=None):
    """earliest one-candle-rule row per (sym, day). `only`:
       None      -> every OCR row whatever its status  (the repair's filter)
       'fired'   -> status == 'fired'
       'traded'  -> status == 'fired' and traded"""
    d = {}
    for r in rows:
        if r.get("setup") != "one_candle_rule":
            continue
        if only == "fired" and r.get("status") != "fired":
            continue
        if only == "traded" and not (r.get("status") == "fired" and r.get("traded")):
            continue
        k = (r["sym"], r["day"])
        et = r.get("et") or ""
        if k not in d or et < d[k]:
            d[k] = et
    return d


def mins(et):
    return int(et[:2]) * 60 + int(et[3:5])


def delay_report(off_rows, on_rows, only):
    a = first_ocr_by_symbol_day(off_rows, only)
    b = first_ocr_by_symbol_day(on_rows, only)
    later = same = earlier = orphan = 0
    deltas = []
    for k, v in b.items():
        if k not in a:
            orphan += 1
            continue
        if v > a[k]:
            later += 1
            deltas.append(mins(v) - mins(a[k]))
        elif v == a[k]:
            same += 1
        else:
            earlier += 1
    deltas.sort()
    return {"filter": only or "any status", "on_symbol_days": len(b),
            "off_symbol_days": len(a), "later": later, "same": same,
            "earlier": earlier, "no_off_twin": orphan,
            "median_delay_min": deltas[len(deltas) // 2] if deltas else None,
            "median_statistics": statistics.median(deltas) if deltas else None,
            "max_delay_min": deltas[-1] if deltas else None}


# ------------------------------------------------------------------- the main

def main():
    paths = {"baseline": TAPE / "baseline_2026-09-05.json.gz",
             "off": TAPE / "book_OCR_RETEST_DISPLACEMENT_off.json.gz",
             "on": TAPE / "book_OCR_RETEST_DISPLACEMENT_on.json.gz"}
    books = {k: load(p) for k, p in paths.items()}
    out = {"script": "research/l3_referee4.py", "referee_pass": 4,
           "builder_commit_under_review": "5a1e010f",
           "unit": "up_to_3_stop_win_or_2loss", "slice": 'tier == "core"',
           "boundary": BOUNDARY}

    # 1 -- provenance
    prov = {}
    for k, (meta, rows) in books.items():
        st = meta["stamp"]
        prov[k] = {"stamp_book_id": st.get("book_id"),
                   "book_id_retyped": bookstamp_id(rows),
                   "wide_fingerprint": wide_fingerprint(rows),
                   "commit": st["git"]["commit"][:8],
                   "commit_subject": st["git"].get("commit_subject"),
                   "dirty_engine_py": st["git"]["dirty_engine_py"],
                   "dirty_py_count": st["git"]["dirty_py_count"],
                   "built_at": st["built_at"], "rows": len(rows),
                   "entry_fill": meta.get("entry_fill"),
                   "sessions": meta.get("sessions"),
                   "window": [meta.get("first"), meta.get("last")],
                   "scale_plan": st["flags"].get("backtest_week.SCALE_PLAN"),
                   "disaster_stop_r": st["flags"].get("stop_rule.DISASTER_STOP_R"),
                   "loss_halt": st["flags"].get("loss_halt.LOSS_HALT"),
                   "day_policy": st["flags"].get("signal_runner.DAY_POLICY"),
                   "ocr_flag": st["flags"].get("signal_runner.OCR_RETEST_DISPLACEMENT")}
    out["provenance"] = prov

    # 2 -- OFF == baseline
    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))
    out["off_vs_baseline"] = {
        "configured_baseline_book_id": cfg["baseline_book_id"],
        "off_book_id_retyped": prov["off"]["book_id_retyped"],
        "baseline_book_id_retyped": prov["baseline"]["book_id_retyped"],
        "book_id_match": prov["off"]["book_id_retyped"] == prov["baseline"]["book_id_retyped"]
                         == cfg["baseline_book_id"],
        "wide_fingerprint_match": prov["off"]["wide_fingerprint"] == prov["baseline"]["wide_fingerprint"],
        "deep_equal_rows": books["off"][1] == books["baseline"][1]}

    # 3 -- exactly one flag differs
    off_flags, on_flags = books["off"][0]["stamp"]["flags"], books["on"][0]["stamp"]["flags"]
    diff = {k: [off_flags.get(k), on_flags.get(k)]
            for k in sorted(set(off_flags) | set(on_flags))
            if off_flags.get(k) != on_flags.get(k)}
    out["stamp_flag_diff"] = diff
    out["stamp_flag_diff_is_exactly_the_flag"] = (
        list(diff) == ["signal_runner.OCR_RETEST_DISPLACEMENT"])
    out["flag_in_book_stamp_FLAG_SOURCES"] = (
        "OCR_RETEST_DISPLACEMENT" in (ROOT / "research" / "book_stamp.py").read_text(encoding="utf-8"))
    src = (ROOT / "signal_runner.py").read_text(encoding="utf-8")
    m = re.search(r'^OCR_RETEST_DISPLACEMENT = os\.getenv\("OCR_RETEST_DISPLACEMENT", "([^"]*)"\)',
                  src, re.M)
    out["code_default"] = m.group(1) if m else "NOT FOUND"
    out["code_default_is_off"] = (m.group(1) == "0") if m else False

    # 4 -- the gate
    off_rows, on_rows = core11(books["off"][1]), core11(books["on"][1])
    before, after = slices(books["off"][0], off_rows), slices(books["on"][0], on_rows)
    out["off_figures"], out["on_figures"] = before, after
    g = {k: verdict(before[k], after[k]) for k in ("whole", "h1", "h2")}
    out["gate"] = g
    out["decision"] = ("ship" if (g["h1"]["enough"] and g["h1"]["pass"]
                                  and g["h2"]["enough"] and g["h2"]["pass"]) else "hold")
    row = cycles_l3_row()
    out["cycles_md_row"] = row
    if row:
        out["cycles_md_agrees"] = {
            "per_day": row["per_day"] == "%.1f -> %.1f" % (before["whole"]["per_day"],
                                                           after["whole"]["per_day"]),
            "green": row["green"] == "%d -> %d" % (before["whole"]["months_green"],
                                                   after["whole"]["months_green"]),
            "h1": row["h1"] == ("pass" if g["h1"]["pass"] else "fail"),
            "h2": row["h2"] == ("pass" if g["h2"]["pass"] else "fail"),
            "trades": row["trades"] == str(after["whole"]["trades"]),
            "decision": row["decision"] == out["decision"]}

    # 5 -- the OCR slice
    out["ocr_slice_core11"] = {"off": ocr_slice(off_rows), "on": ocr_slice(on_rows)}
    out["ocr_slice_full_pool"] = {"off": ocr_slice(books["off"][1]),
                                  "on": ocr_slice(books["on"][1])}

    # 6 -- the delta decomposition the repair published
    def key(r):
        return (r["sym"], r["day"], r.get("et"), r.get("dir"), r.get("setup"))

    uo, un = unit_rows(off_rows), unit_rows(on_rows)
    ko, kn = {key(r): r for r in uo}, {key(r): r for r in un}
    removed = [ko[k] for k in ko.keys() - kn.keys()]
    added = [kn[k] for k in kn.keys() - ko.keys()]

    def by_setup(rows):
        c, p = defaultdict(int), defaultdict(float)
        for r in rows:
            c[r["setup"]] += 1
            p[r["setup"]] += r.get("pnl", 0.0)
        return {s: {"trades": c[s], "pnl": round(p[s])} for s in sorted(c)}

    d_off = sum(r.get("pnl", 0.0) for r in uo)
    d_on = sum(r.get("pnl", 0.0) for r in un)
    out["delta_decomposition"] = {
        "unit_total_off": round(d_off), "unit_total_on": round(d_on),
        "delta": round(d_on - d_off),
        "key_collisions_off": len(uo) - len(ko), "key_collisions_on": len(un) - len(kn),
        "removed": {"n": len(removed), "pnl": round(sum(r.get("pnl", 0.0) for r in removed)),
                    "by_setup": by_setup(removed)},
        "added": {"n": len(added), "pnl": round(sum(r.get("pnl", 0.0) for r in added)),
                  "by_setup": by_setup(added)},
        "identity_holds": round(sum(r.get("pnl", 0.0) for r in added)
                                - sum(r.get("pnl", 0.0) for r in removed)) == round(d_on - d_off),
        "unit_by_setup_off": by_setup(uo), "unit_by_setup_on": by_setup(un),
        "_note": "every cell under the 30-trade floor: an arithmetic identity, not a verdict"}

    # 7 -- the delay claim, under three filters
    out["ocr_delay"] = [delay_report(off_rows, on_rows, f) for f in (None, "fired", "traded")]

    # 8 -- sample sizes
    out["sample_sizes"] = {
        k: {"off_trades": before[k]["trades"], "on_trades": after[k]["trades"],
            "off_months": before[k]["months"], "on_months": after[k]["months"],
            "clears_floor": before[k]["trades"] >= MIN_TRADES and before[k]["months"] >= MIN_MONTHS}
        for k in ("whole", "h1", "h2")}

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
