"""ADVERSARIAL VERIFY of track `smeasure`. Part 2: re-run the discrimination
test with Austin's ACTUAL ladder instead of S / not-S.

The smeasure test (research/g71_smeasure_test.py:186 `neg_pool`) defines the
negative sample as "days he judged and did NOT call S" and then reports it as
"days he refused". On Austin's ladder (CLAUDE.md: S / A / C / none, "A = one
downgrade, C = two") A and C days are days he WOULD trade. The pool it calls
"refused" is therefore S-complement, not refusal.

This script:
  1. reproduces the smeasure S/not-S split exactly (control), then
  2. re-splits the same judged days into  S | A | C | REFUSED  and re-runs the
     two-proportion test against REFUSED only, and
  3. reports how the pool was SOURCED (engine-fired deck vs engine-silent
     autopsy), because that decides whether the comparison is confounded.

Read-only. No mark file, no engine file, no artifact is written.
"""
from __future__ import annotations
import os, sys, json, math
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import research.build_deck as bd
import research.g71_smeasure_pools as pools_mod

BOOK = os.path.join(HERE, "bt2y_trades.json")
SEP = os.sep

# ---------------------------------------------------------------- the ladder
# Every scalar field any corpus uses to carry Austin's own grade.
_SCALARS = ("austin_tier", "tier", "austin_grade", "grade", "verdict")
_ANSWERS = ("grade", "your_grade", "s", "s_call")

# canonical -> class.  B appears 17 times in two legacy corpora; it is between
# A and C on the legacy ladder, so it is scored as tradeable-not-S.
LADDER = {"s": "S", "a": "A", "b": "A", "c": "C",
          "x": "REFUSED", "none": "REFUSED", "no": "REFUSED", "null": "REFUSED"}


def row_grades(row):
    """Every canonical grade token this row carries."""
    out = []
    for k in _SCALARS:
        v = str(row.get(k, "")).strip().lower()
        if v and v in LADDER:
            out.append(v)
    a = row.get("answers")
    if isinstance(a, dict):
        for k in _ANSWERS:
            if a.get(k):
                v = a[k][0] if isinstance(a[k], list) else a[k]
                v = str(v).strip().lower()
                if v in LADDER:
                    out.append(v)
    if not out and row.get("_no_trade"):
        out.append("none")
    return out


RANK = {"S": 3, "A": 2, "C": 1, "REFUSED": 0}


def collect_ladder():
    """key -> {'best': class, 'classes': Counter, 'corpora': set}
    Day-level grain, same as smeasure: the BEST grade any row of that
    symbol-day carries wins (a day with one S bar is an S day)."""
    day = defaultdict(lambda: {"classes": Counter(), "corpora": set()})
    for path in bd.mark_sources():
        name = os.path.relpath(path, HERE).replace(SEP, "/")
        for r in bd._rows(path):
            key = bd._judgement_key(r)
            if not key:
                continue
            gs = row_grades(r)
            if not gs:
                continue
            for g in gs:
                day[key]["classes"][LADDER[g]] += 1
            day[key]["corpora"].add(name)
    for k, v in day.items():
        v["best"] = max(v["classes"], key=lambda c: RANK[c])
    return day


# ------------------------------------------------------------------ the book

def book_index():
    d = json.load(open(BOOK, encoding="utf-8"))
    meta = d["meta"]
    by = defaultdict(lambda: {"sigs": 0, "routed": 0, "traded": 0})
    for t in d["trades"]:
        e = by[(t["sym"], t["day"])]
        e["sigs"] += 1
        if t.get("status") == "fired":
            e["routed"] += 1
        if t.get("traded"):
            e["traded"] += 1
    return by, meta


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def zt(k1, n1, k2, n2):
    if n1 == 0 or n2 == 0:
        return (0.0, 0.0, 1.0)
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = 0.0 if se == 0 else (p1 - p2) / se
    return ((p1 - p2) * 100, z, math.erfc(abs(z) / math.sqrt(2)))


def split(key):
    sym, d = key.rsplit("_", 1)
    return sym, d


def line(label, days, hitmap):
    n = len(days); k = sum(1 for d in days if hitmap.get(d))
    p, lo, hi = wilson(k, n)
    print("  %-34s %4d/%4d = %5.1f%%  [%.1f, %.1f]"
          % (label, k, n, p * 100, lo * 100, hi * 100))
    return k, n


def main():
    by_day, meta = book_index()
    lo_d, hi_d = meta["first"], meta["last"]
    syms = set(meta["symbols"])
    print("BOOK %s  %s..%s  %d sessions  %d signals  %d traded"
          % (os.path.basename(BOOK), lo_d, hi_d, meta["sessions"],
             meta["signals"], meta["traded"]))

    # ---- control: reproduce smeasure's own S / not-S split -----------------
    pools, per_source, _ = pools_mod.collect()
    s_ctrl, n_ctrl = [], []
    for key, byc in pools.items():
        sym, d = split(key)
        if sym not in syms or not (lo_d <= d <= hi_d):
            continue
        if any(t[True] for t in byc.values()):
            s_ctrl.append(key)
        elif any(t[False] for t in byc.values()):
            n_ctrl.append(key)
    tr = lambda k: by_day.get(split(k), {}).get("traded", 0)
    ro = lambda k: by_day.get(split(k), {}).get("routed", 0)
    sw = lambda k: by_day.get(split(k), {}).get("sigs", 0)
    print("\nCONTROL -- smeasure's own S vs not-S split, recomputed here")
    ks, ns = line("S days, traded", s_ctrl, {k: tr(k) for k in s_ctrl})
    kn, nn = line("not-S days, traded", n_ctrl, {k: tr(k) for k in n_ctrl})
    d, z, p = zt(ks, ns, kn, nn)
    print("    diff %+.1f pts  z=%.3f  p=%.4f" % (d, z, p))
    prec = wilson(ks, ks + kn)
    print("    precision %.1f%%  [%.1f, %.1f]"
          % (prec[0] * 100, prec[1] * 100, prec[2] * 100))

    # ---- the ladder split --------------------------------------------------
    day = collect_ladder()
    elig = {k: v for k, v in day.items()
            if split(k)[0] in syms and lo_d <= split(k)[1] <= hi_d}
    buckets = defaultdict(list)
    for k, v in elig.items():
        buckets[v["best"]].append(k)
    print("\nLADDER SPLIT of the same eligible judged days  (n=%d)" % len(elig))
    for c in ("S", "A", "C", "REFUSED"):
        print("  %-8s %4d" % (c, len(buckets[c])))

    print("\nTRADED RATE by his actual grade")
    res = {}
    for c in ("S", "A", "C", "REFUSED"):
        res[c] = line(c, buckets[c], {k: tr(k) for k in buckets[c]})
    print("\nROUTED RATE by his actual grade")
    for c in ("S", "A", "C", "REFUSED"):
        line(c, buckets[c], {k: ro(k) for k in buckets[c]})
    print("\nSAW RATE by his actual grade")
    for c in ("S", "A", "C", "REFUSED"):
        line(c, buckets[c], {k: sw(k) for k in buckets[c]})

    print("\nDISCRIMINATION, traded arm, against the REAL refusal set")
    for pair in (("S", "REFUSED"), ("S", "A"), ("S", "C"),
                 ("A", "REFUSED"), ("C", "REFUSED")):
        (k1, n1), (k2, n2) = res[pair[0]], res[pair[1]]
        d, z, p = zt(k1, n1, k2, n2)
        print("  %-14s %+6.1f pts  z=%7.3f  p=%.4f  (%d/%d vs %d/%d)"
              % ("%s vs %s" % pair, d, z, p, k1, n1, k2, n2))
    # tradeable (S|A|C) vs refused -- the question the engine actually answers
    kt = sum(res[c][0] for c in ("S", "A", "C"))
    nt = sum(res[c][1] for c in ("S", "A", "C"))
    kr, nr = res["REFUSED"]
    d, z, p = zt(kt, nt, kr, nr)
    print("  %-14s %+6.1f pts  z=%7.3f  p=%.4f  (%d/%d vs %d/%d)"
          % ("S|A|C vs REF", d, z, p, kt, nt, kr, nr))
    pr = wilson(kt, kt + kr)
    print("  precision against TRADEABLE (S|A|C): %.1f%%  [%.1f, %.1f]"
          % (pr[0] * 100, pr[1] * 100, pr[2] * 100))

    # ---- how the pool was sourced -----------------------------------------
    print("\nSOURCING of the eligible S pool (which corpus contributed it)")
    src = Counter()
    for k in buckets["S"]:
        for c in elig[k]["corpora"]:
            src[c] += 1
    for c, n in src.most_common():
        print("  %-52s %4d" % (c, n))

    # engine-silent-by-construction contamination
    autopsy = set()
    for path in bd.mark_sources():
        name = os.path.relpath(path, HERE).replace(SEP, "/")
        if "autopsy" not in name:
            continue
        for r in bd._rows(path):
            k = bd._judgement_key(r)
            if k:
                autopsy.add(k)
    a_elig = [k for k in buckets["S"] if k in autopsy]
    print("\n  S days sourced from the SILENT-DAY autopsy probe "
          "(selected because the engine did NOT fire): %d of %d"
          % (len(a_elig), len(buckets["S"])))
    ks2 = [k for k in buckets["S"] if k not in autopsy]
    print("  S recall with those removed:")
    k1, n1 = line("S minus autopsy, traded", ks2, {k: tr(k) for k in ks2})
    d, z, p = zt(k1, n1, kr, nr)
    print("    vs REFUSED: %+.1f pts  z=%.3f  p=%.4f" % (d, z, p))


if __name__ == "__main__":
    main()
