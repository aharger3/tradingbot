"""E6 fit/explore: mantra setup with INTRABAR stop-market entry (level +/- tol x previous candle range) and an
optional ON WATCH refusal, vs the frozen next-open-fill mantra baseline.  Paper research only, not advice.

FIT WINDOW ONLY: real NQ 1-min 2024-09-26 -> 2026-09-25.  Window A (2019-09-26 -> 2024-09-25) is reserved and is
never loaded: the loader drops any row dated outside the fit window before doing anything else, and asserts it.

Frozen pieces (imported by absolute path from the main checkout, never edited): v3-t-mnq/mnq.py (signal, trade,
load helpers) and v2-t01-orb-1m/orb1m.py (pin, strong, sim, TICK).

Declared BEFORE any variant was run (see declared.json): 6 variants = tol {0.15, 0.25, 0.35} x ON WATCH {off, on};
best variant = highest mean R per trade among variants with n >= 30 (tie -> larger n), chosen on the fit window only.

Intrabar entry model (1-minute bars; strict = primary, M1 = first run kept for the record):
  * Same setup state machine as mnq.signal (OR5 break, displacement >= 1 ATR, wick touch of the level within 1 tick,
    retest within 30 bars, a close back through the level voids it, cutoff 10:30 flat).
  * The strong/pin close filter is DROPPED (it is only knowable at the close). Its job is replaced by price having to
    cross level +/- U, where U = tol x range of the previous candle (floor 2 ticks).
  * STRICT (primary, M2): when a touch (retest) bar CLOSES, a buy stop-market is armed at T = level + U with
    U = tol x that retest candle's range, stop S = retest low - 1 tick (short mirrors). It is live from the next bar.
    No fill is ever allowed inside the bar that made the stop level, so no within-bar order assumption is needed.
    A resting order fills on a later bar when high >= T (fill max(T, open) + 1 tick). If the same bar also has
    low <= S, the stop wins: stopped loss at min(S, open) - 1 tick. If only low <= S the order is cancelled and
    the setup stays alive for a fresh touch. The order dies on a close back through the level or after 30 bars.
  * M1 (first run, optimistic, NOT the primary): fill allowed inside the touch bar itself under the path convention
    close >= open -> O,L,H,C ; close < open -> O,H,L,C (long), U from the candle before the touch bar. It assumes the
    touch low is final before the cross, i.e. a stop placed with knowledge of the final low. Kept only as a record.
  * ON WATCH = on: after an entry triggers, if that bar CLOSES within one tolerance unit (tol x range of the prior
    candle) of the running RTH day extreme in the trade direction, the trade is refused (never taken).
  * Exit identical to the baseline: 2R target (needs 1 tick through), same-bar stop wins, flat at 10:30 bar open less
    1 tick, 1 tick entry slip, $1.24 round trip per micro, R = pts/dist - comm/(dist x $2).
"""
import os, sys, json, glob, hashlib
import numpy as np
import pandas as pd

AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"
for p in (AR + r"\v3-t-mnq", AR + r"\v2-signal", AR + r"\v2-t01-orb-1m", r"C:\Users\aharg\Desktop\Projects\tradingbot\research"):
    if p not in sys.path:
        sys.path.insert(0, p)
import mnq  # frozen v3 mantra (imports frozen orb1m)
from orb1m import TICK

FIT_START, FIT_END = "2024-09-26", "2026-09-25"
CUT = mnq.CUTS["10:30"]            # 60 -> bars 0..59, flat at the 10:30 open
USD, COMM = mnq.USD, mnq.COMM      # 2.0, 1.24
ORN, DK = 5, 1.0
TOLS = (0.15, 0.25, 0.35)
ONW = (False, True)
GRID = [(t, w) for t in TOLS for w in ONW]
assert len(GRID) == 6
MIN_N = 30


# ---------------------------------------------------------------- data (fit window only)
def load_fit_days(fut_dir=None):
    """Real NQ 1-min, front month by RTH volume per day, fit window only. Same logic as mnq.load_real, but rows
    outside the fit window are dropped immediately after the timestamp conversion."""
    fut_dir = fut_dir or (AR + r"\t01-orb5\fut")
    parts = []
    for f in sorted(glob.glob(fut_dir + r"\NQ*.csv")):
        d = pd.read_csv(f)
        if d.empty:
            continue
        d.columns = [c.lower() for c in d.columns]
        d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
        dd = d["ts"].dt.strftime("%Y-%m-%d")
        d = d[(dd >= FIT_START) & (dd <= FIT_END)]
        if d.empty:
            continue
        d["k"] = os.path.basename(f).split("_")[0]
        parts.append(d[["ts", "open", "high", "low", "close", "volume", "k"]])
    df = pd.concat(parts).set_index("ts").sort_index()
    t = df.index.hour * 60 + df.index.minute
    rth = df[(t >= 570) & (t < 960)].copy()
    rth["date"] = rth.index.strftime("%Y-%m-%d")
    assert rth["date"].min() >= FIT_START and rth["date"].max() <= FIT_END
    front = rth.groupby(["date", "k"])["volume"].sum().reset_index().sort_values("volume").groupby("date").last()["k"]
    days = []
    for D, k in front.items():
        if D in mnq.HOL:
            continue
        g = rth[(rth.date == D) & (rth.k == k)]
        A = mnq.arr91(g)
        if np.isnan(A["open"][:5]).all():
            continue
        A["date"] = D
        days.append(A)
    assert days[0]["date"] >= FIT_START and days[-1]["date"] <= FIT_END
    return days


# ---------------------------------------------------------------- cost / R
def r_of(e, x, side, dist):
    return (x - e) * side / dist - COMM / (dist * USD)


def _exit_from(A, side, k, e, stop, tgt, cut, reach_k):
    """Exit price for a position entered in bar k. reach_k = the furthest the bar can go in the trade direction
    AFTER the fill (high for longs, low for shorts). Later bars use the full bar. Stop first (stop wins)."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    if side > 0:
        if reach_k >= tgt + TICK:
            return tgt
    else:
        if reach_k <= tgt - TICK:
            return tgt
    for b in range(k + 1, cut):
        if np.isnan(O[b]):
            continue
        if side > 0:
            if L[b] <= stop:
                return min(stop, O[b]) - TICK
            if H[b] >= tgt + TICK:
                return tgt
        else:
            if H[b] >= stop:
                return max(stop, O[b]) + TICK
            if L[b] <= tgt - TICK:
                return tgt
    if cut < 91 and not np.isnan(O[cut]):
        px = O[cut]
    else:
        px = C[:cut][~np.isnan(C[:cut])][-1]
    return px - TICK * side


# ---------------------------------------------------------------- E6 intrabar entry
def e6_day(A, tol, onwatch, cut=CUT, trace=None, strict=True):
    """Returns (trade_dict | None, n_refused). trade_dict: date,k(entry bar),side,e,stop,dist,x,R,how."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    orh, orl = np.nanmax(H[:ORN]), np.nanmin(L[:ORN])
    rngs = H - L
    state = None
    pend = None            # (side, T, S)
    refused = 0
    no_arm = -1

    def brk(j, atr):
        s = [1, orh, j, H[j] - orh, False] if C[j] > orh else ([-1, orl, j, orl - L[j], False] if C[j] < orl else None)
        if s:
            s[4] = DK == 0 or s[3] >= DK * atr
        return s

    def finish(j, side, e, stop, how, reach):
        """Build the trade for an entry in bar j. Applies ON WATCH. Returns trade dict, or 'refused'."""
        dist = (e - stop) * side
        if onwatch:
            prior = rngs[j - 1] if j >= 1 else np.nan
            u = tol * prior if not np.isnan(prior) else 0.0
            if side > 0:
                near = C[j] >= np.nanmax(H[:j + 1]) - u
            else:
                near = C[j] <= np.nanmin(L[:j + 1]) + u
            if near:
                return "refused"
        if dist < 2 * TICK:
            return None
        if how == "stopwins":
            x = (min(stop, O[j]) - TICK) if side > 0 else (max(stop, O[j]) + TICK)
        else:
            tgt = e + side * 2 * dist
            x = _exit_from(A, side, j, e, stop, tgt, cut, reach)
        return dict(date=A["date"], k=j, side=side, e=float(e), stop=float(stop), dist=float(dist), x=float(x),
                    R=float(r_of(e, x, side, dist)), how=how)

    for j in range(ORN, cut):
        if np.isnan(C[j]):
            continue
        prev = rngs[max(0, j - 14):j]
        atr = np.nanmean(prev) if np.sum(~np.isnan(prev)) >= 3 else np.nan

        # 1) resting order from an earlier touch bar
        if pend is not None:
            side, T, S = pend
            if side > 0:
                trig, stp = H[j] >= T, L[j] <= S
            else:
                trig, stp = L[j] <= T, H[j] >= S
            if trig and stp:
                e = (max(T, O[j]) + TICK) if side > 0 else (min(T, O[j]) - TICK)
                r = finish(j, side, e, S, "stopwins", None)
                if r == "refused":
                    refused += 1; pend = None; no_arm = j
                else:
                    return r, refused
            elif trig:
                e = (max(T, O[j]) + TICK) if side > 0 else (min(T, O[j]) - TICK)
                r = finish(j, side, e, S, "rest", H[j] if side > 0 else L[j])
                if r == "refused":
                    refused += 1; pend = None; no_arm = j
                else:
                    return r, refused
            elif stp:
                pend = None

        # 2) setup state machine (mirrors mnq.signal)
        if state is None:
            state = brk(j, atr)
            continue
        side, lvl, bi, exc, disp = state
        if (C[j] - lvl) * side <= 0:
            state = brk(j, atr)
            pend = None
            continue
        touched = (L[j] <= lvl + TICK) if side > 0 else (H[j] >= lvl - TICK)
        if touched and disp and j > bi and pend is None and j <= cut - 2 and no_arm != j:
            if trace is not None:
                trace.append((j, side))
            prior = rngs[j] if strict else rngs[j - 1]
            u = max(tol * prior, 2 * TICK) if not np.isnan(prior) else 2 * TICK
            if side > 0:
                T, S = lvl + u, L[j] - TICK
                reach = H[j] if C[j] >= O[j] else C[j]
                hit = (not strict) and reach >= T
            else:
                T, S = lvl - u, H[j] + TICK
                reach = L[j] if C[j] <= O[j] else C[j]
                hit = (not strict) and reach <= T
            if hit:
                e = (T + TICK) if side > 0 else (T - TICK)
                r = finish(j, side, e, S, "touchbar", reach)
                if r == "refused":
                    refused += 1
                else:
                    return r, refused
            else:
                pend = (side, T, S)
        exc = max(exc, (H[j] - lvl) if side > 0 else (lvl - L[j]))
        state[3] = exc
        if not disp and not np.isnan(atr) and exc >= DK * atr:
            state[4] = True
        if j - bi > 30:
            state = None
            pend = None
    return None, refused


# ---------------------------------------------------------------- baselines (frozen mnq.py)
def baseline_day(A, trig="strong", cut=CUT):
    """B0 (trig='strong') = the frozen v3 mantra, next-open fill. B2 (trig='any') = control, same fill, no trigger
    candle filter (isolates the filter from the fill)."""
    s = mnq.signal(A, cut, DK, trig, TICK, 99)
    if not s:
        return None
    i, side, stop, j = s
    e = A["open"][i] + TICK * side
    dist = (e - stop) * side
    if dist < 2 * TICK:
        return None
    r, _ = mnq.trade(A, i, side, dist, cut, j, "2R")
    return dict(date=A["date"], k=i, side=side, e=float(e), stop=float(stop), dist=float(dist), R=float(r), how="nextopen")


# ---------------------------------------------------------------- statistics
def signflip_p(d, nperm=100000, seed=11, chunk=2000):
    """One-sided paired sign-flip permutation: P(mean of randomly signed d >= observed mean). d: per-day differences
    (zero days carry no weight). (1 + hits) / (1 + nperm)."""
    d = np.asarray(d, float)
    d = d[d != 0]
    if len(d) == 0:
        return 1.0
    obs = d.mean()
    rng = np.random.default_rng(seed)
    hits = 0
    done = 0
    while done < nperm:
        m = min(chunk, nperm - done)
        s = rng.integers(0, 2, size=(m, len(d))) * 2 - 1
        hits += int(((s * d).mean(axis=1) >= obs - 1e-12).sum())
        done += m
    return (1 + hits) / (1 + nperm)


def day_series(trades, dates):
    idx = {d: i for i, d in enumerate(dates)}
    v = np.zeros(len(dates))
    for t in trades:
        v[idx[t["date"]]] = t["R"]
    return v


def summarize(trades, dates, nperm=100000):
    n = len(trades)
    if n == 0:
        return dict(n=0)
    R = np.array([t["R"] for t in trades])
    mid = dates[len(dates) // 2]
    h1 = np.array([t["date"] < mid for t in trades])
    top5 = float(np.sort(R)[::-1][:5].sum())
    tot = float(R.sum())
    return dict(n=n, meanR=float(R.mean()), win=float((R > 0).mean()), h1_n=int(h1.sum()), h2_n=int((~h1).sum()),
                h1_R=float(R[h1].mean()) if h1.any() else None, h2_R=float(R[~h1].mean()) if (~h1).any() else None,
                p_vs_zero=signflip_p(R, nperm=nperm), top5_share=(top5 / tot) if tot > 0 else None,
                total_R=tot, R_per_session=tot / len(dates), mid=mid)


def run_all(days, nperm=100000, strict=True):
    dates = [A["date"] for A in days]
    out = {"sessions": len(dates), "first": dates[0], "last": dates[-1], "variants": {}, "trades": {}}
    B0 = [t for t in (baseline_day(A) for A in days) if t]
    B2 = [t for t in (baseline_day(A, "any") for A in days) if t]
    s0 = day_series(B0, dates)
    s2 = day_series(B2, dates)
    out["baseline"] = summarize(B0, dates, nperm)
    out["control_B2_next_open_no_trigger_filter"] = summarize(B2, dates, nperm)
    out["control_B2_next_open_no_trigger_filter"]["paired_p_vs_B0"] = signflip_p(s2 - s0, nperm)
    out["trades"]["B0"], out["trades"]["B2"] = B0, B2
    for tol, w in GRID:
        key = f"tol{int(round(tol * 100))}_onwatch_{'on' if w else 'off'}"
        T, nref = [], 0
        for A in days:
            t, r = e6_day(A, tol, w, strict=strict)
            nref += r
            if t:
                T.append(t)
        sv = day_series(T, dates)
        row = summarize(T, dates, nperm)
        row["refused_by_onwatch"] = nref
        if T:
            row["diff_meanR_per_trade_vs_B0"] = row["meanR"] - out["baseline"]["meanR"]
            row["diff_R_per_session_vs_B0"] = row["R_per_session"] - out["baseline"]["R_per_session"]
            row["paired_p_vs_B0"] = signflip_p(sv - s0, nperm)
            row["paired_p_vs_B2"] = signflip_p(sv - s2, nperm)
            row["days_differ_from_B0"] = int((sv != s0).sum())
            row["how"] = {h: int(sum(1 for t in T if t["how"] == h)) for h in ("touchbar", "rest", "stopwins")}
        out["variants"][key] = row
        out["trades"][key] = T
    ok = {k: v for k, v in out["variants"].items() if v.get("n", 0) >= MIN_N}
    out["best"] = max(ok, key=lambda k: (ok[k]["meanR"], ok[k]["n"])) if ok else None
    return out


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    nperm = int(os.environ.get("E6_NPERM", "100000"))
    days = load_fit_days()
    here = os.path.dirname(os.path.abspath(__file__))
    out = run_all(days, nperm, strict=True)
    m1 = run_all(days, nperm, strict=False)
    m1.pop("trades", None)
    out["M1_first_run_optimistic_not_primary"] = m1
    out["code_sha256"] = {"e6.py": sha(os.path.abspath(__file__)), "mnq.py": sha(AR + r"\v3-t-mnq\mnq.py"),
                          "orb1m.py": sha(AR + r"\v2-t01-orb-1m\orb1m.py")}
    json.dump(out, open(os.path.join(here, "e6_results.json"), "w"), indent=1, default=float)
    b = out["baseline"]
    print("sessions", out["sessions"], out["first"], out["last"])
    print("B0 frozen next-open", json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in b.items()}))
    print("B2 control", json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in out["control_B2_next_open_no_trigger_filter"].items()}))
    for k, v in out["variants"].items():
        print(k, json.dumps({a: (round(c, 4) if isinstance(c, float) else c) for a, c in v.items()}))
    print("BEST", out["best"])


if __name__ == "__main__":
    main()
