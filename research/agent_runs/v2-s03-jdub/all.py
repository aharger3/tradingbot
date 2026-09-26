import re,sys,glob,collections
pat=re.compile(sys.argv[1],re.I); W=int(sys.argv[2]); cap=int(sys.argv[3])
c=collections.Counter(); out=[]
for f in sorted(glob.glob('tx/*_transcript.txt')):
    vid=f[3:].replace('_transcript.txt','')
    t=re.sub(r'\s+',' ',open(f).read()); w=t.split()
    s=' '.join(w).lower()
    for m in pat.finditer(s):
        c[vid]+=1
        i=len(s[:m.start()].split())
        if c[vid]<=cap: out.append((vid,' '.join(w[max(0,i-W):i+W])))
for v,x in out: print(v,'|',x)
print(sum(c.values()),'hits in',len(c),'videos')
