import sys, os, json, glob, collections as C
R=r"C:\Users\aharg\Desktop\Projects\tradingbot\research"
sys.path.insert(0,R); sys.path.insert(0,os.path.dirname(R))
import build_deck as bd, grade_read as gr
srcs=bd.mark_sources(); print(len(srcs))
keys=C.Counter()
for p in srcs:
    if not os.path.exists(p): continue
    for r in bd._rows(p):
        keys.update(r.keys())
print(keys.most_common(80))
r=next(iter(bd._rows(os.path.join(R,"austin_marks_v7.jsonl"))),None); print(json.dumps(r)[:1500])
print(sorted(os.listdir(os.path.join(os.path.dirname(R),"data_archive"))))
print([n for n in dir(gr) if not n.startswith('__')])
