import re,sys
pat=re.compile(sys.argv[2],re.I)
t=open(f'tx/{sys.argv[1]}_transcript.txt').read().replace('\n',' ')
t=re.sub(r'\s+',' ',t)
ss=re.split(r'(?<=[.?!])\s+',t)
out=[s for s in ss if pat.search(s)]
n=int(sys.argv[3]) if len(sys.argv)>3 else 40
for s in out[:n]: print('-',s[:300])
