"""L4 referee -- independent re-derivation of the TREND_DEF gate.

Refutes-or-upholds the builder's row L4 (commit f81db426, code commit
355d7cc0).  Nothing here imports research/loop_cycle.py or
research/g72_suppress_price.py: the unit, the monthly bucketing, the
$/day denominators and the gate are all re-implemented from their
written definitions so a bug in the builder's rig cannot reproduce
itself in the check.

Unit:   up_to_3_stop_win_or_2loss -- per session day, candidates are
        (status == 'fired' and traded) or status == 'halted', ordered by
        (et, sym); take up to 3, stop after the first winner, stop after
        the second loser.
Slice:  tier == 'core'   (loop.json universe.row_filter, CORE_SYMBOLS)
Fill:   close (meta.entry_fill), exit: shipped engine 1R hard stop +
        hod_then_runner_be ladder, per the book stamp.
$/day:  whole = total / meta.sessions ; halves = total / (distinct book
        days on that side of 2025-09-01).  A second, stricter denominator
        (distinct core-slice days) is printed beside it.

Run:  python research/l4_referee.py
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"
RISK = 1000.0
BOUNDARY = "2025-09-01"
MIN_TRADES = 30
MIN_MONTHS = 12
MAX_DROP_PCT = 5.0

OFF = TAPE / "book_TREND_DEF_off.json.gz"
ON = TAPE / "book_TREND_DEF_on.json.gz"
BASE = TAPE / "baseline_2026-09-05.json.gz"


def load(p: Path):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        b = json.load(f)
    return b["meta"], b["trades"]


def core(rows):
    return [r for r in rows if r.get("tier") == "core"]


def unit_rows(rows):
    """up_to_3_stop_win_or_2loss, re-implemented from the written rule."""
    byday = defaultdict(list)
    for r in rows:
        if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted":
            byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        losses = 0
        for i, r in enumerate(sorted(byday[day],
                                     key=lambda x: (x.get("et") or "", x.get("sym") or ""))):
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


def stats(urows, n_days):
    if not urows or not n_days:
        return {"trades": 0, "per_day": 0.0, "mean_r": 0.0, "win_pct": 0.0,
                "months": 0, "months_green": 0, "total": 0.0,
                "avg_win": 0.0, "avg_loss": 0.0, "awal": None}
    pnls = [r["pnl"] for r in urows]
    total = sum(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    by_m = defaultdict(float)
    for r in urows:
        by_m[r["day"][:7]] += r["pnl"]
    aw = sum(wins) / len(wins) if wins else 0.0
    al = abs(sum(losses) / len(losses)) if losses else 0.0
    return {
        "trades": len(urows),
        "total": round(total, 0),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(urows) / RISK, 4),
        "win_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 1) if (wins or losses) else 0.0,
        "months": len(by_m),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "avg_win": round(aw, 0),
        "avg_loss": round(al, 0),
        "awal": round(aw / al, 3) if al else None,
    }


def half_verdict(before, after, tag):
    enough = before["trades"] >= MIN_TRADES and before["months"] >= MIN_MONTHS
    if not enough:
        return {"half": tag, "enough": False, "pass": None}
    green_ok = after["months_green"] >= before["months_green"]
    b, a = before["per_day"], after["per_day"]
    if b > 0:
        dollar_ok = a >= b * (1 - MAX_DROP_PCT / 100.0)
    elif b < 0:
        dollar_ok = a >= b * (1 + MAX_DROP_PCT / 100.0)
    else:
        dollar_ok = a >= 0
    return {"half": tag, "enough": True, "pass": bool(green_ok and dollar_ok),
            "green_ok": green_ok, "dollar_ok": dollar_ok,
            "green": (before["months_green"], after["months_green"]),
            "dollars": (b, a)}


def slice_rows(rows, tag):
    if tag == "whole":
        return rows
    if tag == "h1":
        return [r for r in rows if r.get("day", "") < BOUNDARY]
    return [r for r in rows if r.get("day", "") >= BOUNDARY]


def main():
    off_meta, off_rows = load(OFF)
    on_meta, on_rows = load(ON)
    base_meta, base_rows = load(BASE)

    print("=" * 78)
    print("0. structure15_trend BEHAVIOUR, exercised directly")
    print("=" * 78)
    sys.path.insert(0, str(ROOT))
    import signal_runner as sr

    class C:
        def __init__(self, h, l):
            self.high, self.low = h, l

    def mk(n, hi0, lo0, step):
        return [C(hi0 + i * step, lo0 + i * step) for i in range(n)]

    checks = [
        ("default TREND_DEF is 'off'", sr.TREND_DEF, "off"),
        ("29 bars -> None (needs 2 full buckets)", sr.structure15_trend(mk(29, 10, 9, 0.01)), None),
        ("30 rising bars -> bullish", sr.structure15_trend(mk(30, 10, 9, 0.01)), "bullish"),
        ("30 falling bars -> bearish", sr.structure15_trend(mk(30, 10, 9, -0.01)), "bearish"),
        ("flat 30 bars (inside) -> None", sr.structure15_trend(mk(30, 10, 9, 0.0)), None),
        ("empty -> None", sr.structure15_trend([]), None),
        # 44 bars: n_full=2, so buckets are [0:15] and [15:30]; bars 30..43 are
        # IGNORED -- the read is up to 14 minutes stale by construction.
        ("44 bars, first 30 rising then 14 collapsing -> still bullish (stale)",
         sr.structure15_trend(mk(30, 10, 9, 0.01) + mk(14, 5, 4, -0.01)), "bullish"),
        ("45 bars, last 15 collapsing -> bearish (bucket completes)",
         sr.structure15_trend(mk(30, 10, 9, 0.01) + mk(15, 5, 4, -0.01)), "bearish"),
    ]
    for name, got, want in checks:
        print("  [%s] %-62s got=%s want=%s" % ("ok" if got == want else "**", name, got, want))
    # the gate is a no-op when the flag is off, whatever the trend says
    print("  [%s] _trend_ok is a no-op while TREND_DEF=='off'"
          % ("ok" if sr.TREND_DEF != "structure15" else "**"))

    print()
    print("=" * 78)
    print("1. STAMPS")
    print("=" * 78)
    ob, nb, bb = (m["stamp"]["book_id"] for m in (off_meta, on_meta, base_meta))
    print("baseline book_id      :", bb)
    print("OFF book_id           :", ob, "MATCHES BASELINE" if ob == bb else "*** MISMATCH ***")
    print("ON  book_id           :", nb, "(differs from OFF)" if nb != ob else "*** IDENTICAL ***")
    loop = json.loads((TAPE / "loop.json").read_text(encoding="utf-8"))
    print("loop.json baseline_id :", loop["baseline_book_id"],
          "MATCHES OFF" if loop["baseline_book_id"] == ob else "*** MISMATCH ***")
    of, nf = off_meta["stamp"]["flags"], on_meta["stamp"]["flags"]
    diffs = {k: (of.get(k), nf.get(k)) for k in set(of) | set(nf) if of.get(k) != nf.get(k)}
    print("flag diffs OFF vs ON  :", diffs, "-> ONE FLAG" if len(diffs) == 1 else "*** NOT ONE FLAG ***")
    for tag, m in (("OFF", off_meta), ("ON", on_meta)):
        g = m["stamp"]["git"]
        print("%s built_at=%s commit=%s dirty_engine=%s dirty_py=%s sessions=%s window=%s..%s"
              % (tag, m["stamp"]["built_at"], g["commit"][:8], g["dirty_engine_py"],
                 g["dirty_py_count"], m["sessions"], m["first"], m["last"]))

    print()
    print("=" * 78)
    print("2. GATE, RE-DERIVED (core-11, up_to_3_stop_win_or_2loss, close fill)")
    print("=" * 78)
    off_core, on_core = core(off_rows), core(on_rows)
    n_all = off_meta["sessions"]
    book_days = sorted({r["day"] for r in off_rows if r.get("day")})
    n_h1 = sum(1 for d in book_days if d < BOUNDARY)
    n_h2 = sum(1 for d in book_days if d >= BOUNDARY)
    core_days = sorted({r["day"] for r in off_core if r.get("day")})
    n_h1c = sum(1 for d in core_days if d < BOUNDARY)
    n_h2c = sum(1 for d in core_days if d >= BOUNDARY)
    print("sessions(meta)=%d  book days=%d (h1 %d / h2 %d)  core-slice days=%d (h1 %d / h2 %d)"
          % (n_all, len(book_days), n_h1, n_h2, len(core_days), n_h1c, n_h2c))

    denoms = {"whole": n_all, "h1": n_h1, "h2": n_h2}
    res = {}
    for tag in ("whole", "h1", "h2"):
        a = stats(unit_rows(slice_rows(off_core, tag)), denoms[tag])
        b = stats(unit_rows(slice_rows(on_core, tag)), denoms[tag])
        res[tag] = (a, b)
        print("\n[%s]  n_days=%d" % (tag, denoms[tag]))
        for lab, s in (("OFF", a), ("ON ", b)):
            print("  %s trades=%4d  total=%9.0f  $/day=%6.0f  meanR=%+.4f  win%%=%4.1f "
                  "avgW=%5.0f avgL=%5.0f  W/L=%s  green=%d/%d"
                  % (lab, s["trades"], s["total"], s["per_day"], s["mean_r"], s["win_pct"],
                     s["avg_win"], s["avg_loss"], s["awal"], s["months_green"], s["months"]))

    print("\ngate verdicts:")
    v1 = half_verdict(res["h1"][0], res["h1"][1], "H1")
    v2 = half_verdict(res["h2"][0], res["h2"][1], "H2")
    for v in (v1, v2):
        print("  ", v)
    decision = "ship" if (v1.get("pass") and v2.get("pass")) else "hold"
    print("  DECISION:", decision)

    print()
    print("=" * 78)
    print("3. BASELINE FIGURES IN loop.json vs OFF ARM")
    print("=" * 78)
    bf = loop["baseline_figures"]
    for tag in ("whole", "h1", "h2"):
        s = res[tag][0]
        want = bf[tag]
        for k in ("trades", "per_day", "months_green"):
            got = s[k]
            exp = want.get(k)
            flag = "ok" if got == exp else "*** DIFF ***"
            print("  %-5s %-13s loop.json=%-8s referee=%-8s %s" % (tag, k, exp, got, flag))

    print()
    print("=" * 78)
    print("4. DIRECTION-ELIGIBILITY FLIPS (fired, core, OFF vs ON)")
    print("=" * 78)

    def key(r):
        return (r["sym"], r["day"], r.get("et"), r.get("dir"), r.get("setup"))

    off_fired = {key(r): r for r in off_core if r.get("status") == "fired"}
    on_fired = {key(r): r for r in on_core if r.get("status") == "fired"}
    lost = set(off_fired) - set(on_fired)
    gained = set(on_fired) - set(off_fired)
    print("fired OFF=%d  fired ON=%d  lost=%d  gained=%d"
          % (len(off_fired), len(on_fired), len(lost), len(gained)))
    print("by setup, fired counts OFF:", dict(Counter(k[4] for k in off_fired)))
    print("by setup, fired counts ON :", dict(Counter(k[4] for k in on_fired)))
    print("by setup, LOST            :", dict(Counter(k[4] for k in lost)))
    print("by setup, GAINED          :", dict(Counter(k[4] for k in gained)))
    for setup in sorted({k[4] for k in lost}):
        traded = [off_fired[k] for k in lost if k[4] == setup and off_fired[k].get("traded")]
        if traded:
            mr = sum(r["r"] for r in traded) / len(traded)
            print("  LOST %-20s traded=%3d  mean r=%+.4f %s"
                  % (setup, len(traded), mr, "" if len(traded) >= 30 else "(n<30, not enough)"))
        else:
            print("  LOST %-20s traded=0" % setup)

    print()
    print("=" * 78)
    print("5. DID THE GATE TOUCH SETUPS IT SHOULD NOT? (BR rows)")
    print("=" * 78)
    br_lost = [k for k in lost if k[4] not in ("one_candle_rule", "reentry_84_rule")]
    br_gain = [k for k in gained if k[4] not in ("one_candle_rule", "reentry_84_rule")]
    print("non-OCR / non-84 fired rows lost:", len(br_lost), " gained:", len(br_gain))
    if br_lost:
        print("  sample:", br_lost[:5])
    if br_gain:
        print("  sample:", br_gain[:5])

    print()
    print("=" * 78)
    print("6. DIRECTION CHECK: do the surviving ON rows agree with a 15m read?")
    print("=" * 78)
    # cheap consistency probe: for the gated setups, the ON arm must not have
    # kept a row whose direction the flag would veto.  We cannot recompute the
    # trend without bars, so instead assert the structural invariant: no OCR /
    # 84% row is fired in ON that was NOT fired in OFF, EXCEPT through the
    # documented dedupe-release path (a released level slot).
    rel = [k for k in gained if k[4] in ("one_candle_rule", "reentry_84_rule")]
    print("OCR/84 rows fired only in ON (dedupe-release candidates):", len(rel))
    for k in rel[:10]:
        print("   ", k)

    print()
    print("=" * 78)
    print("7. REACHABILITY: when can structure15_trend return a non-None read?")
    print("=" * 78)
    # candles are RTH-only (backtest_week.fetch_* filters t < 09:30 into the
    # premarket bucket), so candles[0] is the 09:30 bar and the 15-candle
    # buckets are clock-aligned.  structure15_trend needs len(candles)//15 >= 2,
    # i.e. bar index >= 29 -> the 09:59 bar.  Every signal that fires before
    # 09:59 sees trend=None and the gate is a guaranteed no-op on it.
    def before(rows, cutoff):
        return sum(1 for r in rows if (r.get("et") or "99:99") < cutoff)

    for setup in ("one_candle_rule", "reentry_84_rule"):
        f = [r for r in off_core if r.get("status") == "fired" and r.get("setup") == setup]
        print("  %-18s fired OFF=%3d  of which et<09:59 (gate structurally cannot bite)=%3d (%.0f%%)"
              % (setup, len(f), before(f, "09:59"),
                 100.0 * before(f, "09:59") / len(f) if f else 0))
    brocr = [r for r in off_core
             if r.get("status") == "fired" and r.get("setup_label") == "BR+OCR"]
    print("  BR+OCR fired rows in OFF (an OCR-flavoured setup the gate never sees): %d"
          % len(brocr))

    print()
    print("=" * 78)
    print("8. WHERE THE $4,638 WENT (unit rows, whole window)")
    print("=" * 78)
    off_u = unit_rows(off_core)
    on_u = unit_rows(on_core)
    print("OFF unit total %.0f  ON unit total %.0f  delta %.0f"
          % (sum(r["pnl"] for r in off_u), sum(r["pnl"] for r in on_u),
             sum(r["pnl"] for r in on_u) - sum(r["pnl"] for r in off_u)))
    okeys = Counter(key(r) for r in off_u)
    nkeys = Counter(key(r) for r in on_u)
    only_off = [r for r in off_u if nkeys[key(r)] == 0]
    only_on = [r for r in on_u if okeys[key(r)] == 0]
    shared_off = sum(r["pnl"] for r in off_u if nkeys[key(r)] > 0)
    shared_on = sum(r["pnl"] for r in on_u if okeys[key(r)] > 0)
    print("  unit rows only in OFF: %3d  pnl %+9.0f" % (len(only_off), sum(r["pnl"] for r in only_off)))
    print("  unit rows only in ON : %3d  pnl %+9.0f" % (len(only_on), sum(r["pnl"] for r in only_on)))
    print("  shared unit rows pnl: OFF %+9.0f  ON %+9.0f (should match)" % (shared_off, shared_on))
    print("  only-in-OFF by setup :", dict(Counter(r["setup"] for r in only_off)))
    print("  only-in-ON  by setup :", dict(Counter(r["setup"] for r in only_on)))
    gset = set(gained)
    lset = set(lost)
    on_from_release = [r for r in only_on if key(r) in gset]
    on_from_reorder = [r for r in only_on if key(r) not in gset]
    off_from_gate = [r for r in only_off if key(r) in lset]
    off_from_reorder = [r for r in only_off if key(r) not in lset]
    print("  only-in-ON that are NEW fires (release): %d, pnl %+.0f"
          % (len(on_from_release), sum(r["pnl"] for r in on_from_release)))
    print("  only-in-ON that fired in BOTH books but the day-policy only reached in ON: %d, pnl %+.0f"
          % (len(on_from_reorder), sum(r["pnl"] for r in on_from_reorder)))
    print("  only-in-OFF that the gate removed outright: %d, pnl %+.0f"
          % (len(off_from_gate), sum(r["pnl"] for r in off_from_gate)))
    print("  only-in-OFF that still fire in ON but the day-policy no longer reaches: %d, pnl %+.0f"
          % (len(off_from_reorder), sum(r["pnl"] for r in off_from_reorder)))

    print()
    print("=" * 78)
    print("9. THE FIVE ROWS THAT MOVED THE BOOK, AND WHAT CHANGED ON THEIR DAYS")
    print("=" * 78)

    def pool(rows):
        """The unit's candidate pool, before the up-to-3 walk."""
        return [r for r in rows
                if (r.get("status") == "fired" and r.get("traded")) or r.get("status") == "halted"]

    off_pool = {key(r): r for r in pool(off_core)}
    on_pool = {key(r): r for r in pool(on_core)}
    moved_days = sorted({r["day"] for r in only_off} | {r["day"] for r in only_on})
    for d in moved_days:
        o = sorted([k for k in off_pool if k[1] == d], key=lambda k: (k[2], k[0]))
        n = sorted([k for k in on_pool if k[1] == d], key=lambda k: (k[2], k[0]))
        ou = [r for r in off_u if r["day"] == d]
        nu = [r for r in on_u if r["day"] == d]
        print("\n  %s   day pnl OFF %+8.0f -> ON %+8.0f   (delta %+.0f)"
              % (d, sum(r["pnl"] for r in ou), sum(r["pnl"] for r in nu),
                 sum(r["pnl"] for r in nu) - sum(r["pnl"] for r in ou)))
        print("    OFF candidate pool (%d):" % len(o))
        for k in o:
            r = off_pool[k]
            print("      %s %-5s %-18s %-4s %-11s pnl %+8.0f %s"
                  % (k[2], k[0], k[4], k[3], r.get("status"), r.get("pnl", 0),
                     "<TAKEN>" if any(key(x) == k for x in ou) else ""))
        print("    ON candidate pool (%d):" % len(n))
        for k in n:
            r = on_pool[k]
            print("      %s %-5s %-18s %-4s %-11s pnl %+8.0f %s"
                  % (k[2], k[0], k[4], k[3], r.get("status"), r.get("pnl", 0),
                     "<TAKEN>" if any(key(x) == k for x in nu) else ""))

    print()
    print("=" * 78)
    print("10. WHICH MONTHS FLIPPED GREEN->RED")
    print("=" * 78)
    mo, mn = defaultdict(float), defaultdict(float)
    for r in off_u:
        mo[r["day"][:7]] += r["pnl"]
    for r in on_u:
        mn[r["day"][:7]] += r["pnl"]
    for m in sorted(set(mo) | set(mn)):
        a, b = mo[m], mn[m]
        if (a > 0) != (b > 0):
            print("  %s  OFF %+9.0f (%s) -> ON %+9.0f (%s)  FLIP"
                  % (m, a, "green" if a > 0 else "red", b, "green" if b > 0 else "red"))
    print("  months green OFF=%d ON=%d" % (sum(1 for v in mo.values() if v > 0),
                                           sum(1 for v in mn.values() if v > 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
