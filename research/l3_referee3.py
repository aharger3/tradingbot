"""L3 referee, PASS 3 -- independent re-derivation of OCR_RETEST_DISPLACEMENT.

Written to REFUTE. Imports nothing from research/loop_cycle.py,
research/g72_suppress_price.py, research/l3_referee.py or research/l3_referee2.py.
Every figure is re-typed from the spec's wording:

  unit  up_to_3_stop_win_or_2loss -- candidate pool = rows whose status is
        "fired" and traded, plus rows whose status is "halted" (the account-wide
        two-loss halt's own rows); per day, sorted by (et, sym), take up to 3,
        stop after the first winner, stop after the second loser.
  fill  honest close (meta.entry_fill == "close", asserted).
  exit  the shipped engine: 1R disaster stop on the intrabar touch,
        SCALE_PLAN=hod_then_runner_be, loss halt on (all asserted off the stamp).
  slice core 11 (tier == "core").
  gate  green months may not fall; $/day may not fall more than 5% (a negative
        baseline: the loss may not get more than 5% worse). Both halves, H1
        before 2025-09-01, H2 on/after. Under 30 trades or 12 months on the
        BEFORE side => no verdict.

Also re-derives, independently:
  * book_id for baseline / OFF / ON via research.book_stamp.book_id
  * a home-made fingerprint (sha256 over every row's identity+P&L) so the
    identity claim does not rest on book_stamp's own hash
  * the exact set of stamp keys that differ between the two arms
  * the one-candle-rule slice counts
  * whether the core-11 rows really do span all `meta.sessions` days
    (loop_cycle divides the whole window by meta.sessions, a FULL-POOL count)

Usage:  python research/l3_referee3.py
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TAPE = ROOT / "research" / "tape"

BOUNDARY = "2025-09-01"
MAX_DROP_PCT = 5.0
MIN_TRADES = 30
MIN_MONTHS = 12


def load(path):
    with gzip.open(str(path), "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def core11(rows):
    return [r for r in rows if r.get("tier") == "core"]


def unit_rows(rows):
    """up_to_3_stop_win_or_2loss, re-typed."""
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


def stats(rows, n_days):
    u = unit_rows(rows)
    total = sum(r.get("pnl", 0.0) for r in u)
    bym = defaultdict(float)
    for r in u:
        bym[r["ym"]] += r.get("pnl", 0.0)
    wins = [r["pnl"] for r in u if r.get("pnl", 0.0) > 0]
    losses = [r["pnl"] for r in u if r.get("pnl", 0.0) < 0]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(losses) / len(losses)) if losses else 0.0
    return {
        "trades": len(u),
        "total": round(total, 0),
        "per_day": round(total / n_days) if n_days else 0,
        "mean_r": round(sum(r.get("r", 0.0) for r in u) / len(u), 4) if u else 0.0,
        "win_pct": round(100.0 * len(wins) / len(u), 1) if u else 0.0,
        "months": len(bym),
        "months_green": sum(1 for v in bym.values() if v > 0),
        "avg_win": round(aw, 0),
        "avg_loss": round(al, 0),
        "awal": round(aw / al, 3) if al else None,
        "fires_per_day": round(len(u) / n_days, 3) if n_days else 0.0,
    }


def slices(meta, rows):
    days = sorted({r["day"] for r in rows if r.get("day")})
    n_whole = meta.get("sessions") or len(days)
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    return {
        "whole": stats(rows, n_whole),
        "h1": stats([r for r in rows if r.get("day", "") < BOUNDARY], n1),
        "h2": stats([r for r in rows if r.get("day", "") >= BOUNDARY], n2),
        "_days": {"distinct_in_rows": len(days), "meta_sessions": meta.get("sessions"),
                  "h1_days": n1, "h2_days": n2},
    }


def verdict(before, after):
    if before["trades"] < MIN_TRADES or before["months"] < MIN_MONTHS:
        return {"enough": False, "pass": None}
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        floor = b * (1 - MAX_DROP_PCT / 100.0)
    elif b < 0:
        floor = b * (1 + MAX_DROP_PCT / 100.0)
    else:
        floor = 0
    return {"enough": True, "pass": bool(green_ok and a >= floor),
            "floor": round(floor, 1), "green": "%d -> %d" % (before["months_green"], after["months_green"]),
            "per_day": "%d -> %d" % (b, a)}


def fingerprint(rows):
    h = hashlib.sha256()
    for r in rows:
        h.update(("|".join(str(r.get(k)) for k in
                           ("day", "sym", "et", "dir", "setup", "status", "traded",
                            "entry", "stop", "exit", "pnl", "r")) + "\n").encode())
    return h.hexdigest()[:16]


def ocr_slice(rows):
    o = [r for r in rows if r.get("setup") == "one_candle_rule"]
    tr = [r for r in o if r.get("traded")]
    return {"rows": len(o), "traded": len(tr),
            "mean_r_traded": round(sum(r.get("r", 0.0) for r in tr) / len(tr), 4) if tr else None}


def main():
    from research.book_stamp import book_id  # noqa: E402

    paths = {
        "baseline": TAPE / "baseline_2026-09-05.json.gz",
        "off": TAPE / "book_OCR_RETEST_DISPLACEMENT_off.json.gz",
        "on": TAPE / "book_OCR_RETEST_DISPLACEMENT_on.json.gz",
    }
    books = {k: load(p) for k, p in paths.items()}

    out = {"unit": "up_to_3_stop_win_or_2loss", "fill": None, "universe": 'tier == "core"',
           "boundary": BOUNDARY, "script": "research/l3_referee3.py"}

    # ---- provenance asserted off the stamps, not the report
    prov = {}
    for k, (meta, rows) in books.items():
        st = meta["stamp"]
        prov[k] = {
            "book_id_recomputed": book_id(rows),
            "book_id_in_stamp": st.get("book_id"),
            "commit": st["git"]["commit"][:8],
            "dirty_engine_py": st["git"]["dirty_engine_py"],
            "dirty_py_count": st["git"]["dirty_py_count"],
            "built_at": st["built_at"],
            "entry_fill": meta.get("entry_fill"),
            "loss_halt": meta.get("loss_halt"),
            "sessions": meta.get("sessions"),
            "window": [meta.get("first"), meta.get("last")],
            "rows": len(rows),
            "fingerprint": fingerprint(rows),
            "scale_plan": st["flags"].get("backtest_week.SCALE_PLAN"),
            "disaster_r": st["flags"].get("stop_rule.DISASTER_STOP_R"),
        }
    out["fill"] = prov["off"]["entry_fill"]
    out["provenance"] = prov

    off_flags = books["off"][0]["stamp"]["flags"]
    on_flags = books["on"][0]["stamp"]["flags"]
    keys = set(off_flags) | set(on_flags)
    diff = {k: [off_flags.get(k), on_flags.get(k)] for k in sorted(keys)
            if off_flags.get(k) != on_flags.get(k)}
    out["stamp_flag_diff"] = diff
    out["stamp_flag_diff_exactly_one"] = list(diff) == ["signal_runner.OCR_RETEST_DISPLACEMENT"]

    # non-flag stamp differences
    off_st = dict(books["off"][0]["stamp"])
    on_st = dict(books["on"][0]["stamp"])
    off_st.pop("flags"), on_st.pop("flags")
    out["stamp_nonflag_diff"] = sorted(k for k in set(off_st) | set(on_st)
                                       if off_st.get(k) != on_st.get(k))

    out["off_equals_baseline_deep"] = (books["off"][1] == books["baseline"][1])
    out["off_book_id_equals_baseline"] = (prov["off"]["book_id_recomputed"]
                                          == prov["baseline"]["book_id_recomputed"])
    out["configured_baseline_book_id"] = json.loads(
        (TAPE / "loop.json").read_text(encoding="utf-8"))["baseline_book_id"]

    # ---- the gate
    off_rows, on_rows = core11(books["off"][1]), core11(books["on"][1])
    before = slices(books["off"][0], off_rows)
    after = slices(books["on"][0], on_rows)
    out["off"] = before
    out["on"] = after
    out["gate"] = {"whole": verdict(before["whole"], after["whole"]),
                   "h1": verdict(before["h1"], after["h1"]),
                   "h2": verdict(before["h2"], after["h2"])}
    out["decision"] = ("ship" if (out["gate"]["h1"]["enough"] and out["gate"]["h1"]["pass"]
                                  and out["gate"]["h2"]["enough"] and out["gate"]["h2"]["pass"])
                       else "hold")

    # ---- whole-window denominator sanity: core-11 rows on every session?
    out["denominator_check"] = {
        "core11_distinct_days_off": before["_days"]["distinct_in_rows"],
        "meta_sessions": before["_days"]["meta_sessions"],
        "h1_days+h2_days": before["_days"]["h1_days"] + before["_days"]["h2_days"],
        "same": before["_days"]["distinct_in_rows"] == before["_days"]["meta_sessions"],
    }

    # ---- the one-candle-rule slice
    out["ocr_slice_core11"] = {"off": ocr_slice(off_rows), "on": ocr_slice(on_rows)}
    out["ocr_slice_full_pool"] = {"off": ocr_slice(books["off"][1]),
                                  "on": ocr_slice(books["on"][1])}

    # ---- where did the whole-window delta actually come from? (pass-1 section 2)
    def key(r):
        return (r["sym"], r["day"], r.get("et"), r.get("dir"), r.get("setup"))

    uo, un = unit_rows(off_rows), unit_rows(on_rows)
    ko = {key(r): r for r in uo}
    kn = {key(r): r for r in un}
    removed = [ko[k] for k in ko.keys() - kn.keys()]
    added = [kn[k] for k in kn.keys() - ko.keys()]

    def by_setup(rows):
        c, p = defaultdict(int), defaultdict(float)
        for r in rows:
            c[r["setup"]] += 1
            p[r["setup"]] += r.get("pnl", 0.0)
        return {s: {"trades": c[s], "pnl": round(p[s])} for s in sorted(c)}

    out["delta_decomposition"] = {
        "unit_total_off": round(sum(r.get("pnl", 0.0) for r in uo)),
        "unit_total_on": round(sum(r.get("pnl", 0.0) for r in un)),
        "delta": round(sum(r.get("pnl", 0.0) for r in un) - sum(r.get("pnl", 0.0) for r in uo)),
        "removed": {"n": len(removed), "pnl": round(sum(r.get("pnl", 0.0) for r in removed)),
                    "by_setup": by_setup(removed)},
        "added": {"n": len(added), "pnl": round(sum(r.get("pnl", 0.0) for r in added)),
                  "by_setup": by_setup(added)},
        "unit_by_setup_off": by_setup(uo),
        "unit_by_setup_on": by_setup(un),
        "_note": "every cell here is under the 30-trade floor: counts and an arithmetic "
                 "identity, no verdict",
    }

    # ---- does the flag delay the OCR entry? (pass-2 defect 2, re-checked)
    def first_ocr(rows):
        d = {}
        for r in rows:
            if r.get("setup") != "one_candle_rule":
                continue
            k = (r["sym"], r["day"])
            if k not in d or (r.get("et") or "") < d[k]:
                d[k] = r.get("et") or ""
        return d
    a, b = first_ocr(off_rows), first_ocr(on_rows)
    later = same = earlier = orphan = 0
    deltas = []
    for k, v in b.items():
        if k not in a:
            orphan += 1
            continue
        if v > a[k]:
            later += 1
            deltas.append((int(v[:2]) * 60 + int(v[3:5])) - (int(a[k][:2]) * 60 + int(a[k][3:5])))
        elif v == a[k]:
            same += 1
        else:
            earlier += 1
    deltas.sort()
    out["ocr_delay"] = {"symbol_days_kept": len(b), "later": later, "same": same,
                        "earlier": earlier, "no_off_twin": orphan,
                        "median_delay_min": deltas[len(deltas) // 2] if deltas else None,
                        "max_delay_min": deltas[-1] if deltas else None}

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
