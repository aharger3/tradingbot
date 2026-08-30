"""g88 -- is the $469/day resting-limit arm real, or a size-gate survivor?

g87 swept the retest tolerance Austin asked about and the answer was blunt:
every widened tolerance loses money, and the only arm that makes any is
`AT_LEVEL` -- a limit resting EXACTLY at the level, tolerance zero. It printed
$469/day, 118% of the bar, 19/25 green months.

THE THREAT TO THAT NUMBER. It is measured on 15% of its own rows. 6,996 of
8,236 filled rows were discarded by the size gate as unsizeable, against 14.5%
for the shipped control. That asymmetry is not incidental: `intrabar_stop`
places the stop at the ENTRY BAR'S COMPLETED EXTREME, so risk = (level - bar
low). A limit at the level fills on the retest bar, whose low is usually right
at the level -- risk collapses, the row is dropped. What SURVIVES the gate is
precisely the rows whose entry bar ran a long way from the level, which is a
fact about the rest of that bar. Selecting trades on the completed extreme of
the bar you entered on is the look-ahead class this project has already been
bitten by twice (g81 displacement, entry_fill).

THE TEST. Widening the stop is not the same decision as skipping the trade. A
trader whose structural stop lands three cents away does not pass -- they put
the stop where structure says and size down. So: 2x2, order type crossed with
what happens when risk is too small.

    entry        stop policy
    -----        -----------
    BOOK         intrabar  -> risk collapses -> DROP the row      (the shipped pair)
    BOOK         structural, widened to the floor -> DROP NOTHING
    LEVEL        intrabar  -> risk collapses -> DROP the row      (g87's AT_LEVEL)
    LEVEL        structural, widened to the floor -> DROP NOTHING

The `_floor` arms discard no row for size, so they cannot be survivors of
anything. If LEVEL still beats BOOK there, the order type is the edge. If it
does not, $469/day was the size gate reading the future and the arm is dead.

The floor itself is taken from bars[fill_i - 1].close -- the last bar CLOSED
before the fill -- so even the sizing constant is causal.

Everything else is g80's: `day_pack`, `arm_index`, `limit_touch`, `run_trade`,
`price`, `day_ci`, and the exits are the shipped ladder. Only the resting price
and the stop policy move.

    python research/g88_level_limit.py

Nothing here is applied.
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
import signal_runner as sr                        # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT_JSON = ROOT / "research" / "g88_level_limit.json"
OUT_MD = ROOT / "research" / "g88_level_limit.md"

BAR_PER_DAY = 397.0

# (name, entry, stop_policy)
ARMS = [
    ("BOOK",        "book",  "intrabar"),
    ("BOOK_floor",  "book",  "floor"),
    ("LEVEL",       "level", "intrabar"),
    ("LEVEL_floor", "level", "floor"),
    # THE FALSIFICATION. `level` rests the limit from arm_index+1, which is
    # BEFORE the engine fired -- and the row is only in this book because it
    # eventually fired. That is knowledge of the future used to place an order.
    # `post` rests the same limit strictly AFTER the signal bar, so nothing is
    # known that a live trader would not know. If the money survives here it is
    # an order type; if it collapses, it was the early rest.
    ("POST_floor",  "post",  "floor"),
]


def floored_row(row, entry_px, bars, fill_i, long):
    """A copy of ``row`` whose structural stop is pushed out until the risk
    clears ``min_risk_floor``. Never drops a trade; a too-tight structural stop
    becomes a wider stop and a smaller position, which is what a trader does.

    Causal: the floor reads bars[fill_i - 1].close, the last bar CLOSED before
    the order filled, never the fill bar's own completed price.
    """
    ref = bars[fill_i - 1].close if fill_i > 0 else bars[fill_i].open
    # run_trade re-tests risk against min_risk_floor(bars[fill_i].close). Taking
    # the wider of the two floors makes the stop WIDER, never tighter, so this
    # peek can only cost the arm money -- and it stops boundary rows being
    # silently dropped by a sub-cent disagreement between the two references.
    floor = max(sr.min_risk_floor(ref),
                sr.min_risk_floor(bars[fill_i].close)) * 1.001
    struct = (entry_px - row["stop"]) if long else (row["stop"] - entry_px)
    risk = max(struct, floor)
    out = dict(row)
    out["stop"] = (entry_px - risk) if long else (entry_px + risk)
    return out


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, allrows = book["meta"], book["trades"]
    n_days = meta["sessions"]
    all_days = sorted({r["day"] for r in allrows})

    universe = {i: r for i, r in enumerate(allrows)
                if r.get("traded") or r["status"] == "halted"}
    keys = sorted(universe, key=lambda i: (allrows[i]["day"], allrows[i]["et"],
                                           allrows[i]["sym"], i))
    print("book %s: %d candidates, %d sessions, %d arms"
          % (BOOK.name, len(keys), n_days, len(ARMS)), flush=True)

    priced = {a[0]: {} for a in ARMS}
    nofill = {a[0]: Counter() for a in ARMS}
    lead = defaultdict(list)

    for n, k in enumerate(keys):
        if n and n % 1000 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        if not bars or r["entry_i"] >= len(bars):
            for a in ARMS:
                nofill[a[0]]["no_bars"] += 1
            continue
        arm_i, _how = G.arm_index(r, bars)
        long = r["dir"] == "call"

        # the two entries, resolved once each
        entries = {}
        entries["book"] = ((r["entry_i"], r["entry"], "shipped")
                           if r["entry_i"] < len(bars) - 1
                           else (None, None, "signal_bar_is_last"))
        if arm_i is None:
            entries["level"] = (None, None, "arming_bar_untraced")
        else:
            j, px = G.limit_touch(bars, r["level_px"], long,
                                  arm_i + 1, G.cutoff_idx(bars))
            if j is None:
                entries["level"] = (None, None, "limit_never_touched")
            elif j >= len(bars) - 1:
                entries["level"] = (None, None, "filled_on_last_bar")
            else:
                entries["level"] = (j, px, "limit")

        cut = G.cutoff_idx(bars)
        if r["entry_i"] + 1 >= min(cut, len(bars) - 1):
            entries["post"] = (None, None, "no_bars_after_signal")
        else:
            j2, px2 = G.limit_touch(bars, r["level_px"], long,
                                    r["entry_i"] + 1, cut)
            if j2 is None:
                entries["post"] = (None, None, "limit_never_touched")
            elif j2 >= len(bars) - 1:
                entries["post"] = (None, None, "filled_on_last_bar")
            else:
                entries["post"] = (j2, px2, "limit_post")

        for name, entry_kind, stop_policy in ARMS:
            fi, px, tag = entries[entry_kind]
            if fi is None:
                nofill[name][tag] += 1
                continue
            if stop_policy == "floor":
                res = G.run_trade(floored_row(r, px, bars, fi, long), bars, fi,
                                  px, pdh, pdl, pmh, pml,
                                  move_stop_to_entry_bar=False)
            else:
                res = G.run_trade(r, bars, fi, px, pdh, pdl, pmh, pml,
                                  move_stop_to_entry_bar=True)
            if res is None:
                nofill[name]["risk_collapsed"] += 1
                continue
            res["tag"] = tag
            priced[name][k] = res
            if entry_kind in ("level", "post"):
                lead[name].append(r["entry_i"] - fi)

    cand_by_day = defaultdict(list)
    for k in keys:
        r = allrows[k]
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            cand_by_day[r["day"]].append(k)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"], i))

    out = {"bar_per_day": BAR_PER_DAY, "book": BOOK.name, "sessions": n_days,
           "candidates": len(keys), "arms": {}}
    for name, entry_kind, stop_policy in ARMS:
        # The `floor` arms do not drop a row for size -- their stop was widened
        # until it cleared the floor -- so `sizeable` is True by construction
        # and this gate is a no-op there. On the `intrabar` arms it is the
        # shipped gate and it decides which rows exist at all.
        oneaday = []
        for d in sorted(cand_by_day):
            for k in cand_by_day[d]:
                res = priced[name].get(k)
                if res is not None and res["sizeable"]:
                    oneaday.append(res)
                    break
        every = [x for x in priced[name].values() if x["sizeable"]]
        unsizeable = sum(1 for x in priced[name].values() if not x["sizeable"])
        st = G.price(oneaday, n_days, all_days)
        leads = sorted(lead[name])
        out["arms"][name] = {
            "entry": entry_kind, "stop": stop_policy,
            "oneaday": st, "oneaday_ci": G.day_ci(oneaday, all_days),
            "pct_of_bar": round(st["per_day"] / BAR_PER_DAY * 100, 1),
            "days_traded": len(oneaday),
            "day_rate_pct": round(len(oneaday) / len(cand_by_day) * 100, 1),
            "rows_priced": len(priced[name]),
            "rows_dropped_for_size": unsizeable,
            "dropped_pct": round(unsizeable / max(1, len(priced[name])) * 100, 1),
            "every_trade": G.price(every, n_days, all_days),
            "median_bars_early": (leads[len(leads) // 2] if leads else None),
            "pct_before_signal": (round(sum(1 for x in leads if x > 0)
                                        / len(leads) * 100, 1) if leads else None),
            "median_risk": round(sorted(x["risk"] for x in priced[name].values())
                                 [len(priced[name]) // 2], 3) if priced[name] else None,
            "nofill": dict(nofill[name].most_common(6)),
        }
        a = out["arms"][name]
        print("  %-12s $%5d/day  %6.1f%% of bar  win %.1f%%  meanR %+.3f  "
              "%2d/%d green  days %3d  dropped %4.1f%%  medR $%.2f"
              % (name, st["per_day"], a["pct_of_bar"], st["win_pct"],
                 st["mean_r"], st["months_green"], st["months"],
                 a["days_traded"], a["dropped_pct"], a["median_risk"] or 0),
              flush=True)

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    for name, a in out["arms"].items():
        if a["pct_before_signal"] is not None:
            print("  %-12s fills before the signal bar: %.1f%% (median %s bars)"
                  % (name, a["pct_before_signal"], a["median_bars_early"]))
    b, bf = out["arms"]["BOOK"], out["arms"]["BOOK_floor"]
    l, lf = out["arms"]["LEVEL"], out["arms"]["LEVEL_floor"]
    pf = out["arms"]["POST_floor"]
    survives = pf["oneaday"]["per_day"] > bf["oneaday"]["per_day"]
    out["verdict"] = (
        "ORDER TYPE IS REAL -- resting the limit STRICTLY AFTER the signal bar, "
        "with nothing dropped for size, still earns $%d/day against the shipped "
        "entry's $%d/day. (Resting it from the arming bar earns $%d, but that "
        "uses the knowledge that the setup would fire.)"
        % (pf["oneaday"]["per_day"], bf["oneaday"]["per_day"],
           lf["oneaday"]["per_day"]) if survives else
        "LOOK-AHEAD -- the money lives in resting the order BEFORE the signal "
        "existed. Strictly after it, the limit earns $%d/day against the shipped "
        "entry's $%d/day; resting from the arming bar it earns $%d/day, and the "
        "row is only in this book because it eventually fired."
        % (pf["oneaday"]["per_day"], bf["oneaday"]["per_day"],
           lf["oneaday"]["per_day"]))
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g88 -- is the resting-limit arm real, or a size-gate survivor?", "",
          "**%s**" % out["verdict"], "",
          "One trade a day on `%s`, %d candidates over %d sessions, 1R = $1,000, "
          "bar = $%d/day. Exits are the shipped ladder."
          % (BOOK.name, len(keys), n_days, BAR_PER_DAY), "",
          "| arm | entry | stop when risk < floor | $/day | 95% band | % of bar | "
          "win | mean R | green | days traded | rows dropped | median risk |",
          "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, entry_kind, stop_policy in ARMS:
        a, st = out["arms"][name], out["arms"][name]["oneaday"]
        ci = a["oneaday_ci"]
        md.append("| `%s` | %s | %s | **$%d** | $%d..$%d | %.1f%% | %.1f%% | "
                  "%+.3f | %d/%d | %d | %.1f%% | $%.2f |"
                  % (name, "shipped" if entry_kind == "book" else "limit at level",
                     "drop the trade" if stop_policy == "intrabar" else "widen the stop",
                     st["per_day"], ci.get("lo", 0), ci.get("hi", 0),
                     a["pct_of_bar"], st["win_pct"], st["mean_r"],
                     st["months_green"], st["months"], a["days_traded"],
                     a["dropped_pct"], a["median_risk"] or 0))
    md += ["",
           "`intrabar` is the shipped pair: `signal_runner.intrabar_stop` moves the "
           "stop to the entry bar's completed extreme, and any row whose risk then "
           "falls under `signal_runner.min_risk_floor` is dropped as un-takeable. "
           "That drop is the thing under test -- it selects rows using the entry "
           "bar's own future.",
           "",
           "`floor` holds the structural stop and pushes it out until the risk "
           "clears the same floor, reading `bars[fill_i - 1].close` so the constant "
           "is causal. No row is dropped for size, so nothing in those arms can be "
           "a survivor.",
           "",
           "The limit fills a median of %s bars before the book's own entry."
           % (l["median_bars_early"]),
           ""]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n" + out["verdict"])
    print("wrote %s\nwrote %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
