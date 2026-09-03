import json, collections
p="research/marks/probe_s_sweep_2026-08-28.jsonl"
rows=[json.loads(l) for l in open(p) if l.strip()]
print("rows",len(rows))
print("keys sample",sorted(rows[0].keys()))
gr=collections.Counter(r.get("grade") for r in rows)
print("grade field:",dict(gr))
ans=collections.Counter(tuple(r.get("answers",{}).get("s",[])) for r in rows)
print("answers.s:",dict(ans))
S=[r for r in rows if r.get("answers",{}).get("s")==["s"]]
print("S count",len(S))
per=collections.Counter(r["symbol"] for r in S)
cards=collections.Counter(r["symbol"] for r in rows)
print("distinct symbols in file",len(cards),"distinct symbols among S",len(per))
for sym,c in cards.most_common():
    print(f"{sym:6s} cards={c:2d} S={per.get(sym,0)}")
for combo in [("SPY","TSLA","AAPL"),("SPY","TSLA","NVDA"),("SPY","QQQ","TSLA"),("SPY","TSLA","AMD")]:
    print(combo,"cards",sum(cards.get(s,0) for s in combo),"S",sum(per.get(s,0) for s in combo))
