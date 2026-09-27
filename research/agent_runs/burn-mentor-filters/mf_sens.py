"""Sensitivity: PDH/PDL confluence width, and close-stop tail. Reads mf.py; paper research only."""
import numpy as np, mf
days = mf.load_real(); T = []
for k, A in enumerate(days):
    s = mf.signal(A)
    if not s: continue
    f = A["open"][s["i"]] + mf.TICK * s["side"]; d = (f - s["stop"]) * s["side"]
    if d < 2 * mf.TICK: continue
    T.append((k, s, f, d, mf.ex_trade(A, s["i"], s["side"], d)[0]))
R0 = np.array([t[4] for t in T]); print("n", len(T), "R", round(R0.mean(), 3), "min", round(R0.min(), 2))
for w in (0.5, 1, 2, 3, 5):
    for lv in (("pdh", "pdl"), ("pdh", "pdl", "onh", "onl")):
        m = [t[4] for t in T if any(days[t[0]][x] is not None and abs(t[1]["lvl"] - days[t[0]][x]) <= w * t[1]["atr"] for x in lv)]
        print("conf", w, "ATR", "+".join(lv), "n", len(m), "R", round(float(np.mean(m)), 3) if m else None)
cs = np.array([mf.ex_trade(days[t[0]], t[1]["i"], t[1]["side"], t[3], "closestop")[0] for t in T])
print("closestop min", round(cs.min(), 2), "p5", round(np.percentile(cs, 5), 2), "n<-1.5R", int((cs < -1.5).sum()), "base n<-1.5R", int((R0 < -1.5).sum()))
