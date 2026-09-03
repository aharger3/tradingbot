"""G7.1 rtarget ADVERSARIAL VERIFY -- is min(r,2.0) the right model of the live 2R exit?

The claim (research/g71_rtarget.md sec.2, research/g71_rtarget_model.py:385-397)
models the live path by clipping every booked R at 2.0. But the live target is a
RESTING LIMIT ORDER and fills on any intrabar TOUCH -- paper_trader.py:132-143
`_check_target(high, low)` compares high/low, not close, and its own docstring
says "a target is a resting limit order and fills on any intrabar touch."

So the clip is ONE-SIDED. It removes the upside above 2R, but it does not book
the +2R that the live target would have taken on every trade whose HIGH reached
the 2R level and then gave it back -- including trades the shipped scale/runner
exit turned into losers.

This replays the archived RTH bars for P1's 496 one-trade-a-day rows and builds
the CORRECT live model:
    walk bars from entry+1, wick-touch of the 2R level BEFORE a close-based stop
        -> +2.0R (the live limit fills)
    otherwise                                   -> the same stop / EOD exit
Fill rule is stop_rule.stop_fill_price(), never re-implemented here.
"""
import json, statistics, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research"))
import polygon_feed as pf
from stop_rule import (stop_hit_on_close, stop_fill_price, disaster_stop_price,
                       disaster_stop_hit)
import g71_firsts_policy as F

bk = json.loads((ROOT / "research" / "bt2y_trades.json").read_text(encoding="utf-8"))
counted = [r for r in bk["trades"]
           if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
by_day = defaultdict(list)
for r in counted:
    by_day[r["day"]].append(r)
for d in by_day:
    by_day[d].sort(key=F.ekey)

picked = []
for d in sorted(by_day):
    picked.extend(F.walk(by_day[d], F.P_FIRST))
print("P1 rows: %d over %d days" % (len(picked), len(by_day)))

bars_cache = {}
def rth_for(sym, day):
    k = (sym, day)
    if k not in bars_cache:
        try:
            bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            bars_cache[k] = []
    return bars_cache[k]

rows, miss = [], 0
for r in picked:
    rth = rth_for(r["sym"], r["day"])
    i0 = r.get("entry_i")
    if not rth or i0 is None or i0 >= len(rth):
        miss += 1; continue
    entry, stop = r["entry"], r["stop"]
    long = r["dir"] == "call"
    risk = abs(entry - stop)
    if risk <= 0:
        miss += 1; continue
    tgt2 = entry + 2.0 * risk if long else entry - 2.0 * risk
    dz = disaster_stop_price(entry, risk, long)
    mfe = 0.0
    touched2 = False
    exit_px, exited = rth[-1].close, False
    for i in range(i0 + 1, len(rth)):
        c = rth[i]
        fav = (c.high - entry) if long else (entry - c.low)
        mfe = max(mfe, fav / risk)
        # limit order: the 2R touch fills INTRABAR, before any close-based stop
        if (c.high >= tgt2) if long else (c.low <= tgt2):
            touched2 = True
            exit_px, exited = tgt2, True
            break
        if disaster_stop_hit(c.high, c.low, dz, long):
            exit_px, exited = dz, True; break
        if stop_hit_on_close(c.close, stop, long):
            exit_px, exited = stop_fill_price(c.close, entry, risk, long), i; break
    live_r = ((exit_px - entry) if long else (entry - exit_px)) / risk
    rows.append({"day": r["day"], "booked": r["r"], "mfe": mfe,
                 "touched2": touched2, "live_r": live_r})

n = len(rows)
print("replayed %d  (skipped %d)" % (n, miss))
bkd = [x["booked"] for x in rows]
clip = [min(x["booked"], 2.0) for x in rows]
live = [x["live_r"] for x in rows]
t2 = sum(1 for x in rows if x["touched2"])
booked_over = sum(1 for x in rows if x["booked"] > 2 + 1e-9)

def line(lbl, v):
    w = sum(1 for x in v if x > 0)
    print("  %-34s n=%d  mean %+0.4fR  total %+8.2fR  win %5.2f%%  E$/day $%d"
          % (lbl, len(v), statistics.fmean(v), sum(v), 100*w/len(v),
             round(statistics.fmean(v) * 1000)))

print("\n-- on the %d rows that replayed --" % n)
line("A. shipped backtest exit (booked)", bkd)
line("B. CLAIM's model  min(booked, 2.0)", clip)
line("C. TRUE live 2R limit (wick touch)", live)
print("\n  rows whose BOOKED r exceeded 2R      : %d (%.2f%%)" % (booked_over, 100*booked_over/n))
print("  rows that TOUCHED the 2R level       : %d (%.2f%%)" % (t2, 100*t2/n))
print("  touched 2R but booked <= 2R          : %d" % sum(1 for x in rows if x["touched2"] and x["booked"] <= 2 + 1e-9))
print("  touched 2R and booked a LOSS         : %d, booked %+0.2fR, live books %+0.2fR"
      % (sum(1 for x in rows if x["touched2"] and x["booked"] < 0),
         sum(x["booked"] for x in rows if x["touched2"] and x["booked"] < 0),
         2.0 * sum(1 for x in rows if x["touched2"] and x["booked"] < 0)))
print("\n  CLAIM says live mean R = %+0.4f ; true live model = %+0.4f  (delta %+0.4fR/trade)"
      % (statistics.fmean(clip), statistics.fmean(live),
         statistics.fmean(live) - statistics.fmean(clip)))
print("  E$/day:  claim $%d   true $%d   (backtest exit $%d)"
      % (round(statistics.fmean(clip)*1000), round(statistics.fmean(live)*1000),
         round(statistics.fmean(bkd)*1000)))

# "half of all profit" -- net vs gross
over = [x for x in bkd if x > 2.0]
gross = sum(x for x in bkd if x > 0)
print("\n  excess above 2R = %+0.2fR ; net total %+0.2fR (%.1f%%) ; GROSS profit %+0.2fR (%.1f%%)"
      % (sum(x-2 for x in over), sum(bkd), 100*sum(x-2 for x in over)/sum(bkd),
         gross, 100*sum(x-2 for x in over)/gross))
