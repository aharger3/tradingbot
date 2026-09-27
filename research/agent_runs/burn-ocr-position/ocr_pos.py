"""burn-ocr-position: Austin's one-candle rule (OCR) block, redefined, and whether retest position in it predicts R.

OCR (00-austin-spec-0926): "draw a block over the opposite-close candle; price breaks it and retests
anywhere inside the block (higher in the block = better)". a1's proxy (any opposite-close candle <=10 bars
before the break) existed 92% of the time and carried no signal. Redefinition here:

  block = high/low of the LAST opposite-close 1-min candle (down-close for a long, up-close for a short)
          INSIDE the displacement leg, i.e. bars break_idx .. extreme_idx, where extreme_idx is the bar with
          the furthest excursion past the ORB level before the retest bar.
  pos   = where the retest bar's extreme (low for long, high for short) sits in the block, direction-normalised:
          1 = far edge in trade direction (top for longs, bottom for shorts = shallow), 0 = near edge,
          >1 = retest never reached the block, <0 = retest pierced through it.
          "Higher in the block = better" predicts R rising with pos.

Samples: (a) the 105 frozen MNQ trades (v2-t01 OR5 10:30 D1 strong), re-derived with an instrumented copy of
orb1m.signal and asserted to match trade-for-trade; (b) the 40 v3-eye2 replay candidates (last 20 Mon-Thu
sessions), R2 simulated with orb1m's honest-fill run_trade to 11:00.
Paper research only; reads the main checkout's untracked data read-only.
"""
import sys, json
from pathlib import Path
import numpy as np

RUNS = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
TICK = 0.25
NPERM = 5000


def find_block(A, side, bi, j):
    """Leg = bars bi..ext (ext = furthest excursion bar in [bi, j-1]). Returns (lo, hi, k, ext) of the last
    opposite-close candle in the leg, or (None, None, None, ext) if the leg has none."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    idx = [k for k in range(bi, j) if not np.isnan(C[k])]
    if not idx:
        return None, None, None, None
    ext = max(idx, key=lambda k: H[k]) if side > 0 else min(idx, key=lambda k: L[k])
    for k in range(ext, bi - 1, -1):
        if np.isnan(C[k]):
            continue
        if (C[k] - O[k]) * side < 0:
            return float(L[k]), float(H[k]), k, ext
    return None, None, None, ext


def block_pos(A, side, j, lo, hi):
    """Direction-normalised retest position in the block (1 = shallow edge, 0 = deep edge)."""
    if lo is None or hi <= lo:
        return None
    px = A["low"][j] if side > 0 else A["high"][j]
    return float((px - lo) / (hi - lo)) if side > 0 else float((hi - px) / (hi - lo))


def signal_x(A, orn, cut, disp_k, trig, orb):
    """orb1m.signal with the active break index and level returned. Logic copied verbatim."""
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    if np.isnan(H[:orn]).all():
        return None
    orh, orl = np.nanmax(H[:orn]), np.nanmin(L[:orn])
    rngs = H - L
    state = None
    for j in range(orn, cut - 1):
        if np.isnan(C[j]):
            continue
        prev = rngs[max(0, j - 14):j]
        atr = np.nanmean(prev) if np.sum(~np.isnan(prev)) >= 3 else np.nan
        if state is None:
            if C[j] > orh:
                state = [1, orh, j, H[j] - orh, False]
            elif C[j] < orl:
                state = [-1, orl, j, orl - L[j], False]
            else:
                continue
            state[4] = disp_k == 0 or state[3] >= disp_k * atr
            continue
        side, lvl, bi, exc, disp = state
        if (C[j] - lvl) * side <= 0:
            state = None
            if C[j] > orh:
                state = [1, orh, j, H[j] - orh, False]
            elif C[j] < orl:
                state = [-1, orl, j, orl - L[j], False]
            if state:
                state[4] = disp_k == 0 or state[3] >= disp_k * atr
            continue
        touched = (L[j] <= lvl + TICK) if side > 0 else (H[j] >= lvl - TICK)
        if touched and disp and j > bi:
            ok = True if trig == "any" else (orb.pin(O[j], H[j], L[j], C[j], side) if trig == "pin" else orb.strong(O[j], H[j], L[j], C[j], side))
            if ok and not np.isnan(O[j + 1]):
                stop = (L[j] - TICK) if side > 0 else (H[j] + TICK)
                return (j + 1, side, stop, bi, lvl)
        exc = max(exc, (H[j] - lvl) if side > 0 else (lvl - L[j]))
        state[3] = exc
        if not disp and not np.isnan(atr) and exc >= disp_k * atr:
            state[4] = True
        if j - bi > 30:
            state = None
    return None


def tercile_table(pos, R, h1, rng):
    """Quantile terciles of pos (block-exists rows only). Label-permutation p: P(perm tercile mean >= obs),
    and top-minus-bottom diff p (one-sided, 'higher is better')."""
    pos, R, h1 = np.asarray(pos, float), np.asarray(R, float), np.asarray(h1, bool)
    q1, q2 = np.quantile(pos, [1 / 3, 2 / 3])
    lab = np.where(pos <= q1, 0, np.where(pos <= q2, 1, 2))
    obs = np.array([R[lab == t].mean() for t in range(3)])
    perm = np.empty((NPERM, 3))
    for b in range(NPERM):
        Rp = rng.permutation(R)
        perm[b] = [Rp[lab == t].mean() for t in range(3)]
    rows = []
    for t in range(3):
        m = lab == t
        rows.append(dict(tercile=["low", "mid", "high"][t], lo=float(pos[m].min()), hi=float(pos[m].max()), n=int(m.sum()),
                         R=float(obs[t]), H1=float(R[m & h1].mean()) if (m & h1).any() else None,
                         H2=float(R[m & ~h1].mean()) if (m & ~h1).any() else None,
                         p=float((perm[:, t] >= obs[t]).mean())))
    d_obs = obs[2] - obs[0]
    p_diff = float(((perm[:, 2] - perm[:, 0]) >= d_obs).mean())
    rho = float(np.corrcoef(np.argsort(np.argsort(pos)), np.argsort(np.argsort(R)))[0, 1])
    return rows, dict(top_minus_bottom=float(d_obs), p_diff=p_diff, spearman=rho, cuts=[float(q1), float(q2)])


def summarise(recs, rng, label):
    n = len(recs)
    has = [r for r in recs if r["pos"] is not None]
    inside = [r for r in has if 0 <= r["pos"] <= 1]
    out = dict(sample=label, n=n, block_exists=len(has) / n if n else 0, retest_inside_block=len(inside) / n if n else 0,
               R_all=float(np.mean([r["R"] for r in recs])) if n else None,
               R_no_block=float(np.mean([r["R"] for r in recs if r["pos"] is None])) if n > len(has) else None,
               n_no_block=n - len(has),
               R_inside=float(np.mean([r["R"] for r in inside])) if inside else None, n_inside=len(inside))
    if len(has) >= 6:
        rows, diff = tercile_table([r["pos"] for r in has], [r["R"] for r in has], [r["h1"] for r in has], rng)
        out["terciles"], out["diff"] = rows, diff
    return out


def main():
    sys.path.insert(0, str(RUNS / "v2-s07-data"))
    sys.path.insert(0, str(RUNS / "v2-t01-orb-1m"))
    sys.path.insert(0, str(RUNS / "v3-eye2-candidates"))
    import orb1m
    from omen_data import load_fut, SPEC
    rng = np.random.default_rng(7)
    usd, comm = SPEC["MNQ"]["usd_pt"], SPEC["MNQ"]["rt_comm"]
    df = load_fut("MNQ", "09:30", "11:01")
    days = {str(d): orb1m.day_arrays(g) for d, g in df.groupby("date")}
    dates = sorted(days)
    mid = dates[len(dates) // 2]

    frozen = json.load(open(RUNS / "v2-t01-orb-1m" / "trades_MNQ_OR5_1030_D1_strong.json"))
    recs = []
    for t in frozen:
        A = days[t["date"]]
        s = signal_x(A, 5, 60, 1.0, "strong", orb1m)
        assert s and s[0] == t["i"] and s[1] == t["side"], (t, s)
        i, side, stop, bi, lvl = s
        r, _ = orb1m.run_trade(A, i, side, t["dist"], 60, usd, comm)
        assert abs(r - t["R"]) < 1e-9, (t, r)
        j = i - 1
        lo, hi, k, ext = find_block(A, side, bi, j)
        recs.append(dict(date=t["date"], side=side, bi=bi, ext=ext, k=k, j=j, pos=block_pos(A, side, j, lo, hi),
                         R=t["R"], h1=t["date"] < mid))
    res_frozen = summarise(recs, rng, "MNQ frozen 105 (2024-09..2026-09)")

    import candidates as cand_mod
    cands, sess = cand_mod.run("MNQ", 20, None)
    crec = []
    cmid = str(sess[len(sess) // 2])
    for c in cands:
        d = c["time"][:10]
        A = days[d]
        side = 1 if c["direction"] == "long" else -1
        j = c["features"]["minutes_after_open"]
        bi = j - c["features"]["retest_bars_after_break"]
        dist = c["features"]["stop_dist_pts"]
        r, _ = orb1m.run_trade(A, j + 1, side, dist, 90, usd, comm)
        lo, hi, k, ext = find_block(A, side, bi, j)
        crec.append(dict(date=d, side=side, pos=block_pos(A, side, j, lo, hi), R=float(r), h1=d < cmid, grade=c["grade_hint"]))
    res_eye2 = summarise(crec, rng, "eye2 40 replay candidates (last 20 Mon-Thu, R2 to 11:00)")

    out = dict(frozen=res_frozen, eye2=res_eye2, frozen_rows=recs, eye2_rows=crec)
    Path("ocr_pos.json").write_text(json.dumps(out, indent=1, default=float))
    for res in (res_frozen, res_eye2):
        print(json.dumps({k: v for k, v in res.items() if k not in ("terciles",)}, default=float))
        for row in res.get("terciles", []):
            print("  ", json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}))


if __name__ == "__main__":
    main()
