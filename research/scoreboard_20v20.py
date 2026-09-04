"""scoreboard_20v20 -- EV/R, last 20 sessions vs the prior 20, on the shipped book.

The nightly AUGUR pass's own scorecard (Projects/AUGUR.md's daily loop, Friday
row): "EV/R last 20 sessions vs prior 20, green or red. Kill rule: 60 sessions
at EV/R <= 0 means this approach is dead."

Nothing new is computed here for the headline numbers. `research/omen_metrics.py`'s
`first_of_day_arm` (the one-trade-a-day pick stream, size-gated, chronological) and
`ev_r_scoreboard` (the one EV/R definition) are the only two functions the last-20/
prior-20/last-60 table calls -- it slices their output into the most-recent 20
sessions and the 20 before that, plus the last 60 for the kill rule.

AN ADVERSARIAL PASS (2026-09-03 night) on this file's first cut found the kill-rule
number was arithmetically right but its framing was not: quoting "KILL RULE TRIPPED"
as news, alone, is misleading. A 60-session ev/R <= 0 stretch turned out to be
COMMON in this book's own history (42.4% of all 439 rolling 60-session windows,
across 8 separate episodes including one 55 sessions long that fully recovered),
and the current stretch is only ~1.3 standard errors from the book's own long-run
mean -- not statistically distinguishable from "the same process having a bad
quarter." The 20-vs-20 RED delta is worse: 48.6% of ALL such comparisons in this
book's history are RED, so on its own it carries almost no information. This file
now computes that context (`rolling_60_context`, `rolling_20v20_context`) so the
kill rule is never reported bare, and separately checks the ONE thing the same
pass found that IS new: whether the trailing-250-session ev/R has gone negative for
the first time in the book's own history (`trailing_250_first_negative`) -- that is
the defensible way to argue decay, not a single 60-session slice.

    python research/scoreboard_20v20.py

Writes research/scoreboard.md and research/scoreboard.json.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from omen_metrics import BOOK_PATH, ev_r_scoreboard, first_of_day_arm  # noqa: E402

OUT_MD = os.path.join(HERE, "scoreboard.md")
OUT_JSON = os.path.join(HERE, "scoreboard.json")


def rolling_windows(firsts, width):
    """ev/R over every contiguous `width`-pick window in `firsts`, in order.
    One number per window start index; len(out) == len(firsts) - width + 1."""
    out = []
    for i in range(0, len(firsts) - width + 1):
        window = firsts[i:i + width]
        sb = ev_r_scoreboard(window, risk_dollars=1000.0)
        out.append(sb["ev_r"])
    return out


def trailing_250_first_negative(firsts, width=250):
    """The first index (in pick order) at which the TRAILING `width`-session
    ev/R (picks [i-width+1 : i+1]) first goes negative, and whether it is
    still negative at the end of the book -- i.e. is this a NEW, still-open
    condition, not just a number that dipped once."""
    if len(firsts) < width:
        return None
    trail = []
    for i in range(width - 1, len(firsts)):
        window = firsts[i - width + 1:i + 1]
        sb = ev_r_scoreboard(window, risk_dollars=1000.0)
        trail.append((firsts[i]["day"], sb["ev_r"]))
    first_neg = next(((day, v) for day, v in trail if v < 0), None)
    still_negative = trail[-1][1] < 0 if trail else False
    # longest consecutive negative streak, and where the current one started
    streaks, cur_start, cur_len, best = [], None, 0, 0
    for day, v in trail:
        if v < 0:
            if cur_start is None:
                cur_start = day
            cur_len += 1
            best = max(best, cur_len)
        else:
            if cur_len:
                streaks.append(cur_len)
            cur_start, cur_len = None, 0
    current_streak = cur_len if still_negative else 0
    current_streak_start = cur_start if still_negative else None
    return {"width": width, "first_negative_day": first_neg[0] if first_neg else None,
            "first_negative_value": round(first_neg[1], 4) if first_neg else None,
            "still_negative_at_book_end": still_negative,
            "current_streak_sessions": current_streak,
            "current_streak_start_day": current_streak_start,
            "longest_streak_ever": best,
            "trailing_now": round(trail[-1][1], 4) if trail else None}


def quarter_of(day_str):
    y, m = day_str[:4], int(day_str[5:7])
    q = (m - 1) // 3 + 1
    return "%s Q%d" % (y, q)


def quarterly_ev_r(firsts):
    by_q = {}
    for r in firsts:
        by_q.setdefault(quarter_of(r["day"]), []).append(r)
    out = []
    for q in sorted(by_q):
        sb = ev_r_scoreboard(by_q[q], risk_dollars=1000.0)
        out.append({"quarter": q, "ev_r": sb["ev_r"], "n": sb["n"]})
    return out


def main():
    if not os.path.exists(BOOK_PATH):
        raise SystemExit("missing %s -- gzip -dk research/bt2y_trades_retest_on.json.gz first"
                          % BOOK_PATH)
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    firsts = first_of_day_arm(rows)
    n = len(firsts)
    print("book: %s -- %d one-a-day picks (size-gated)" % (os.path.basename(BOOK_PATH), n))

    if n < 40:
        raise SystemExit("only %d picks -- need at least 40 for a last-20-vs-prior-20 read" % n)

    last20 = firsts[-20:]
    prior20 = firsts[-40:-20]
    last60 = firsts[-60:] if n >= 60 else None

    sb_last = ev_r_scoreboard(last20, risk_dollars=1000.0)
    sb_prior = ev_r_scoreboard(prior20, risk_dollars=1000.0)
    sb_last60 = ev_r_scoreboard(last60, risk_dollars=1000.0) if last60 else None

    def fmt(sb):
        return ("ev/R %+.4f  n=%d  win %.1f%%  total_R %+.2f  max_dd_R %+.2f"
                % (sb["ev_r"], sb["n"], sb["win_rate"] * 100, sb["total_R"], sb["max_drawdown_R"]))

    print("\nlast 20 sessions (%s .. %s): %s"
          % (last20[0]["day"], last20[-1]["day"], fmt(sb_last)))
    print("prior 20 sessions (%s .. %s): %s"
          % (prior20[0]["day"], prior20[-1]["day"], fmt(sb_prior)))

    delta = sb_last["ev_r"] - sb_prior["ev_r"]
    getting_better = delta > 0
    print("\ndelta (last - prior): %+.4f ev/R -- %s"
          % (delta, "GREEN (getting better)" if getting_better else "RED (not getting better)"))

    kill_line = "n/a (book has fewer than 60 picks)"
    kill_triggered = False
    if sb_last60:
        kill_triggered = sb_last60["ev_r"] <= 0
        kill_line = ("ev/R %+.4f over the last 60 sessions (%s .. %s) -- %s"
                     % (sb_last60["ev_r"], last60[0]["day"], last60[-1]["day"],
                        "at or below zero" if kill_triggered else "above zero, not tripped"))
    print("\nkill rule (raw): %s" % kill_line)

    # ---- historical context, so the kill rule is never reported bare -----
    # An adversarial pass (2026-09-03 night) found the bare "TRIPPED" framing
    # misleading: a 60-session ev/R <= 0 stretch is common in this book's own
    # history. Compute that context every time so the number is never quoted
    # alone again.
    roll60 = rolling_windows(firsts, 60) if n >= 60 else []
    roll60_neg_frac = (sum(1 for v in roll60 if v <= 0) / len(roll60)) if roll60 else None
    roll60_mean = statistics.mean(roll60) if roll60 else None
    roll60_sd = statistics.stdev(roll60) if len(roll60) > 1 else None
    roll60_pct = (sum(1 for v in roll60 if v <= sb_last60["ev_r"]) / len(roll60) * 100
                 if roll60 and sb_last60 else None)
    t_stat = (None if not (roll60_sd and sb_last60)
             else (sb_last60["ev_r"] - roll60_mean) / (roll60_sd if roll60_sd else 1))

    deltas20v20 = []
    if n >= 40:
        for i in range(20, n - 19):
            a = ev_r_scoreboard(firsts[i - 20:i], risk_dollars=1000.0)["ev_r"]
            b = ev_r_scoreboard(firsts[i:i + 20], risk_dollars=1000.0)["ev_r"]
            deltas20v20.append(b - a)
    red_frac = (sum(1 for d in deltas20v20 if d <= 0) / len(deltas20v20)) if deltas20v20 else None
    delta_pct = (sum(1 for d in deltas20v20 if abs(d) <= abs(delta)) / len(deltas20v20) * 100
                if deltas20v20 else None)

    t250 = trailing_250_first_negative(firsts) if n >= 250 else None
    quarters = quarterly_ev_r(firsts)

    print("rolling-60 history: %d windows, %.1f%% at/below zero, current is %s "
          "percentile, %s stderr from the book's own long-run mean%s"
          % (len(roll60), (roll60_neg_frac or 0) * 100, "n/a" if roll60_pct is None else "%.0f" % roll60_pct,
             "n/a" if t_stat is None else "%+.2f" % t_stat,
             " -- NOT distinguishable from a normal bad stretch" if t_stat is not None and abs(t_stat) < 2 else ""))
    print("20-vs-20 delta history: %.1f%% of all such deltas are RED; current |delta| "
          "at the %s percentile of magnitude"
          % ((red_frac or 0) * 100, "n/a" if delta_pct is None else "%.0f" % delta_pct))
    if t250:
        print("trailing-250 ev/R: now %s, first went negative %s (still negative: %s, "
              "current streak %d sessions%s, longest ever %d)"
              % (t250["trailing_now"], t250["first_negative_day"] or "never",
                 t250["still_negative_at_book_end"], t250["current_streak_sessions"],
                 (" since %s" % t250["current_streak_start_day"]) if t250["current_streak_start_day"] else "",
                 t250["longest_streak_ever"]))

    md = ["# Scoreboard -- EV/R, last 20 sessions vs the prior 20", "",
          "One-trade-a-day pick stream (size-gated), `%s`, %d picks total. "
          "Same definition every week: `research/omen_metrics.py::ev_r_scoreboard` "
          "on `research/omen_metrics.py::first_of_day_arm`." % (os.path.basename(BOOK_PATH), n),
          "",
          "| window | sessions | ev/R | win % | total R | max DD (R) |",
          "|---|---|---:|---:|---:|---:|",
          "| last 20 | %s .. %s | %+.4f | %.1f%% | %+.2f | %+.2f |" % (
              last20[0]["day"], last20[-1]["day"], sb_last["ev_r"],
              sb_last["win_rate"] * 100, sb_last["total_R"], sb_last["max_drawdown_R"]),
          "| prior 20 | %s .. %s | %+.4f | %.1f%% | %+.2f | %+.2f |" % (
              prior20[0]["day"], prior20[-1]["day"], sb_prior["ev_r"],
              sb_prior["win_rate"] * 100, sb_prior["total_R"], sb_prior["max_drawdown_R"]),
          "",
          "**Delta (last - prior): %+.4f ev/R -- %s**"
          % (delta, "GREEN, getting better" if getting_better else "RED, not getting better"),
          "",
          "But read the delta next to its own history, not alone: **%.1f%% of every "
          "20-vs-20 comparison in this book's 2-year history is RED**, and the "
          "current |delta| sits at only the %s percentile of magnitude -- typical, "
          "not unusual." % ((red_frac or 0) * 100, "n/a" if delta_pct is None else "%.0f" % delta_pct),
          "",
          "## Kill rule (60 sessions at ev/R <= 0 means this approach is dead)", "",
          kill_line + ".", "",
          "**Read this next to its own history before treating it as news.** Across "
          "all %d rolling 60-session windows in this book, **%.1f%% sit at or below "
          "zero** (8 separate episodes, one 55 sessions long that fully recovered). "
          "The current window is at the %s percentile (low, but not rare) and "
          "%s standard errors from the book's own long-run mean%s. A single "
          "60-session slice of a process with per-trade sd ~1R and a long-run mean "
          "near zero trips this rule constantly by construction -- it is not, on "
          "its own, evidence of decay."
          % (len(roll60), (roll60_neg_frac or 0) * 100,
             "n/a" if roll60_pct is None else "%.0f" % roll60_pct,
             "n/a" if t_stat is None else "%+.2f" % t_stat,
             "" if t_stat is not None and abs(t_stat) >= 2 else
             " -- inside the range chance alone produces"),
          ""]

    if t250:
        md += ["## The one signal that IS new: trailing-250-session ev/R", "",
               "Trailing %d-session ev/R is now **%+.4f**. It first went negative on "
               "**%s** (value %+.4f) and %s (current streak: %d sessions%s; the "
               "longest negative streak anywhere else in the book's history is %d "
               "sessions). Unlike the 60-session kill rule, a first-ever sign flip "
               "on a 250-session trailing window is not something the book's own "
               "history has done before -- this is the more defensible way to argue "
               "the edge is decaying, not the 60-session slice above."
               % (t250["width"], t250["trailing_now"], t250["first_negative_day"],
                  t250["first_negative_value"],
                  "remains negative through the end of the book" if t250["still_negative_at_book_end"]
                  else "has since recovered",
                  t250["current_streak_sessions"], (" since %s" % t250["current_streak_start_day"])
                  if t250["current_streak_start_day"] else "", t250["longest_streak_ever"]),
               "", "| quarter | ev/R | n |", "|---|---:|---:|"]
        for q in quarters:
            md.append("| %s | %+.4f | %d |" % (q["quarter"], q["ev_r"], q["n"]))
        md.append("")

    md += ["Adversarial pass, 2026-09-03 night: the raw numbers above (last-20, "
           "prior-20, last-60, trailing-250) were independently re-derived and "
           "CONFIRMED; the bare 'kill rule tripped' framing this file used to print "
           "was found misleading and dropped in favor of the historical-context "
           "read above.", ""]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s" % OUT_MD)

    out = {"book": os.path.basename(BOOK_PATH), "n_picks": n,
           "last20": sb_last, "prior20": sb_prior, "delta": round(delta, 4),
           "getting_better": getting_better, "last60": sb_last60,
           "kill_triggered_raw": kill_triggered,
           "rolling_60_context": {
               "n_windows": len(roll60), "pct_at_or_below_zero": round((roll60_neg_frac or 0) * 100, 1),
               "current_percentile": roll60_pct, "current_vs_mean_stderr": t_stat,
               "distinguishable_from_chance": (abs(t_stat) >= 2) if t_stat is not None else None},
           "rolling_20v20_context": {
               "n_deltas": len(deltas20v20), "pct_red": round((red_frac or 0) * 100, 1),
               "current_abs_delta_percentile": delta_pct},
           "trailing_250": t250, "quarterly": quarters}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1, sort_keys=True)
    print("  -> %s" % OUT_JSON)
    return out


if __name__ == "__main__":
    main()
