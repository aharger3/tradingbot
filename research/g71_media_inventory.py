"""G7.1 media track inventory. Read-only. Counts upstream vs downloaded vs transcribed."""
import json, re, glob, os
from pathlib import Path

DATA = Path("circle_data"); OUT = DATA / "transcripts_text"
def slug(n): return re.sub(r"[^a-z0-9]+","-",n.lower()).strip("-")[:60]

rows=[]; tot=dict(lessons=0,with_url=0,txt=0,vtt=0,mp4=0,yt=0)
vids = {p.name for p in Path("circle_videos").glob("*.mp4")}
vtts = {p.name for p in (DATA/"transcripts").glob("*.vtt")}
for f in sorted(DATA.glob("*/videos.json")):
    space=f.parent.name
    data=json.loads(f.read_text(encoding="utf-8"))
    n=len(data); wu=0; t=0; m=0; yt=0
    for v in data:
        if v.get("download_url") or v.get("video_url"): wu+=1
        if (OUT/f"{space}_{slug(v['name'])}_transcript.txt").exists(): t+=1
        name = re.sub(r'[^a-zA-Z0-9]+','_',v["name"]).strip("_")[:60]
        if f"{space}_{name}.mp4" in vids: m+=1
        yt += len(v.get("youtube_ids") or [])
    rows.append((space,n,wu,t,m,yt))
    tot['lessons']+=n; tot['with_url']+=wu; tot['txt']+=t; tot['mp4']+=m; tot['yt']+=yt

print(f"{'space':34}{'lessons':>8}{'has_url':>8}{'txt':>6}{'mp4':>6}{'ytids':>7}")
for r in rows: print(f"{r[0]:34}{r[1]:>8}{r[2]:>8}{r[3]:>6}{r[4]:>6}{r[5]:>7}")
print(f"{'TOTAL':34}{tot['lessons']:>8}{tot['with_url']:>8}{tot['txt']:>6}{tot['mp4']:>6}{tot['yt']:>7}")
print()
print("transcripts_text files :", len(list(OUT.glob('*.txt'))))
print("transcripts vtt files  :", len(vtts))
print("circle_videos mp4      :", len(vids))
print("circle_audio leftovers :", len(list(Path('circle_audio').glob('*'))))
pv=json.load(open(DATA/"playlist_videos.json"))
print("playlist_videos total  :", pv['total_videos'], "unique:", len(pv['unique_video_ids']))
ytd=Path("youtube_data")
print("yt transcripts (youtube_data):", len(list(ytd.glob('*_transcript.txt'))))
print("yt thumbnails               :", len(list(ytd.glob('*_thumbnail.*'))))
ytt=DATA/"youtube_transcripts"
print("circle_data/youtube_transcripts exists:", ytt.exists(), len(list(ytt.glob('*'))) if ytt.exists() else 0)

# --- playlist (YouTube-hosted live-sessions + trade-reviews) coverage ---
ids=set(pv['unique_video_ids'])
have={p.name.replace('_transcript.txt','') for p in ytd.glob('*_transcript.txt')}
thumbs={p.name.rsplit('_thumbnail',1)[0] for p in ytd.glob('*_thumbnail.*')}
print()
print("playlist ids                :", len(ids))
print("  with youtube_data transcript:", len(ids & have))
print("  MISSING transcript          :", len(ids - have))
print("  with thumbnail              :", len(ids & thumbs))
print("youtube_data transcripts not in playlists:", len(have - ids))
import collections
# per playlist space
for sp in ('live-sessions','trade-reviews'):
    tot=0; got=0
    for p in pv['playlists']:
        if p['space']!=sp: continue
        for v in p['videos']:
            tot+=1; got += v['id'] in have
    print(f"  {sp}: {got}/{tot} transcribed")
