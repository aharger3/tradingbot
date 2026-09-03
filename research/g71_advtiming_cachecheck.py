"""Cache fidelity: rebuild earlier_candidates from a live sim_day replay for a
random sample of the 203 swap rows and compare against g71_timing_params.json."""
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import g71_timing as G
from signal_runner import min_risk_floor

book = json.load(open(G.BOOK, encoding="utf-8"))
rows = [r for r in book["trades"] if r["status"] == "fired" and r["traded"]]
G.load_or_build_index(rows)
cand_rows = [n for n in G._CANDS if any(
    c["status"] != "skipped_tight_stop" and abs(c["entry"] - c["stop"]) >= min_risk_floor(c["entry"])
    for c in G._CANDS[n])]
rnd = random.Random(31)
sample = rnd.sample(sorted(cand_rows), 12)
bad = 0
for n in sample:
    r = rows[n]
    src = G.match(n)
    # rebuild the SimTrade for this row from a live replay, then its candidates
    live = None
    for t in G.sim_day(r["sym"], r["day"]):
        if not t.counted: continue
        if G._key(t.entry_idx, t.signal_type, t.direction, t.entry, t.stop, t.target) == \
           G._key(r["entry_i"], r["setup"], r["dir"], r["entry"], r["stop"], r["target"]):
            live = t; break
    if live is None:
        print("  row %d %s %s: NO LIVE MATCH" % (n, r["sym"], r["day"])); bad += 1; continue
    fresh = G.earlier_candidates(r["sym"], r["day"], live)
    cachd = G._CANDS[n]
    fk = [(c["off"], round(c["entry"], 4), round(c["stop"], 4), c["status"], c["grade"], c["sgrade"]) for c in fresh]
    ck = [(c["off"], round(c["entry"], 4), round(c["stop"], 4), c["status"], c["grade"], c["sgrade"]) for c in cachd]
    ok = fk == ck
    if not ok: bad += 1
    print("  row %4d %-5s %s cands fresh=%d cache=%d %s" % (n, r["sym"], r["day"], len(fk), len(ck), "OK" if ok else "MISMATCH"))
    if not ok:
        print("     fresh:", fk); print("     cache:", ck)
print("cache mismatches: %d of %d" % (bad, len(sample)))
