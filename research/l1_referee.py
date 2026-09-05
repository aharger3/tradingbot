"""L1 referee -- re-derive the MIN_PT1_R gate from the two stamped books.

Referee for row L1 (builder commit 842b3f3c, code commit e073b94a). Written to
REFUTE, so nothing here imports the builder's gate verdict: the trade unit, the
$/day, the mean R, the green months and the no-regression verdict are all
recomputed from `research/tape/book_MIN_PT1_R_{off,on}.json.gz` with arithmetic
written out longhand below, and only THEN compared against
`research/loop_cycle.py`'s own output and against `research/tape/cycles.md`.

Two universes are computed side by side, because that is the whole question:

  core11   rows with tier == "core" -- `research/tape/loop.json`'s
           `universe.row_filter`, and what `research/g212_trace.py` (R3, the
           baseline this gate is defined against) actually measures.
  full29   every row in the book -- what `research/loop_cycle.py::stage_gate`
           measures, because it never reads cfg["universe"].

Unit: up_to_3_stop_win_or_2loss (the spec's day policy), reimplemented here
rather than imported. Fill: close (`entry_fill.ENTRY_FILL`, stamped in both
books). Exit: the shipped engine -- 1R resting disaster stop on the intrabar
touch, SCALE_PLAN=hod_then_runner_be, LOSS_HALT on (stamped). Halves boundary
2025-09-01.

Run:  python research/l1_referee.py
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
MIN_TRADES, MIN_MONTHS = 30, 12
MAX_DROP_PCT = 5.0


def load(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def up_to_3(rows):
    """Up to 3 fired-and-traded signals a day in arrival order; stop after the
    first win or the second loss. Candidate pool = fired-and-traded plus the
    account-wide two-loss halt's own rows."""
    byday = {}
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday.setdefault(r["day"], []).append(r)
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


def figures(unit_rows, n_days):
    if not unit_rows or not n_days:
        return {"trades": 0, "per_day": 0.0, "mean_r": 0.0, "win_pct": 0.0,
                "months_green": 0, "months": 0, "avg_win": 0.0, "avg_loss": 0.0,
                "awal": None}
    pnls = [r["pnl"] for r in unit_rows]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    by_m = {}
    for r in unit_rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r["pnl"]
    total = sum(pnls)
    aw = round(sum(wins) / len(wins), 0) if wins else 0.0
    al = round(abs(sum(losses) / len(losses)), 0) if losses else 0.0
    return {
        "trades": len(unit_rows),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(unit_rows) / RISK, 4),
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (wins or losses) else 0.0,
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "avg_win": aw, "avg_loss": al,
        "awal": round(aw / al, 3) if al else None,
        "total": round(total, 0),
    }


def slice_book(meta, rows, core_only):
    rows = [r for r in rows if r.get("tier") == "core"] if core_only else rows
    days = sorted({r["day"] for r in rows if r.get("day")})
    n_all = meta.get("sessions") or len(days)
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    h1 = [r for r in rows if r.get("day", "") < BOUNDARY]
    h2 = [r for r in rows if r.get("day", "") >= BOUNDARY]
    return {"whole": figures(up_to_3(rows), n_all),
            "h1": figures(up_to_3(h1), n1),
            "h2": figures(up_to_3(h2), n2)}


def half_verdict(before, after):
    enough = before["trades"] >= MIN_TRADES and before["months"] >= MIN_MONTHS
    if not enough:
        return {"enough": False, "pass": None}
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        dollar_ok = a >= b * (1 - MAX_DROP_PCT / 100.0)
    elif b < 0:
        dollar_ok = a >= b * (1 + MAX_DROP_PCT / 100.0)
    else:
        dollar_ok = a >= 0
    return {"enough": True, "pass": bool(green_ok and dollar_ok),
            "green_ok": green_ok, "dollar_ok": dollar_ok}


def main():
    off_meta, off_rows = load(TAPE / "book_MIN_PT1_R_off.json.gz")
    on_meta, on_rows = load(TAPE / "book_MIN_PT1_R_on.json.gz")
    base_meta, base_rows = load(TAPE / "baseline_2026-09-05.json.gz")

    # --- stamp checks -----------------------------------------------------
    so, sn, sb = off_meta["stamp"], on_meta["stamp"], base_meta["stamp"]
    print("book_id  off=%s  on=%s  baseline=%s" % (
        so.get("book_id"), sn.get("book_id"), sb.get("book_id")))
    print("OFF book_id == baseline book_id:",
          so.get("book_id") == sb.get("book_id"))
    diff = {k: (so["flags"].get(k), sn["flags"].get(k))
            for k in set(so["flags"]) | set(sn["flags"])
            if so["flags"].get(k) != sn["flags"].get(k)}
    print("flag diff OFF->ON:", diff)
    print("dirty at build: off=%s on=%s (engine: %s / %s)" % (
        so["git"]["dirty_py_count"], sn["git"]["dirty_py_count"],
        so["git"]["dirty_engine_py"], sn["git"]["dirty_engine_py"]))
    print("commits: off=%s on=%s" % (so["git"]["commit"][:8], sn["git"]["commit"][:8]))
    print("rows: off=%d on=%d baseline=%d" % (len(off_rows), len(on_rows), len(base_rows)))

    # --- the gate, both universes ----------------------------------------
    for core_only, name in ((True, "core11 (loop.json universe.row_filter)"),
                            (False, "full29 (what loop_cycle.py actually gates on)")):
        before = slice_book(off_meta, off_rows, core_only)
        after = slice_book(on_meta, on_rows, core_only)
        h1v, h2v = half_verdict(before["h1"], after["h1"]), half_verdict(before["h2"], after["h2"])
        dec = "ship" if (h1v["enough"] and h1v["pass"] and h2v["enough"] and h2v["pass"]) else "hold"
        print("\n=== %s ===" % name)
        for k in ("whole", "h1", "h2"):
            print("  %-5s OFF %s" % (k, json.dumps(before[k], sort_keys=True)))
            print("  %-5s ON  %s" % (k, json.dumps(after[k], sort_keys=True)))
        print("  H1 verdict:", h1v, " H2 verdict:", h2v, " decision:", dec)

    # --- skip-reason accounting ------------------------------------------
    # The builder published these three figures ("9,283 / 1,082 / -0.065R")
    # from an ad hoc query it did NOT commit (SWARM law 5). Re-derived here.
    def key(r):
        return (r.get("sym"), r.get("day"), r.get("et"),
                round(r.get("entry", 0.0), 4), round(r.get("stop", 0.0), 4), r.get("dir"))

    offmap = {}
    for r in off_rows:
        offmap.setdefault(key(r), []).append(r)
    skipped = [r for r in on_rows if "MIN_PT1_R" in (r.get("reason") or "")]
    matched = []
    for r in skipped:
        for o in offmap.get(key(r), []):
            if o.get("traded"):
                matched.append(o)
                break
    rs = [m["r"] for m in matched if m.get("r") is not None]
    w = sum(1 for m in matched if m.get("pnl", 0) > 0)
    ls = sum(1 for m in matched if m.get("pnl", 0) < 0)
    print("\nON-book rows tagged MIN_PT1_R: %d of %d (core-11: %d)"
          % (len(skipped), len(on_rows),
             sum(1 for r in skipped if r.get("tier") == "core")))
    print("  ... that DID trade in the OFF book: %d (core-11: %d), mean R %.4f, "
          "win %.1f%% of all / %.1f%% of decided"
          % (len(matched), sum(1 for m in matched if m.get("tier") == "core"),
             sum(rs) / len(rs), w / len(matched) * 100, w / (w + ls) * 100))

    # --- the X_LIFT ordering hole ----------------------------------------
    # The gate sits BEFORE self._apply_x_lift() in _route and only fires on
    # grades outside _SKIP_GRADES, so an X-graded row that X_LIFT ("clean",
    # the shipped default) promotes to B is never tested by the RR gate. The
    # S_CLASSIFIER drop 25 lines below it is placed AFTER _apply_x_lift for
    # exactly this reason, with a comment saying so.
    lifted = [r for r in on_rows if "x-lift" in (r.get("reason") or "")]
    lifted_traded = [r for r in lifted if r.get("traded")]
    print("\nON-book x-lifted rows: %d, of which traded: %d (core-11 traded: %d)"
          % (len(lifted), len(lifted_traded),
             sum(1 for r in lifted_traded if r.get("tier") == "core")))
    print("  x-lifted rows ALSO carrying the MIN_PT1_R skip tag: %d"
          % sum(1 for r in lifted if "MIN_PT1_R" in (r.get("reason") or "")))


if __name__ == "__main__":
    main()
