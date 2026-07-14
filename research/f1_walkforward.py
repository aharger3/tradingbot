"""F1 walk-forward validation of tier v2 + every C10 flag choice.

Data constraint (honest): the repo has exactly ONE 12mo intraday window
(research/c1_off_charts.json, 2025-07-14..2026-07-10, 222 sessions, 671 traded).
A true rolling train-12mo/test-3mo needs ~24mo+ of data -> impossible here.
This script does the honest version:

  1. Leave-one-quarter-out (LOQO) walk-forward of the C10 SELECTION PROCESS:
     re-run the full 3,072-config tier sweep on 3 quarters (train ~9.7mo),
     select the winner by C10's stated criterion (WR>=50%, min-trades scaled
     from >=20/yr, max $), evaluate it on the held-out quarter. 4 folds;
     fold 4 (train=Q1-3, test=Q4) is the only PURE forward fold. Pooled
     held-out trades = the anti-selection-bias OOS estimate.
  2. Fixed tier-v2 stability: per-quarter / per-month / H1-H2 tables.
  3. Per-flag sign-stability: for every C10 decision, v2 vs v2-with-that-
     lever-flipped, per quarter -> does the chosen direction win OOS-ish?
  4. C6 whitelist cross-half validation (select on H1, test H2; reverse).
  5. C7 weekday effect per half.
  6. RULE84_STRICT: the 4 strict re-entries listed (n too small to validate).
  7. OOS win-rate estimate + Wilson 95% CI vs the 55% RoR threshold (D3).

Usage: py -3.13 research/f1_walkforward.py
"""
import itertools
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 guard

ROOT = Path(__file__).resolve().parents[1]
CHARTS = ROOT / "research" / "c1_off_charts.json"
STRICT = ROOT / "research" / "c9_strict_charts.json"
NEWS = set(json.loads((ROOT / "news_days.json").read_text())["news_days"])

WL12 = {"AMD", "AMZN", "COIN", "GOOGL", "INTC", "IREN",
        "NFLX", "NVDA", "ORCL", "PLTR", "QQQ", "UBER"}  # C6 proposal


def s_score(rec):
    m = re.search(r" S(\d+)", rec["reason"])
    return int(m.group(1)) if m else None


def is_hammer(rec):
    c = rec["candles"][rec["entry_i"]]
    body = abs(c["c"] - c["o"]); rng = c["h"] - c["l"]
    if rng == 0:
        return False
    if rec["direction"] == "call":
        return min(c["o"], c["c"]) - c["l"] >= body and c["c"] >= c["l"] + 0.5 * rng
    return c["h"] - max(c["o"], c["c"]) >= body and c["c"] <= c["h"] - 0.5 * rng


def entry_t(rec):
    return rec["candles"][rec["entry_i"]]["t"]


def tier_take(recs, s_min=4, hammer_req=False, max_n=2, stop_green=False,
              skip_chase=True, cutoff=None, skip_news=True, symbols="all24",
              s_formula="base", require_qqqa=False):
    """Return the list of taken trade records (chronological within day).
    Defaults = tier v2. Mechanics verbatim from c10_tier_sweep.tier_sim."""
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    taken = []
    for day in sorted(byday):
        if skip_news and day in NEWS:
            continue
        rs = sorted(byday[day], key=entry_t)
        n = pnl_day = 0
        for r in rs:
            if n >= max_n or (stop_green and pnl_day > 0):
                break
            if symbols == "wl12" and r["symbol"] not in WL12:
                continue
            if isinstance(symbols, (set, frozenset)) and r["symbol"] not in symbols:
                continue
            if cutoff and entry_t(r) >= cutoff:
                continue
            s = s_score(r)
            if s is None:
                continue
            if s_formula == "nodisp+1" and "[nodisp]" in r["reason"]:
                s += 1
            if s < s_min:
                continue
            if hammer_req and not is_hammer(r):
                continue
            if skip_chase and "[chase]" in r["reason"]:
                continue
            if require_qqqa and "[qqqA]" not in r["reason"]:
                continue
            n += 1; pnl_day += r["pnl"]; taken.append(r)
    return taken


def stats(tk):
    n = len(tk)
    w = sum(1 for r in tk if r["outcome"] == "win")
    pnl = sum(r["pnl"] for r in tk)
    return n, w, (w / n * 100 if n else 0.0), pnl


def fstats(tk):
    n, w, wr, pnl = stats(tk)
    return f"{n:>3} tr {wr:5.1f}%W ${pnl:>8,.0f}"


def wilson(w, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 1.0
    p = w / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, ctr - hw), min(1.0, ctr + hw)


V1 = dict(s_min=4, hammer_req=True, max_n=2, stop_green=True, skip_chase=False,
          skip_news=False)
V2 = dict()  # tier_take defaults


# ---------------------------------------------------------------- sweep grid
GRID_COLS = ("s_min hammer max_n stopgrn skipchase cutoff skipnews symbols "
             "s_formula reqqqqA").split()
GRID = list(itertools.product(
    [3, 4, 5], [True, False], [1, 2, 3, 99], [True, False], [False, True],
    [None, "10:30"], [False, True], ["all24", "wl12"],
    ["base", "nodisp+1"], [False, True]))


def lever_str(g):
    d = dict(zip(GRID_COLS, g))
    return (f"S>={d['s_min']}" + ("+ham" if d["hammer"] else "")
            + f" max{d['max_n']}" + ("+grn" if d["stopgrn"] else "")
            + ("+skipchase" if d["skipchase"] else "")
            + (f"+cut{d['cutoff']}" if d["cutoff"] else "")
            + ("+skipnews" if d["skipnews"] else "")
            + (f"+{d['symbols']}" if d["symbols"] != "all24" else "")
            + ("+nodisp+1" if d["s_formula"] != "base" else "")
            + ("+reqqqqA" if d["reqqqqA"] else ""))


def take_g(recs, g):
    d = dict(zip(GRID_COLS, g))
    return tier_take(recs, s_min=d["s_min"], hammer_req=d["hammer"],
                     max_n=d["max_n"], stop_green=d["stopgrn"],
                     skip_chase=d["skipchase"], cutoff=d["cutoff"],
                     skip_news=d["skipnews"], symbols=d["symbols"],
                     s_formula=d["s_formula"], require_qqqa=d["reqqqqA"])


V2_G = (4, False, 2, False, True, None, True, "all24", "base", False)


def select_c10(train_recs, train_days_n):
    """C10's stated criterion on the train window: WR>=50%, trade count
    scaled from >=20/yr, rank by P&L. Returns (top5 list, qualifiers_n)."""
    min_tr = max(10, round(20 * train_days_n / 222))
    rows = []
    for g in GRID:
        tk = take_g(train_recs, g)
        n, w, wr, pnl = stats(tk)
        rows.append((g, n, wr, pnl))
    qual = [r for r in rows if r[2] >= 50 and r[1] >= min_tr]
    pool = qual if qual else rows
    top = sorted(pool, key=lambda r: -r[3])[:5]
    # v2's rank among qualifiers by P&L
    ranked = sorted(pool, key=lambda r: -r[3])
    v2_rank = next((i + 1 for i, r in enumerate(ranked) if r[0] == V2_G), None)
    return top, len(qual), min_tr, v2_rank


def main():
    recs = [r for r in json.load(open(CHARTS)) if not r["alert_only"]]
    days = sorted({r["day"] for r in recs})
    days_n = len(days)
    print(f"# F1 walk-forward — {CHARTS.name}, {days_n} sessions "
          f"{days[0]}..{days[-1]}, {len(recs)} traded")

    # sanity: v2 reproduces C10 headline
    v2_all = tier_take(recs)
    n, w, wr, pnl = stats(v2_all)
    print(f"\n## Sanity: v2 full-sample = {fstats(v2_all)} "
          f"(C10 said 156 / 50.6% / $81k)")

    # sanity 2: v2 tier identical on strict arm (tier no-op check)
    strict = [r for r in json.load(open(STRICT)) if not r["alert_only"]]
    print(f"   v2 on c9_strict arm  = {fstats(tier_take(strict))} "
          f"(must match — 84%% re-entries carry no S-score)")

    # ---- quarters: 4 contiguous session blocks
    qsz = (days_n + 3) // 4
    blocks = [days[i * qsz:(i + 1) * qsz] for i in range(4)]
    qname = [f"Q{i+1} {b[0]}..{b[-1]} ({len(b)}d)" for i, b in enumerate(blocks)]
    qset = [set(b) for b in blocks]

    # ============================================ 1. LOQO walk-forward
    print("\n" + "=" * 78)
    print("## 1. Leave-one-quarter-out walk-forward of the C10 selection process")
    print("   (fold 4 = train Q1-3 / test Q4 = the only PURE forward fold)")
    pooled_sel, pooled_v2 = [], []
    for k in range(4):
        test_days = qset[k]
        train = [r for r in recs if r["day"] not in test_days]
        test = [r for r in recs if r["day"] in test_days]
        tr_days_n = days_n - len(blocks[k])
        top, nqual, min_tr, v2_rank = select_c10(train, tr_days_n)
        g_sel, n_tr, wr_tr, pnl_tr = top[0]
        sel_test = take_g(test, g_sel)
        v2_test = take_g(test, V2_G)
        v2_train = take_g(train, V2_G)
        pooled_sel += sel_test
        pooled_v2 += v2_test
        print(f"\n### Fold {k+1}: test {qname[k]}  "
              f"(train {tr_days_n}d, {nqual} qualifiers @min {min_tr} tr)")
        print(f"  selected on train: {lever_str(g_sel)}")
        print(f"    train {n_tr:>3} tr {wr_tr:5.1f}%W ${pnl_tr:>8,.0f}"
              f"   ->  TEST {fstats(sel_test)}")
        print(f"  v2 fixed:          rank #{v2_rank} on train, "
              f"train {fstats(v2_train)}   ->  TEST {fstats(v2_test)}")
        print("  train top-5: " + " | ".join(
            f"{lever_str(g)} ({wr0:.1f}%W ${p0:,.0f})" for g, n0, wr0, p0 in top))

    print("\n### Pooled held-out (the OOS numbers)")
    for label, pool in (("selected-per-fold", pooled_sel), ("v2 fixed", pooled_v2)):
        n, w, wr, pnl = stats(pool)
        p, lo, hi = wilson(w, n)
        print(f"  {label:18}: {n:>3} tr  {wr:5.1f}%W  ${pnl:>8,.0f}"
              f"   Wilson95 [{lo*100:.1f}%, {hi*100:.1f}%]")
    print("  NOTE: v2-fixed pooled test == v2 full-sample (fixed rule, folds tile"
          " the year) — quasi-OOS only. 'selected-per-fold' is the honest"
          " anti-selection-bias estimate of the C10 process.")

    # ============================================ 2. v2 stability
    print("\n" + "=" * 78)
    print("## 2. Fixed tier-v2 stability (vs v1) per quarter / month")
    print(f"{'window':34} | {'v2':>28} | {'v1':>28}")
    v1_all = tier_take(recs, **V1)
    for i in range(4):
        v2q = [r for r in v2_all if r["day"] in qset[i]]
        v1q = [r for r in v1_all if r["day"] in qset[i]]
        print(f"{qname[i]:34} | {fstats(v2q):>28} | {fstats(v1q):>28}")
    mid = days[days_n // 2]
    for lbl, cond in (("H1", lambda d: d < mid), ("H2", lambda d: d >= mid)):
        v2h = [r for r in v2_all if cond(r["day"])]
        v1h = [r for r in v1_all if cond(r["day"])]
        print(f"{lbl + ' (split ' + mid + ')':34} | {fstats(v2h):>28} | {fstats(v1h):>28}")
    print("\n  per month (v2):")
    bymo = defaultdict(list)
    for r in v2_all:
        bymo[r["day"][:7]].append(r)
    for m in sorted(bymo):
        print(f"    {m}: {fstats(bymo[m])}")
    negmo = [m for m in bymo if sum(r['pnl'] for r in bymo[m]) < 0]
    print(f"  months negative: {len(negmo)}/{len(bymo)} {sorted(negmo)}")

    # ============================================ 3. per-flag sign stability
    print("\n" + "=" * 78)
    print("## 3. Per-flag OOS sign-stability: v2 vs v2-with-lever-flipped, per quarter")
    print("   Δ = v2 P&L − flipped P&L (positive = C10's choice wins in that window)")
    flips = [
        ("hammer req DROPPED (v1 had ON)", dict(hammer_req=True)),
        ("stop_after_win OFF", dict(stop_green=True)),
        ("skip-[chase] ON", dict(skip_chase=False)),
        ("skip-news ON", dict(skip_news=False)),
        ("cutoff 11:00 (vs 10:30 revert)", dict(cutoff="10:30")),
        ("C6 wl12 NOT shipped (all24)", dict(symbols="wl12")),
        ("require-[qqqA] NOT shipped", dict(require_qqqa=True)),
        ("nodisp+1 NOT shipped", dict(s_formula="nodisp+1")),
        ("S>=4 (vs S>=3)", dict(s_min=3)),
        ("S>=4 (vs S>=5)", dict(s_min=5)),
        ("max 2/day (vs 1)", dict(max_n=1)),
        ("max 2/day (vs 3)", dict(max_n=3)),
    ]
    print(f"{'lever (C10 choice)':34} {'Q1 Δ$':>9} {'Q2 Δ$':>9} {'Q3 Δ$':>9} "
          f"{'Q4 Δ$':>9} {'wins':>5}  {'full Δ$':>9} {'ΔW%':>6}")
    for name, kw in flips:
        alt_all = tier_take(recs, **kw)
        dq = []
        for i in range(4):
            v2p = sum(r["pnl"] for r in v2_all if r["day"] in qset[i])
            alp = sum(r["pnl"] for r in alt_all if r["day"] in qset[i])
            dq.append(v2p - alp)
        wins = sum(1 for d in dq if d > 0)
        n2, _, wr2, p2 = stats(v2_all)
        na, _, wra, pa = stats(alt_all)
        print(f"{name:34} {dq[0]:>+9,.0f} {dq[1]:>+9,.0f} {dq[2]:>+9,.0f} "
              f"{dq[3]:>+9,.0f} {wins:>4}/4  {p2-pa:>+9,.0f} {wr2-wra:>+6.1f}")
        if name.startswith("C6"):
            # extra: wl12 per-quarter stats (is the whitelist's edge stable?)
            for i in range(4):
                wq = [r for r in alt_all if r["day"] in qset[i]]
                v2q = [r for r in v2_all if r["day"] in qset[i]]
                print(f"    wl12 Q{i+1}: {fstats(wq):>26}   vs v2 {fstats(v2q):>26}")

    # ============================================ 4. C6 whitelist cross-half
    print("\n" + "=" * 78)
    print("## 4. C6 symbol whitelist — honest cross-half validation")
    print("   rule: whitelist = symbols with net-positive v2-tier P&L in TRAIN half;")
    print("   apply as tier symbol filter in the OTHER half.")
    h1d = set(d for d in days if d < mid); h2d = set(d for d in days if d >= mid)
    for tr_lbl, tr_days, te_lbl, te_days in (("H1", h1d, "H2", h2d),
                                             ("H2", h2d, "H1", h1d)):
        tr_take = [r for r in v2_all if r["day"] in tr_days]
        sym_pnl = defaultdict(float)
        for r in tr_take:
            sym_pnl[r["symbol"]] += r["pnl"]
        wl = frozenset(s for s, p in sym_pnl.items() if p > 0)
        te_recs = [r for r in recs if r["day"] in te_days]
        wl_test = tier_take(te_recs, symbols=wl)
        v2_test = tier_take(te_recs)
        print(f"\n  train {tr_lbl} -> whitelist ({len(wl)}): {', '.join(sorted(wl))}")
        print(f"  test {te_lbl} whitelisted: {fstats(wl_test)}")
        print(f"  test {te_lbl} v2 (all24):  {fstats(v2_test)}")
    # fixed WL12 halves
    print("\n  fixed C6 WL12 list per half (vs v2):")
    wl12_all = tier_take(recs, symbols="wl12")
    for lbl, dset in (("H1", h1d), ("H2", h2d)):
        wlh = [r for r in wl12_all if r["day"] in dset]
        v2h = [r for r in v2_all if r["day"] in dset]
        print(f"    {lbl}: wl12 {fstats(wlh):>26}   vs v2 {fstats(v2h):>26}")

    # ============================================ 5. C7 weekday per half
    print("\n" + "=" * 78)
    print("## 5. C7 weekday effect inside v2, per half (stability check)")
    import datetime as dt
    wd = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    for lbl, cond in (("H1", lambda d: d < mid), ("H2", lambda d: d >= mid)):
        row = []
        for i in range(5):
            tk = [r for r in v2_all if cond(r["day"])
                  and dt.date.fromisoformat(r["day"]).weekday() == i]
            n, w, wr0, p = stats(tk)
            row.append(f"{wd[i]} {n:>2}tr {wr0:4.0f}% ${p:>7,.0f}")
        print(f"  {lbl}: " + " | ".join(row))

    # ============================================ 6. RULE84_STRICT
    print("\n" + "=" * 78)
    print("## 6. RULE84_STRICT (default ON per C9/C10) — the 4 strict re-entries")
    re84 = [r for r in strict if r["setup"] == "reentry_84_rule"]
    for r in sorted(re84, key=lambda r: r["day"]):
        print(f"  {r['day']} {r['symbol']:5} {r['direction']:4} "
              f"{r['outcome']:4} ${r['pnl']:>8,.0f}")
    n, w, wr0, p = stats(re84)
    pp, lo, hi = wilson(w, n)
    print(f"  total: {n} tr {wr0:.0f}%W ${p:,.0f}  Wilson95 [{lo*100:.0f}%, {hi*100:.0f}%]"
          f"  — all in H2; tier no-op (no S-score)")

    # ============================================ 7. OOS estimate vs 55%
    print("\n" + "=" * 78)
    print("## 7. OOS win-rate estimate vs the 55% RoR threshold (D3)")
    n, w, wr0, pnl = stats(pooled_sel)
    p, lo, hi = wilson(w, n)
    print(f"  walk-forward selected-config pooled: {n} tr, {wr0:.1f}%W, "
          f"Wilson95 [{lo*100:.1f}%, {hi*100:.1f}%], ${pnl:,.0f}")
    n2, w2, wr2, pnl2 = stats(v2_all)
    p2, lo2, hi2 = wilson(w2, n2)
    print(f"  v2 fixed full-sample (in-sample):    {n2} tr, {wr2:.1f}%W, "
          f"Wilson95 [{lo2*100:.1f}%, {hi2*100:.1f}%], ${pnl2:,.0f}")
    qwr = []
    for i in range(4):
        qq = [r for r in v2_all if r["day"] in qset[i]]
        nn, ww, wwr, _ = stats(qq)
        qwr.append(wwr)
    print(f"  v2 per-quarter WR: {['%.1f' % x for x in qwr]}  "
          f"(worst {min(qwr):.1f}%)")
    print(f"  55%% threshold: in Wilson95? "
          f"selected: {'YES' if lo <= 0.55 <= hi else ('below' if hi < 0.55 else 'above')}; "
          f"v2: {'YES' if lo2 <= 0.55 <= hi2 else ('below' if hi2 < 0.55 else 'above')}")


if __name__ == "__main__":
    main()
