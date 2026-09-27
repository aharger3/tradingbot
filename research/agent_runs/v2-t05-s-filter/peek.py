import json
d=json.load(open(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s01-s-trades\s_rows.json"))
print(type(d),len(d)); print(d[0])
import collections as C
print(C.Counter((m['g'],m['sym']) for m in d if m['sym'] in ('SPY','QQQ')))
