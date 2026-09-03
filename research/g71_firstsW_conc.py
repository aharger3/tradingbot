"""Is the 'shipped book holds 2.37 at once, 18 at peak' number real, or is it
duplicate rows? Re-count concurrency three ways."""
import json, statistics as st
from collections import defaultdict, Counter
from pathlib import Path
T = json.loads((Path(__file__).resolve().parent.parent / "research/bt2y_trades.json").read_text())["trades"]
sh = defaultdict(list)
for r in T:
    if r["traded"]: sh[r["day"]].append(r)
rows = [r for rs in sh.values() for r in rs]
c = Counter((r["day"], r["sym"], r["entry_i"]) for r in rows)
print("shipped rows=%d  distinct (day,sym,minute)=%d  rows on a duplicated key=%d (%.1f%%)"
      % (len(rows), len(c), sum(v for v in c.values() if v > 1),
         100*sum(v for v in c.values() if v > 1)/len(rows)))
exact = Counter((r["day"], r["sym"], r["entry_i"], r["bars"], round(r["r"], 6)) for r in rows)
print("byte-identical duplicate rows (same day/sym/minute/bars/R): %d"
      % sum(v-1 for v in exact.values() if v > 1))

def stats(pick, lab):
    mxs = []
    for d, rs in sh.items():
        rs2 = pick(rs)
        ev = sorted([(r["entry_i"], 1) for r in rs2] + [(r["entry_i"]+r["bars"], -1) for r in rs2])
        cur = mx = 0
        for _t, v in ev:
            cur += v; mx = max(mx, cur)
        mxs.append(mx)
    print("%-34s mean(dailyMAX)=%.2f max=%d days>=2=%d/%d" % (lab, st.fmean(mxs), max(mxs), sum(1 for x in mxs if x >= 2), len(mxs)))

stats(lambda rs: rs, "as-shipped (report's number)")
def dedupe(rs):
    seen, out = set(), []
    for r in sorted(rs, key=lambda r: (r["entry_i"], r["sym"])):
        k = (r["sym"], r["entry_i"])
        if k in seen: continue
        seen.add(k); out.append(r)
    return out
stats(dedupe, "one row per symbol-minute")
def dedupe_sym(rs):
    # a human holds at most one position per symbol at a time
    out, busy = [], {}
    for r in sorted(rs, key=lambda r: (r["entry_i"], r["sym"])):
        if busy.get(r["sym"], -1) > r["entry_i"]: continue
        busy[r["sym"]] = r["entry_i"] + r["bars"]; out.append(r)
    return out
stats(dedupe_sym, "one open position per symbol")
