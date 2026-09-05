import json,os,sys
HERE=os.path.abspath('research'); ROOT=os.path.dirname(HERE)
sys.path.insert(0,ROOT); sys.path.insert(0,HERE)
import importlib.util
spec=importlib.util.spec_from_file_location("g154amb", os.path.join(HERE,"g154_rule_ambiguous-stop-candidates.py"))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import marks_pool
blob=json.load(open(m.BOOK_PATH,encoding="utf-8"))
byday=m.by_day_candidates(blob["trades"]); pool=marks_pool.canonical_pool()
b=m.pick_first_of_day(byday,False); a=m.pick_first_of_day(byday,True)
bd={r["day"]:r for r in b}; ad={r["day"]:r for r in a}
tot=0
for d in sorted(bd):
    x,y=bd[d],ad.get(d)
    if y is None or x is y: continue
    tot+=1
    gx=pool.get("%s_%s"%(x["sym"],x["day"])); gy=pool.get("%s_%s"%(y["sym"],y["day"]))
    print("%s  %s(%s, pnl %+.0f, grade %s) -> %s(%s, pnl %+.0f, grade %s)"%(
        d,x["sym"],x["et"],x["pnl"],gx.grade if gx else "-",y["sym"],y["et"],y["pnl"],gy.grade if gy else "-"))
print("changed days:",tot,"  pnl delta total: %+.0f"%(sum(ad[d]["pnl"] for d in ad)-sum(bd[d]["pnl"] for d in bd)))
# direction against his grades
import math
S=(31,295); NONE=(38,405)
print("ambiguous rate  S %.1f%%  A 12.2%%  none %.1f%%  -> refusal-indicator points the WRONG way"%(S[0]/S[1]*100,NONE[0]/NONE[1]*100))
p=(S[0]+NONE[0])/(S[1]+NONE[1]); se=math.sqrt(p*(1-p)*(1/S[1]+1/NONE[1]))
z=(S[0]/S[1]-NONE[0]/NONE[1])/se
print("S vs none two-proportion z = %+.2f (p=%.2f) -- not distinguishable"%(z, 2*(1-0.5*(1+math.erf(abs(z)/math.sqrt(2))))))
