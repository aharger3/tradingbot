"""E10 - J-Dub premarket levels as targets (OMEN canon section 5, row E10). Paper research only. Not investment advice.

DECLARATION (written and committed BEFORE any result was computed or seen)
---------------------------------------------------------------------------
Fit/explore window : real NQ 1-min, 2024-09-26 -> 2026-09-25 ONLY. Window A (2019-09-26 -> 2024-09-25) is never loaded:
                     the only NQ files on disk start 2024-09-25 20:00 ET and run_fit() asserts every session date is inside
                     the fit window. Window B (2010-06-07 -> 2019-09-25) is the confirm window and is not touched here.
Entries (frozen)   : research/agent_runs/v3-t-mnq/mnq.py signal() + the trade bookkeeping of trade(), setup
                     "v2 baseline (OR5 D1.0 strong)", cut 10:30 (60 bars after 09:30), 1 trade/day, entry = next bar open +1 tick,
                     stop past the trigger candle. mnq.py and v2-t01-orb-1m/orb1m.py are imported unchanged (sha256 recorded).
Fills / same-bar   : orb1m.sim() unchanged: stop is checked before target inside one 1-min bar (stop wins); a limit target
                     needs price 1 tick THROUGH it; flat at the 10:30 bar open less 1 tick; $1.24 round trip per contract.
Levels             : PDH/PDL = high/low of the previous trading session's RTH bars, 09:30:00-15:59:59 ET, same contract as today.
                     PMH/PML = high/low of today's 1-min bars stamped 04:00 through 09:29 ET inclusive (bars covering
                     04:00:00-09:29:59), same contract. Known at 09:30, so no look-ahead for a 09:35+ entry.
Rule (literal)     : R-distance of a level = (level - fill) * side / dist, where fill is the entry fill and dist = |fill - stop|.
                     Look only at levels strictly beyond the fill in the trade direction. Take the NEAREST such level.
                     If its R-distance >= m, the target is that level. Otherwise (or if no level lies ahead) the target is flat 2R.
                     (The other reading, "nearest level among those >= m R away", is NOT tested; it would be a second family.)
Grid               : m in {1.0, 1.5, 2.0}. MAX VARIANT COUNT = 3. Baseline = flat 2R (not a variant).
Pick rule          : the variant with the largest mean(R_variant - R_baseline) on the fit window. Ties -> smaller m.
Statistics         : per variant n, mean R, win%, H1/H2 (split at the median session date of the fit window, as mnq.summ does),
                     top-5-days share, day-shuffle p (1,000 random other days, same entry minute/side/dist, that day's own
                     levels), and the PAIRED test vs the baseline: one-sided day-level sign-flip permutation on
                     d = R_variant - R_baseline (200,000 flips, seed 20261003). Within-family Bonferroni x3 shown for the pick.
Output             : a locked pre-registration for the window B confirm (prereg-E10.md). The fit window can never confirm anything.
"""
import os, sys, glob, json, hashlib, math
import numpy as np, pandas as pd

AR = os.environ.get("OMEN_FROZEN_DIR", r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
FIT_START, FIT_END = "2024-09-26", "2026-09-25"
GRID = (1.0, 1.5, 2.0)
LEVEL_KEYS = ("pdh", "pdl", "pmh", "pml")
PM_START = "04:00"          # inclusive
PM_LAST_BAR = "09:29"       # inclusive (bar covers 09:29:00-09:29:59)
N_FLIPS, FLIP_SEED = 200_000, 20261003
N_SHUF, SHUF_SEED = 1000, 7

for p in ("v3-t-mnq", "v2-t01-orb-1m", "v2-signal", "v2-s07-data"):
    sys.path.insert(0, os.path.join(AR, p))
sys.path.insert(0, os.path.dirname(AR))
import mnq                                   # frozen, unchanged
from orb1m import sim, TICK                  # frozen, unchanged
USD, COMM, RISK, MAXN = mnq.USD, mnq.COMM, mnq.RISK, mnq.MAXN
CUT = mnq.CUTS["10:30"]
SETUP = "v2 baseline (OR5 D1.0 strong)"


def frozen_shas():
    out = {}
    for rel in ("v3-t-mnq/mnq.py", "v2-t01-orb-1m/orb1m.py"):
        out[rel] = hashlib.sha256(open(os.path.join(AR, rel), "rb").read()).hexdigest()
    return out


# ---------------------------------------------------------------- data
def load_days(nq_dir=None):
    """Same day construction as mnq.load_real (front month by RTH volume, holiday list), plus explicit PMH/PML.
    Each day: open/high/low/close arrays (91 one-minute bars from 09:30), date, pdh, pdl, pmh, pml."""
    nq_dir = nq_dir or os.path.join(AR, "t01-orb5", "fut")
    NY = "America/New_York"
    parts = []
    for f in sorted(glob.glob(os.path.join(nq_dir, "NQ*.csv"))):
        d = pd.read_csv(f)
        if d.empty:
            continue
        d.columns = [c.lower() for c in d.columns]
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert(NY)
        d["k"] = os.path.basename(f).split("_")[0]
        parts.append(d[["ts", "open", "high", "low", "close", "volume", "k"]])
    df = pd.concat(parts).set_index("ts").sort_index()
    t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy()
    rth["date"] = rth.index.strftime("%Y-%m-%d")
    front = rth.groupby(["date", "k"])["volume"].sum().reset_index().sort_values("volume").groupby("date").last()["k"]
    by_k = {k: df[df.k == k] for k in df.k.unique()}
    days, prev = [], None
    for D, k in front.items():
        if D in mnq.HOL:
            continue
        g = rth[(rth.date == D) & (rth.k == k)]
        A = mnq.arr91(g)
        if np.isnan(A["open"][:5]).all():
            continue
        c = by_k[k]
        pm = c.loc[pd.Timestamp(f"{D} {PM_START}", tz=NY):pd.Timestamp(f"{D} {PM_LAST_BAR}", tz=NY)]
        pr = rth[(rth.date == prev) & (rth.k == k)] if prev else None
        A.update(date=D,
                 pmh=float(pm.high.max()) if len(pm) else None, pml=float(pm.low.min()) if len(pm) else None,
                 pdh=float(pr.high.max()) if pr is not None and len(pr) else None,
                 pdl=float(pr.low.min()) if pr is not None and len(pr) else None)
        days.append(A)
        prev = D
    return days


# ---------------------------------------------------------------- rule
def nearest_level(A, fill, d, dist):
    """Nearest of PDH/PDL/PMH/PML strictly beyond fill in the trade direction. Returns (R_dist, name, price) or None."""
    best = None
    for k in LEVEL_KEYS:
        v = A.get(k)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        r = (v - fill) * d / dist
        if r > 0 and (best is None or r < best[0]):
            best = (r, k, v)
    return best


def target_for(A, fill, d, dist, m):
    """m=None -> flat 2R baseline. Returns (target_price, label)."""
    flat = fill + d * 2.0 * dist
    if m is None:
        return flat, "flat2R"
    b = nearest_level(A, fill, d, dist)
    if b is not None and b[0] >= m - 1e-9:
        return b[2], b[1]
    return flat, "flat2R"


def trade_to_target(A, i, side, dist, cut, tgt):
    """Same sizing/commission bookkeeping as mnq.trade(..., '2R') but with an arbitrary absolute target price.
    Returns (R, usd, exit_kind)."""
    d = side
    fill = A["open"][i] + TICK * d
    stop = fill - d * dist
    n = min(MAXN, int(RISK // (dist * USD + COMM)))
    if n == 0:
        n = 1
    x = sim(A, d, i, stop, tgt, cut)
    pts = (x - fill) * d * n
    usd = pts * USD - n * COMM
    kind = "target" if x == tgt else ("stop" if (x - stop) * d <= 0 else "time")
    return usd / (n * dist * USD), usd, kind


def frozen_entries(days):
    dk, trig, tol, jm = mnq.SETUPS[SETUP]
    T = []
    for k, A in enumerate(days):
        s = mnq.signal(A, CUT, dk, trig, tol, jm)
        if not s:
            continue
        i, side, stop, j = s
        e = A["open"][i] + TICK * side
        dist = (e - stop) * side
        if dist < 2 * TICK:
            continue
        T.append(dict(date=A["date"], k=k, i=i, side=side, dist=dist, j=j))
    return T


def run_variant(days, T, m):
    rows = []
    for t in T:
        A = days[t["k"]]
        fill = A["open"][t["i"]] + TICK * t["side"]
        tgt, lab = target_for(A, fill, t["side"], t["dist"], m)
        R, usd, kind = trade_to_target(A, t["i"], t["side"], t["dist"], CUT, tgt)
        rows.append(dict(date=t["date"], R=R, usd=usd, kind=kind, tgt_label=lab, tgt_R=(tgt - fill) * t["side"] / t["dist"]))
    return rows


# ---------------------------------------------------------------- statistics
def top5_share(R):
    R = np.asarray(R, float)
    tot = R.sum()
    top = np.sort(R)[::-1][:5].sum()
    pos = R[R > 0].sum()
    return (float(top / tot) if tot > 0 else None, float(top / pos) if pos > 0 else None)


def summarize(R, dates, mid):
    R = np.asarray(R, float)
    h1 = np.array([d < mid for d in dates])
    return dict(n=int(len(R)), mean=float(R.mean()), win=float((R > 0).mean()),
                h1=float(R[h1].mean()) if h1.any() else None, h2=float(R[~h1].mean()) if (~h1).any() else None,
                n_h1=int(h1.sum()), n_h2=int((~h1).sum()), top5_net=top5_share(R)[0], top5_gross=top5_share(R)[1])


def paired_signflip(d, n_flips=N_FLIPS, seed=FLIP_SEED, chunk=20_000):
    """One-sided (mean d > 0) day-level sign-flip permutation p-value. Also returns two-sided."""
    d = np.asarray(d, float)
    obs = d.mean()
    rng = np.random.default_rng(seed)
    ge = ge2 = 0
    done = 0
    while done < n_flips:
        c = min(chunk, n_flips - done)
        s = rng.integers(0, 2, size=(c, len(d)), dtype=np.int8) * 2 - 1
        pm = (s @ d) / len(d)
        ge += int((pm >= obs - 1e-12).sum())
        ge2 += int((np.abs(pm) >= abs(obs) - 1e-12).sum())
        done += c
    return (1 + ge) / (n_flips + 1), (1 + ge2) / (n_flips + 1)


def boot_ci(d, n=10_000, seed=11):
    d = np.asarray(d, float)
    rng = np.random.default_rng(seed)
    m = rng.choice(d, size=(n, len(d)), replace=True).mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def day_shuffle_p(days, T, m, obs_mean, n_shuf=N_SHUF, seed=SHUF_SEED):
    """Std-bar convention (mnq.run_cell): each trade replaced by the same entry minute/side/dist on a random other day,
    that day's own levels and the same target rule. p = share of shuffles with mean R >= observed."""
    rng = np.random.default_rng(seed)
    ge = 0
    for _ in range(n_shuf):
        rr = []
        for t in T:
            while True:
                k = int(rng.integers(len(days)))
                if k != t["k"] and not np.isnan(days[k]["open"][t["i"]]):
                    break
            A = days[k]
            fill = A["open"][t["i"]] + TICK * t["side"]
            tgt, _ = target_for(A, fill, t["side"], t["dist"], m)
            rr.append(trade_to_target(A, t["i"], t["side"], t["dist"], CUT, tgt)[0])
        if np.mean(rr) >= obs_mean:
            ge += 1
    return ge / n_shuf


def run_fit(days=None, out_dir=None, n_flips=N_FLIPS, n_shuf=N_SHUF):
    days = days if days is not None else load_days()
    assert days[0]["date"] >= FIT_START and days[-1]["date"] <= FIT_END, "window guard: only the fit window may be loaded"
    dates = [A["date"] for A in days]
    mid = dates[len(dates) // 2]
    T = frozen_entries(days)
    base = run_variant(days, T, None)
    Rb = np.array([r["R"] for r in base])
    res = dict(window=[dates[0], dates[-1]], sessions=len(days), mid=mid, shas=frozen_shas(),
               n_pm_missing=sum(A["pmh"] is None for A in days), n_pd_missing=sum(A["pdh"] is None for A in days),
               baseline=summarize(Rb, [r["date"] for r in base], mid), variants={})
    res["baseline"]["kinds"] = {k: sum(r["kind"] == k for r in base) for k in ("target", "stop", "time")}
    res["baseline"]["p_shuffle"] = day_shuffle_p(days, T, None, Rb.mean(), n_shuf)
    h1b = np.array([r["date"] < mid for r in base])
    allrows = {"base": base}
    for m in GRID:
        rows = run_variant(days, T, m)
        allrows[m] = rows
        R = np.array([r["R"] for r in rows])
        d = R - Rb
        p1, p2 = paired_signflip(d, n_flips)
        lo, hi = boot_ci(d)
        changed = np.array([r["tgt_label"] != "flat2R" for r in rows])
        v = summarize(R, [r["date"] for r in rows], mid)
        v.update(dict(
            diff=float(d.mean()), diff_h1=float(d[h1b].mean()), diff_h2=float(d[~h1b].mean()),
            p_paired_1s=p1, p_paired_2s=p2, diff_ci95=[lo, hi],
            p_shuffle=day_shuffle_p(days, T, m, R.mean(), n_shuf),
            n_level_target=int(changed.sum()),
            mean_R_changed=float(R[changed].mean()) if changed.any() else None,
            mean_R_base_changed=float(Rb[changed].mean()) if changed.any() else None,
            levels={k: int(sum(r["tgt_label"] == k for r in rows)) for k in LEVEL_KEYS},
            kinds={k: sum(r["kind"] == k for r in rows) for k in ("target", "stop", "time")},
            mean_tgt_R_changed=float(np.mean([r["tgt_R"] for r in rows if r["tgt_label"] != "flat2R"])) if changed.any() else None))
        res["variants"][str(m)] = v
    pick = max(GRID, key=lambda m: (round(res["variants"][str(m)]["diff"], 12), -m))
    res["pick_m"] = pick
    res["pick_p_bonf3"] = min(1.0, res["variants"][str(pick)]["p_paired_1s"] * len(GRID))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "e10_trades.csv"), "w") as f:
            f.write("date,side,dist,R_base," + ",".join(f"R_m{m},tgt_m{m},tgtR_m{m}" for m in GRID) + "\n")
            for n_, t in enumerate(T):
                cells = []
                for m in GRID:
                    r = allrows[m][n_]
                    cells += [f"{r['R']:.4f}", r["tgt_label"], f"{r['tgt_R']:.3f}"]
                f.write(f"{t['date']},{t['side']},{t['dist']:.2f},{allrows['base'][n_]['R']:.4f}," + ",".join(cells) + "\n")
    return res


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    r = run_fit(out_dir=out)
    open(os.path.join(out, "e10_result.txt"), "w").write(json.dumps(r, indent=1, default=float))
    print(json.dumps(r, indent=1, default=float))
