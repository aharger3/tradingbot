"""G7.1 media: YouTube-link gap between Discord posts and transcripts on disk."""
import json,re
from pathlib import Path
VID=re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|live/|embed/))([\w-]{11})")
PL =re.compile(r"list=([\w-]{16,})")
pv=json.load(open('circle_data/playlist_videos.json',encoding='utf-8'))
ids=set(pv['unique_video_ids'])
pl_have={p['playlist_id'] for p in pv['playlists']}
have={p.name.replace('_transcript.txt','') for p in Path('youtube_data').glob('*_transcript.txt')}
rows=[]; pls={}
for f in sorted(Path('discord_data').glob('*.json')):
    if f.name.startswith('_'): continue
    try: msgs=json.loads(f.read_text(encoding='utf-8'))
    except Exception: continue
    if not isinstance(msgs,list): continue
    for m in msgs:
        if not isinstance(m,dict): continue
        blob=(m.get('content') or '')+' '+' '.join(map(str,m.get('embeds') or []))
        ts=(m.get('ts') or '')[:10]
        for v in VID.findall(blob): rows.append((ts,f.stem,v))
        for p in PL.findall(blob): pls.setdefault(p,(ts,f.stem))
uniq={}
for ts,ch,v in sorted(rows): uniq.setdefault(v,(ts,ch))
print('unique yt video ids in discord:',len(uniq))
print('  transcript on disk           :',sum(1 for v in uniq if v in have))
print('  NO transcript                :',sum(1 for v in uniq if v not in have))
print('  in playlist_videos.json      :',sum(1 for v in uniq if v in ids))
for cut in ('2026-07-05','2026-08-01'):
    n=[v for v,(ts,_) in uniq.items() if ts>=cut]
    print(f'  posted >= {cut}: {len(n)}  transcribed {sum(1 for v in n if v in have)}')
print('  latest discord yt post:',max(ts for ts,_ in uniq.values()))
from collections import Counter
c=Counter(ch for v,(ts,ch) in uniq.items() if v not in have)
print('  untranscribed by channel:',c.most_common(12))
print()
print('playlists referenced in discord:',len(pls),' captured in playlist_videos.json:',sum(1 for p in pls if p in pl_have))
for p,(ts,ch) in sorted(pls.items(),key=lambda x:x[1][0]):
    if p not in pl_have: print('   MISSING PLAYLIST',ts,ch,p)
