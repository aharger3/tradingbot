from pathlib import Path
root=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\data_archive")
tot=0
for d in sorted(p for p in root.iterdir() if p.is_dir() and p.name!="options"):
    fs=sorted(d.glob("*.csv")); rows=0; rth=0; short=0
    for f in fs:
        L=f.read_text().splitlines()[1:]; rows+=len(L)
        r=sum(1 for l in L if "T09:3" <= l[10:16] < "T16:00"); rth+=r
        if r<380: short+=1
    tot+=rows
    print(f"{d.name},{len(fs)},{fs[0].stem},{fs[-1].stem},{rows},{rth},{short}")
print("TOTAL",tot)
c=Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\data\cache")
for d in sorted(c.iterdir())[:40]:
    subs=[s.name+":"+str(len(list(s.iterdir()))) for s in d.iterdir() if s.is_dir()]
    print("cache",d.name,subs)
