import json
d=json.load(open(r'C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t02-break-retest\results.json'))
for r in d['grid']:
    if r['levels']=='PRE' and r['stop']=='LVL' and r['tgt']==3:
        print({k:v for k,v in r.items() if not isinstance(v,(list,dict))})
print('familywise_p', d['familywise_p'])
es=[r['R_es'] for r in d['grid']]; print('ES R range', min(es), max(es), 'n>0', sum(x>0 for x in es))
g=d['gates']['PRE/LVL/3R']; print('eval_ready', sum(v['eval_ready'] for v in g.values()), '/', len(g))
