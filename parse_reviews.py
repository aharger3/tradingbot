"""Trade-review transcripts -> labeled trades. The title carries the outcome:
'October 4th Trade Review (-$1.6k NVDA)' -> date, NVDA, loss, -$1600.
Body (parsed later) adds level/entry/target. This is the real supervised set.
Run: python parse_reviews.py
"""
import re, glob, json
from pathlib import Path

TICK = set('SPY QQQ IWM AAPL TSLA NVDA AMD AMZN META MSFT GOOGL GOOG NFLX COIN HOOD PLTR SMCI MSTR AVGO MU BABA SHOP CRM UBER DIS BA INTC GME SOFI RIVN LCID'.split())
PNL_RE = re.compile(r"\(([-+]?)\$?([\d.]+)k?\b", re.I)
MONTH = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
DATE_RE = re.compile(MONTH + r"\s+(\d{1,2})", re.I)


def parse_title(title: str):
    m = PNL_RE.search(title)
    pnl = outcome = None
    if m:
        sign, num = m.group(1), float(m.group(2))
        # 'k' in title means thousands; bare number in review titles is $k too
        pnl = num * 1000 * (-1 if sign == "-" else 1)
        outcome = "loss" if sign == "-" else "win"
    tickers = [t for t in re.findall(r"\b[A-Z]{2,5}\b", title) if t in TICK]
    dm = DATE_RE.search(title)
    return {"pnl": pnl, "outcome": outcome, "tickers": tickers,
            "date_str": f"{dm.group(1)} {dm.group(2)}" if dm else None}


def run():
    recs = []
    for f in glob.glob("youtube_data/*_transcript.txt") + glob.glob("circle_data/transcripts_text/*_transcript.txt"):
        head = Path(f).read_text(encoding="utf-8", errors="ignore")[:200]
        title = head.splitlines()[0].lstrip("# ").strip() if head else ""
        if "trade review" not in title.lower():
            continue
        p = parse_title(title)
        recs.append({"file": Path(f).name, "title": title, **p})
    labeled = [r for r in recs if r["outcome"] and r["tickers"]]
    wins = sum(1 for r in labeled if r["outcome"] == "win")
    print(f"trade-review transcripts: {len(recs)}")
    print(f"  with outcome+ticker in title: {len(labeled)}")
    print(f"  win/loss: {wins}W / {len(labeled)-wins}L = {wins/max(1,len(labeled))*100:.0f}% win")
    tot = sum(r['pnl'] for r in labeled if r['pnl'])
    print(f"  net P&L across titled reviews: ${tot:+,.0f}")
    Path("labeled_reviews.json").write_text(json.dumps(recs, indent=1))
    print("wrote labeled_reviews.json")
    print("--- sample ---")
    for r in labeled[:10]:
        print(f"  {r['date_str'] or '?':13s} {'/'.join(r['tickers']):10s} {r['outcome']:4s} ${r['pnl']:+,.0f}")


if __name__ == "__main__":
    run()
