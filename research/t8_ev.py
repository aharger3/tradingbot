"""EV per trade, in R, for the omen-5.0 two-year run -- and what it survives.

Reads research/t8_rows.json (every trade the T8 replay produced) and reports
expectancy per bucket, the shape of the R distribution behind it, and how much
of that expectancy is carried by a handful of outsized runners. An EV that
collapses when the top 1% of trades is removed is a tail, not an edge.

Baseline for comparison: backtest_metrics_full.json -- 2024-07-31..2026-07-31,
24 symbols, 1,289 counted trades, 38.0% win rate, $185,000 net at $1k risk =
+0.144R per trade. Blind 2R exits, wick-based stops, no pivot levels, and (per
the BacktestRunner._route defect) none of the T11 gates.
"""
import json, os, sys, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == "research" \
    else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from universe import MAJOR_15, INDEX_POOL, OTHER_POOL

ROWS = json.load(open(os.path.join(ROOT, "research", "t8_rows.json")))
OUT = os.path.join(ROOT, "research", "t8_ev.md")

BASE_N, BASE_WR, BASE_EV = 1289, 38.0, 0.144
POOLS = [("MAJOR_15", set(MAJOR_15)), ("INDEX_POOL", set(INDEX_POOL)), ("OTHER_POOL", set(OTHER_POOL))]
TIERS = ["S+", "S", "A", "C"]


def ev(rows):
    if not rows:
        return None
    rs = [r["r"] for r in rows]
    dec = [r for r in rows if r["outcome"] in ("win", "loss")]
    wr = 100.0 * sum(1 for r in dec if r["outcome"] == "win") / len(dec) if dec else None
    return dict(n=len(rs), ev=sum(rs) / len(rs), med=st.median(rs), wr=wr,
                best=max(rs), worst=min(rs), total=sum(rs))


def clipped_ev(rows, cap):
    rs = [min(r["r"], cap) for r in rows]
    return sum(rs) / len(rs) if rs else None


def trimmed_ev(rows, pct):
    """EV after dropping the top `pct`% of trades by R -- the tail-dependence test."""
    rs = sorted(r["r"] for r in rows)
    k = max(1, int(len(rs) * pct / 100.0))
    keep = rs[:-k]
    return (sum(keep) / len(keep) if keep else None), k


def line(label, s):
    if not s:
        return f"| {label} | 0 | -- | -- | -- | -- | -- |"
    wr = f"{s['wr']:.1f}%" if s["wr"] is not None else "--"
    return (f"| {label} | {s['n']} | {wr} | **{s['ev']:+.3f}R** | {s['med']:+.2f}R | "
            f"{s['best']:+.1f}R | {s['worst']:+.1f}R |")


HEAD = ("| | trades | win rate | EV/trade | median R | best | worst |\n"
        "|---|---|---|---|---|---|---|")

fired = [r for r in ROWS if r["status"] == "fired"]
traded = [r for r in ROWS if r["counted"]]
alerts = [r for r in fired if r["grade"] == "C"]

L = ["# T8 -- expectancy per trade, and what carries it\n"]
L.append("Every number is R at $1,000 risk (`pnl / 1000`). Win rate counts decided "
         "trades only; EV counts every trade including scratches.\n")

L.append("## Against the previous backtest\n")
L.append("| run | window | symbols | trades | win rate | EV/trade |")
L.append("|---|---|---|---|---|---|")
L.append(f"| `backtest_metrics_full.json` (blind 2R, wick stops, pre-pivot, T11 gates inert) "
         f"| 2024-07-31..2026-07-31 | 24 | {BASE_N} | {BASE_WR}% | **+{BASE_EV:.3f}R** |")
t = ev(traded)
L.append(f"| **omen-5.0 T8** (close stops, ladder B, pivots, T11 live) "
         f"| 2024-08-12..2026-08-11 | 29 | {t['n']} | {t['wr']:.1f}% | **{t['ev']:+.3f}R** |")
L.append("")
L.append(f"Delta: **{t['ev'] - BASE_EV:+.3f}R per trade**, "
         f"win rate **{t['wr'] - BASE_WR:+.1f} points**, on "
         f"{t['n'] - BASE_N:+d} trades over near-identical windows.\n")

L.append("## Expectancy by bucket\n")
L.append(HEAD)
L.append(line("all fired", ev(fired)))
L.append(line("**traded (A+/A/B)**", ev(traded)))
L.append(line("C alerts (not traded)", ev(alerts)))
L.append("| | | | | | | |")
for name, syms in POOLS:
    L.append(line(f"pool: {name}", ev([r for r in traded if r["symbol"] in syms])))
L.append("| | | | | | | |")
for tr in TIERS:
    L.append(line(f"tier: {tr}", ev([r for r in fired if r["tier"] == tr])))
L.append("| | | | | | | |")
for s in sorted({r["setup"] for r in fired}):
    L.append(line(f"setup: {s}", ev([r for r in fired if r["setup"] == s])))
L.append("")

L.append("## Is it an edge or a tail?\n")
L.append("The ladder-B runner has no fixed R ceiling -- it exits at the first key level "
         "beyond the scale point, so a trade with a few-cent stop can return tens of R. "
         "That makes the mean sensitive to a handful of trades. Three ways of asking "
         "whether the expectancy survives without them:\n")
L.append("| view | traded EV | MAJOR_15 EV |")
L.append("|---|---|---|")
maj = [r for r in traded if r["symbol"] in set(MAJOR_15)]
L.append(f"| as measured | {ev(traded)['ev']:+.3f}R | {ev(maj)['ev']:+.3f}R |")
for cap in (2, 5, 10):
    L.append(f"| R capped at +{cap} | {clipped_ev(traded, cap):+.3f}R | {clipped_ev(maj, cap):+.3f}R |")
for pct in (1, 5):
    a, ka = trimmed_ev(traded, pct)
    b, kb = trimmed_ev(maj, pct)
    L.append(f"| top {pct}% of trades dropped ({ka} / {kb} trades) | {a:+.3f}R | {b:+.3f}R |")
L.append("")

rs = sorted((r["r"] for r in traded), reverse=True)
tot = sum(rs)
for pct in (1, 5, 10):
    k = max(1, int(len(rs) * pct / 100.0))
    L.append(f"- Top **{pct}%** of traded ({k} trades) carry **{100.0 * sum(rs[:k]) / tot:.0f}%** of total R.")
L.append(f"- Median traded trade: **{st.median([r['r'] for r in traded]):+.2f}R**. "
         f"Best: **{max(rs):+.1f}R**. Trades over +10R: **{sum(1 for x in rs if x > 10)}**.")
L.append("")

L.append("## Biggest winners (traded)\n")
L.append("| symbol | day | setup | tier | R |")
L.append("|---|---|---|---|---|")
for r in sorted(traded, key=lambda x: -x["r"])[:10]:
    L.append(f"| {r['symbol']} | {r['day']} | {r['setup']} | {r['tier']} | {r['r']:+.1f}R |")
L.append("")

open(OUT, "w").write("\n".join(L))
print("\n".join(L))
print("\nwrote", OUT)
