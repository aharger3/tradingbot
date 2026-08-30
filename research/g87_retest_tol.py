"""g87 -- what IS the retest tolerance? Austin asked for the stress test.

His words, 2026-08-30, on mentor ballot rule 1:

    "except it doesn't follow the 25 percent candle unit, its just if its close
     but didnt actually touch, within a few cents give or take, you stress test
     and find the best metric yourself"

That is a direct correction of a shipped constant. `BAR_EXTREME_FRAC` (25% of the
previous candle's range) governs the ON WATCH entry trigger, the 84% reclaim
window and stop slippage -- and this says it is the WRONG UNIT for the retest.
A retest counts when price comes CLOSE to the level, a few cents shy, without
printing it.

Mechanically that is one thing: a resting buy limit does not sit AT the level, it
sits a tolerance ABOVE it, so a near-miss still fills. Bigger tolerance = more
fills at a slightly worse price and a wider stop. There is an optimum and it is
findable.

FOUR CANDIDATE METRICS, because "a few cents" is not scale-free -- 3 cents on a
$20 stock is 15 bps and on QQQ at $580 it is half a basis point, and this book
holds both:

    cents      fixed dollars off the level
    bps        fraction of the level's own price      <- the trader's unit
    prevrange  fraction of the arming bar's range     <- the incumbent, BAR_EXTREME_FRAC
    atr        fraction of the 14-bar ATR at arming

WHAT THIS RIG IS. It re-prices the committed book; it does not re-detect. Every
exit is the shipped ladder (`backtest_week._ladder_bar`) and every helper --
`day_pack`, `arm_index`, `limit_touch`, `run_trade`, `price`, `day_ci` -- is
imported from `research/g80_ordertype_grid.py` rather than re-written, so an arm
here is comparable to a policy there line for line. Only the resting PRICE moves.

THE LOOK-AHEAD RULE. An order cannot rest before it exists. The limit is armed at
`arm_index() + 1` -- the first bar after the setup left the level -- exactly as
g80 policy A does, and the same discipline `entry_fill.py` documents: letting the
order rest early once turned a +$92/day arm into a fabricated -$252/day.

    python research/g87_retest_tol.py            # full sweep, ~1 candidate pass
    python research/g87_retest_tol.py --arms 4   # smoke test on 4 arms

Nothing here is applied. It answers one question: which metric, and how much.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G      # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT_JSON = ROOT / "research" / "g87_retest_tol.json"
OUT_MD = ROOT / "research" / "g87_retest_tol.md"
BAR_PER_DAY = 397.0
ATR_N = 14


# ------------------------------------------------------------- the tolerance

def atr_at(bars, j, n=ATR_N):
    """True range average over the n bars ending at j. Causal by construction."""
    lo = max(1, j - n + 1)
    if j < 1:
        return None
    trs = []
    for k in range(lo, j + 1):
        c, p = bars[k], bars[k - 1]
        trs.append(max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)))
    return sum(trs) / len(trs) if trs else None


def tol_price(metric, size, level, bars, arm):
    """Dollars to shift the resting limit by, or None when the metric cannot be
    computed on this bar (reported as a no-fill reason, never silently zeroed)."""
    if size == 0:
        return 0.0
    if metric == "cents":
        return size
    if metric == "bps":
        return level * size / 10000.0
    if metric == "prevrange":
        if arm is None or arm >= len(bars):
            return None
        c = bars[arm]
        return (c.high - c.low) * size
    if metric == "atr":
        a = atr_at(bars, arm) if arm is not None else None
        return None if a is None else a * size
    raise ValueError(metric)


def resolve_tol_entry(row, bars, arm, metric, size):
    """g80 policy A with the limit shifted by the tolerance.

    A resting BUY sits `tol` ABOVE the level so a near-miss fills; a resting
    SELL sits `tol` BELOW it. Returns (fill_i, price, tag) or (None, None, why).
    """
    i, lvl, long = row["entry_i"], row["level_px"], row["dir"] == "call"
    if arm is None:
        return None, None, "arming_bar_untraced"
    tol = tol_price(metric, size, lvl, bars, arm)
    if tol is None:
        return None, None, "tolerance_uncomputable"
    rest = lvl + tol if long else lvl - tol
    cut = G.cutoff_idx(bars)
    j, px = G.limit_touch(bars, rest, long, arm + 1, cut)
    if j is None:
        return None, None, "limit_never_touched"
    if j >= len(bars) - 1:
        return None, None, "filled_on_last_bar"
    return j, px, ("early" if j < i else "on_signal_bar" if j == i else "late")


# ------------------------------------------------------------------ the arms

def build_arms(limit=None):
    """(name, metric, size, move_stop) for every arm.

    THE STOP DIMENSION, added after the first run and it is the whole story.
    `signal_runner.intrabar_stop` moves the stop to the ENTRY BAR's own extreme.
    On a long break-and-retest a limit resting ABOVE the level fills early inside
    a bar that is still falling toward it -- so the bar's low is at or below the
    level and the risk denominator collapses to the tolerance itself. That is why
    a 2-cent tolerance came back 97.6% unsizeable while a limit AT the level came
    back 84.9%: widening it did not buy fills, it bought un-takeable ones.

    `struct` holds the stop where the setup put it, below the level. Then a
    2-cent-early fill costs 2 cents of extra risk instead of destroying the
    trade. That is what a trader actually does with a resting order, and it is
    the reading Austin's rule needs to be tested under."""
    sizes = [("AT_LEVEL", "cents", 0.0)]
    for size in (0.02, 0.05, 0.10, 0.20):
        sizes.append(("cents_%.2f" % size, "cents", size))
    for size in (2, 5, 10, 20):
        sizes.append(("bps_%d" % size, "bps", float(size)))
    for size in (0.10, 0.25, 0.50):
        sizes.append(("prevrange_%.2f" % size, "prevrange", size))
    for size in (0.05, 0.10, 0.25):
        sizes.append(("atr_%.2f" % size, "atr", size))
    arms = [("BOOK", None, None, True)]
    for move, tag in ((True, ""), (False, "|struct")):
        for name, metric, size in sizes:
            arms.append((name + tag, metric, size, move))
    return arms[:limit] if limit else arms


# -------------------------------------------------------------------- pricing

def main():
    limit = None
    if "--arms" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--arms") + 1])

    book = json.load(open(BOOK, encoding="utf-8"))
    meta, allrows = book["meta"], book["trades"]
    n_days = meta["sessions"]
    all_days = sorted({r["day"] for r in allrows})
    arms = build_arms(limit)

    universe = {i: r for i, r in enumerate(allrows)
                if r.get("traded") or r["status"] == "halted"}
    keys = sorted(universe, key=lambda i: (allrows[i]["day"], allrows[i]["et"],
                                           allrows[i]["sym"], i))
    print("book %s: %d candidates, %d sessions, %d arms"
          % (BOOK.name, len(keys), n_days, len(arms)), flush=True)

    priced = {a[0]: {} for a in arms}
    nofill = {a[0]: Counter() for a in arms}
    lead = defaultdict(list)          # bars EARLIER than the book's own entry

    for n, k in enumerate(keys):
        if n and n % 500 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        if not bars or r["entry_i"] >= len(bars):
            for a in arms:
                nofill[a[0]]["no_bars"] += 1
            continue
        arm_i, _how = G.arm_index(r, bars)
        for name, metric, size, move_stop in arms:
            if name == "BOOK":
                fi, px, tag = ((r["entry_i"], r["entry"], "shipped")
                               if r["entry_i"] < len(bars) - 1
                               else (None, None, "signal_bar_is_last"))
            else:
                fi, px, tag = resolve_tol_entry(r, bars, arm_i, metric, size)
            if fi is None:
                nofill[name][tag] += 1
                continue
            res = G.run_trade(r, bars, fi, px, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=move_stop)
            if res is None:
                nofill[name]["risk_collapsed"] += 1
                continue
            res["tag"] = tag
            priced[name][k] = res
            if name != "BOOK":
                lead[name].append(r["entry_i"] - fi)

    # ---- one trade a day: the first candidate of the day that actually filled
    cand_by_day = defaultdict(list)
    for k in keys:
        r = allrows[k]
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            cand_by_day[r["day"]].append(k)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"], i))

    out = {"bar_per_day": BAR_PER_DAY, "book": BOOK.name, "sessions": n_days,
           "candidates": len(keys), "arms": {}}
    for name, metric, size, move_stop in arms:
        # THE SIZE GATE, and it is not optional. 1R is a fixed $1,000, so a fill
        # that lands a cent from its stop is a 100,000-share position and an
        # R-multiple with a one-cent denominator. Without this the sweep prints
        # $15,119/day at a 30% win rate -- pure arithmetic. Same gate g80 applies
        # (signal_runner.min_risk_floor), applied to EVERY arm including the
        # control so the comparison stays like-for-like.
        oneaday, oneaday_raw = [], []
        for d in sorted(cand_by_day):
            took = took_raw = False
            for k in cand_by_day[d]:
                res = priced[name].get(k)
                if res is None:
                    continue
                if not took_raw:
                    oneaday_raw.append(res)
                    took_raw = True
                if res["sizeable"] and not took:
                    oneaday.append(res)
                    took = True
                if took and took_raw:
                    break
        every = [r for r in priced[name].values() if r["sizeable"]]
        unsizeable = sum(1 for r in priced[name].values() if not r["sizeable"])
        st = G.price(oneaday, n_days, all_days)
        ci = G.day_ci(oneaday, all_days)
        leads = sorted(lead[name])
        out["arms"][name] = {
            "metric": metric, "size": size, "move_stop_to_entry_bar": move_stop,
            "oneaday": st, "oneaday_ci": ci,
            "pct_of_bar": round(st["per_day"] / BAR_PER_DAY * 100, 1),
            "days_filled": len(oneaday),
            "fill_rate_pct": round(len(oneaday) / len(cand_by_day) * 100, 1),
            "every_trade": G.price(every, n_days, all_days),
            "ungated_oneaday_per_day": G.price(oneaday_raw, n_days, all_days)["per_day"],
            "unsizeable_fills": unsizeable,
            "unsizeable_pct": round(unsizeable / max(1, len(priced[name])) * 100, 1),
            "median_bars_early": (leads[len(leads) // 2] if leads else None),
            "pct_filled_before_signal": (
                round(sum(1 for x in leads if x > 0) / len(leads) * 100, 1)
                if leads else None),
            "nofill": dict(nofill[name].most_common(6)),
        }
        print("  %-16s $%5d/day  %4.1f%% of bar  win %4.1f%%  %2d/%d green  "
              "fills %4.1f%%  early %s  unsizeable %4.1f%% (ungated $%d)"
              % (name, st["per_day"], out["arms"][name]["pct_of_bar"],
                 st["win_pct"], st["months_green"], st["months"],
                 out["arms"][name]["fill_rate_pct"],
                 out["arms"][name]["median_bars_early"],
                 out["arms"][name]["unsizeable_pct"],
                 out["arms"][name]["ungated_oneaday_per_day"]), flush=True)

    best = max((a for n, a in out["arms"].items() if n != "BOOK"),
               key=lambda a: a["oneaday"]["per_day"])
    out["best_arm"] = next(n for n, a in out["arms"].items() if a is best)
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g87 -- the retest tolerance, stress tested", "",
          "> Austin, 2026-08-30: *\"it doesn't follow the 25 percent candle unit, "
          "its just if its close but didnt actually touch, within a few cents give "
          "or take, you stress test and find the best metric yourself.\"*", "",
          "A resting buy limit sits `tol` **above** the level so a near-miss still "
          "fills. One pass over `%s`, %d candidates, %d sessions. Every exit is the "
          "shipped ladder; only the resting price moves. Bar: **$%d/day**."
          % (BOOK.name, len(keys), n_days, BAR_PER_DAY), "",
          "| arm | $/day | 95% band | % of bar | win | mean R | green | fill rate | bars early | unsizeable |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, _m, _s, _ms in arms:
        a = out["arms"][name]
        st, ci = a["oneaday"], a["oneaday_ci"]
        md.append("| %s%s | $%d | [$%d, $%d] | %.1f%% | %.1f%% | %+.3f | %d/%d | %.1f%% | %s | %.1f%% |"
                  % ("**" if name == out["best_arm"] else "", name,
                     st["per_day"], ci["ci95_low"], ci["ci95_high"],
                     a["pct_of_bar"], st["win_pct"], st["mean_r"],
                     st["months_green"], st["months"], a["fill_rate_pct"],
                     a["median_bars_early"], a["unsizeable_pct"]))
    md += ["", "`BOOK` is the shipped fill on this book (control). `AT_LEVEL` is a "
           "resting limit exactly at the level -- tolerance zero, the thing Austin "
           "says is wrong. Everything below it is his near-miss rule at a different "
           "size.", "",
           "**Every arm is SIZE GATED** (`signal_runner.min_risk_floor`). 1R is a "
           "fixed $1,000, so a fill landing a cent from its stop is a 100,000-share "
           "position and an R-multiple with a one-cent denominator. Ungated, this "
           "sweep prints four-figure and five-figure days that are arithmetic, not "
           "money -- the `unsizeable` column is how much of each arm that would "
           "have been, and `ungated_oneaday_per_day` in the JSON is what it would "
           "have falsely claimed.", "",
           "**Read the 95%% bands before picking a winner.** The standing error bar "
           "on this project is +/-1.5799R; arms whose bands overlap are a tie no "
           "matter how the point estimates sort.", ""]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\nbest arm: %s" % out["best_arm"])
    print("wrote %s\nwrote %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
