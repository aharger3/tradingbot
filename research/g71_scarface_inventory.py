"""G7.1/scarface: inventory discord_data for extractable trade reviews.
Read-only. Writes nothing but stdout."""
import json, re, sys
from pathlib import Path
from collections import Counter

DATA = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\discord_data")
FILES = ["futures-trade-reviews.json","options-trade-reviews.json","scarface-alerts.json",
         "jdub-alerts.json","trade-feedback.json","backtesting.json","live-sessions.json",
         "pre-market-live.json","premarket-charts.json","swing-ideas.json",
         "trading-floor.json","youtube.json","futures-alerts.json",
         # adjacent, same family
         "scarface-trade-reviews.json","jdub-trade-reviews.json"]

TICK = re.compile(r'\b(SPY|QQQ|IWM|AAPL|TSLA|NVDA|AMD|AMZN|META|MSFT|GOOGL|GOOG|NFLX|COIN|HOOD|PLTR|SMCI|MSTR|AVGO|MU|BABA|SHOP|CRM|UBER|DIS|BA|INTC|GME|SOFI|RIVN|LCID|SPX|NDX|ES|NQ|MNQ|MES|RTY|YM|CL|GC)\b')
DIR  = re.compile(r'\b(long|short|call|put|calls|puts|bull|bear|bullish|bearish|buying|selling)\b', re.I)
LVL  = re.compile(r'\b\d{2,6}(?:\.\d{1,2})?\b')
OUT  = re.compile(r'\b(win|won|loss|lost|stopped|stop\s*out|target|pt1|pt2|tp1|runner|green|red|profit|filled|hit|scratch|breakeven|be\b)\b', re.I)
ZOOM = re.compile(r'(zoom\.us|youtube\.com|youtu\.be|vimeo)', re.I)
IMGEXT = re.compile(r'\.(png|jpe?g|gif|webp)(\?|$)', re.I)

def has_chart(m):
    for a in m.get("attachments") or []:
        s = a if isinstance(a,str) else json.dumps(a)
        if IMGEXT.search(s): return True
    for e in m.get("embeds") or []:
        s = e if isinstance(e,str) else json.dumps(e)
        if IMGEXT.search(s): return True
    return False

rows=[]
for fn in FILES:
    p = DATA/fn
    if not p.exists():
        rows.append((fn,0,"-","-",0,0,0,0,0,0)); continue
    d = json.load(open(p,encoding='utf-8'))
    if not isinstance(d,list): d=[]
    ts=[m.get("ts","") for m in d if m.get("ts")]
    lo,hi=(min(ts)[:10],max(ts)[:10]) if ts else ("-","-")
    n=len(d)
    nsym=ndir=nlvl=nout=nfull=nchart=nlink=0
    authors=Counter()
    for m in d:
        c = m.get("content","") or ""
        authors[m.get("author","?")]+=1
        s=bool(TICK.search(c)); di=bool(DIR.search(c)); l=bool(LVL.search(c)); o=bool(OUT.search(c))
        nsym+=s; ndir+=di; nlvl+=l; nout+=o
        if s and di and l and o: nfull+=1
        if has_chart(m): nchart+=1
        if ZOOM.search(c): nlink+=1
    rows.append((fn,n,lo,hi,nsym,ndir,nlvl,nout,nfull,nchart,nlink,authors.most_common(3)))

print(f"{'file':34s}{'msgs':>7}{'from':>12}{'to':>12}{'sym':>6}{'dir':>6}{'lvl':>6}{'out':>6}{'ALL4':>6}{'chart':>7}{'vidlink':>8}")
for r in rows:
    if len(r)==10: continue
    fn,n,lo,hi,ns,nd,nl,no,nf,nc,nk,au=r
    print(f"{fn:34s}{n:>7}{lo:>12}{hi:>12}{ns:>6}{nd:>6}{nl:>6}{no:>6}{nf:>6}{nc:>7}{nk:>8}")
print()
for r in rows:
    if len(r)==12:
        print(f"{r[0]:34s} top authors: {r[11]}")
