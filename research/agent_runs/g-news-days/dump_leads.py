# g-news-days: dump per-date Zarattini ORB trades (NONE + NQ925, 1 tick slip) from the zarattini worktree, read-only.
import sys, json
from pathlib import Path
Z = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot-zarattini\research\zarattini")
sys.path.insert(0, str(Z))
import zarattini as z
SESS = {r: z.bt.sessions(r) for r in ("NQ", "ES")}
PRE = {r: z.pre_bars(r) for r in ("NQ", "ES")}
out = {"sessions": sorted(SESS["NQ"])}
for f in ("NONE", "NQ925"):
    bk = z.book(SESS, PRE, f, 1)
    out[f] = {D: dict(R=float(t["R"]), d=int(t["d"]), why=t["why"]) for D, t in bk.items()}
    print(f, len(bk))
json.dump(out, open(Path(__file__).parent / "zar_trades.json", "w"))
