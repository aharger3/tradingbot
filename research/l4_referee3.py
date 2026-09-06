"""l4_referee3.py -- L4 referee pass 3 (a different model, told to refute).

Independent re-derivation of every number in research/l4_trend_def.md as
repaired at commit 746ccc2a, from the two stamped books
research/tape/book_TREND_DEF_{off,on}.json.gz.

Nothing here imports research/loop_cycle.py, research/g72_suppress_price.py,
research/l4_referee.py or research/l4_referee2*.py: the unit, the monthly
bucketing, the $/day denominators, the gate and the 15-minute structure read
are all re-typed from their written definitions, so a bug in the builder's rig
(or in either earlier referee's rig) cannot reproduce itself in this check.

    python research/l4_referee3.py            # books only (fast)
    python research/l4_referee3.py --bars     # + the raw-bar semantics pass
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
GATED = {"one_candle_rule", "reentry_84_rule"}


def load(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


# ---------------------------------------------------------------- the unit

def up_to_3(rows):
    """His day policy, re-typed from the spec sentence: up to 3 fired-and-traded
    candidates a day (plus the account-halt rows the halt blocked), in time
    order; stop after the first winner, stop after the second loser."""
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
            if r.get("pnl", 0.0) > 0:
                break
            if r.get("pnl", 0.0) < 0:
                losses += 1
                if losses >= 2:
                    break
    return out


def figures(unit_rows, n_days):
    if not unit_rows:
        return None
    pnl = [r["pnl"] for r in unit_rows]
    total = sum(pnl)
    w = [p for p in pnl if p > 0]
    l = [p for p in pnl if p < 0]
    bym = defaultdict(float)
    for r in unit_rows:
        bym[r["day"][:7]] += r["pnl"]
    aw = sum(w) / len(w) if w else 0.0
    al = abs(sum(l) / len(l)) if l else 0.0
    return {
        "trades": len(unit_rows),
        "total": round(total),
        "per_day": round(total / n_days),
        "mean_r": round(total / len(unit_rows) / RISK, 4),
        "win_pct": round(len(w) / (len(w) + len(l)) * 100, 1) if (w or l) else 0.0,
        "avg_win": round(aw),
        "avg_loss": round(al),
        "wl": round(aw / al, 3) if al else None,
        "months": len(bym),
        "green": sum(1 for v in bym.values() if v > 0),
        "n_days": n_days,
    }


def slice_all(meta, rows):
    days = sorted({r["day"] for r in rows if r.get("day")})
    n1 = sum(1 for d in days if d < BOUNDARY)
    n2 = sum(1 for d in days if d >= BOUNDARY)
    whole = figures(up_to_3(rows), meta.get("sessions") or len(days))
    h1 = figures(up_to_3([r for r in rows if r["day"] < BOUNDARY]), n1)
    h2 = figures(up_to_3([r for r in rows if r["day"] >= BOUNDARY]), n2)
    return {"whole": whole, "h1": h1, "h2": h2}


def half_verdict(b, a, max_drop_pct=5.0):
    enough = b["trades"] >= 30 and b["months"] >= 12
    if not enough:
        return {"enough": False, "pass": None}
    green_ok = a["green"] >= b["green"]
    bd, ad = b["per_day"], a["per_day"]
    if bd > 0:
        dollar_ok = ad >= bd * (1 - max_drop_pct / 100.0)
    elif bd < 0:
        dollar_ok = ad >= bd * (1 + max_drop_pct / 100.0)
    else:
        dollar_ok = ad >= 0
    return {"enough": True, "pass": bool(green_ok and dollar_ok),
            "green_ok": green_ok, "dollar_ok": dollar_ok}


def key(r):
    return (r["day"], r.get("et"), r["sym"], r.get("dir"), r.get("setup"))


def main():
    off_meta, off_all = load(TAPE / "book_TREND_DEF_off.json.gz")
    on_meta, on_all = load(TAPE / "book_TREND_DEF_on.json.gz")
    base_meta, base_all = load(TAPE / "baseline_2026-09-05.json.gz")

    print("=" * 78)
    print("1. STAMPS")
    for name, m in (("OFF", off_meta), ("ON", on_meta), ("baseline", base_meta)):
        s = m["stamp"]
        print("  %-8s book_id=%s commit=%s dirty_engine=%s dirty_py=%s built=%s rows=%d win=%s..%s sessions=%s"
              % (name, s.get("book_id"), s["git"]["commit"][:8], s["git"]["dirty_engine_py"],
                 s["git"]["dirty_py_count"], s["built_at"], m["signals"],
                 m["first"], m["last"], m["sessions"]))
    cfg = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))
    print("  loop.json baseline_book_id = %s" % cfg["baseline_book_id"])
    print("  OFF == baseline book_id  : %s" % (off_meta["stamp"]["book_id"] == base_meta["stamp"]["book_id"]))
    print("  OFF == loop.json baseline: %s" % (off_meta["stamp"]["book_id"] == cfg["baseline_book_id"]))
    fo, fn = off_meta["stamp"]["flags"], on_meta["stamp"]["flags"]
    diff = {k: (fo.get(k), fn.get(k)) for k in set(fo) | set(fn) if fo.get(k) != fn.get(k)}
    print("  flag-dict differences OFF vs ON: %s" % diff)
    print("  script in stamp: OFF=%r ON=%r" % (off_meta["stamp"].get("script"), on_meta["stamp"].get("script")))
    print("  stamp keys: %s" % sorted(off_meta["stamp"].keys()))

    off = [r for r in off_all if r.get("tier") == "core"]
    on = [r for r in on_all if r.get("tier") == "core"]
    print("  core rows OFF=%d ON=%d (of %d / %d)" % (len(off), len(on), len(off_all), len(on_all)))

    print("=" * 78)
    print("2. THE GATE, re-derived (unit up_to_3_stop_win_or_2loss, core-11, close fill)")
    A, B = slice_all(off_meta, off), slice_all(on_meta, on)
    hdr = "  %-6s %-4s %6s %9s %7s %8s %6s %7s %7s %6s %6s"
    print(hdr % ("slice", "arm", "trades", "total$", "$/day", "meanR", "win%", "avgW", "avgL", "green", "mo"))
    for sl in ("whole", "h1", "h2"):
        for nm, d in (("OFF", A[sl]), ("ON", B[sl])):
            print(hdr % (sl, nm, d["trades"], d["total"], d["per_day"], d["mean_r"],
                         d["win_pct"], d["avg_win"], d["avg_loss"], d["green"], d["months"]))
    h1v, h2v = half_verdict(A["h1"], B["h1"]), half_verdict(A["h2"], B["h2"])
    print("  H1 verdict: %s" % h1v)
    print("  H2 verdict: %s" % h2v)
    print("  DECISION  : %s" % ("ship" if (h1v["enough"] and h1v["pass"] and h2v["enough"] and h2v["pass"]) else "hold"))

    print("=" * 78)
    print("3. FIRED-ROW FLIPS by setup (core tier, status=='fired')")
    ko = {key(r): r for r in off if r.get("status") == "fired"}
    kn = {key(r): r for r in on if r.get("status") == "fired"}
    setups = sorted({k[4] for k in ko} | {k[4] for k in kn})
    print("  %-22s %8s %8s %8s %8s" % ("setup", "OFF", "ON", "lost", "gained"))
    for s in setups:
        o = {k for k in ko if k[4] == s}
        n = {k for k in kn if k[4] == s}
        print("  %-22s %8d %8d %8d %8d" % (s, len(o), len(n), len(o - n), len(n - o)))
    lost = [ko[k] for k in set(ko) - set(kn) if k[4] in GATED]
    for s in ("one_candle_rule", "reentry_84_rule"):
        lo = [ko[k] for k in set(ko) - set(kn) if k[4] == s]
        traded = [r for r in lo if r.get("traded")]
        mr = sum(r["r"] for r in traded) / len(traded) if traded else 0.0
        print("  %-22s lost=%d of which traded=%d mean r=%.4f  (30-trade floor: %s)"
              % (s, len(lo), len(traded), mr, "CLEARS" if len(traded) >= 30 else "UNDER -> not enough"))

    print("  setup_label counts in OFF core (fired):")
    print("   ", Counter(r.get("setup_label") for r in off if r.get("status") == "fired").most_common())
    gated_fired = sum(1 for r in off if r.get("status") == "fired" and r.get("setup") in GATED)
    br_fired = sum(1 for r in off if r.get("status") == "fired" and r.get("setup") == "break_and_retest")
    brocr_fired = sum(1 for r in off if r.get("status") == "fired" and r.get("setup_label") == "BR+OCR")
    print("  gated fired core rows      : %d" % gated_fired)
    print("  break_and_retest fired core: %d  (ratio to gated %.2fx)" % (br_fired, br_fired / gated_fired))
    print("  setup_label BR+OCR fired   : %d  (ratio to gated %.2fx)" % (brocr_fired, brocr_fired / gated_fired))

    print("=" * 78)
    print("4. THE DEDUPE-RELEASE CLAIM: are the ON-only fired rows absent from the OFF book?")
    for s in ("reentry_84_rule", "break_and_retest", "one_candle_rule"):
        gained = [kn[k] for k in set(kn) - set(ko) if k[4] == s]
        if not gained:
            continue
        offidx = defaultdict(list)
        for r in off:
            offidx[key(r)].append(r)
        st = Counter()
        for r in gained:
            rows = offidx.get(key(r), [])
            st[";".join(sorted(x.get("status") for x in rows)) or "ABSENT FROM OFF BOOK"] += 1
        print("  %-18s gained=%d -> same key in the OFF book with status: %s"
              % (s, len(gained), dict(st)))
        for r in gained[:12]:
            rows = offidx.get(key(r), [])
            print("     %s %s %-5s %-4s off:%s off_pnl=%s on_traded=%s on_pnl=%s"
                  % (r["day"], r["et"], r["sym"], r["dir"],
                     [x.get("status") for x in rows] or "ABSENT",
                     [x.get("pnl") for x in rows] or "-", r.get("traded"), r.get("pnl")))
        # do any of them reach the traded unit?
        u = {key(r) for r in up_to_3(on)}
        print("     of those, rows that reach the ON unit: %d"
              % sum(1 for r in gained if key(r) in u))

    print("=" * 78)
    print("5. WHERE THE UNIT MOVED (day level, no join)")
    ua, ub = up_to_3(off), up_to_3(on)
    da, db = defaultdict(float), defaultdict(float)
    for r in ua:
        da[r["day"]] += r["pnl"]
    for r in ub:
        db[r["day"]] += r["pnl"]
    moved = sorted(((d, da.get(d, 0.0), db.get(d, 0.0)) for d in set(da) | set(db)
                    if abs(da.get(d, 0.0) - db.get(d, 0.0)) > 1e-6),
                   key=lambda x: x[1] - x[2], reverse=True)
    tot = sum(a - b for _, a, b in moved)
    print("  days that move: %d, summing to %+.0f (whole-window unit delta OFF-ON)" % (len(moved), tot))
    for d, a, b in moved:
        print("     %s OFF %+9.0f ON %+9.0f delta %+9.0f" % (d, a, b, b - a))
    bym_a, bym_b = defaultdict(float), defaultdict(float)
    for r in ua:
        bym_a[r["day"][:7]] += r["pnl"]
    for r in ub:
        bym_b[r["day"][:7]] += r["pnl"]
    flipped = [(m, bym_a[m], bym_b.get(m, 0.0)) for m in sorted(bym_a)
               if (bym_a[m] > 0) != (bym_b.get(m, 0.0) > 0)]
    print("  months whose sign flips: %s" % [(m, round(a), round(b)) for m, a, b in flipped])

    if "--bars" in sys.argv:
        bars_pass(off, ko, kn)


# ------------------------------------------------------- the raw-bar pass

def my_structure15(bars):
    """Re-typed from the rulebook sentence, NOT imported from signal_runner:
    consecutive 15-candle buckets from the session start, trailing partial
    bucket dropped, higher-high AND higher-low = bullish, lower-high AND
    lower-low = bearish, anything else None."""
    n_full = len(bars) // 15
    if n_full < 2:
        return None
    last = bars[(n_full - 1) * 15: n_full * 15]
    prev = bars[(n_full - 2) * 15: (n_full - 1) * 15]
    lh, ll = max(c.high for c in last), min(c.low for c in last)
    ph, pl = max(c.high for c in prev), min(c.low for c in prev)
    if lh > ph and ll > pl:
        return "bullish"
    if lh < ph and ll < pl:
        return "bearish"
    return None


def bars_pass(off, ko, kn):
    import polygon_feed as pf
    from signal_runner import structure15_trend as engine_trend

    print("=" * 78)
    print("6. RAW-BAR SEMANTICS (own re-implementation, bar list truncated at the signal bar)")
    gated_fired = [r for r in off if r.get("status") == "fired" and r.get("setup") in GATED]
    lostk = set(ko) - set(kn)
    cache = {}

    def bars(sym, day):
        if (sym, day) not in cache:
            try:
                cache[(sym, day)] = pf.rth(pf.fetch_day(sym, day))
            except Exception:
                cache[(sym, day)] = []
        return cache[(sym, day)]

    firsts = Counter()
    for sym, day in sorted({(r["sym"], r["day"]) for r in gated_fired}):
        b = bars(sym, day)
        firsts[b[0].timestamp if b else "NO BARS"] += 1
    print("  first RTH bar over %d touched sessions: %s" % (sum(firsts.values()), dict(firsts)))

    reach = Counter()
    lag = Counter()
    mismatch = 0
    cascades = []
    for r in gated_fired:
        b = bars(r["sym"], r["day"])
        want = (r.get("et") or "") + ":00"
        idx = next((i for i, c in enumerate(b) if c.timestamp == want), None)
        if idx is None:
            reach["no bars"] += 1
            continue
        trunc = b[: idx + 1]
        t = my_structure15(trunc)
        if t != engine_trend(trunc):
            mismatch += 1
        removed = key(r) in lostk
        if t is None:
            reach["abstain"] += 1
            blocked = False
        elif (t == "bullish") == (r.get("dir") == "call"):
            reach["allowed"] += 1
            blocked = False
        else:
            reach["blocked"] += 1
            blocked = True
        if removed and not blocked:
            cascades.append((r["day"], r["et"], r["sym"], r["dir"], r["setup"], t))
        if not removed and blocked:
            cascades.append(("KEPT-BUT-BLOCKED", r["day"], r["et"], r["sym"], r["setup"], t))
        lag[(idx + 1) % 15] += 1
    print("  reach over %d fired gated rows: %s" % (len(gated_fired), dict(reach)))
    print("  my re-implementation vs signal_runner.structure15_trend: %d mismatches" % mismatch)
    print("  removals whose own trend read ALLOWS the trade (cascades): %d" % len(cascades))
    for c in cascades:
        print("     ", c)
    tot = sum(lag.values())
    stale = sum(v for k, v in lag.items() if k >= 10)
    print("  staleness (bars past the last completed bucket): %s" % dict(sorted(lag.items())))
    print("  >=10 minutes stale: %d of %d (%.0f%%), max %d" % (stale, tot, 100.0 * stale / tot, max(lag)))


if __name__ == "__main__":
    main()
