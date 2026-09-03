"""ADVERSARIAL VERIFY, part 2: how often does the degraded runner target
actually DETERMINE an exit?

Reuses the reproduction in g71_farawayadv_verify but adds the exit test:
a row's runner target only matters if (a) the trade scaled (backtest_week.py
:521 `if not t.scaled: ... return` -- runner_target is read only at :579/:604)
and (b) the recorded exit price equals that target.
"""
from __future__ import annotations
import json, math, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf
from universe import ALL_SYMS, has_archive


def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


def main():
    raw = json.load(open(ROOT / "research" / "bt2y_trades.json"))
    traded = [t for t in raw["trades"] if t.get("traded")]
    by_day = defaultdict(list)
    for t in traded:
        by_day[(t["sym"], t["day"])].append(t)

    syms = [s for s in ALL_SYMS if has_archive(s, 100)]
    last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
    start = (date.fromisoformat(last) - timedelta(days=730)).isoformat()

    c = defaultdict(int)
    exit_r = defaultdict(list)
    for sym in syms:
        day_bars, prev = {}, None
        for d in [x for x in archive_days(sym) if x >= start]:
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
                pdh, pdl = max(x.high for x in prth), min(x.low for x in prth)
            else:
                pdh = pdl = None
            pmh, pml = pf.premarket_hi_lo(bars)
            prev = d
            for t in by_day.get((sym, d), []):
                i = t.get("entry_i")
                if i is None or i >= len(rth):
                    continue
                long = t["side"] == "L"
                if long:
                    scale = max(x.high for x in rth[:i + 1])
                    cands = [x for x in (pdh, pmh) if x is not None and x > scale]
                    psych = math.floor(scale) + 1.0
                    cands.append(psych)
                    tgt = min(cands)
                else:
                    scale = min(x.low for x in rth[:i + 1])
                    cands = [x for x in (pdl, pml) if x is not None and x < scale]
                    psych = math.ceil(scale) - 1.0
                    cands.append(psych)
                    tgt = max(cands)
                src = "psych" if abs(tgt - psych) <= 1e-12 else "named"
                sc = bool(t.get("scaled"))
                hit = abs(round(tgt, 2) - t["exit"]) <= 0.011
                c[(src, sc, hit)] += 1
                if src == "psych" and sc and hit:
                    exit_r["psych_target_exit"].append(t["r"])

    print("(src, scaled, exit==runner_target) -> rows")
    for k in sorted(c):
        print("  %-6s scaled=%-5s tgt_exit=%-5s : %d" % (k[0], k[1], k[2], c[k]))
    tot = sum(c.values())
    psych = sum(v for k, v in c.items() if k[0] == "psych")
    psych_sc = sum(v for k, v in c.items() if k[0] == "psych" and k[1])
    psych_hit = sum(v for k, v in c.items() if k[0] == "psych" and k[1] and k[2])
    print("\ntotal evaluated                   : %d" % tot)
    print("psych degraded                    : %d  (%.1f%%)" % (psych, 100.0 * psych / tot))
    print("psych AND scaled (runner leg read): %d  (%.1f%%)" % (psych_sc, 100.0 * psych_sc / tot))
    print("psych AND exited AT that target   : %d  (%.1f%%)" % (psych_hit, 100.0 * psych_hit / tot))
    v = exit_r["psych_target_exit"]
    if v:
        print("mean R on those                   : %+.4f  (n=%d)" % (sum(v) / len(v), len(v)))


if __name__ == "__main__":
    main()
