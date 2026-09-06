"""l2_referee2.py -- SECOND-PASS independent re-derivation of row L2 (RULE84_DECIDED).

Referee pass 2, for builder repair commit d317ff43 (pass-1 refutation 4f819bf6,
original hold 5306416e, flag-OFF landing 7fb977f7).

This file deliberately does NOT import research/loop_cycle.py,
research/g72_suppress_price.py, or research/l2_referee.py (pass 1's script).
The day-policy unit, the session/month arithmetic, the no-regression gate and
the funnel counts are re-typed here from the spec sentence so that neither the
builder's rig nor pass 1's checker can reproduce its own bug in the check.

Unit:  up_to_3_stop_win_or_2loss -- up to 3 fired-and-traded signals a day in
       arrival order (et, then symbol), stop after the first win or the second
       loss. Candidate pool = fired-and-traded rows plus `status == "halted"`
       rows (the account-wide two-loss halt sits downstream of this unit's own
       stop rule; excluding them would silently erase the rest of a day).
Fill:  close (both books stamp entry_fill == "close").
Exit:  shipped engine -- 1R hard stop resting on the level, filled on the
       intrabar touch (DISASTER_STOP_R = 1.0); SCALE_PLAN = hod_then_runner_be;
       LOSS_HALT on. Read off the books' own stamps, not assumed.
Books: research/tape/book_RULE84_DECIDED_{off,on}.json.gz.
1R = $1,000 (CLAUDE.md).

    python research/l2_referee2.py
"""
from __future__ import annotations

import gzip
import json
import re
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


# ------------------------------------------------------------------- the unit

def day_policy(rows):
    byday = {}
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday.setdefault(r["day"], []).append(r)
    picked = []
    for day in sorted(byday):
        losses = 0
        for n, r in enumerate(sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or ""))):
            if n >= 3:
                break
            picked.append(r)
            p = r.get("pnl", 0.0)
            if p > 0:
                break
            if p < 0:
                losses += 1
                if losses >= 2:
                    break
    return picked


def stats(unit_rows, n_days):
    if not unit_rows or not n_days:
        return {"trades": 0, "total": 0.0, "per_day": 0.0, "mean_r": 0.0,
                "green": 0, "months": 0, "win_pct": 0.0, "avg_win": 0.0, "avg_loss": 0.0}
    total = sum(r["pnl"] for r in unit_rows)
    by_m = {}
    for r in unit_rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r["pnl"]
    wins = [r["pnl"] for r in unit_rows if r["pnl"] > 0]
    losses = [r["pnl"] for r in unit_rows if r["pnl"] < 0]
    return {
        "trades": len(unit_rows),
        "total": round(total, 0),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(unit_rows) / RISK, 4),
        "green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (wins or losses) else 0.0,
        "avg_win": round(sum(wins) / len(wins), 0) if wins else 0.0,
        "avg_loss": round(abs(sum(losses) / len(losses)), 0) if losses else 0.0,
    }


def three_slices(meta, rows):
    days = sorted({r["day"] for r in rows if r.get("day")})
    n_all = meta.get("sessions") or len(days)
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    return {
        "whole": stats(day_policy(rows), n_all),
        "h1": stats(day_policy([r for r in rows if r.get("day", "") < BOUNDARY]), n1),
        "h2": stats(day_policy([r for r in rows if r.get("day", "") >= BOUNDARY]), n2),
        "_sessions": (n_all, n1, n2),
    }


def gate(before, after):
    if before["trades"] < MIN_TRADES or before["months"] < MIN_MONTHS:
        return "not enough"
    green_ok = after["green"] >= before["green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        dollar_ok = a >= b * (1 - MAX_DROP_PCT / 100.0)
    elif b < 0:
        dollar_ok = a >= b * (1 + MAX_DROP_PCT / 100.0)
    else:
        dollar_ok = a >= 0
    return "pass" if (green_ok and dollar_ok) else "fail"


def table(tag, off, on):
    print("\n== %s ==   sessions whole/h1/h2 = %s" % (tag, off["_sessions"]))
    print("%-6s %7s %10s %10s %9s %9s %10s %10s %8s"
          % ("slice", "trades", "$/day off", "$/day on", "green off", "green on",
             "meanR off", "meanR on", "gate"))
    for k in ("whole", "h1", "h2"):
        g = gate(off[k], on[k]) if k in ("h1", "h2") else "-"
        print("%-6s %7d %10s %10s %9s %9s %10s %10s %8s"
              % (k, off[k]["trades"], off[k]["per_day"], on[k]["per_day"],
                 "%d/%d" % (off[k]["green"], off[k]["months"]),
                 "%d/%d" % (on[k]["green"], on[k]["months"]),
                 off[k]["mean_r"], on[k]["mean_r"], g))
    ship = gate(off["h1"], on["h1"]) == "pass" and gate(off["h2"], on["h2"]) == "pass"
    print("decision: %s" % ("SHIP" if ship else "HOLD"))
    return ship


# ------------------------------------------------------------------- the funnel

def funnel(rows, label, tier=None):
    sel = [r for r in rows if r.get("setup") == "reentry_84_rule"]
    if tier:
        sel = [r for r in sel if r.get("tier") == tier]
    fired = [r for r in sel if r.get("status") == "fired"]
    traded = [r for r in sel if r.get("traded")]
    all_fired = [r for r in rows if r.get("status") == "fired"] if not tier else \
        [r for r in rows if r.get("status") == "fired" and r.get("tier") == tier]
    all_traded = [r for r in rows if r.get("traded")] if not tier else \
        [r for r in rows if r.get("traded") and r.get("tier") == tier]
    mr = (sum(r["pnl"] for r in traded) / len(traded) / RISK) if traded else 0.0
    print("%-22s rows(any status) %4d  fired %4d  traded %3d  meanR %+.4f  "
          "share-of-fired %.2f%%  share-of-traded %.2f%%"
          % (label, len(sel), len(fired), len(traded), mr,
             100.0 * len(fired) / len(all_fired) if all_fired else 0.0,
             100.0 * len(traded) / len(all_traded) if all_traded else 0.0))
    return len(sel), len(fired), len(traded)


# ------------------------------------------------------------------- config filter

def row_filter(rows, cfg):
    u = (cfg or {}).get("universe") or {}
    expr = u.get("row_filter")
    if not expr:
        return rows
    m = re.match(r'^\s*(\w+)\s*==\s*"([^"]*)"\s*$', expr)
    if not m:
        raise SystemExit("unsupported row_filter %r" % expr)
    return [r for r in rows if r.get(m.group(1)) == m.group(2)]


def main():
    off_meta, off_rows = load(TAPE / "book_RULE84_DECIDED_off.json.gz")
    on_meta, on_rows = load(TAPE / "book_RULE84_DECIDED_on.json.gz")
    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))

    print("== stamps ==")
    for nm, m in (("OFF", off_meta), ("ON", on_meta)):
        s = m["stamp"]
        print("%-4s book_id %s  commit %s  dirty_py %s  dirty_engine %s  window %s..%s  "
              "sessions %s  built_at %s  script %s"
              % (nm, s.get("book_id"), s["git"]["commit"][:8], s["git"]["dirty_py_count"],
                 s["git"].get("dirty_engine_py"), m.get("first"), m.get("last"),
                 m.get("sessions"), s.get("built_at"), s.get("script") or s.get("argv")))
    print("baseline_book_id (loop.json) %s   OFF matches: %s"
          % (cfg["baseline_book_id"], off_meta["stamp"]["book_id"] == cfg["baseline_book_id"]))
    fo, fn = off_meta["stamp"]["flags"], on_meta["stamp"]["flags"]
    diffs = {k: (fo.get(k), fn.get(k)) for k in set(fo) | set(fn) if fo.get(k) != fn.get(k)}
    print("flag diffs OFF->ON (%d): %s" % (len(diffs), diffs))
    print("entry_fill stamp: OFF %r  ON %r"
          % (fo.get("entry_fill.ENTRY_FILL"), fn.get("entry_fill.ENTRY_FILL")))
    print("row counts: OFF %d  ON %d" % (len(off_rows), len(on_rows)))

    off_core, on_core = row_filter(off_rows, cfg), row_filter(on_rows, cfg)
    print("core-11 rows: OFF %d  ON %d   (filter %r)"
          % (len(off_core), len(on_core), cfg["universe"]["row_filter"]))
    syms_core = sorted({r["sym"] for r in off_core})
    print("core-11 symbols in book: %s" % syms_core)
    print("config symbols           : %s" % sorted(cfg["universe"]["symbols"]))
    print("match: %s" % (syms_core == sorted(cfg["universe"]["symbols"])))
    print("all symbols in book (%d): %s"
          % (len({r["sym"] for r in off_rows}), sorted({r["sym"] for r in off_rows})))

    full = (three_slices(off_meta, off_rows), three_slices(on_meta, on_rows))
    core = (three_slices(off_meta, off_core), three_slices(on_meta, on_core))
    table("FULL POOL (every symbol in the book)", *full)
    table("CORE 11 (tier == 'core') -- the configured lane", *core)

    print("\n== reconciliation against loop.json baseline_figures (R3) ==")
    b = cfg["baseline_figures"]
    for k in ("whole", "h1", "h2"):
        e, g = b[k], core[0][k]
        ok = (e["trades"] == g["trades"] and e["per_day"] == g["per_day"]
              and e["months_green"] == g["green"])
        print("%-6s R3 %4dtr %6s$/day %2dgreen  |  here %4dtr %6s$/day %2dgreen  | %s"
              % (k, e["trades"], e["per_day"], e["months_green"],
                 g["trades"], g["per_day"], g["green"], "MATCH" if ok else "MISMATCH"))

    print("\n== the 84%% funnel ==")
    funnel(off_rows, "OFF full pool")
    funnel(on_rows, "ON  full pool")
    funnel(off_rows, "OFF core-11", tier="core")
    funnel(on_rows, "ON  core-11", tier="core")

    print("\n== cycles.md row check ==")
    txt = (TAPE / "cycles.md").read_text(encoding="utf-8")
    rows84 = [l for l in txt.splitlines() if "RULE84_DECIDED" in l and l.startswith("|")]
    print("RULE84_DECIDED table rows in cycles.md: %d" % len(rows84))
    for l in rows84:
        print("  " + l.strip())
    st = json.loads((TAPE / "loop_state.json").read_text(encoding="utf-8"))
    print("loop_state cycle=%s consecutive_holds=%s history_len=%s flags=%s"
          % (st.get("cycle"), st.get("consecutive_holds"), len(st.get("history", [])),
             [h.get("flag") for h in st.get("history", [])]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
