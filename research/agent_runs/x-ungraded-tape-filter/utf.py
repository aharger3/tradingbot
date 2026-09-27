"""x/ungraded-tape-filter: top-3 "eye pays" contexts as an ENGINE filter on every MNQ break-retest candidate
(eye2 detect_candidates) on real NQ 1-min 2024-09-26..2026-09-25, Mon-Thu. No grades used anywhere.

PRE-REGISTERED (life-plan 07-money/omen/x/ungraded-tape-filter.md, written before the run):
  deep   = max penetration through the OR level over break+1..trigger bars > 40 ticks (10 NQ pts)
  htf3   = htf_agree >= 3 of 4 (5m & 15m EMA20 side + EMA20 3-bar slope with trade; closed HTF bars; 3 prior RTH days)
  rs_top = (NQ - ES) % return 09:30 open -> trigger close, signed with trade, top tercile (cut over all signals)
  PASS iff R2_eng: >=2-of-3 mean >= +0.20R, >0 in both halves (split 2025-09-26), 200x day-shuffle p<.05 for diff.
Fills: frozen v3-t-mnq mnq.trade() (next open +1 tick, 2R, flat 11:00, $1.24 RT). Paper research only.
"""
import sys, json
import numpy as np, pandas as pd

AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"   # read-only imports/data (main checkout)
for p in (r"\v3-t-mnq", r"\v3-eye2-candidates", r"\v2-s07-data"):
    sys.path.insert(0, AR + p)
TICK, ORN, CUT, MID, DEPTH_TICKS = 0.25, 5, 90, "2025-09-26", 40


def pen_ticks(A, side, lvl, bi, j):
    """Deepest push through the level (ticks) over bars bi+1..j (post-break retest window, trigger included)."""
    H, L = A["high"][bi + 1:j + 1], A["low"][bi + 1:j + 1]
    pen = (lvl - L) if side > 0 else (H - lvl)
    return float(np.nanmax(pen) / TICK) if np.isfinite(pen).any() else np.nan


def rs_signed(Anq, Aes, j, side):
    """(NQ - ES) % return from the 09:30 open to the trigger-bar close, signed with the trade."""
    try:
        r = (Anq["close"][j] / Anq["open"][0] - 1) - (Aes["close"][j] / Aes["open"][0] - 1)
    except (KeyError, IndexError, TypeError):
        return np.nan
    return float(r * 100 * side)


def htf_agree(hist, cut, px, side):
    """mtf.py htf_agree: ema5_with + ema15_with + slope5_with + slope15_with (closed HTF bars only)."""
    h = hist[hist.index < cut]; v = 0
    for m in (5, 15):
        b = h.resample(f"{m}min", label="left", closed="left").agg({"close": "last"}).dropna()
        b = b[b.index + pd.Timedelta(minutes=m) <= cut]
        if len(b) < 4:
            return np.nan
        e = b.close.ewm(span=20, adjust=False).mean()
        v += int(np.sign(px - e.iloc[-1]) == side) + int(np.sign(e.iloc[-1] - e.iloc[-4]) == side)
    return v


def n_ctx(deep, htf, rs_top):
    return int(bool(deep)) + int(bool(htf)) + int(bool(rs_top))


def es_days():
    from omen_data import load_fut
    from candidates import day_arrays
    df = load_fut("MES", "09:30", "11:01")
    return {str(d): day_arrays(g) for d, g in df.groupby("date")}


def nq_rth_by_contract():
    from omen_data import _raw
    d = _raw("NQ"); t = d.ts.dt.hour * 60 + d.ts.dt.minute
    d = d[(t >= 570) & (t < 960)].copy(); d["ds"] = d.date.astype(str)
    return {k: g.set_index("ts")[["close", "ds"]] for k, g in d.groupby("contract")}, d


def main():
    import mnq
    from candidates import detect_candidates
    rng = np.random.default_rng(20260927)
    days = [A for A in mnq.load_real() if pd.Timestamp(A["date"]).weekday() <= 3]
    ES = es_days(); byc, rth = nq_rth_by_contract()
    front = rth.groupby(["ds", "contract"]).volume.sum().reset_index().sort_values("volume").groupby("ds").last().contract
    rows = []
    for k, A in enumerate(days):
        D = A["date"]; kc = front.get(D)
        if kc is None: continue
        g = byc[kc]; sess = sorted(set(g.ds)); prior = [s for s in sess if s < D][-3:]
        hist = g[g.ds.isin(prior + [D])]
        for c in detect_candidates(A, D, "MNQ", window_end=CUT):
            f = c.features; j = f["minutes_after_open"]; i = j + 1; side = 1 if c.direction == "long" else -1
            if i > 90 or np.isnan(A["open"][i]): continue
            lvl = c.level; bi = ORN + f["bars_to_break"]; fill = A["open"][i] + TICK * side
            cut = pd.Timestamp(D + " 09:30", tz="America/New_York") + pd.Timedelta(minutes=j + 1)
            r = dict(date=D, k=k, i=i, j=j, side=side, grade_hint=c.grade_hint,
                     depth=pen_ticks(A, side, lvl, bi, j), htf=htf_agree(hist, cut, A["close"][j], side),
                     rs=rs_signed(A, ES.get(D), j, side), d_wick=(fill - c.stop) * side, d_eng=(fill - lvl) * side)
            for s in ("wick", "eng"):
                dd = r["d_" + s]
                r["R_" + s] = mnq.trade(A, i, side, dd, CUT, j, "2R")[0] if dd >= 2 * TICK else np.nan
            rows.append(r)
    T = pd.DataFrame(rows)
    rs_cut = float(T.rs.quantile(2 / 3))
    T["deep"] = T.depth > DEPTH_TICKS; T["htf3"] = T.htf >= 3; T["rs_top"] = T.rs > rs_cut
    T["nctx"] = [n_ctx(a, b, c) for a, b, c in zip(T.deep, T.htf3, T.rs_top)]; T["on"] = T.nctx >= 2
    T["h1"] = T.date < MID
    # day-shuffle: same minute/side/stop-dist replayed on a random other session
    NS = 200; SH = {s: np.full((NS, len(T)), np.nan) for s in ("wick", "eng")}
    rec = T.to_dict("records")
    for n in range(NS):
        for q, t in enumerate(rec):
            while True:
                kk = int(rng.integers(len(days)))
                if kk != t["k"] and not np.isnan(days[kk]["open"][t["i"]]): break
            for s in ("wick", "eng"):
                if not np.isnan(t["R_" + s]):
                    SH[s][n, q] = mnq.trade(days[kk], t["i"], t["side"], t["d_" + s], CUT, t["j"], "2R")[0]
        if n % 50 == 0: print("shuffle", n, flush=True)
    out = dict(n_signals=len(T), n_days=int(T.date.nunique()), rs_cut_pct=rs_cut, split=MID,
               ctx_rate={c: float(T[c].mean()) for c in ("deep", "htf3", "rs_top", "on")},
               nctx_hist={str(v): int((T.nctx == v).sum()) for v in range(4)}, res={})
    for s in ("wick", "eng"):
        m = T["R_" + s].notna().to_numpy(); R = T["R_" + s].to_numpy(); on = T.on.to_numpy(); h1 = T.h1.to_numpy()
        a, b = m & on, m & ~on; sh = SH[s]
        obs = R[a].mean() - R[b].mean(); shd = np.nanmean(sh[:, a], 1) - np.nanmean(sh[:, b], 1)
        perm = [(lambda p: R[m][p].mean() - R[m][~p].mean())(rng.permutation(on[m])) for _ in range(5000)]
        res = dict(n_on=int(a.sum()), n_off=int(b.sum()), R_on=float(R[a].mean()), R_off=float(R[b].mean()), diff=float(obs),
                   p_shuffle_diff=float((shd >= obs).mean()), p_shuffle_on=float((np.nanmean(sh[:, a], 1) >= R[a].mean()).mean()),
                   p_labelperm_diff=float((np.array(perm) >= obs).mean()),
                   H1=dict(n_on=int((a & h1).sum()), R_on=float(R[a & h1].mean()), R_off=float(R[b & h1].mean())),
                   H2=dict(n_on=int((a & ~h1).sum()), R_on=float(R[a & ~h1].mean()), R_off=float(R[b & ~h1].mean())),
                   by_nctx={str(v): [int((m & (T.nctx == v)).sum()), float(np.nanmean(R[m & (T.nctx == v).to_numpy()]))] for v in range(4)},
                   by_ctx={c: [float(np.nanmean(R[m & T[c].to_numpy()])), float(np.nanmean(R[m & ~T[c].to_numpy()]))] for c in ("deep", "htf3", "rs_top")},
                   all_R=float(R[m].mean()))
        out["res"][s] = res
    e = out["res"]["eng"]
    out["PASS"] = bool(e["R_on"] >= 0.20 and e["H1"]["R_on"] > 0 and e["H2"]["R_on"] > 0 and e["p_shuffle_diff"] < 0.05)
    json.dump(out, open("results.json", "w"), indent=1)
    T.to_csv("signals.csv", index=False)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
