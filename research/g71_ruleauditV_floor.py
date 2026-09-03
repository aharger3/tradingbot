"""G7.1 ruleaudit ADVERSARIAL VERIFY -- is the -1.25R floor dead code?

Two questions the headline claim conflates:
  (a) is stop_rule.stop_fill_price REACHED?          -> count calls
  (b) does its -1.25R floor CHANGE a booked fill?    -> A/B floor_r=1.25 vs inf
Same 40 archive sessions, shipped defaults otherwise.
"""
import sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import backtest_week as bw, stop_rule, polygon_feed as pf
from stop_rule import stop_fill_price as ORIG
from universe import ALL_SYMS, has_archive

def archive_days(sym):
    d = ROOT / "data_archive" / sym
    return sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []

# which level was _stop_hit called with: the ORIGINAL stop or a moved one?
LV = collections.Counter()
_oh = bw._stop_hit
CUR = {}
def hit(c, level, long):
    r = _oh(c, level, long)
    if r:
        t = CUR.get("t")
        LV["fired_original_stop" if (t is not None and abs(level - t.stop) < 1e-12)
           else "fired_moved_stop"] += 1
    return r
_of = bw._stop_fill_px
def fillpx(t, c, long):
    CUR["t"] = t
    return _of(t, c, long)
bw._stop_hit = hit
bw._stop_fill_px = fillpx
# _stop_hit is called BEFORE _stop_fill_px, so seed CUR from the ladder instead:
_olb = bw._ladder_bar
def ladder(t, c, i, ot, r):
    CUR["t"] = t
    return _olb(t, c, i, ot, r)
bw._ladder_bar = ladder

N = 40
syms = [s for s in ALL_SYMS if has_archive(s, 100)]
allday = sorted({d for s in syms for d in archive_days(s)})[-N:]

def run(floor_r):
    bw.stop_fill_price = (lambda close, entry, risk, long: ORIG(close, entry, risk, long, floor_r=floor_r))
    rows = {}
    for sym in syms:
        days = set(archive_days(sym))
        for d in allday:
            if d not in days: continue
            try:
                rth = pf.rth(pf.fetch_day(sym, d))
            except Exception: continue
            if len(rth) < 30: continue
            try: tr = bw.simulate_day(sym, d, rth, None, None, None)
            except Exception: continue
            for t in tr:
                if t.counted:
                    rows[(sym, d, t.entry_time, round(t.entry,4))] = t.pnl / bw.RISK_DOLLARS
    return rows

LV.clear(); a = run(1.25); lv_a = dict(LV)
LV.clear(); b = run(float("inf"))
ka, kb = set(a), set(b)
diff = [(k, a[k], b[k]) for k in ka & kb if abs(a[k]-b[k]) > 1e-9]
print("_stop_hit fires by level:", lv_a)
print("floored n=%d meanR %+.4f worst %+.4f" % (len(a), sum(a.values())/len(a), min(a.values())))
print("nofloor n=%d meanR %+.4f worst %+.4f" % (len(b), sum(b.values())/len(b), min(b.values())))
print("rows whose booked R CHANGES when the -1.25R floor is removed: %d of %d shared"
      % (len(diff), len(ka & kb)))
print("R given back by removing the floor: %+.4f total" % sum(x[1]-x[2] for x in diff))
for k, x, y in sorted(diff, key=lambda z: z[1]-z[2], reverse=True)[:6]:
    print("   %s  floored %+.4f  nofloor %+.4f" % (k, x, y))
