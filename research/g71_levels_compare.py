"""G7.1 track `levels` -- compare the arm books produced by g71_levels_book.py.

Every figure is off the same rig (`backtest_2y.py`), so only the level roster
differs between arms. Reports the money gate (win% / mean R), durability
(months green), total R, and the error bar the method rule requires
(1.96 x SE of the mean R difference, paired where the arms share signals).

Usage:
    python research/g71_levels_compare.py research/g71_arm_base.json \
        research/g71_arm_six_target.json ...
"""
from __future__ import annotations
import json, math, statistics as st, sys
from collections import defaultdict


def load(p):
    d = json.load(open(p, encoding="utf-8"))
    return d["meta"], [t for t in d["trades"] if t["traded"]]


def stats(tr):
    rs = [t["r"] for t in tr]
    wins = sum(1 for t in tr if t["out"] == "win")
    losses = sum(1 for t in tr if t["out"] == "loss")
    dec = wins + losses
    m = defaultdict(float)
    for t in tr:
        m[t["ym"]] += t["r"]
    sd = st.pstdev(rs) if len(rs) > 1 else 0.0
    return {"n": len(tr), "win": (wins / dec * 100) if dec else 0.0,
            "mean_r": st.fmean(rs) if rs else 0.0, "total_r": sum(rs),
            "green": sum(1 for v in m.values() if v > 0), "months": len(m),
            "se": sd / math.sqrt(len(rs)) if rs else 0.0,
            "scaled": sum(1 for t in tr if t.get("scaled"))}


def key(t):
    return (t["sym"], t["day"], t["et"], t["setup"], t["dir"], t["entry"], t["stop"])


def main():
    paths = sys.argv[1:]
    books = {}
    for p in paths:
        name = p.split("g71_arm_")[-1].replace(".json", "")
        meta, tr = load(p)
        books[name] = tr
        s = stats(tr)
        print("%-12s n=%-5d win=%.1f%% meanR=%+.4f totalR=%+.1f green=%d/%d scaled=%d"
              % (name, s["n"], s["win"], s["mean_r"], s["total_r"], s["green"],
                 s["months"], s["scaled"]))

    if "base" not in books:
        return
    base = books["base"]
    bmap = {key(t): t for t in base}
    print()
    for name, tr in books.items():
        if name == "base":
            continue
        amap = {key(t): t for t in tr}
        shared = set(bmap) & set(amap)
        diffs = [amap[k]["r"] - bmap[k]["r"] for k in shared]
        moved = sum(1 for d in diffs if abs(d) > 1e-9)
        sd = st.pstdev(diffs) if len(diffs) > 1 else 0.0
        se = sd / math.sqrt(len(diffs)) if diffs else 0.0
        print("%-12s vs base: shared=%d moved=%d  paired dR=%+.4f  +/-%.4f (95%%)  "
              "base-only=%d arm-only=%d"
              % (name, len(shared), moved, st.fmean(diffs) if diffs else 0.0,
                 1.96 * se, len(bmap) - len(shared), len(amap) - len(shared)))


if __name__ == "__main__":
    main()
