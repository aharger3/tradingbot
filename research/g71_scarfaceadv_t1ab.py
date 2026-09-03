"""ADVERSARIAL: reproduce old-rule T1 (any decimal) vs new-rule T1 (level-in-context).
Read-only. Mirrors g71_scarface_candidates.build() exactly but tiers both ways."""
import json,re,sys
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime,timedelta
ROOT=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot"); DATA=ROOT/"discord_data"
sys.path.insert(0,str(ROOT/"research")); sys.path.insert(0,str(ROOT))
import importlib
m=importlib.import_module("g71_scarface_candidates")
CH=m.CHANNELS
rows=[]
for fname,auth,tag in CH:
    p=DATA/fname
    if not p.exists(): continue
    d=json.load(open(p,encoding='utf-8'))
    if auth: d=[x for x in d if auth in (x.get("author") or "")]
    seqs,last=defaultdict(list),{}
    for msg in sorted(d,key=lambda x:x.get("ts","")):
        ts=msg.get("ts") or ""
        if not ts: continue
        c=msg.get("content") or ""; day=ts[:10]
        hit=m.TICK.findall(c); sym=hit[0].upper() if hit else last.get(day)
        if hit: last[day]=sym
        if not sym: continue
        seqs[(day,sym)].append(msg)
    for (day,sym),msgs in seqs.items():
        w=[x for x in msgs if m.in_window(x["ts"])]
        if not w: continue
        txt="\n".join((x.get("content") or "") for x in w)
        nc,np_=len(m.DIRC.findall(txt)),len(m.DIRP.findall(txt))
        direction="call" if nc>np_ else ("put" if np_>nc else None)
        strikes=sorted({float(x) for x in m.STRIKE.findall(txt)})
        lvlctx=sorted({float(x) for x in m.LVLCTX.findall(txt)})
        anydec=sorted({float(x) for x in m.LEVEL.findall(txt)})
        charts=sum(1 for x in w if m.has_chart(x))
        rows.append((tag,sym,day,direction,bool(anydec),bool(lvlctx),bool(charts),
                     strikes,lvlctx,anydec))
old=[r for r in rows if r[3] and r[4]]
new=[r for r in rows if r[3] and r[5]]
print(f"total units={len(rows)}  OLD T1(dir+any decimal)={len(old)}  NEW T1(dir+lvlctx)={len(new)}")
print("OLD by tag",Counter(r[0] for r in old))
print("NEW by tag",Counter(r[0] for r in new))
# of the OLD-only rows, how many had ONLY strike decimals (i.e. would have been fed a strike)?
onlystrike=0; nostrike=0
for r in old:
    if r[5]: continue
    st=set(r[7]); dec=set(r[9])
    if dec and dec<=st: onlystrike+=1
    elif not (dec&st): nostrike+=1
print(f"OLD-only rows={len(old)-len(new) if False else sum(1 for r in old if not r[5])}"
      f"  of which every-decimal-is-a-strike={onlystrike}  no-decimal-is-a-strike={nostrike}")
json.dump([[r[0],r[1],r[2],r[3],r[7],r[8],r[9]] for r in old if not r[5]],
          open(ROOT/"research"/"g71_scarfaceadv_oldonly.json","w"))
