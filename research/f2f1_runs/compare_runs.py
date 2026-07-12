"""Compare two backtest_charts_12mo.json snapshots: full-pop, take-tier, S-dist.

Usage: py -3.13 compare_runs.py baseline.json variant.json [labelA labelB]
Tier = S>=4 + hammer entry candle, max 2/day, stop when green (analyze_aplus).
"""
import json
import re
import sys
from collections import Counter, defaultdict


def load(path):
    return [r for r in json.load(open(path)) if not r["alert_only"]]


def s_score(rec):
    m = re.search(r" S(\d+)", rec["reason"])
    return int(m.group(1)) if m else None


def is_hammer(rec):
    c = rec["candles"][rec["entry_i"]]
    body = abs(c["c"] - c["o"])
    rng = c["h"] - c["l"]
    if rng == 0:
        return False
    if rec["direction"] == "call":
        return min(c["o"], c["c"]) - c["l"] >= body and c["c"] >= c["l"] + 0.5 * rng
    return c["h"] - max(c["o"], c["c"]) >= body and c["c"] <= c["h"] - 0.5 * rng


def pnl_of(rec):
    # rec["pnl"] is authoritative (ladder exits aren't fixed +-R amounts)
    return rec["pnl"]


def stats(recs):
    w = sum(1 for r in recs if r["outcome"] == "win")
    l = sum(1 for r in recs if r["outcome"] == "loss")
    pnl = sum(pnl_of(r) for r in recs)
    wr = w / (w + l) * 100 if w + l else 0
    return len(recs), wr, pnl


def tier_sim(recs, min_s=4, max_n=2):
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
            p = pnl_of(r)
            taken += 1; n += 1; pnl_day += p; tot += p
            w += r["outcome"] == "win"
    wr = w / n * 100 if n else 0
    return n, wr, tot


def report(label, recs):
    n, wr, pnl = stats(recs)
    tn, twr, tpnl = tier_sim(recs)
    print(f"{label}: full-pop {n} tr {wr:.1f}%W ${pnl:,.0f} | "
          f"tier {tn} tr {twr:.1f}%W ${tpnl:,.0f}/yr (${tpnl/12:,.0f}/mo)")
    bnr = [r for r in recs if r["setup"] == "break_and_retest"]
    dist = Counter(s_score(r) for r in bnr)
    print(f"  B&R S-dist ({len(bnr)} tr): "
          + "  ".join(f"S{s}:{dist[s]}" for s in sorted(d for d in dist if d is not None)))
    # stop width distribution on B&R
    widths = sorted(abs(r["entry"] - r["stop"]) / r["entry"] * 100 for r in bnr)
    if widths:
        med = widths[len(widths) // 2]
        print(f"  B&R stop width %: median {med:.2f}  p25 {widths[len(widths)//4]:.2f}  p75 {widths[3*len(widths)//4]:.2f}")


def split(label, recs, pred):
    a = [r for r in recs if pred(r)]
    b = [r for r in recs if not pred(r)]
    for tag, grp in ((f"{label}=YES", a), (f"{label}=no ", b)):
        if grp:
            n, wr, pnl = stats(grp)
            print(f"    {tag}: {n} tr {wr:.1f}%W ${pnl:,.0f}")


def extra_splits(recs):
    bnr = [r for r in recs if r["setup"] == "break_and_retest"]
    tagged = [r for r in bnr if "[qqqA]" in r["reason"] or "[qqqX]" in r["reason"]]
    if tagged:
        print(f"  F4 QQQ Rule-4 alignment (PD/PM key-level break, {len(tagged)} tagged):")
        split("qqqA", tagged, lambda r: "[qqqA]" in r["reason"])
    hodlod = [r for r in bnr if " above HOD " in r["reason"] or " below LOD " in r["reason"]]
    if hodlod:
        print(f"  F3 HOD/LOD setup standalone:")
        n, wr, pnl = stats(hodlod)
        print(f"    {n} tr {wr:.1f}%W ${pnl:,.0f}")
    scaled = [r for r in recs if r.get("scaled")]
    if scaled:
        print(f"  F1 ladder: {len(scaled)}/{len(recs)} trades scaled at HOD/LOD")


if __name__ == "__main__":
    a, b = sys.argv[1], sys.argv[2]
    la = sys.argv[3] if len(sys.argv) > 3 else "baseline"
    lb = sys.argv[4] if len(sys.argv) > 4 else "variant"
    ra, rb = load(a), load(b)
    report(la, ra)
    extra_splits(ra)
    report(lb, rb)
    extra_splits(rb)
