import json,gzip,glob,os
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
for pat in ["tape/*r2ref*","*r2ref*","tape/*","reconcile*","*edge_slices*","agent_runs/*/slices*"]:
    for f in glob.glob(pat)[:30]: print(pat, f, os.path.getsize(f))
src=open("marks_pool.py",encoding="utf-8").read()
import re
print([m for m in re.findall(r"^def (\w+)\(.*", src, re.M)])
print(src[:1500])
