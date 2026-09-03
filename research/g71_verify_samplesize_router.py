"""ADVERSARIAL VERIFY, part 2: re-run the G71/samplesize corpus recall through the
CORRECT (delegating) router, the fix g71_router_recall.py already isolates.

Read-only. Monkeypatch is in-process; no engine file is edited.
"""
from __future__ import annotations
import json, os, sys, time, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import research.t4_engine_recall as t4
import research.g71_router_recall as rr
import importlib.util
spec = importlib.util.spec_from_file_location("vrep", os.path.join(HERE, "g71_verify_samplesize_replay.py"))
v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)

def run(rows, tag):
    t0 = time.time(); fired = {}
    for i, r in enumerate(rows):
        try:
            ent, sigs, _ = t4.run_day(r["symbol"], r["day"])
        except Exception:
            continue
        if ent is None: continue
        fired[r["key"]] = (len(ent) > 0, len(sigs) > 0)
        if i % 300 == 0: print("  %s %d/%d %.0fs" % (tag, i, len(rows), time.time()-t0), flush=True)
    return fired

def tally(rows, fired):
    by = collections.defaultdict(lambda: {"n":0,"fired":0,"det":0})
    for r in rows:
        f = fired.get(r["key"])
        if f is None: continue
        b = by[r["grade"]]; b["n"]+=1; b["fired"]+=int(f[0]); b["det"]+=int(f[1])
    return by

def main():
    per = v.build(); rows = []
    for k, d in per.items():
        g = v.top(d)
        if not g: continue
        sym, _, day = k.rpartition("_")
        if not os.path.exists(os.path.join(v.ARCHIVE, sym, day + ".csv")): continue
        rows.append({"key":k,"symbol":sym,"day":day,"grade":g})
    rows.sort(key=lambda r: r["key"])
    t4.CaptureRunner._route = rr._delegating_route
    fired = run(rows, "deleg")
    by = tally(rows, fired)
    out = {"router":"delegating (backtest_week shape)","replayed":len(fired),
           "by_grade":{g:{**x,"recall_pct":round(x["fired"]/max(1,x["n"])*100,1),
                          "detect_pct":round(x["det"]/max(1,x["n"])*100,1)} for g,x in sorted(by.items())}}
    gs=["S","A","C","none"]; pr={}
    for i in range(len(gs)):
        for j in range(i+1,len(gs)):
            a,b_=gs[i],gs[j]
            z,p = v.ztest(by[a]["fired"],by[a]["n"],by[b_]["fired"],by[b_]["n"])
            pr["%s_vs_%s"%(a,b_)]={"z":round(z,3),"p":round(p,4),"bonf6":round(min(1.0,p*6),4)}
    out["pairwise_z"]=pr
    print(json.dumps(out, indent=2))
    json.dump(out, open(os.path.join(HERE,"g71_verify_samplesize_router.json"),"w",encoding="utf-8"), indent=2)

if __name__ == "__main__":
    main()
