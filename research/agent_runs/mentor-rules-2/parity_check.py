"""Parity: (1) every NQ trade of cell C re-priced with the round-1 loop-based run_trade; (2) 400 random stock trades re-priced with a
plain-loop reference written here. Both must match the vectorized engine to 1e-9. Reads trades_*.csv produced by run.py."""
import csv, os, pickle, random, sys
import numpy as np
import mentor2 as m
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "mentor-rules"))
import mentor_cells as r1

def ref_loop(A, side, i, dist, spec, cut=90):
    tick = spec["tick"]; e = A["open"][i] + tick * side
    stop = e - side * dist; tgt = e + side * 2 * dist
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    x = None
    for j in range(i, cut):
        if np.isnan(O[j]): continue
        if side > 0:
            if L[j] <= stop + 1e-9: x = min(stop, O[j]) - tick; break
            if H[j] >= tgt + tick - 1e-9: x = tgt; break
        else:
            if H[j] >= stop - 1e-9: x = max(stop, O[j]) + tick; break
            if L[j] <= tgt - tick + 1e-9: x = tgt; break
    if x is None:
        px = O[cut] if not np.isnan(O[cut]) else C[:cut][~np.isnan(C[:cut])][-1]
        x = px - tick * side
    usd = (x - e) * side * spec["pv"] - spec["comm"]
    return usd / (dist * spec["pv"])

nq = {a["date"]: a for a in m.load_nq()}
rows = list(csv.DictReader(open(os.path.join(HERE, "trades_C.csv"))))
bad = 0
for r in rows:
    A = nq[r["date"]]
    rr, _ = r1.run_trade(A, int(r["i"]), int(r["side"]), float(r["dist"]))   # round-1 loop fills, frozen constants (NQ)
    bad += abs(rr - float(r["R"])) > 1e-9
print("C trades re-priced with round-1 run_trade:", len(rows), "mismatches", bad)

cache = pickle.load(open(os.environ["MR2_CACHE"], "rb"))
sess = {s: {A["date"]: A for A in cache[s][0]} for s in cache}
random.seed(5); bad = 0; tot = 0
for cell in "DE":
    rows = list(csv.DictReader(open(os.path.join(HERE, f"trades_{cell}.csv"))))
    for r in random.sample(rows, 200):
        A = sess[r["sym"]][r["date"]]
        rr = ref_loop(A, int(r["side"]), int(r["i"]), float(r["dist"]), m.SPEC_STK)
        bad += abs(rr - float(r["R"])) > 1e-9; tot += 1
print("stock trades re-priced with plain-loop reference:", tot, "mismatches", bad)
