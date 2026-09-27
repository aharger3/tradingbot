import pandas as p, numpy as n
d = p.read_csv("t02_ocr1m_trades.csv")
for s in ("MNQ", "MES"):
    x = d[d.sym == s]; g = x.groupby("v")
    print(s); print(p.DataFrame({"n": g.net.size(), "net": g.net.mean().round(3),
        "t": (g.net.mean() / (g.net.std() / n.sqrt(g.net.size()))).round(2),
        "h1": x[x.date < "2025-09-01"].groupby("v").net.mean().round(3),
        "h2": x[x.date >= "2025-09-01"].groupby("v").net.mean().round(3),
        "usd_day": (g.usd.sum() / 501).round(1)}).to_string())
