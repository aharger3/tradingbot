"""ADVERSARIAL VERIFY (g71/sigfire): is `meta["signals"]` the raw capture length,
or the post-R16-dedupe row count? Instruments BacktestRunner and counts both on a
deterministic session sample. Read-only; writes nothing but stdout."""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf
import backtest_week as bw
from backtest_week import simulate_day, htf_bias_for
from backtest_12mo import hourly_from_1m
from universe import ALL_SYMS, has_archive

CNT = Counter()
_orig = bw.BacktestRunner._route


def _route(self, signals, sig):
    n = len(self.captured)
    _orig(self, signals, sig)
    if len(self.captured) > n:
        CNT["captured"] += 1
        CNT["cap:" + str(sig.get("status"))] += 1
        CNT["capgrade:" + str(sig.get("grade"))] += 1


bw.BacktestRunner._route = _route


def days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []


syms = [s for s in ALL_SYMS if has_archive(s, 100)][:6]
for sym in syms:
    ds = days(sym)[-40:]
    bars_by_day, hourly = {}, []
    for d in ds:
        try:
            b = pf.fetch_day(sym, d)
        except Exception:
            continue
        if not b:
            continue
        r = pf.rth(b)
        if len(r) < 30:
            continue
        bars_by_day[d] = (b, r)
        hourly += hourly_from_1m(d, r)
    prev = None
    for d in sorted(bars_by_day):
        b, rth = bars_by_day[d]
        if prev:
            _, p = bars_by_day[prev]
            pdh, pdl = max(c.high for c in p), min(c.low for c in p)
            pdo, pdc = p[0].open, p[-1].close
        else:
            pdh = pdl = pdo = pdc = None
        pmh, pml = pf.premarket_hi_lo(b)
        t = simulate_day(sym, d, rth, pdh, pdl, htf_bias_for(hourly, d), pmh, pml, pdo, pdc)
        CNT["rows"] += len(t)
        for x in t:
            CNT["row:" + str(x.status)] += 1
            CNT["rowgrade:" + str(x.grade)] += 1
        CNT["sessions"] += 1
        prev = d

print("sample: %d symbols %s, %d sessions" % (len(syms), syms, CNT["sessions"]))
print("captured (raw _route appends) : %d" % CNT["captured"])
print("rows (what backtest_2y counts): %d" % CNT["rows"])
print("dropped by R16 dedupe         : %d (%.1f%%)"
      % (CNT["captured"] - CNT["rows"],
         100.0 * (CNT["captured"] - CNT["rows"]) / max(1, CNT["captured"])))
for k in sorted(CNT):
    if k.startswith(("cap:", "row:", "capgrade:", "rowgrade:")):
        print("  %-24s %d" % (k, CNT[k]))
