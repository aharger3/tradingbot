"""g104 -- what each gate the engine already has is actually worth, book and ladder.

Two facts from the book stamp of research/bt2y_trades_retest_on.json make this
necessary before any new gate is proposed:

  * the LIVE process forces `ENABLE_SAC_LADDER=1` (live_scanner.py:30) and then
    trades only `sac_grade == "S"` (live_scanner.py:~573). The 2-year book does
    NOT set that env var -- its stamp lists no ENABLE_SAC_LADDER -- so every
    published figure in this repo is measured on the legacy A/B/C grader while
    the live process trades a different one. Nobody has priced the live gate on
    the honest book.
  * `sgrade` IS stamped on every row (reported only). So the live gate can be
    priced retrospectively, exactly, with no new backtest.

Also cross-tabs the setup family, because his S prose names the one-candle rule
in 18 of 347 S marks while the book is 93.8% break-and-retest.

First size-gated candidate of each of the 498 sessions (the one-a-day unit). Ladder column is the
g101 replica, 4 priced rungs + 20% free runner, ratchet trail.

    python research/g104_gate_value.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g102_wait_for_the_open as g102             # noqa: E402
import signal_runner as sr                        # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g104_gate_value.json")


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    rows_all = b["trades"] if isinstance(b, dict) else b
    n_sessions = (b.get("meta") or {}).get("sessions") or 498
    byday = g86.candidates(rows_all)

    recs = []
    for d in sorted(byday):
        first = next((r for r in byday[d] if g102.sized(r)), None)
        if first is None:
            continue
        v = g102.replay(first)
        if v is None:
            continue
        bp, lp, mfe, state, al = v
        recs.append({"day": d, "sym": first["sym"], "et": first["et"],
                     "book": bp, "ladder": lp, "runner": mfe >= 3.0,
                     "sgrade": first.get("sgrade"), "grade": first.get("grade"),
                     "setup": first.get("setup"), "tags": first.get("tags") or [],
                     "downgrades": first.get("downgrades") or [],
                     "entry_i": first.get("entry_i")})
    n = len(recs)
    print("first-of-day, size-gated, priced: %d over %d sessions\n" % (n, n_sessions))

    def show(title, groups):
        print("=== %s ===" % title)
        print("| slice | trades | trades/day kept | book $/day | ladder $/day "
              "| ladder win | ladder months green | ladder max DD | runner |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        out = {}
        for label, v in groups:
            if not v:
                continue
            br = [dict(day=x["day"], et=x["et"], sym=x["sym"], pnl=x["book"]) for x in v]
            lr = [dict(day=x["day"], et=x["et"], sym=x["sym"], pnl=x["ladder"]) for x in v]
            bs = g86.stats(br, n_sessions)
            ls = g86.stats(lr, n_sessions)
            run = sum(1 for x in v if x["runner"]) / len(v) * 100
            out[label] = {"n": len(v), "book": bs, "ladder": ls,
                          "runner_pct": round(run, 1)}
            print("| %-28s | %3d | %.2f | $%-5d | $%-5d | %5.1f%% | %5s | $%-7d | %5.1f%% |"
                  % (label, len(v), len(v) / n_sessions, bs["per_day"],
                     ls["per_day"], ls["win_pct"],
                     "%d/%d" % (ls["months_green"], ls["months"]),
                     ls["worst_drawdown"], run))
        print()
        return out

    out = {}
    out["sgrade"] = show(
        "THE LIVE GATE: sac/sgrade (denominator = all %d sessions)" % n_sessions,
        [("everything (shipped backtest)", recs),
         ("sgrade S only  <- LIVE GATE", [x for x in recs if x["sgrade"] == "S"]),
         ("sgrade S or A", [x for x in recs if x["sgrade"] in ("S", "A")]),
         ("sgrade C only", [x for x in recs if x["sgrade"] == "C"])])

    out["chase"] = show(
        "THE CHASE VETO -- the one right-signed, reachable entry gate available",
        [("everything", recs),
         ("minus chase", [x for x in recs if "chase" not in x["tags"]]),
         ("minus chase, minus nodisp",
          [x for x in recs if "chase" not in x["tags"] and "nodisp" not in x["tags"]]),
         ("minus chase, sgrade S or A",
          [x for x in recs if "chase" not in x["tags"] and x["sgrade"] in ("S", "A")])])

    out["setup"] = show(
        "setup family",
        [("break_and_retest", [x for x in recs if x["setup"] == "break_and_retest"]),
         ("one_candle_rule", [x for x in recs if x["setup"] == "one_candle_rule"]),
         ("reentry_84_rule", [x for x in recs if x["setup"] == "reentry_84_rule"])])

    tagset = sorted({t for x in recs for t in x["tags"]})
    out["tags"] = show(
        "engine tags (reachability + value)",
        [(t, [x for x in recs if t in x["tags"]]) for t in tagset])

    dgset = sorted({t for x in recs for t in x["downgrades"]})
    print("=== downgrade variable reachability on the 498 first-of-day rows ===")
    dg = {}
    for t in dgset:
        v = [x for x in recs if t in x["downgrades"]]
        w = [x for x in recs if t not in x["downgrades"]]
        mv = statistics.fmean(x["ladder"] for x in v) / g86.RISK
        mw = statistics.fmean(x["ladder"] for x in w) / g86.RISK
        dg[t] = {"n": len(v), "pct": round(len(v) / n * 100, 1),
                 "ladder_r_tripped": round(mv, 4), "ladder_r_clean": round(mw, 4),
                 "sign_ok": mv < mw}
        print("  %-30s trips %3d (%4.1f%%)  ladder R tripped %+.4f vs clean %+.4f  %s"
              % (t, len(v), len(v) / n * 100, mv, mw,
                 "OK" if mv < mw else "WRONG-SIGNED (marks better trades worse)"))
    out["downgrades"] = dg

    json.dump({"n": n, "sessions": n_sessions, "arms": out},
              open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("\n  -> %s" % OUT_JSON)


if __name__ == "__main__":
    main()
