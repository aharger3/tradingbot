"""g201 refute #1 -- lookahead / leakage attack on F9 (research/g158_mid_candle_arms.md).

Four controls the original row did not run, all on the SAME book, the SAME
universe (8227 traded-or-halted rows of research/bt2y_trades_retest_on.json),
the SAME one-trade-a-day unit and the SAME size gate:

  C1  CLOSE_RT -- the CLOSE control re-priced through the identical harness the
      MID arms use (g80_ordertype_grid.run_trade, move_stop_to_entry_bar=True,
      fill_i = the signal bar).  g158's CLOSE row is the BOOK's own pnl field,
      produced by backtest_2y/simulate_day; the MID rows are run_trade output.
      If CLOSE_RT != g158's $34 the published gap is the exit harness, not the
      entry price.

  C2  NOSKIP -- g158's oneaday_for walks the day's candidates in signal-time
      order and takes the first one that HAS a priced result.  A MID candidate
      has no priced result exactly when its limit never filled -- a fact not
      knowable until 11:00.  NOSKIP takes the day's first sizeable candidate
      whatever happens to it: if its limit never fills, the day has NO trade.

  C3  COLLAPSE -- run_trade calls signal_runner.intrabar_stop, which, when the
      limit fill lands at/through the structural stop, moves the stop to the
      FILL BAR's own low/high.  That extreme is not known when the limit fills.
      Count them, and re-score with those picks dropped.

  C4  FILLBAR -- run_trade manages bars fill_i+1 .. EOD, so the bar the limit
      filled on is never managed.  A collapsed row's stop IS that bar's extreme,
      so price demonstrably touched the stop after the fill.  Re-score forcing
      every pick whose fill bar already traded through its own post-fill stop to
      the shipped -1R (DISASTER_STOP_R = 1.0, a resting touch order).

Writes research/g201_refute1_check.json.  Reads only; nothing shipped.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G   # noqa: E402
import signal_runner as sr                     # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT = ROOT / "research" / "g201_refute1_check.json"
RISK = 1000.0
SPLIT_DAY = "2025-09-01"
FRACS = (0.25, 0.50, 0.75)
NAME = {0.25: "MID25", 0.50: "MID50", 0.75: "MID75"}
EPS = 1e-9


def half(d):
    return "H1" if d < SPLIT_DAY else "H2"


def resting_price(entry_close, rng, long, frac):
    return entry_close - frac * rng if long else entry_close + frac * rng


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, allrows = book["meta"], book["trades"]
    all_days = sorted({r["day"] for r in allrows})
    n_days = meta["sessions"]

    universe = {i: r for i, r in enumerate(allrows)
                if r.get("traded") or r["status"] == "halted"}
    keys = sorted(universe, key=lambda i: (allrows[i]["day"], allrows[i]["et"],
                                           allrows[i]["sym"], i))
    print("universe %d, sessions %d, entry_fill=%s"
          % (len(keys), n_days, meta.get("entry_fill")), flush=True)

    cand_by_day = defaultdict(list)
    for k in keys:
        cand_by_day[allrows[k]["day"]].append(k)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"], i))

    priced = {f: {} for f in FRACS}
    close_rt = {}
    diag = {f: Counter() for f in FRACS}
    flags = {f: {} for f in FRACS}

    for n, k in enumerate(keys):
        if n and n % 1000 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r["entry_i"]
        if not bars or i >= len(bars):
            continue
        long = r["dir"] == "call"
        entry_close = r["entry"]

        # ---- C1: the CLOSE control through the MID arms' own harness
        if i < len(bars) - 1:
            res = G.run_trade(r, bars, i, entry_close, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is not None:
                close_rt[k] = res

        rng = bars[i].high - bars[i].low
        cutoff = G.cutoff_idx(bars)
        if rng <= 0 or i + 1 >= min(cutoff, len(bars) - 1):
            continue

        for f in FRACS:
            px = resting_price(entry_close, rng, long, f)
            j, fillpx = G.limit_touch(bars, px, long, i + 1, cutoff)
            if j is None:
                diag[f]["limit_never_touched"] += 1
                continue
            if j >= len(bars) - 1:
                diag[f]["filled_on_last_bar"] += 1
                continue
            res = G.run_trade(r, bars, j, fillpx, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is None:
                diag[f]["risk_collapsed"] += 1
                continue
            priced[f][k] = res
            struct = r["stop"]
            collapsed = (fillpx <= struct + EPS) if long else (fillpx >= struct - EPS)
            moved = abs(res["stop"] - struct) > 1e-6
            s = res["stop"]
            hit_on_fill_bar = ((bars[j].low <= s + EPS) if long
                               else (bars[j].high >= s - EPS))
            flags[f][k] = {"collapsed": bool(collapsed), "stop_moved": bool(moved),
                           "hit_on_fill_bar": bool(hit_on_fill_bar),
                           "j": j, "i": i}
            if collapsed:
                diag[f]["collapsed"] += 1
            if moved:
                diag[f]["stop_moved_to_fill_bar_extreme"] += 1
            if hit_on_fill_bar:
                diag[f]["stop_touched_on_unmanaged_fill_bar"] += 1

    # ------------------------------------------------------------- scoring
    def sizeable_of(res):
        if "sizeable" in res:
            return res["sizeable"]
        return abs(res["entry"] - res["stop"]) >= sr.min_risk_floor(res["entry"])

    def oneaday(rows_by_key, day_filter=None, skip_missing=True,
                drop=None, force_minus_1r=None):
        picked = []
        for d in sorted(cand_by_day):
            if day_filter and not day_filter(d):
                continue
            for k in cand_by_day[d]:
                res = rows_by_key.get(k)
                if res is None:
                    if skip_missing:
                        continue
                    br = universe[k]
                    if abs(br["entry"] - br["stop"]) >= sr.min_risk_floor(br["entry"]):
                        break          # day burned on a limit that never filled
                    continue
                if not sizeable_of(res):
                    continue
                if drop and drop(k):
                    break              # the trade happened; refuse its tainted pnl
                if force_minus_1r and force_minus_1r(k):
                    res = dict(res, pnl=-RISK, r=-1.0, out="loss")
                picked.append(res)
                break
        return picked

    def days_in(h):
        return [d for d in all_days if half(d) == h]

    out_arms = {}

    def score(name, rows_by_key, **kw):
        full = oneaday(rows_by_key, **kw)
        h1 = oneaday(rows_by_key, day_filter=lambda d: half(d) == "H1", **kw)
        h2 = oneaday(rows_by_key, day_filter=lambda d: half(d) == "H2", **kw)
        st = G.price(full, n_days, all_days)
        s1 = G.price(h1, len(days_in("H1")), days_in("H1"))
        s2 = G.price(h2, len(days_in("H2")), days_in("H2"))
        out_arms[name] = {"combined": st, "H1": s1, "H2": s2,
                          "rows_priced": len(rows_by_key)}
        series[name] = day_series(full)
        print("  %-24s $%5d/day  H1 $%5d  H2 $%5d  meanR %+.3f  win %.1f%%  "
              "%d/%d green  n=%d"
              % (name, st["per_day"], s1["per_day"], s2["per_day"], st["mean_r"],
                 st["win_pct"], st["months_green"], st["months"], st["trades"]),
              flush=True)

    series = {}

    def day_series(rows):
        v = {d: 0.0 for d in all_days}
        for r in rows:
            v[r["day"]] = v.get(r["day"], 0.0) + r["pnl"]
        return [v[d] for d in all_days]

    close_book = {k: universe[k] for k in keys}
    print("\n-- reproduce g158 --", flush=True)
    score("CLOSE (book pnl, g158)", close_book)
    for f in FRACS:
        score("%s (g158)" % NAME[f], priced[f])

    print("\n-- C1 same-harness control --", flush=True)
    score("CLOSE_RT (run_trade)", close_rt)

    print("\n-- C2 no-lookahead selection (never-fill burns the day) --", flush=True)
    for f in FRACS:
        score("%s NOSKIP" % NAME[f], priced[f], skip_missing=False)

    print("\n-- C3 drop picks whose stop was moved to the fill bar's extreme --",
          flush=True)
    for f in FRACS:
        fl = flags[f]
        score("%s NOCOLLAPSE" % NAME[f], priced[f],
              drop=lambda k, fl=fl: fl.get(k, {}).get("stop_moved", False))

    print("\n-- C4 fill bar is managed: stop touched on it -> -1R --", flush=True)
    for f in FRACS:
        fl = flags[f]
        score("%s FILLBAR" % NAME[f], priced[f],
              force_minus_1r=lambda k, fl=fl: fl.get(k, {}).get("hit_on_fill_bar", False))

    print("\n-- C2+C4 together --", flush=True)
    for f in FRACS:
        fl = flags[f]
        score("%s NOSKIP+FILLBAR" % NAME[f], priced[f], skip_missing=False,
              force_minus_1r=lambda k, fl=fl: fl.get(k, {}).get("hit_on_fill_bar", False))

    # ---- paired day-level bootstrap: corrected MID vs the shipped CLOSE
    import random
    base = series["CLOSE (book pnl, g158)"]
    pairs = {}
    for nm in ("MID25 (g158)", "MID25 FILLBAR", "MID25 NOSKIP",
               "MID25 NOSKIP+FILLBAR", "MID50 NOSKIP+FILLBAR"):
        d = [a - b for a, b in zip(series[nm], base)]
        rng_ = random.Random(20260905)
        n = len(d)
        means = sorted(sum(rng_.choices(d, k=n)) / n for _ in range(5000))
        pairs[nm] = {"mean_diff_per_day": round(sum(d) / n, 1),
                     "ci95_low": round(means[125], 1),
                     "ci95_high": round(means[4875], 1)}
        print("  paired %-24s vs CLOSE: %+7.1f $/day  95%% [%+.0f, %+.0f]"
              % (nm, pairs[nm]["mean_diff_per_day"], pairs[nm]["ci95_low"],
                 pairs[nm]["ci95_high"]), flush=True)

    burn = Counter()
    for f in FRACS:
        for d in sorted(cand_by_day):
            for k in cand_by_day[d]:
                br = universe[k]
                if abs(br["entry"] - br["stop"]) < sr.min_risk_floor(br["entry"]):
                    continue
                if k not in priced[f]:
                    burn[NAME[f]] += 1
                break

    payload = {"book": BOOK.name, "sessions": n_days, "candidates": len(keys),
               "arms": out_arms,
               "diagnostics": {NAME[f]: dict(diag[f]) for f in FRACS},
               "paired_vs_close": pairs,
               "days_whose_first_sizeable_candidate_never_filled": dict(burn),
               "total_days": len(cand_by_day)}
    json.dump(payload, open(OUT, "w", encoding="utf-8"), indent=1)
    print("\ndiagnostics:", json.dumps(payload["diagnostics"], indent=1))
    print("first-candidate-never-filled days:", dict(burn), "of", len(cand_by_day))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
