import json,re,collections,os
H=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(H,"g71_ladderv_instr_book.json")))
rows=d["trades"]; tr=[t for t in rows if t.get("traded")]
FL="[floor B: first with-trend signal of the day]"
tag=re.compile(r"\{\{pa=(\w+|None)\|stk=(\d)\}\}")
def parse(t):
    m=tag.search(t.get("reason") or "")
    return (m.group(1),m.group(2)=="1") if m else (None,None)
print("traded=%d"%len(tr))
buck=lambda t: "floor" if FL in t["reason"] else ("xlift" if "[x-lift:" in t["reason"] else "neither")
c=collections.Counter(buck(t) for t in tr); print(dict(c))
print("\nRAW _grade_trade verdict by bucket (final grade in parens):")
for b in ("floor","xlift","neither"):
    rs=[t for t in tr if buck(t)==b]
    print(" %-8s n=%4d  raw=%s"%(b,len(rs),dict(collections.Counter(parse(t)[0] for t in rs))))
nei=[t for t in tr if buck(t)=="neither"]
print("\nNEITHER bucket -- raw verdict x aplus_stack x final grade:")
for k,v in collections.Counter((parse(t)[0],parse(t)[1],t["grade"],t["setup"]) for t in nei).most_common(30):
    print("   raw=%-3s stack=%-5s final=%-3s %-18s %d"%(k[0],k[1],k[2],k[3],v))
untr=[t for t in nei if parse(t)[0] in ("C","X","D")]
print("\nNEITHER rows whose RAW _grade_pa verdict was NOT tradeable (C/X/D): %d"%len(untr))
print("  -> promoted untagged at the emission site (A+ stack floor sr:2768/:3052 etc)")
print("  raw dist:",dict(collections.Counter(parse(t)[0] for t in untr)))
print("  all carry aplus_stack=True? ", all(parse(t)[1] for t in untr))
gp=len(nei)-len(untr)
print("\nTRUE _grade_pa-selected traded rows: %d / %d = %.1f%%"%(gp,len(tr),100.0*gp/len(tr)))
print("claim said 485 / 2437 = 19.9%%; error = +%d rows"%(485-gp))
