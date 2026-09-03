"""G7.1 ruleaudit ADVERSARIAL VERIFY -- instrumented branch counter.

Runs the SHIPPED engine (backtest_week.simulate_day, defaults untouched) over a
sample of the local data_archive and counts, per exit, which stop branch fired:
  disaster  -- backtest_week._disaster_hit returned a price (intrabar TOUCH)
  level     -- backtest_week._stop_hit fired (close-triggered) and booked
                through _stop_fill_px (the -1.25R floor's only caller)
Also records whether stop_rule.stop_fill_price's floor CLAMPED (fill != close).

Usage: python research/g71_ruleauditV_branch.py [NDAYS]
"""
import sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import backtest_week as bw
import stop_rule
import polygon_feed as pf
from universe import ALL_SYMS, has_archive

C = collections.Counter()
CLAMP = []

_orig_dis = bw._disaster_hit
_orig_hit = bw._stop_hit
_orig_fillpx = bw._stop_fill_px

def dis(t, c, long):
    r = _orig_dis(t, c, long)
    C["disaster_called"] += 1
    if r is not None:
        C["disaster_fired"] += 1
    return r

def hit(c, level, long):
    r = _orig_hit(c, level, long)
    C["stophit_called"] += 1
    if r:
        C["stophit_fired"] += 1
    return r

def fillpx(t, c, long):
    px = _orig_fillpx(t, c, long)
    C["fillpx_called"] += 1
    if abs(px - c.close) > 1e-9:
        C["floor_clamped"] += 1
        CLAMP.append((t.symbol, t.day, round(c.close, 4), round(px, 4)))
    return px

bw._disaster_hit, bw._stop_hit, bw._stop_fill_px = dis, hit, fillpx

def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
syms = [s for s in ALL_SYMS if has_archive(s, 100)]
allday = sorted({d for s in syms for d in archive_days(s)})[-N:]
print("DISASTER_STOP=%s DISASTER_R=%s STOP_ON_CLOSE=%s SCALE_PLAN=%r BE_TRIGGER=%r"
      % (bw.DISASTER_STOP, bw.DISASTER_R, bw.STOP_ON_CLOSE, bw.SCALE_PLAN, bw.BE_TRIGGER))
print("syms=%d days=%d (%s..%s)" % (len(syms), len(allday), allday[0], allday[-1]))

OUT = collections.Counter(); RS = []
for sym in syms:
    days = set(archive_days(sym))
    for d in allday:
        if d not in days:
            continue
        try:
            bars = pf.fetch_day(sym, d)
            rth = pf.rth(bars)
        except Exception:
            continue
        if len(rth) < 30:
            continue
        try:
            tr = bw.simulate_day(sym, d, rth, None, None, None)
        except Exception:
            continue
        for t in tr:
            if not t.counted:
                continue
            OUT[t.outcome] += 1
            RS.append(t.pnl / bw.RISK_DOLLARS)
            if t.outcome == "loss":
                risk = abs(t.entry - t.stop)
                dpx = stop_rule.disaster_stop_price(t.entry, risk, t.direction == "call", bw.DISASTER_R)
                OUT["loss_at_disaster_px" if abs(t.exit_price - dpx) < 1e-9 else "loss_elsewhere"] += 1

print("counters:", dict(C))
print("outcomes:", dict(OUT))
print("traded=%d" % len(RS))
if RS:
    print("meanR %+.4f  worst %+.4f  rows at exactly -1.0000R: %d  at -1.2500R: %d"
          % (sum(RS)/len(RS), min(RS),
             sum(1 for r in RS if abs(r + 1.0) < 1e-9),
             sum(1 for r in RS if abs(r + 1.25) < 1e-9)))
print("floor CLAMP events:", C["floor_clamped"], CLAMP[:10])
