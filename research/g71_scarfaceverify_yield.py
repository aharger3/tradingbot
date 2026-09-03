"""G7.1 adversarial verify (scarface): yield of a TEXT-ONLY parser on scarface-trade-reviews.
Emits distinct (trade_date, symbol, outcome_sign, usd) rows. Read-only; stdout only."""
import json,re,sys,datetime as dt
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
ROOT=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
UNI=set(re.findall(r"['\"]([A-Z]{1,5})['\"]",(ROOT/"universe.py").read_text(encoding='utf-8')))
SYMS=UNI|{"AMD","NQ","GOOG","GME","BA","DIS"}
MONN={m.lower():i for i,m in enumerate(
 "January February March April May June July August September October November December".split(),1)}
RE_MD=re.compile(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})',re.I)
RE_USD=re.compile(r'(-)?\$\s?([\d,]+(?:\.\d+)?)\s?([kK])?')
RE_LOSS=re.compile(r'\bloss\b',re.I)
RE_SYM=re.compile(r'\b[A-Z]{1,5}\b')
rows=[]; noparse=[]
for m in json.load(open(ROOT/"discord_data/scarface-trade-reviews.json",encoding='utf-8')):
    t=re.sub(r'https?://\S+',' ',m.get("content","") or "")
    md=RE_MD.search(t); us=RE_USD.search(t)
    sy=[x for x in dict.fromkeys(RE_SYM.findall(t)) if x in SYMS]
    if not(md and us and sy): noparse.append((m["ts"][:10],t.strip()[:70])); continue
    post=dt.date.fromisoformat(m["ts"][:10])
    mo,day=MONN[md.group(1).lower()],int(md.group(2))
    yr=post.year - (1 if mo==12 and post.month==1 else 0)
    try: d=dt.date(yr,mo,day)
    except ValueError: noparse.append((m["ts"][:10],t.strip()[:70])); continue
    amt=float(us.group(2).replace(",",""))*(1000 if us.group(3) else 1)
    neg=bool(us.group(1)) or bool(RE_LOSS.search(t))
    for s in sy: rows.append((d.isoformat(),s,"LOSS" if neg else "WIN",-amt if neg else amt))
u=sorted(set((r[0],r[1]) for r in rows))
print(f"scarface-trade-reviews.json: 267 msgs -> {len(rows)} (date,symbol) trade rows, {len(u)} DISTINCT symbol-days")
print(f"  date range {u[0][0]} .. {u[-1][0]}")
print(f"  WIN={sum(1 for r in rows if r[2]=='WIN')}  LOSS={sum(1 for r in rows if r[2]=='LOSS')}  (win rate {sum(1 for r in rows if r[2]=='WIN')/len(rows):.1%} - survivorship-curated, do NOT use as ground truth)")
from collections import Counter
print("  symbols:",Counter(r[1] for r in rows).most_common())
print(f"  msgs the parser could NOT resolve: {len(noparse)}/267")
for x in noparse[:8]: print("     ",x[0],repr(x[1]))
# overlap with Austin's judged corpus
sys.path.insert(0,str(ROOT/"research"))
try:
    from build_deck import marked_card_ids
    mk=marked_card_ids(); print(f"  marked_card_ids() = {len(mk)}")
    def cid(d,s):
        for f in (f"{s}_{d}",f"{d}_{s}",f"{s}|{d}",f"{d}|{s}"):
            if f in mk: return True
        return False
    ov=sum(1 for d,s in u if cid(d,s))
    print(f"  overlap with Austin's judged symbol-days: {ov} / {len(u)}  -> NEW = {len(u)-ov}")
except Exception as e:
    print("  marked_card_ids unavailable:",type(e).__name__,str(e)[:120])
