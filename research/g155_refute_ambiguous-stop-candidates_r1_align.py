import json,os,sys,random
HERE=os.path.abspath('research'); ROOT=os.path.dirname(HERE)
sys.path.insert(0,ROOT); sys.path.insert(0,HERE)
import importlib.util
spec=importlib.util.spec_from_file_location("g154amb", os.path.join(HERE,"g154_rule_ambiguous-stop-candidates.py"))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
blob=json.load(open(m.BOOK_PATH,encoding="utf-8"))
byday=m.by_day_candidates(blob["trades"])
all_c=[r for v in byday.values() for r in v]
sample=random.Random(7).sample(all_c,1500)
mis=[]
for r in sample:
    b=m.get_bars(r["sym"],r["day"]); i=r["entry_i"]
    if not b or i>=len(b): continue
    if abs(b[i].close-r["entry"])>1e-6: mis.append((r,b))
print("mismatch",len(mis))
for r,b in mis[:6]:
    i=r["entry_i"]
    print("%s %s et=%s entry_i=%d entry=%.4f  bar[i].ts=%s close=%.4f  bar[0].ts=%s"%(
        r["sym"],r["day"],r["et"],i,r["entry"],b[i].timestamp,b[i].close,b[0].timestamp))
    # search for a bar whose close matches
    hits=[j for j,x in enumerate(b) if abs(x.close-r["entry"])<1e-6]
    print("   closes matching entry at idx:",hits[:8])
# offset distribution for mismatches
from collections import Counter
off=Counter()
for r,b in mis:
    hits=[j for j,x in enumerate(b) if abs(x.close-r["entry"])<1e-6]
    if hits: off[min(hits,key=lambda j:abs(j-r["entry_i"]))-r["entry_i"]]+=1
    else: off["nomatch"]+=1
print("offset (nearest matching-close idx - entry_i):",off.most_common(12))
