"""REFUTER #2 (multiplicity + sampling error) for the g154 claim
"be-stop-after-enough-past-pt1 survives at k=0.50R".

Fill named, per CLAUDE.md: entry = the signal bar CLOSE (the book's own
`entry`); stops via stop_rule.stop_hit_on_close + stop_rule.stop_fill_price;
disaster stop stop_rule.disaster_stop_price at DISASTER_STOP_R = 1.0;
one-trade-a-day unit = omen_metrics.first_of_day_arm(size_gate=True) with the
signal_runner.min_risk_floor size gate; 1R = $1,000. Book
research/bt2y_trades_retest_on.json, 498 sessions, H1/H2 split 2025-09-01.

This reuses the CLAIM SCRIPT'S OWN _sim(), imported unmodified, so nothing
here is a re-implementation that could disagree for its own reasons.

  A. FINE k GRID -- k in 0.125..2.0 step 0.125 (16 points) against the same
     no-BE control. A real "far enough past PT1" threshold should be smooth.
     An isolated one-point spike is the signature of noise.
  B. PAIRED BOOTSTRAP over the 498 sessions (10k resamples) of the per-day
     dollar delta (k=0.5 arm minus no-BE control): overall, H1, H2.
  C1. SELECTION STABILITY -- inside each resample, re-pick the best k by
     full-sample $/day exactly as the claim script does; how often is it 0.5?
  C2. CENTERED NULL -- de-mean each published arm's per-day delta so the true
     effect is exactly zero, then measure how often ANY of the 4 published k
     arms clears the claim's survivor gate (H1 delta > 0 AND H2 delta > 0).
     That is the family-wise false-positive rate of the gate itself.
"""
import json
import os
import sys
import random
import importlib.util
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

spec = importlib.util.spec_from_file_location(
    "g154be", os.path.join(HERE, "g154_rule_be-stop-after-enough-past-pt1.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

import omen_metrics as om              # noqa: E402
from t8_two_year import rth_candles    # noqa: E402

H_SPLIT = "2025-09-01"
RISK = G.g86.RISK
FINE_K = [round(0.125 * i, 3) for i in range(1, 17)]     # 0.125 .. 2.0
PUBLISHED_K = [0.25, 0.5, 0.75, 1.0]
CACHE = os.path.join(HERE, "g154_refute2_be_kgrid.json")


def build_cache():
    blob = json.load(open(G.BOOK_PATH, encoding="utf-8"))
    rows = blob["trades"]
    firsts = om.first_of_day_arm(rows, size_gate=True)
    out = []
    for row in firsts:
        rec = {"day": row["day"], "sym": row["sym"], "book_r": row.get("r"),
               "base": None, "k": {}, "fallback": False}
        bars = rth_candles(row["sym"], row["day"])
        idx = None
        if bars:
            ts = row["et"] + ":00"
            idx = next((i for i, c in enumerate(bars) if c.timestamp == ts), None)
        tgt = row.get("target")
        if (not bars) or idx is None or tgt is None or abs(row["entry"] - row["stop"]) <= 0:
            rec["fallback"] = True
            out.append(rec)
            continue
        e, s, long = row["entry"], row["stop"], row["dir"] == "call"
        rec["risk"] = abs(e - s)
        rec["target_r"] = (tgt - e) / rec["risk"] if long else (e - tgt) / rec["risk"]
        b = G._sim(bars, idx, e, s, tgt, long, k=None)
        rec["base"] = b
        for k in FINE_K:
            rec["k"][str(k)] = G._sim(bars, idx, e, s, tgt, long, k=k)
        out.append(rec)
    json.dump(out, open(CACHE, "w"), indent=0)
    return out


def rval(rec, key):
    """R booked for one pick under arm `key`, with the claim script's own
    fallback convention (the book's own r when the replay is unavailable)."""
    if rec["fallback"] or rec["base"] is None:
        return rec["book_r"] or 0.0
    if key == "base":
        return rec["base"]
    v = rec["k"].get(key)
    return v if v is not None else rec["base"]


def per_day(recs, key, days):
    d = defaultdict(float)
    for r in recs:
        d[r["day"]] += rval(r, key) * RISK
    return [d.get(x, 0.0) for x in days]


def main():
    if os.path.exists(CACHE):
        recs = json.load(open(CACHE))
        print("cache hit: %s" % os.path.basename(CACHE))
    else:
        recs = build_cache()
    days = sorted({r["day"] for r in recs})
    h1 = [i for i, d in enumerate(days) if d < H_SPLIT]
    h2 = [i for i, d in enumerate(days) if d >= H_SPLIT]
    n, n1, n2 = len(days), len(h1), len(h2)
    nfb = sum(1 for r in recs if r["fallback"] or r["base"] is None)
    print("picks %d  sessions %d (H1 %d / H2 %d)  fallbacks %d" % (len(recs), n, n1, n2, nfb))

    tr = sorted(r["target_r"] for r in recs if "target_r" in r)
    print("book target in R: min %.2f  p25 %.2f  median %.2f  p75 %.2f  max %.2f  n %d"
          % (tr[0], tr[len(tr) // 4], tr[len(tr) // 2], tr[3 * len(tr) // 4], tr[-1], len(tr)))

    base = per_day(recs, "base", days)
    b_all = sum(base) / n
    b_1 = sum(base[i] for i in h1) / n1
    b_2 = sum(base[i] for i in h2) / n2

    print("")
    print("A. FINE k GRID (every arm vs the same no-BE control)")
    print("%7s %9s %9s %9s %9s %9s" % ("k", "$/day", "H1 $/d", "H2 $/d", "d_H1", "d_H2"))
    print("%7s %9.1f %9.1f %9.1f %9s %9s" % ("no-BE", b_all, b_1, b_2, "-", "-"))
    grid = {}
    for k in FINE_K:
        v = per_day(recs, str(k), days)
        a = sum(v) / n
        a1 = sum(v[i] for i in h1) / n1
        a2 = sum(v[i] for i in h2) / n2
        grid[k] = {"usd_day": round(a, 2), "h1": round(a1, 2), "h2": round(a2, 2),
                   "d_h1": round(a1 - b_1, 2), "d_h2": round(a2 - b_2, 2),
                   "gate_pass": bool(a1 - b_1 > 0 and a2 - b_2 > 0)}
        print("%7.3f %9.1f %9.1f %9.1f %+9.1f %+9.1f%s"
              % (k, a, a1, a2, a1 - b_1, a2 - b_2,
                 "   GATE-PASS" if grid[k]["gate_pass"] else ""))

    K = "0.5"
    dv = [x - y for x, y in zip(per_day(recs, K, days), base)]
    n_changed = 0
    for r in recs:
        if r["fallback"] or r["base"] is None:
            continue
        v = r["k"].get(K)
        v = r["base"] if v is None else v
        if abs(v - r["base"]) > 1e-9:
            n_changed += 1
    print("")
    print("B. PAIRED BOOTSTRAP, k=0.50R vs no-BE control (10,000 session resamples)")
    print("   picks whose R actually changed: %d / %d (%.1f%%)"
          % (n_changed, len(recs), 100.0 * n_changed / len(recs)))
    rnd = random.Random(20260905)
    B = 10000
    boot = {"all": [], "h1": [], "h2": []}
    idx_all = list(range(n))
    for _ in range(B):
        boot["all"].append(sum(dv[rnd.choice(idx_all)] for _ in range(n)) / n)
        boot["h1"].append(sum(dv[rnd.choice(h1)] for _ in range(n1)) / n1)
        boot["h2"].append(sum(dv[rnd.choice(h2)] for _ in range(n2)) / n2)
    obs = {"all": sum(dv) / n,
           "h1": sum(dv[i] for i in h1) / n1,
           "h2": sum(dv[i] for i in h2) / n2}
    res_b = {}
    for lab in ("all", "h1", "h2"):
        arr = sorted(boot[lab])
        p_le0 = sum(1 for x in arr if x <= 0) / B
        res_b[lab] = {"obs_usd_day": round(obs[lab], 2),
                      "ci2.5": round(arr[int(.025 * B)], 2),
                      "ci97.5": round(arr[int(.975 * B)], 2),
                      "p_delta_le_0": round(p_le0, 4)}
        print("   %-3s delta %+8.2f $/day   95%% CI [%+8.2f, %+8.2f]   P(delta<=0) = %.3f"
              % (lab, res_b[lab]["obs_usd_day"], res_b[lab]["ci2.5"],
                 res_b[lab]["ci97.5"], p_le0))
    joint = sum(1 for a, b in zip(boot["h1"], boot["h2"]) if a > 0 and b > 0) / B
    print("   P(H1 delta > 0 AND H2 delta > 0) across resamples = %.3f" % joint)

    print("")
    print("C1. SELECTION STABILITY -- best k by full-sample $/day, per resample")
    pk = {k: per_day(recs, str(k), days) for k in PUBLISHED_K}
    winct = defaultdict(int)
    NS = 2000
    for _ in range(NS):
        sel = [rnd.choice(idx_all) for _ in range(n)]
        best, bestv = None, None
        for k in PUBLISHED_K:
            v = sum(pk[k][i] for i in sel) / n
            if bestv is None or v > bestv:
                best, bestv = k, v
        winct[best] += 1
    for k in PUBLISHED_K:
        print("   k=%.2f wins in %5.1f%% of resamples" % (k, 100.0 * winct[k] / NS))

    print("")
    print("C2. CENTERED NULL -- per-arm deltas de-meaned (true effect exactly 0),")
    print("    how often does the claim's survivor gate still fire?")
    devs = {}
    for k in PUBLISHED_K:
        d = [x - y for x, y in zip(pk[k], base)]
        m = sum(d) / n
        devs[k] = [x - m for x in d]
    hits_any = hits_one = 0
    NB = 4000
    for _ in range(NB):
        sel1 = [rnd.choice(h1) for _ in range(n1)]
        sel2 = [rnd.choice(h2) for _ in range(n2)]
        any_pass = False
        for j, k in enumerate(PUBLISHED_K):
            a1 = sum(devs[k][i] for i in sel1) / n1
            a2 = sum(devs[k][i] for i in sel2) / n2
            if a1 > 0 and a2 > 0:
                any_pass = True
                if j == 1:
                    hits_one += 1
        if any_pass:
            hits_any += 1
    print("   P(a SPECIFIC arm passes the gate | no effect)     = %.3f" % (hits_one / NB))
    print("   P(AT LEAST ONE of the 4 arms passes | no effect)  = %.3f" % (hits_any / NB))

    out = {"fill": "signal-bar CLOSE entry; stop_rule.stop_fill_price; disaster 1.0R; "
                   "size-gated omen_metrics.first_of_day_arm; 1R=$1000",
           "book": os.path.basename(G.BOOK_PATH), "sessions": n,
           "fallbacks": nfb,
           "fine_k_grid": {str(k): grid[k] for k in FINE_K},
           "bootstrap_k0.5": res_b, "p_joint_h1h2_positive": round(joint, 4),
           "picks_changed": n_changed, "picks": len(recs),
           "selection_win_share": {str(k): round(winct[k] / NS, 3) for k in PUBLISHED_K},
           "gate_fpr_centered_null_single_arm": round(hits_one / NB, 4),
           "gate_fwer_centered_null_any_of_4": round(hits_any / NB, 4)}
    json.dump(out, open(os.path.join(HERE, "g154_refute2_be_multiplicity.json"), "w"), indent=1)
    print("")
    print(" -> research/g154_refute2_be_multiplicity.json")


if __name__ == "__main__":
    main()
