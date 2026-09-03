"""Does 09:30-11:00 return redundancy PREDICT anything the money/durability
gates care about? The claim uses maxcorr to disqualify NVDA. Test the
premise across all 105 trios that research/g71_symbols_trio.py already scored."""
import json, os, statistics
HERE=os.path.dirname(os.path.abspath(__file__))
d=json.load(open(os.path.join(HERE,'g71_symbols_trio.json')))
def pear(xs,ys):
    mx,my=statistics.fmean(xs),statistics.fmean(ys)
    n=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    dx=sum((x-mx)**2 for x in xs)**.5; dy=sum((y-my)**2 for y in ys)**.5
    return n/(dx*dy)
c=[t['maxcorr'] for t in d]
print('n trios',len(d))
for f in ['meanR','green','win','n','heldout_S']:
    print('  corr(maxcorr, %-9s) = %+.3f' % (f, pear(c,[t[f] for t in d])))
# excluding QQQ trios (maxcorr dominated by SPY-QQQ 0.91, a mechanical outlier)
e=[t for t in d if 'QQQ' not in t['trio']]
ce=[t['maxcorr'] for t in e]
print('\nexcluding QQQ trios, n=%d'%len(e))
for f in ['meanR','green','win','heldout_S']:
    print('  corr(maxcorr, %-9s) = %+.3f' % (f, pear(ce,[t[f] for t in e])))
print('\ntop-5 trios by green months, with their maxcorr:')
for t in sorted(e,key=lambda t:(-t['green'],-t['meanR']))[:6]:
    print('  %-18s green %2d/%d  meanR %+.4f  n=%4d  maxcorr %.2f' %
          (t['trio'],t['green'],t['months'],t['meanR'],t['n'],t['maxcorr']))
print('\nlowest-5 maxcorr trios:')
for t in sorted(e,key=lambda t:t['maxcorr'])[:6]:
    print('  %-18s green %2d/%d  meanR %+.4f  n=%4d  maxcorr %.2f' %
          (t['trio'],t['green'],t['months'],t['meanR'],t['n'],t['maxcorr']))
print('\nthe two trios the claim compares:')
for t in d:
    if t['trio'] in ('SPY+TSLA+AAPL','SPY+TSLA+NVDA','SPY+NVDA+GOOGL','SPY+AAPL+ORCL'):
        print('  %-18s green %2d/%d  meanR %+.4f [%.3f,%.3f] n=%4d  maxcorr %.2f  heldout_S %d' %
              (t['trio'],t['green'],t['months'],t['meanR'],t['lo'],t['hi'],t['n'],t['maxcorr'],t['heldout_S']))
