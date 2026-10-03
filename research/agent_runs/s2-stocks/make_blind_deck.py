"""Arm B sample for the S2 pre-registration: 300 unmarked, simmable engine candidates (signal 09:35-10:30), seeded, uniform.
Output has NO outcome columns on purpose (the deck must be graded blind). Usage: python make_blind_deck.py CANDS_PICKLE OUT.csv"""
import sys, pickle, csv
import numpy as np
import s2_lib as L
from s2_run import marked_filter
C = pickle.load(open(sys.argv[1], "rb"))
S_all = [x for x in L.run_sim(L.load_s_rows()) if x["r"] is not None]
pool = [x for x in marked_filter(C, S_all) if 575 <= x["m"] <= 630]
pool.sort(key=lambda x: (x["day"], x["sym"], x["m"], x["side"]))
rng = np.random.default_rng(20261003)
pick = sorted(rng.choice(len(pool), size=300, replace=False))
with open(sys.argv[2], "w", newline="") as f:
    w = csv.writer(f); w.writerow(["n", "sym", "day", "signal_t", "side", "engine_stop"])
    for k, i in enumerate(pick, 1):
        x = pool[i]; w.writerow([k, x["sym"], x["day"], "%02d:%02d" % divmod(x["m"], 60), "long" if x["side"] > 0 else "short", x["stop"]])
print(len(pool), "eligible; 300 written")
