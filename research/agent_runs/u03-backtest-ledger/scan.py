import os,re,datetime
R=r"C:\Users\aharg\Desktop\Projects\tradingbot"
pat=re.compile(r"\$[\d,]+(?:\.\d+)?\s*/\s*day|/day")
rows=[]
for root,ds,fs in os.walk(R):
    ds[:]=[d for d in ds if d not in (".git",".claude","node_modules","__pycache__","data_archive","data","circle_videos","circle_audio","youtube_data","discord_data","circle_data",".cache")]
    for f in fs:
        if not f.endswith((".md",".txt")): continue
        p=os.path.join(root,f)
        try: s=open(p,encoding="utf-8",errors="ignore").read()
        except: continue
        n=len(pat.findall(s))
        if n: rows.append((datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d"),n,os.path.relpath(p,R)))
rows.sort()
for r in rows: print(*r)
print(len(rows))
print(os.listdir(os.path.join(R,"research","agent_runs")))
