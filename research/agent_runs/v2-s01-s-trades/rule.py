import json,random,collections as C,sys,statistics as st
random.seed(5)
A=json.load(open(sys.argv[1]))  # sym,day,tso,setup,disp,retest,trig,ct,bbs,R,status
M=json.load(open(sys.argv[2]))
def mean(x): return sum(x)/len(x) if x else float('nan')
rules={
 "base (all engine candidates <11:00)":lambda r:True,
 "T: <=30 min after open":lambda r:r[2]<=30,
 "O: ORB or ORB+OCR":lambda r:r[3] in("ORB","ORB+OCR"),
 "D: displacement >=1.0 ATR":lambda r:r[4]>=1.0,
 "W: wick-touch retest, no close thru":lambda r:r[5]=="wick-touch" and not r[7],
 "P: hammer/pin or strong-body trigger":lambda r:r[6] in("hammer/pin","strong-body"),
}
rules["S-rule = T+O+D+W+P"]=lambda r:all(f(r) for k,f in list(rules.items())[1:6])
rules["S-rule minus W"]=lambda r:rules["T: <=30 min after open"](r) and rules["O: ORB or ORB+OCR"](r) and r[4]>=1.0 and rules["P: hammer/pin or strong-body trigger"](r)
rules["S-rule, 10:45 window (<=75)"]=lambda r:r[2]<=75 and r[3] in("ORB","ORB+OCR") and r[4]>=1.0 and r[5]=="wick-touch" and not r[7] and r[6] in("hammer/pin","strong-body")
bkt=lambda r:r[2]//15
pool=C.defaultdict(list)
for r in A: pool[bkt(r)].append(r[9])
print("rule | n | win | meanR | H1 n/R | H2 n/R | time-matched null R | p")
for k,f in rules.items():
    s=[r for r in A if f(r)]; Rs=[r[9] for r in s]
    h1=[r[9] for r in s if r[1]<"2025-09-29"]; h2=[r[9] for r in s if r[1]>="2025-09-29"]
    if k.startswith("base"): print(k,len(s),round(sum(x>0 for x in Rs)/len(Rs),3),round(mean(Rs),3),len(h1),round(mean(h1),3),len(h2),round(mean(h2),3)); continue
    bk=[bkt(r) for r in s]; nulls=[]
    for _ in range(500):
        nulls.append(mean([random.choice(pool[b]) for b in bk]))
    p=(1+sum(n>=mean(Rs) for n in nulls))/501
    print(k,len(s),round(sum(x>0 for x in Rs)/len(Rs),3),round(mean(Rs),3),len(h1),round(mean(h1),3),len(h2),round(mean(h2),3),round(mean(nulls),3),round(p,4))
# his grades vs rule
print("\nhis marks meeting each rule (%)")
def asrow(m): return [m["sym"],m["day"],m["tso"],m["setup"],m.get("disp_atr") or 0,m.get("retest"),m.get("trig"),m.get("closed_thru_since_first_break"),m.get("bars_brk_to_sig"),m.get("R") or 0,""]
for k,f in rules.items():
    out=[]
    for g in("S","A","C"):
        v=[m for m in M if m["g"]==g]; n=sum(1 for m in v if f(asrow(m))); out.append(f"{g} {n}/{len(v)} ({100*n/len(v):.0f}%)")
    print(k,"|"," | ".join(out))
print("\nclose-through since first break by grade")
for g in("S","A","C"):
    v=[m for m in M if m["g"]==g]; print(g,C.Counter(m.get("closed_thru_since_first_break") for m in v))
