"""ADVERSARIAL RE-COMPUTE of the six-figure sizing page (research/g83_sizing.md).

Independent of research/g83_sizing.py: this file re-prices the two-year book
itself off the archived one-minute bars, rebuilds the one-trade-a-day series
from scratch, and only THEN opens research/g83_series.json to see whether the
page's series is the same series.

What it re-computes, all against the $397/day bar ($100,000 / 252 sessions):

  1. options, same-day ATM contract, honest fill (market at the close of the
     signal minute), BEFORE spread -- the page's headline $346/day at $1,000
     of risk, its "$1,148 of risk reaches the bar", and its 21-of-25 green
     months.
  2. shares after a penny round trip -- the page's $167/day.
  3. scale invariance of the green-month count, asserted at 0.25x / 3x / 17.5x.
  4. day-for-day agreement with research/g83_series.json.

Run:  python research/g83_verify_3.py            (~4 min, offline, read-only)
      python research/g83_verify_3.py --cached   (skip re-pricing, audit only)

Writes research/g83_verify_3.json. Opens no mark file, edits no engine file.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from research import g80_options_honest as oh  # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
THEIRS = ROOT / "research" / "g83_series.json"
CLAIM = ROOT / "research" / "g83_sizing.json"
OUT = ROOT / "research" / "g83_verify_3.json"

RISK0 = 1000.0
TARGET_DAY = 100_000 / 252
MULT = 100
OPT_ROUND_TRIP = 0.05
SHR_ROUND_TRIP = 0.01


def month_of(d):
    return d[:7]


def stats(series, all_days, risk=RISK0):
    """Everything the page claims, from one {day: R} series."""
    daily = [series.get(d, 0.0) for d in all_days]
    mean_r = sum(daily) / len(daily)
    per_day = mean_r * risk
    m = defaultdict(float)
    for d in all_days:
        m[month_of(d)] += series.get(d, 0.0)
    green = sum(1 for v in m.values() if v > 0)
    return {
        "days_traded": len(series),
        "sessions": len(all_days),
        "mean_daily_r": round(mean_r, 6),
        "per_day": round(per_day, 1),
        "distance_to_397": round(per_day - TARGET_DAY, 1),
        "pct_of_397": round(100 * per_day / TARGET_DAY, 1),
        "risk_for_397": round(TARGET_DAY / mean_r, 0) if mean_r > 0 else None,
        "months_green": green,
        "months": len(m),
        "durability_pass": green == len(m),
    }


def main():
    cached = "--cached" in sys.argv
    book = json.load(open(BOOK, encoding="utf-8"))
    all_days = sorted({r["day"] for r in book["trades"]})
    report = {"bar_per_day": round(TARGET_DAY, 2), "sessions": len(all_days),
              "book_generated": book["meta"]["generated"]}

    mine = {}
    if not cached:
        print("re-pricing %d traded rows, honest fill only (~4 min) ..."
              % book["meta"]["traded"], flush=True)
        arms, diag = oh.build_many(book["trades"], {"B": {"arm": "B", "iv": 1.0}})
        rows = arms["B"]
        sc = oh.scoreable(rows)
        one_opt = oh.first_takeable_per_day(sc)
        one_shr = oh.first_takeable_per_day(rows)
        mine["options_raw"] = {r["day"]: r["dollars"] / RISK0 for r in one_opt}
        mine["options_nickel"] = {
            r["day"]: (r["dollars"] - r["contracts"] * OPT_ROUND_TRIP * MULT) / RISK0
            for r in one_opt}
        mine["shares_penny"] = {
            r["day"]: (r["shares_dollars"] - r["shares_held"] * SHR_ROUND_TRIP) / RISK0
            for r in one_shr}
        report["diagnostics"] = diag["B"]
        (ROOT / "research" / "g83_verify_3_series.json").write_text(
            json.dumps(mine), encoding="utf-8")
    else:
        mine = json.load(open(ROOT / "research" / "g83_verify_3_series.json",
                              encoding="utf-8"))

    report["recomputed"] = {k: stats(v, all_days) for k, v in mine.items()}

    # ---- scale invariance of the green-month count, asserted not assumed
    inv = {}
    for mult in (0.25, 1.0, 3.0, 17.5):
        scaled = {d: v * mult for d, v in mine["options_raw"].items()}
        inv[str(mult)] = stats(scaled, all_days)["months_green"]
    report["green_months_by_scale"] = inv
    report["scale_invariant"] = len(set(inv.values())) == 1

    # ---- does their series equal mine, day for day?
    if THEIRS.exists():
        theirs = json.load(open(THEIRS, encoding="utf-8"))["series"]
        cmp = {}
        for mykey, theirkey in (("options_raw", "B/options_raw"),
                                ("options_nickel", "B/options"),
                                ("shares_penny", "B/shares")):
            t = theirs.get(theirkey, {})
            a, b = mine[mykey], t
            keys = set(a) | set(b)
            worst = max(((abs(a.get(k, 0.0) - b.get(k, 0.0)), k) for k in keys),
                        default=(0.0, None))
            cmp[theirkey] = {"my_days": len(a), "their_days": len(b),
                             "days_match": set(a) == set(b),
                             "worst_abs_R_diff": round(worst[0], 9),
                             "worst_day": worst[1],
                             "their_stats": stats(b, all_days)}
            cmp[theirkey]["identical"] = (set(a) == set(b) and worst[0] < 1e-9)
        report["vs_page_series"] = cmp

    # ---- and against the page's own published record
    if CLAIM.exists():
        c = json.load(open(CLAIM, encoding="utf-8"))
        report["page_claims"] = {
            k: {kk: c["instruments"][k].get(kk) for kk in
                ("per_day_at_1k", "risk_for_397", "months_green", "months",
                 "durability_pass", "pct_of_397_at_1k")}
            for k in c.get("instruments", {})}

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    r = report["recomputed"]
    print()
    print("THE $397/DAY BAR -- independent re-price, 1R = $1,000")
    print("%-18s %9s %10s %8s %10s %10s" %
          ("instrument", "$/day", "vs $397", "% bar", "risk->397", "green mo"))
    for k in ("options_raw", "options_nickel", "shares_penny"):
        s = r[k]
        print("%-18s %9s %10s %7s%% %10s %6s/%s" %
              (k, "$%.0f" % s["per_day"], "$%+.0f" % s["distance_to_397"],
               s["pct_of_397"], "$%s" % s["risk_for_397"],
               s["months_green"], s["months"]))
    print()
    print("green months by risk scale:", report["green_months_by_scale"],
          "-> scale-invariant:", report["scale_invariant"])
    if "vs_page_series" in report:
        for k, v in report["vs_page_series"].items():
            print("%-16s identical to page: %s  (worst |dR| %.2e)"
                  % (k, v["identical"], v["worst_abs_R_diff"]))
    print("wrote %s" % OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
