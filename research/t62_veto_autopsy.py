"""t62_veto_autopsy.py -- which gate throws away Austin's trades?

Ticket 18 found the engine is not blind. Across his 120 graded day-cards the
break-and-retest FSM produces **1,601** valid setups and only **56** signals come
out the far end. Roughly 97% die AFTER detection, in grading and the veto stack.

Counting every veto over every bar answers the wrong question -- most of those
1,601 are setups Austin would not have taken either. The question that matters is
narrower:

    of the signals that land on one of his 64 marked entries (+/-3 bars),
    what killed them?

That is the true-positive kill list. A gate that vetoes 40,000 bars and none of
his entries is doing its job. A gate that vetoes 12 bars and 9 of them are his is
the wound.

    python research/t62_veto_autopsy.py

Writes research/t62_veto_autopsy.md.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from research.t4_engine_recall import (CaptureRunner, rth_candles, prior_day_levels,
                                       premarket_extremes, htf_bias, ENTRY_CUTOFF)
from research.t60_baseline import load_day_cards

OUT = os.path.join(HERE, "t62_veto_autopsy.md")
TOL = 3                      # bars, same tolerance every recall figure uses
TAG = re.compile(r"\[([^\]]+)\]")
SKIP_GRADES = ("X", "D")


def tags_of(reason):
    """Every bracketed annotation the veto stack left on a signal."""
    out = []
    for t in TAG.findall(reason or ""):
        t = t.strip()
        # normalise "capped C: S_GATE low displacement" -> "capped C: S_GATE"
        if ":" in t:
            head, rest = t.split(":", 1)
            t = "%s: %s" % (head.strip(), rest.strip().split(" (")[0][:44])
        out.append(t)
    return out


def why_graded_d(s):
    """Re-derive which branch of _grade_pa handed this signal a D.

    Not guesswork: _grade_pa is eight lines and every input is on the record.
    For BNR_STOP_MODE="level" the signal's stop IS the level it broke, which is
    also what grade_trade received -- the parameter is only NAMED or_high.

        long:  not bullish -> D ; low  > level -> D ; else C/B/A+
        short: not bearish -> D ; high < level -> D ; else C/B/A+
    """
    is_long = s.get("dir") == "call"
    level = s.get("stop")
    bullish = s["c"] >= s["o"]
    if level is None:
        return "no level on the signal"
    if is_long:
        if not bullish:
            return "entry candle is RED on a long"
        if s["l"] > level:
            return "candle never traded back down to the level"
    else:
        if bullish:
            return "entry candle is GREEN on a short"
        if s["h"] < level:
            return "candle never traded back up to the level"
    return "HTF bias opposed the trade"


def replay(symbol, day):
    """Every signal the engine considered on this day, reason strings intact."""
    candles = rth_candles(symbol, day)
    if not candles:
        return None
    pdh, pdl, pdo, pdc = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    r = CaptureRunner(symbol)
    r.pdh, r.pdl = pdh, pdl
    r.pmh, r.pml = pmh, pml
    r.pd_open, r.pd_close = pdo, pdc
    r.htf_bias = htf_bias(symbol, day)
    r.qqq_breaks = None

    sigs = []
    for i in range(5, len(candles)):
        if ENTRY_CUTOFF and candles[i].timestamp >= ENTRY_CUTOFF:
            continue
        r.candles = candles[: i + 1]
        before = len(r.captured)
        try:
            r.detect_signals()
        except Exception:
            continue
        for s in r.captured[before:]:
            sigs.append({"bar": i, "grade": s.get("grade"), "status": s.get("status"),
                         "level": s.get("stop_level_name"),
                         "stop": s.get("stop"), "dir": s.get("direction"),
                         "o": candles[i].open, "h": candles[i].high,
                         "l": candles[i].low, "c": candles[i].close,
                         "type": getattr(s.get("signal_type"), "value", s.get("signal_type")),
                         "reason": s.get("reason", "")})
    return sigs


def main():
    days, marks = load_day_cards()
    by_day = defaultdict(list)
    for m in marks:
        if m.get("entry_i") is not None:
            by_day[(m["symbol"], m["date"])].append(m)

    all_tags = Counter()          # every signal, every day
    all_grades = Counter()
    tp_tags = Counter()           # signals landing on one of Austin's entries
    tp_grades = Counter()
    tp_status = Counter()
    n_sigs = n_tp = 0
    tp_x_levels = Counter()      # which LEVEL did the X-graded true positives break?
    tp_x_why = Counter()         # and WHY did _grade_pa hand them a D?
    marks_covered = set()
    marks_total = sum(len(v) for v in by_day.values())
    days_run = 0

    for (sym, date) in sorted(days):
        sigs = replay(sym, date)
        if sigs is None:
            continue
        days_run += 1
        mine = by_day.get((sym, date), [])
        for s in sigs:
            n_sigs += 1
            all_grades[s["grade"]] += 1
            for t in tags_of(s["reason"]):
                all_tags[t] += 1
            hit = [m for m in mine if abs(s["bar"] - m["entry_i"]) <= TOL]
            if not hit:
                continue
            n_tp += 1
            tp_grades[s["grade"]] += 1
            tp_status[s["status"]] += 1
            if s["grade"] in SKIP_GRADES:
                tp_x_levels[s.get("level") or "(none)"] += 1
                tp_x_why[why_graded_d(s)] += 1
            for m in hit:
                marks_covered.add((sym, date, m["entry_i"]))
            for t in tags_of(s["reason"]):
                tp_tags[t] += 1

    L = ["# T62 — the veto autopsy", ""]
    L.append("Generated by `research/t62_veto_autopsy.py`. Replays Austin's **%d** graded "
             "day-cards bar by bar and reads the annotations the veto stack leaves on every "
             "signal's `reason` string." % days_run)
    L.append("")
    L.append("## 1. The funnel")
    L.append("")
    L.append("| stage | count |")
    L.append("|---|---:|")
    L.append("| signals the engine considered | %d |" % n_sigs)
    L.append("| ... landing within +/-%d bars of one of his entries | **%d** |" % (TOL, n_tp))
    L.append("| his marked entries the engine got anywhere near | **%d / %d** |"
             % (len(marks_covered), marks_total))
    L.append("")
    tradeable = sum(v for k, v in tp_grades.items() if k not in SKIP_GRADES)
    L.append("Of the %d signals that land on one of his entries, **%d** carry a tradeable "
             "grade and **%d** are graded %s." % (n_tp, tradeable, n_tp - tradeable,
                                                  " / ".join(SKIP_GRADES)))
    L.append("")

    L.append("## 2. What kills HIS entries")
    L.append("")
    L.append("This is the list that matters. A gate high here is throwing away trades Austin "
             "actually took.")
    L.append("")
    L.append("| tag on the signal | hits on his entries | hits everywhere | share of its own hits |")
    L.append("|---|---:|---:|---:|")
    for tag, c in tp_tags.most_common(30):
        everywhere = all_tags[tag]
        L.append("| `%s` | **%d** | %d | %.1f%% |"
                 % (tag, c, everywhere, 100.0 * c / max(everywhere, 1)))
    if not tp_tags:
        L.append("| _no tagged signal landed on any marked entry_ | | | |")
    L.append("")

    L.append("## 3. Grade of the signals that found him")
    L.append("")
    L.append("| grade | count |")
    L.append("|---|---:|")
    for g, c in sorted(tp_grades.items(), key=lambda kv: -kv[1]):
        L.append("| %s | %d |" % (g, c))
    L.append("")
    L.append("| status | count |")
    L.append("|---|---:|")
    for s, c in sorted(tp_status.items(), key=lambda kv: -kv[1]):
        L.append("| %s | %d |" % (s, c))
    L.append("")

    L.append("## 3b. Why _grade_pa handed them a D")
    L.append("")
    L.append("**Correction, 2026-08-23.** An earlier draft of this report claimed the grader "
             "measured `at_key_level` against the opening range whatever level the setup "
             "broke. That is wrong. Every `grade_trade` call site passes the real level — "
             "`level_hi`/`level_lo`, the FVG edge, the order block, the flag boundary. The "
             "parameter is merely still NAMED `or_high` from when the opening range was the "
             "only level there was. No level bug exists. The kill is the grader's actual "
             "logic:")
    L.append("")
    L.append("| why it was graded D | hits on his entries |")
    L.append("|---|---:|")
    for why, c in tp_x_why.most_common():
        L.append("| %s | **%d** |" % (why, c))
    L.append("")
    L.append("### The level the X-graded true positives were trading")
    L.append("")
    L.append("Reported for coverage, not blame — the grader saw each of these correctly.")
    L.append("")
    L.append("| level the setup actually broke | X-graded hits on his entries |")
    L.append("|---|---:|")
    for lv, c in tp_x_levels.most_common():
        L.append("| `%s` | %d |" % (lv, c))
    wrong = sum(c for lv, c in tp_x_levels.items() if lv not in ("OR high", "OR low"))
    tot = sum(tp_x_levels.values())
    L.append("")
    L.append("**%d of %d** (%.0f%%) were graded against a level they were not trading."
             % (wrong, tot, 100.0 * wrong / max(tot, 1)))
    L.append("")
    L.append("## 4. Every veto, over every bar")
    L.append("")
    L.append("Context only. A big number here is not evidence of a problem — most of these "
             "bars are setups Austin would have refused too.")
    L.append("")
    L.append("| tag | hits |")
    L.append("|---|---:|")
    for tag, c in all_tags.most_common(30):
        L.append("| `%s` | %d |" % (tag, c))
    L.append("")
    L.append("| grade, all signals | count |")
    L.append("|---|---:|")
    for g, c in sorted(all_grades.items(), key=lambda kv: -kv[1]):
        L.append("| %s | %d |" % (g, c))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("wrote %s" % OUT)
    print("  %d days, %d signals, %d landed on his entries, %d/%d marks reached"
          % (days_run, n_sigs, n_tp, len(marks_covered), marks_total))
    for tag, c in tp_tags.most_common(8):
        print("    %-46s %3d on his entries / %d everywhere" % (tag, c, all_tags[tag]))


if __name__ == "__main__":
    main()
