import json,os
p=r"C:\Users\aharg\Desktop\Projects\tradingbot\research\marks_pool.json"
print(os.path.getsize(p))
d=json.load(open(p))
print(type(d))
if isinstance(d,dict):
    for k,v in list(d.items())[:6]: print(k, str(v)[:800])
else:
    print(len(d)); 
    for r in d[:3]: print(str(r)[:800])
