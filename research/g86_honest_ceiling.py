"""g86 -- the one question that decides the lane.

The $3,458/day selection prize (research/g81_htf_thesis.md step 1) was measured on
the PUBLISHED fill, which bought at prices that did not exist: only 105 of 4,508
trades were obtainable at the book's own price (research/g80_dollar_reconcile.md).
research/g85_entry_fill.md then made the honest fill the default and the one-a-day
book fell from $721/day to $28/day.

So: does the CEILING survive the honest fill?

  - If best-of-day is still far above first-of-day, the setup has edge and we are
    picking the wrong one. Selection is the lane.
  - If best-of-day collapses too, the entry rule itself has no edge at an
    obtainable price, and no amount of selection saves it. The lane is the entry.

Nothing here is applied and nothing is a rule. One number, two books, same code.

    python research/g86_honest_ceiling.py
"""
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

RISK = 1000.0
HONEST = os.path.join(HERE, "bt2y_trades.json")
PUBLISHED = os.path.join(HERE, "bt2y_trades_published_fill.json")
OUT_JSON = os.path.join(HERE, "g86_honest_ceiling.json")
OUT_MD = os.path.join(HERE, "g86_honest_ceiling.md")

BAR_PER_DAY = 397.0          # Austin's stated bar: six figures a year


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


def drawdown(pnls):
    peak = cum = worst = 0.0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def candidates(rows):
    """The one-trade-a-day candidate stream. Identical rule to
    g81_htf_thesis.candidates / g72_suppress_price.oneaday_rows: fired-and-traded
    plus rows the account-wide two-loss halt blocked (under one-a-day that halt
    cannot have fired yet, so those days are live again)."""
    byday = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday[r["day"]].append(r)
    for v in byday.values():
        v.sort(key=ekey)
    return dict(byday)


def stats(rows, n_days):
    if not rows:
        return {"trades": 0}
    rows = sorted(rows, key=ekey)
    pnls = [r["pnl"] for r in rows]
    wins = sum(1 for r in rows if r["pnl"] > 0)
    losses = sum(1 for r in rows if r["pnl"] < 0)
    total = sum(pnls)
    by_m, by_w = defaultdict(float), defaultdict(float)
    for r in rows:
        by_m[r["day"][:7]] += r["pnl"]
        by_w[iso_week(r["day"])] += r["pnl"]
    return {
        "trades": len(rows),
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "total_dollars": round(total),
        "per_trade": round(total / len(rows)),
        "mean_r": round(total / len(rows) / RISK, 3),
        "per_day": round(total / n_days),
        "pct_of_bar": round(total / n_days / BAR_PER_DAY * 100, 1),
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "weeks_green": sum(1 for v in by_w.values() if v > 0),
        "weeks": len(by_w),
        "worst_drawdown": round(drawdown(pnls)),
    }


def arm(path, label):
    blob = json.load(open(path, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    n_days = meta.get("sessions") or meta.get("days") or len(
        {r["day"] for r in rows})
    byday = candidates(rows)
    firsts, bests, worsts, means = [], [], [], []
    first_is_best = 0
    for day in sorted(byday):
        v = byday[day]
        best = max(v, key=lambda r: r["r"])
        firsts.append(v[0])
        bests.append(best)
        worsts.append(min(v, key=lambda r: r["r"]))
        means.append(statistics.fmean(r["pnl"] for r in v))
        if v[0]["r"] >= best["r"]:
            first_is_best += 1
    n = len(byday)
    per_day_counts = [len(v) for v in byday.values()]
    out = {
        "label": label,
        "book": os.path.basename(path),
        "sessions": n_days,
        "days_with_candidates": n,
        "candidates_total": sum(per_day_counts),
        "candidates_per_day_median": statistics.median(per_day_counts),
        "first": stats(firsts, n_days),
        "best": stats(bests, n_days),
        "worst": stats(worsts, n_days),
        "coinflip_per_day": round(sum(means) / n_days),
        "first_is_best": first_is_best,
        "first_is_best_pct": round(first_is_best / n * 100, 1),
        "chance_pct": round(sum(1.0 / c for c in per_day_counts) / n * 100, 1),
    }
    out["prize_per_day"] = out["best"]["per_day"] - out["first"]["per_day"]
    out["arrival_edge_per_day"] = out["first"]["per_day"] - out["coinflip_per_day"]
    return out


def main():
    arms = {}
    for path, label in ((HONEST, "honest (close fill, current default)"),
                        (PUBLISHED, "published (old fill, unobtainable)")):
        if not os.path.exists(path):
            print("MISSING %s -- skipped" % path)
            continue
        print("reading %s ..." % os.path.basename(path))
        a = arm(path, label)
        arms[label] = a
        print("  first $%d/day  best $%d/day  PRIZE $%d/day  (%d candidates over %d days)"
              % (a["first"]["per_day"], a["best"]["per_day"], a["prize_per_day"],
                 a["candidates_total"], a["days_with_candidates"]))

    hon = arms.get("honest (close fill, current default)")
    pub = arms.get("published (old fill, unobtainable)")
    verdict = {}
    if hon and pub:
        verdict = {
            "prize_honest": hon["prize_per_day"],
            "prize_published": pub["prize_per_day"],
            "prize_survival_pct": round(
                hon["prize_per_day"] / pub["prize_per_day"] * 100, 1)
            if pub["prize_per_day"] else None,
            "ceiling_clears_bar": hon["best"]["per_day"] >= BAR_PER_DAY,
            "ceiling_months_green": "%d/%d" % (hon["best"]["months_green"],
                                               hon["best"]["months"]),
            "lane": ("SELECTION -- the ceiling survives the honest fill, so the "
                     "setup has edge and the engine is picking the wrong one"
                     if hon["best"]["per_day"] >= BAR_PER_DAY else
                     "ENTRY -- the ceiling does not clear the bar even with "
                     "perfect selection, so no selector can save this entry rule"),
        }

    blob = {"bar_per_day": BAR_PER_DAY, "risk_dollars": RISK,
            "arms": arms, "verdict": verdict}
    json.dump(blob, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    lines = ["# g86 -- does the selection prize survive an honest fill?", ""]
    if verdict:
        lines += ["**%s**" % verdict["lane"], ""]
    lines += ["| book | first of day | best of day | prize | coin flip | months green (best) |",
              "|---|---:|---:|---:|---:|---:|"]
    for a in arms.values():
        lines.append("| %s | $%d/day, %.1f%% win | $%d/day, %.1f%% win | **$%d/day** | $%d/day | %d/%d |"
                     % (a["label"], a["first"]["per_day"], a["first"]["win_pct"],
                        a["best"]["per_day"], a["best"]["win_pct"],
                        a["prize_per_day"], a["coinflip_per_day"],
                        a["best"]["months_green"], a["best"]["months"]))
    lines += ["", "Bar: **$%d/day** (six figures a year). One trade a day, 1R = $%d."
              % (BAR_PER_DAY, RISK), ""]
    for a in arms.values():
        lines += ["## %s" % a["label"], "",
                  "`%s` -- %d sessions, %d candidates over %d days, median %d/day."
                  % (a["book"], a["sessions"], a["candidates_total"],
                     a["days_with_candidates"], a["candidates_per_day_median"]),
                  "",
                  "| arm | $/day | %% of bar | mean R | win | months green | worst DD |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for k in ("first", "best", "worst"):
            st = a[k]
            lines.append("| %s | $%d | %.1f%% | %+.3f | %.1f%% | %d/%d | $%d |"
                         % (k, st["per_day"], st["pct_of_bar"], st["mean_r"],
                            st["win_pct"], st["months_green"], st["months"],
                            st["worst_drawdown"]))
        lines += ["",
                  "Arrival order picks the day's best on %d of %d days (%.1f%%); chance is %.1f%%. "
                  "Edge over a coin flip: $%d/day."
                  % (a["first_is_best"], a["days_with_candidates"],
                     a["first_is_best_pct"], a["chance_pct"],
                     a["arrival_edge_per_day"]),
                  ""]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    print("\nwrote %s\nwrote %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
