"""ADVERSARIAL VERIFY of the g71_scanners S-funnel claim. Read-only over the book."""
import json, collections, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
d = json.load(open(ROOT/"research"/"bt2y_trades.json", encoding="utf-8"))
rows = d["trades"]; print("meta:", d["meta"])
S = [r for r in rows if r["sgrade"]=="S"]

# 1. aligned distribution + _grade_pa D-rate conditional on NOT vetoed
def tab(name, rs):
    n=len(rs)
    c=collections.Counter(r["aligned"] for r in rs)
    print("%-8s n=%6d  aligned: %s" % (name,n,dict(c)))
    exposed=[r for r in rs if r["aligned"]!="against"]
    x=sum(1 for r in exposed if r["grade"]=="X")
    print("         exposed to _grade_pa (aligned!=against): %d, of which X=%d (%.1f%%)" % (len(exposed),x,100*x/len(exposed)))
    for a in ("with","n/a"):
        sub=[r for r in rs if r["aligned"]==a]
        if sub:
            xx=sum(1 for r in sub if r["grade"]=="X")
            print("           aligned=%-4s n=%6d  X=%6d (%.1f%%)" % (a,len(sub),xx,100*xx/len(sub)))
    vet=[r for r in rs if r["aligned"]=="against"]
    xv=sum(1 for r in vet if r["grade"]=="X")
    print("           aligned=against n=%6d  X=%6d (%.1f%%)  <- veto short-circuits, _grade_pa never ran" % (len(vet),xv,100*xv/len(vet)))
    return len(exposed), x, len(vet)
ea,xa,va = tab("ALL",rows)
es,xs,vs = tab("sgrade S",S)

print("\n--- marginal (counterfactual) kill attributable to HTF veto ---")
for name,(e,x,v) in (("ALL",(ea,xa,va)),("S",(es,xs,vs))):
    base = x/e
    survive = v*(1-base)
    tot = len([r for r in rows if r["sgrade"]=="S"]) if name=="S" else len(rows)
    print("%-4s veto-killed=%d ; base _grade_pa D-rate on non-vetoed=%.3f ; expected to survive _grade_pa if veto lifted=%.0f (%.1f%% of all %s rows) vs first-blame %.1f%%"
          % (name,v,base,survive,100*survive/tot,name,100*v/tot))

# 2. is the S kill-rate actually different from non-S?  chi-sq 2x2 on traded
import math
nS=len(S); tS=sum(1 for r in S if r["traded"])
NS=[r for r in rows if r["sgrade"]!="S"]; nN=len(NS); tN=sum(1 for r in NS if r["traded"])
print("\nS traded %d/%d = %.3f%% ; non-S traded %d/%d = %.3f%%" % (tS,nS,100*tS/nS,tN,nN,100*tN/nN))

# 3. does sgrade S actually pick better trades among those that DID trade?
tr=[r for r in rows if r["traded"]]
for g in ("S","A","C","n/a"):
    sub=[r["r"] for r in tr if r["sgrade"]==g]
    if sub:
        m=statistics.fmean(sub); sd=statistics.pstdev(sub)
        print("traded sgrade=%-4s n=%4d win%%=%5.1f meanR=%+.4f  se=%.4f  95%%CI=[%+.3f,%+.3f]"
              % (g,len(sub),100*sum(1 for x in sub if x>0)/len(sub),m,sd/math.sqrt(len(sub)),
                 m-1.96*sd/math.sqrt(len(sub)), m+1.96*sd/math.sqrt(len(sub))))

# 4. downgrade vocabulary actually present in the book
c=collections.Counter()
for r in rows: c.update(r["downgrades"])
print("\ndowngrade variables present:", dict(c))
