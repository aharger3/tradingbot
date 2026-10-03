"""Descriptive diagnostics on e6_results.json (exploratory, never used for selection)."""
import json, os, numpy as np
here = os.path.dirname(os.path.abspath(__file__))
o = json.load(open(os.path.join(here, "e6_results.json")))
COMM, USD = 1.24, 2.0
print("key n meanR grossR(no comm) medDist costR | stopwins n/meanR | rest n/meanR")
for k, T in o["trades"].items():
    if not T: continue
    R = np.array([t["R"] for t in T]); d = np.array([t["dist"] for t in T]); c = COMM / (d * USD)
    sw = [t["R"] for t in T if t.get("how") == "stopwins"]; rs = [t["R"] for t in T if t.get("how") == "rest"]
    print(k, len(T), round(R.mean(), 3), round((R + c).mean(), 3), round(float(np.median(d)), 2), round(c.mean(), 3), "|",
          len(sw), round(float(np.mean(sw)), 3) if sw else None, "|", len(rs), round(float(np.mean(rs)), 3) if rs else None)
m1 = o["M1_first_run_optimistic_not_primary"]
print("M1 (optimistic, not primary):")
for k, v in m1["variants"].items():
    print(k, v["n"], round(v["meanR"], 3), "H1", round(v["h1_R"], 3), "H2", round(v["h2_R"], 3), "pB0", v.get("paired_p_vs_B0"))
print("M1 best", m1["best"])
