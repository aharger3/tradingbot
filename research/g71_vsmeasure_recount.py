"""Independent re-count of the smeasure claim. Read-only."""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import research.build_deck as bd

SCALAR = ("austin_tier","tier","austin_grade","grade","verdict")
ANS    = ("grade","your_grade","s","s_call")

def is_s(v):
    return str(v).strip().lower() == "s"

scalar_s, ans_s = set(), set()
field_hits = collections.Counter()
per_file = collections.defaultdict(lambda: [0,0,0])  # keys, scalarS, ansS
for path in bd.mark_sources():
    name = os.path.relpath(path, HERE).replace("\\","/")
    for r in bd._rows(path):
        k = bd._judgement_key(r)
        if not k: continue
        per_file[name][0] += 1
        for f in SCALAR:
            if is_s(r.get(f, "")):
                scalar_s.add(k); field_hits["scalar."+f] += 1; per_file[name][1]+=1
        a = r.get("answers")
        if isinstance(a, dict):
            for f in ANS:
                v = a.get(f)
                if not v: continue
                first = v[0] if isinstance(v, list) else v
                if is_s(first):
                    ans_s.add(k); field_hits["answers."+f] += 1; per_file[name][2]+=1

only_ans = ans_s - scalar_s
print(json.dumps({
 "guard_keys": len(bd.marked_card_ids()),
 "S_scalar": len(scalar_s), "S_answers": len(ans_s),
 "S_only_answers": len(only_ans), "S_union": len(scalar_s | ans_s),
 "S_both": len(scalar_s & ans_s),
 "field_row_hits": dict(field_hits)}, indent=2))
print("\nper file  keys/scalarS/ansS")
for n,(a,b,c) in per_file.items(): print("  %-52s %4d %4d %4d" % (n,a,b,c))
print("\nonly-in-answers sample:", sorted(only_ans)[:12])
