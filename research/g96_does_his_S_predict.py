"""g96 -- the only question left: does Austin's S label predict money?

g95 showed the oracle is max-of-N arithmetic (real $2,684/day vs a null of
$2,763), and that of 81 features the book already stamps, the best selector is
`dow = Wed`. The engine cannot see what separates a winner from a loser, and the
per-trade mean is -0.033R -- a coin flip. Selection among edgeless candidates
cannot manufacture edge.

That leaves exactly one hypothesis standing, and it is the one the whole project
is built on:

    **Austin's eye is a feature the book does not have.**

If symbol-days he graded S carry higher engine R than days he refused, then his
label is real signal, the 1,246 judged symbol-days are the training set, and the
classifier has a target worth chasing. If they do not, then no amount of grading
will help and the lane has to change.

Nothing else in this repo tests that. `research/t61_onwatch_ab.py` A/Bs detection
flags against his marks; `research/downgrade.py` scores his rules. Neither asks
whether **his verdict predicts the engine's own P&L**.

    python research/g96_does_his_S_predict.py
    python research/g96_does_his_S_predict.py --lane index

Honest book, 1R = $1,000. Applies nothing, ships nothing.

READ THE DENOMINATORS. His marks are not a random sample of sessions -- deck
cards were chosen by `build_deck`, often BECAUSE the engine fired on them. Every
comparison below is therefore within the judged pool only, never judged-vs-world,
and the permutation test asks the one question that survives that bias: given
these judged days and these labels, is the split better than chance?
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g91_lane_slice as g91                      # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g96_does_his_S_predict.json")
OUT_MD = os.path.join(HERE, "g96_does_his_S_predict.md")


def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return b["trades"] if isinstance(b, dict) else b


def mean(xs):
    return statistics.mean(xs) if xs else 0.0


def permutation_p(a, b, trials=20000, seed=20260902):
    """P(a's mean beats b's by this much | labels are meaningless).

    A t-test would assume normal R-multiples; they are anything but -- the
    distribution is a spike at -1R with a long right tail. Shuffling the labels
    makes no distributional assumption at all.
    """
    obs = mean(a) - mean(b)
    pool = list(a) + list(b)
    na = len(a)
    rng = random.Random(seed)
    hits = 0
    for _ in range(trials):
        rng.shuffle(pool)
        if mean(pool[:na]) - mean(pool[na:]) >= obs:
            hits += 1
    return obs, (hits + 1) / (trials + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", choices=("full", "index"), default="full")
    ap.add_argument("--trials", type=int, default=20000)
    a = ap.parse_args()

    from research import marks_pool as mp
    judged = mp.canonical_pool()
    s_days = set(mp.s_days(judged))
    judged = set(judged)
    print("judged symbol-days: %d, of which S: %d (%.1f%%)"
          % (len(judged), len(s_days), 100 * len(s_days) / len(judged)))

    rows = load(BOOK)
    if a.lane == "index":
        rows = [r for r in rows if r["sym"] in g91.INDEX]

    # --- per SYMBOL-DAY, since that is the unit he judges ------------------
    bysd = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            bysd["%s_%s" % (r["sym"], r["day"])].append(r)
    for v in bysd.values():
        v.sort(key=g86.ekey)

    hit = [k for k in bysd if k in judged]
    print("judged symbol-days the engine also had a candidate on: %d" % len(hit))
    if len(hit) < 40:
        raise SystemExit("too few overlapping symbol-days to say anything")

    s_hit = [k for k in hit if k in s_days]
    n_hit = [k for k in hit if k not in s_days]
    print("  of those: %d he graded S, %d he did not" % (len(s_hit), len(n_hit)))

    out = {"lane": a.lane, "judged": len(judged), "s_days": len(s_days),
           "overlap": len(hit), "s_overlap": len(s_hit), "arms": {}}
    md = ["# g96 -- does Austin's S label predict the engine's money?", "",
          "Book `research/bt2y_trades_retest_on.json`, %s lane, 1R = $1,000, "
          "honest close fill. %d judged symbol-days, %d of them S; the engine had "
          "a candidate on %d of them (%d S, %d not)."
          % (a.lane, len(judged), len(s_days), len(hit), len(s_hit), len(n_hit)),
          "", "| policy on the symbol-day | S days | non-S days | gap | perm p |",
          "|---|---:|---:|---:|---:|"]

    for label, pick in (("first candidate of the day", lambda v: v[0]),
                        ("every candidate (mean R)", None)):
        if pick is None:
            sa = [r["r"] for k in s_hit for r in bysd[k]]
            na = [r["r"] for k in n_hit for r in bysd[k]]
        else:
            sa = [pick(bysd[k])["r"] for k in s_hit]
            na = [pick(bysd[k])["r"] for k in n_hit]
        obs, p = permutation_p(sa, na, trials=a.trials)
        print("\n=== %s ===" % label)
        print("  S days    : n=%5d  mean %+.4fR  ($%+.0f/trade)  win %.1f%%"
              % (len(sa), mean(sa), mean(sa) * 1000,
                 100 * sum(1 for x in sa if x > 0) / len(sa)))
        print("  non-S days: n=%5d  mean %+.4fR  ($%+.0f/trade)  win %.1f%%"
              % (len(na), mean(na), mean(na) * 1000,
                 100 * sum(1 for x in na if x > 0) / len(na)))
        print("  gap %+.4fR   permutation p = %.4f  %s"
              % (obs, p, "SIGNAL" if p < 0.05 else "not distinguishable from chance"))
        out["arms"][label] = {"n_s": len(sa), "n_non": len(na),
                              "mean_s": round(mean(sa), 4),
                              "mean_non": round(mean(na), 4),
                              "gap_r": round(obs, 4), "p": round(p, 4)}
        md.append("| %s | %+.4fR (n=%d) | %+.4fR (n=%d) | %+.4fR | %.4f |"
                  % (label, mean(sa), len(sa), mean(na), len(na), obs, p))

    # --- the money version: trade ONLY his S days -------------------------
    print("\n=== trading only the days he graded S, first candidate ===")
    all_days = sorted({k.split("_", 1)[1] for k in hit})
    s_pnl = defaultdict(float)
    for k in s_hit:
        s_pnl[k.split("_", 1)[1]] += bysd[k][0]["pnl"]
    n_sessions = len(all_days)
    per_traded = sum(s_pnl.values()) / len(s_pnl) if s_pnl else 0
    per_all = sum(s_pnl.values()) / n_sessions if n_sessions else 0
    g, m = g91.months_green(s_pnl)
    print("  %d sessions have an S symbol-day; total $%.0f"
          % (len(s_pnl), sum(s_pnl.values())))
    print("  $%.0f per S-session, $%.0f per session across all %d judged sessions"
          % (per_traded, per_all, n_sessions))
    print("  months green: %d/%d" % (g, m))
    out["s_only"] = {"sessions_with_s": len(s_pnl), "total": round(sum(s_pnl.values()), 2),
                     "per_s_session": round(per_traded, 2),
                     "per_all_session": round(per_all, 2), "green": "%d/%d" % (g, m)}

    md += ["", "## Trading only the S symbol-days (first candidate)", "",
           "%d sessions carry an S symbol-day. Total **$%.0f** = **$%.0f per "
           "S-session**, months green **%d/%d**."
           % (len(s_pnl), sum(s_pnl.values()), per_traded, g, m), "",
           "## Read this before quoting it", "",
           "Deck cards were selected by `build_deck`, not sampled at random, and "
           "often BECAUSE the engine fired. These are comparisons *within the "
           "judged pool*, never judged-vs-world. The permutation test is the "
           "honest read: given these days and these labels, is the split better "
           "than shuffling the labels?"]
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
