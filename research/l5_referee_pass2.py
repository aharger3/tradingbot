"""L5 referee, PASS 2 (2026-09-05) -- independent re-derivation of the repair
commit 350b02fc ("L5 repair: day_policy scoped to core-11 lane + shared
candidate pool ... ships as new default").

Pass 1's script is research/l5_referee.py and is left untouched (evidence).
This file re-derives everything from the two stamped books with its own
arithmetic -- it deliberately does NOT import research/loop_cycle.py's unit
function, so the gate numbers are independent of the code that produced them.

Every dollar on this page: fill = honest close (backtest_2y.py ENTRY_FILL
default), exit = shipped engine (1R hard stop on the intrabar touch,
DISASTER_STOP_R=1.0, SCALE_PLAN=hod_then_runner_be, LOSS_HALT on), unit =
up_to_3_stop_win_or_2loss on the 11 core symbols (loop.json), window
2024-09-04 -> 2026-09-04, script = this file.

Usage:  python research/l5_referee_pass2.py
"""
from __future__ import annotations

import copy
import gzip
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TAPE = ROOT / "research" / "tape"
BOUNDARY = "2025-09-01"


def load(path):
    p = Path(path)
    if str(p).endswith(".gz"):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            obj = json.load(fh)
    else:
        obj = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(obj, dict):
        rows = obj.get("trades") or obj.get("rows") or obj.get("signals") or []
        return obj, rows
    return {}, obj


# ------------------------------------------------------------ the unit, mine

def core(rows):
    return [r for r in rows if r.get("tier") == "core"]


def up_to_3(rows):
    """Independent re-implementation of loop.json's unit sentence:
    up to 3 fired-and-traded signals a day (plus rows R31's halt already
    removed, which the unit keeps in its candidate pool), stop after the
    first winner or the second loser."""
    byday = defaultdict(list)
    for r in rows:
        st = r.get("status")
        if (st == "fired" and r.get("traded")) or st == "halted":
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        drows = sorted(byday[day], key=lambda r: (r.get("et") or "", r.get("sym") or ""))
        losses = taken = 0
        for r in drows:
            if taken >= 3:
                break
            out.append(r)
            taken += 1
            pnl = r.get("pnl", 0.0)
            if pnl > 0:
                break
            if pnl < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


def sessions(rows):
    return sorted({r["day"] for r in rows if r.get("day")})


def figures(picked, n_days):
    pnl = [float(r.get("pnl", 0.0)) for r in picked]
    total = sum(pnl)
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    bymonth = defaultdict(float)
    for r in picked:
        bymonth[r["day"][:7]] += float(r.get("pnl", 0.0))
    aw = (sum(wins) / len(wins)) if wins else 0.0
    al = (abs(sum(losses)) / len(losses)) if losses else 0.0
    return {
        "trades": len(picked),
        "total": round(total, 2),
        "per_day": round(total / n_days, 2) if n_days else 0.0,
        "win_pct": round(100.0 * len(wins) / len(pnl), 2) if pnl else 0.0,
        "months": len(bymonth),
        "months_green": sum(1 for v in bymonth.values() if v > 0),
        "avg_win": round(aw, 2),
        "avg_loss": round(al, 2),
        "awal": round(aw / al, 3) if al else None,
        "fires_per_day": round(len(picked) / n_days, 3) if n_days else 0.0,
    }


def slice_half(rows, which):
    if which == "h1":
        return [r for r in rows if r["day"] < BOUNDARY]
    if which == "h2":
        return [r for r in rows if r["day"] >= BOUNDARY]
    return rows


def measure(all_rows, label):
    c = core(all_rows)
    all_days = sessions(all_rows)
    out = {}
    for which in ("whole", "h1", "h2"):
        rows_h = slice_half(c, which)
        days_h = [d for d in all_days
                  if which == "whole"
                  or (which == "h1" and d < BOUNDARY)
                  or (which == "h2" and d >= BOUNDARY)]
        out[which] = figures(up_to_3(rows_h), len(days_h))
        out[which]["sessions"] = len(days_h)
    out["label"] = label
    return out


# ------------------------------------------------------------------- reports

def stamp_of(meta):
    return ((meta.get("meta") or {}).get("stamp")
            or meta.get("stamp") or {}) or {}


def flags_of(meta):
    return stamp_of(meta).get("flags", {}) or {}


def main():
    off_p = TAPE / "book_DAY_POLICY_off.json.gz"
    on_p = TAPE / "book_DAY_POLICY_on.json.gz"
    base_p = TAPE / "baseline_2026-09-05.json.gz"
    loop = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))

    off_meta, off_rows = load(off_p)
    on_meta, on_rows = load(on_p)
    base_meta, base_rows = load(base_p)

    print("=" * 78)
    print("1. STAMPS")
    for name, meta, rws in (("OFF", off_meta, off_rows), ("ON", on_meta, on_rows),
                            ("BASELINE", base_meta, base_rows)):
        st = stamp_of(meta)
        g = st.get("git") or {}
        print("  %-8s book_id=%s built=%s rows=%s" % (name, st.get("book_id"),
                                                      st.get("built_at"), st.get("rows")))
        print("           git=%s" % json.dumps(g, sort_keys=True)[:300])
        print("           out=%r  entry_fill=%r  actual_rows=%d"
              % (st.get("out"), st.get("entry_fill"), len(rws)))
        print("           window(meta)=%s..%s sessions=%s"
              % (meta.get("first"), meta.get("last"), meta.get("sessions")))
    print("  loop.json baseline_book_id = %s" % loop["baseline_book_id"])
    off_id = stamp_of(off_meta).get("book_id")
    print("  OFF == baseline book_id ? %s" % (off_id == loop["baseline_book_id"]))

    print("\n2. FLAG DIFF between the two stamps")
    fo, fn = flags_of(off_meta), flags_of(on_meta)
    keys = sorted(set(fo) | set(fn))
    diffs = [(k, fo.get(k), fn.get(k)) for k in keys if fo.get(k) != fn.get(k)]
    for k, a, b in diffs:
        print("  %-32s %r -> %r" % (k, a, b))
    print("  total flags stamped: %d ; differing: %d" % (len(keys), len(diffs)))

    print("\n3. GATE, re-derived with this file's own arithmetic")
    m_off = measure(off_rows, "OFF")
    m_on = measure(on_rows, "ON")
    hdr = "  %-6s %-4s %7s %9s %7s %7s %8s %7s" % (
        "arm", "half", "trades", "$/day", "green", "months", "aw/al", "fires/d")
    print(hdr)
    for m in (m_off, m_on):
        for which in ("whole", "h1", "h2"):
            f = m[which]
            print("  %-6s %-4s %7d %9.2f %7d %7d %8s %7.3f"
                  % (m["label"], which, f["trades"], f["per_day"], f["months_green"],
                     f["months"], f["awal"], f["fires_per_day"]))

    print("\n4. cycles.md's L5 row vs mine")
    print("  cycles.md: $/day -52.0 -> -52.0, green 11 -> 11, H1 pass, H2 pass, trades 769")
    print("  mine     : $/day %.1f -> %.1f, green %d -> %d, trades %d -> %d"
          % (m_off["whole"]["per_day"], m_on["whole"]["per_day"],
             m_off["whole"]["months_green"], m_on["whole"]["months_green"],
             m_off["whole"]["trades"], m_on["whole"]["trades"]))
    for h in ("h1", "h2"):
        a, b = m_off[h], m_on[h]
        drop = None if a["per_day"] == 0 else (a["per_day"] - b["per_day"]) / abs(a["per_day"]) * 100.0
        print("  %s: $/day %.2f -> %.2f (drop %.2f%%), green %d -> %d, trades %d -> %d"
              % (h.upper(), a["per_day"], b["per_day"],
                 (drop if drop is not None else float("nan")),
                 a["months_green"], b["months_green"], a["trades"], b["trades"]))

    print("\n5. Row-level diff between the two books (not just the unit)")
    same_order = (len(off_rows) == len(on_rows)) and all(
        (a.get("day"), a.get("sym"), a.get("et")) == (b.get("day"), b.get("sym"), b.get("et"))
        for a, b in zip(off_rows, on_rows))
    print("  rows OFF=%d ON=%d ; positionally aligned=%s"
          % (len(off_rows), len(on_rows), same_order))
    stat_ch = [i for i, (a, b) in enumerate(zip(off_rows, on_rows))
               if a.get("status") != b.get("status")]
    print("  status changed at %d positions" % len(stat_ch))
    dph = [i for i in stat_ch if on_rows[i].get("status") == "day_policy_halt"]
    print("  of those, flipped to day_policy_halt: %d" % len(dph))
    tiers = defaultdict(int)
    prevstat = defaultdict(int)
    traded_before = 0
    for i in dph:
        tiers[on_rows[i].get("tier")] += 1
        prevstat[off_rows[i].get("status")] += 1
        if off_rows[i].get("traded"):
            traded_before += 1
    print("  blocked rows by tier: %s" % dict(tiers))
    print("  their status in the OFF book: %s ; traded in OFF: %d"
          % (dict(prevstat), traded_before))
    # did any BLOCKED row actually appear in the OFF arm's measured unit?
    picked_off_keys = {id(r) for r in up_to_3(core(off_rows))}
    n_in_unit = sum(1 for i in dph if id(off_rows[i]) in picked_off_keys)
    print("  blocked rows that the OFF arm's unit actually counted: %d" % n_in_unit)

    print("\n6. THE DEFAULT FLIP: does the OFF arm still reproduce the baseline at HEAD?")
    import signal_runner
    import day_policy
    from research import book_stamp
    print("  signal_runner.DAY_POLICY at HEAD default = %r" % signal_runner.DAY_POLICY)
    print("  backtest_2y calls day_policy.apply_to_book unconditionally (line 293);")
    print("  loop_cycle.stage_build builds the OFF arm with env_overrides={} and")
    print("  loop.json rebuild.env == %r, so the OFF arm inherits the HEAD default." % loop["rebuild"]["env"])
    sim = copy.deepcopy(base_rows)
    blocked = day_policy.apply_to_book(sim)
    new_id = book_stamp.book_id(sim)
    print("  applying day_policy at the HEAD default to the BASELINE book:")
    print("    rows blocked        = %d" % blocked)
    print("    resulting book_id   = %s" % new_id)
    print("    baseline book_id    = %s" % loop["baseline_book_id"])
    print("    ON book_id (stamp)  = %s" % stamp_of(on_meta).get("book_id"))
    print("    -> next L-row's OFF arm matches the baseline? %s"
          % (new_id == loop["baseline_book_id"]))

    print("\n7. Daily P&L distribution, core-11 baseline unit, OFF arm (the shipped lens)")
    c = core(off_rows)
    picked = up_to_3(c)
    byday = defaultdict(float)
    for r in picked:
        byday[r["day"]] += float(r.get("pnl", 0.0))
    vals = sorted(byday.values())
    n = len(vals)
    def pct(p):
        if not vals:
            return 0.0
        i = min(n - 1, max(0, int(round(p / 100.0 * (n - 1)))))
        return vals[i]
    print("  traded days=%d  p5=%.0f p25=%.0f median=%.0f p75=%.0f p95=%.0f worst=%.0f best=%.0f"
          % (n, pct(5), pct(25), pct(50), pct(75), pct(95), vals[0], vals[-1]))
    for lim in (1000, 2000, 2500):
        br = sum(1 for v in vals if v <= -lim)
        print("    days at or below -$%-5d : %3d  (pass %.1f%% of %d)"
              % (lim, br, 100.0 * (n - br) / n, n))
    fires = defaultdict(int)
    for r in picked:
        fires[r["day"]] += 1
    hist = defaultdict(int)
    all_days = sessions(off_rows)
    for d in all_days:
        hist[fires.get(d, 0)] += 1
    print("  days with 0/1/2/3 fires: %s (sessions=%d)"
          % ({k: hist[k] for k in sorted(hist)}, len(all_days)))

    print("\n8. live_scanner branch check")
    ls = (ROOT / "live_scanner.py").read_text(encoding="utf-8", errors="replace")
    print("  '3fires_stop_win_or_2loss' appears in live_scanner.py: %s"
          % ("3fires_stop_win_or_2loss" in ls))
    print("  branches present: one_and_done=%s"
          % ('_LIVE_DAY_POLICY == "one_and_done"' in ls))

    print("\n9b. The OTHER units on the same two books (the default book now")
    print("    carries the day-policy marks, so every unit that reads it moves)")
    from research.g72_suppress_price import shipped_rows, oneaday_rows
    for uname, fn in (("every_signal", shipped_rows), ("first_of_day", oneaday_rows)):
        line = []
        for label, rws in (("OFF", off_rows), ("ON", on_rows)):
            c = core(rws)
            picked = fn(c)
            f = figures(picked, len(sessions(rws)))
            line.append("%s: %d trades, $%.2f/day, %d/%d green"
                        % (label, f["trades"], f["per_day"], f["months_green"], f["months"]))
        print("  %-14s %s" % (uname, "   |   ".join(line)))

    print("\n9. FLAG_SOURCES check")
    from research import book_stamp as bs
    found = any("DAY_POLICY" in names for _mod, names in bs.FLAG_SOURCES)
    print("  DAY_POLICY in book_stamp.FLAG_SOURCES: %s" % found)
    print("=" * 78)


if __name__ == "__main__":
    main()
