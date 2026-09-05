"""l1_referee2.py -- SECOND-PASS referee for OMEN 10.0 row L1 (MIN_PT1_R).

Independent re-derivation. Nothing here imports research/loop_cycle.py or
research/g72_suppress_price.py or research/l1_referee.py: the day-policy unit,
the month bucketing, the green-month count and $/day are all written out
longhand below so that a bug shared by the builder's script and the first
referee's script cannot hide in both. 1R = $1,000 (CLAUDE.md).

Every dollar this file prints:
    fill   = close (market at the close of the signal bar, ENTRY_FILL default)
    exit   = shipped engine, 1R hard stop resting at exactly 1R filled on the
             intrabar touch, SCALE_PLAN=hod_then_runner_be, LOSS_HALT on
    unit   = up_to_3_stop_win_or_2loss (up to 3 fired-and-traded signals a day
             in arrival order; stop after the first win or the second loss)
    window = the books' own stamp window, 2024-09-04..2026-09-04, 499 sessions
    script = this file

    python research/l1_referee2.py            # the tables, on the row's books
    python research/l1_referee2.py --stamps   # stamp diff + book ids only
    python research/l1_referee2.py --postfix  # same, on the PAIR REBUILT at
                                              # d062da84 (the repair commit),
                                              # which is what the code in the
                                              # tree actually produces today

REBUILD COMMAND (the --postfix pair; run at the repair commit, Saturday
2026-09-05, archive last session 2026-09-04 so the 730-day window is the
books' own 499 sessions):

    PYTHONIOENCODING=utf-8 python backtest_2y.py --days 730 \\
        --out research/tape/l1ref2_off_tmp.json                  # OFF arm
    PYTHONIOENCODING=utf-8 MIN_PT1_R=1.0 python backtest_2y.py --days 730 \\
        --out research/tape/l1ref2_on_tmp.json                   # ON arm
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RISK = 1000.0
BOUNDARY = "2025-09-01"
TAPE = ROOT / "research" / "tape"
OFF = TAPE / "book_MIN_PT1_R_off.json.gz"
ON = TAPE / "book_MIN_PT1_R_on.json.gz"
POSTFIX_OFF = TAPE / "book_MIN_PT1_R_off_postfix.json.gz"
POSTFIX_ON = TAPE / "book_MIN_PT1_R_on_postfix.json.gz"
BASELINE = TAPE / "baseline_2026-09-05.json.gz"


def load(path):
    path = str(path)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


# ------------------------------------------------------ the unit, written out
def up_to_3(rows):
    """His day policy. Candidate pool = fired-and-traded rows plus the rows the
    account-wide two-loss halt blocked (a halt this unit's own stop rule would
    not have reached yet must not erase the rest of the day). Arrival order is
    (et, sym)."""
    byday = defaultdict(list)
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        losses = 0
        for i, r in enumerate(sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or ""))):
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
        return {"trades": 0, "per_day": 0.0, "mean_r": 0.0, "win_pct": 0.0,
                "months_green": 0, "months": 0, "avg_win": 0.0, "avg_loss": 0.0,
                "awal": None, "total": 0.0}
    pnls = [r.get("pnl", 0.0) for r in unit_rows]
    total = sum(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    bym = defaultdict(float)
    for r in unit_rows:
        bym[r["day"][:7]] += r.get("pnl", 0.0)
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(losses) / len(losses)) if losses else 0.0
    return {
        "trades": len(unit_rows),
        "total": round(total, 0),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(unit_rows) / RISK, 4),
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (wins or losses) else 0.0,
        "months_green": sum(1 for v in bym.values() if v > 0),
        "months": len(bym),
        "avg_win": round(aw, 0),
        "avg_loss": round(al, 0),
        "awal": round(aw / al, 3) if al else None,
    }


def slice_book(meta, rows, core_only):
    """whole / h1 / h2 figures. n_days for the whole window is the book's own
    session count; for a half it is the number of distinct day values on that
    side (loop_cycle.py's approximation, reproduced deliberately so the two
    tables are comparable)."""
    pool = [r for r in rows if (not core_only or r.get("tier") == "core")]
    days = sorted({r["day"] for r in rows if r.get("day")})
    n_all = meta.get("sessions") or len(days)
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    h1 = [r for r in pool if r.get("day", "") < BOUNDARY]
    h2 = [r for r in pool if r.get("day", "") >= BOUNDARY]
    return {"whole": figures(up_to_3(pool), n_all),
            "h1": figures(up_to_3(h1), n1),
            "h2": figures(up_to_3(h2), n2),
            "fires_per_day": round(len(up_to_3(pool)) / n_all, 3) if n_all else 0.0}


def gate(before, after, max_drop_pct=5.0):
    """SWARM law 2 on one half. A negative baseline's '$/day may not fall more
    than 5%' reads as 'the loss may not get more than 5% worse'."""
    enough = before["trades"] >= 30 and before["months"] >= 12
    if not enough:
        return {"enough": False, "pass": None}
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        dollar_ok = a >= b * 0.95
    elif b < 0:
        dollar_ok = a >= b * 1.05
    else:
        dollar_ok = a >= 0
    return {"enough": True, "pass": bool(green_ok and dollar_ok),
            "green_ok": green_ok, "dollar_ok": dollar_ok}


# --------------------------------------------------------------- skip accounting
def skip_slice(off_rows, on_rows):
    """How many ON-book signals carry the MIN_PT1_R skip reason, how many of
    them actually traded in the OFF book, and what that slice returned."""
    # The gate appends its tag to the row's free-text `reason`; `status` is
    # normalised to "skipped_tight_stop" by the book writer, so `reason` is the
    # only field that identifies these rows.
    tagged = [r for r in on_rows if "MIN_PT1_R" in str(r.get("reason"))]
    key = lambda r: (r.get("sym"), r.get("day"), r.get("et"), r.get("entry"),
                     r.get("stop"), r.get("dir"))
    off_traded = {key(r): r for r in off_rows if r.get("traded")}
    hit = [off_traded[key(r)] for r in tagged if key(r) in off_traded]
    pnls = [r.get("pnl", 0.0) for r in hit]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    return {
        "on_rows_total": len(on_rows),
        "tagged": len(tagged),
        "tagged_core": sum(1 for r in tagged if r.get("tier") == "core"),
        "would_have_traded": len(hit),
        "would_have_traded_core": sum(1 for r in hit if r.get("tier") == "core"),
        "mean_r": round(sum(pnls) / len(pnls) / RISK, 4) if pnls else None,
        "win_pct": round(wins / (wins + losses) * 100, 1) if (wins + losses) else None,
    }


def tagged_grades(on_rows):
    """Grade mix of the rows the gate skipped. Under the PRE-repair ordering the
    gate ran before `_apply_x_lift`, so an X-graded row could never be tagged;
    a zero X count here is the fingerprint of a book built on that code."""
    g = defaultdict(int)
    for r in on_rows:
        if "MIN_PT1_R" in str(r.get("reason")):
            g[r.get("grade")] += 1
    return dict(g)


def table(name, off, on):
    print("\n== %s ==" % name)
    print("%-26s %7s %9s %9s %7s %7s %7s" % ("", "trades", "$/day", "mean R", "win%", "green", "months"))
    for half in ("whole", "h1", "h2"):
        for arm, d in (("OFF", off[half]), ("ON ", on[half])):
            print("%-26s %7d %9.0f %9.4f %7.1f %7d %7d" % (
                "%s %s" % (half, arm), d["trades"], d["per_day"], d["mean_r"],
                d["win_pct"], d["months_green"], d["months"]))
    print("fires/day OFF %.3f -> ON %.3f" % (off["fires_per_day"], on["fires_per_day"]))
    h1 = gate(off["h1"], on["h1"])
    h2 = gate(off["h2"], on["h2"])
    print("H1 gate: %s   H2 gate: %s" % (h1, h2))
    ship = bool(h1["enough"] and h1["pass"] and h2["enough"] and h2["pass"])
    print("decision: %s" % ("ship" if ship else "hold"))


def main():
    postfix = "--postfix" in sys.argv
    off_p, on_p = (POSTFIX_OFF, POSTFIX_ON) if postfix else (OFF, ON)
    print("arm pair: %s  /  %s" % (off_p.name, on_p.name))
    off_meta, off_rows = load(off_p)
    on_meta, on_rows = load(on_p)
    base_meta, base_rows = load(BASELINE)

    print("book ids: OFF %s  ON %s  BASELINE %s" % (
        off_meta.get("stamp", {}).get("book_id"),
        on_meta.get("stamp", {}).get("book_id"),
        base_meta.get("stamp", {}).get("book_id")))
    print("OFF == BASELINE book_id: %s" % (
        off_meta.get("stamp", {}).get("book_id") == base_meta.get("stamp", {}).get("book_id")))
    print("rows: OFF %d  ON %d  BASELINE %d" % (len(off_rows), len(on_rows), len(base_rows)))

    of, onf = off_meta.get("stamp", {}).get("flags", {}), on_meta.get("stamp", {}).get("flags", {})
    diff = {k: (of.get(k), onf.get(k)) for k in set(of) | set(onf) if of.get(k) != onf.get(k)}
    print("flag stamp diff OFF vs ON: %s" % json.dumps(diff, default=str))
    for k in ("commit", "dirty_py_count", "dirty_engine_py", "window", "sessions", "script"):
        print("  stamp[%s]: OFF=%r ON=%r" % (k, off_meta.get("stamp", {}).get(k),
                                             on_meta.get("stamp", {}).get(k)))

    tiers = defaultdict(int)
    for r in off_rows:
        tiers[r.get("tier")] += 1
    print("tier counts (OFF): %s" % dict(tiers))
    core_syms = sorted({r["sym"] for r in off_rows if r.get("tier") == "core"})
    print("tier=='core' symbols (%d): %s" % (len(core_syms), core_syms))
    try:
        import universe
        print("universe.CORE_SYMBOLS (%d): %s" % (len(universe.CORE_SYMBOLS), sorted(universe.CORE_SYMBOLS)))
        print("core set matches CORE_SYMBOLS: %s" % (set(core_syms) == set(universe.CORE_SYMBOLS)))
    except Exception as e:  # pragma: no cover
        print("universe import failed: %r" % (e,))

    if "--stamps" in sys.argv:
        return

    table("full-29 (every symbol in the book)",
          slice_book(off_meta, off_rows, core_only=False),
          slice_book(on_meta, on_rows, core_only=False))
    table("core-11 (tier == 'core', the settled universe)",
          slice_book(off_meta, off_rows, core_only=True),
          slice_book(on_meta, on_rows, core_only=True))

    print("\n== skip accounting ==")
    print(json.dumps(skip_slice(off_rows, on_rows), indent=2))
    print("grade mix of the skipped rows: %s" % tagged_grades(on_rows))


if __name__ == "__main__":
    main()
