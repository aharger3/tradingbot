import json
d = json.load(open(r'C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t03-one-candle\t03_result_ES_NQ.json'))
rows = d['grid']; rows = rows if isinstance(rows, list) else list(rows.values())
print(json.dumps(rows[0])[:300])
def R(x): return x.get('R_net', x.get('meanR', x.get('netR'))) if isinstance(x, dict) else x
both = [(r['mode'], r['zone'], r['age'], r['kR'], R(r['h1']), R(r['h2'])) for r in rows]
print('both+', sum(1 for b in both if (b[4] or 0) > 0 and (b[5] or 0) > 0), 'best all', max(R(r['all']) for r in rows))
