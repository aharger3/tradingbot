"""G7.2 / share_props -- what Trade The Pool's share commission costs the book.

TTP commission (tradethepool.com, retrieved 2026-08-29 via review aggregators):
    $0.75 minimum per execution up to 150 shares, else $0.005/share.
Round trip = 2 executions.

1R = risk_dollars / stock_risk_per_share shares, where stock_risk = |entry-stop|.
Friction in R = round-trip commission $ / risk_dollars.
"""
import json, os, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "bt2y_trades.json")))
rows = d["trades"] if isinstance(d, dict) else d
meta = d.get("meta", {}) if isinstance(d, dict) else {}
RISK = float(meta.get("risk_dollars", 1000))

def exec_fee(shares):
    return max(0.75, 0.005 * shares) if shares > 150 else 0.75

fr = []
sh = []
for t in rows:
    if not t.get("traded"):
        continue
    sr = abs(float(t["entry"]) - float(t["stop"]))
    if sr <= 0:
        continue
    shares = RISK / sr
    sh.append(shares)
    fr.append(2 * exec_fee(shares) / RISK)

fr.sort(); sh.sort()
q = lambda a, p: a[int(p * (len(a) - 1))]
print(f"traded rows           {len(fr)}   1R = ${RISK:,.0f}")
print(f"shares/trade          p10 {q(sh,.10):8.0f}  median {q(sh,.50):8.0f}  p90 {q(sh,.90):8.0f}")
print(f"TTP round-trip comm R p10 {q(fr,.10):8.4f}  median {q(fr,.50):8.4f}  p90 {q(fr,.90):8.4f}  mean {statistics.mean(fr):.4f}")
print(f"as %% of the book's +0.5481R mean: {statistics.mean(fr)/0.5481*100:.1f}%")
for risk in (150, 250, 500):
    f = [2 * exec_fee(risk / abs(float(t['entry']) - float(t['stop']))) / risk
         for t in rows if t.get('traded') and abs(float(t['entry']) - float(t['stop'])) > 0]
    print(f"  at ${risk}/trade risk: mean {statistics.mean(f):.4f} R   median {statistics.median(f):.4f} R")
