"""ADVERSARIAL VERIFY of g71/scarface Finding 2. Read-only. Independent recount."""
import json,re
from pathlib import Path
from collections import Counter
ROOT=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
d=json.load(open(ROOT/"discord_data"/"scarface-alerts.json",encoding='utf-8'))
print("msgs total",len(d))
print("authors",Counter((m.get("author") or "") for m in d).most_common(3))

STRIKE=re.compile(r'(\d{2,4}(?:\.\d{1,2})?)\s*(?:strike\s*)?(?:calls?|puts?)\b',re.I)
LVLCTX=re.compile(r'(?:level|retest|reclaim|pdh|pdl|hod|lod|above|below|holds?|break)\D{0,18}(\d{2,4}\.\d{1,2})',re.I)
LEVEL=re.compile(r'\b(\d{2,4}\.\d{1,2})\b')
s=l=b=0
for m in d:
    c=m.get("content") or ""
    hs=bool(STRIKE.search(c)); hl=bool(LVLCTX.search(c))
    s+=hs; l+=hl; b+= (hs and hl)
print(f"STRIKE msgs={s}  LVLCTX msgs={l}  both={b}")
# how many msgs have ANY decimal number
anynum=sum(1 for m in d if LEVEL.search(m.get("content") or ""))
print("msgs with any 2-4digit decimal:",anynum)
# strike-only decimals: msgs where every decimal found is also a strike
onlystrike=0; strikehasdec=0
for m in d:
    c=m.get("content") or ""
    dec=set(LEVEL.findall(c))
    if not dec: continue
    st=set(x for x in STRIKE.findall(c) if '.' in x)
    if st: strikehasdec+=1
    if dec and dec<=st: onlystrike+=1
print("msgs whose every decimal is a strike:",onlystrike," msgs w/ decimal strike:",strikehasdec)
