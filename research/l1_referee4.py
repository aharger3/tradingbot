"""l1_referee4.py -- L1 (MIN_PT1_R) referee, pass 4. Independent re-derivation.

Written to REFUTE research/l1_min_pt1_r.md at builder commit f298369f.
Nothing here imports research/loop_cycle.py or research/g72_suppress_price.py:
the unit, the halves split, the month-green count, the $/day divisor and the
no-regression gate are all re-implemented from their written definitions
(SWARM.md law 2/3, omen-10-0-spec.md "The law for every row",
research/tape/loop.json) so that a bug shared by the builder's arithmetic and
the controller's arithmetic cannot hide.

Unit          : up_to_3_stop_win_or_2loss -- up to 3 fired-and-traded signals a
                day in arrival order (et, then sym), stop after the first win or
                after the second loss. Candidate pool = status "fired" AND
                traded, plus status "halted" (the account-wide two-loss halt's
                own rows), per loop.json's documented unit.
Universe      : loop.json universe.row_filter, tier == "core" (core 11).
Fill          : each book's own meta["entry_fill"] (close).
Exit          : the shipped engine (1R hard stop on the intrabar touch,
                SCALE_PLAN=hod_then_runner_be, LOSS_HALT on) -- read off the
                stamp, not assumed.
$/day         : whole window divides by meta["sessions"]; each half divides by
                the count of distinct days present in that half's rows (the
                controller's documented approximation, reproduced so the two
                are comparable).
1R            = $1,000.

usage: python research/l1_referee4.py
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
MAX_DROP_PCT = 5.0
MIN_TRADES, MIN_MONTHS = 30, 12


def load(name):
    with gzip.open(TAPE / name, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def core_only(rows):
    return [r for r in rows if r.get("tier") == "core"]


def up_to_3(rows):
    """Independent implementation of his day policy."""
    byday = {}
    for r in rows:
        fired_traded = r.get("status") == "fired" and r.get("traded")
        if fired_traded or r.get("status") == "halted":
            byday.setdefault(r["day"], []).append(r)
    out = []
    for day in sorted(byday):
        ordered = sorted(byday[day], key=lambda r: ((r.get("et") or ""), (r.get("sym") or "")))
        losses = 0
        for i, r in enumerate(ordered):
            if i >= 3:
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


def figures(unit_rows, n_days):
    if not unit_rows or not n_days:
        return {"trades": 0, "per_day": 0.0, "mean_r": 0.0, "months_green": 0,
                "months": 0, "win_pct": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
                "total": 0.0}
    pnls = [r.get("pnl", 0.0) for r in unit_rows]
    total = sum(pnls)
    by_m = {}
    for r in unit_rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r.get("pnl", 0.0)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    return {
        "trades": len(unit_rows),
        "per_day": round(total / n_days, 0),
        "total": round(total, 0),
        "mean_r": round(total / len(unit_rows) / RISK, 4),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (wins or losses) else 0.0,
        "avg_win": round(sum(wins) / len(wins), 0) if wins else 0.0,
        "avg_loss": round(abs(sum(losses) / len(losses)), 0) if losses else 0.0,
    }


def slice_all(meta, rows):
    n_all = meta.get("sessions") or len({r["day"] for r in rows})
    days = sorted({r["day"] for r in rows if r.get("day")})
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


def flag_diff(m_off, m_on):
    fo = (m_off.get("stamp") or {}).get("flags") or {}
    fn = (m_on.get("stamp") or {}).get("flags") or {}
    keys = sorted(set(fo) | set(fn))
    return {k: (fo.get(k, "<absent>"), fn.get(k, "<absent>"))
            for k in keys if fo.get(k, "<absent>") != fn.get(k, "<absent>")}


def report(tag, off_name, on_name, universe):
    m_off, r_off = load(off_name)
    m_on, r_on = load(on_name)
    if universe == "core11":
        r_off, r_on = core_only(r_off), core_only(r_on)
    before, after = slice_all(m_off, r_off), slice_all(m_on, r_on)
    h1v, h2v = half_verdict(before["h1"], after["h1"]), half_verdict(before["h2"], after["h2"])
    decision = "ship" if (h1v["enough"] and h1v["pass"] and h2v["enough"] and h2v["pass"]) else "hold"
    print("\n=== %s (%s) ===" % (tag, universe))
    print("  off=%s  on=%s" % (off_name, on_name))
    print("  off commit=%s dirty_py=%s | on commit=%s dirty_py=%s" % (
        (m_off.get("stamp") or {}).get("git", {}).get("commit", "?")[:8],
        (m_off.get("stamp") or {}).get("git", {}).get("dirty_py_count"),
        (m_on.get("stamp") or {}).get("git", {}).get("commit", "?")[:8],
        (m_on.get("stamp") or {}).get("git", {}).get("dirty_py_count")))
    print("  flag stamp diff off->on: %s" % json.dumps(flag_diff(m_off, m_on)))
    for k in ("whole", "h1", "h2"):
        b, a = before[k], after[k]
        print("  %-5s OFF trades=%4d $/day=%7.0f meanR=%+.4f green=%2d/%2d win=%.1f%%"
              % (k, b["trades"], b["per_day"], b["mean_r"], b["months_green"], b["months"], b["win_pct"]))
        print("  %-5s ON  trades=%4d $/day=%7.0f meanR=%+.4f green=%2d/%2d win=%.1f%%"
              % (k, a["trades"], a["per_day"], a["mean_r"], a["months_green"], a["months"], a["win_pct"]))
    print("  H1 %s  H2 %s  -> decision=%s" % (h1v, h2v, decision))
    return {"before": before, "after": after, "h1": h1v, "h2": h2v, "decision": decision}


def book_ids():
    from research.book_stamp import book_id
    out = {}
    for n in ("baseline_2026-09-05", "book_MIN_PT1_R_off", "book_MIN_PT1_R_on",
              "book_MIN_PT1_R_off_postfix", "book_MIN_PT1_R_on_postfix"):
        m, r = load(n + ".json.gz")
        stamped = (m.get("stamp") or {}).get("book_id")
        out[n] = {"stamped": stamped, "recomputed": book_id(r), "rows": len(r),
                  "traded": m.get("traded"), "signals": m.get("signals")}
    print("\n=== book_id ===")
    for k, v in out.items():
        ok = "OK" if v["stamped"] == v["recomputed"] else "MISMATCH"
        print("  %-32s stamped=%s recomputed=%s %s rows=%d traded=%s signals=%s"
              % (k, v["stamped"], v["recomputed"], ok, v["rows"], v["traded"], v["signals"]))
    return out


def semantics_from_raw_bars(n=40, seed=20260906):
    """Does the flag do what the rulebook sentence says?

    Austin, 2026-09-05: "RR gate: first scale point (HOD/LOD) must be >= 1R
    from entry." For a sample of rows in the ON book, recompute the session
    (RTH 09:30-16:00, premarket excluded -- polygon_feed.rth) high/low as of
    the signal bar straight from data_archive/<sym>/<day>.csv, and check that
    every MIN_PT1_R-tagged row has (HOD - entry) < 1R for a call / (entry -
    LOD) < 1R for a put, and that every fired-and-traded row does not."""
    import csv
    import random
    random.seed(seed)
    m, rows = load("book_MIN_PT1_R_on_postfix.json.gz")
    tagged = [r for r in rows if "MIN_PT1_R" in (r.get("reason") or "")]
    fired = [r for r in rows if r.get("status") == "fired" and r.get("traded")]
    picks = [("tagged", r) for r in random.sample(tagged, n)] + \
            [("fired", r) for r in random.sample(fired, n)]

    def session_extremes(sym, day, et):
        p = ROOT / "data_archive" / sym / (day + ".csv")
        if not p.exists():
            return None
        hi, lo = None, None
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ts = row["Datetime"][11:19]
                if ts < "09:30:00" or ts >= "16:00:00":
                    continue
                if ts > et + ":00":
                    break
                h, l = float(row["High"]), float(row["Low"])
                hi = h if hi is None else max(hi, h)
                lo = l if lo is None else min(lo, l)
        return hi, lo

    ok = bad = skipped = 0
    fails = []
    for kind, r in picks:
        ex = session_extremes(r["sym"], r["day"], r["et"])
        if not ex or ex[0] is None:
            skipped += 1
            continue
        hi, lo = ex
        risk = abs(r["entry"] - r["stop"])
        dist = (hi - r["entry"]) if r["dir"] == "call" else (r["entry"] - lo)
        want_under = (kind == "tagged")
        got_under = dist < risk
        if want_under == got_under:
            ok += 1
        else:
            bad += 1
            fails.append((kind, r["sym"], r["day"], r["et"], r["dir"],
                          round(dist, 4), round(risk, 4)))
    print("\n=== semantics against raw archived bars ===")
    print("  %d/%d agree with the rulebook sentence (%d unreadable), %d disagree"
          % (ok, ok + bad, skipped, bad))
    for f in fails[:10]:
        print("   MISMATCH", f)
    return ok, bad, skipped


if __name__ == "__main__":
    ids = book_ids()
    semantics_from_raw_bars()
    res = {}
    for uni in ("core11", "full29"):
        res[("pre", uni)] = report("pre-x_lift-move books (e073b94a)",
                                   "book_MIN_PT1_R_off.json.gz",
                                   "book_MIN_PT1_R_on.json.gz", uni)
        res[("post", uni)] = report("post-x_lift-move books (d062da84)",
                                    "book_MIN_PT1_R_off_postfix.json.gz",
                                    "book_MIN_PT1_R_on_postfix.json.gz", uni)
