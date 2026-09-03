"""G7.1 losshalt ADVERSARIAL VERIFY — independent re-derivation of the
CONDITIONAL EDGE table (streak at entry) plus the checks the original omitted:
day-clustered SE, within-day sequence confound, and the pool sensitivity.

Read-only over research/bt2y_trades.json. Touches no engine file.
Usage: python research/g71_losshaltverify_repro.py
"""
import json, statistics, random
from collections import defaultdict, Counter

BOOK = "research/bt2y_trades.json"
d = json.load(open(BOOK, encoding="utf-8"))
rows = d["trades"]
meta = d["meta"]
print("meta:", {k: meta[k] for k in ("first","last","sessions","signals","halted","traded")})

def pool(name):
    if name == "orig":   # what the claim used
        return [r for r in rows if (r["status"]=="fired" and r["traded"]) or r["status"]=="halted"]
    if name == "traded": # the shipped book only
        return [r for r in rows if r["status"]=="fired" and r["traded"]]
    if name == "allfired":  # + alert-only rows
        return [r for r in rows if r["status"] in ("fired","halted")]
    raise KeyError(name)

ekey = lambda r: (r["entry_i"], r["et"], r["sym"])
xkey = lambda r: (r["entry_i"]+r["bars"], r["et"], r["sym"])

def walk(cand):
    """Yield (row, streak_at_entry, realised_day_r_at_entry, seq_within_day)."""
    by_day = defaultdict(list)
    for r in cand: by_day[r["day"]].append(r)
    for day in sorted(by_day):
        order = sorted(by_day[day], key=ekey)
        pending, streak, realised = [], 0, 0.0
        for i, row in enumerate(order):
            at = ekey(row)
            while pending and pending[0][0] <= at:
                _x, lost, rr = pending.pop(0)
                streak = streak+1 if lost else 0
                realised += rr
            yield row, streak, realised, i
            pending.append((xkey(row), row["out"]=="loss", row["r"]))
            pending.sort(key=lambda p: p[0])

def tab(recs, keyfn, order=None):
    b = defaultdict(list)
    for row, s, rz, i in recs:
        b[keyfn(row, s, rz, i)].append(row)
    keys = order or sorted(b)
    print("%-16s %7s %10s %10s %10s %8s" % ("bucket","n","mean R","naiveSE","daySE","win%"))
    out = {}
    for k in keys:
        v = b.get(k, [])
        if not v: continue
        rs = [x["r"] for x in v]
        m = statistics.fmean(rs)
        nse = statistics.pstdev(rs)/len(rs)**0.5
        # day-clustered SE: cluster robust, days as clusters
        byd = defaultdict(list)
        for x in v: byd[x["day"]].append(x["r"])
        nD = len(byd); N = len(rs)
        # sum over clusters of (sum residuals)^2 / N^2  (cluster-robust mean SE)
        num = sum((sum(r-m for r in g))**2 for g in byd.values())
        dse = (num*(nD/(nD-1)))**0.5/N if nD > 1 else float("nan")
        w = sum(1 for x in rs if x>0)/N*100
        out[k] = dict(n=N, mean=round(m,4), nse=round(nse,4), dse=round(dse,4),
                      days=nD, win=round(w,1))
        print("%-16s %7d %10.4f %10.4f %10.4f %8.1f" % (k, N, m, nse, dse, w))
    return out, b

for pname in ("orig","traded","allfired"):
    cand = pool(pname)
    recs = list(walk(cand))
    print("\n=== POOL %s  n=%d ===" % (pname, len(cand)))
    print("-- streak at entry --")
    tab(recs, lambda r,s,rz,i: min(s,4), order=[0,1,2,3,4])
    if pname == "orig":
        print("-- realised day R at entry --")
        tab(recs, lambda r,s,rz,i: ("<=-3R" if rz<=-3 else "-3..-2R" if rz<=-2 else
              "-2..-1R" if rz<=-1 else "-1..0R" if rz<=0 else "green"),
            order=["<=-3R","-3..-2R","-2..-1R","-1..0R","green"])
        print("-- within-day sequence (confound candidate) --")
        tab(recs, lambda r,s,rz,i: min(i,6), order=list(range(7)))
        print("-- streak WITHIN sequence bucket (does streak survive seq control?) --")
        print("%-24s %6s %9s %9s" % ("seq bucket / streak","n","mean R","daySE"))
        b2 = defaultdict(list)
        for row,s,rz,i in recs:
            b2[(min(i//2,3), min(s,2))].append(row)
        for sb in range(4):
            for sk in range(3):
                v = b2.get((sb,sk),[])
                if len(v) < 25: continue
                rs=[x["r"] for x in v]; m=statistics.fmean(rs)
                byd=defaultdict(list)
                for x in v: byd[x["day"]].append(x["r"])
                nD=len(byd); N=len(rs)
                num=sum((sum(r-m for r in g))**2 for g in byd.values())
                dse=(num*(nD/(nD-1)))**0.5/N if nD>1 else float("nan")
                print("seq %d-%d  streak %d%s  %6d %9.4f %9.4f" %
                      (sb*2, sb*2+1, sk, "+" if sk==2 else " ", N, m, dse))
