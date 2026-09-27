"""g-card-ux: which chart context separates Austin's S marks, and 3 card layouts.

1) marks study on research/agent_runs/eye1/s_trades.csv (266 graded marks):
   per-feature AUC S vs not-S with a 2000-shuffle permutation p; note-text
   keyword tally (time / levels / prior bars / higher timeframe).
2) renders layouts A (current), B (context: full session + prior-day H/L/C),
   C (grade card: zoomed break->retest + S-trait checklist) for replay
   candidates from the last sessions that have S/one-off candidates.
Paper only, read-only over bars on disk.
"""
import csv, json, math, re, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v3-eye2-candidates"))
sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s07-data")

RNG = np.random.default_rng(7)


def auc(x, y):
    x, y = np.asarray(x, float), np.asarray(y, int)
    ok = ~np.isnan(x)
    x, y = x[ok], y[ok]
    r = np.argsort(np.argsort(x)) + 1.0
    # average ties
    for v in np.unique(x):
        m = x == v
        r[m] = r[m].mean()
    n1, n0 = y.sum(), (1 - y).sum()
    if n1 == 0 or n0 == 0:
        return float("nan"), 0
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0), int(ok.sum())


def perm_p(x, y, n=2000):
    a, _ = auc(x, y)
    y = np.asarray(y)
    hits = sum(abs(auc(x, RNG.permutation(y))[0] - 0.5) >= abs(a - 0.5) for _ in range(n))
    return (hits + 1) / (n + 1)


def num(v):
    try:
        f = float(v)
        return f if not math.isnan(f) else np.nan
    except (TypeError, ValueError):
        return np.nan


def study():
    rows = list(csv.DictReader(open(REPO / "research/agent_runs/eye1/s_trades.csv", encoding="utf-8")))
    y = [1 if r["grade"] == "S" else 0 for r in rows]
    feats = {
        "min_after_open": [num(r["min_after_open"]) for r in rows],
        "bars_break_to_sig": [num(r["bars_break_to_sig"]) for r in rows],
        "retest_depth_atr_abs": [abs(num(r["retest_depth_atr"])) for r in rows],
        "closed_thru": [num(r["closed_thru"]) for r in rows],
        "trig_close_vs_lvl_atr": [num(r["trig_close_vs_lvl_atr"]) for r in rows],
        "gap_with": [num(r["gap_with"]) for r in rows],
        "disp_atr": [num(r["disp_atr"]) for r in rows],
        "vs_vwap_atr": [num(r["vs_vwap_atr"]) for r in rows],
        "day_move_with": [num(r["day_move_with"]) for r in rows],
        "level_is_OR": [1.0 if "OR" in r["eng_level"] else (np.nan if not r["eng_level"] else 0.0) for r in rows],
        "level_is_prior_day": [1.0 if r["eng_level"] in ("PDH", "PDL", "PDC") else (np.nan if not r["eng_level"] else 0.0) for r in rows],
    }
    out = {}
    for k, x in feats.items():
        a, n = auc(x, y)
        out[k] = dict(auc=round(a, 3), n=n, p=round(perm_p(x, y), 4))
    # S-trait checklist score (the card's right panel), in-sample + H2 half only
    def score(r):
        s = 0
        s += num(r["min_after_open"]) <= 20
        s += num(r["bars_break_to_sig"]) <= 6
        s += abs(num(r["retest_depth_atr"])) <= 0.35
        s += num(r["closed_thru"]) == 0
        s += num(r["trig_close_vs_lvl_atr"]) >= 0.5
        s += num(r["gap_with"]) == 1
        return float(s)
    sc = [score(r) for r in rows]
    a, n = auc(sc, y)
    out["checklist_score"] = dict(auc=round(a, 3), n=n, p=round(perm_p(sc, y), 4))
    h2 = [i for i, r in enumerate(rows) if r["half"] == "H2"]
    a2, n2 = auc([sc[i] for i in h2], [y[i] for i in h2])
    out["checklist_score_H2"] = dict(auc=round(a2, 3), n=n2,
                                     p=round(perm_p([sc[i] for i in h2], [y[i] for i in h2]), 4))
    cats = {
        "time": r"\b(time|late|early|window|10:\d\d|9:\d\d|open)\b",
        "levels": r"\b(level|pdh|pdl|vwap|pivot|support|resist\w*|structure|orb|range|high|low)\b",
        "prior_bars": r"\b(candle\w*|wick\w*|displacement|price action|bars?|ugly|clean|strong|chop\w*)\b",
        "htf": r"(higher time ?frame|htf|\b5 ?m|\b15 ?m|daily|trend)",
    }
    notes = {"S": {c: 0 for c in cats}, "not_S": {c: 0 for c in cats}}
    n_notes = {"S": 0, "not_S": 0}
    for r in rows:
        t = (r.get("note") or "").lower()
        if not t or t.startswith("{"):
            continue
        g = "S" if r["grade"] == "S" else "not_S"
        n_notes[g] += 1
        for c, pat in cats.items():
            notes[g][c] += bool(re.search(pat, t))
    out["notes"] = dict(n=n_notes, hits=notes)
    out["counts"] = dict(S=sum(y), not_S=len(y) - sum(y))
    return out


def render():
    import candidates as eye2
    from omen_data import load_fut
    from eye_card.chart import Candidate, render_candidate_chart
    from eye_card.grade_card import render_grade_card
    import matplotlib.pyplot as plt
    # eye_runner imports eye_paper -> orb1m (untracked on main); mirror its two helpers
    def bars_from_day_array(A, up_to):
        out = []
        for i in range(up_to + 1):
            o = A["open"][i]
            if o != o:
                continue
            hh, mm = 9 + (30 + i) // 60, (30 + i) % 60
            out.append(dict(time=f"{hh:02d}:{mm:02d}:00", open=float(o), high=float(A["high"][i]),
                            low=float(A["low"][i]), close=float(A["close"][i])))
        return out

    def to_chart_candidate(c, cid):
        return Candidate(candidate_id=cid, symbol=c.instrument,
                         direction="LONG" if c.direction == "long" else "SHORT",
                         trigger_time=c.time.split("T")[1][:8], entry=c.entry, stop=c.stop,
                         targets=[c.target_1r, c.target_2r], level=c.level, level_label="ORB level",
                         setup=f"ORB break/retest ({c.grade_hint})",
                         or_high=c.features.get("or_high"), or_low=c.features.get("or_low"))

    full = load_fut("MNQ", "09:30", "16:00")
    days = sorted(full["date"].unique())
    prior = {}
    for i in range(1, len(days)):
        g = full[full["date"] == days[i - 1]]
        prior[str(days[i])] = dict(PDH=float(g["high"].max()), PDL=float(g["low"].min()),
                                   PDC=float(g["close"].iloc[-1]))
    early = full[full["ts"].dt.strftime("%H:%M") < "11:01"]
    picked = []
    for d in reversed(days[-40:]):
        g = early[early["date"] == d]
        A = eye2.day_arrays(g)
        cs = [c for c in eye2.detect_candidates(A, str(d), "MNQ") if c.grade_hint in ("S", "one-off")]
        for c in cs[:1]:
            picked.append((str(d), A, c))
        if len(picked) >= 3:
            break
    out_dir = HERE / "layouts"
    made = []
    for d, A, c in picked:
        j = c.features["minutes_after_open"]
        bars = bars_from_day_array(A, j)
        cc = to_chart_candidate(c, f"{d}-{j}")
        cc.extra = dict(c.features)
        tag = f"{d}_{cc.trigger_time[:5].replace(':', '')}_{c.grade_hint}"
        made.append(str(render_candidate_chart(cc, bars, out_dir / f"A_current_{tag}.png").name))
        # B: current chart + prior-day H/L/C + session open
        render_context(cc, bars, prior.get(d, {}), out_dir / f"B_context_{tag}.png")
        made.append(f"B_context_{tag}.png")
        made.append(str(render_grade_card(cc, bars, out_dir / f"C_grade_{tag}.png").name))
    return made


def render_context(cc, bars, pd_lv, path):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    from eye_card.chart import _bars_up_to
    w = _bars_up_to(bars, cc.trigger_time)
    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=150)
    for x, b in enumerate(w):
        col = "#f0a500" if b["time"] == cc.trigger_time else ("#1a9850" if b["close"] >= b["open"] else "#d73027")
        ax.plot([x, x], [b["low"], b["high"]], color=col, lw=1)
        lo, hi = sorted([b["open"], b["close"]])
        ax.add_patch(Rectangle((x - 0.3, lo), 0.6, max(hi - lo, 1e-6), color=col))
    lo_all = min(b["low"] for b in w); hi_all = max(b["high"] for b in w)
    pad = (hi_all - lo_all) * 0.6
    lines = [(cc.level, "ORB", "#4575b4", "-"), (w[0]["open"], "Open", "#777777", ":"),
             (cc.stop, "Stop", "#d73027", "--")] + [(t, f"T{i}", "#1a9850", ":") for i, t in enumerate(cc.targets, 1)]
    for k, v in pd_lv.items():
        if lo_all - pad <= v <= hi_all + pad:
            lines.append((v, k, "#7b3294", "-."))
    for yv, lab, col, st in lines:
        ax.axhline(yv, color=col, ls=st, lw=1)
        ax.text(len(w) - 0.5, yv, f" {lab} {yv:g}", color=col, fontsize=7.5, va="center")
    ax.axvspan(-0.5, 14.5, color="#4575b4", alpha=0.06)
    step = 5
    ax.set_xticks(range(0, len(w), step))
    ax.set_xticklabels([w[i]["time"][:5] for i in range(0, len(w), step)], fontsize=7.5)
    ax.set_xlim(-1, len(w) + 4)
    ax.set_title(f"{cc.symbol} {cc.direction} {cc.trigger_time[:5]} ET - context (prior day + open)", fontsize=10)
    ax.grid(alpha=0.15)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


if __name__ == "__main__":
    res = study()
    res["layouts"] = render()
    (HERE / "results.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
