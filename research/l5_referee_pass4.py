"""L5 referee, PASS 4 -- independent re-derivation of the DAY_POLICY row.

Refereeing commit 58c00a7b ("L5 repair: complete pass-2's instruction ...").

Deliberately imports NOTHING from research/loop_cycle.py,
research/g72_suppress_price.py, research/day_policy.py or the three earlier
referee scripts. The unit walk, the monthly buckets, the halves split, the
gate arithmetic and the book comparison are all re-implemented here from the
definitions in research/tape/loop.json and SWARM.md, so a shared bug cannot
make the builder's number and mine agree.

Every dollar this script prints names its terms once:
  fill   = honest close (backtest_2y.py default ENTRY_FILL=close)
  exit   = shipped engine, 1R hard stop on the intrabar touch
           (DISASTER_STOP_R=1.0), SCALE_PLAN=hod_then_runner_be, LOSS_HALT on
  unit   = up_to_3_stop_win_or_2loss on the 11 core symbols
           (research/tape/loop.json, universe.row_filter tier == "core")
  window = 2024-09-04 .. 2026-09-04, 499 sessions
  script = research/l5_referee_pass4.py

Usage: python research/l5_referee_pass4.py
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"
BOUNDARY = "2025-09-01"
MIN_TRADES = 30
MIN_MONTHS = 12
MAX_DROP_PCT = 5.0


def load(path):
    p = Path(path)
    with gzip.open(p, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


# --------------------------------------------------------- the universe filter
# loop.json: universe.row_filter = 'tier == "core"'.  Re-implemented literally.
def core_rows(rows):
    return [r for r in rows if r.get("tier") == "core"]


# ------------------------------------------------------------------- the unit
def unit_rows(rows):
    """up to 3 fired-and-taken (or account-halted) rows a day, in time order;
    the day ends after the first positive-P&L row or the second negative one."""
    byday = {}
    for r in rows:
        st = r.get("status")
        if (st == "fired" and r.get("traded")) or st == "halted":
            byday.setdefault(r["day"], []).append(r)
    out = []
    for day in sorted(byday):
        rs = sorted(byday[day], key=lambda r: (r.get("et") or "", r.get("sym") or ""))
        taken = 0
        losses = 0
        for r in rs:
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


# ------------------------------------------------------------------ the figures
def month_of(day):
    return day[:7]


def figures(rws, n_days):
    tot = sum(r.get("pnl", 0.0) for r in rws)
    months = {}
    for r in rws:
        months[month_of(r["day"])] = months.get(month_of(r["day"]), 0.0) + r.get("pnl", 0.0)
    wins = [r["pnl"] for r in rws if r.get("pnl", 0.0) > 0]
    loss = [r["pnl"] for r in rws if r.get("pnl", 0.0) < 0]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(loss) / len(loss)) if loss else 0.0
    return {
        "trades": len(rws),
        "total": round(tot, 2),
        "per_day": round(tot / n_days, 0) if n_days else 0.0,
        "months": len(months),
        "months_green": sum(1 for v in months.values() if v > 0),
        "avg_win": round(aw, 0),
        "avg_loss": round(al, 0),
        "awal": round(aw / al, 3) if al else None,
        "fires_per_day": round(len(rws) / n_days, 3) if n_days else 0.0,
        "n_days": n_days,
    }


def slices(meta, rows):
    """whole / h1 / h2 figures on the core-11 unit, mirroring loop_cycle's own
    session-count approximation (distinct day values on each side)."""
    core = core_rows(rows)
    days = sorted({r["day"] for r in core if r.get("day")})
    n_all = meta.get("sessions") or len(days)
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    h1 = [r for r in core if r.get("day", "") < BOUNDARY]
    h2 = [r for r in core if r.get("day", "") >= BOUNDARY]
    return {
        "whole": figures(unit_rows(core), n_all),
        "h1": figures(unit_rows(h1), n1),
        "h2": figures(unit_rows(h2), n2),
    }


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


def rowkey(r):
    return (r.get("day"), r.get("et"), r.get("sym"), round(r.get("pnl", 0.0), 4))


def main():
    off_meta, off_rows = load(TAPE / "book_DAY_POLICY_off.json.gz")
    on_meta, on_rows = load(TAPE / "book_DAY_POLICY_on.json.gz")
    base_meta, base_rows = load(TAPE / "baseline_2026-09-05.json.gz")

    print("=" * 74)
    print("L5 referee pass 4 -- independent re-derivation")
    print("=" * 74)
    print("rows: off %d  on %d  baseline %d" % (len(off_rows), len(on_rows), len(base_rows)))

    # ---- 1. is the OFF book the baseline?  compare rows directly, not a hash
    HASHED = ("day", "sym", "et", "status", "traded", "pnl", "out", "entry", "stop")
    def sig(rows):
        return [tuple(r.get(k) for k in HASHED) for r in rows]
    same = sig(off_rows) == sig(base_rows)
    print("\n[1] OFF book == baseline_2026-09-05, row for row on %s: %s"
          % (",".join(HASHED), same))
    if not same:
        d = sum(1 for a, b in zip(sig(off_rows), sig(base_rows)) if a != b)
        print("    differing rows: %d" % d)

    # book_id as book_stamp defines it (the canonical fingerprint the loop pins)
    sys.path.insert(0, str(ROOT))
    from research import book_stamp                                # noqa: E402
    ids = {}
    for name, (m, rws) in {"off": (off_meta, off_rows), "on": (on_meta, on_rows),
                           "baseline": (base_meta, base_rows)}.items():
        ids[name] = book_stamp.book_id(rws)
    print("    book_id recomputed: off=%s on=%s baseline=%s"
          % (ids["off"], ids["on"], ids["baseline"]))
    loopcfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))
    print("    loop.json baseline_book_id = %s" % loopcfg["baseline_book_id"])

    # ---- 2. the two stamps differ in exactly one flag
    fo = off_meta["stamp"]["flags"]
    fn = on_meta["stamp"]["flags"]
    keys = sorted(set(fo) | set(fn))
    diffs = [(k, fo.get(k, "<absent>"), fn.get(k, "<absent>")) for k in keys
             if fo.get(k, "<absent>") != fn.get(k, "<absent>")]
    print("\n[2] flag stamp diff OFF -> ON: %d key(s)" % len(diffs))
    for k, a, b in diffs:
        print("      %s: %r -> %r" % (k, a, b))
    print("    DAY_POLICY present in stamp: %s" % ("signal_runner.DAY_POLICY" in fo))
    print("    off commit=%s dirty_py=%s dirty_engine=%s"
          % (off_meta["stamp"]["git"]["commit"][:8],
             off_meta["stamp"]["git"]["dirty_py_count"],
             off_meta["stamp"]["git"]["dirty_engine_py"]))
    print("    on  commit=%s dirty_py=%s dirty_engine=%s"
          % (on_meta["stamp"]["git"]["commit"][:8],
             on_meta["stamp"]["git"]["dirty_py_count"],
             on_meta["stamp"]["git"]["dirty_engine_py"]))
    print("    stamp has 'script' field: %s ; 'window' field: %s"
          % ("script" in off_meta["stamp"], "window" in off_meta["stamp"]))

    # ---- 3. the gate, recomputed
    so = slices(off_meta, off_rows)
    sn = slices(on_meta, on_rows)
    print("\n[3] gate, my arithmetic, unit=up_to_3_stop_win_or_2loss, core-11,")
    print("    fill=close, exit=shipped 1R disaster + hod_then_runner_be,")
    print("    window 2024-09-04..2026-09-04, boundary %s" % BOUNDARY)
    hdr = "%-6s %7s %9s %8s %8s %8s %8s" % ("slice", "sess", "$/day", "green", "trades", "aw/al", "fires/d")
    print("    " + hdr)
    for tag, s, label in ((so, "OFF", "OFF"), (sn, "ON", "ON")):
        pass
    for label, s in (("OFF", so), ("ON", sn)):
        for k in ("whole", "h1", "h2"):
            f = s[k]
            print("    %-6s %7d %9.0f %5d/%-3d %8d %8s %8.3f"
                  % (label + ":" + k, f["n_days"], f["per_day"], f["months_green"],
                     f["months"], f["trades"], f["awal"], f["fires_per_day"]))
    v1 = half_verdict(so["h1"], sn["h1"])
    v2 = half_verdict(so["h2"], sn["h2"])
    print("    H1 verdict: %s   H2 verdict: %s" % (v1, v2))
    print("    gate decision (both halves pass) = %s"
          % ("ship" if (v1.get("pass") and v2.get("pass")) else "hold"))

    # ---- 4. is the no-op exact, row for row?
    uo = unit_rows(core_rows(off_rows))
    un = unit_rows(core_rows(on_rows))
    ko = sorted(rowkey(r) for r in uo)
    kn = sorted(rowkey(r) for r in un)
    print("\n[4] unit row-set identical OFF vs ON: %s (%d vs %d)"
          % (ko == kn, len(ko), len(kn)))
    halts = [r for r in on_rows if r.get("status") == "day_policy_halt"]
    noncore = [r for r in halts if r.get("tier") != "core"]
    off_unit_keys = set(ko)
    overlap = [r for r in halts if rowkey(r) in off_unit_keys]
    print("    ON book day_policy_halt rows: %d (non-core among them: %d)"
          % (len(halts), len(noncore)))
    print("    of those, rows the OFF unit had picked: %d" % len(overlap))

    # ---- 5. what the ledgers say
    cyc = (TAPE / "cycles.md").read_text(encoding="utf-8")
    dp = [l for l in cyc.splitlines() if "| DAY_POLICY |" in l]
    print("\n[5] cycles.md DAY_POLICY row(s): %d" % len(dp))
    for l in dp:
        print("    " + l.strip())
    st = json.loads((TAPE / "loop_state.json").read_text(encoding="utf-8"))
    print("    loop_state: consecutive_holds=%s stop=%s stop_reason=%r target_met=%s"
          % (st["consecutive_holds"], st["stop"], st["stop_reason"], st["target_met"]))
    print("    loop_state history decisions: %s"
          % [h["decision"] for h in st["history"]])

    # ---- 6. the code default and FLAG_SOURCES
    sr = (ROOT / "signal_runner.py").read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^DAY_POLICY\s*=\s*(.+)$', sr, re.M)
    print("\n[6] signal_runner.py default line: %s" % (m.group(0) if m else "<not found>"))
    import signal_runner                                            # noqa: E402
    print("    imported signal_runner.DAY_POLICY = %r" % signal_runner.DAY_POLICY)
    bs = (ROOT / "research" / "book_stamp.py").read_text(encoding="utf-8", errors="replace")
    print("    'DAY_POLICY' in book_stamp.FLAG_SOURCES source: %s"
          % ("DAY_POLICY" in bs))

    # ---- 7. sgrade scope of the unit (the "up to 3 S fires" sentence)
    from collections import Counter
    print("\n[7] sgrade of the %d unit rows: %s"
          % (len(uo), dict(Counter(r.get("sgrade") for r in uo))))

    # ---- 8. the two definitions of "a win"
    pool = []
    byday = {}
    for r in core_rows(off_rows):
        st_ = r.get("status")
        if (st_ == "fired" and r.get("traded")) or st_ == "halted":
            byday.setdefault(r["day"], []).append(r)
    for d in byday:
        pool.extend(byday[d])
    disagree = [r for r in pool
                if (r.get("out") == "win") != (r.get("pnl", 0.0) > 0)]
    print("\n[8] causal candidate pool: %d rows; out=='win' vs pnl>0 disagree on %d"
          % (len(pool), len(disagree)))
    if disagree:
        worst = sorted(disagree, key=lambda r: -abs(r.get("pnl", 0.0)))[:5]
        print("    outs among disagreements: %s"
              % dict(Counter(r.get("out") for r in disagree)))
        for r in worst:
            print("      %s %s %s out=%s pnl=%+.2f"
                  % (r["day"], r.get("et"), r.get("sym"), r.get("out"), r.get("pnl", 0.0)))
    lossdis = [r for r in pool if (r.get("out") == "loss") != (r.get("pnl", 0.0) < 0)]
    print("    out=='loss' vs pnl<0 disagree on %d" % len(lossdis))

    # ---- 9. daily distribution / prop-firm pass rate on the OFF (= ON) unit
    daily = {}
    for r in uo:
        daily[r["day"]] = daily.get(r["day"], 0.0) + r.get("pnl", 0.0)
    vals = sorted(daily.values())
    def pct(p):
        if not vals:
            return 0.0
        i = max(0, min(len(vals) - 1, int(round(p / 100.0 * (len(vals) - 1)))))
        return vals[i]
    print("\n[9] daily P&L on the unit, %d days traded: p5=%.0f p25=%.0f med=%.0f "
          "p75=%.0f p95=%.0f worst=%.0f"
          % (len(vals), pct(5), pct(25), pct(50), pct(75), pct(95), vals[0] if vals else 0))
    for lim in (1000, 2500):
        breach = sum(1 for v in vals if v < -lim)
        print("    $%d daily-loss limit: %d/%d days breach (%.1f%% pass)"
              % (lim, breach, len(vals), 100.0 * (1 - breach / len(vals)) if vals else 0))
    fires = {}
    for r in uo:
        fires[r["day"]] = fires.get(r["day"], 0) + 1
    dist = Counter(fires.values())
    sessions_all = off_meta.get("sessions")
    core_days = sorted({r["day"] for r in core_rows(off_rows) if r.get("day")})
    print("    fires-per-day histogram over %d days that had a unit row: %s"
          % (len(fires), dict(sorted(dist.items()))))
    print("    core-tier days appearing anywhere in the book: %d ; meta sessions: %s"
          % (len(core_days), sessions_all))

    # ---- 10. the report's own claims
    rep = (ROOT / "research" / "l5_day_policy.md").read_text(encoding="utf-8")
    for probe in ("default flipped", "Decision: hold", "Decision: ship",
                  "now the **default**", "commit named below"):
        print("\n[10] l5_day_policy.md contains %r: %s" % (probe, probe in rep))


if __name__ == "__main__":
    main()
