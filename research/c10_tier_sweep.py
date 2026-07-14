"""C10 tier-definition grid sweep.

Sweeps the tier gate (what Austin actually trades) across every lever the
C-series measured, on the frozen 12mo baseline research/c1_off_charts.json
(24 symbols, 11:00 cutoff, news days included, 671 traded / 866 signals).
Tier mechanics (chronological take, max-N/day, stop-when-green) reused
verbatim from b4_analyze/c3_tag_split tier_sim.

Goal frame (Austin): 1-2 trades/day, 50%+ win rate, six-figure year.
Report shows the honest frontier: what this signal population can and
cannot deliver at $1k flat risk.

Usage: py -3.13 research/c10_tier_sweep.py
"""
import itertools
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTS = ROOT / "research" / "c1_off_charts.json"
NEWS = ROOT / "news_days.json"

WL12 = {"AMD", "AMZN", "COIN", "GOOGL", "INTC", "IREN",
        "NFLX", "NVDA", "ORCL", "PLTR", "QQQ", "UBER"}  # C6 proposal (overfit-flagged)


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


def tier_sim(recs, days_n, s_min, hammer_req, max_n, stop_green, skip_chase,
             cutoff, skip_news, news_set, symbols, s_formula, require_qqqa):
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    tot = w = n = 0
    for day, rs in byday.items():
        if skip_news and day in news_set:
            continue
        rs.sort(key=entry_t)
        taken = pnl_day = 0
        for r in rs:
            if taken >= max_n or (stop_green and pnl_day > 0):
                break
            if symbols == "wl12" and r["symbol"] not in WL12:
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
            taken += 1; n += 1
            pnl_day += r["pnl"]; tot += r["pnl"]
            w += r["outcome"] == "win"
    wr = w / n * 100 if n else 0.0
    return n, wr, tot, n / days_n


def main():
    recs = [r for r in json.load(open(CHARTS)) if not r["alert_only"]]
    news_set = set(json.loads(NEWS.read_text())["news_days"])
    days_n = len({r["day"] for r in recs})

    grid = list(itertools.product(
        [3, 4, 5],                 # s_min
        [True, False],             # hammer_req
        [1, 2, 3, 99],             # max_n
        [True, False],             # stop_green
        [False, True],             # skip_chase
        [None, "10:30"],           # cutoff
        [False, True],             # skip_news
        ["all24", "wl12"],         # symbols
        ["base", "nodisp+1"],      # s_formula
        [False, True],             # require_qqqa
    ))
    rows = []
    for g in grid:
        n, wr, pnl, tpd = tier_sim(recs, days_n, *g[:5], g[5], g[6], news_set, *g[7:])
        rows.append((*g, n, wr, pnl, tpd))

    cols = ("s_min hammer max_n stopgrn skipchase cutoff skipnews symbols "
            "s_formula reqqqqA tr wr pnl tpd").split()

    def fmt(r):
        d = dict(zip(cols, r))
        lever = (f"S>={d['s_min']}"
                 + ("+ham" if d["hammer"] else "")
                 + f" max{d['max_n']}"
                 + ("+grn" if d["stopgrn"] else "")
                 + ("+skipchase" if d["skipchase"] else "")
                 + (f"+cut{d['cutoff']}" if d["cutoff"] else "")
                 + ("+skipnews" if d["skipnews"] else "")
                 + (f"+{d['symbols']}" if d["symbols"] != "all24" else "")
                 + ("+nodisp+1" if d["s_formula"] != "base" else "")
                 + ("+reqqqqA" if d["reqqqqA"] else ""))
        return (f"{lever:64} {d['tr']:>4} tr  {d['tpd']:.2f}/day  "
                f"{d['wr']:5.1f}%W  ${d['pnl']:>8,.0f}/yr")

    def find(**kw):
        for r in rows:
            if all(dict(zip(cols, r))[k] == v for k, v in kw.items()):
                return r

    base = find(s_min=4, hammer=True, max_n=2, stopgrn=True, skipchase=False,
                cutoff=None, skipnews=False, symbols="all24",
                s_formula="base", reqqqqA=False)
    print(f"# C10 tier grid sweep — {len(rows)} configs, {days_n} sessions, $1k flat risk")
    print("\n## Baseline (current tier definition)")
    print(fmt(base))

    print("\n## A2-config tier approximation (cutoff 10:30 + skip-news on baseline tier)")
    print(fmt(find(s_min=4, hammer=True, max_n=2, stopgrn=True, skipchase=False,
                   cutoff="10:30", skipnews=True, symbols="all24",
                   s_formula="base", reqqqqA=False)))

    print("\n## One-lever-flip attribution around baseline")
    basekw = dict(s_min=4, hammer=True, max_n=2, stopgrn=True, skipchase=False,
                  cutoff=None, skipnews=False, symbols="all24",
                  s_formula="base", reqqqqA=False)
    flips = [("s_min", 3), ("s_min", 5), ("hammer", False), ("max_n", 1),
             ("max_n", 3), ("max_n", 99), ("stopgrn", False), ("skipchase", True),
             ("cutoff", "10:30"), ("skipnews", True), ("symbols", "wl12"),
             ("s_formula", "nodisp+1"), ("reqqqqA", True)]
    for k, v in flips:
        kw = dict(basekw); kw[k] = v
        print(fmt(find(**kw)))

    print("\n## Top 15 by $/yr (any win rate)")
    for r in sorted(rows, key=lambda r: -r[-2])[:15]:
        print(fmt(r))

    print("\n## Win rate >=50%, ranked by $/yr (top 15)")
    hits = [r for r in rows if r[-3] >= 50 and r[-4] >= 20]  # >=20 tr to kill tiny-n flukes
    for r in sorted(hits, key=lambda r: -r[-2])[:15]:
        print(fmt(r))
    if not hits:
        print("(none with >=20 trades)")

    print("\n## Win rate >=50% AND >=0.5 trades/day, ranked by $/yr")
    hits2 = [r for r in rows if r[-3] >= 50 and r[-1] >= 0.5]
    for r in sorted(hits2, key=lambda r: -r[-2])[:10]:
        print(fmt(r))
    if not hits2:
        print("(NONE — population cannot deliver 50%W at 0.5+/day)")

    print("\n## 1+/day (>=233 tr), ranked by win rate")
    hits3 = [r for r in rows if r[-4] >= days_n]
    for r in sorted(hits3, key=lambda r: -r[-3])[:10]:
        print(fmt(r))
    if not hits3:
        print("(NONE — no tier config reaches 1 trade/day)")

    print("\n## Pareto frontier (win% vs $/yr, >=20 tr)")
    cand = sorted([r for r in rows if r[-4] >= 20], key=lambda r: (-r[-3], -r[-2]))
    frontier, best_pnl = [], -1e18
    for r in cand:
        if r[-2] > best_pnl:
            frontier.append(r); best_pnl = r[-2]
    for r in sorted(frontier, key=lambda r: -r[-2]):
        print(fmt(r))

    print("\n## Goal math ($1k flat risk, 2R target)")
    print("$/trade = $3k*W - $1k  ->  50%W = $500/tr; 42.3%W = $269/tr")
    print("Six figures needs: 200 tr/yr @50%W, or 372 tr/yr @42.3%W, or bigger risk unit (D-phase).")


if __name__ == "__main__":
    main()
