"""L5 referee (2026-09-05) -- refute the DAY_POLICY row built at 9b5fdc5a.

Everything here is re-derived by this file's own arithmetic; nothing is taken
from the builder's report, and `research/loop_cycle.py` is imported only as a
CROSS-CHECK at the end (my numbers first, its numbers second, and the script
prints both so a disagreement is visible rather than hidden).

HOW THE "ON" BOOK IS OBTAINED WITHOUT A REBUILD, and why that is exact.
`DAY_POLICY` has exactly one consumer inside `backtest_2y.py`'s build path:
the `day_policy.apply_to_book(rows)` call the row added right after
`loss_halt.apply_to_book(rows)`, and `day_policy.apply_to_book` is a pure
post-pass over the finished row list that returns immediately unless the flag
holds the new value (`grep -rn DAY_POLICY --include=*.py .` -- the only other
reader is `live_scanner.py`, which is not in the build path).  Therefore

    ON book  ==  OFF book with day_policy.apply_to_book() applied

bit for bit, and the OFF book is the loop's own stamped baseline.  This is
strictly better than rebuilding: `--days 730` counts back from the last
archived session, so a rebuild is a different universe the moment the archive
advances, while this derivation cannot drift.  `--prove-rebuild` runs a real
15-session pair of rebuilds to demonstrate the equivalence empirically.

Fill / exit / unit, said once, for every dollar this script prints:
  fill   = honest close fill (`backtest_2y.py` default `ENTRY_FILL`)
  exit   = shipped engine, 1R hard stop on the intrabar touch, SCALE_PLAN
           hod_then_runner_be, LOSS_HALT on
  unit   = `up_to_3_stop_win_or_2loss` on the 11 core symbols -- the loop's
           baseline unit, `research/tape/loop.json`
  source = research/tape/baseline_2026-09-05.json.gz (book_id 2c39ced2697c26cc)
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RISK = 1000.0
BOUNDARY = "2025-09-01"
MIN_TRADES = 30
MIN_MONTHS = 12
MAX_DROP_PCT = 5.0


# ------------------------------------------------------------------ loading

def load_book(path):
    p = str(path)
    if p.endswith(".gz"):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            b = json.load(f)
    else:
        b = json.loads(Path(p).read_text(encoding="utf-8"))
    return b["meta"], b["trades"]


# ------------------------------------- my own unit, written from the sentence
# Austin, 2026-09-05: "up to 3 S fires; stop after a win or after 2 losses."

def unit_up_to_3(rows):
    """Independent implementation. Candidate pool = a row the engine actually
    took (fired+traded), plus rows the account-wide loss halt removed, so a
    halt this unit would not itself have reached cannot silently erase the
    rest of that day. Order within a day: entry time, then symbol."""
    byday = defaultdict(list)
    for r in rows:
        took = (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted"
        if took:
            byday[r["day"]].append(r)
    picked = []
    for day in sorted(byday):
        for r in sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or "")):
            picked.append(r)
            pnl = r.get("pnl", 0.0) or 0.0
            if pnl > 0:
                break                                   # a win ends the day
            if sum(1 for q in picked if q["day"] == day and (q.get("pnl") or 0) < 0) >= 2:
                break                                   # two losses end the day
            if sum(1 for q in picked if q["day"] == day) >= 3:
                break                                   # three fires is the cap
    return picked


def unit_first_of_day(rows):
    byday = defaultdict(list)
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        out.append(sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or ""))[0])
    return out


UNITS = {"up_to_3_stop_win_or_2loss": unit_up_to_3, "first_of_day": unit_first_of_day}
# unit_up_to_3_causal is registered after its definition below.


# ------------------------------------------------------------- my own figures

def iso_week(day):
    import datetime as _dt
    y, m, d = (int(x) for x in day.split("-"))
    iy, iw, _ = _dt.date(y, m, d).isocalendar()
    return "%04d-W%02d" % (iy, iw)


def figures(rows, n_days):
    if not rows or not n_days:
        return {"trades": 0, "total": 0.0, "per_day": 0.0, "mean_r": 0.0,
                "win_pct": 0.0, "months_green": 0, "months": 0,
                "avg_win": 0.0, "avg_loss": 0.0, "awal": None}
    pnls = [r.get("pnl", 0.0) or 0.0 for r in rows]
    total = sum(pnls)
    by_m = defaultdict(float)
    for r in rows:
        by_m[r["day"][:7]] += r.get("pnl", 0.0) or 0.0
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(losses) / len(losses)) if losses else 0.0
    return {"trades": len(rows), "total": round(total, 0),
            "per_day": round(total / n_days, 0),
            "mean_r": round(total / len(rows) / RISK, 4),
            "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1)
                       if (wins or losses) else 0.0,
            "months_green": sum(1 for v in by_m.values() if v > 0),
            "months": len(by_m),
            "avg_win": round(aw, 0), "avg_loss": round(al, 0),
            "awal": round(aw / al, 3) if al else None}


def slice_all(rows, unit_name, n_days_whole):
    f = UNITS[unit_name]
    days = sorted({r["day"] for r in rows if r.get("day")})
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    h1 = [r for r in rows if r.get("day", "") < BOUNDARY]
    h2 = [r for r in rows if r.get("day", "") >= BOUNDARY]
    return {"whole": figures(f(rows), n_days_whole),
            "h1": figures(f(h1), n1),
            "h2": figures(f(h2), n2)}


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


# --------------------------------------------------------- the derivation

def derive_on(off_rows):
    """OFF book + the row's own post-pass = the ON book (see module docstring)."""
    import signal_runner
    import day_policy
    rows = copy.deepcopy(off_rows)
    saved = signal_runner.DAY_POLICY
    signal_runner.DAY_POLICY = "3fires_stop_win_or_2loss"
    try:
        blocked = day_policy.apply_to_book(rows)
    finally:
        signal_runner.DAY_POLICY = saved
    return rows, blocked


def core_only(rows):
    return [r for r in rows if r.get("tier") == "core"]


def unit_up_to_3_causal(rows):
    """The SAME day policy as `unit_up_to_3`, but causal -- a stop condition
    only counts once the relevant trade has actually CLOSED. This is what the
    row's `day_policy.py` argues for, expressed the way the spec asks for it
    ('measured as a unit'): the unit changes, the book does not. Candidate
    pool is identical to `unit_up_to_3`'s, so the two are comparable."""
    byday = defaultdict(list)
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday[r["day"]].append(r)
    picked = []
    for day in sorted(byday):
        day_rows = sorted(byday[day], key=lambda x: (x.get("entry_i", 0),
                                                     x.get("et") or "", x.get("sym") or ""))
        pending, taken, wins, losses = [], 0, 0, 0
        for r in day_rows:
            at = r.get("entry_i", 0)
            while pending and pending[0][0] <= at:
                _e, w, l = pending.pop(0)
                wins += 1 if w else 0
                losses += 1 if l else 0
            if wins >= 1 or losses >= 2 or taken >= 3:
                continue
            picked.append(r)
            taken += 1
            pending.append((r.get("entry_i", 0) + r.get("bars", 0),
                            r.get("out") == "win", r.get("out") == "loss"))
            pending.sort(key=lambda p: p[0])
    return picked


UNITS["up_to_3_causal"] = unit_up_to_3_causal


# ------------------------------------------------- daily loss distribution

def daily_pnl(rows, unit_name):
    by_day = defaultdict(float)
    for r in UNITS[unit_name](rows):
        by_day[r["day"]] += r.get("pnl", 0.0) or 0.0
    return by_day


def loss_table(by_day):
    vals = sorted(by_day.values())
    n = len(vals)
    out = {"days_traded": n, "worst_day": round(vals[0], 0) if n else 0.0,
           "median_day": round(vals[n // 2], 0) if n else 0.0}
    for lim in (1000, 1500, 2000, 2500, 3000):
        breaches = sum(1 for v in vals if v <= -lim)
        out["days_at_or_below_-$%d" % lim] = breaches
        out["pass_rate_-$%d" % lim] = round((n - breaches) / n * 100, 1) if n else 0.0
    return out


# --------------------------------------------------------------------- main

def prove_rebuild():
    """Empirically show DAY_POLICY changes nothing but the post-pass: build a
    15-session book at each value and check that the ON book equals the OFF
    book once the rows this flag blocked are put back."""
    tmp = ROOT / "research" / "tape" / "logs"
    tmp.mkdir(parents=True, exist_ok=True)
    outs = {}
    for label, val in (("off", "first3"), ("on", "3fires_stop_win_or_2loss")):
        out = tmp / ("l5ref_prove_%s.json" % label)
        env = dict(os.environ)
        env["DAY_POLICY"] = val
        env["PYTHONIOENCODING"] = "utf-8"
        log = tmp / ("l5ref_prove_%s.log" % label)
        with open(log, "w", encoding="utf-8") as lf:
            p = subprocess.run([sys.executable, str(ROOT / "backtest_2y.py"),
                                "--days", "15", "--out", str(out)],
                               cwd=str(ROOT), env=env, stdout=lf,
                               stderr=subprocess.STDOUT, text=True)
        if p.returncode != 0:
            return {"ok": False, "why": "build %s exited %d (see %s)" % (label, p.returncode, log)}
        outs[label] = out
    _, off = load_book(outs["off"])
    _, on = load_book(outs["on"])
    if len(off) != len(on):
        return {"ok": False, "why": "row counts differ: %d vs %d" % (len(off), len(on))}
    blocked = [r for r in on if r.get("day_policy_halt")]
    diffs = 0
    for a, b in zip(off, on):
        b2 = {k: v for k, v in b.items()
              if k not in ("traded", "status", "day_policy_halt", "reason")}
        a2 = {k: v for k, v in a.items()
              if k not in ("traded", "status", "day_policy_halt", "reason")}
        if a2 != b2:
            diffs += 1
    return {"ok": diffs == 0, "rows": len(off), "blocked_15d": len(blocked),
            "rows_differing_outside_the_post_pass": diffs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prove-rebuild", action="store_true")
    args = ap.parse_args()

    from research import book_stamp

    cfg = json.loads((ROOT / "research" / "tape" / "loop.json").read_text(encoding="utf-8"))
    off_path = ROOT / cfg["baseline_book"]
    meta, off_rows = load_book(off_path)

    print("== the books ==")
    for name in ("book_DAY_POLICY_off.json.gz", "book_DAY_POLICY_on.json.gz"):
        p = ROOT / "research" / "tape" / name
        print("  %-34s %s" % (name, "EXISTS" if p.exists() else "MISSING"))
    bid = book_stamp.book_id(off_rows)
    print("  baseline book_id            %s (loop.json says %s) -> %s"
          % (bid, cfg["baseline_book_id"],
             "MATCH" if bid == cfg["baseline_book_id"] else "MISMATCH"))
    print("  baseline stamp commit       %s  dirty_py=%s  sessions=%s"
          % (meta.get("stamp", {}).get("git", {}).get("commit"),
             meta.get("stamp", {}).get("git", {}).get("dirty_py_count"),
             meta.get("sessions")))

    on_rows, blocked = derive_on(off_rows)
    print("\n== the flag's effect on the built book ==")
    print("  rows in book                %d" % len(off_rows))
    print("  rows day_policy blocked     %d (whole 28-symbol pool)" % blocked)
    print("  rows blocked, core 11       %d"
          % sum(1 for r in on_rows if r.get("day_policy_halt") and r.get("tier") == "core"))

    off_c, on_c = core_only(off_rows), core_only(on_rows)
    n_days = meta.get("sessions") or len({r["day"] for r in off_rows})

    results = {}
    for unit in ("up_to_3_stop_win_or_2loss", "first_of_day"):
        a = slice_all(off_c, unit, n_days)
        b = slice_all(on_c, unit, n_days)
        results[unit] = {"off": a, "on": b,
                         "h1": half_verdict(a["h1"], b["h1"]),
                         "h2": half_verdict(a["h2"], b["h2"])}
        print("\n== unit %s, core 11, honest close fill, shipped exit ==" % unit)
        for half in ("whole", "h1", "h2"):
            x, y = a[half], b[half]
            print("  %-5s  $/day %8.0f -> %8.0f | green %2d/%2d -> %2d/%2d | trades %4d -> %4d"
                  % (half, x["per_day"], y["per_day"], x["months_green"], x["months"],
                     y["months_green"], y["months"], x["trades"], y["trades"]))
        print("  H1 verdict %s   H2 verdict %s" % (results[unit]["h1"], results[unit]["h2"]))
        # did the unit's own pick change at all?
        pa = {(r["day"], r.get("et"), r.get("sym")) for r in UNITS[unit](off_c)}
        pb = {(r["day"], r.get("et"), r.get("sym")) for r in UNITS[unit](on_c)}
        print("  rows the unit picked that the flag removed: %d ; added: %d"
              % (len(pa - pb), len(pb - pa)))
        results[unit]["picked_removed"] = len(pa - pb)
        results[unit]["picked_added"] = len(pb - pa)

    print("\n== daily loss distribution, baseline unit, core 11 (the row asked for this) ==")
    for label, rows, unit in (("off (lens unit)", off_c, "up_to_3_stop_win_or_2loss"),
                              ("on  (lens unit)", on_c, "up_to_3_stop_win_or_2loss"),
                              ("off (causal unit)", off_c, "up_to_3_causal")):
        t = loss_table(daily_pnl(rows, unit))
        print("  %s: %s" % (label, json.dumps(t)))

    print("\n== cross-check against research/loop_cycle.py's own arithmetic ==")
    try:
        import importlib
        lc = importlib.import_module("research.loop_cycle")
        for unit in ("up_to_3_stop_win_or_2loss", "first_of_day"):
            for label, rows in (("off", off_c), ("on", on_c)):
                got = lc.compute_all({"sessions": n_days}, rows, unit, BOUNDARY)
                mine = results[unit][label]
                for half in ("whole", "h1", "h2"):
                    same = (got[half]["per_day"] == mine[half]["per_day"]
                            and got[half]["months_green"] == mine[half]["months_green"]
                            and got[half]["trades"] == mine[half]["trades"])
                    print("  %-26s %-3s %-5s loop=%8.0f/%2d/%4d  mine=%8.0f/%2d/%4d  %s"
                          % (unit, label, half, got[half]["per_day"],
                             got[half]["months_green"], got[half]["trades"],
                             mine[half]["per_day"], mine[half]["months_green"],
                             mine[half]["trades"], "OK" if same else "DIFFER"))
    except Exception as exc:                                   # pragma: no cover
        print("  cross-check unavailable: %r" % (exc,))

    # ---- the row's own two books, if the builder's crashed wrapper left them
    off_b = ROOT / "research" / "tape" / "book_DAY_POLICY_off.json.gz"
    on_b = ROOT / "research" / "tape" / "book_DAY_POLICY_on.json.gz"
    if off_b.exists() and on_b.exists():
        print("\n== the row's own stamped books ==")
        m_off, r_off = load_book(off_b)
        m_on, r_on = load_book(on_b)
        id_off, id_on = book_stamp.book_id(r_off), book_stamp.book_id(r_on)
        print("  OFF book_id %s vs baseline %s -> %s"
              % (id_off, cfg["baseline_book_id"],
                 "MATCH" if id_off == cfg["baseline_book_id"] else "MISMATCH"))
        print("  ON  book_id %s (differs from OFF: %s)" % (id_on, id_on != id_off))
        print("  ON  book_id == my derivation from the baseline: %s"
              % (id_on == book_stamp.book_id(on_rows)))
        f_off = (m_off.get("stamp") or {}).get("flags") or {}
        f_on = (m_on.get("stamp") or {}).get("flags") or {}
        diff = {k: (f_off.get(k), f_on.get(k))
                for k in set(f_off) | set(f_on) if f_off.get(k) != f_on.get(k)}
        print("  stamp flag differences: %s" % json.dumps(diff))
        for label, m in (("OFF", m_off), ("ON", m_on)):
            g = (m.get("stamp") or {}).get("git") or {}
            print("  %s stamp: commit=%r dirty_py=%s dirty_engine=%s traded=%s sessions=%s"
                  % (label, g.get("commit"), g.get("dirty_py_count"),
                     g.get("dirty_engine_py"), m.get("traded"), m.get("sessions")))

    # ---- defect 1: the flag is applied to all 28 symbols, then read on core 11
    print("\n== defect probe: which universe the flag was applied to ==")
    on_wrong = on_c                                   # applied to 28, read on 11
    on_right_rows, blocked_right = derive_on(core_only(off_rows))
    print("  blocked when applied to the whole 28-symbol book, seen on core 11: %d"
          % sum(1 for r in on_wrong if r.get("day_policy_halt")))
    print("  blocked when applied to the core 11 alone                       : %d"
          % blocked_right)
    a = slice_all(off_c, "up_to_3_stop_win_or_2loss", n_days)
    w = slice_all(on_wrong, "up_to_3_stop_win_or_2loss", n_days)
    g = slice_all(on_right_rows, "up_to_3_stop_win_or_2loss", n_days)
    for label, tbl in (("OFF (baseline)", a), ("ON as the row built it (28-sym)", w),
                       ("ON applied to core 11 only", g)):
        print("  %-32s whole $/day %6.0f green %2d/%2d trades %4d | h1 %6.0f %2d/%2d | h2 %6.0f %2d/%2d"
              % (label, tbl["whole"]["per_day"], tbl["whole"]["months_green"],
                 tbl["whole"]["months"], tbl["whole"]["trades"],
                 tbl["h1"]["per_day"], tbl["h1"]["months_green"], tbl["h1"]["months"],
                 tbl["h2"]["per_day"], tbl["h2"]["months_green"], tbl["h2"]["months"]))
    print("  H1/H2 verdict, ON as built     : %s / %s"
          % (half_verdict(a["h1"], w["h1"]), half_verdict(a["h2"], w["h2"])))
    print("  H1/H2 verdict, ON core-11 only : %s / %s"
          % (half_verdict(a["h1"], g["h1"]), half_verdict(a["h2"], g["h2"])))
    days_wiped = (len({r["day"] for r in UNITS["up_to_3_stop_win_or_2loss"](off_c)})
                  - len({r["day"] for r in UNITS["up_to_3_stop_win_or_2loss"](on_wrong)}))
    print("  core-11 sessions that lose EVERY candidate under the as-built flag: %d" % days_wiped)

    # ---- defect 2: the two implementations disagree about the candidate pool
    halted_days = {r["day"] for r in off_c if r.get("status") == "halted"}
    print("\n== defect probe: candidate-pool disagreement (loss_halt rows) ==")
    print("  day_policy.apply_to_book pool  : fired+traded only")
    print("  loop_cycle's unit pool         : fired+traded PLUS status=='halted'")
    print("  core-11 rows with status=='halted': %d, on %d of %d sessions"
          % (sum(1 for r in off_c if r.get("status") == "halted"),
             len(halted_days), n_days))

    # ---- the comparison the spec actually asked for: change the UNIT, not the book
    print("\n== the spec's own framing: 'measured as a unit', same baseline book ==")
    for uname in ("first_of_day", "up_to_3_stop_win_or_2loss", "up_to_3_causal"):
        t = slice_all(off_c, uname, n_days)
        print("  %-26s whole $/day %6.0f green %2d/%2d trades %4d avg_win/avg_loss %s"
              % (uname, t["whole"]["per_day"], t["whole"]["months_green"],
                 t["whole"]["months"], t["whole"]["trades"], t["whole"]["awal"]))

    if args.prove_rebuild:
        print("\n== empirical proof the flag only adds the post-pass (15 sessions) ==")
        print("  %s" % json.dumps(prove_rebuild()))


if __name__ == "__main__":
    main()
