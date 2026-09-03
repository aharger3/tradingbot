"""g75_trendfilter_book.py -- price "only trade a trending day" on the two-year book.

One arm per (trendiness definition x threshold). The book is un-halted, the
filter is applied, then R31's loss halt (loss_halt.apply_to_book) is RE-RUN on
the survivors -- same construction as research/g71_trend.py and t23_stack.py,
because dropping a trade changes which days halt.

Money arithmetic is IMPORTED from research/g72_suppress_price.py (stats,
shipped_rows, oneaday_rows) so these numbers mean exactly what the G7.2 board's
numbers mean. 1R = $1,000.

The one-trade-a-day delta carries a paired daily bootstrap against the unfiltered
book -- 10,000 resamples of the 500 sessions -- because every A/B in this project
so far has been inside its own error bar and the default assumption must be that
this one is too.

Read-only on the book. Writes research/g75_trendfilter_book.json.

Usage:  python research/g75_trendfilter_book.py
"""
from __future__ import annotations
import argparse, json, os, random, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import loss_halt                                                  # noqa: E402
from g72_suppress_price import stats, shipped_rows, oneaday_rows, RISK  # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades.json")
CACHE = os.path.join(HERE, "g75_trendfilter_cache.json")
OUT = os.path.join(HERE, "g75_trendfilter_book.json")
RNG = random.Random(753)


def er(v):
    if v is None or len(v) < 3:
        return None
    path = sum(abs(v[i] - v[i - 1]) for i in range(1, len(v)))
    return abs(v[-1] - v[0]) / path if path > 0 else None


def unhalt(rows):
    tag = " [halt: %d consecutive losses]" % loss_halt.HALT_AFTER_CONSECUTIVE_LOSSES
    out = []
    for r in rows:
        r = dict(r)
        if r.get("halted") or r.get("status") == "halted":
            r["traded"] = True
            r["status"] = "fired"
            r.pop("halted", None)
            r["reason"] = r.get("reason", "").replace(tag, "")
        out.append(r)
    return out


def rehalt(rows):
    fresh = [dict(r) for r in rows]
    loss_halt.apply_to_book(fresh)
    return fresh


# ------------------------------------------------------------------- scores
def build_scores(rows, cache):
    """Attach every trendiness score to every candidate row."""
    sess = {s: sorted(d) for s, d in cache.items()}
    idx = {s: {d: i for i, d in enumerate(days)} for s, days in sess.items()}

    def prior(sym, day, n):
        i = idx.get(sym, {}).get(day)
        if i is None:
            return []
        return sess[sym][max(0, i - n):i]

    for r in rows:
        sym, day, et = r["sym"], r["day"], r["et"]
        rec = (cache.get(sym) or {}).get(day)
        s = {}
        if rec:
            s["er_session"] = rec["er"]                       # HINDSIGHT
            s["pm_er_full"] = rec["pm_full"]
            s["pm_er_0800"] = rec["pm_0800"]
            # ER of 09:30 up to and including the entry bar -- causal at entry
            k = None
            for i, t in enumerate(rec["wt"]):
                if t <= et:
                    k = i
                else:
                    break
            s["er_to_entry"] = er(rec["wc"][:k + 1]) if k is not None else None
            s["er_or0945"] = er([c for t, c in zip(rec["wt"], rec["wc"]) if t < "09:45"])
            s["er_or1000"] = er([c for t, c in zip(rec["wt"], rec["wc"]) if t < "10:00"])
            p1 = prior(sym, day, 1)
            s["prior_day_er"] = cache[sym][p1[0]]["er"] if p1 else None
            p5 = [cache[sym][d]["er"] for d in prior(sym, day, 5)]
            p5 = [v for v in p5 if v is not None]
            s["prior5_er"] = sum(p5) / len(p5) if p5 else None
            for n in (10, 20):
                cl = [cache[sym][d]["rc"] for d in prior(sym, day, n + 1)]
                s["daily_er_%d" % n] = er(cl)
            if p1:
                pr = cache[sym][p1[0]]
                rng = pr["hi"] - pr["lo"]
                s["gap_prior_range"] = abs(rec["o"] - pr["rc"]) / rng if rng > 0 else None
        r["_s"] = s
    return rows


# (name, the clock at which the score is knowable).
#
# THE CAUSALITY RULE, and it is the whole point of this file. A score known at
# 10:00 may not decide a trade entered at 09:42. So a row whose entry minute is
# EARLIER than the score's clock is passed through untouched -- the filter never
# sees it. Only rows at or after the clock are filtered. The first version of
# this script filtered every row on the 10:00 score and produced a spectacular,
# entirely fake +$420/day.
#
# "09:30" means knowable before the first bar closes, so it filters everything.
# "entry" means the score is recomputed at each row's own entry minute.
DEFS = [
    ("pm_er_full", "09:30"), ("pm_er_0800", "09:30"),
    ("prior_day_er", "09:30"), ("prior5_er", "09:30"),
    ("daily_er_10", "09:30"), ("daily_er_20", "09:30"),
    ("gap_prior_range", "09:30"),
    ("er_to_entry", "entry"),
    ("er_or0945", "09:45"), ("er_or1000", "10:00"),
    ("er_session", "HINDSIGHT"),
]
KNOWN_AT = dict(DEFS)


def daily_series(rws):
    d = defaultdict(float)
    for r in rws:
        d[r["day"]] += r["pnl"]
    return dict(d)


def price(rows, nd):
    """Money for one arm, both policies."""
    hb = rehalt(rows)
    sh = stats(shipped_rows(hb), nd)
    oa = stats(oneaday_rows(hb), nd)
    return {"all_trades": sh, "one_a_day": oa,
            "oneaday_daily": daily_series(oneaday_rows(hb))}


def boot(base_daily, arm_daily, days, iters=10000):
    """Paired daily bootstrap of the $/day difference, over the book's sessions."""
    diff = [arm_daily.get(d, 0.0) - base_daily.get(d, 0.0) for d in days]
    n = len(diff)
    obs = sum(diff) / n
    out = []
    for _ in range(iters):
        out.append(sum(diff[RNG.randrange(n)] for _ in range(n)) / n)
    out.sort()
    return obs, out[int(0.025 * iters)], out[int(0.975 * iters)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    book = json.load(open(BOOK, encoding="utf-8"))
    meta, all_rows = book["meta"], book["trades"]
    nd = meta["sessions"]
    cache = json.load(open(CACHE, encoding="utf-8"))

    cand = unhalt([r for r in all_rows
                   if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted"])
    cand = build_scores(cand, cache)
    days = sorted({r["day"] for r in all_rows})

    base = price(cand, nd)
    base_daily = base.pop("oneaday_daily")
    b1, b2 = base["all_trades"], base["one_a_day"]
    print("BASE (no filter)   all-trades: n=%d  $%s/day  win %.1f%%  months %d/%d  weeks %d/%d  dd $%s"
          % (b1["trades"], b1["per_day"], b1["win_pct"], b1["months_green"], b1["months"],
             b1["weeks_green"], b1["weeks"], b1["worst_drawdown"]))
    print("                   one-a-day : n=%d  $%s/day  win %.1f%%  months %d/%d  weeks %d/%d  dd $%s"
          % (b2["trades"], b2["per_day"], b2["win_pct"], b2["months_green"], b2["months"],
             b2["weeks_green"], b2["weeks"], b2["worst_drawdown"]))
    print()

    res = {"base": base, "arms": {}, "sessions": nd, "risk_dollars": RISK}

    # Control: the pure time filter each windowed score drags along with it.
    print("== CONTROLS: what the CLOCK alone does, with no trendiness in it ==")
    print("   %-16s %6s | %6s %7s %6s | %6s %7s %6s %s"
          % ("arm", "keep%", "n", "$/day", "win%", "n", "$/day", "win%", "1/day delta"))
    res["clock_controls"] = {}
    for clk in ("09:45", "10:00"):
        keep = [r for r in cand if r["et"] < clk]
        p = price(keep, nd)
        ad = p.pop("oneaday_daily")
        o, lo, hi = boot(base_daily, ad, days)
        res["clock_controls"]["only_before_" + clk] = {
            **p, "kept_pct": round(len(keep) / len(cand) * 100, 1),
            "oneaday_delta_per_day": round(o, 0), "oneaday_delta_ci95": [round(lo, 0), round(hi, 0)]}
        print("   %-16s %5.1f%% | %6d %7s %6.1f | %6d %7s %6.1f %+6.0f [%+.0f,%+.0f]"
              % ("only before " + clk, len(keep) / len(cand) * 100,
                 p["all_trades"]["trades"], p["all_trades"]["per_day"], p["all_trades"]["win_pct"],
                 p["one_a_day"]["trades"], p["one_a_day"]["per_day"], p["one_a_day"]["win_pct"],
                 o, lo, hi))
    print()

    for dfn, clock in DEFS:
        vals = sorted(r["_s"].get(dfn) for r in cand if r["_s"].get(dfn) is not None)
        cov = len(vals) / len(cand) * 100
        # rows the filter is actually allowed to touch
        if clock in ("09:30", "HINDSIGHT", "entry"):
            n_reach = len(cand)
        else:
            n_reach = sum(1 for r in cand if r["et"] >= clock)
        cuts = sorted({round(vals[int(q * len(vals))], 4)
                       for q in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)})
        print("== %s ==  knowable at %s   scoreable %.1f%%   rows this filter may touch: %d of %d (%.1f%%)"
              % (dfn, clock, cov, n_reach, len(cand), n_reach / len(cand) * 100))
        print("   %-7s %6s | %6s %7s %6s %7s %8s %8s | %6s %7s %6s %7s %8s %8s %s"
              % ("thresh", "keep%", "n", "$/day", "win%", "months", "weeks", "dd",
                 "n", "$/day", "win%", "months", "weeks", "dd", "1/day delta 95% bar"))
        arms = {}
        for c in cuts:
            keep = []
            for r in cand:
                if clock not in ("09:30", "HINDSIGHT", "entry") and r["et"] < clock:
                    keep.append(r)          # not knowable yet -- filter may not touch it
                    continue
                v = r["_s"].get(dfn)
                if v is not None and v >= c:
                    keep.append(r)
            if len(keep) < 50:
                continue
            p = price(keep, nd)
            ad = p.pop("oneaday_daily")
            o, lo, hi = boot(base_daily, ad, days)
            clears = bool(lo > 0 or hi < 0)
            arms["%.4f" % c] = {"threshold": c,
                                "kept_pct": round(len(keep) / len(cand) * 100, 1),
                                **p, "oneaday_delta_per_day": round(o, 0),
                                "oneaday_delta_ci95": [round(lo, 0), round(hi, 0)],
                                "clears_bar": clears}
            s_, o_ = p["all_trades"], p["one_a_day"]
            print("   %-7.4f %5.1f%% | %6d %7s %6.1f %4d/%-2d %4d/%-3d %8s | %6d %7s %6.1f %4d/%-2d %4d/%-3d %8s %+6.0f [%+.0f,%+.0f]%s"
                  % (c, len(keep) / len(cand) * 100, s_["trades"], s_["per_day"], s_["win_pct"],
                     s_["months_green"], s_["months"], s_["weeks_green"], s_["weeks"],
                     s_["worst_drawdown"], o_["trades"], o_["per_day"], o_["win_pct"],
                     o_["months_green"], o_["months"], o_["weeks_green"], o_["weeks"],
                     o_["worst_drawdown"], o, lo, hi, "  **" if clears else ""))
        res["arms"][dfn] = {"knowable_at": clock, "coverage_pct": round(cov, 1),
                            "rows_filter_may_touch": n_reach, "cuts": arms}
        print()

    json.dump(res, open(a.out, "w", encoding="utf-8"), indent=1, default=float)
    print("wrote %s" % a.out)


if __name__ == "__main__":
    main()
