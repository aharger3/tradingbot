"""G7.1 adversarial verify (track: scanners) — is the regime filter / news halt
really absent from every backtest number, and what would they cost the current
2-year book? Read-only."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

bk = json.loads((ROOT / "research/bt2y_trades.json").read_text())
tr = [t for t in bk["trades"] if t.get("traded")]
print("all signal rows:", len(bk["trades"]))
print("meta:", {k: v for k, v in bk["meta"].items() if k != "trades"})
print("trades in book:", len(tr))
print("sample keys:", sorted(tr[0].keys()))

nd = set(json.loads((ROOT / "news_days.json").read_text()).get("news_days", []))
print("news_days.json entries:", len(nd), "range:", min(nd), max(nd))

days = sorted({t["day"] for t in tr})
print("book day range:", days[0], "->", days[-1], "days:", len(days))
hit = nd & set(days)
print("news days inside book window:", len(hit))

on = [t for t in tr if t["day"] in nd]
off = [t for t in tr if t["day"] not in nd]
def stat(rs, label):
    if not rs: print(f"{label}: 0 trades"); return
    r = [t["r"] for t in rs]
    w = sum(1 for x in r if x > 0)
    print(f"{label}: n={len(r)} meanR={sum(r)/len(r):+.4f} win={w/len(r):.1%} sumR={sum(r):+.1f}")
stat(tr, "ALL (no filter)")
stat(on, "  news days")
stat(off, "  SKIP_NEWS=1 book")

# ---- regime filter replay over the same book, live config ----
from regime_detector import (RegimeDetector, RegimeConfig, MODE_SMA,
                             ACTION_STOP, ACTION_STOP_LONG, ACTION_STOP_SHORT)
from market_data import fetch_spy_daily_closes
try:
    raw = fetch_spy_daily_closes(days_back=1200)
    dts = sorted(raw); cl = [raw[d] for d in dts]
    det = RegimeDetector(RegimeConfig(mode=MODE_SMA, directional=True,
                                      melt_up_threshold=0.05, melt_down_threshold=-0.05))
    det.feed_daily_closes(dts, cl)
    acts = {d: det.get_action(d) for d in days}
    from collections import Counter
    print("regime action histogram over book days:", Counter(a for _, a in acts.values()))
    kept = []
    for t in tr:
        a = acts.get(t["day"], (None, "normal"))[1]
        d = (t.get("dir") or "").lower()
        if a == ACTION_STOP: continue
        if a == ACTION_STOP_LONG and d in ("call", "long"): continue
        if a == ACTION_STOP_SHORT and d in ("put", "short"): continue
        kept.append(t)
    stat(kept, "REGIME-FILTERED book")
    print("directions seen:", Counter((t.get('direction') or '?') for t in tr))
except Exception as e:
    print("regime replay failed:", type(e).__name__, str(e)[:200])
