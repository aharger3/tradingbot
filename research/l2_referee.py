"""l2_referee.py -- independent re-derivation of row L2's gate (RULE84_DECIDED).

Referee for builder commit 5306416e (flag landed OFF at 7fb977f7). Nothing here
imports research/loop_cycle.py or research/g72_suppress_price.py: the day-policy
unit, the month/half arithmetic and the no-regression gate are re-typed from the
spec's own words so a bug in the builder's rig cannot reproduce itself in the
check.

Unit:   up_to_3_stop_win_or_2loss -- up to 3 fired-and-traded signals a day in
        arrival order, stop after the first win or the second loss.
Fill:   close (both books stamp entry_fill == "close").
Exit:   shipped engine (1R hard stop, DISASTER_STOP_R=1.0, SCALE_PLAN=
        hod_then_runner_be, LOSS_HALT on) -- read off the books' own stamps.
Books:  research/tape/book_RULE84_DECIDED_{off,on}.json.gz, both built at
        7fb977f7, window 2024-09-04..2026-09-04, 499 sessions.
1R = $1,000.

The one thing this script tests that the builder's rig does not: the config
(research/tape/loop.json) declares universe.row_filter == 'tier == "core"'
(core 11), and loop_cycle.py never applies it. So every slice is printed twice
-- once on the full 28-symbol pool (what the builder actually measured) and once
on the core-11 rows (what the config, the spec and the report all say the unit
runs on).

    python research/l2_referee.py
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
MAX_DROP_PCT = 5.0
MIN_TRADES, MIN_MONTHS = 30, 12


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def day_policy_rows(rows):
    """Up to 3 fired-and-traded signals a day, arrival order, stop after the
    first win or the second loss. Halted rows stay in the candidate pool (the
    account-wide two-loss halt is downstream of this unit's own stop rule)."""
    byday = {}
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday.setdefault(r["day"], []).append(r)
    out = []
    for day in sorted(byday):
        taken = losses = 0
        for r in sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or "")):
            if taken >= 3:
                break
            out.append(r)
            taken += 1
            p = r.get("pnl", 0.0)
            if p > 0:
                break
            if p < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


def figures(unit_rows, n_days):
    if not unit_rows or not n_days:
        return {"trades": 0, "total": 0.0, "per_day": 0.0, "mean_r": 0.0,
                "months_green": 0, "months": 0, "win_pct": 0.0}
    total = sum(r["pnl"] for r in unit_rows)
    by_m = {}
    for r in unit_rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r["pnl"]
    wins = sum(1 for r in unit_rows if r["pnl"] > 0)
    losses = sum(1 for r in unit_rows if r["pnl"] < 0)
    return {
        "trades": len(unit_rows),
        "total": round(total, 0),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(unit_rows) / RISK, 4),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
    }


def slices(meta, rows):
    """whole / h1 / h2 figures on the day-policy unit, sessions counted the way
    loop_cycle.py counts them (meta sessions for the whole window, distinct day
    values either side of the boundary for the halves)."""
    days = sorted({r["day"] for r in rows if r.get("day")})
    n_all = meta.get("sessions") or len(days)
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    h1 = [r for r in rows if r.get("day", "") < BOUNDARY]
    h2 = [r for r in rows if r.get("day", "") >= BOUNDARY]
    return {"whole": figures(day_policy_rows(rows), n_all),
            "h1": figures(day_policy_rows(h1), n1),
            "h2": figures(day_policy_rows(h2), n2)}


def half_gate(before, after):
    """Green months may not fall; $/day may not fall more than 5%. A negative
    baseline reads as 'the loss may not get more than 5% worse'."""
    if before["trades"] < MIN_TRADES or before["months"] < MIN_MONTHS:
        return "not enough"
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        dollar_ok = a >= b * (1 - MAX_DROP_PCT / 100.0)
    elif b < 0:
        dollar_ok = a >= b * (1 + MAX_DROP_PCT / 100.0)
    else:
        dollar_ok = a >= 0
    return "pass" if (green_ok and dollar_ok) else "fail"


def show(tag, off, on):
    print("\n== %s ==" % tag)
    print("%-6s %7s %9s %9s %9s %9s %6s" %
          ("slice", "trades", "$/day off", "$/day on", "green off", "green on", "gate"))
    for k in ("whole", "h1", "h2"):
        g = half_gate(off[k], on[k]) if k in ("h1", "h2") else "-"
        print("%-6s %7d %9s %9s %9s %9s %6s" % (
            k, off[k]["trades"], off[k]["per_day"], on[k]["per_day"],
            "%d/%d" % (off[k]["months_green"], off[k]["months"]),
            "%d/%d" % (on[k]["months_green"], on[k]["months"]), g))
    ship = (half_gate(off["h1"], on["h1"]) == "pass"
            and half_gate(off["h2"], on["h2"]) == "pass")
    print("decision: %s" % ("SHIP" if ship else "HOLD"))
    return ship


def funnel(rows, label):
    f = [r for r in rows if r.get("setup") == "reentry_84_rule"]
    fired = [r for r in f if r.get("status") == "fired"]
    traded = [r for r in f if r.get("traded")]
    mr = (sum(r["pnl"] for r in traded) / len(traded) / RISK) if traded else 0.0
    core_f = [r for r in fired if r.get("tier") == "core"]
    core_t = [r for r in traded if r.get("tier") == "core"]
    print("%-4s 84%%-rule rows %4d  fired %4d  traded %3d  mean R %.4f  | core-11 fired %3d traded %2d"
          % (label, len(f), len(fired), len(traded), mr, len(core_f), len(core_t)))
    return len(fired), len(traded)


def main():
    off_meta, off_rows = load(TAPE / "book_RULE84_DECIDED_off.json.gz")
    on_meta, on_rows = load(TAPE / "book_RULE84_DECIDED_on.json.gz")
    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))

    print("OFF book_id %s   ON book_id %s   baseline_book_id %s" % (
        off_meta["stamp"]["book_id"], on_meta["stamp"]["book_id"], cfg["baseline_book_id"]))
    print("OFF commit %s  dirty_py %s   ON commit %s  dirty_py %s" % (
        off_meta["stamp"]["git"]["commit"][:8], off_meta["stamp"]["git"]["dirty_py_count"],
        on_meta["stamp"]["git"]["commit"][:8], on_meta["stamp"]["git"]["dirty_py_count"]))
    fo, fn = off_meta["stamp"]["flags"], on_meta["stamp"]["flags"]
    diffs = {k: (fo.get(k), fn.get(k)) for k in set(fo) | set(fn) if fo.get(k) != fn.get(k)}
    print("flag diffs OFF->ON: %s" % diffs)
    print("config universe: %s  row_filter %r" % (
        cfg["universe"]["slice"], cfg["universe"]["row_filter"]))

    off_all, on_all = slices(off_meta, off_rows), slices(on_meta, on_rows)
    core_off = [r for r in off_rows if r.get("tier") == "core"]
    core_on = [r for r in on_rows if r.get("tier") == "core"]
    off_core, on_core = slices(off_meta, core_off), slices(on_meta, core_on)

    show("FULL POOL (28 symbols) -- what loop_cycle.py actually measured", off_all, on_all)
    show("CORE 11 (tier == 'core') -- what the config, the spec and the report name",
         off_core, on_core)

    print("\n== R3 baseline reconciliation (research/tape/loop.json baseline_figures) ==")
    b = cfg["baseline_figures"]
    for k in ("whole", "h1", "h2"):
        exp = b[k]
        print("%-6s R3: trades %4d $/day %5s green %s   |  core-11 OFF here: trades %4d $/day %5s green %d"
              % (k, exp["trades"], exp["per_day"],
                 ("%d/%d" % (exp["months_green"], exp["months"])) if "months" in exp else exp["months_green"],
                 off_core[k]["trades"], off_core[k]["per_day"], off_core[k]["months_green"]))
    print("%-6s R3: trades %4d $/day %5s  |  FULL-pool OFF here: trades %4d $/day %5s"
          % ("whole", b["whole"]["trades"], b["whole"]["per_day"],
             off_all["whole"]["trades"], off_all["whole"]["per_day"]))

    print("\n== the 84%% funnel ==")
    funnel(off_rows, "OFF")
    funnel(on_rows, "ON")


if __name__ == "__main__":
    sys.exit(main())
