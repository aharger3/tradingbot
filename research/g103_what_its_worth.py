"""g103 -- what the classifier is worth ON TOP of the ladder, honestly.

Two levers are on the table for the S-route:

  EXIT   the ladder (research/g101_open_and_ladder.py): four priced rungs plus a
         free runner tranche. Measured, applies to every trade, no new signal.
  ENTRY  the classifier: fire only on symbol-days that look like the ones Austin
         grades S. g96 proved the LABEL predicts (+0.157R gap, p=0.037); it did
         not price what the label is worth once the ladder is also on, and it
         did not price it per DAY.

This script crosses them. Unit is the SYMBOL-DAY, because that is the unit he
judges. For every judged symbol-day the engine had a candidate on, take the
FIRST size-gated candidate and price it two ways -- the shipped book fill, and
the ladder replay -- then split by whether he graded that symbol-day S.

READ THE DENOMINATOR WARNING IN g96. His marks are not a random sample of
sessions: deck cards were often chosen BECAUSE the engine fired. Everything here
is within-judged-pool only. It is an upper bound on what a PERFECT classifier
would have been worth on the days he has actually judged -- not a forecast for
unjudged days.

    python research/g103_what_its_worth.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g101_open_and_ladder as g101               # noqa: E402
import g102_wait_for_the_open as g102             # noqa: E402
import signal_runner as sr                        # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g103_what_its_worth.json")


def main():
    from research import marks_pool as mp
    judged = mp.canonical_pool()
    s_days = set(mp.s_days(judged))
    judged = set(judged)
    print("judged symbol-days %d, S %d (%.1f%%)"
          % (len(judged), len(s_days), 100 * len(s_days) / len(judged)))

    b = json.load(open(BOOK, encoding="utf-8"))
    rows = b["trades"] if isinstance(b, dict) else b
    n_sessions = (b.get("meta") or {}).get("sessions") or len({r["day"] for r in rows})

    bysd = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            bysd["%s_%s" % (r["sym"], r["day"])].append(r)
    for v in bysd.values():
        v.sort(key=g86.ekey)

    hit = [k for k in bysd if k in judged]
    print("judged symbol-days with an engine candidate: %d (S: %d)"
          % (len(hit), sum(1 for k in hit if k in s_days)))

    recs = []
    for k in hit:
        first = next((r for r in bysd[k] if g102.sized(r)), None)
        if first is None:
            continue
        v = g102.replay(first)
        if v is None:
            continue
        bp, lp, mfe, state, al = v
        recs.append({"sd": k, "day": first["day"], "sym": first["sym"],
                     "et": first["et"], "S": k in s_days,
                     "book": bp, "ladder": lp, "mfe": mfe,
                     "runner": mfe >= 3.0, "entry_i": first["entry_i"]})
    print("priced %d of them\n" % len(recs))

    def blk(v, label):
        if not v:
            return None
        bk = [x["book"] for x in v]
        ld = [x["ladder"] for x in v]
        return {"label": label, "n": len(v),
                "book_per_trade": round(statistics.fmean(bk)),
                "book_mean_r": round(statistics.fmean(bk) / g86.RISK, 4),
                "book_win": round(sum(1 for x in bk if x > 0) / len(bk) * 100, 1),
                "ladder_per_trade": round(statistics.fmean(ld)),
                "ladder_mean_r": round(statistics.fmean(ld) / g86.RISK, 4),
                "ladder_win": round(sum(1 for x in ld if x > 0) / len(ld) * 100, 1),
                "runner_pct": round(sum(1 for x in v if x["runner"]) / len(v) * 100, 1),
                "early_pct": round(sum(1 for x in v if (x["entry_i"] or 0) < 15)
                                   / len(v) * 100, 1)}

    print("=== per judged symbol-day, first size-gated candidate ===")
    print("| arm | n | book $/trade | book win | ladder $/trade | ladder win | runner | entry <09:45 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    out = {}
    for label, v in (("every judged day", recs),
                     ("he graded S", [x for x in recs if x["S"]]),
                     ("he did NOT grade S", [x for x in recs if not x["S"]])):
        st = blk(v, label)
        out[label] = st
        print("| %-20s | %3d | $%-5d | %5.1f%% | $%-5d | %5.1f%% | %5.1f%% | %5.1f%% |"
              % (label, st["n"], st["book_per_trade"], st["book_win"],
                 st["ladder_per_trade"], st["ladder_win"], st["runner_pct"],
                 st["early_pct"]))

    s = out["he graded S"]
    ns = out["he did NOT grade S"]
    print("\ngap, book fill    : %+.4fR" % (s["book_mean_r"] - ns["book_mean_r"]))
    print("gap, ladder fill  : %+.4fR" % (s["ladder_mean_r"] - ns["ladder_mean_r"]))

    # label-shuffle test, same method as g96.permutation_p -- no distributional
    # assumption, because R-multiples are a spike at -1R with a long right tail.
    import g96_does_his_S_predict as g96          # noqa: E402
    for col in ("book", "ladder"):
        a = [x[col] / g86.RISK for x in recs if x["S"]]
        c = [x[col] / g86.RISK for x in recs if not x["S"]]
        obs, p = g96.permutation_p(a, c, trials=20000)
        out["perm_" + col] = {"obs_r": round(obs, 4), "p": round(p, 4),
                              "n_s": len(a), "n_not": len(c)}
        print("  permutation, %-6s: obs %+.4fR  p=%.4f  (n=%d vs %d)"
              % (col, obs, p, len(a), len(c)))
    a = [x["runner"] for x in recs if x["S"]]
    c = [x["runner"] for x in recs if not x["S"]]
    obs, p = g96.permutation_p([1.0 if x else 0.0 for x in a],
                               [1.0 if x else 0.0 for x in c], trials=20000)
    out["perm_runner"] = {"obs": round(obs, 4), "p": round(p, 4)}
    print("  permutation, runner rate: obs %+.1fpp  p=%.4f" % (obs * 100, p))

    # ---- how many S symbol-days a day, and what one-a-day on them pays ----
    byday = defaultdict(list)
    for x in recs:
        if x["S"]:
            byday[x["day"]].append(x)
    per_day = [len(v) for v in byday.values()]
    print("\n=== S symbol-days per judged day ===")
    print("  days with >=1 judged S: %d ; median S/day %.1f ; max %d"
          % (len(byday), statistics.median(per_day), max(per_day)))

    firsts = []
    for d in sorted(byday):
        v = sorted(byday[d], key=lambda x: (x["et"], x["sym"]))
        firsts.append(v[0])
    for col, name in (("book", "book fill"), ("ladder", "ladder fill")):
        rws = [dict(day=x["day"], et=x["et"], sym=x["sym"], pnl=x[col]) for x in firsts]
        st_traded = g86.stats(rws, len(firsts))
        st_all = g86.stats(rws, n_sessions)
        print("  one-a-day on S days, %-11s: $%d per S-day traded (n=%d), "
              "$%d/day spread over all %d sessions, %.1f%% win, %d/%d months green, DD $%d"
              % (name, st_traded["per_day"], len(firsts), st_all["per_day"],
                 n_sessions, st_traded["win_pct"], st_traded["months_green"],
                 st_traded["months"], st_traded["worst_drawdown"]))
        out["one_a_day_S_" + col] = {"traded": st_traded, "all_sessions": st_all}

    json.dump({"judged": len(judged), "s_days": len(s_days), "priced": len(recs),
               "sessions": n_sessions, "arms": out},
              open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("\n  -> %s" % OUT_JSON)


if __name__ == "__main__":
    main()
