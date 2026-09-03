"""Splits the nearest-candidate swap by whether the picked candidate is a row
the book ALREADY traded, and by the engine's own routing status."""
import json, os, statistics, random, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import g71_timing as G
from signal_runner import min_risk_floor
from backtest_week import RISK_DOLLARS

book = json.load(open(G.BOOK, encoding="utf-8"))
rows = [r for r in book["trades"] if r["status"] == "fired" and r["traded"]]
G.load_or_build_index(rows)
support = []
for n, row in enumerate(rows):
    src = G.match(n)
    if src is None: continue
    ctx = G.day_ctx(row["sym"], row["day"])
    if ctx is None: continue
    L = len(ctx[0]); i0 = src.entry_idx
    if all(5 <= i0 + k < L - 1 for k in (-2,-1,0,1,2)) and i0 < L: support.append(n)
kept = {}
for n in support:
    keep = [c for c in G._CANDS.get(n, [])
            if c["status"] != "skipped_tight_stop"
            and abs(c["entry"] - c["stop"]) >= min_risk_floor(c["entry"])]
    if keep: kept[n] = keep
traded_fp = {(r["sym"], r["day"], r["entry_i"], r["dir"]) for r in rows}
recs = []
for n in sorted(kept):
    c = kept[n][0]; row = rows[n]
    ctx = G.day_ctx(row["sym"], row["day"])
    t = G.build(G._Src(c), ctx[0], ctx[1], ctx[2], ctx[3], ctx[4], 0, "T")
    if t is None: continue
    G.manage(t, ctx[0], G._StubRunner(ctx[0]))
    recs.append({"took": row["r"], "swap": t.pnl / RISK_DOLLARS,
                 "dup": (c["symbol"], c["day"], c["entry_idx"], c["direction"]) in traded_fp,
                 "status": c["status"], "off": c["off"], "sgrade": c["sgrade"],
                 "sym": row["sym"], "day": row["day"]})

def boot(xs, reps=20000, seed=917):
    rnd = random.Random(seed); ms = sorted(statistics.fmean(rnd.choices(xs, k=len(xs))) for _ in range(reps))
    return ms[int(.025*reps)], ms[int(.975*reps)]

def rep(name, rs):
    if len(rs) < 3: print("  %-34s n=%d (too small)" % (name, len(rs))); return
    d = [r["swap"] - r["took"] for r in rs]
    lo, hi = boot(d)
    print("  %-34s n=%3d took %+.4f swap %+.4f delta %+.4f [%+.4f,%+.4f] tot %+.1fR"
          % (name, len(rs), statistics.fmean(r["took"] for r in rs),
             statistics.fmean(r["swap"] for r in rs), statistics.fmean(d), lo, hi, sum(d)))

print("ALL / SPLITS (nearest earlier candidate)")
rep("all", recs)
rep("pick NOT already traded", [r for r in recs if not r["dup"]])
rep("pick already traded in book", [r for r in recs if r["dup"]])
rep("pick status=skipped_d (grade X)", [r for r in recs if r["status"] == "skipped_d"])
rep("pick status=fired", [r for r in recs if r["status"] == "fired"])
rep("off -1..-2", [r for r in recs if r["off"] >= -2])
rep("off -3..-6", [r for r in recs if r["off"] < -2])
rep("sgrade S", [r for r in recs if r["sgrade"] == "S"])
rep("sgrade S and off>=-2", [r for r in recs if r["sgrade"] == "S" and r["off"] >= -2])
# how many distinct symbol-days, for clustering
print("\ndistinct symbol-days among the 203: %d" % len({(r["sym"], r["day"]) for r in recs}))
# day-clustered bootstrap on the blanket arm
days = {}
for r in recs: days.setdefault((r["sym"], r["day"]), []).append(r["swap"] - r["took"])
keys = list(days); rnd = random.Random(5150); ms = []
for _ in range(20000):
    pick = [x for k in rnd.choices(keys, k=len(keys)) for x in days[k]]
    ms.append(statistics.fmean(pick))
ms.sort()
print("day-clustered boot on blanket delta: [%+.4f, %+.4f]" % (ms[500], ms[19499]))
