"""G7.1 adversarial verify (router claim): does backtest_week's dedupe map get
armed by NON-fired captured signals, and if so does that ever suppress a signal
that WOULD have fired?

No engine file is edited. `backtest_week.dedupe_window` is monkeypatched with a
frame-inspecting shim: it is called on line 830 for every captured signal,
before the `seen[key] = i` write, so the caller frame hands us `seen`, `key`,
`i` and `sig` exactly as the real loop sees them.

Usage: python research/g71_router_dedupe_probe.py [--syms N]
"""
import sys, inspect, argparse, json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import polygon_feed as pf
import backtest_week as bw
from backtest_week import simulate_day, htf_bias_for
from backtest_2y import archive_days
from backtest_12mo import hourly_from_1m, qqq_level_breaks
from universe import ALL_SYMS, has_archive

EV = Counter()
SUPPRESSED = []          # rows a preceding non-fired signal killed
SHADOW = {}              # id(seen) -> {key: status of last writer}
_real = bw.dedupe_window


def shim():
    w = _real()
    f = inspect.currentframe().f_back
    L = f.f_locals
    if "seen" not in L or "key" not in L:
        return w
    seen, key, i, sig = L["seen"], L["key"], L["i"], L["sig"]
    sh = SHADOW.setdefault((L.get("symbol"), L.get("day_iso")), {})
    cur = sig.get("status")            # set by BacktestRunner._route before capture
    prev = sh.get(key)
    fires = key in seen and i - seen[key] < w
    EV["signals"] += 1
    if fires:
        EV["suppressed_total"] += 1
        EV["suppressed_%s_by_%s" % (cur, prev)] += 1
        if cur == "fired" and prev != "fired":
            SUPPRESSED.append({"sym": L.get("symbol"), "day": L.get("day_iso"),
                               "bar": i, "gap": i - seen[key], "key": str(key),
                               "grade": sig.get("grade"), "killer": prev})
    sh[key] = cur
    return w


bw.dedupe_window = shim

ap = argparse.ArgumentParser()
ap.add_argument("--syms", type=int, default=0)
ap.add_argument("--days", type=int, default=730)
a = ap.parse_args()

syms = [s for s in ALL_SYMS if has_archive(s, 100)]
if a.syms:
    syms = syms[:a.syms]
last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
start = (date.fromisoformat(last) - timedelta(days=a.days)).isoformat()
window = sorted({d for s in syms for d in archive_days(s) if d >= start})
qqq_brk = qqq_level_breaks(window)

fired_book = 0
for sym in syms:
    days = [d for d in archive_days(sym) if d >= start]
    day_bars, hourly = {}, []
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
        hourly += hourly_from_1m(d, r)
    prev = None
    for d in sorted(day_bars):
        bars, rth = day_bars[d]
        if prev:
            _, prth = day_bars[prev]
            pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
            pdo, pdc = prth[0].open, prth[-1].close
        else:
            pdh = pdl = pdo = pdc = None
        pmh, pml = pf.premarket_hi_lo(bars)
        bias = htf_bias_for(hourly, d)
        tr = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                          qqq=qqq_brk.get(d))
        fired_book += sum(1 for t in tr if t.status == "fired")
        prev = d
    print("  %-6s done" % sym, flush=True)

print(json.dumps({"syms": len(syms), "sessions": len(window),
                  "fired_rows_in_book": fired_book,
                  "counts": dict(EV),
                  "fired_killed_by_nonfired": len(SUPPRESSED),
                  "killer_mix": dict(Counter(x["killer"] for x in SUPPRESSED)),
                  "sample": SUPPRESSED[:10]}, indent=1))
