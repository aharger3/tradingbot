"""R2 referee pass 3, part B.

Two questions the books alone cannot answer:

  (1) SIM D was built on 2026-09-05 at commit 15a729ce; fwd_1 and fwd_2 were
      built on 2026-09-06 at commit 5f8b554e.  SWARM law 5 forbids A/B-ing two
      books built on different days from different bases, and the headline
      table does exactly that twice.  Is the cross-commit comparison actually
      contaminated?  Test: fwd_2 and SIM D claim the SAME 14,332-row
      population.  Pair them key-for-key and check entry price, stop price and
      signal identity.  If the two commits produce the identical signal set at
      identical prices, the engine change between them is empirically inert
      for this population.

  (2) The repaired headline names ONE mechanism for the substrate leg: "a stop
      that reacts the instant price touches it, instead of one that only reacts
      once the candle closes."  Go to the raw 1-minute bars for the trades that
      actually flipped (fwd_1 win -> SIM D loss) and ask what came first after
      the entry bar: a wick through the stop with the candle closing back on
      the right side (the named mechanism), a close beyond the stop (a
      mechanism BOTH rigs share, so it cannot explain the flip), or the 2R
      target (neither -- something else moved).

Usage: python research/r2_referee_pass3b.py [--sample N]
"""
import csv
import gzip
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TAPE = os.path.join(HERE, "tape")
ARCHIVE = os.path.join(ROOT, "data_archive")


def load(name):
    with gzip.open(os.path.join(TAPE, name + ".json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)


def key(r, shift=0):
    hh, mm, _ = r["entry_time"].split(":")
    return (r["sym"], r["day"], int(hh) * 60 + int(mm) + shift, r["side"])


def bars_for(sym, day):
    p = os.path.join(ARCHIVE, sym, day + ".csv")
    if not os.path.exists(p):
        return None
    out = []
    with open(p, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            t = row["Datetime"]
            hhmm = t[11:16]
            try:
                out.append((hhmm, float(row["Open"]), float(row["High"]),
                            float(row["Low"]), float(row["Close"])))
            except (TypeError, ValueError):
                continue
    return out


def main():
    n_sample = 120
    if "--sample" in sys.argv:
        n_sample = int(sys.argv[sys.argv.index("--sample") + 1])

    f1 = load("reconcile_fwd_1_add_C_grades")
    f2 = load("reconcile_fwd_2_swap_exit_shipped_ladder")
    sd = load("r2ref_simd_next_open_blind2r_real_engine")

    print("=" * 100)
    print("1. CROSS-COMMIT IDENTITY -- SIM D (15a729ce, 2026-09-05) vs fwd_2 (5f8b554e, 2026-09-06)")
    print("=" * 100)
    A = {key(r): r for r in sd["trades"]}
    B = {key(r): r for r in f2["trades"]}
    print(f"   SIM D rows {len(sd['trades'])} -> {len(A)} unique keys")
    print(f"   fwd_2 rows {len(f2['trades'])} -> {len(B)} unique keys")
    common = set(A) & set(B)
    print(f"   keys only in SIM D: {len(set(A)-set(B))}   only in fwd_2: {len(set(B)-set(A))}"
          f"   common: {len(common)}")
    same_e = sum(1 for k in common if abs(A[k]["entry"] - B[k]["entry"]) < 1e-9)
    same_s = sum(1 for k in common if abs(A[k]["stop"] - B[k]["stop"]) < 1e-9)
    print(f"   identical entry price on {same_e}/{len(common)}; identical stop on {same_s}/{len(common)}")
    if same_e == len(common) and same_s == len(common) and not (set(A) ^ set(B)):
        print("   => the two commits emit the SAME signals at the SAME prices: the engine")
        print("      change between 15a729ce and 5f8b554e is EMPIRICALLY INERT for this book.")
    else:
        print("   => the populations DIFFER across the commit boundary: cross-commit A/B is contaminated.")

    print()
    print("=" * 100)
    print("2. RAW-BAR REPLAY of the substrate leg's flips (fwd_1 win -> SIM D loss)")
    print("=" * 100)
    a1 = {key(r, 1): r for r in f1["trades"]}
    common2 = sorted(set(a1) & set(A))
    flips = [k for k in common2
             if a1[k].get("outcome") in ("win", "scratch") and A[k].get("outcome") == "loss"]
    holds = [k for k in common2
             if a1[k].get("outcome") == "win" and A[k].get("outcome") == "win"]
    print(f"   matched pairs {len(common2)}; flips to loss {len(flips)}; wins held {len(holds)}")

    random.seed(7)
    sample = random.sample(flips, min(n_sample, len(flips)))
    tally = defaultdict(int)
    unexplained = []
    for k in sample:
        r = A[k]
        bars = bars_for(r["sym"], r["day"])
        if not bars:
            tally["no_bars"] += 1
            continue
        et = r["entry_time"][:5]
        idx = next((i for i, b in enumerate(bars) if b[0] == et), None)
        if idx is None:
            tally["entry_bar_not_found"] += 1
            continue
        entry, stop = r["entry"], r["stop"]
        long = r["side"] == "call"
        risk = abs(entry - stop)
        if risk <= 0:
            tally["zero_risk"] += 1
            continue
        target = entry + 2 * risk if long else entry - 2 * risk
        verdict = "ran_to_session_end"
        for _, o, hi, lo, cl in bars[idx:]:
            touch = (lo <= stop) if long else (hi >= stop)
            closebey = (cl <= stop) if long else (cl >= stop)
            hittgt = (hi >= target) if long else (lo <= target)
            if touch and closebey and hittgt:
                verdict = "same_bar_ambiguous"
                break
            if touch and not closebey:
                verdict = "INTRABAR_WICK_FIRST"   # the report's named mechanism
                break
            if closebey:
                verdict = "close_beyond_first"    # both rigs stop here -- cannot explain a flip
                break
            if hittgt:
                verdict = "target_first"          # neither rig should have lost
                break
        tally[verdict] += 1
        if verdict in ("close_beyond_first", "target_first", "ran_to_session_end"):
            unexplained.append((k, verdict))

    print(f"   sampled {len(sample)} flips:")
    for k in sorted(tally, key=lambda x: -tally[x]):
        print(f"      {k:<24} {tally[k]:>5}   ({100.0*tally[k]/len(sample):.1f}%)")
    explained = tally["INTRABAR_WICK_FIRST"] + tally["same_bar_ambiguous"]
    print(f"   explained by the report's named mechanism (wick first, or same-bar "
          f"touch+target ambiguity the engine resolves pessimistically): "
          f"{explained}/{len(sample)} = {100.0*explained/len(sample):.1f}%")
    for k, v in unexplained[:12]:
        print("      NOT the named mechanism:", k, v)


if __name__ == "__main__":
    main()
