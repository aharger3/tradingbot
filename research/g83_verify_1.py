"""g83_verify_1 -- adversarial recomputation of research/g83_recall278.json.

Independently rebuilds the headline numbers of the "free 278" recall pass:
  * the pool counts (S / A / C / none, bar-backed);
  * the base-arm hit map, by REPLAYING every bar-backed judged day through
    t4_engine_recall.run_day again from scratch -- not by reading the arm file;
  * recall, false-fire rate, the S-minus-refusal separation, and their
    confidence intervals, computed here with independent code;
  * three robustness checks the original did not run:
      (a) drop the X-only days from the refusal bucket (X is a refusal aimed
          at the engine, not at the day) and re-read the separation;
      (b) drop the "contested" days (a symbol-day two corpora disagree about,
          resolved by best-grade-wins) and re-read the separation;
      (c) a bootstrap on the separation, as a check on the Newcombe band.

Read-only over every mark corpus. Writes only research/g83_verify_1.json and a
regenerable replay cache.

    python research/g83_verify_1.py            # full replay, ~4 min
    python research/g83_verify_1.py --reuse    # score off the saved replay
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

OUT = os.path.join(HERE, "g83_verify_1.json")
REPLAY = os.path.join(HERE, "_g83_verify_replay.json")
THEIRS = os.path.join(HERE, "g83_recall278.json")
THEIR_ARM = os.path.join(HERE, "_g83_arms", "arm_base.json")
Z = 1.959963984540054


def wilson(k, n):
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def newcombe(k1, n1, k2, n2):
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = k1 / n1 - k2 / n2
    return (d - math.sqrt((k1 / n1 - l1) ** 2 + (u2 - k2 / n2) ** 2),
            d + math.sqrt((u1 - k1 / n1) ** 2 + (k2 / n2 - l2) ** 2))


def boot_sep(s_hits, n_s, no_hits, n_no, iters=10000, seed=7):
    """Non-parametric bootstrap on the S-minus-refusal gap, as an independent
    read on the Newcombe band."""
    rng = random.Random(seed)
    p1 = s_hits / n_s
    p2 = no_hits / n_no
    out = []
    for _ in range(iters):
        a = sum(1 for _ in range(n_s) if rng.random() < p1) / n_s
        b = sum(1 for _ in range(n_no) if rng.random() < p2) / n_no
        out.append(a - b)
    out.sort()
    return (out[int(0.025 * iters)] * 100, out[int(0.975 * iters)] * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true")
    args = ap.parse_args()

    import inspect

    import marks_pool
    import t4_engine_recall as t4
    router_ok = "super()._route" in inspect.getsource(t4.CaptureRunner._route)

    pool = marks_pool.canonical_pool()
    with_bars = {k: e for k, e in pool.items() if e.has_bars}
    counts_all = Counter(e.grade for e in pool.values())
    counts_bars = Counter(e.grade for e in with_bars.values())
    x_only = marks_pool.x_only_days(pool)
    contested = {k for k, e in pool.items() if e.contested}

    # ---- independent replay ------------------------------------------------
    if args.reuse and os.path.exists(REPLAY):
        rep = json.load(open(REPLAY))
    else:
        rep, errs, t0 = {}, [], time.time()
        days = sorted(with_bars)
        for i, k in enumerate(days):
            e = with_bars[k]
            try:
                entries, sigs, _raw = t4.run_day(e.symbol, e.date)
            except Exception as exc:                                # noqa: BLE001
                errs.append({"key": k, "err": type(exc).__name__})
                continue
            if entries is None:
                errs.append({"key": k, "err": "no bars"})
                continue
            rep[k] = {"hit": bool(entries), "n_signals": len(sigs),
                      "grades": [x["grade"] for x in entries]}
            if i and i % 250 == 0:
                print("  %d/%d  %.0fs" % (i, len(days), time.time() - t0), flush=True)
        json.dump(rep, open(REPLAY, "w"))
        print("replayed %d days, %d errors, %.0fs"
              % (len(rep), len(errs), time.time() - t0), flush=True)

    def slice_rate(keys):
        keys = [k for k in keys if k in rep]
        h = sum(1 for k in keys if rep[k]["hit"])
        lo, hi = wilson(h, len(keys)) if keys else (0, 0)
        return {"k": h, "n": len(keys),
                "pct": round(h / len(keys) * 100, 1) if keys else None,
                "wilson95_pct": [round(lo * 100, 1), round(hi * 100, 1)]}

    S = [k for k, e in with_bars.items() if e.grade == "S"]
    NO = [k for k, e in with_bars.items() if e.grade == "none"]
    A = [k for k, e in with_bars.items() if e.grade == "A"]
    C = [k for k, e in with_bars.items() if e.grade == "C"]

    rS, rNO = slice_rate(S), slice_rate(NO)
    lo, hi = newcombe(rS["k"], rS["n"], rNO["k"], rNO["n"])
    sep = {"points": round((rS["k"] / rS["n"] - rNO["k"] / rNO["n"]) * 100, 1),
           "newcombe95_pts": [round(lo * 100, 1), round(hi * 100, 1)],
           "bootstrap95_pts": [round(x, 1) for x in
                               boot_sep(rS["k"], rS["n"], rNO["k"], rNO["n"])]}

    det_S = sum(1 for k in S if k in rep and rep[k]["n_signals"])
    det_NO = sum(1 for k in NO if k in rep and rep[k]["n_signals"])

    # ---- robustness (a): X-only days out of the refusal bucket -------------
    NO_noX = [k for k in NO if k not in x_only]
    rNOx = slice_rate(NO_noX)
    lox, hix = newcombe(rS["k"], rS["n"], rNOx["k"], rNOx["n"])

    # ---- robustness (b): drop contested days -------------------------------
    Sc = [k for k in S if k not in contested]
    NOc = [k for k in NO if k not in contested]
    rSc, rNOc = slice_rate(Sc), slice_rate(NOc)
    loc, hic = newcombe(rSc["k"], rSc["n"], rNOc["k"], rNOc["n"])

    # ---- agreement with their stored arm file ------------------------------
    agree = None
    if os.path.exists(THEIR_ARM):
        theirs = json.load(open(THEIR_ARM))
        tr = theirs.get("replay", theirs)
        common = [k for k in rep if isinstance(tr.get(k), dict)]
        dis = [k for k in common if bool(tr[k]["hit"]) != rep[k]["hit"]]
        agree = {"days_compared": len(common), "disagreements": len(dis),
                 "sample": dis[:10],
                 "keys_only_mine": len([k for k in rep if k not in tr]),
                 "keys_only_theirs": len([k for k in tr
                                          if isinstance(tr[k], dict) and k not in rep])}

    theirs_json = json.load(open(THEIRS)) if os.path.exists(THEIRS) else {}
    base = theirs_json.get("arms", {}).get("base", {})

    out = {
        "router_delegates_to_shipped_engine": router_ok,
        "pool": {"total_judged": len(pool), "with_bars": len(with_bars),
                 "grade_mix_all": dict(counts_all),
                 "grade_mix_with_bars": dict(counts_bars),
                 "x_only_days_in_none_bucket": len(x_only),
                 "contested_days": len(contested)},
        "my_recall_S": rS, "my_false_fire_none": rNO,
        "my_fire_A": slice_rate(A), "my_fire_C": slice_rate(C),
        "my_separation": sep,
        "my_detection_any_signal": {
            "S_pct": round(det_S / len(S) * 100, 1),
            "none_pct": round(det_NO / len(NO) * 100, 1)},
        "robustness_X_only_removed_from_refusals": {
            "refusals_n": rNOx["n"], "false_fire_pct": rNOx["pct"],
            "separation_pts": round((rS["k"] / rS["n"] - rNOx["k"] / rNOx["n"]) * 100, 1),
            "newcombe95_pts": [round(lox * 100, 1), round(hix * 100, 1)]},
        "robustness_contested_days_removed": {
            "S_n": rSc["n"], "refusals_n": rNOc["n"],
            "recall_pct": rSc["pct"], "false_fire_pct": rNOc["pct"],
            "separation_pts": round((rSc["k"] / rSc["n"] - rNOc["k"] / rNOc["n"]) * 100, 1),
            "newcombe95_pts": [round(loc * 100, 1), round(hic * 100, 1)]},
        "agreement_with_their_saved_replay": agree,
        "their_published": {
            "recall_S": base.get("recall_S"),
            "false_fire_none": base.get("false_fire_none"),
            "separation": base.get("separation_S_minus_none"),
            "pool": theirs_json.get("pool"),
        },
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "their_published"}, indent=1))


if __name__ == "__main__":
    main()
