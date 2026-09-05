"""g201 refute #3 -- the F9/MID25 claim, reproduced then attacked with controls.

F9 (research/g158_mid_candle_arms.md, commit 685b50e5) claims a limit resting
strictly after the signal bar at 25% of that bar's range back toward the level
pays $100/day one-trade-a-day against the shipped CLOSE arm's $34/day.

g158 scores CLOSE off the BOOK ROWS' own `pnl` field and scores every MID arm
through `g80_ordertype_grid.run_trade`. Those are two different exit engines.
This script holds the ENTRY PRICE fixed and varies only the machinery, then
holds the MACHINERY fixed and varies only the price, so the two effects can be
told apart.

ARMS
  CLOSE        g158's control, verbatim: the book row's own pnl.
  CLOSE_RT     THE NULL CONTROL. Identical entry price (the book's own close)
               and identical entry bar, priced through run_trade. A placebo:
               nothing about the entry changed, so any $/day difference from
               CLOSE is the harness, not the fill.
  MID00        SECOND NULL. A limit resting strictly after the signal bar at
               0% of the bar's range back -- i.e. AT the same close price
               MID25 measures from. Same waiting, same stop-move, same exits
               as MID25, but no price improvement at all.
  ANTI25       ADVERSARIAL. A limit resting 25% of the range on the WRONG side
               of the close (away from the level) -- a strictly WORSE entry
               price than CLOSE. Under the claim's own logic this must lose.
  MID25        g158's headline, reproduced.
  MID25_STRICT ADVERSARIAL. MID25 but price must trade a full cent THROUGH the
               limit (no bar-extreme-equals-limit fills). The test that killed
               scale-before-the-level in F5.
  MID25_PAIRED ADVERSARIAL. MID25 priced only on the candidate CLOSE_RT
               actually picked that day; a no-fill books $0 rather than
               promoting the next candidate.

Fill: signal-bar CLOSE for CLOSE/CLOSE_RT; strictly-after-signal resting-limit
touch for the rest. Exits via g80_ordertype_grid.run_trade (backtest_week
_ladder_bar + stop_rule). Size-gated on signal_runner.min_risk_floor.
1R = $1,000. One-trade-a-day = first sizeable candidate of the day in signal
order. H1 < 2025-09-01 <= H2.

    python research/g201_refute3.py
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G   # noqa: E402
import signal_runner as sr                     # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT_JSON = ROOT / "research" / "g201_refute3.json"
RISK = 1000.0
BAR_PER_DAY = 397.0
SPLIT_DAY = "2025-09-01"
EPS = G.EPS
SEED = 20260905
BOOTS = 10000


def half(day):
    return "H1" if day < SPLIT_DAY else "H2"


def limit_touch_strict(bars, lvl, long, j0, j1):
    """MID25_STRICT: the bar must trade a full cent THROUGH the limit."""
    for j in range(max(j0, 0), min(j1, len(bars))):
        c = bars[j]
        if long and c.low <= lvl - 0.01 + EPS:
            return j, min(lvl, c.open)
        if (not long) and c.high >= lvl + 0.01 - EPS:
            return j, max(lvl, c.open)
    return None, None


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, allrows = book["meta"], book["trades"]
    all_days = sorted({r["day"] for r in allrows})
    n_days = meta["sessions"]
    print("book %s: %d sessions, entry_fill=%s"
          % (BOOK.name, n_days, meta.get("entry_fill")), flush=True)

    universe = {i: r for i, r in enumerate(allrows)
                if r.get("traded") or r["status"] == "halted"}
    keys = sorted(universe, key=lambda i: (allrows[i]["day"], allrows[i]["et"],
                                           allrows[i]["sym"], i))
    print("  %d candidates" % len(keys), flush=True)

    cand_by_day = defaultdict(list)
    for k in keys:
        cand_by_day[allrows[k]["day"]].append(k)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"], i))

    ARMS = ["CLOSE_RT", "MID00", "ANTI25", "MID25", "MID25_STRICT"]
    priced = {a: {} for a in ARMS}
    nofill = {a: Counter() for a in ARMS}

    for n, k in enumerate(keys):
        if n and n % 2000 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r["entry_i"]
        if not bars or i >= len(bars):
            for a in ARMS:
                nofill[a]["no_bars"] += 1
            continue
        long = r["dir"] == "call"
        entry_close = r["entry"]

        # CLOSE_RT -- the null: same price, same bar, run_trade machinery.
        if i < len(bars) - 1:
            res = G.run_trade(r, bars, i, entry_close, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is None:
                nofill["CLOSE_RT"]["risk_collapsed"] += 1
            else:
                priced["CLOSE_RT"][k] = res
        else:
            nofill["CLOSE_RT"]["signal_bar_is_last"] += 1

        rng = bars[i].high - bars[i].low
        cutoff = G.cutoff_idx(bars)
        if rng <= 0 or i + 1 >= min(cutoff, len(bars) - 1):
            for a in ARMS[1:]:
                nofill[a]["no_bars_after_signal"] += 1
            continue

        specs = [
            ("MID00", entry_close, G.limit_touch),
            ("ANTI25", entry_close + 0.25 * rng if long
                       else entry_close - 0.25 * rng, None),
            ("MID25", entry_close - 0.25 * rng if long
                      else entry_close + 0.25 * rng, G.limit_touch),
            ("MID25_STRICT", entry_close - 0.25 * rng if long
                             else entry_close + 0.25 * rng, limit_touch_strict),
        ]
        for name, px, toucher in specs:
            fillpx = None
            if name == "ANTI25":
                # a worse price is ABOVE the close for a long: it fills when a
                # LATER bar trades UP through it -- the mirror of limit_touch.
                j = None
                for jj in range(i + 1, min(cutoff, len(bars))):
                    c = bars[jj]
                    if long and c.high >= px - EPS:
                        j, fillpx = jj, max(px, c.open)
                        break
                    if (not long) and c.low <= px + EPS:
                        j, fillpx = jj, min(px, c.open)
                        break
            else:
                j, fillpx = toucher(bars, px, long, i + 1, cutoff)
            if j is None:
                nofill[name]["limit_never_touched"] += 1
                continue
            if j >= len(bars) - 1:
                nofill[name]["filled_on_last_bar"] += 1
                continue
            res = G.run_trade(r, bars, j, fillpx, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is None:
                nofill[name]["risk_collapsed"] += 1
                continue
            priced[name][k] = res

    # ---------------------------------------------------------- one-a-day
    close_rows = {k: universe[k] for k in keys}

    def sizeable_of(res):
        if "sizeable" in res:
            return res["sizeable"]
        return abs(res["entry"] - res["stop"]) >= sr.min_risk_floor(
            res.get("close", res["entry"]))

    def oneaday_for(rows_by_key, day_filter=None):
        picked, picks = [], {}
        for d in sorted(cand_by_day):
            if day_filter and not day_filter(d):
                continue
            for k in cand_by_day[d]:
                res = rows_by_key.get(k)
                if res is None:
                    continue
                if sizeable_of(res):
                    picked.append(res)
                    picks[d] = k
                    break
        return picked, picks

    def days_in_half(h):
        return [d for d in all_days if half(d) == h]

    arms_out, day_pnl = {}, {}

    def score(name, rows):
        full, picks = oneaday_for(rows)
        h1, _ = oneaday_for(rows, lambda d: half(d) == "H1")
        h2, _ = oneaday_for(rows, lambda d: half(d) == "H2")
        st = G.price(full, n_days, all_days)
        arms_out[name] = {
            "combined": st,
            "H1": G.price(h1, len(days_in_half("H1")), days_in_half("H1")),
            "H2": G.price(h2, len(days_in_half("H2")), days_in_half("H2")),
            "pct_of_bar_combined": round(st["per_day"] / BAR_PER_DAY * 100, 1),
            "rows_priced": len(rows),
        }
        by_d = {d: 0.0 for d in all_days}
        for r in full:
            by_d[r["day"]] += r["pnl"]
        day_pnl[name] = by_d
        print("  %-13s $%5d/day (%5.1f%%)  H1 $%5d  H2 $%5d  meanR %+.3f  "
              "win %.1f%%  %d/%d green  n=%d"
              % (name, st["per_day"], arms_out[name]["pct_of_bar_combined"],
                 arms_out[name]["H1"]["per_day"], arms_out[name]["H2"]["per_day"],
                 st["mean_r"], st["win_pct"], st["months_green"], st["months"],
                 st["trades"]), flush=True)
        return picks

    print("\nARMS (one-trade-a-day, size-gated, 1R=$1,000):", flush=True)
    score("CLOSE", close_rows)
    rt_picks = score("CLOSE_RT", priced["CLOSE_RT"])
    score("MID00", priced["MID00"])
    score("ANTI25", priced["ANTI25"])
    mid_picks = score("MID25", priced["MID25"])
    score("MID25_STRICT", priced["MID25_STRICT"])

    # MID25_PAIRED -- MID25 priced ONLY on the day-pick CLOSE_RT made.
    paired = {}
    for d, k in rt_picks.items():
        res = priced["MID25"].get(k)
        if res is not None and sizeable_of(res):
            paired[k] = res
    rows_p = list(paired.values())
    st_p = G.price(rows_p, n_days, all_days)
    h1r = [r for r in rows_p if half(r["day"]) == "H1"]
    h2r = [r for r in rows_p if half(r["day"]) == "H2"]
    arms_out["MID25_PAIRED"] = {
        "combined": st_p,
        "H1": G.price(h1r, len(days_in_half("H1")), days_in_half("H1")),
        "H2": G.price(h2r, len(days_in_half("H2")), days_in_half("H2")),
        "pct_of_bar_combined": round(st_p["per_day"] / BAR_PER_DAY * 100, 1),
        "rows_priced": len(paired),
    }
    by_d = {d: 0.0 for d in all_days}
    for r in rows_p:
        by_d[r["day"]] += r["pnl"]
    day_pnl["MID25_PAIRED"] = by_d
    print("  %-13s $%5d/day (%5.1f%%)  H1 $%5d  H2 $%5d  meanR %+.3f  win %.1f%%  "
          "%d/%d green  n=%d"
          % ("MID25_PAIRED", st_p["per_day"],
             arms_out["MID25_PAIRED"]["pct_of_bar_combined"],
             arms_out["MID25_PAIRED"]["H1"]["per_day"],
             arms_out["MID25_PAIRED"]["H2"]["per_day"], st_p["mean_r"],
             st_p["win_pct"], st_p["months_green"], st_p["months"],
             st_p["trades"]), flush=True)

    # how often does the arm's own day-pick differ from the null's, and does
    # the whole gap live on exactly those days?
    reshuffled = [d for d in rt_picks if mid_picks.get(d) != rt_picks.get(d)]
    diff_picks = len(reshuffled)
    same = [d for d in rt_picks if mid_picks.get(d) == rt_picks.get(d)]
    gap_resh = sum(day_pnl["MID25"][d] - day_pnl["CLOSE_RT"][d] for d in reshuffled)
    gap_same = sum(day_pnl["MID25"][d] - day_pnl["CLOSE_RT"][d] for d in same)
    print("\nday-picks where MID25 chose a DIFFERENT candidate than CLOSE_RT: "
          "%d of %d" % (diff_picks, len(rt_picks)), flush=True)
    print("  MID25 minus CLOSE_RT, total $: reshuffled days $%d, same-pick days $%d"
          % (round(gap_resh), round(gap_same)), flush=True)
    # on a reshuffled day the SKIPPED order is still live until 11:00, so the
    # promoted candidate could only be taken by knowing the future.
    lookahead = 0
    for d in reshuffled:
        sk, pr = rt_picks[d], mid_picks.get(d)
        if pr is None:
            continue
        if allrows[pr]["et"] < "11:00":
            lookahead += 1
    print("  promoted picks that fired while the skipped limit was still live: "
          "%d of %d" % (lookahead, diff_picks), flush=True)

    # ----------------------------------------------- paired bootstrap on days
    rng_ = random.Random(SEED)

    def paired_ci(a, b):
        va, vb = day_pnl[a], day_pnl[b]
        diffs = [va[d] - vb[d] for d in all_days]
        n = len(diffs)
        means = sorted(sum(rng_.choices(diffs, k=n)) / n for _ in range(BOOTS))
        return {"mean_diff_per_day": round(sum(diffs) / n, 1),
                "ci95_low": round(means[int(BOOTS * 0.025)], 1),
                "ci95_high": round(means[int(BOOTS * 0.975)], 1)}

    cis = {
        "CLOSE_RT_minus_CLOSE": paired_ci("CLOSE_RT", "CLOSE"),
        "MID00_minus_CLOSE": paired_ci("MID00", "CLOSE"),
        "ANTI25_minus_CLOSE": paired_ci("ANTI25", "CLOSE"),
        "MID25_minus_CLOSE": paired_ci("MID25", "CLOSE"),
        "MID25_minus_CLOSE_RT": paired_ci("MID25", "CLOSE_RT"),
        "MID00_minus_CLOSE_RT": paired_ci("MID00", "CLOSE_RT"),
        "MID25_minus_MID00": paired_ci("MID25", "MID00"),
        "MID25_PAIRED_minus_CLOSE_RT": paired_ci("MID25_PAIRED", "CLOSE_RT"),
    }
    print("\nPAIRED 95%% bootstrap over the %d sessions ($/day):" % n_days,
          flush=True)
    for k, v in cis.items():
        print("  %-30s %+7.1f  [%+8.1f, %+8.1f]"
              % (k, v["mean_diff_per_day"], v["ci95_low"], v["ci95_high"]),
              flush=True)

    out = {"book": BOOK.name, "sessions": n_days, "candidates": len(keys),
           "split_day": SPLIT_DAY, "arms": arms_out,
           "nofill": {a: dict(nofill[a].most_common(6)) for a in ARMS},
           "paired_ci": cis,
           "day_picks_differing_MID25_vs_CLOSE_RT": diff_picks,
           "day_picks_total": len(rt_picks),
           "gap_dollars_on_reshuffled_days": round(gap_resh),
           "gap_dollars_on_same_pick_days": round(gap_same),
           "promoted_while_skipped_limit_live": lookahead}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("\nwrote", OUT_JSON)


if __name__ == "__main__":
    main()
