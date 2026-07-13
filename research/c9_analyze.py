"""C9 analyzer: full-pop + tier stats for the three real backtest arms."""
import json, re
from collections import defaultdict, Counter

ARMS = [
    ("current de-martingaled", "research/c9_baseline_charts.json"),
    ("strict-spec",            "research/c9_strict_charts.json"),
    ("detector OFF",           "research/c9_off_charts.json"),
]


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


def stats(rs):
    n = len(rs)
    w = sum(1 for r in rs if r["outcome"] == "win")
    pnl = sum(r["pnl"] for r in rs)
    return n, (w / n * 100 if n else 0.0), pnl


def tier(recs):
    recs = [r for r in recs if not r["alert_only"]]
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    out = []
    for day, rs in byday.items():
        rs.sort(key=lambda r: r["candles"][r["entry_i"]]["t"])
        taken = pnl_day = 0
        for r in rs:
            if taken >= 2 or pnl_day > 0:
                break
            s = s_score(r)
            if s is None or s < 4 or not is_hammer(r):
                continue
            taken += 1; pnl_day += r["pnl"]; out.append(r)
    return out


print("# C9 real-backtest A/B (backtest_12mo.py 365, Polygon cache, $1k flat risk)\n")
print(f"{'arm':24} | {'full-pop tr/win%/P&L':>30} | {'re84 tr/win%/P&L':>26} | {'tier tr/win%/P&L':>24}")
print("-" * 115)
rows = []
for name, path in ARMS:
    d = json.load(open(path))
    traded = [r for r in d if not r["alert_only"]]
    re84 = [r for r in traded if r["setup"] == "reentry_84_rule"]
    fn, fw, fp = stats(traded)
    rn, rw, rp = stats(re84)
    tn, tw, tp = stats(tier(traded))
    rows.append((name, fn, fw, fp, rn, rw, rp, tn, tw, tp))
    print(f"{name:24} | {fn:>4} {fw:>5.1f}% ${fp:>10,.0f} | {rn:>3} {rw:>5.1f}% ${rp:>8,.0f} | {tn:>3} {tw:>5.1f}% ${tp:>8,.0f}")

off_fp = rows[2][3]
print("\n## Full-pop delta vs detector OFF")
for name, fn, fw, fp, *_ in rows:
    print(f"  {name:24} ${fp-off_fp:>+9,.0f}/yr")
