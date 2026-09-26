import re,sys
pat=re.compile(sys.argv[2],re.I); W=int(sys.argv[4]) if len(sys.argv)>4 else 22
w=open(f'tx/{sys.argv[1]}_transcript.txt').read().split()
hits=[i for i,x in enumerate(w) if pat.search(' '.join(w[i:i+3]))]
spans=[]
for i in hits:
    a,b=max(0,i-W),min(len(w),i+W)
    if spans and a<=spans[-1][1]: spans[-1][1]=b
    else: spans.append([a,b])
n=int(sys.argv[3])
for a,b in spans[:n]: print('-',' '.join(w[a:b]))
print('words',len(w),'spans',len(spans))
