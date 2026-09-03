"""ADVERSARIAL VERIFY part 2: is money really a non-separator?

Independent paired day-block bootstrap (different seed + a paired sign test)
on total R AND on mean R/trade, the metric the money gate actually names.
Read-only over research/bt2y_trades.json.
"""
import json, random, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "research" / "bt2y_trades.json").read_text(encoding="utf-8"))
rows = d["trades"]
cand = [r for r in rows if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
sess = sorted({r["day"] for r in cand})
ek = lambda r: (r["entry_i"], r["et"], r["sym"])
xk = lambda r: (r["entry_i"] + r["bars"], r["et"], r["sym"])

def walk(day_rows, hn, fl):
    pending, streak, real = [], 0, 0.0
    taken = []
    for row in sorted(day_rows, key=ek):
        at = ek(row)
        while pending and pending[0][0] <= at:
            _x, lost, rr = pending.pop(0)
            streak = streak + 1 if lost else 0
            real += rr
        if (hn and streak >= hn) or (fl is not None and real <= fl):
            continue
        taken.append(row)
        pending.append((xk(row), row["out"] == "loss", row["r"]))
        pending.sort(key=lambda p: p[0])
    return taken

by_day = defaultdict(list)
for r in cand: by_day[r["day"]].append(r)

def arm(hn, fl):
    dr, dn = {}, {}
    tot = n = 0
    for s in sess:
        t = walk(by_day[s], hn, fl)
        dr[s] = sum(x["r"] for x in t); dn[s] = len(t)
        tot += dr[s]; n += len(t)
    return dr, dn, tot, n

A = {"halt=2 (shipped)": arm(2, None), "halt=3+-2R": arm(3, -2.0),
     "-2R floor": arm(None, -2.0), "no gov": arm(None, None)}
for k, (dr, dn, tot, n) in A.items():
    print("%-18s n=%4d totalR=%8.1f meanR/trade=%.4f" % (k, n, tot, tot / n))

def boot(a, b, seed, B=20000):
    rnd = random.Random(seed)
    diff = [A[a][0][s] - A[b][0][s] for s in sess]
    k = len(sess); out = []
    for _ in range(B):
        out.append(sum(diff[rnd.randrange(k)] for _ in range(k)))
    out.sort()
    return sum(diff), out[int(.025*B)], out[int(.975*B)-1]

print("\npaired day bootstrap, total R (seed 1234, B=20000)")
for a, b in [("-2R floor", "halt=2 (shipped)"), ("halt=3+-2R", "halt=2 (shipped)")]:
    dlt, lo, hi = boot(a, b, 1234)
    print("  %-20s vs %-18s  %+8.1f  [%+.1f, %+.1f]  %s"
          % (a, b, dlt, lo, hi, "SEPARATES" if lo*hi > 0 else "tie"))

# mean R / trade -- the metric the money gate names -- ratio-of-sums bootstrap
def boot_mean(a, b, seed, B=20000):
    rnd = random.Random(seed); k = len(sess); out = []
    ra = [A[a][0][s] for s in sess]; na = [A[a][1][s] for s in sess]
    rb = [A[b][0][s] for s in sess]; nb = [A[b][1][s] for s in sess]
    for _ in range(B):
        idx = [rnd.randrange(k) for _ in range(k)]
        sa = sum(ra[i] for i in idx); ca = sum(na[i] for i in idx)
        sb = sum(rb[i] for i in idx); cb = sum(nb[i] for i in idx)
        out.append(sa/ca - sb/cb)
    out.sort()
    pt = A[a][2]/A[a][3] - A[b][2]/A[b][3]
    return pt, out[int(.025*B)], out[int(.975*B)-1]

print("\npaired day bootstrap, MEAN R PER TRADE (the money-gate metric)")
for a, b in [("-2R floor", "halt=2 (shipped)"), ("halt=3+-2R", "halt=2 (shipped)"),
             ("no gov", "halt=2 (shipped)")]:
    pt, lo, hi = boot_mean(a, b, 1234)
    print("  %-20s vs %-18s  %+.4f  [%+.4f, %+.4f]  %s"
          % (a, b, pt, lo, hi, "SEPARATES" if lo*hi > 0 else "tie"))
