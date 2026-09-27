import json
for f in [r"..\v2-t01-orb-1m\trades_MNQ_OR5_1030_D1_strong.json", r"..\v3-a2-s-detector\fires_all.json"]:
    t=json.load(open(f)); print(type(t).__name__, len(t))
    x = t[:2] if isinstance(t,list) else {k:(str(v)[:300]) for k,v in list(t.items())[:3]}
    print(str(x)[:700])
