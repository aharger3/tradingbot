"""l4_referee2.py -- L4 referee, pass 2 (told to refute).

Independent re-derivation of every number in research/l4_trend_def.md and of
every claim in research/l4_referee.md (pass 1). Nothing here imports
research/loop_cycle.py or research/g72_suppress_price.py: the unit, the
monthly buckets, the $/day denominators and the no-regression gate are
re-typed from their WRITTEN definitions (research/tape/loop.json,
SWARM.md law 2/3, loop_cycle.py's docstring) so a bug in the builder's rig
cannot reproduce itself in the check.

Books:  research/tape/book_TREND_DEF_off.json.gz  (baseline arm)
        research/tape/book_TREND_DEF_on.json.gz   (TREND_DEF=structure15)
Unit:   up_to_3_stop_win_or_2loss on tier == "core" (CORE_SYMBOLS, 11 names)
Fill:   close (entry_fill.ENTRY_FILL, stamped in both books)
Exit:   shipped engine -- 1R hard stop, intrabar touch, SCALE_PLAN=
        hod_then_runner_be, account-wide two-loss halt on
Window: 499 sessions, 2024-09-04..2026-09-04

    python research/l4_referee2.py
"""
from __future__ import annotations

import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
MIN_TRADES, MIN_MONTHS = 30, 12
MAX_DROP_PCT = 5.0


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def core(rows):
    return [r for r in rows if r.get("tier") == "core"]


def unit_rows(rows):
    """His day policy, re-typed from the spec sentence: 'up to 3 S fires;
    stop after a win or after 2 losses'.  Candidate pool = fired-and-traded
    plus the account-wide halt's own rows (loop_cycle.up_to_3_rows'
    documented pool)."""
    byday = defaultdict(list)
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        losses = 0
        for n, r in enumerate(sorted(byday[day], key=lambda x: (x.get("et") or "", x.get("sym") or ""))):
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


def figures(rows, n_days):
    if not rows or not n_days:
        return {"trades": 0, "months": 0, "months_green": 0, "per_day": 0.0}
    pnl = [r["pnl"] for r in rows]
    total = sum(pnl)
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    bym = defaultdict(float)
    for r in rows:
        bym[r["day"][:7]] += r["pnl"]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(losses) / len(losses)) if losses else 0.0
    return {
        "trades": len(rows),
        "total": round(total, 0),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(rows) / RISK, 4),
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (wins or losses) else 0.0,
        "avg_win": round(aw, 0),
        "avg_loss": round(al, 0),
        "wl": round(aw / al, 3) if al else None,
        "months": len(bym),
        "months_green": sum(1 for v in bym.values() if v > 0),
        "n_days": n_days,
    }


def slices(meta, rows):
    """whole / h1 / h2 on the unit.  n_days: whole = the book's own session
    count; halves = distinct day values in the (filtered) rows either side of
    the boundary -- loop_cycle.py's documented SESSION-COUNT CAVEAT."""
    days = sorted({r["day"] for r in rows if r.get("day")})
    n_whole = meta.get("sessions") or len(days)
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    h1 = [r for r in rows if r.get("day", "") < BOUNDARY]
    h2 = [r for r in rows if r.get("day", "") >= BOUNDARY]
    return {"whole": figures(unit_rows(rows), n_whole),
            "h1": figures(unit_rows(h1), n1),
            "h2": figures(unit_rows(h2), n2)}


def half_gate(before, after):
    """SWARM.md law 2 + law 3, re-typed."""
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


def key(r):
    return (r["day"], r.get("et"), r["sym"], r.get("dir"), r.get("setup"))


def main():
    off_meta, off_all = load(TAPE / "book_TREND_DEF_off.json.gz")
    on_meta, on_all = load(TAPE / "book_TREND_DEF_on.json.gz")
    off, on = core(off_all), core(on_all)

    print("=" * 78)
    print("SECTION 1 -- stamps")
    so, sn = off_meta["stamp"], on_meta["stamp"]
    print("  off book_id      :", so["book_id"])
    print("  on  book_id      :", sn["book_id"])
    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))
    print("  loop.json baseline_book_id:", cfg["baseline_book_id"],
          "MATCH" if cfg["baseline_book_id"] == so["book_id"] else "MISMATCH")
    bmeta, brows = load(TAPE / cfg["baseline_book"].split("/")[-1])
    print("  baseline book stamp id    :", bmeta["stamp"]["book_id"],
          "MATCH" if bmeta["stamp"]["book_id"] == so["book_id"] else "MISMATCH")
    print("  baseline rows == off rows :", len(brows) == len(off_all), len(brows), len(off_all))
    diffs = [k for k in set(so["flags"]) | set(sn["flags"])
             if so["flags"].get(k) != sn["flags"].get(k)]
    print("  flag keys differing       :", diffs)
    for k in diffs:
        print("     ", k, so["flags"].get(k), "->", sn["flags"].get(k))
    print("  off git   :", so["git"]["commit"][:8], "dirty_engine", so["git"]["dirty_engine_py"],
          "dirty_py_count", so["git"]["dirty_py_count"])
    print("  on  git   :", sn["git"]["commit"][:8], "dirty_engine", sn["git"]["dirty_engine_py"],
          "dirty_py_count", sn["git"]["dirty_py_count"])
    print("  windows   :", off_meta["first"], off_meta["last"], off_meta["sessions"],
          "|", on_meta["first"], on_meta["last"], on_meta["sessions"])
    print("  entry_fill:", off_meta["entry_fill"], on_meta["entry_fill"])

    print("=" * 78)
    print("SECTION 2 -- the gate, re-derived")
    B, A = slices(off_meta, off), slices(on_meta, on)
    hdr = "%-6s %-4s %7s %10s %8s %9s %6s %8s %9s %7s %8s"
    print(hdr % ("slice", "arm", "trades", "total$", "$/day", "meanR", "win%", "avgwin", "avgloss", "W/L", "green"))
    for s in ("whole", "h1", "h2"):
        for nm, d in (("OFF", B), ("ON", A)):
            f = d[s]
            print(hdr % (s, nm, f["trades"], f["total"], f["per_day"], f["mean_r"],
                         f["win_pct"], f["avg_win"], f["avg_loss"], f["wl"],
                         "%d/%d" % (f["months_green"], f["months"])))
    g1, g2 = half_gate(B["h1"], A["h1"]), half_gate(B["h2"], A["h2"])
    decision = "ship" if (g1["enough"] and g1["pass"] and g2["enough"] and g2["pass"]) else "hold"
    print("  H1 gate:", g1, " H2 gate:", g2, " DECISION:", decision)
    print("  n_days whole/h1/h2 OFF:", B["whole"]["n_days"], B["h1"]["n_days"], B["h2"]["n_days"],
          "| ON:", A["whole"]["n_days"], A["h1"]["n_days"], A["h2"]["n_days"])

    print("=" * 78)
    print("SECTION 3 -- direction-eligibility flips, by setup (fired core rows)")
    fo = {k: r for k, r in ((key(r), r) for r in off if r.get("status") == "fired")}
    fn = {k: r for k, r in ((key(r), r) for r in on if r.get("status") == "fired")}
    setups = sorted({r.get("setup") for r in off if r.get("status") == "fired"} |
                    {r.get("setup") for r in on if r.get("status") == "fired"})
    print("%-22s %7s %7s %7s %7s %8s %10s" % ("setup", "OFF", "ON", "lost", "gained", "lost_trd", "meanR_lost"))
    for s in setups:
        o = {k for k in fo if k[4] == s}
        n = {k for k in fn if k[4] == s}
        lost, gained = o - n, n - o
        lt = [fo[k] for k in lost if fo[k].get("traded")]
        mr = round(sum(x["r"] for x in lt) / len(lt), 4) if lt else None
        print("%-22s %7d %7d %7d %7d %8d %10s" % (s, len(o), len(n), len(lost), len(gained), len(lt), mr))

    print("=" * 78)
    print("SECTION 4 -- where the unit's money moved (the causal claim)")
    ub = {key(r): r for r in unit_rows(off)}
    ua = {key(r): r for r in unit_rows(on)}
    only_off = [ub[k] for k in ub if k not in ua]
    only_on = [ua[k] for k in ua if k not in ub]
    shared = [k for k in ub if k in ua]
    shared_diff = [k for k in shared if abs(ub[k]["pnl"] - ua[k]["pnl"]) > 1e-6]
    print("  unit rows OFF %d  ON %d" % (len(ub), len(ua)))
    print("  only-OFF %d  pnl %+.0f" % (len(only_off), sum(r["pnl"] for r in only_off)))
    print("  only-ON  %d  pnl %+.0f" % (len(only_on), sum(r["pnl"] for r in only_on)))
    print("  shared   %d  pnl-differing %d" % (len(shared), len(shared_diff)))
    print("  delta total = %+.0f (ON total %.0f - OFF total %.0f)"
          % (A["whole"]["total"] - B["whole"]["total"], A["whole"]["total"], B["whole"]["total"]))
    # is any only-ON unit row a row that does not exist AT ALL in the OFF book?
    off_any = {key(r) for r in off}
    brand_new = [r for r in only_on if key(r) not in off_any]
    print("  only-ON rows absent from the OFF book entirely (dedupe-release): %d" % len(brand_new))
    for r in brand_new:
        print("     ", key(r), r.get("status"), r.get("pnl"))
    print("  only-ON rows present in OFF with a non-unit status:")
    for r in only_on:
        o = None
        for x in off:
            if key(x) == key(r):
                o = x
                break
        print("     ", key(r), "ON", r.get("status"), r.get("pnl"),
              "| OFF", (o or {}).get("status"), (o or {}).get("traded"), (o or {}).get("pnl"))
    print("  only-OFF rows and their ON-book fate:")
    for r in sorted(only_off, key=lambda x: -abs(x["pnl"])):
        o = None
        for x in on:
            if key(x) == key(r):
                o = x
                break
        print("     ", key(r), "OFF", r.get("status"), r.get("pnl"),
              "| ON", (o or {}).get("status"), (o or {}).get("traded"), (o or {}).get("pnl"))

    print("=" * 78)
    print("SECTION 5 -- per-day deltas of the unit")
    dob, doa = defaultdict(float), defaultdict(float)
    for r in unit_rows(off):
        dob[r["day"]] += r["pnl"]
    for r in unit_rows(on):
        doa[r["day"]] += r["pnl"]
    days = sorted(set(dob) | set(doa))
    moved = [(d, dob.get(d, 0.0), doa.get(d, 0.0), doa.get(d, 0.0) - dob.get(d, 0.0))
             for d in days if abs(doa.get(d, 0.0) - dob.get(d, 0.0)) > 1e-6]
    print("  days whose unit pnl moved: %d, summed delta %+.0f"
          % (len(moved), sum(m[3] for m in moved)))
    for d, b, a, dl in sorted(moved, key=lambda m: m[3]):
        print("     %s  OFF %+9.0f  ON %+9.0f  delta %+9.0f" % (d, b, a, dl))

    print("=" * 78)
    print("SECTION 6 -- month-by-month, the green column")
    mb, ma = defaultdict(float), defaultdict(float)
    for r in unit_rows(off):
        mb[r["day"][:7]] += r["pnl"]
    for r in unit_rows(on):
        ma[r["day"][:7]] += r["pnl"]
    for m in sorted(set(mb) | set(ma)):
        b, a = mb.get(m, 0.0), ma.get(m, 0.0)
        flip = ""
        if (b > 0) != (a > 0):
            flip = "  <== FLIPS %s" % ("green->red" if b > 0 else "red->green")
        print("   %s  OFF %+10.0f  ON %+10.0f%s" % (m, b, a, flip))

    print("=" * 78)
    print("SECTION 7 -- how far the gate can reach (blind window, BR+OCR scope)")
    for s in ("one_candle_rule", "reentry_84_rule", "break_and_retest"):
        fired = [r for r in off if r.get("status") == "fired" and r.get("setup") == s]
        early = [r for r in fired if (r.get("et") or "99:99") < "09:59"]
        print("   %-18s fired %5d  fired before 09:59 %4d (%.0f%%)"
              % (s, len(fired), len(early), 100.0 * len(early) / len(fired) if fired else 0))
    lbl = Counter(r.get("setup_label") for r in off
                  if r.get("status") == "fired" and r.get("setup") == "break_and_retest")
    print("   break_and_retest fired by setup_label:", lbl.most_common())

    print("=" * 78)
    print("SECTION 8 -- cycles.md row + loop_state.json cycle 4")
    txt = (TAPE / "cycles.md").read_text(encoding="utf-8")
    for line in txt.splitlines():
        if "TREND_DEF" in line:
            print("   ", line.strip())
    st = json.loads((TAPE / "loop_state.json").read_text(encoding="utf-8"))
    print("    cycle_count", st.get("cycle_count"), "consecutive_holds",
          st.get("consecutive_holds"), "target_met", st.get("target_met"), "stop", st.get("stop"))
    for h in st.get("history", []):
        if h.get("flag") == "TREND_DEF":
            print("    history:", json.dumps(h))

    print("=" * 78)
    print("SECTION 9 -- structure15_trend exercised directly")
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import signal_runner as sr
    print("   TREND_DEF default in code:", repr(sr.TREND_DEF))
    src = (ROOT / "research" / "book_stamp.py").read_text(encoding="utf-8")
    print("   TREND_DEF in book_stamp FLAG_SOURCES:", "TREND_DEF" in src)

    def C(o, h, l, c):
        return sr.Candle(timestamp="09:30:00", open=o, high=h, low=l, close=c, volume=1)
    rising = [C(i, i + 1, i - 1, i) for i in range(30)]
    falling = [C(-i, -i + 1, -i - 1, -i) for i in range(30)]
    flat = [C(1, 2, 0, 1) for _ in range(30)]
    print("   29 bars       ->", sr.structure15_trend(rising[:29]))
    print("   30 rising     ->", sr.structure15_trend(rising))
    print("   30 falling    ->", sr.structure15_trend(falling))
    print("   30 flat       ->", sr.structure15_trend(flat))
    print("   empty         ->", sr.structure15_trend([]))
    print("   44 (partial)  ->", sr.structure15_trend(rising + falling[:14]))
    print("   45 (complete) ->", sr.structure15_trend(rising + falling[:15]))
    # inside bar: second bucket entirely inside the first
    inside = [C(0, 10, -10, 0) for _ in range(15)] + [C(0, 5, -5, 0) for _ in range(15)]
    print("   inside bucket ->", sr.structure15_trend(inside))
    outside = [C(0, 5, -5, 0) for _ in range(15)] + [C(0, 10, -10, 0) for _ in range(15)]
    print("   outside bucket->", sr.structure15_trend(outside))

    print("=" * 78)
    print("SECTION 10 -- report claims, checked literally")
    txt = (ROOT / "research" / "l4_trend_def.md").read_text(encoding="utf-8")
    for phrase in ["dedupe-release", "n=27", "not enough", "-0.1219R", "-0.3947R",
                   "769", "768", "-$52", "-$61"]:
        print("   report contains %-18r : %s" % (phrase, phrase in txt))
    m = re.search(r"the mechanism is not.*?dedupe-release", txt, re.S)
    print("   causal sentence present:", bool(m))

    print("=" * 78)
    print("SECTION 11 -- unit-row key collisions (both referee passes' row join)")
    ur_off, ur_on = unit_rows(off), unit_rows(on)
    ko = Counter(key(r) for r in ur_off)
    kn = Counter(key(r) for r in ur_on)
    print("   OFF unit rows %d, distinct keys %d, collisions %d"
          % (len(ur_off), len(ko), len(ur_off) - len(ko)))
    print("   ON  unit rows %d, distinct keys %d, collisions %d"
          % (len(ur_on), len(kn), len(ur_on) - len(kn)))
    for k, n in ko.items():
        if n > 1:
            print("      dup OFF:", k, "x", n,
                  [r["pnl"] for r in ur_off if key(r) == k])

    print("=" * 78)
    print("SECTION 12 -- the single row the verdict rests on")
    ONE = ("2024-10-25", "10:30", "SPY", "put", "one_candle_rule")
    off2 = [r for r in off if key(r) != ONE]
    on2 = [r for r in on if key(r) != ONE]
    B2, A2 = slices(off_meta, off2), slices(on_meta, on2)
    for s in ("whole", "h1", "h2"):
        print("   %-5s OFF %6d tr %8s $/day %5s green | ON %6d tr %8s $/day %5s green"
              % (s, B2[s]["trades"], B2[s]["per_day"],
                 "%d/%d" % (B2[s]["months_green"], B2[s]["months"]),
                 A2[s]["trades"], A2[s]["per_day"],
                 "%d/%d" % (A2[s]["months_green"], A2[s]["months"])))
    q1, q2 = half_gate(B2["h1"], A2["h1"]), half_gate(B2["h2"], A2["h2"])
    d2 = "ship" if (q1["enough"] and q1["pass"] and q2["enough"] and q2["pass"]) else "hold"
    print("   H1", q1, " H2", q2, " DECISION WITHOUT THAT ROW:", d2)
    print("   NOTE: pass 1 (research/l4_referee.md) wrote that removing this row leaves")
    print("   October 2024 green and H1's dollars 'roughly break-even'. Recomputed:")
    mb2 = defaultdict(float)
    ma2 = defaultdict(float)
    for r in unit_rows(off2):
        mb2[r["day"][:7]] += r["pnl"]
    for r in unit_rows(on2):
        ma2[r["day"][:7]] += r["pnl"]
    print("     2024-10 without the row: OFF %+0.0f  ON %+0.0f"
          % (mb2["2024-10"], ma2["2024-10"]))
    print("   (counterfactual A above: the row never existed, so the day walk")
    print("    re-fills its slot from the same book.)")
    print("   counterfactual B -- delete the row from the OFF UNIT after the walk:")
    ub3 = [r for r in unit_rows(off) if key(r) != ONE]
    ua3 = unit_rows(on)
    days_all = sorted({r["day"] for r in off if r.get("day")})
    n1 = sum(1 for d in days_all if d < BOUNDARY)
    n2 = sum(1 for d in days_all if d >= BOUNDARY)
    fb = {"whole": figures(ub3, off_meta["sessions"]),
          "h1": figures([r for r in ub3 if r["day"] < BOUNDARY], n1),
          "h2": figures([r for r in ub3 if r["day"] >= BOUNDARY], n2)}
    fa = {"whole": figures(ua3, on_meta["sessions"]),
          "h1": figures([r for r in ua3 if r["day"] < BOUNDARY], n1),
          "h2": figures([r for r in ua3 if r["day"] >= BOUNDARY], n2)}
    for s in ("whole", "h1", "h2"):
        print("     %-5s OFF %5s $/day %7s green | ON %5s $/day %7s green"
              % (s, fb[s]["per_day"], "%d/%d" % (fb[s]["months_green"], fb[s]["months"]),
                 fa[s]["per_day"], "%d/%d" % (fa[s]["months_green"], fa[s]["months"])))
    r1, r2 = half_gate(fb["h1"], fa["h1"]), half_gate(fb["h2"], fa["h2"])
    print("     H1", r1, " H2", r2, " DECISION:",
          "ship" if (r1["enough"] and r1["pass"] and r2["enough"] and r2["pass"]) else "hold")


if __name__ == "__main__":
    main()
