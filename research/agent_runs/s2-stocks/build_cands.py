"""simulate every engine candidate in the fit window once and cache to a pickle (slow: ~2.5 min)."""
import sys, pickle, collections
import s2_lib as L
C = L.load_candidates()
C.sort(key=lambda x: (x["sym"], x["day"]))
L.run_sim(C)
print(len(C), sum(x["r"] is None for x in C), collections.Counter(x["how"] for x in C))
pickle.dump(C, open(sys.argv[1], "wb"))
