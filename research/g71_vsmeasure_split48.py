"""Are the 48 'answers-only S' days truly invisible, or visible-with-another-grade? Read-only."""
import json, os, sys, collections
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,ROOT); sys.path.insert(0,HERE)
import research.build_deck as bd
SCALAR=("austin_tier","tier","austin_grade","grade","verdict")
ANS=("grade","your_grade","s","s_call")
scal=collections.defaultdict(set); ansS=set(); scalS=set()
for path in bd.mark_sources():
    n=os.path.relpath(path,HERE).replace("\\","/")
    for r in bd._rows(path):
        k=bd._judgement_key(r)
        if not k: continue
        for f in SCALAR:
            v=str(r.get(f,"")).strip().lower()
            if v and v not in ("none","null",""):
                scal[k].add(v)
                if v=="s": scalS.add(k)
        a=r.get("answers")
        if isinstance(a,dict):
            for f in ANS:
                v=a.get(f)
                if not v: continue
                fv=str((v[0] if isinstance(v,list) else v)).strip().lower()
                if fv=="s": ansS.add(k)
only=ansS-scalS
noscalar=[k for k in only if not scal.get(k)]
withscalar={k:sorted(scal[k]) for k in only if scal.get(k)}
print("only-in-answers S:",len(only))
print("  no scalar grade anywhere (truly invisible):",len(noscalar))
print("  HAS a non-S scalar grade elsewhere (visible, contradicted):",len(withscalar))
print(json.dumps(collections.Counter(tuple(v) for v in withscalar.values()).most_common(),default=str))
print("sample contradicted:",list(withscalar.items())[:10])
