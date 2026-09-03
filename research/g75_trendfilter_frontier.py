"""g75_trendfilter_frontier.py -- the one table that decides it.

The book sweep (g75_trendfilter_book.py) and the recall replay
(g75_trendfilter_marks.py) each answer half the question. This puts them on the
SAME threshold so the trade-off is visible: at the cut that keeps X% of the
book's trades, how many of Austin's 278 S days does the engine still fire on?

Recall today is 163/278 = 58.6% and DIRECTION.md's gate is 90%. A day filter can
only subtract, so any arm that costs recall has to buy something that clears its
own error bar, and none of the causal ones do.

Reads (never writes) research/g75_trendfilter_book.json,
research/g75_trendfilter_marks.json and research/g75_trendfilter_cache.json.
Writes research/g75_trendfilter_frontier.json.
"""
from __future__ import annotations
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

BOOK = os.path.join(HERE, "g75_trendfilter_book.json")
MARKS = os.path.join(HERE, "g75_trendfilter_marks.json")
CACHE = os.path.join(HERE, "g75_trendfilter_cache.json")
CORPUS = os.path.join(HERE, "g71_samplesize_corpus.json")
OUT = os.path.join(HERE, "g75_trendfilter_frontier.json")

sys.path.insert(0, HERE)
from g75_trendfilter_marks import day_scores, top_austin, er  # noqa: E402


def main():
    bk = json.load(open(BOOK, encoding="utf-8"))
    mk = json.load(open(MARKS, encoding="utf-8"))
    cache = json.load(open(CACHE, encoding="utf-8"))
    sess = {s: sorted(d) for s, d in cache.items()}
    idx = {s: {d: i for i, d in enumerate(days)} for s, days in sess.items()}

    rows = [r for r in json.load(open(CORPUS, encoding="utf-8"))["rows"]
            if r["bars"] and r["austin"]]
    S = []
    for r in rows:
        if top_austin(r) != "S":
            continue
        sc = day_scores(cache, sess, idx, r["symbol"], r["day"])
        if not sc:
            continue
        key = r["symbol"] + "_" + r["day"]
        f = mk["fires"].get(key) or {}
        sc["_fired"] = bool(f.get("mins"))
        sc["_first"] = f["mins"][0] if f.get("mins") else None
        if sc["_fired"]:
            sc["er_to_entry"] = er([c for t, c in zip(sc["_wt"], sc["_wc"])
                                    if t <= sc["_first"]])
        S.append(sc)
    nS = len(S)
    base_hits = sum(1 for s in S if s["_fired"])
    print("Austin's S days with bars: %d.  Engine fires on %d today = %.1f%%  (gate 90%%)"
          % (nS, base_hits, base_hits / nS * 100))
    print()
    b1 = bk["base"]["all_trades"]
    b2 = bk["base"]["one_a_day"]
    print("Unfiltered book: %d trades, $%s/day all-in, one-a-day $%s/day, win %.1f%%, "
          "months %d/%d, weeks %d/%d, worst drawdown $%s"
          % (b1["trades"], b1["per_day"], b2["per_day"], b2["win_pct"],
             b2["months_green"], b2["months"], b2["weeks_green"], b2["weeks"],
             b2["worst_drawdown"]))
    print()
    hdr = ("  %-16s %-9s %7s %6s | %6s %7s %6s %7s %7s %8s | %6s %6s"
           % ("score", "knowable", "thresh", "keep%", "1/d n", "$/day", "win%",
              "months", "weeks", "dd", "S recall", "vs now"))
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    out = {"n_S": nS, "base_recall": base_hits, "rows": []}
    for dfn, arm in bk["arms"].items():
        clock = arm["knowable_at"]
        for _, cut in sorted(arm["cuts"].items(), key=lambda kv: kv[1]["threshold"]):
            t = cut["threshold"]
            kept = 0
            for s in S:
                if not s["_fired"]:
                    continue
                if clock not in ("09:30", "HINDSIGHT", "entry") and (s["_first"] or "") < clock:
                    kept += 1               # filter cannot reach this fire
                    continue
                v = s.get("er_to_entry") if dfn == "er_to_entry" else s.get(dfn)
                if v is not None and v >= t:
                    kept += 1
            o = cut["one_a_day"]
            rec = kept / nS * 100
            row = {"score": dfn, "knowable_at": clock, "threshold": t,
                   "book_kept_pct": cut["kept_pct"], "oneaday": o,
                   "oneaday_delta_per_day": cut["oneaday_delta_per_day"],
                   "oneaday_delta_ci95": cut["oneaday_delta_ci95"],
                   "clears_bar": cut["clears_bar"],
                   "S_recall_n": kept, "S_recall_pct": round(rec, 1),
                   "S_recall_delta_pts": round(rec - base_hits / nS * 100, 1)}
            out["rows"].append(row)
            print("  %-16s %-9s %7.4f %5.1f%% | %6d %7s %6.1f %4d/%-2d %4d/%-3d %8s | %3d/%d %+5.1f%s"
                  % (dfn, clock, t, cut["kept_pct"], o["trades"], o["per_day"],
                     o["win_pct"], o["months_green"], o["months"], o["weeks_green"],
                     o["weeks"], o["worst_drawdown"], kept, nS,
                     rec - base_hits / nS * 100,
                     "  ** money clears its bar" if cut["clears_bar"] else ""))
        print()
    # ------------------------------------------------------------------ lift
    # The filter fails as a money gate. The same score is still the best
    # available answer to "is today worth being at the screen for", so report
    # that separately and honestly: his S rate by quartile of each score, over
    # every day he graded S or refused.
    print()
    print("HOW OFTEN A DAY TURNS OUT TO BE ONE OF HIS, BY QUARTILE OF EACH SCORE")
    pool_rows = []
    for r in rows:
        g = top_austin(r)
        if g not in ("S", "none"):
            continue
        sc = day_scores(cache, sess, idx, r["symbol"], r["day"])
        if sc:
            pool_rows.append((sc, 1 if g == "S" else 0))
    lift = {}
    for name in ("er_or0945", "er_or1000", "er_session"):
        p = sorted([(sc[name], y) for sc, y in pool_rows if sc.get(name) is not None],
                   key=lambda x: x[0])
        n = len(p)
        q = n // 4
        base = sum(y for _, y in p) / n * 100
        cells = []
        for lab, g in (("choppiest 25%", p[:q]), ("2nd", p[q:2 * q]),
                       ("3rd", p[2 * q:3 * q]), ("trendiest 25%", p[3 * q:])):
            cells.append({"quartile": lab, "n": len(g), "S": sum(y for _, y in g),
                          "S_rate_pct": round(sum(y for _, y in g) / len(g) * 100, 1),
                          "range": [g[0][0], g[-1][0]]})
        lift[name] = {"n": n, "base_S_rate_pct": round(base, 1), "quartiles": cells}
        print("  %-12s n=%d, base S rate %.1f%%   %s"
              % (name, n, base, "   ".join("%s %.1f%%" % (c["quartile"], c["S_rate_pct"])
                                           for c in cells)))
    out["day_quality_lift"] = lift

    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
