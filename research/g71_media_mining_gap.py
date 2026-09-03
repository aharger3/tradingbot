"""G7.1 media: which transcripts have actually been mined for rules."""
import json,re
from pathlib import Path
vt={p.name for p in Path('research/video_transcripts').glob('*_transcript.txt')}
tt={p.name for p in Path('circle_data/transcripts_text').glob('*.txt')}
yt={p.name.replace('_transcript.txt','') for p in Path('youtube_data').glob('*_transcript.txt')}
print('research/video_transcripts (mined corpus):',len(vt))
print('circle_data/transcripts_text            :',len(tt))
print('  overlap by filename                   :',len(vt&tt))
print('  in transcripts_text but NOT mined     :',len(tt-vt))
groups=json.load(open('research/video_transcripts/_extract_groups.json',encoding='utf-8'))
flat=[f for g in groups for f in g]
print('files in _extract_groups.json           :',len(flat),'groups',len(groups))
ck=sorted(Path('research/video_transcripts/_extract_checkpoints').glob('group_*.md'))
print('group checkpoints present               :',len(ck),'of',len(groups))
done=Path('research/video_transcripts/_done_files.txt')
if done.exists(): print('_done_files.txt lines                   :',len(done.read_text(encoding='utf-8').split()))
# youtube rule mining coverage: which ids are cited in the youtube rule md files
cited=set()
for md in Path('research').glob('scarface-rules-*.md'):
    txt=md.read_text(encoding='utf-8',errors='replace')
    cited|=set(re.findall(r'([A-Za-z0-9_-]{11})_transcript',txt))
    print(f'  {md.name:40} {len(txt):>8} chars')
print('youtube transcripts on disk             :',len(yt))
print('  cited in any scarface-rules-*.md      :',len(cited & yt))
print('  NOT cited (unmined)                   :',len(yt - cited))
# ladder coverage
wl=[json.loads(l) for l in open('research/yt_worklist.jsonl',encoding='utf-8') if l.strip()]
print('yt_worklist.jsonl rows                  :',len(wl))
for r in ('qwen','batch','flash'):
    p=Path(f'research/video_ladder_results_{r}.jsonl')
    print(f'  video_ladder_results_{r:6}          :',sum(1 for _ in open(p,encoding='utf-8')) if p.exists() else 'MISSING')
print('vision_pilot_manifest rows              :',sum(1 for _ in open('research/vision_pilot_manifest.jsonl',encoding='utf-8')))
