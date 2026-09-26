import gzip,json,os,glob
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot\research")
d=json.load(gzip.open("tape/baseline_2026-09-13.json.gz"))
print(type(d))
if isinstance(d,dict):
    for k,v in d.items():
        print(k, type(v).__name__, (v if not isinstance(v,(list,dict)) else (len(v))))
    for k in ("meta","params","config","flags","summary"):
        if k in d: print(k, json.dumps(d[k])[:1500])
    t=d.get("trades") or []
    if t: print(json.dumps(t[0])[:1500])
for f in glob.glob("**/*.json.gz",recursive=True):
    print(f, os.path.getsize(f))
