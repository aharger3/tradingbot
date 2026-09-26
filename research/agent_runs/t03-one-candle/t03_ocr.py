"""t03 -- one-candle rule (order block) on ES/NQ 1-min, traded as MES/MNQ.

Honest rules (fixed for every grid cell):
  signal on 1m bar close -> fill NEXT bar open + 1 tick (adverse)
  hard stop = OCR wick -/+ 1 tick; stop fill = stop - 1 tick, or bar open - 1 tick if gapped
  target = limit at entry + k*R, fills only if price trades 1 tick THROUGH it
  stop and target in the same bar -> stop (worst case)
  time exit at 11:00 (close of 10:59 bar - 1 tick); signals 09:31-10:30 only
  commission $1.25 round trip per micro; size = floor($RISK / (R*V + tick*V + 1.25)), cap 50
  one trade per instrument per day (first signal), both directions
Grid (24): mode {his, ict} x zone {full, half} x max_age {10, 30} x target {1, 2, 3}R
"""
import glob, gzip, json, math, os, random, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research"))

TICK = 0.25
SPEC = {"ES": dict(V=5.0, name="MES"), "NQ": dict(V=2.0, name="MNQ")}
COMM = 1.25
CAP = 50
MIN_R_TICKS = 4
SPLIT = "2025-09-01"
RISKS = [200.0, 400.0]


def _norm(d, contract):
    ts = pd.to_datetime(d["ts_ns"].astype("int64"), unit="ns", utc=True).dt.tz_convert("America/New_York")
    hm = ts.dt.hour * 60 + ts.dt.minute
    d = d[(hm >= 8 * 60) & (hm < 11 * 60 + 5)].copy()
    d["ts"] = ts[d.index].dt.strftime("%Y-%m-%d %H:%M")
    d["contract"] = contract
    return d[["ts", "open", "high", "low", "close", "volume", "contract"]]


def load(root):
    """Union of this run's cache and the sibling runs' caches (t01 per-contract CSV, t02 monthly json.gz).
    Read-only on the siblings' files; dedup on (contract, minute)."""
    parts = []
    for f in glob.glob(str(HERE / "fut" / f"{root}??.csv.gz")):
        try: d = pd.read_csv(f)
        except Exception: continue
        if len(d): d["contract"] = Path(f).name.split(".")[0]; parts.append(d)
    for f in glob.glob(str(HERE.parent / "t01-orb5" / "fut" / f"{root}??_*.csv")):
        try: d = pd.read_csv(f)
        except Exception: continue
        if len(d): parts.append(_norm(d, Path(f).name.split("_")[0]))
    for f in glob.glob(str(HERE.parent / "t02-break-retest" / "bars" / f"{root}_*.json.gz")):
        try: j = json.load(gzip.open(f, "rt"))
        except Exception: continue
        if j.get("rows"):
            d = pd.DataFrame(j["rows"], columns=["ts_ns", "open", "high", "low", "close", "volume"])
            parts.append(_norm(d, j["ticker"]))
    df = pd.concat(parts).drop_duplicates(["contract", "ts"])
    df["date"] = df["ts"].str[:10]
    df["hm"] = df["ts"].str[11:16]
    rth = df[(df.hm >= "09:30") & (df.hm < "11:00")]
    vol = rth.groupby(["date", "contract"])["volume"].sum().reset_index()
    front = vol.sort_values("volume").groupby("date").tail(1).set_index("date")["contract"]
    days = {}
    groups = {k: g for k, g in df.groupby(["date", "contract"])}
    for date, c in front.items():
        d = groups[(date, c)].sort_values("ts").reset_index(drop=True)
        r = d[(d.hm >= "09:30") & (d.hm < "11:00")]
        if len(r) < 80 or d.hm.iloc[0] > "09:30":  # need a near-full window
            continue
        days[date] = d
    return days


def prep(d):
    o, h, l, c, v = (d[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    hm = d["hm"].to_numpy()
    ema = lambda x, n: pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()
    e9, e20 = ema(c, 9), ema(c, 20)
    rth = hm >= "09:30"
    tp = (h + l + c) / 3
    cv = np.cumsum(np.where(rth, tp * v, 0)); cvol = np.cumsum(np.where(rth, v, 0))
    vwap = np.where(cvol > 0, cv / np.maximum(cvol, 1e-9), c)
    return dict(o=o, h=h, l=l, c=c, hm=hm, e9=e9, e20=e20, vwap=vwap)


def mirror(p):
    """Short side = long logic on negated prices."""
    return dict(o=-p["o"], h=-p["l"], l=-p["h"], c=-p["c"], hm=p["hm"],
                e9=-p["e9"], e20=-p["e20"], vwap=-p["vwap"])


def first_signal(p, mode, zone, age):
    """Long-side OCR. Returns (signal bar index, block low) or None."""
    o, h, l, c, hm = p["o"], p["h"], p["l"], p["c"], p["hm"]
    n = len(c)
    start = int(np.argmax(hm >= "09:30"))
    cand = None     # most recent down-close candle (index)
    act = None      # (j, hi, lo, mid, k_activation)
    touched = False
    for i in range(start, n):
        if hm[i] > "10:30": break
        # existing active block: invalidate / retest / confirm
        if act is not None and i > act[4]:
            j, hi, lo, mid, _ = act
            if c[i] < lo:
                act = None; touched = False
            else:
                ztop = hi if zone == "full" else mid
                if l[i] <= ztop: touched = True
                if touched and c[i] > o[i] and c[i] > hi and (i - j) <= age and hm[i] >= "09:31":
                    return i, lo
                if (i - j) > age:
                    act = None; touched = False
        # activation of the current candidate
        if cand is not None and i > cand:
            j = cand; rng = h[j] - l[j]
            if rng > 0:
                if mode == "his":
                    ok = c[i] > h[j]
                else:  # ict: BOS over prior 10-bar high + displacement >= 1.5x block range, within 6 bars
                    swing = h[max(0, j - 10):j + 1].max()
                    ok = (i - j) <= 6 and c[i] > swing and c[i] >= h[j] + 1.5 * rng
                if ok:
                    act = (j, h[j], l[j], (h[j] + l[j]) / 2, i); touched = False; cand = None
            if cand is not None and c[i] < l[cand]:
                cand = None
        # new candidate: down-close candle (in uptrend for "his")
        if c[i] < o[i]:
            if mode == "his":
                if p["e9"][i] > p["e20"][i] and c[i] > p["vwap"][i]:
                    cand = i
            else:
                cand = i
    return None


def simulate(p, e, stop, kR, entry=None):
    """Long trade from bar e open. Returns (entry, exit, R_pts) or None."""
    o, h, l, c, hm = p["o"], p["h"], p["l"], p["c"], p["hm"]
    if e >= len(o) or hm[e] >= "11:00": return None
    ent = o[e] + TICK if entry is None else entry
    R = ent - stop
    if R < MIN_R_TICKS * TICK: return None
    tgt = ent + kR * R
    for t in range(e, len(o)):
        if hm[t] >= "11:00":
            return ent, c[t - 1] - TICK, R, "time"
        if t > e and o[t] <= stop: return ent, o[t] - TICK, R, "gap"
        if l[t] <= stop: return ent, stop - TICK, R, "stop"
        if h[t] >= tgt + TICK: return ent, tgt, R, "target"
    return ent, c[-1] - TICK, R, "time"


def trade_row(date, root, side, ent, ex, R, kind, V):
    pts = ex - ent
    # gross = no slippage, no commission: raw entry = ent - tick; raw exit = ex (+tick unless target)
    raw_pts = pts + TICK + (0 if kind == "target" else TICK)
    gross_R = raw_pts / (R - TICK)
    net_R = (pts * V - COMM) / (R * V)
    row = dict(day=date, root=root, side=side, kind=kind, R_pts=R, pts=pts, net_R=net_R, gross_R=gross_R)
    for rk in RISKS:
        n = min(CAP, int(rk // (R * V + TICK * V + COMM)))
        row[f"n{int(rk)}"] = n
        row[f"usd{int(rk)}"] = n * (pts * V - COMM)
    return row


def run_cell(data, mode, zone, age, kR, keep_meta=False):
    rows = []
    for root, days in data.items():
        V = SPEC[root]["V"]
        for date, (pL, pS) in days.items():
            best = None
            for side, p in (("L", pL), ("S", pS)):
                sg = first_signal(p, mode, zone, age)
                if sg is None: continue
                if best is None or sg[0] < best[1]: best = (side, sg[0], p, sg[1])
            if best is None: continue
            side, i, p, blk = best
            stop = blk - TICK  # OCR wick - 1 tick
            r = simulate(p, i + 1, stop, kR)
            if r is None: continue
            row = trade_row(date, root, side, *r, V)
            if keep_meta: row.update(sig=int(i))
            rows.append(row)
    return rows


def stats(rows, sessions, risk=200):
    if not rows: return dict(n=0)
    df = pd.DataFrame(rows)
    k = f"usd{int(risk)}"
    m = df.groupby(df.day.str[:7])[k].sum()
    allm = sorted({d[:7] for d in sessions})
    green = sum(1 for mm in allm if m.get(mm, 0) > 0)
    R = df.net_R.to_numpy()
    return dict(n=len(df), win=round(100 * (df.pts > 0).mean(), 1), meanR=round(R.mean(), 3),
                grossR=round(df.gross_R.mean(), 3), t=round(R.mean() / (R.std(ddof=1) / math.sqrt(len(R))), 2) if len(R) > 2 else None,
                usd_day=round(df[k].sum() / len(sessions), 1), green=f"{green}/{len(allm)}",
                medRpts=round(float(np.median(df.R_pts)), 2), costR=round(float((df.gross_R - df.net_R).mean()), 3))


def daily_series(rows, risk):
    k = f"usd{int(risk)}"
    s = {}
    for r in rows: s[r["day"]] = s.get(r["day"], 0.0) + r[k]
    return sorted(s.items())


def _sim_R(p, i, side_R, kR, V):
    if i + 1 >= len(p["o"]): return None
    ent = p["o"][i + 1] + TICK
    res = simulate(p, i + 1, ent - side_R, kR, entry=ent)
    if res is None: return None
    e, x, R, _ = res
    return ((x - e) * V - COMM) / (R * V)


def nulls(data, rows, kR, reps=300, seed=7):
    """Two nulls, each keeps side, R distance and target of every real trade.
    day_shuffle: same clock-time entry on a random OTHER session (same root) -- does the day matter?
    late_random: same day, random entry bar between the real signal and 10:30 -- does the OCR minute matter?
    p = share of null means >= the real mean."""
    rng = random.Random(seed)
    real = float(np.mean([r["net_R"] for r in rows]))
    keys = {root: sorted(d) for root, d in data.items()}
    out = {}
    for kind in ("day_shuffle", "late_random"):
        means = []
        for _ in range(reps):
            acc = []
            for r in rows:
                V = SPEC[r["root"]]["V"]
                if kind == "day_shuffle":
                    d2 = rng.choice(keys[r["root"]])
                    while d2 == r["day"]: d2 = rng.choice(keys[r["root"]])
                    p0 = data[r["root"]][r["day"]][0]
                    hm = p0["hm"][r["sig"]]
                    pp = data[r["root"]][d2][0 if r["side"] == "L" else 1]
                    ii = np.where(pp["hm"] == hm)[0]
                    if not len(ii): continue
                    v = _sim_R(pp, int(ii[0]), r["R_pts"], kR, V)
                else:
                    pp = data[r["root"]][r["day"]][0 if r["side"] == "L" else 1]
                    idx = [i for i in range(r["sig"], len(pp["hm"])) if pp["hm"][i] <= "10:30"]
                    v = _sim_R(pp, rng.choice(idx), r["R_pts"], kR, V)
                if v is not None: acc.append(v)
            means.append(np.mean(acc))
        m = np.array(means)
        out[kind] = dict(real=round(real, 3), null_mean=round(float(m.mean()), 3),
                         null_p95=round(float(np.percentile(m, 95)), 3), p=round(float((m >= real).mean()), 3))
    return out


def main():
    if "--coverage" in sys.argv:
        for root in SPEC:
            days = load(root); ks = sorted(days)
            by = pd.Series(1, index=[k[:7] for k in ks]).groupby(level=0).sum()
            print(root, len(ks), ks[:1], ks[-1:], dict(by))
        return
    roots = [a for a in sys.argv[1:] if a in SPEC] or list(SPEC)
    data = {}
    sess = {}
    for root in roots:
        days = load(root)
        data[root] = {d: (lambda p: (p, mirror(p)))(prep(x)) for d, x in days.items()}
        sess[root] = sorted(days)
    sessions = sorted(set().union(*sess.values()))
    h1s = [d for d in sessions if d < SPLIT]; h2s = [d for d in sessions if d >= SPLIT]
    print("sessions", len(sessions), sessions[0], sessions[-1], "H1", len(h1s), "H2", len(h2s),
          {r: len(v) for r, v in sess.items()}, flush=True)
    grid = []
    for mode in ("his", "ict"):
        for zone in ("full", "half"):
            for age in (10, 30):
                for kR in (1, 2, 3):
                    rows = run_cell(data, mode, zone, age, kR, keep_meta=True)
                    h1 = [r for r in rows if r["day"] < SPLIT]; h2 = [r for r in rows if r["day"] >= SPLIT]
                    cell = dict(mode=mode, zone=zone, age=age, kR=kR, all=stats(rows, sessions),
                                h1=stats(h1, h1s), h2=stats(h2, h2s),
                                es=stats([r for r in rows if r["root"] == "ES"], sessions),
                                nq=stats([r for r in rows if r["root"] == "NQ"], sessions))
                    grid.append((cell, rows))
                    print(json.dumps(cell), flush=True)
    # selection on H1 only
    elig = [g for g in grid if g[0]["h1"].get("n", 0) >= 50]
    sel = max(elig, key=lambda g: g[0]["h1"]["meanR"])
    best_all = max(grid, key=lambda g: g[0]["all"].get("meanR", -9))
    out = dict(sessions=len(sessions), first=sessions[0], last=sessions[-1], h1=len(h1s), h2=len(h2s),
               grid=[g[0] for g in grid])
    import propfirm_gate, propfirm_luck_check
    for tag, (cell, rows) in (("h1_selected", sel), ("full_best", best_all)):
        res = dict(cell={k: cell[k] for k in ("mode", "zone", "age", "kR")})
        res["null"] = nulls(data, rows, cell["kR"])
        # day-level bootstrap on $/traded-day at $200
        ds = np.array([v for _, v in daily_series(rows, 200)])
        rng = np.random.default_rng(3)
        bs = np.array([rng.choice(ds, len(ds)).mean() for _ in range(5000)])
        res["boot_daymean_200"] = dict(mean=round(ds.mean(), 1), lo=round(np.percentile(bs, 2.5), 1),
                                       hi=round(np.percentile(bs, 97.5), 1), p_le0=round(float((bs <= 0).mean()), 4))
        res["gate"] = {}
        for rk in RISKS:
            daily = daily_series(rows, rk)
            g = propfirm_gate.gate_series(daily)
            luck = propfirm_luck_check.compute(daily, propfirm_gate.FIRM_RULES, n_shuffles=200)
            res["gate"][int(rk)] = {name: dict(passed=v["passed"], fail_reason=v.get("fail_reason"),
                                               all_starts=v["all_starts_pass_pct"],
                                               eval_ready=luck[name]["eval_ready"],
                                               h1=luck[name]["h1"], h2=luck[name]["h2"])
                                    for name, v in g.items()}
        out[tag] = res
        print(tag, json.dumps(res, default=str)[:3000], flush=True)
    (HERE / f"t03_result_{'_'.join(roots)}.json").write_text(json.dumps(out, indent=1, default=str))
    pd.DataFrame(sel[1]).to_csv(HERE / f"t03_selected_trades_{'_'.join(roots)}.csv", index=False)
    print("WROTE")


if __name__ == "__main__":
    main()
