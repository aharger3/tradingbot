import json
d=json.load(open(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t04-his-eye-test\eye_test.json"))
for k in ("post_1100","visible_future","per_source","ladder","S_dollars_per_session"): print(k,json.dumps(d[k]))
