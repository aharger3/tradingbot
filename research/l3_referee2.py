"""L3 referee, pass 2 -- independent re-derivation of the OCR_RETEST_DISPLACEMENT gate.

Written by the second-pass referee (a different model from the builder AND from
the pass-1 referee) with one instruction: refute. It therefore imports NOTHING
from `research/loop_cycle.py`, `research/g72_suppress_price.py` or
`research/l3_referee.py` -- the unit, the halves split, months-green, $/day and
the no-regression gate are all re-typed here from the spec's wording so that a
bug in the shared arithmetic cannot hide behind itself.

Unit: up_to_3_stop_win_or_2loss (his day policy -- up to 3 fired-and-traded
signals a day, stop after the first win or the second loss).
Fill: honest close (`ENTRY_FILL=close`, read back out of each book's stamp).
Exit: the shipped engine ladder (1R hard stop on the intrabar touch,
SCALE_PLAN=hod_then_runner_be, loss halt on) -- also read back out of the stamp.
Universe: core 11 (`tier == "core"`, loop.json's row_filter).
1R = $1,000. Window and session count come from each book's own meta.

Usage:  python research/l3_referee2.py            # prints one JSON blob
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"
BOUNDARY = "2025-09-01"
MAX_DROP_PCT = 5.0
MIN_TRADES = 30
MIN_MONTHS = 12


def load(path):
    p = str(path)
    op = gzip.open if p.endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def core(rows):
    return [r for r in rows if r.get("tier") == "core"]


def unit_rows(rows):
    """His day policy, re-typed from the spec sentence 'up to 3 S fires; stop
    after a win or after 2 losses'. Candidate pool = fired-and-traded rows plus
    the account-wide halt rows (a halt this unit would not itself have reached
    must not silently erase the rest of the day)."""
    byday = defaultdict(list)
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        losses = 0
        for r in sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or ""))[:3]:
            out.append(r)
            pnl = r.get("pnl", 0.0)
            if pnl > 0:
                break
            if pnl < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


def months_green(rows):
    """A calendar month is green when the unit's dollars for that month are > 0."""
    by = defaultdict(float)
    for r in rows:
        by[r["day"][:7]] += r.get("pnl", 0.0)
        pass
    return sum(1 for v in by.values() if v > 0), len(by)


def figures(all_rows, slice_rows, n_days_override=None):
    u = unit_rows(slice_rows)
    total = sum(r.get("pnl", 0.0) for r in u)
    n_days = n_days_override if n_days_override is not None else \
        len({r["day"] for r in slice_rows if r.get("day")})
    g, m = months_green(u)
    wins = [r["pnl"] for r in u if r.get("pnl", 0) > 0]
    losses = [-r["pnl"] for r in u if r.get("pnl", 0) < 0]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = sum(losses) / len(losses) if losses else 0.0
    return {
        "trades": len(u),
        "total": round(total, 0),
        "n_days": n_days,
        "per_day": round(total / n_days, 0) if n_days else 0.0,
        "mean_r": round(sum(r.get("r", 0.0) or 0.0 for r in u) / len(u), 4) if u else 0.0,
        "win_pct": round(100.0 * len(wins) / len(u), 1) if u else 0.0,
        "months": m,
        "months_green": g,
        "avg_win": round(aw, 0),
        "avg_loss": round(al, 0),
        "awal": round(aw / al, 3) if al else None,
        "fires_per_day": round(len(u) / n_days, 3) if n_days else 0.0,
    }


def gate_half(before, after):
    enough = before["trades"] >= MIN_TRADES and before["months"] >= MIN_MONTHS
    if not enough:
        return {"enough": False, "pass": None}
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        floor = b * (1 - MAX_DROP_PCT / 100.0)
    elif b < 0:
        floor = b * (1 + MAX_DROP_PCT / 100.0)
    else:
        floor = 0.0
    return {"enough": True,
            "pass": bool(after["months_green"] >= before["months_green"] and a >= floor),
            "green": "%s -> %s" % (before["months_green"], after["months_green"]),
            "per_day": "%s -> %s (floor %.1f)" % (b, a, floor)}


def slice_of(rows, half):
    if half == "whole":
        return rows
    if half == "h1":
        return [r for r in rows if r.get("day", "") < BOUNDARY]
    return [r for r in rows if r.get("day", "") >= BOUNDARY]


def ocr_slice(rows):
    o = [r for r in rows if r.get("setup") == "one_candle_rule"]
    traded = [r for r in o if r.get("traded")]
    mr = round(sum(r.get("r", 0.0) or 0.0 for r in traded) / len(traded), 4) if traded else None
    return {"rows": len(o), "traded": len(traded), "mean_r_traded": mr}


def book_fingerprint(rows):
    """A fingerprint of my own, deliberately NOT research/book_stamp.book_id:
    the sorted (day, sym, entry-minute, side, pnl) tuple of every fired row."""
    import hashlib
    h = hashlib.sha256()
    for t in sorted((r.get("day"), r.get("sym"), r.get("et"), r.get("side"),
                     round(r.get("pnl", 0.0) or 0.0, 4))
                    for r in rows if r.get("status") == "fired"):
        h.update(repr(t).encode())
    return h.hexdigest()[:16]


def main():
    out = {}
    books = {
        "baseline": TAPE / "baseline_2026-09-05.json.gz",
        "off": TAPE / "book_OCR_RETEST_DISPLACEMENT_off.json.gz",
        "on": TAPE / "book_OCR_RETEST_DISPLACEMENT_on.json.gz",
    }
    metas, rowsets = {}, {}
    for k, p in books.items():
        metas[k], rowsets[k] = load(p)

    # --- identity, my own fingerprint, not book_stamp's ---------------------
    out["identity"] = {
        "baseline_stamp_book_id": metas["baseline"]["stamp"].get("book_id"),
        "off_stamp_book_id": metas["off"]["stamp"].get("book_id"),
        "on_stamp_book_id": metas["on"]["stamp"].get("book_id"),
        "my_fingerprint_baseline": book_fingerprint(rowsets["baseline"]),
        "my_fingerprint_off": book_fingerprint(rowsets["off"]),
        "my_fingerprint_on": book_fingerprint(rowsets["on"]),
        "rows": {k: len(v) for k, v in rowsets.items()},
        "off_rows_equal_baseline_rows": rowsets["off"] == rowsets["baseline"],
    }

    # --- the stamps differ in exactly one flag ------------------------------
    fo, fn = metas["off"]["stamp"].get("flags", {}), metas["on"]["stamp"].get("flags", {})
    diff = sorted(set(fo) | set(fn))
    diff = [k for k in diff if fo.get(k) != fn.get(k)]
    out["stamp_flag_diff"] = {"keys": diff,
                              "off": {k: fo.get(k) for k in diff},
                              "on": {k: fn.get(k) for k in diff}}
    nonflag = {}
    for k in ("commit", "dirty_engine_py", "entry_fill", "window", "script", "date",
              "dirty_py_count", "built_at"):
        if metas["off"]["stamp"].get(k) != metas["on"]["stamp"].get(k):
            nonflag[k] = [metas["off"]["stamp"].get(k), metas["on"]["stamp"].get(k)]
    out["stamp_nonflag_diff"] = nonflag
    out["stamps"] = {k: {kk: metas[k]["stamp"].get(kk) for kk in
                         ("commit", "dirty", "dirty_py_count", "dirty_engine_py",
                          "built_at", "script", "window", "book_id")}
                     for k in ("baseline", "off", "on")}
    out["meta_window"] = {k: {"first": metas[k].get("first"), "last": metas[k].get("last"),
                              "sessions": metas[k].get("sessions"),
                              "entry_fill": metas[k].get("entry_fill")}
                          for k in ("baseline", "off", "on")}

    # --- the gate, both ways of counting sessions ---------------------------
    for arm in ("off", "on"):
        rows = core(rowsets[arm])
        sess = metas[arm].get("sessions")
        out.setdefault("figures_meta_sessions", {})[arm] = {
            h: figures(rows, slice_of(rows, h),
                       n_days_override=(sess if h == "whole" else None))
            for h in ("whole", "h1", "h2")}
        out.setdefault("figures_core_days", {})[arm] = {
            h: figures(rows, slice_of(rows, h)) for h in ("whole", "h1", "h2")}
        out.setdefault("ocr", {})[arm] = ocr_slice(rows)
        out.setdefault("ocr_full_pool", {})[arm] = ocr_slice(rowsets[arm])

    for style in ("figures_meta_sessions", "figures_core_days"):
        out.setdefault("gate", {})[style] = {
            h: gate_half(out[style]["off"][h], out[style]["on"][h])
            for h in ("whole", "h1", "h2")}
        g = out["gate"][style]
        out["gate"][style]["decision"] = (
            "ship" if (g["h1"]["enough"] and g["h1"]["pass"]
                       and g["h2"]["enough"] and g["h2"]["pass"]) else "hold")

    json.dump(out, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
