import sys, json; sys.path.insert(0, r"C:\Users\aharg\Desktop\Projects\tradingbot-b1-prereg-cells\research\databento")
import cells
mnq = cells._mnq(); days = mnq.load_real(); W = (days[0]["date"], days[-1]["date"])
print("days", len(days), W, flush=True)
for nm in cells.CELLS:
    T, s = cells.run(nm, days, W, nshuf=0)
    print(nm, json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}), flush=True)
