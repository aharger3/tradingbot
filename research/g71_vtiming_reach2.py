import sys, os, json, re
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE); sys.path.insert(0,ROOT)
import polygon_feed as pf
book=json.load(open(os.path.join(HERE,'bt2y_trades.json'),encoding='utf-8'))
rows=[r for r in book['trades'] if r['traded']]
pat=re.compile(r'\$(\d+\.\d+)')
through=past=tot=0; both=0
for r in rows:
    if r['setup']!='break_and_retest': continue
    m=pat.search(r['reason'] or '')
    if not m: continue
    lvl=float(m.group(1))
    try: rth=pf.rth(pf.fetch_day(r['sym'],r['day']))
    except Exception: continue
    i=r['entry_i']
    if i<1 or i>=len(rth): continue
    tot+=1; long=r['dir']=='call'
    t=(rth[i].close>lvl) if long else (rth[i].close<lvl)
    p=(rth[i].close>rth[i-1].close) if long else (rth[i].close<rth[i-1].close)
    through+=t; past+=p; both+= (t and p)
print("B&R traded rows with a parsed level price: %d" % tot)
print("  entry bar closes THROUGH the level : %d (%.1f%%)" % (through,100*through/tot))
print("  entry bar closes past close[i-1]   : %d (%.1f%%)" % (past,100*past/tot))
print("  both                               : %d (%.1f%%)" % (both,100*both/tot))
