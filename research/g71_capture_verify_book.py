import json, collections
d = json.load(open("research/bt2y_trades.json"))
print("meta:", {k:v for k,v in d["meta"].items()})
rows = [r for r in d["trades"] if isinstance(r, dict) and r.get("status") == "fired"]
rs = [r["r"] for r in rows if isinstance(r.get("r"), (int,float))]
losses = [x for x in rs if x < 0]
print("fired n:", len(rows), "with r:", len(rs), "losses:", len(losses))
print("min r %.4f | worse than -1.0R: %d | == -1.0R: %d"
      % (min(rs), sum(1 for x in rs if x < -1.0-1e-9), sum(1 for x in rs if abs(x+1.0)<1e-9)))
print("buckets:", collections.Counter(round(x,3) for x in losses).most_common(6))
print("mean r %.4f  win%% %.1f" % (sum(rs)/len(rs), 100*sum(1 for x in rs if x>0)/len(rs)))
