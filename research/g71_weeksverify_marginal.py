"""Marginal edge by within-day sequence slot, and the corr_drag decomposition.

`weeks` claims CAP-N is "a count sweep with quality held fixed" and that the
trades a cut would drop "do not have negative edge". Both are testable directly:
walk the sequential book and tag each taken trade with its slot index.
"""
import json, math, statistics, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/"research"))
from g71_firsts_policy import ekey, xkey
from g71_weeks import iso_week

b = json.loads((ROOT/"research/bt2y_trades.json").read_text())
tr = b["trades"]
counted = [r for r in tr if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
by_day = defaultdict(list)
for r in counted: by_day[r["day"]].append(r)
for d in by_day: by_day[d].sort(key=ekey)

slot = defaultdict(list)          # within-day sequential slot -> R list
for d, rows in by_day.items():
    free = None; i = 0
    for c in rows:
        if free is not None and ekey(c) < free: continue
        slot[i].append(c["r"]); free = xkey(c); i += 1

print("%5s %7s %9s %9s %9s %9s" % ("slot","n","meanR","sdR","mu/sig","cum mu/sig"))
cum = []
for k in sorted(slot):
    if k > 9: break
    v = slot[k]; cum += v
    mu = statistics.fmean(v); sg = statistics.pstdev(v)
    cm = statistics.fmean(cum); cs = statistics.pstdev(cum)
    print("%5d %7d %9.4f %9.4f %9.4f %9.4f" % (k+1, len(v), mu, sg, mu/sg, cm/cs))
tail = [x for k in slot if k >= 3 for x in slot[k]]
print("\nslots 4+ (what a cut from CAP-24 to CAP-3 drops): n=%d meanR=%.4f sd=%.4f mu/sig=%.4f"
      % (len(tail), statistics.fmean(tail), statistics.pstdev(tail),
         statistics.fmean(tail)/statistics.pstdev(tail)))
head = [x for k in slot if k < 3 for x in slot[k]]
print("slots 1-3 kept:                                    n=%d meanR=%.4f sd=%.4f mu/sig=%.4f"
      % (len(head), statistics.fmean(head), statistics.pstdev(head),
         statistics.fmean(head)/statistics.pstdev(head)))

# ---- corr_drag: is it intra-WEEK correlation, or intra-DAY concurrency?
def drag(rows, label):
    wk = defaultdict(float); wn = defaultdict(int)
    for r in rows:
        wk[iso_week(r["day"])] += r["r"]; wn[iso_week(r["day"])] += 1
    weeks = sorted({iso_week(d) for d in by_day})
    ser = [wk.get(w,0.0) for w in weeks]
    rs = [r["r"] for r in rows]
    sg = statistics.pstdev(rs); n = len(rows)/len(weeks)
    sdw = statistics.pstdev(ser)
    # DAY-level iid: treat each DAY total as the atom -> isolates intra-week corr
    dy = defaultdict(float)
    for r in rows: dy[r["day"]] += r["r"]
    days = sorted(by_day); dser = [dy.get(d,0.0) for d in days]
    sdd = statistics.pstdev(dser); dpw = len(days)/len(weeks)
    print("%-28s sd_wk=%7.3f  iid_from_TRADES=%7.3f (x%.3f)  iid_from_DAYS=%7.3f (x%.3f)"
          % (label, sdw, sg*math.sqrt(n), sdw/(sg*math.sqrt(n)),
             sdd*math.sqrt(dpw), sdw/(sdd*math.sqrt(dpw))))

print()
shipped = [r for r in tr if r["traded"]]
seq = [c for d,rows in by_day.items() for c in (lambda rs:[x for x in rs])(
        [c for c in rows])]
drag(shipped, "P0 shipped (concurrent)")
drag(counted, "P0u all counted (concurrent)")
seqrows = []
for d, rows in by_day.items():
    free=None
    for c in rows:
        if free is not None and ekey(c) < free: continue
        seqrows.append(c); free = xkey(c)
drag(seqrows, "P0seq (one at a time)")
