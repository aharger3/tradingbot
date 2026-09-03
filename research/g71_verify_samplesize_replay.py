"""ADVERSARIAL VERIFY of G71/samplesize. Read-only. Writes no mark file, edits no engine file.

Re-derives the corpus grade map from build_deck (not from the audit json), replays
every Austin-graded day with archived bars through research.t4_engine_recall.run_day,
and recomputes the by-grade recall/detection AND the two-proportion z-tests, plus:
  * a 'none' arm cleaned of page-default grade:"none" rows (probe pages where EVERY
    row carries grade:"none" and the real answer lives in a non-grade lane)
  * all six pairwise contrasts, so the S-vs-none contrast can be seen against the
    family it was selected from
"""
from __future__ import annotations
import json, os, sys, time, math, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import build_deck as bd
import research.t4_engine_recall as t4

ARCHIVE = os.path.join(ROOT, "data_archive")
AUSTIN = {"s":"S","a":"A","c":"C","none":"none","no":"none","n":"none","skip":"none","pass":"none","x":"none"}
ENGINE = {"a+":"A+","b":"B","d":"D"}
# probe pages that stamp grade:"none" on EVERY row as a template default
DEFAULT_NONE_FILES = {"research/marks/probe_master_2026-08-29.jsonl",
                      "research/marks/probe_head2head_2026-08-24.jsonl",
                      "research/marks/probe_s_sweep_2026-08-28.jsonl"}

def norm(raw):
    if raw is None: return None
    t = str(raw).strip().lower()
    if not t: return None
    if t in ENGINE: return None
    return AUSTIN.get(t)

def build():
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in bd.mark_sources():
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        for row in bd._rows(p):
            k = bd._judgement_key(row)
            if not k: continue
            for gk in bd._GRADE_KEYS:
                g = norm(row.get(gk))
                if g: per[k][g].append((rel, "field:"+gk))
            a = row.get("answers")
            if isinstance(a, dict):
                for ak, v in a.items():
                    if ak not in ("grade","tier","s","s_call","austin_grade"): continue
                    for vv in (v if isinstance(v, list) else [v]):
                        g = norm(vv)
                        if g: per[k][g].append((rel, "answers:"+ak))
            if row.get("_no_trade"): per[k]["none"].append((rel, "_no_trade"))
    return per

def top(d):
    for g in ("S","A","C","none"):
        if d.get(g): return g
    return None

def is_default_only_none(ev):
    return all(p == "field:grade" and s in DEFAULT_NONE_FILES for s, p in ev)

def ztest(x1,n1,x2,n2):
    if not n1 or not n2: return (float("nan"), float("nan"))
    p1,p2 = x1/n1, x2/n2
    pp = (x1+x2)/(n1+n2)
    se = math.sqrt(pp*(1-pp)*(1/n1+1/n2))
    if se == 0: return (0.0, 1.0)
    z = (p1-p2)/se
    p = math.erfc(abs(z)/math.sqrt(2))
    return (z, p)

def main():
    per = build()
    rows = []
    for k, d in per.items():
        g = top(d)
        if not g: continue
        sym, _, day = k.rpartition("_")
        if not os.path.exists(os.path.join(ARCHIVE, sym, day + ".csv")): continue
        rows.append({"key":k,"symbol":sym,"day":day,"grade":g,
                     "default_only_none": g=="none" and is_default_only_none(d["none"])})
    rows.sort(key=lambda r: r["key"])
    print("replayable Austin-graded days: %d" % len(rows), flush=True)
    t0=time.time(); fired={}; errs=[]
    for i,r in enumerate(rows):
        try:
            ent, sigs, _ = t4.run_day(r["symbol"], r["day"])
        except Exception as e:
            errs.append({"key":r["key"],"err":type(e).__name__}); continue
        if ent is None:
            errs.append({"key":r["key"],"err":"no bars"}); continue
        fired[r["key"]] = {"entries":len(ent), "signals":len(sigs)}
        if i % 200 == 0: print("  %d/%d %.0fs"%(i,len(rows),time.time()-t0), flush=True)
    by = collections.defaultdict(lambda: {"n":0,"fired":0,"det":0})
    for r in rows:
        f = fired.get(r["key"])
        if f is None: continue
        b = by[r["grade"]]; b["n"]+=1; b["fired"]+=int(f["entries"]>0); b["det"]+=int(f["signals"]>0)
    clean = {"n":0,"fired":0}
    for r in rows:
        f = fired.get(r["key"])
        if f is None or r["grade"]!="none" or r["default_only_none"]: continue
        clean["n"]+=1; clean["fired"]+=int(f["entries"]>0)
    out = {"replayed":len(fired), "errors":len(errs),
           "by_grade":{g:{**v,"recall_pct":round(v["fired"]/max(1,v["n"])*100,1),
                          "detect_pct":round(v["det"]/max(1,v["n"])*100,1)} for g,v in sorted(by.items())},
           "none_clean_of_page_default": {**clean, "recall_pct": round(clean["fired"]/max(1,clean["n"])*100,1)},
           "n_default_only_none_days": sum(1 for r in rows if r["default_only_none"])}
    pairs = {}
    gs = ["S","A","C","none"]
    for i in range(len(gs)):
        for j in range(i+1,len(gs)):
            a,b_ = gs[i],gs[j]
            z,p = ztest(by[a]["fired"],by[a]["n"],by[b_]["fired"],by[b_]["n"])
            pairs["%s_vs_%s"%(a,b_)] = {"z":round(z,3),"p":round(p,4)}
    z,p = ztest(by["S"]["fired"],by["S"]["n"],clean["fired"],clean["n"])
    pairs["S_vs_none_cleaned"] = {"z":round(z,3),"p":round(p,4)}
    out["pairwise_z"] = pairs
    out["bonferroni_6"] = {k:round(min(1.0,v["p"]*6),4) for k,v in pairs.items() if k!="S_vs_none_cleaned"}
    print(json.dumps(out, indent=2))
    json.dump({**out,"fired":fired,"errors_detail":errs[:40]},
              open(os.path.join(HERE,"g71_verify_samplesize_replay.json"),"w",encoding="utf-8"), indent=2)

if __name__ == "__main__":
    main()
