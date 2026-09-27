"""v2-t10: t01 best variant (ORB OR5 + displacement>=1 ATR + wick retest, no close-through + strong trigger,
fixed 2R) on YM/RTY (sized MYM/M2K) vs ES/NQ (MES/MNQ). Signal/fill code imported verbatim from v2-t01 orb1m.py;
only TICK is swapped per instrument. Paper research only. No network, no keys."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
RUNS = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
sys.path.insert(0, str(RUNS / "v2-t01-orb-1m")); sys.path.insert(0, str(RUNS / "v2-s07-data"))
import orb1m
from omen_data import load_fut
ET = "America/New_York"
SPEC = {"MES": dict(tick=0.25, usd=5.0), "MNQ": dict(tick=0.25, usd=2.0),
        "MYM": dict(tick=1.0, usd=0.5), "M2K": dict(tick=0.1, usd=5.0)}
COMM = 1.24
DIRS = [RUNS / "v2-s11-other-indices" / "fut", RUNS / "v2-t10-other-indices"]

def load_root(root):
    parts = []
    for dd in DIRS:
        for f in sorted(dd.glob(f"{root}[FGHJKMNQUVXZ][0-9].csv")):
            d = pd.read_csv(f)
            if d.empty: continue
            d["contract"] = f.stem; parts.append(d)
    d = pd.concat(parts, ignore_index=True).drop_duplicates(["ts_ns", "contract"])
    d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert(ET)
    d["date"] = d["ts"].dt.date
    t = d["ts"].dt.strftime("%H:%M")
    rth = d[(t >= "09:30") & (t < "16:00")]
    vol = rth.groupby(["date", "contract"])["volume"].sum().reset_index()
    pick = vol.loc[vol.groupby("date")["volume"].idxmax(), ["date", "contract"]]
    cnt = rth.merge(pick, on=["date", "contract"]).groupby("date").size()
    pick = pick[pick["date"].map(cnt) > 212]          # same NYSE-closed rule as s07 loader
    out = d.merge(pick, on=["date", "contract"])
    t = out["ts"].dt.strftime("%H:%M")
    return out[(t >= "09:30") & (t < "11:01")].sort_values("ts").reset_index(drop=True)

def days_of(sym):
    df = load_fut(sym, "09:30", "11:01") if sym in ("MES", "MNQ") else load_root({"MYM": "YM", "M2K": "RTY"}[sym])
    return [(d, orb1m.day_arrays(g)) for d, g in df.groupby("date")]

RNG = np.random.default_rng(10)
def cell(sym, days, cutname, lo=None):
    sp = SPEC[sym]; orb1m.TICK = sp["tick"]; cut = orb1m.CUTS[cutname]
    if lo: days = [x for x in days if x[0] >= lo]
    T = []
    for d, A in days:
        s = orb1m.signal(A, 5, cut, 1.0, "strong")
        if not s: continue
        i, side, stop = s
        e = A["open"][i] + sp["tick"] * side; dist = (e - stop) * side
        if dist < 2 * sp["tick"]: continue
        r, u = orb1m.run_trade(A, i, side, dist, cut, sp["usd"], COMM)
        T.append(dict(date=str(d), i=int(i), side=int(side), dist=float(dist), R=float(r), usd=float(u)))
    n = len(T); R = np.array([t["R"] for t in T]); dates = [str(d) for d, _ in days]
    mid = dates[len(dates) // 2]; h1 = np.array([t["date"] < mid for t in T], bool)
    sh = []
    for _ in range(200):
        rr = []
        for t in T:
            while True:
                k = RNG.integers(len(days))
                if dates[k] != t["date"] and not np.isnan(days[k][1]["open"][t["i"]]): break
            rr.append(orb1m.run_trade(days[k][1], t["i"], t["side"], t["dist"], cut, sp["usd"], COMM)[0])
        sh.append(np.mean(rr) if rr else 0)
    sh = np.array(sh)
    mo = {}
    for t in T: mo[t["date"][:7]] = mo.get(t["date"][:7], 0) + t["R"]
    res = dict(sym=sym, cut=cutname, sessions=len(days), first=dates[0], last=dates[-1], n=n,
               win=float((R > 0).mean()) if n else 0, avgR=float(R.mean()) if n else 0,
               t=float(R.mean() / (R.std(ddof=1) / np.sqrt(n))) if n > 2 else None,
               h1=(round(float(R[h1].mean()), 3) if h1.any() else None, int(h1.sum())),
               h2=(round(float(R[~h1].mean()), 3) if (~h1).any() else None, int((~h1).sum())),
               p=max(float((sh >= (R.mean() if n else 0)).mean()), 0.005), shufR=float(sh.mean()),
               day200=float(R.sum() * 200 / len(days)), day1=float(sum(t["usd"] for t in T) / len(days)),
               green=f"{sum(v > 0 for v in mo.values())}/{len(mo)}",
               stop_med=float(np.median([t["dist"] for t in T])) if n else None,
               cost_R=float(np.median([(COMM + 2 * sp["tick"] * sp["usd"]) / (t["dist"] * sp["usd"]) for t in T])) if n else None,
               long=float(np.mean([t["side"] > 0 for t in T])) if n else None)
    json.dump(T, open(f"trades_{sym}_{cutname.replace(':','')}{'_common' if lo else ''}.json", "w"))
    return res

if __name__ == "__main__":
    D = {s: days_of(s) for s in SPEC}
    lo = max(D["MYM"][0][0], D["M2K"][0][0])
    out = []
    for s in SPEC:
        for c in ("10:30", "10:45", "11:00"):
            r = cell(s, D[s], c); out.append(r); print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}), flush=True)
    for s in ("MES", "MNQ"):   # ES/NQ restricted to the YM/RTY date range, like-for-like
        for c in ("10:30",):
            r = cell(s, D[s], c, lo); r["sym"] += "_common"; out.append(r); print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}), flush=True)
    json.dump(out, open("results.json", "w"), indent=1, default=str)
    print("DONE")
