"""C2 FVG_RETEST A/B analyzer: full-pop traded + S>=4+hammer tier
for two backtest_charts.json snapshots (OFF vs ON).

Reuses c1_analyze.py / b4_analyze.py logic verbatim (gstats + tier_sim).
Usage: py -3.13 c2_analyze.py off.json on.json
"""
import json, re, sys
from collections import defaultdict

GRADES = ["A+", "A", "B", "C", "D"]


def load_all(path):
    return json.load(open(path))


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


def gstats(recs):
    counted = [r for r in recs if not r["alert_only"]]
    w = sum(1 for r in counted if r["outcome"] == "win")
    l = sum(1 for r in counted if r["outcome"] == "loss")
    pnl = sum(r["pnl"] for r in counted)
    wr = w / (w + l) * 100 if (w + l) else 0.0
    return len(counted), w, l, pnl, wr


def by_grade_table(recs):
    rows = {}
    for g in GRADES:
        gr = [r for r in recs if r["grade"] == g]
        if not gr:
            continue
        if g == "C":
            w = sum(1 for r in gr if r["outcome"] == "win")
            l = sum(1 for r in gr if r["outcome"] == "loss")
            pnl = sum(r["pnl"] for r in gr)
            wr = w / (w + l) * 100 if (w + l) else 0.0
            rows[g] = (len(gr), w, l, pnl, wr, "alert-only")
        else:
            n, w, l, pnl, wr = gstats(gr)
            rows[g] = (n, w, l, pnl, wr, "traded")
    return rows


def tier_sim(recs, min_s=4, max_n=2):
    recs = [r for r in recs if not r["alert_only"]]
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    tot = w = n = 0
    for day, rs in byday.items():
        rs.sort(key=lambda r: r["candles"][r["entry_i"]]["t"])
        taken = pnl_day = 0
        for r in rs:
            if taken >= max_n or pnl_day > 0:
                break
            s = s_score(r)
            if s is None or s < min_s or not is_hammer(r):
                continue
            taken += 1; n += 1; pnl_day += r["pnl"]; tot += r["pnl"]
            w += r["outcome"] == "win"
    wr = w / n * 100 if n else 0.0
    return n, wr, tot


def print_run(label, recs):
    n, w, l, pnl, wr = gstats(recs)
    print(f"\n=== {label} ===")
    print(f"Traded (A+/A/B): {n} tr  {w}W {l}L  {wr:.1f}%W  ${pnl:,.0f}")
    tn, twr, tpnl = tier_sim(recs)
    print(f"S>=4+hammer tier: {tn} tr  {twr:.1f}%W  ${tpnl:,.0f}/yr (${tpnl/12:,.0f}/mo)")
    print("By grade:")
    for g, (n, w, l, pnl, wr, kind) in by_grade_table(recs).items():
        print(f"  {g:2} | {n:4} tr | {w}W {l}L | {wr:5.1f}%W | ${pnl:>8,.0f} | {kind}")


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    ra, rb = load_all(a), load_all(b)
    print_run("FVG_RETEST OFF (baseline)", ra)
    print_run("FVG_RETEST ON", rb)
