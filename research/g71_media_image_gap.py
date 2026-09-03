"""G7.1 media: discord image coverage — messages with an image URL vs files on disk."""
import json,re,datetime
from pathlib import Path
D=Path('discord_data'); IMG=D/'images'
IMGRE=re.compile(r"\.(png|jpe?g|webp|gif)(\?|$)",re.I)
tot=miss=0; expiring=0; rows=[]
for f in sorted(D.glob('*.json')):
    if f.name.startswith('_'): continue
    ch=f.stem
    try: msgs=json.loads(f.read_text(encoding='utf-8'))
    except Exception: continue
    if not isinstance(msgs,list): continue
    d=IMG/ch
    have={p.stem.rsplit('_',1)[0] for p in d.iterdir()} if d.exists() else set()
    n=m=0; last_ts=''; last_miss=''
    for msg in msgs:
        urls=[u for u in (msg.get('attachments') or [])+[u for u in (msg.get('embeds') or []) if u] if IMGRE.search(str(u))]
        if not urls: continue
        n+=1
        if any('ex=' in str(u) for u in urls): expiring+=1
        ts=(msg.get('ts') or '')[:10]
        last_ts=max(last_ts,ts)
        if msg['id'] not in have:
            m+=1; last_miss=max(last_miss,ts)
    if n: rows.append((ch,n,len(have),m,last_ts,last_miss))
    tot+=n; miss+=m
rows.sort(key=lambda r:-r[3])
print(f"{'channel':26}{'msgs_w_img':>11}{'ids_on_disk':>12}{'missing':>9}  {'last_img_msg':<12} {'last_missing':<12}")
for r in rows: print(f"{r[0]:26}{r[1]:>11}{r[2]:>12}{r[3]:>9}  {r[4]:<12} {r[5]:<12}")
print(f"{'TOTAL':26}{tot:>11}{'':>12}{miss:>9}")
print("\nmessages whose image URL carries an expiry token (ex=):",expiring,f"({expiring/max(tot,1)*100:.1f}%)")
