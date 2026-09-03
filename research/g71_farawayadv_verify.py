"""ADVERSARIAL VERIFY of track `faraway` claim 2 (the runner TARGET DEGRADATION).

Independently re-derives, from the SHIPPED pipeline's own inputs, how often
`backtest_week.py:848-859` lets the unconditionally-appended whole dollar
`math.floor(scale_level)+1.0` win the min()/max() over a real PDH/PDL/PMH/PML.

Does NOT reuse research/g71_faraway.py. pdh/pdl/pmh/pml are rebuilt exactly the
way backtest_2y.py::main builds them (prev ARCHIVED day's RTH hi/lo chained
inside the >= start window; pf.premarket_hi_lo on the full day), so this is the
shipped book's own level roster, not p21's.

Read-only. Writes stdout + research/g71_farawayadv_verify.json.
"""
from __future__ import annotations
import json, math, sys, time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf
import backtest_week as bw
from universe import ALL_SYMS, has_archive

BOOK = ROOT / "research" / "bt2y_trades.json"


def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def main():
    raw = json.load(open(BOOK))
    meta = raw["meta"]
    rows = raw["trades"]
    traded = [t for t in rows if t.get("traded")]
    print("book %s  sessions=%d signals=%d traded=%d loss_halt=%s halted=%d"
          % (meta["generated"], meta["sessions"], meta["signals"],
             meta["traded"], meta["loss_halt"], meta["halted"]))
    print("window %s .. %s ; traded rows loaded = %d"
          % (meta["first"], meta["last"], len(traded)))
    print("SCALE_PLAN as imported = %r ; RULE6_ENABLED=%r"
          % (bw.SCALE_PLAN, getattr(bw, "RULE6_ENABLED", None)))

    by_day = defaultdict(list)
    for t in traded:
        by_day[(t["sym"], t["day"])].append(t)

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=730)).isoformat()

    n = 0
    miss_bars = 0
    src_count = defaultdict(int)
    psych_with_named_beyond = 0
    psych_no_named = 0
    named_by_name = defaultdict(int)
    over_extreme = []
    lost_r = []
    scaled_flag = defaultdict(int)
    detail = []

    t0 = time.time()
    for si, sym in enumerate(syms):
        days = [d for d in archive_days(sym) if d >= start]
        day_bars, prev = {}, None
        for d in days:
            try:
                bars = pf.fetch_day(sym, d)
            except Exception:
                continue
            if not bars:
                continue
            r = pf.rth(bars)
            if len(r) < 30:
                continue
            day_bars[d] = (bars, r)
        for d in sorted(day_bars):
            bars, rth = day_bars[d]
            if prev:
                _, prth = day_bars[prev]
                pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
            else:
                pdh = pdl = None
            pmh, pml = pf.premarket_hi_lo(bars)
            prev = d
            for t in by_day.get((sym, d), []):
                i = t.get("entry_i")
                if i is None or i >= len(rth):
                    miss_bars += 1
                    continue
                n += 1
                long = t["side"] == "L"
                entry, stop = t["entry"], t["stop"]
                risk = abs(entry - stop)
                if long:
                    scale = max(c.high for c in rth[:i + 1])
                    cands = [x for x in (pdh, pmh) if x is not None and x > scale]
                    psych = math.floor(scale) + 1.0
                    cands.append(psych)
                    tgt = min(cands)
                else:
                    scale = min(c.low for c in rth[:i + 1])
                    cands = [x for x in (pdl, pml) if x is not None and x < scale]
                    psych = math.ceil(scale) - 1.0
                    cands.append(psych)
                    tgt = max(cands)
                named = [x for x in cands if abs(x - psych) > 1e-12]
                src = "psych" if abs(tgt - psych) <= 1e-12 else "named"
                src_count[src] += 1
                scaled_flag[(src, bool(t.get("scaled")))] += 1
                if src == "psych":
                    over_extreme.append(abs(psych - scale))
                    if named:
                        psych_with_named_beyond += 1
                        best = min(named) if long else max(named)
                        if risk > 0:
                            lost_r.append(abs(best - psych) / risk)
                        pairs = ((("PDH", pdh), ("PMH", pmh)) if long
                                 else (("PDL", pdl), ("PML", pml)))
                        for nm, px in pairs:
                            if px is not None and ((px > scale) if long else (px < scale)):
                                named_by_name[nm] += 1
                    else:
                        psych_no_named += 1
                detail.append({"sym": sym, "day": d, "i": i, "side": t["side"],
                               "src": src, "scale": round(scale, 4),
                               "psych": psych, "tgt": round(tgt, 4),
                               "scaled": bool(t.get("scaled")),
                               "out": t["out"], "r": t["r"]})
        if (si + 1) % 25 == 0:
            print("  %d/%d syms  n=%d  %.0fs" % (si + 1, len(syms), n,
                                                 time.time() - t0), flush=True)

    tot = src_count["psych"] + src_count["named"]
    print("\n--- shipped runner-target source over TRADED rows ---")
    print("traded rows in book      : %d" % len(traded))
    print("rows evaluated           : %d   (missing bars/entry_i: %d)" % (n, miss_bars))
    print("psych (floor+1) won      : %d  (%.1f%% of evaluated, %.1f%% of traded)"
          % (src_count["psych"], 100.0 * src_count["psych"] / max(1, tot),
             100.0 * src_count["psych"] / max(1, len(traded))))
    print("named level won          : %d" % src_count["named"])
    print("  psych wins WITH a real named level beyond the scale point: %d"
          % psych_with_named_beyond)
    print("  psych wins with NO named level out there at all          : %d"
          % psych_no_named)
    print("  named-level breakdown among overrides: %s" % dict(named_by_name))
    if over_extreme:
        over_extreme.sort()
        print("psych target distance past the session extreme ($): "
              "min=%.4f med=%.4f max=%.4f"
              % (over_extreme[0], over_extreme[len(over_extreme) // 2], over_extreme[-1]))
    if lost_r:
        lost_r.sort()
        print("R given up vs the overridden named level: med=%.2fR mean=%.2fR max=%.2fR"
              % (lost_r[len(lost_r) // 2], sum(lost_r) / len(lost_r), lost_r[-1]))
    print("\n--- reachability: did the trade ever REACH the runner leg? ---")
    for k in sorted(scaled_flag):
        print("  src=%-5s scaled=%-5s : %d" % (k[0], k[1], scaled_flag[k]))
    sc = sum(v for k, v in scaled_flag.items() if k[1])
    print("  scaled at all: %d / %d (%.1f%%) -- only these ever test runner_target"
          % (sc, tot, 100.0 * sc / max(1, tot)))
    psych_scaled = scaled_flag[("psych", True)]
    print("  psych-degraded AND scaled: %d (%.1f%% of traded)"
          % (psych_scaled, 100.0 * psych_scaled / max(1, len(traded))))

    (ROOT / "research" / "g71_farawayadv_verify.json").write_text(
        json.dumps({"n": n, "traded": len(traded), "src": dict(src_count),
                    "psych_with_named": psych_with_named_beyond,
                    "psych_no_named": psych_no_named,
                    "named_by_name": dict(named_by_name),
                    "scaled": {"%s|%s" % (k[0], k[1]): v for k, v in scaled_flag.items()},
                    "detail": detail[:200]}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
