"""C4 — puts problem A/B/C decision sim.

Three arms on the clean 12mo baseline (research/c1_off_charts.json,
866 signals / 671 traded / 78 tier):
  (a) puts off entirely
  (b) puts only when QQQ-aligned bearish ([qqqA] on the put)
  (c) status quo

Full-pop AND S>=4+[hammer] tier (max 2/day, stop-when-green) per arm.
Tier sim refuses filtered puts at the gate -> freed slots go to later
signals that day (same mechanics as c3_tag_split skip_tags).

Also: puts split by QQQ alignment, by grade, by symbol — WHY puts lose.
Cross-check of the -$21k/24mo synthesis figure vs current 12mo baseline.

Usage: python research/c4_puts_sim.py   (cwd = tradingbot)
"""
import json, re
from collections import defaultdict

CHARTS = "research/c1_off_charts.json"


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


def tier_sim(recs, allow):
    """S>=4+hammer tier, max 2/day, stop-when-green. allow(rec) -> bool
    refuses arm-filtered signals at the gate (slot freed for next signal)."""
    recs = [r for r in recs if not r["alert_only"]]
    byday = defaultdict(list)
    for r in recs:
        byday[r["day"]].append(r)
    tot = w = n = 0
    taken = []
    for day, rs in byday.items():
        rs.sort(key=lambda r: r["candles"][r["entry_i"]]["t"])
        k = pnl_day = 0
        for r in rs:
            if k >= 2 or pnl_day > 0:
                break
            s = s_score(r)
            if s is None or s < 4 or not is_hammer(r):
                continue
            if not allow(r):
                continue
            k += 1; n += 1; pnl_day += r["pnl"]; tot += r["pnl"]
            w += r["outcome"] == "win"
            taken.append(r)
    wr = w / n * 100 if n else 0.0
    return n, wr, tot, taken


ARMS = [
    ("(c) status quo", lambda r: True),
    ("(a) puts off entirely", lambda r: r["direction"] != "put"),
    ("(b) puts only if [qqqA]", lambda r: r["direction"] != "put" or "[qqqA]" in r["reason"]),
]


def row(label, sub):
    n, w, l, p, wr = gstats(sub)
    print(f"{label:34} {n:>6} {w:>4} {l:>4} {wr:>5.1f}% ${p:>9,.0f}")
    return n, w, l, p, wr


def main():
    recs = json.load(open(CHARTS))
    traded = [r for r in recs if not r["alert_only"]]

    print("# C4 — puts A/B/C (12mo baseline, c1_off_charts.json)")
    n, w, l, p, wr = gstats(recs)
    print(f"Baseline full-pop: {n} traded  {wr:.1f}%W  ${p:,.0f}\n")

    # --- cross-check the -$21k/24mo figure on current 12mo ---
    print("## Direction split — full population")
    print(f"{'group':34} {'trades':>6} {'W':>4} {'L':>4} {'win%':>6} {'P&L':>10}")
    calls = [r for r in traded if r["direction"] == "call"]
    puts = [r for r in traded if r["direction"] == "put"]
    row("calls", calls)
    prow = row("puts", puts)
    print()

    # --- WHY puts lose: QQQ alignment split ---
    print("## Puts by QQQ alignment — full population")
    print(f"{'group':34} {'trades':>6} {'W':>4} {'L':>4} {'win%':>6} {'P&L':>10}")
    pa = [r for r in puts if "[qqqA]" in r["reason"]]
    px = [r for r in puts if "[qqqX]" in r["reason"]]
    po = [r for r in puts if "[qqqA]" not in r["reason"] and "[qqqX]" not in r["reason"]]
    row("puts [qqqA] (QQQ-aligned bearish)", pa)
    row("puts [qqqX] (counter-QQQ)", px)
    if po:
        row("puts no-qqq-tag", po)
    # calls mirror for context
    ca = [r for r in calls if "[qqqA]" in r["reason"]]
    cx = [r for r in calls if "[qqqX]" in r["reason"]]
    row("calls [qqqA] (context)", ca)
    row("calls [qqqX] (context)", cx)
    print()

    # --- puts by grade ---
    print("## Puts by grade — full population")
    print(f"{'group':34} {'trades':>6} {'W':>4} {'L':>4} {'win%':>6} {'P&L':>10}")
    for g in ["A+", "A", "B"]:
        row(f"puts grade {g}", [r for r in puts if r["grade"] == g])
    print()

    # --- puts by symbol (sorted by P&L, only |P&L|>1k or n>=10) ---
    print("## Puts by symbol — full population (|P&L|>$2k or n>=15)")
    print(f"{'group':34} {'trades':>6} {'W':>4} {'L':>4} {'win%':>6} {'P&L':>10}")
    bysym = defaultdict(list)
    for r in puts:
        bysym[r["symbol"]].append(r)
    stats = {s: gstats(v) for s, v in bysym.items()}
    for s in sorted(bysym, key=lambda s: stats[s][3]):
        if abs(stats[s][3]) > 2000 or stats[s][0] >= 15:
            row(f"puts {s}", bysym[s])
    print()

    # --- the three arms ---
    print("## Arms — full population")
    print(f"{'arm':34} {'trades':>6} {'W':>4} {'L':>4} {'win%':>6} {'P&L':>10}")
    for label, allow in ARMS:
        row(label, [r for r in traded if allow(r)])
    print()

    print("## Arms — tier (S>=4+[hammer], max 2/day, stop-green)")
    print(f"{'arm':34} {'tier tr':>7} {'win%':>6} {'$/yr':>10}  puts-in-tier")
    for label, allow in ARMS:
        tn, twr, tp, taken = tier_sim(recs, allow)
        tputs = [r for r in taken if r["direction"] == "put"]
        pw = sum(1 for r in tputs if r["outcome"] == "win")
        pl = sum(1 for r in tputs if r["outcome"] == "loss")
        pp = sum(r["pnl"] for r in tputs)
        print(f"{label:34} {tn:>7} {twr:>5.1f}% ${tp:>9,.0f}  {len(tputs)} tr {pw}W/{pl}L ${pp:,.0f}")
    print()

    # --- within-tier puts detail for status quo ---
    _, _, _, taken = tier_sim(recs, lambda r: True)
    tputs = [r for r in taken if r["direction"] == "put"]
    print("## Status-quo tier puts, QQQ split")
    for lbl, sub in [("tier puts [qqqA]", [r for r in tputs if "[qqqA]" in r["reason"]]),
                     ("tier puts [qqqX]", [r for r in tputs if "[qqqX]" in r["reason"]])]:
        w2 = sum(1 for r in sub if r["outcome"] == "win")
        l2 = sum(1 for r in sub if r["outcome"] == "loss")
        p2 = sum(r["pnl"] for r in sub)
        wr2 = w2 / (w2 + l2) * 100 if (w2 + l2) else 0.0
        print(f"{lbl:34} {len(sub):>6} {w2:>4} {l2:>4} {wr2:>5.1f}% ${p2:>9,.0f}")


if __name__ == "__main__":
    main()
