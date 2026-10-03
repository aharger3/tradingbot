"""s-matcher hindsight check: did his S trades still work AFTER the bars he could see?

He graded decks drawn out to 11:00 (t04), so an S that "worked" by 11:00 was seen working. Here the same signals are
re-entered at the 11:00 open (same side, same risk per share as the tape's stop), 2R limit / stop, flat 15:55. A real
S-skill should survive; hindsight should not.
Usage: python sm_posthoc.py DATADIR OUTJSON
"""
import os, sys, json, gzip
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sm_features as F
import sm_data as D

rng = np.random.default_rng(7)


def main(datadir, outjson, n_unmarked=6000):
    st = pd.read_csv(os.path.join(datadir, "stock.csv.gz"))
    B = json.load(gzip.open(os.path.join(D.ROOT, r"research\tape\baseline_2026-09-13.json.gz")))["trades"]
    lab = st[st["lab"].isin(["S", "A", "B", "C", "none"])]
    unm = st[st["lab"] == "unmarked"]
    unm = unm.iloc[rng.choice(len(unm), n_unmarked, replace=False)]
    rows = []
    cache = {}
    for _, r in pd.concat([lab, unm]).iterrows():
        t = B[int(r["idx"])]
        key = (r["sym"], r["day"])
        if key not in cache:
            if len(cache) > 200:
                cache.clear()
            cache[key] = D.load_stock_day(*key)
        d = cache[key]
        if d is None:
            continue
        side = int(r["side"])
        risk0 = abs(float(t["entry"]) - float(t["stop"]))
        if not np.isfinite(d["O"][660]) or risk0 <= 0:
            continue
        stop = d["O"][660] + 0.01 * side - side * risk0
        x = F.simulate(d, 659, side, stop, flat_m=955)
        if x is None:
            continue
        rows.append(dict(lab=r["lab"] if r["lab"] != "unmarked" else "unmarked", day=r["day"], cl=key[0] + key[1], R=x[0]))
    df = pd.DataFrame(rows)
    out = {}
    u = df[df["lab"] == "unmarked"]["R"].to_numpy()
    for g in ["S", "A", "C", "none"]:
        x = df[df["lab"] == g]["R"].to_numpy()
        ge = sum(rng.choice(u, len(x)).mean() >= x.mean() for _ in range(5000))
        out[g] = dict(n=int(len(x)), meanR=round(float(x.mean()), 3), win=round(100 * float((x > 0).mean()), 1),
                      p_vs_unmarked=round((ge + 1) / 5001, 4))
    out["unmarked_sample"] = dict(n=int(len(u)), meanR=round(float(u.mean()), 3))
    json.dump(out, open(outjson, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
