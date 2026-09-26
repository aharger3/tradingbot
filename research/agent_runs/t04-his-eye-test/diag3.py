import os,sys,json,collections as C
os.chdir(r"C:\Users\aharg\Desktop\Projects\tradingbot"); sys.path.insert(0,"research")
import build_deck as bd, marks_pool as mp
for p in bd.mark_sources():
    n=mp._relname(p)
    if "probe_daily" in n or "omen_test1" in n or "batch_02" in n or "blind_marks" in n or "master_2026" in n:
        rows=list(bd._rows(p))
        print(n, json.dumps({k:v for k,v in rows[-1].items() if k not in("notes","note","answers")},default=str)[:600])
        print("  modes",C.Counter(str(r.get("mode"))+"/"+str(r.get("n_bars"))+"/"+str(r.get("part"))+"/"+str(r.get("lane")) for r in rows).most_common(6))
