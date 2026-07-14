"""C10 robustness check on candidate tier-v2 configs.

Half-split (time), stop-green variant, direction split, monthly P&L,
day-level max drawdown, symbol concentration. Guards against the sweep's
in-sample selection (3072 configs) crowning a fluke.

Usage: py -3.13 research/c10_robustness.py [charts.json]
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "research" / "c1_off_charts.json"
NEWS = set(json.loads((ROOT / "news_days.json").read_text())["news_days"])


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


CANDIDATES = {
    "v1 baseline  S>=4+ham max2+grn": dict(s_min=4, hammer=True, max_n=2, grn=True, skipchase=False, skipnews=False, reqqqqa=False),
    "v2 lead      S>=4 max2 skipchase skipnews": dict(s_min=4, hammer=False, max_n=2, grn=False, skipchase=True, skipnews=True, reqqqqa=False),
    "v2 +grn variant": dict(s_min=4, hammer=False, max_n=2, grn=True, skipchase=True, skipnews=True, reqqqqa=False),
    "v2 conservative +reqqqqA": dict(s_min=4, hammer=False, max_n=2, grn=False, skipchase=True, skipnews=True, reqqqqa=True),
    "v2 no-skipnews control": dict(s_min=4, hammer=False, max_n=2, grn=False, skipchase=True, skipnews=False, reqqqqa=False),
}


def take(recs, cfg):
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    taken = []
    for day in sorted(byday):
        if cfg["skipnews"] and day in NEWS:
            continue
        rs = sorted(byday[day], key=lambda r: r["candles"][r["entry_i"]]["t"])
        n = pnl = 0
        for r in rs:
            if n >= cfg["max_n"] or (cfg["grn"] and pnl > 0):
                break
            s = s_score(r)
            if s is None or s < cfg["s_min"]:
                continue
            if cfg["hammer"] and not is_hammer(r):
                continue
            if cfg["skipchase"] and "[chase]" in r["reason"]:
                continue
            if cfg["reqqqqa"] and "[qqqA]" not in r["reason"]:
                continue
            n += 1; pnl += r["pnl"]; taken.append(r)
    return taken


def stats(tk):
    n = len(tk)
    if not n:
        return "0 tr"
    w = sum(1 for r in tk if r["outcome"] == "win")
    pnl = sum(r["pnl"] for r in tk)
    return f"{n:>3} tr  {w / n * 100:5.1f}%W  ${pnl:>8,.0f}"


def main():
    recs = [r for r in json.load(open(CHARTS)) if not r["alert_only"]]
    days = sorted({r["day"] for r in recs})
    mid = days[len(days) // 2]
    print(f"# C10 robustness — {CHARTS.name}, {len(days)} sessions, split at {mid}")
    for name, cfg in CANDIDATES.items():
        tk = take(recs, cfg)
        h1 = [r for r in tk if r["day"] < mid]
        h2 = [r for r in tk if r["day"] >= mid]
        # day-level equity + max drawdown
        bd = defaultdict(float)
        for r in tk:
            bd[r["day"]] += r["pnl"]
        eq = peak = mdd = 0.0
        for d in sorted(bd):
            eq += bd[d]
            peak = max(peak, eq)
            mdd = min(mdd, eq - peak)
        calls = [r for r in tk if r["direction"] == "call"]
        puts = [r for r in tk if r["direction"] == "put"]
        sym = defaultdict(float)
        for r in tk:
            sym[r["symbol"]] += r["pnl"]
        top3 = sorted(sym.items(), key=lambda kv: -kv[1])[:3]
        tot = sum(r["pnl"] for r in tk) or 1
        print(f"\n## {name}")
        print(f"  full : {stats(tk)}   maxDD ${mdd:,.0f}")
        print(f"  H1   : {stats(h1)}")
        print(f"  H2   : {stats(h2)}")
        print(f"  calls: {stats(calls)}")
        print(f"  puts : {stats(puts)}")
        print(f"  top3 sym: {', '.join(f'{s} ${p:,.0f}' for s, p in top3)}"
              f"  (top3 = {sum(p for _, p in top3) / tot * 100:.0f}% of P&L)")
        mo = defaultdict(float)
        for r in tk:
            mo[r["day"][:7]] += r["pnl"]
        neg = [m for m in sorted(mo) if mo[m] < 0]
        print(f"  months neg: {len(neg)}/{len(mo)} {neg}")


if __name__ == "__main__":
    main()
