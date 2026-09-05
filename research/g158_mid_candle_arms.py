"""g158 -- mid-candle, categorized honestly (OMEN 9.0 F9).

Austin's ON WATCH rule (2026-08-23) says the CLOSE decides whether to trade,
not the previous candle. The shipped fill is the signal bar's own close
(`entry_fill.py`, changed 2026-08-30 after g80's lookahead refute). This row
asks a narrower, honest question: on the bars that come AFTER the signal bar
already fired, could a resting limit have improved on that close, and how
often?

THE ARM. For every book signal, rest a limit strictly AFTER the signal bar
at 25% / 50% / 75% of the SIGNAL BAR'S OWN RANGE, measured back from that
bar's close toward the level (25% = a small pullback near the close, 75% = a
deep pullback near the level). Fill only on a LATER bar's touch (g80's
`limit_touch`, the same convention `stop_rule` and g88's POST arm already
use: a resting order fills at its own price unless the fill bar opened past
it). Stop and target are the book's own, untouched -- this is an ENTRY-only
question, not a re-priced trade (`g80_ordertype_grid.run_trade`,
`move_stop_to_entry_bar=True`, the same convention g88's shipped-pair arms
use).

THIS IS NOT g87/g88 AGAIN. g87 swept the RETEST TOLERANCE (how close a
retest has to come to the level to count as a signal at all) and found zero
tolerance wins. g88 asked whether a limit resting AT THE LEVEL beats the
close, and found the honest (strictly-after-signal) version of that arm
pays $275/day against the shipped $33 -- real direction, not shippable
(CLAUDE.md, 89.6% of AT_LEVEL's headline fills were look-ahead). This row
is a different question again: not "is the level a better price", but
"within the signal bar's OWN range, how far back does price usually go
after the fact, and does that change anything Austin could plan for before
he knows the answer." Categorization, not a new arm to ship.

CATEGORIES (my operational definition -- stated so it is auditable, not
implied). For each signal, find the DEEPEST of {25%, 50%, 75%} that fills on
a later bar before the 11:00 cutoff:
    never-returns  -- none of the three ever fill. Price ran away; the close
                       was already the only price a resting order would have
                       gotten, and the RANGE never even partially retraced.
    close-only     -- only the 25% checkpoint ever fills. A shallow pullback
                       happened but not far; the close was NEAR the best
                       price obtainable, not exactly it.
    mid-fillable    -- the 50% or 75% checkpoint fills. A meaningfully better
                       entry existed on a later bar, in principle plannable.

Nothing here is applied. `signal_runner.py` is read, never edited.

    python research/g158_mid_candle_arms.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G   # noqa: E402
import signal_runner as sr                     # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT_JSON = ROOT / "research" / "g158_mid_candle_arms.json"
OUT_MD = ROOT / "research" / "g158_mid_candle_arms.md"

RISK = 1000.0
BAR_PER_DAY = 397.0          # his bar, $397/day, one-trade-a-day
SPLIT_DAY = "2025-09-01"     # H1/H2 per THE LAW

FRACS = (0.25, 0.50, 0.75)
ARM_NAMES = {0.25: "MID25", 0.50: "MID50", 0.75: "MID75"}


def half(day):
    return "H1" if day < SPLIT_DAY else "H2"


def resting_price(entry_close, rng, long, frac):
    return entry_close - frac * rng if long else entry_close + frac * rng


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
        r = allrows[k]
        cand_by_day[r["day"]].append(k)
    for d in cand_by_day:
        cand_by_day[d].sort(key=lambda i: (allrows[i]["et"], allrows[i]["sym"], i))

    priced = {f: {} for f in FRACS}          # frac -> key -> run_trade result
    nofill = {f: Counter() for f in FRACS}
    category = {}                            # key -> "never-returns"/"close-only"/"mid-fillable"
    cat_counts = defaultdict(Counter)         # half -> category -> n

    for n, k in enumerate(keys):
        if n and n % 5000 == 0:
            print("   %d / %d" % (n, len(keys)), flush=True)
        r = universe[k]
        h = half(r["day"])
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r["entry_i"]
        if not bars or i >= len(bars):
            for f in FRACS:
                nofill[f]["no_bars"] += 1
            category[k] = "no_bars"
            continue
        rng = bars[i].high - bars[i].low
        cutoff = G.cutoff_idx(bars)
        if rng <= 0 or i + 1 >= min(cutoff, len(bars) - 1):
            for f in FRACS:
                nofill[f]["no_bars_after_signal"] += 1
            category[k] = "never-returns"
            cat_counts[h]["never-returns"] += 1
            continue

        long = r["dir"] == "call"
        entry_close = r["entry"]           # this book's fill IS the bar close
        depth = None
        for f in FRACS:
            px = resting_price(entry_close, rng, long, f)
            # strictly AFTER the signal bar -- i+1, never i or earlier.
            j, fillpx = G.limit_touch(bars, px, long, i + 1, cutoff)
            if j is None:
                nofill[f]["limit_never_touched"] += 1
                continue
            if j >= len(bars) - 1:
                nofill[f]["filled_on_last_bar"] += 1
                continue
            depth = f
            res = G.run_trade(r, bars, j, fillpx, pdh, pdl, pmh, pml,
                              move_stop_to_entry_bar=True)
            if res is None:
                nofill[f]["risk_collapsed"] += 1
                continue
            priced[f][k] = res

        cat = ("never-returns" if depth is None else
               "close-only" if depth == 0.25 else "mid-fillable")
        category[k] = cat
        cat_counts[h][cat] += 1
        cat_counts["ALL"][cat] += 1

    # -------------------------------------------------- CLOSE, the control
    close_rows = {k: universe[k] for k in keys}

    def oneaday_for(rows_by_key, day_filter=None):
        picked = []
        for d in sorted(cand_by_day):
            if day_filter and not day_filter(d):
                continue
            for k in cand_by_day[d]:
                res = rows_by_key.get(k)
                if res is None:
                    continue
                sizeable = (res.get("sizeable") if "sizeable" in res else
                           abs(res["entry"] - res["stop"]) >=
                           sr.min_risk_floor(res.get("close", res["entry"])))
                if sizeable:
                    picked.append(res)
                    break
        return picked

    def days_in_half(h):
        return [d for d in all_days if half(d) == h]

    arms_out = {}

    def score_arm(name, rows_by_key, entry_close_ok=False):
        full = oneaday_for(rows_by_key)
        h1 = oneaday_for(rows_by_key, lambda d: half(d) == "H1")
        h2 = oneaday_for(rows_by_key, lambda d: half(d) == "H2")
        st_full = G.price(full, n_days, all_days)
        st_h1 = G.price(h1, len(days_in_half("H1")), days_in_half("H1"))
        st_h2 = G.price(h2, len(days_in_half("H2")), days_in_half("H2"))
        arms_out[name] = {
            "combined": st_full, "H1": st_h1, "H2": st_h2,
            "pct_of_bar_combined": round(st_full["per_day"] / BAR_PER_DAY * 100, 1),
            "rows_priced": len(rows_by_key),
        }
        print("  %-8s combined $%5d/day (%.1f%% of bar)  H1 $%5d/day  H2 $%5d/day  "
              "meanR %+.3f  %d/%d green"
              % (name, st_full["per_day"], arms_out[name]["pct_of_bar_combined"],
                 st_h1["per_day"], st_h2["per_day"], st_full["mean_r"],
                 st_full["months_green"], st_full["months"]), flush=True)

    score_arm("CLOSE", close_rows)
    for f in FRACS:
        score_arm(ARM_NAMES[f], priced[f])

    out = {
        "book": BOOK.name, "sessions": n_days, "candidates": len(keys),
        "split_day": SPLIT_DAY, "bar_per_day": BAR_PER_DAY,
        "arms": arms_out,
        "categories": {h: dict(c) for h, c in cat_counts.items()},
        "nofill": {ARM_NAMES[f]: dict(nofill[f].most_common(6)) for f in FRACS},
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    onwatch_note = """
## `near_session_extreme` and the ON WATCH block (`signal_runner.py` ~1426-1489)

`fill_price()` (signal_runner.py:1443) delegates every entry to `entry_fill.entry_fill_price`,
passing one verdict: `close_is_bad_fill()` (line 1417), which is true when either the signal
bar's OWN extreme was the close (`bar_extreme_veto`, T3(b)) or -- only when `ON_WATCH` is on --
the close sat within `BAR_EXTREME_FRAC` (25%) of the SESSION'S high/low
(`near_session_extreme()`, line 1470). That second condition is what "mid-candle" means in this
engine today: it never changes WHERE the trade enters (the close still decides whether to trade,
per Austin's 2026-08-23 ruling), only whether `entry_fill` is told the close is a bad price --
which currently still books the close anyway (`mode="close"` forced whenever
`entry_fill.needs_future_bars()`), so the verdict is presently a label with no live consequence,
not a price change. `ON_WATCH` is itself the one flag that could turn this arm's finding into a
live rule change; it defaults ON (`signal_runner.ON_WATCH = True`) and is already the current
default book's setting (`bt2y_trades_retest_on.json` stamps it True).

**The one dynamic that could change it: the 25% bar-range unit (`BAR_EXTREME_FRAC`) vs a
cents-based tolerance, and its measured effect.** g87 (`research/g87_retest_tol.py`) already
swept exactly this axis for the RETEST trigger and the answer was blunt: the best tolerance is
ZERO -- a limit resting exactly at the level -- and every widened tolerance (cents or fraction)
LOSES money, because `intrabar_stop` collapses the risk denominator toward the tolerance itself.
g158's own arms echo it from a different angle: MID25/50/75 rest a limit at fixed fractions of
the signal bar's own range rather than at a cents distance, and the categorization above shows
how often price actually gives that fraction back. A cents-unit version of the same three
checkpoints would move with volatility (a $50 stock's 25 cents is not a $500 stock's 25 cents)
where the bar-range unit already scales with the stock automatically -- which is the same reason
Austin rejected a cents unit for the retest tolerance on 2026-08-30 ("it doesn't follow the 25
percent candle unit ... its just if its close but didnt actually touch"). Nothing in this row
re-litigates that; it is recorded here because the row asked for the paragraph and the answer
routes through the same measured fact.
"""

    close_full = arms_out["CLOSE"]["combined"]
    best_mid = max(FRACS, key=lambda f: arms_out[ARM_NAMES[f]]["combined"]["per_day"])
    best_mid_row = arms_out[ARM_NAMES[best_mid]]["combined"]
    verdict_beats = best_mid_row["per_day"] > close_full["per_day"]

    lines = []
    lines.append("# g158 -- mid-candle, categorized honestly")
    lines.append("")
    lines.append(
        "**What is different now:** every book signal was categorized by how far price actually "
        "pulls back into its own signal bar AFTER that bar fires, and the best mid-candle arm "
        "(%s, resting a limit at %d%% of the signal bar's range back toward the level) prices at "
        "$%d/day against CLOSE's $%d/day (%s) -- fill: signal-bar CLOSE for CLOSE, a strictly-"
        "after-signal resting-limit touch for the MID arms, both through `stop_rule`-consistent "
        "exits (`g80_ordertype_grid.run_trade`), size-gated on `signal_runner.min_risk_floor`, "
        "1R = $1,000. Script: `research/g158_mid_candle_arms.py`."
        % (ARM_NAMES[best_mid], int(best_mid * 100), best_mid_row["per_day"],
           close_full["per_day"],
           "beats it" if verdict_beats else "does not beat it"))
    lines.append("")
    lines.append("## Categories, all %d candidates (not just the one-trade-a-day pick)"
                 % len(keys))
    lines.append("")
    lines.append("| half | never-returns | close-only | mid-fillable |")
    lines.append("|---|---:|---:|---:|")
    for h in ("H1", "H2", "ALL"):
        c = cat_counts.get(h, Counter())
        lines.append("| %s | %d | %d | %d |"
                     % (h, c.get("never-returns", 0), c.get("close-only", 0),
                        c.get("mid-fillable", 0)))
    lines.append("")
    lines.append("Definitions: **never-returns** -- none of 25/50/75% of the signal bar's own "
                 "range ever fills on a later bar (price ran away; close was the only price "
                 "obtainable). **close-only** -- only the shallow 25% checkpoint fills. "
                 "**mid-fillable** -- the 50% or 75% checkpoint fills (a meaningfully better "
                 "entry existed later, in principle plannable).")
    lines.append("")
    lines.append("## Arms, one-trade-a-day unit (`omen_metrics`-style first-of-day, size-gated)")
    lines.append("")
    lines.append("| arm | combined $/day | % of $397 bar | H1 $/day | H2 $/day | mean R | "
                 "win% | green months |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name in ["CLOSE"] + [ARM_NAMES[f] for f in FRACS]:
        a = arms_out[name]
        c = a["combined"]
        lines.append("| %s | $%d | %.1f%% | $%d | $%d | %+.3f | %.1f%% | %d/%d |"
                     % (name, c["per_day"], a["pct_of_bar_combined"],
                        a["H1"]["per_day"], a["H2"]["per_day"], c["mean_r"],
                        c["win_pct"], c["months_green"], c["months"]))
    lines.append("")
    lines.append("No-fill reasons (MID arms, at the candidate level, top 6 each):")
    lines.append("")
    for f in FRACS:
        lines.append("- %s: %s" % (ARM_NAMES[f], out["nofill"][ARM_NAMES[f]]))
    lines.append(onwatch_note)
    lines.append("")
    lines.append("Nothing here is shipped. `signal_runner.py` and `entry_fill.py` were read, "
                 "never edited.")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT_JSON, "and", OUT_MD)


if __name__ == "__main__":
    main()
