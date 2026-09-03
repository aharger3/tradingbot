"""g75_lateness_price.py -- what is the lateness actually costing, in dollars?

Prices the one-candle rule's clock on the shipped two-year book, using the
SAME arithmetic the board uses (research/g72_suppress_price.stats, imported not
re-typed) so every figure means what it meant on the last board.

Four questions, in order of how much they can be trusted:

  A. Does an EARLY one-candle-rule trade make more money than a late one?
     (The whole point of chasing the 40 minutes.)
  B. Same split for break-and-retest -- is "early is better" a property of the
     one-candle rule, or of the morning?
  C. On the days the engine takes a LATE one-candle-rule trade, had it already
     taken an earlier break-and-retest trade on the same chart? If yes, the
     trade Austin wants at 9:38 is not missing -- it is already in the book
     under a different name.
  D. The ceiling: rebuild the one-trade-a-day book keeping only the
     one-candle-rule rows that fire before 10:00, and price it on all six
     headline numbers.

1R = $1,000. Read-only. Writes research/g75_lateness_price.json.
"""
from __future__ import annotations
import json, os, random, statistics as st, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from g72_suppress_price import stats, shipped_rows, oneaday_rows, load, RISK
from pathlib import Path

BOOK = Path(HERE) / "bt2y_trades.json"
OUT = os.path.join(HERE, "g75_lateness_price.json")
RNG = random.Random(751)
J = {}


def mins(et):
    return (int(et[:2]) - 9) * 60 + int(et[3:]) - 30


def boot_mean_diff(a, b, iters=8000):
    d = []
    for _ in range(iters):
        d.append(st.fmean(RNG.choice(a) for _ in a) - st.fmean(RNG.choice(b) for _ in b))
    d.sort()
    return d[int(0.025 * iters)], d[int(0.975 * iters)]


meta, rows = load(BOOK)
nd = meta["sessions"]
traded = shipped_rows(rows)
print("book %s   %d sessions   %d traded rows" % (meta.get("generated"), nd, len(traded)))

CUT = 30  # bars past 09:30 == 10:00


def split(setup):
    e = [r for r in traded if r["setup"] == setup and mins(r["et"]) < CUT]
    l = [r for r in traded if r["setup"] == setup and mins(r["et"]) >= CUT]
    return e, l


def line(tag, g):
    if not g:
        return "  %-34s  no trades" % tag
    r = [x["r"] for x in g]
    w = sum(1 for x in g if x["pnl"] > 0)
    ll = sum(1 for x in g if x["pnl"] < 0)
    return ("  %-34s %5d   %6.1f%%   %+7.3fR   %+9s   %+11s"
            % (tag, len(g), 100.0 * w / (w + ll) if w + ll else 0.0, st.fmean(r),
               "$%d" % round(st.fmean(x["pnl"] for x in g)),
               "$%s" % format(int(round(sum(x["pnl"] for x in g))), ",")))


print()
print("=" * 100)
print("A/B. IS BEING EARLY WORTH MONEY? -- traded rows only, split at 10:00")
print("=" * 100)
print("  %-34s %5s   %7s   %8s   %9s   %11s"
      % ("", "n", "win", "mean R", "per trade", "total"))
J["split"] = {}
for setup, name in (("one_candle_rule", "one-candle rule"),
                    ("break_and_retest", "break-and-retest"),
                    ("reentry_84_rule", "84% re-entry")):
    e, l = split(setup)
    print(line("%s, 9:30-10:00" % name, e))
    print(line("%s, after 10:00" % name, l))
    if e and l:
        ra = [x["r"] for x in e]
        rb = [x["r"] for x in l]
        lo, hi = boot_mean_diff(ra, rb)
        print("  %-34s early minus late = %+.3fR  (95%% CI %+.3f to %+.3f)  %s"
              % ("", st.fmean(ra) - st.fmean(rb), lo, hi,
                 "CLEARS ITS OWN NOISE" if lo > 0 or hi < 0 else "inside the noise"))
        J["split"][setup] = {
            "early_n": len(e), "late_n": len(l),
            "early_mean_r": round(st.fmean(ra), 4), "late_mean_r": round(st.fmean(rb), 4),
            "diff": round(st.fmean(ra) - st.fmean(rb), 4), "ci": [round(lo, 4), round(hi, 4)],
            "early_win": round(100.0 * sum(1 for x in e if x["pnl"] > 0)
                               / max(1, sum(1 for x in e if x["pnl"] != 0)), 1),
            "late_win": round(100.0 * sum(1 for x in l if x["pnl"] > 0)
                              / max(1, sum(1 for x in l if x["pnl"] != 0)), 1),
        }
    print()

print("=" * 100)
print("C. ON A LATE ONE-CANDLE-RULE DAY, WAS THE EARLIER TRADE ALREADY IN THE BOOK?")
print("=" * 100)
byday = defaultdict(list)
for r in traded:
    byday[(r["sym"], r["day"])].append(r)
late_ocr = [r for r in traded if r["setup"] == "one_candle_rule" and mins(r["et"]) >= CUT]
had_earlier, had_earlier_br, earlier_pnl, ocr_pnl = 0, 0, [], []
for r in late_ocr:
    others = [o for o in byday[(r["sym"], r["day"])] if mins(o["et"]) < mins(r["et"])]
    if others:
        had_earlier += 1
        first = min(others, key=lambda o: mins(o["et"]))
        earlier_pnl.append(first["pnl"])
        ocr_pnl.append(r["pnl"])
        if first["setup"] == "break_and_retest":
            had_earlier_br += 1
print("  late one-candle-rule trades (after 10:00): %d" % len(late_ocr))
print("  ...of which the engine had ALREADY traded that same chart earlier the "
      "same morning: %d (%.1f%%)" % (had_earlier, 100.0 * had_earlier / len(late_ocr)))
print("  ...and that earlier trade was a break-and-retest: %d (%.1f%% of the %d)"
      % (had_earlier_br, 100.0 * had_earlier_br / max(1, had_earlier), had_earlier))
if earlier_pnl:
    print("  the earlier trade earned  $%s per trade   |  the late one-candle-rule "
          "trade earned $%s"
          % (format(int(round(st.fmean(earlier_pnl))), ","),
             format(int(round(st.fmean(ocr_pnl))), ",")))
J["already_there"] = {"late_ocr": len(late_ocr), "had_earlier": had_earlier,
                      "had_earlier_br": had_earlier_br,
                      "earlier_per_trade": round(st.fmean(earlier_pnl), 0) if earlier_pnl else None,
                      "ocr_per_trade": round(st.fmean(ocr_pnl), 0) if ocr_pnl else None}

print()
print("=" * 100)
print("D. THE CEILING -- what the book is worth if the one-candle rule only ever")
print("   fired in the first half hour (every late one deleted)")
print("=" * 100)
FIELDS = ["trades", "win_pct", "per_trade", "per_day", "months_green", "months",
          "weeks_green", "weeks", "worst_drawdown", "total_dollars"]


def keep_early_ocr(rs):
    return [r for r in rs if not (r["setup"] == "one_candle_rule" and mins(r["et"]) >= CUT)]


base_all = stats(shipped_rows(rows), nd)
cut_all = stats(shipped_rows(keep_early_ocr(rows)), nd)
base_1d = stats(oneaday_rows(rows), nd)
cut_1d = stats(oneaday_rows(keep_early_ocr(rows)), nd)
print("  %-16s %14s %14s %10s | %14s %14s %10s"
      % ("", "ALL now", "ALL early-only", "chg", "1/day now", "1/day early", "chg"))
for f in FIELDS:
    a, b, c, d = base_all.get(f), cut_all.get(f), base_1d.get(f), cut_1d.get(f)
    print("  %-16s %14s %14s %10s | %14s %14s %10s"
          % (f, a, b, round(b - a, 1) if isinstance(a, (int, float)) else "",
             c, d, round(d - c, 1) if isinstance(c, (int, float)) else ""))
J["ceiling"] = {"all_now": base_all, "all_early_only": cut_all,
                "oneaday_now": base_1d, "oneaday_early_only": cut_1d}

json.dump(J, open(OUT, "w"), indent=1)
print()
print("wrote", OUT)
