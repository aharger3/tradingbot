"""g71 (rrcap): what the exit cap costs. Post-hoc replay over the archived RTH
bars of research/bt2y_trades.json's traded rows -- no engine re-run, no new
fill rule (stop_rule.py is the one definition).

For every traded row:
  booked R          : as the shipped exit (SCALE_PLAN=hod_then_runner_be) booked it
  MFE R             : max favourable excursion from the entry bar to the exit the
                      trade would have had with NO TARGET AT ALL
  no-target R       : R if the same stop (disaster touch -1R, level stop on close,
                      floored -1.25R) ran to EOD with no profit target
Answers: how many rows COULD have run past 2R, and how many actually did.
"""
import json, statistics, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import polygon_feed as pf
from stop_rule import (stop_hit_on_close, stop_fill_price, disaster_stop_price,
                       disaster_stop_hit, DISASTER_STOP_R)

bk = json.loads((ROOT / "research" / "bt2y_trades.json").read_text(encoding="utf-8"))
tr = [r for r in bk["trades"] if r["traded"]]
by_day = defaultdict(list)
for r in tr:
    by_day[(r["sym"], r["day"])].append(r)

out, miss = [], 0
for (sym, day), rows in sorted(by_day.items()):
    try:
        rth = pf.rth(pf.fetch_day(sym, day))
    except Exception:
        miss += len(rows); continue
    if not rth:
        miss += len(rows); continue
    for r in rows:
        i0 = r["entry_i"]
        if i0 is None or i0 >= len(rth):
            miss += 1; continue
        entry, stop = r["entry"], r["stop"]
        long = r["dir"] == "call"
        risk = abs(entry - stop)
        if risk <= 0:
            miss += 1; continue
        dz = disaster_stop_price(entry, risk, long)
        mfe = 0.0
        exit_px, exit_i = rth[-1].close, len(rth) - 1
        for i in range(i0 + 1, len(rth)):
            c = rth[i]
            fav = (c.high - entry) if long else (entry - c.low)
            mfe = max(mfe, fav / risk)
            if disaster_stop_hit(c.high, c.low, dz, long):
                exit_px, exit_i = dz, i; break
            if stop_hit_on_close(c.close, stop, long):
                exit_px, exit_i = stop_fill_price(c.close, entry, risk, long), i; break
        nt_r = ((exit_px - entry) if long else (entry - exit_px)) / risk
        out.append({"sym": sym, "day": day, "booked": r["r"], "mfe": mfe,
                    "notgt": nt_r, "scaled": bool(r.get("scaled")),
                    "grade": r["grade"], "sgrade": r.get("sgrade")})

n = len(out)
print("rows replayed %d  (skipped %d)" % (n, miss))
bk_r = [o["booked"] for o in out]
mf = [o["mfe"] for o in out]
nt = [o["notgt"] for o in out]
print("booked   mean %+.4fR  median %+.4f  >2R %d (%.2f%%)" %
      (statistics.fmean(bk_r), statistics.median(bk_r),
       sum(1 for x in bk_r if x > 2 + 1e-6), 100*sum(1 for x in bk_r if x > 2+1e-6)/n))
print("MFE      mean %+.4fR  median %+.4f  >=2R %d (%.2f%%)  >=3R %d (%.2f%%)  >=4R %d (%.2f%%)" %
      (statistics.fmean(mf), statistics.median(mf),
       sum(1 for x in mf if x >= 2), 100*sum(1 for x in mf if x >= 2)/n,
       sum(1 for x in mf if x >= 3), 100*sum(1 for x in mf if x >= 3)/n,
       sum(1 for x in mf if x >= 4), 100*sum(1 for x in mf if x >= 4)/n))
print("no-tgt   mean %+.4fR  median %+.4f  >2R %d (%.2f%%)" %
      (statistics.fmean(nt), statistics.median(nt),
       sum(1 for x in nt if x > 2 + 1e-6), 100*sum(1 for x in nt if x > 2+1e-6)/n))

# capture: how much of the available excursion the shipped exit keeps
capt = [o["booked"]/o["mfe"] for o in out if o["mfe"] >= 0.5]
print("capture (booked/MFE) over rows with MFE>=0.5R: n=%d mean %.3f median %.3f"
      % (len(capt), statistics.fmean(capt), statistics.median(capt)))

# the rows that reached 2R on the tape but booked less
cut = [o for o in out if o["mfe"] >= 2.0 and o["booked"] < 2.0]
print("reached >=2R on tape but booked <2R: %d (%.2f%% of book); their mean booked %+.4fR, mean MFE %+.4fR"
      % (len(cut), 100*len(cut)/n, statistics.fmean([o["booked"] for o in cut]),
         statistics.fmean([o["mfe"] for o in cut])))
json.dump(out, open(ROOT / "research" / "_g71_rrcap_mfe.json", "w"), separators=(",", ":"))
print("wrote research/_g71_rrcap_mfe.json")
