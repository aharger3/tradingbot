"""G71/rule84verify: adversarial re-check of the 'accidental 0.2R reclaim tolerance' claim.
Read-only. Book: research/bt2y_trades.json (current post-T23 book)."""
import json, collections, statistics as st
B = json.load(open('research/bt2y_trades.json', encoding='utf-8'))
T = B['trades']; m = B['meta']
print("BOOK", m['first'], m['last'], m['sessions'], "sessions", len(T), "signals",
      sum(1 for r in T if r['traded']), "traded")

def ratio(r):
    d = r['entry'] - r['stop']
    if d == 0: return None
    return round((r['target'] - r['entry']) / d, 4)

# 1. the prior agent's exact denominator: traded BR call rows
br = [r for r in T if r['traded'] and r['setup'] == 'break_and_retest'
      and r['dir'] == 'call' and r['entry'] != r['stop']]
c = collections.Counter(ratio(r) for r in br)
print("\nA) traded BR dir=call n=%d  top:" % len(br), c.most_common(4))
print("   share at exactly 2.0000: %d/%d = %.1f%%" % (c[2.0], len(br), 100*c[2.0]/len(br)))

# 2. the CORRECT denominator: the arming pool = traded losses on an arming setup
ARM = ('break_and_retest', 'one_candle_rule')
pool = [r for r in T if r['traded'] and r['out'] == 'loss' and r['setup'] in ARM
        and r['entry'] != r['stop']]
c2 = collections.Counter(ratio(r) for r in pool)
print("\nB) ARMING POOL (traded, out=loss, setup in BR/OCR) n=%d" % len(pool))
print("   top:", c2.most_common(6))
print("   share at exactly 2.0000: %d/%d = %.1f%%" % (c2[2.0], len(pool), 100*c2[2.0]/len(pool)))
# implied cap d_max solving (tgt-c)=1.5*(c-stop) with c=E+d*R
caps = []
for r in pool:
    R = r['entry'] - r['stop']
    k = (r['target'] - r['entry']) / R          # target ratio in R
    d = (k - 1.5) / 2.5                          # d_max in R
    caps.append(round(d, 4))
cc = collections.Counter(caps)
print("   implied d_max (R) distribution, top:", cc.most_common(6))
print("   d_max: min %.4f  median %.4f  max %.4f  frac==0.2: %.1f%%"
      % (min(caps), st.median(caps), max(caps), 100*cc[0.2]/len(caps)))
print("   d_max <= 0 (rr_ok can NEVER pass): %d rows" % sum(1 for d in caps if d <= 0))

# 3. per-direction split (claim says one-sided)
for side in ('call', 'put'):
    p = [r for r in pool if r['dir'] == side]
    print("   dir=%s n=%d  ratio top %s" % (side, len(p),
          collections.Counter(ratio(r) for r in p).most_common(3)))

# 4. is the 84 branch reachable / did it fire
r84 = [r for r in T if r['setup'] == 'reentry_84_rule']
print("\nC) reentry_84_rule detections %d traded %d  status %s"
      % (len(r84), sum(1 for r in r84 if r['traded']),
         collections.Counter(r['status'] for r in r84).most_common()))
