import gzip,json,collections,statistics as st
d=json.load(gzip.open(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\tape\g88_post_floor_trades.json.gz"))
T=d["trades"]
print("syms",sorted(collections.Counter(t["sym"] for t in T).items()))
print("fill_i>signal_i",sum(t["fill_i"]>t["signal_i"] for t in T),"of",len(T))
print("outs",collections.Counter(t["out"] for t in T))
print("r dist",collections.Counter(round(t["r"],1) for t in T).most_common(12))
print("risk median",st.median(t["risk"] for t in T),"entry median",st.median(t["entry"] for t in T))
print("sgrade",collections.Counter(t.get("sgrade") for t in T))
print("setup",collections.Counter(t.get("setup") for t in T))
print("trades/day max",max(collections.Counter(t["day"] for t in T).values()))
