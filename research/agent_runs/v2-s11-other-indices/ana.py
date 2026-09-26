# v2-s11: ES/NQ/YM/RTY comparison on common dates. ORB5 break+retest (t01 'retest' rule), stop = broken level -1 tick,
# 2R target, entry next-bar open +1 tick, stop fill min(stop,open)-1tick, target needs 1 tick through, same-bar = stop,
# flat at cutoff open -1 tick, micro commission $1.24 RT. One trade/day. Split-half + 200x day shuffle.
import sys, json, random
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")
import omen_data as od
HERE = Path(__file__).parent
ET = "America/New_York"
SPEC = {"ES": (0.25, 5.0), "NQ": (0.25, 2.0), "YM": (1.0, 0.5), "RTY": (0.10, 5.0)}  # tick, micro $/pt
def raw(root):
    if root in ("ES", "NQ"):
        return od.load_fut("MES" if root == "ES" else "MNQ", "09:30", "16:00")
    parts = []
    for f in sorted((HERE / "fut").glob(f"{root}[HMUZ]6.csv")) + sorted((HERE / "fut").glob(f"{root}Z5.csv")):
        d = pd.read_csv(f)
        if d.empty: continue
        d["contract"] = f.stem; parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert(ET); d["date"] = d["ts"].dt.date
    t = d["ts"].dt.strftime("%H:%M"); rth = d[(t >= "09:30") & (t < "16:00")]
    v = rth.groupby(["date", "contract"])["volume"].sum().reset_index()
    pick = v.loc[v.groupby("date")["volume"].idxmax(), ["date", "contract"]]
    return rth.merge(pick, on=["date", "contract"]).sort_values("ts").reset_index(drop=True)
def trade(g, tick, cutoff):
    g = g.reset_index(drop=True); hm = g["ts"].dt.strftime("%H:%M")
    orb = g[hm < "09:35"]
    if len(orb) < 5: return None
    H, L = orb.high.max(), orb.low.min()
    i0 = len(orb); n = len(g); o, h, l, c = g.open.values, g.high.values, g.low.values, g.close.values
    lim = (hm < cutoff).values
    br = None
    for i in range(i0, n):
        if not lim[i]: return None
        if c[i] > H and c[i-1] <= H: br = (i, 1, H); break
        if c[i] < L and c[i-1] >= L: br = (i, -1, L); break
    if not br: return None
    ib, s, lvl = br
    for j in range(ib + 1, min(ib + 11, n)):
        if not lim[j]: return None
        if s * (c[j] - lvl) < 0: return None  # close back through = invalid
        touch = (l[j] <= lvl + tick) if s > 0 else (h[j] >= lvl - tick)
        if touch and s * (c[j] - lvl) > 0 and s * (c[j] - o[j]) > 0:
            if j + 1 >= n or not lim[j + 1]: return None
            e = o[j + 1] + s * tick; stp = lvl - s * tick; risk = s * (e - stp)
            if risk <= 0: return None
            tgt = e + s * 2 * risk; out = None
            for k in range(j + 1, n):
                if hm.iloc[k] >= "11:00":
                    out = o[k] - s * tick; break
                hit_s = (l[k] <= stp) if s > 0 else (h[k] >= stp)
                hit_t = (h[k] >= tgt + tick) if s > 0 else (l[k] <= tgt - tick)
                if hit_s: out = (min(stp, o[k]) if s > 0 else max(stp, o[k])) - s * tick; break
                if hit_t: out = tgt; break
            if out is None: out = c[-1] - s * tick
            return dict(side=s, entry=e, risk=risk, pts=s * (out - e), mins=j + 1)
    return None
def run(root, dates, cutoff):
    tick, usd = SPEC[root]; d = raw(root); d = d[d.date.isin(dates)]
    rows = []
    for dt, g in d.groupby("date"):
        t = trade(g, tick, cutoff)
        if t:
            t["date"] = dt; t["R"] = (t["pts"] * usd - 1.24) / (t["risk"] * usd); t["usd"] = t["pts"] * usd - 1.24; rows.append(t)
    return pd.DataFrame(rows)
if __name__ == "__main__":
    roots = ["ES", "NQ", "YM", "RTY"]
    R = {r: raw(r) for r in roots}
    common = sorted(set.intersection(*[set(R[r].date.unique()) for r in roots]))
    common = [x for x in common if all((R[r].date == x).sum() >= 380 for r in roots)]
    print("common full sessions", len(common), common[0], common[-1])
    liq = {}
    for r in roots:
        d = R[r][R[r].date.isin(common)]; w = d[d.ts.dt.strftime("%H:%M") < "11:00"]
        orb = w[w.ts.dt.strftime("%H:%M") < "09:35"].groupby("date").agg(H=("high", "max"), L=("low", "min"), O=("open", "first"))
        rng = w.groupby("date").agg(hi=("high", "max"), lo=("low", "min"), op=("open", "first"))
        tick = SPEC[r][0]
        liq[r] = dict(vol_0930_1100_median=int(w.groupby("date").volume.sum().median()),
                      vol_per_min_median=int(w.volume.median()),
                      orb5_pts_median=float((orb.H - orb.L).median()), orb5_ticks_median=float(((orb.H - orb.L) / tick).median()),
                      orb5_pct_median=float(((orb.H - orb.L) / orb.O * 100).median()),
                      range_0930_1100_pct_median=float(((rng.hi - rng.lo) / rng.op * 100).median()),
                      zero_vol_or_missing_min_pct=float(100 - 100 * len(w) / (90 * len(common))))
    print(json.dumps(liq, indent=1))
    # daily return correlation 09:30-11:00
    ret = pd.DataFrame({r: R[r][R[r].date.isin(common)].groupby("date").apply(lambda g: g[g.ts.dt.strftime("%H:%M") < "11:00"].close.iloc[-1] / g.open.iloc[0] - 1) for r in roots})
    print("corr 0930-1100 returns\n", ret.corr().round(2))
    out = {"liq": liq, "n_common": len(common), "first": str(common[0]), "last": str(common[-1]), "bt": {}}
    half = common[len(common) // 2]
    rng = random.Random(7)
    for cut in ["10:30", "10:45", "11:00"]:
        for r in roots:
            t = run(r, common, cut)
            if t.empty: print(r, cut, "no trades"); continue
            h1 = t[t.date < half].R.mean(); h2 = t[t.date >= half].R.mean()
            # day shuffle: replay each trade's (minute, side, R-multiple-free) -> reshuffle R across... use sign-flip null on side
            # null = same entry minute & side on a random other session, stop distance same in points, 2R target, flat 11:00
            real = t.R.mean(); cnt = 0
            d = R[r][R[r].date.isin(common)]; sess = {k: g.reset_index(drop=True) for k, g in d.groupby("date")}
            keys = list(sess.keys()); tick, usd = SPEC[r]
            for _ in range(200):
                rs = []
                for _, tr in t.iterrows():
                    g = sess[rng.choice(keys)]; k0 = int(tr.mins)
                    if k0 >= len(g): continue
                    s = tr.side; e = g.open.values[k0] + s * tick; stp = e - s * tr.risk; tgt = e + s * 2 * tr.risk
                    hm = g.ts.dt.strftime("%H:%M").values; outp = None
                    for k in range(k0, len(g)):
                        if hm[k] >= "11:00": outp = g.open.values[k] - s * tick; break
                        lo, hi, op = g.low.values[k], g.high.values[k], g.open.values[k]
                        if (s > 0 and lo <= stp) or (s < 0 and hi >= stp): outp = (min(stp, op) if s > 0 else max(stp, op)) - s * tick; break
                        if (s > 0 and hi >= tgt + tick) or (s < 0 and lo <= tgt - tick): outp = tgt; break
                    if outp is None: outp = g.close.values[-1] - s * tick
                    rs.append((s * (outp - e) * usd - 1.24) / (tr.risk * usd))
                cnt += np.mean(rs) >= real
            p = (cnt + 1) / 201
            res = dict(n=len(t), win=float((t.R > 0).mean() * 100), avgR=float(real), usd_day=float(t.usd.sum() / len(common)),
                       H1=float(h1), H2=float(h2), p=float(p), med_risk_ticks=float((t.risk / SPEC[r][0]).median()))
            out["bt"][f"{r}|{cut}"] = res; print(r, cut, {k: round(v, 3) for k, v in res.items()}, flush=True)
    (HERE / "result.json").write_text(json.dumps(out, indent=1, default=str))
    print("DONE")
