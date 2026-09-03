"""Reachability probe: does detect_break_retest's step-4 CLOSE gate actually
fire, and does the entry bar really close through the level?"""
import sys, os, json, random
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE); sys.path.insert(0,ROOT)
import omen_bot as ob, polygon_feed as pf, backtest_week as bw
from backtest_12mo import hourly_from_1m
book=json.load(open(os.path.join(HERE,'bt2y_trades.json'),encoding='utf-8'))
rows=[r for r in book['trades'] if r['traded']]

# 1. branch reachability, over 40 real sessions replayed through the engine
days=sorted({(r['sym'],r['day']) for r in rows})
random.Random(3).shuffle(days)
before=dict(ob.BR_FUNNEL)
n=0
for sym,day in days[:40]:
    try:
        rth=pf.rth(pf.fetch_day(sym,day))
    except Exception: continue
    if len(rth)<30: continue
    for i in range(10,len(rth)):
        w=rth[:i+1]
        hi=max(c.high for c in rth[:15]); lo=min(c.low for c in rth[:15])
        ob.detect_break_retest(w,hi,is_long=True)
        ob.detect_break_retest(w,lo,is_long=False)
    n+=1
print("sessions probed:",n)
for k in ob.BR_FUNNEL:
    print("  %-18s %d" % (k, ob.BR_FUNNEL[k]-before.get(k,0)))

# 2. does the ENTRY bar close through the traded level, and past close[i-1]?
ok=through=past=tot=0
for r in rows:
    lvl=r.get('level')
    if lvl in (None,0) or r['setup']!='break_and_retest': continue
    try: rth=pf.rth(pf.fetch_day(r['sym'],r['day']))
    except Exception: continue
    i=r['entry_i']
    if i<1 or i>=len(rth): continue
    tot+=1
    long=r['dir']=='call'
    if (rth[i].close>lvl) if long else (rth[i].close<lvl): through+=1
    if (rth[i].close>rth[i-1].close) if long else (rth[i].close<rth[i-1].close): past+=1
print("\nB&R traded rows with a level: %d" % tot)
print("  entry bar closes THROUGH the level : %d (%.1f%%)" % (through,100*through/tot))
print("  entry bar closes past close[i-1]   : %d (%.1f%%)" % (past,100*past/tot))
