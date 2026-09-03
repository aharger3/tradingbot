"""g75_trendfilter_marks.py -- cross the trendiness filter against Austin's own
grades BEFORE recommending anything. Step 4 of the trendfilter track.

Two questions, and the second one governs:

  1. Does trendiness separate his S days from his refusals AT ALL, across the
     whole graded corpus (287 S days, 553 refusals) rather than the 30 cards the
     finding came from? Both flavours are scored: the hindsight session ER that
     produced the finding, and every causal score that could actually gate a
     trade.

  2. HELD-OUT S RECALL under the filter. The engine fires on 163 of his 278
     bar-backed S days (research/g72_recall278_paired.json, 58.6%). A day filter
     can only subtract from that. This replays those days through the real
     router -- research/t4_engine_recall.run_day, the harness the regression gate
     uses -- records the minute of every fire, then reports how many S days each
     threshold silences. DIRECTION.md's gate is 90%; the engine is at 58.6% and
     every point matters.

Grades come from research/g71_samplesize_corpus.json (built from all 19 mark
corpora). Mark files are opened read-only. No engine code is touched.

Writes research/g75_trendfilter_marks.json.

Usage:
  python research/g75_trendfilter_marks.py              # scores + recall replay
  python research/g75_trendfilter_marks.py --no-replay  # scores only, seconds
"""
from __future__ import annotations
import argparse, json, math, os, random, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

CORPUS = os.path.join(HERE, "g71_samplesize_corpus.json")
CACHE = os.path.join(HERE, "g75_trendfilter_cache.json")
PAIRED = os.path.join(HERE, "g72_recall278_paired.json")
OUT = os.path.join(HERE, "g75_trendfilter_marks.json")
RNG = random.Random(755)


def er(v):
    if v is None or len(v) < 3:
        return None
    path = sum(abs(v[i] - v[i - 1]) for i in range(1, len(v)))
    return abs(v[-1] - v[0]) / path if path > 0 else None


def mean(x):
    return sum(x) / len(x) if x else float("nan")


def mww(a, b):
    """Mann-Whitney AUC + normal-approximation two-sided p, tie-corrected.

    The 30-card scripts used a shuffle permutation; at 278 x 534 that is a
    billion comparisons, so this uses the standard rank-sum statistic instead.
    Checked against the permutation routine on the 30 cards: same answer.
    """
    n1, n2 = len(a), len(b)
    pool = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    ranks = [0.0] * len(pool)
    i = 0
    tie = 0.0
    while i < len(pool):
        j = i
        while j + 1 < len(pool) and pool[j + 1][0] == pool[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = r
        t = j - i + 1
        tie += t ** 3 - t
        i = j + 1
    r1 = sum(rk for rk, (_, g) in zip(ranks, pool) if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2.0
    auc = u1 / (n1 * n2)
    n = n1 + n2
    var = n1 * n2 / 12.0 * ((n + 1) - tie / (n * (n - 1)))
    if var <= 0:
        return auc, 1.0
    z = (u1 - n1 * n2 / 2.0) / math.sqrt(var)
    p = math.erfc(abs(z) / math.sqrt(2))
    return auc, p


def top_austin(r):
    for g in ("S", "A", "C", "none"):
        if r["austin"].get(g):
            return g
    return None


def day_scores(cache, sess, idx, sym, day):
    rec = (cache.get(sym) or {}).get(day)
    if not rec:
        return None

    def prior(n):
        i = idx.get(sym, {}).get(day)
        return [] if i is None else sess[sym][max(0, i - n):i]

    s = {"er_session": rec["er"], "pm_er_full": rec["pm_full"], "pm_er_0800": rec["pm_0800"],
         "er_or0945": er([c for t, c in zip(rec["wt"], rec["wc"]) if t < "09:45"]),
         "er_or1000": er([c for t, c in zip(rec["wt"], rec["wc"]) if t < "10:00"])}
    p1 = prior(1)
    s["prior_day_er"] = cache[sym][p1[0]]["er"] if p1 else None
    p5 = [cache[sym][d]["er"] for d in prior(5)]
    p5 = [v for v in p5 if v is not None]
    s["prior5_er"] = mean(p5) if p5 else None
    for n in (10, 20):
        s["daily_er_%d" % n] = er([cache[sym][d]["rc"] for d in prior(n + 1)])
    if p1:
        pr = cache[sym][p1[0]]
        rng = pr["hi"] - pr["lo"]
        s["gap_prior_range"] = abs(rec["o"] - pr["rc"]) / rng if rng > 0 else None
    s["_wt"], s["_wc"] = rec["wt"], rec["wc"]
    return s


SCORES = ["er_session", "pm_er_full", "pm_er_0800", "prior_day_er", "prior5_er",
          "daily_er_10", "daily_er_20", "gap_prior_range", "er_or0945", "er_or1000"]
KNOWN = {"er_session": "HINDSIGHT", "er_or0945": "09:45", "er_or1000": "10:00"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-replay", action="store_true")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    cache = json.load(open(CACHE, encoding="utf-8"))
    sess = {s: sorted(d) for s, d in cache.items()}
    idx = {s: {d: i for i, d in enumerate(days)} for s, days in sess.items()}
    rows = [r for r in json.load(open(CORPUS, encoding="utf-8"))["rows"]
            if r["bars"] and r["austin"]]
    for r in rows:
        r["grade"] = top_austin(r)
        r["sc"] = day_scores(cache, sess, idx, r["symbol"], r["day"])
    rows = [r for r in rows if r["sc"]]
    S = [r for r in rows if r["grade"] == "S"]
    NO = [r for r in rows if r["grade"] == "none"]
    print("corpus: %d bar-backed graded days scored  %s"
          % (len(rows), dict(Counter(r["grade"] for r in rows))))
    out = {"n_scored": len(rows), "grade_mix": dict(Counter(r["grade"] for r in rows))}

    print()
    print("=" * 84)
    print("1. DOES TRENDINESS SEPARATE HIS S DAYS FROM HIS REFUSALS?  (%d S vs %d none)"
          % (len(S), len(NO)))
    print("=" * 84)
    print("  %-18s %-10s %8s %8s %7s %8s" % ("score", "known at", "S", "none", "AUC", "p"))
    sep = {}
    for k in SCORES:
        x = [r["sc"][k] for r in S if r["sc"].get(k) is not None]
        y = [r["sc"][k] for r in NO if r["sc"].get(k) is not None]
        if len(x) < 20 or len(y) < 20:
            continue
        auc, p = mww(x, y)
        sep[k] = {"known_at": KNOWN.get(k, "09:29"), "n_S": len(x), "n_none": len(y),
                  "S_mean": mean(x), "none_mean": mean(y), "auc": auc, "p": p}
        print("  %-18s %-10s %8.4f %8.4f %7.3f %8.4f %s"
              % (k, KNOWN.get(k, "09:29"), mean(x), mean(y), auc, p, "**" if p < 0.05 else ""))
    out["separation"] = sep

    if a.no_replay:
        json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1, default=float)
        print("\nwrote %s (scores only)" % a.out)
        return

    print()
    print("=" * 84)
    print("2. HELD-OUT S RECALL UNDER THE FILTER -- replaying his S days on the real router")
    print("=" * 84)
    from t4_engine_recall import run_day  # noqa: E402
    fires = {}
    t0 = time.time()
    for i, r in enumerate(S):
        key = r["symbol"] + "_" + r["day"]
        try:
            entries, _sigs, _raw = run_day(r["symbol"], r["day"])
        except Exception as e:
            fires[key] = {"error": type(e).__name__}
            continue
        if entries is None:
            fires[key] = {"error": "no bars"}
            continue
        mins = sorted({(e["timestamp"][11:16] if "T" in e["timestamp"] else e["timestamp"][:5])
                       for e in entries})
        fires[key] = {"mins": mins}
        if (i + 1) % 50 == 0:
            print("    replayed %d/%d (%.0fs)" % (i + 1, len(S), time.time() - t0), flush=True)
    hit = [r for r in S if fires[r["symbol"] + "_" + r["day"]].get("mins")]
    print("  engine fires on %d of %d S days = %.1f%%   (g72_recall278_paired: 163/278 = 58.6%%)"
          % (len(hit), len(S), len(hit) / len(S) * 100))
    out["recall_base"] = {"n_S": len(S), "fired": len(hit),
                          "pct": round(len(hit) / len(S) * 100, 1)}

    print()
    print("  How many of those %d survive a trendiness cut:" % len(hit))
    print("  %-18s %-10s %s" % ("score", "known at", "recall at threshold (kept / %)"))
    QS = [0.1, 0.2, 0.3, 0.4, 0.5]
    rec = {}
    for k in SCORES + ["er_to_first_fire"]:
        vals = []
        for r in hit:
            if k == "er_to_first_fire":
                sc = r["sc"]
                et = fires[r["symbol"] + "_" + r["day"]]["mins"][0]
                v = er([c for t, c in zip(sc["_wt"], sc["_wc"]) if t <= et])
            else:
                v = r["sc"].get(k)
            if v is not None:
                vals.append(v)
        if len(vals) < 20:
            continue
        # thresholds taken from the BOOK's distribution deciles would not be
        # comparable across scores, so use this pool's own quantiles: "cut the
        # choppiest X% of his own S days" is the cost that matters to him.
        sv = sorted(vals)
        cells = []
        cuts = {}
        for q in QS:
            c = sv[int(q * len(sv))]
            keep = sum(1 for v in vals if v >= c)
            cells.append("%.3f:%d(%.0f%%)" % (c, keep, keep / len(S) * 100))
            cuts["%.4f" % c] = {"threshold": c, "S_kept": keep,
                                "recall_pct": round(keep / len(S) * 100, 1)}
        rec[k] = {"known_at": KNOWN.get(k, "09:29" if k != "er_to_first_fire" else "the fire minute"),
                  "n": len(vals), "cuts": cuts}
        print("  %-18s %-10s %s"
              % (k, KNOWN.get(k, "09:29" if k != "er_to_first_fire" else "fire min"),
                 "  ".join(cells)))
    out["recall_under_filter"] = rec
    out["fires"] = fires

    json.dump(out, open(a.out, "w", encoding="utf-8"), indent=1, default=float)
    print("\nwrote %s" % a.out)


if __name__ == "__main__":
    main()
