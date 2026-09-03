import json, re, collections, os
B=os.path.join(os.path.dirname(os.path.abspath(__file__)),"bt2y_trades.json")
d=json.load(open(B)); rows=d["trades"]; tr=[t for t in rows if t.get("traded")]
FL="[floor B: first with-trend signal of the day]"
def has(t,s): return s in (t.get("reason") or "")
fl=[t for t in tr if has(t,FL)]
xl=[t for t in tr if "[x-lift:" in (t.get("reason") or "")]
both=[t for t in tr if has(t,FL) and "[x-lift:" in (t.get("reason") or "")]
nei=[t for t in tr if not has(t,FL) and "[x-lift:" not in (t.get("reason") or "")]
print("traded=%d floor=%d xlift=%d both=%d neither=%d sum=%d"%(len(tr),len(fl),len(xl),len(both),len(nei),len(fl)+len(xl)+len(nei)))
print("xlift arms:",collections.Counter(re.search(r"\[x-lift:(\w+)\]",t["reason"]).group(1) for t in xl))
print("xlift final grades:",collections.Counter(t["grade"] for t in xl))
pa=re.compile(r"\b(A\+|A|B|C|D|X) PA\b")
def pal(t):
    m=pa.search(t.get("reason") or ""); return m.group(1) if m else "(none)"
print("\nPA letter written into reason at emission:")
for lbl,rs in (("floor",fl),("xlift",xl),("neither",nei)):
    print(" %-8s %s"%(lbl,dict(collections.Counter(pal(t) for t in rs))))
print("\nneither: setup x final grade x PA-letter")
c=collections.Counter((t["setup"],t["grade"],pal(t)) for t in nei)
for k,v in c.most_common(20): print("  ",k,v)
print("\nneither: capped-C tag present?",sum(1 for t in nei if "capped C" in t["reason"]))
print("floor rows with 'capped C':",sum(1 for t in fl if "capped C" in t["reason"]))
