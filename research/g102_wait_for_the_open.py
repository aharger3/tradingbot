"""g102 -- the engine takes the first setup of the day, and the first setup of
the day is almost always before the open has behaved.

g101 found it: on 402 of the 444 size-gated first-of-day trades (90.5%) the
entry bar lands INSIDE the first 15 minutes. Austin's own answer to "what tells
you at 9:45 whether the day will trend" was "how the open behaved" -- a read
that does not exist yet at the moment the engine is already filled.

So this script asks the causal question that follows. Keep the one-trade-a-day
policy, keep arrival order, and change ONE thing: which arrival counts. Take the
first candidate at or after bar K instead of the first candidate at all.

No lookahead anywhere. Bar index K is knowable in real time; the open read is
computed from bars[0:entry_i] only (g101.open_state); nothing consults the
outcome. A day whose candidates all arrive before K is simply NOT TRADED and
earns $0 -- and $/day divides by every session in the book either way, so
sitting out is never free.

    python research/g102_wait_for_the_open.py

Population: research/bt2y_trades_retest_on.json, g86.candidates, size-gated on
signal_runner.min_risk_floor. Book fill = the shipped honest close fill. The
ladder column replays research/g101_open_and_ladder (4 priced rungs + a 20%
free runner), the arm that priced best there.
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
import g97_mfe as g97                             # noqa: E402
import g101_open_and_ladder as g101               # noqa: E402
import signal_runner as sr                        # noqa: E402
from research import g80_ordertype_grid as G      # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g102_wait_for_the_open.json")
LADDER = ("4", (.30, .30, .30, .10), "ratchet", 0.20)

_PACK = {}


def pack(sym, day):
    k = (sym, day)
    if k not in _PACK:
        _PACK[k] = G.day_pack(sym, day)
    return _PACK[k]


def sized(r):
    return abs(r["entry"] - r["stop"]) >= sr.min_risk_floor(r["entry"])


def replay(r):
    """(book_pnl, ladder_pnl, mfe, open_state, aligned) for one row, or None."""
    bars, pdh, pdl, pmh, pml = pack(r["sym"], r["day"])
    i = r.get("entry_i")
    if not bars or i is None or i >= len(bars):
        return None
    w = g97.walk(r, bars)
    if w is None:
        return None
    mfe, _stopped, _out = w
    long = r["dir"] == "call"
    state, _rl, orh, orl = g101.open_state(bars, i)
    named = ({"PDH": pdh, "PMH": pmh, "ORH": orh} if long
             else {"PDL": pdl, "PML": pml, "ORL": orl})
    extreme = (max(c.high for c in bars[:i + 1]) if long
               else min(c.low for c in bars[:i + 1]))
    plan, weights, trail, rw = LADDER
    rungs = g101.build_rungs(r["entry"], r["stop"], long, extreme, named,
                             weights, plan)
    fills = g101.walk_ladder(r, bars, rungs, trail=trail, runner_w=rw)
    lad = g101.r_of(fills, r["entry"], r["stop"], long) * g86.RISK
    return r["pnl"], lad, mfe, state, g101.aligned_with_open(state, long)


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    rows_all = b["trades"] if isinstance(b, dict) else b
    n_days = (b.get("meta") or {}).get("sessions") or len({r["day"] for r in rows_all})
    byday = g86.candidates(rows_all)
    print("sessions in book: %d ; days with candidates: %d" % (n_days, len(byday)))

    # ---- how late does a candidate arrive, across the WHOLE stream? ----
    buckets = Counter()
    tot = 0
    for d in byday:
        for r in byday[d]:
            if not sized(r):
                continue
            i = r.get("entry_i")
            tot += 1
            if i is None:
                buckets["?"] += 1
            elif i < 15:
                buckets["<09:45"] += 1
            elif i < 30:
                buckets["09:45-09:59"] += 1
            elif i < 60:
                buckets["10:00-10:29"] += 1
            else:
                buckets["10:30+"] += 1
    print("\n=== arrival clock, ALL size-gated candidates (n=%d) ===" % tot)
    for k in ("<09:45", "09:45-09:59", "10:00-10:29", "10:30+", "?"):
        if buckets[k]:
            print("  %-12s %5d  %5.1f%%" % (k, buckets[k], buckets[k] / tot * 100))

    # ---- the arms ----
    ARMS = {
        "A first of day (shipped)":       lambda r: True,
        "B first at/after 09:45":         lambda r: (r.get("entry_i") or 0) >= 15,
        "C first at/after 09:50":         lambda r: (r.get("entry_i") or 0) >= 20,
        "D first at/after 10:00":         lambda r: (r.get("entry_i") or 0) >= 30,
    }
    picks = {}
    for label, ok in ARMS.items():
        chosen = []
        for d in sorted(byday):
            for r in byday[d]:
                if sized(r) and ok(r):
                    chosen.append(r)
                    break
        picks[label] = chosen

    # open-read arms are built on top of B: they need a read to exist
    cache = {}

    def rep(r):
        k = (r["sym"], r["day"], r["et"], r["entry_i"])
        if k not in cache:
            cache[k] = replay(r)
        return cache[k]

    for label, extra in (("E B + open not chop", lambda st, al: st != "chop"),
                         ("F B + open trending", lambda st, al: st in ("trend_up", "trend_dn")),
                         ("G B + trending, aligned", lambda st, al: al)):
        chosen = []
        for d in sorted(byday):
            for r in byday[d]:
                if not (sized(r) and (r.get("entry_i") or 0) >= 15):
                    continue
                v = rep(r)
                if v is None:
                    continue
                if extra(v[3], v[4]):
                    chosen.append(r)
                    break
        picks[label] = chosen

    print("\n=== 1-a-day arms. $/day divides by %d sessions in EVERY arm. ===" % n_days)
    print("| arm | days traded | book $/day | book win | ladder $/day | ladder win "
          "| ladder months green | ladder max DD | runner rate |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    out = {}
    for label in ("A first of day (shipped)", "B first at/after 09:45",
                  "C first at/after 09:50", "D first at/after 10:00",
                  "E B + open not chop", "F B + open trending",
                  "G B + trending, aligned"):
        chosen = picks[label]
        brows, lrows, runners, ok = [], [], 0, 0
        for r in chosen:
            v = rep(r)
            if v is None:
                continue
            bp, lp, mfe, st, al = v
            base = dict(day=r["day"], et=r["et"], sym=r["sym"])
            brows.append(dict(base, pnl=bp))
            lrows.append(dict(base, pnl=lp))
            ok += 1
            if mfe >= 3.0:
                runners += 1
        bs = g86.stats(brows, n_days)
        ls = g86.stats(lrows, n_days)
        out[label] = {"days": ok, "book": bs, "ladder": ls,
                      "runner_pct": round(runners / ok * 100, 1) if ok else 0.0}
        print("| %-24s | %3d | $%-5d | %5.1f%% | $%-5d | %5.1f%% | %5s | $%-7d | %5.1f%% |"
              % (label, ok, bs["per_day"], bs["win_pct"], ls["per_day"],
                 ls["win_pct"], "%d/%d" % (ls["months_green"], ls["months"]),
                 ls["worst_drawdown"], runners / ok * 100 if ok else 0.0))

    # ---- runner rate by arrival bucket, across every candidate ----
    print("\n=== runner rate (MFE>=3R while alive) by arrival bucket, first-of-day-eligible ===")
    bb = defaultdict(lambda: [0, 0, 0.0])
    for d in sorted(byday):
        for r in byday[d]:
            if not sized(r):
                continue
            v = rep(r) if (r.get("entry_i") or 0) >= 15 else None
            if v is None:
                continue
            i = r["entry_i"]
            k = ("09:45-09:59" if i < 30 else "10:00-10:29" if i < 60 else "10:30+")
            bb[k][0] += 1
            bb[k][1] += 1 if v[2] >= 3.0 else 0
            bb[k][2] += v[0]
    for k in ("09:45-09:59", "10:00-10:29", "10:30+"):
        if bb[k][0]:
            print("  %-12s n=%4d  runner %.1f%%  book $%d/trade"
                  % (k, bb[k][0], bb[k][1] / bb[k][0] * 100, bb[k][2] / bb[k][0]))

    json.dump({"sessions": n_days, "arrival_buckets": dict(buckets), "arms": out},
              open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("\n  -> %s" % OUT_JSON)


if __name__ == "__main__":
    main()
