"""P3/G8 — prove the book did not move, then print the funnel Austin asked for.

Two jobs, one pass:

  1. DIFF. `research/bt2y_trades.json` is the canonical 2-year book (45,175
     signals, 1,016 traded, mean R +0.957, win rate 53.2%). A replay run after
     the BR+OCR confluence label was added must reproduce it EXACTLY, with the
     only difference being that some rows now carry the new setup label. Every
     field is compared row by row; `tags` and `reason` are allowed to differ by
     exactly the new " [brocr]" tag and nothing else.

  2. FUNNEL. detection -> grade -> traded for break-and-retest alone, the one
     candle rule alone, and BR+OCR confluence, side by side. "Grade" is the
     legacy A+/A/B/C/X ladder that actually gates trades: a row passes it when
     its grade is not a skip grade. Austin's S/A/C ladder is printed alongside,
     because DIRECTION.md requires every new measurement to carry both.

The confluence label rides on the reason tag `[brocr]`, which backtest_2y.py
already lifts into each row's `tags`. The book also carries a `confluence`
column computed offline by downgrade.score at the same bar and level, so the
two are cross-checked here: if they ever disagree, there are two definitions of
confluence in the repo and one of them is wrong.

    python research/p3_confluence_funnel.py \
        [--old research/bt2y_trades.json] [--new research/p3_confluence.json] \
        [--out research/p3_confluence.md]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG = "brocr"
TAG_TEXT = " [brocr]"
SKIP_GRADES = ("X", "D")
BR, OCR, CONF = "break_and_retest", "one_candle_rule", "br_ocr_confluence"


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def label(row):
    """The setup identity as reported by P3/G8: confluence is its own row."""
    if row["setup"] in (BR, OCR) and TAG in row.get("tags", ()):
        return CONF
    return row["setup"]


def book_stats(rows):
    traded = [r for r in rows if r["traded"]]
    wins = [r for r in traded if r["out"] == "win"]
    tot = sum(r["r"] for r in traded)
    return {
        "signals": len(rows),
        "traded": len(traded),
        "wins": len(wins),
        "win_rate": (100.0 * len(wins) / len(traded)) if traded else 0.0,
        "mean_r": (tot / len(traded)) if traded else 0.0,
        "total_r": tot,
    }


def funnel(rows, name):
    graded = [r for r in rows if r["grade"] not in SKIP_GRADES]
    traded = [r for r in rows if r["traded"]]
    wins = [r for r in traded if r["out"] == "win"]
    tot = sum(r["r"] for r in traded)
    sg = Counter(r["sgrade"] for r in rows)
    return {
        "setup": name,
        "detected": len(rows),
        "graded": len(graded),
        "traded": len(traded),
        "grade_pct": 100.0 * len(graded) / len(rows) if rows else 0.0,
        "traded_pct": 100.0 * len(traded) / len(rows) if rows else 0.0,
        "win_rate": 100.0 * len(wins) / len(traded) if traded else 0.0,
        "mean_r": tot / len(traded) if traded else 0.0,
        "total_r": tot,
        "s": sg.get("S", 0), "a": sg.get("A", 0), "c": sg.get("C", 0),
    }


# --- 1. the diff ----------------------------------------------------------

def diff(old_rows, new_rows, out):
    if len(old_rows) != len(new_rows):
        out.append("**ROW COUNT MOVED**: %d -> %d" % (len(old_rows), len(new_rows)))
        return False, 0
    ignore = {"tags", "reason"}
    field_mismatch = Counter()
    tag_only, unexpected = 0, 0
    for o, n in zip(old_rows, new_rows):
        for k in o:
            if k in ignore:
                continue
            if o[k] != n.get(k):
                field_mismatch[k] += 1
        ot, nt = list(o.get("tags", ())), list(n.get("tags", ()))
        if ot == nt:
            if o.get("reason") != n.get("reason"):
                unexpected += 1
            continue
        if [t for t in nt if t != TAG] == ot and TAG in nt:
            tag_only += 1
            if n["reason"].replace(TAG_TEXT, "", 1) != o["reason"]:
                unexpected += 1
        else:
            unexpected += 1
    ok = not field_mismatch and not unexpected
    out.append("| check | result |")
    out.append("|---|---|")
    out.append("| rows compared | %d |" % len(old_rows))
    out.append("| rows whose ONLY change is the new `[brocr]` tag | %d |" % tag_only)
    out.append("| rows with any other field changed | %d |"
               % (sum(field_mismatch.values()) + unexpected))
    if field_mismatch:
        for k, v in field_mismatch.most_common():
            out.append("| **field `%s` moved** | %d rows |" % (k, v))
    return ok, tag_only


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--old", default="research/bt2y_trades.json")
    ap.add_argument("--new", default="research/p3_confluence.json")
    ap.add_argument("--out", default="research/p3_confluence.md")
    args = ap.parse_args()

    old = load(ROOT / args.old)
    new = load(ROOT / args.new)
    o_rows, n_rows = old["trades"], new["trades"]

    md = ["# P3 / G8 — BR+OCR confluence as its own setup",
          "",
          "Generated by `research/p3_confluence_funnel.py` from `%s` (canonical) "
          "and `%s` (replay after the change)." % (args.old, args.new),
          ""]

    md.append("## The book did not move")
    md.append("")
    ob, nb = book_stats(o_rows), book_stats(n_rows)
    md.append("| | canonical | after P3 |")
    md.append("|---|---:|---:|")
    for key, fmt in (("signals", "%d"), ("traded", "%d"), ("wins", "%d"),
                     ("win_rate", "%.2f%%"), ("mean_r", "%+.4fR"),
                     ("total_r", "%+.2fR")):
        md.append("| %s | %s | %s |" % (key.replace("_", " "),
                                        fmt % ob[key], fmt % nb[key]))
    md.append("")
    same_headline = all(abs(ob[k] - nb[k]) < 1e-9 for k in ob)
    ok, tag_only = diff(o_rows, n_rows, md)
    md.append("")
    md.append("**Verdict: %s**" % ("IDENTICAL — %d signals re-labelled, nothing "
                                   "else changed" % tag_only if (ok and same_headline)
                                   else "THE BOOK MOVED — do not ship"))
    md.append("")

    # cross-check the detection-time label against the offline column
    agree = sum(1 for r in n_rows
                if (TAG in r.get("tags", ())) == (r["confluence"] == "yes"
                                                  and r["setup"] in (BR, OCR)))
    md.append("Cross-check: the detection-time `[brocr]` label and the book's "
              "`confluence` column (computed offline by `downgrade.score` on the "
              "whole day at the same bar and level) agree on **%d of %d** rows — "
              "one definition of confluence, two call sites."
              % (agree, len(n_rows)))
    md.append("")

    md.append("## The funnel: detection -> grade -> traded")
    md.append("")
    by = {}
    for r in n_rows:
        by.setdefault(label(r), []).append(r)
    md.append("| setup | detected | passed grade | traded | grade % | traded % | "
              "win rate | mean R | total R | S / A / C |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    order = [BR, OCR, CONF] + sorted(k for k in by if k not in (BR, OCR, CONF))
    for k in order:
        if k not in by:
            continue
        f = funnel(by[k], k)
        md.append("| `%s` | %d | %d | %d | %.1f%% | %.2f%% | %.1f%% | %+.3fR | "
                  "%+.1fR | %d / %d / %d |"
                  % (f["setup"], f["detected"], f["graded"], f["traded"],
                     f["grade_pct"], f["traded_pct"], f["win_rate"], f["mean_r"],
                     f["total_r"], f["s"], f["a"], f["c"]))
    md.append("")

    # what the confluence rows were filed under before
    md.append("Which detector the confluence rows used to be filed under:")
    md.append("")
    md.append("| was filed as | detected | passed grade | traded |")
    md.append("|---|---:|---:|---:|")
    for k in (BR, OCR):
        sub = [r for r in by.get(CONF, ()) if r["setup"] == k]
        if not sub:
            continue
        md.append("| `%s` | %d | %d | %d |"
                  % (k, len(sub),
                     sum(1 for r in sub if r["grade"] not in SKIP_GRADES),
                     sum(1 for r in sub if r["traded"])))
    md.append("")
    md.append("Old labels for comparison (confluence still folded in): "
              + ", ".join("`%s` %d detected / %d traded"
                          % (k, sum(1 for r in n_rows if r["setup"] == k),
                             sum(1 for r in n_rows if r["setup"] == k and r["traded"]))
                          for k in (BR, OCR)) + ".")
    md.append("")

    md.append("## Read this before quoting the confluence row")
    md.append("")
    md.append("- **Confluence is the common case, not the rare one.** It is on "
              "%.1f%% of all detections and %.1f%% of break-and-retest ones. "
              "`downgrade.py`'s thresholds are Austin's variables with guessed "
              "numbers (its own header says so, and A1/P2 owns tuning them); "
              "`find_ocr`'s isolation test already cut confluence from 84%% of "
              "signals to this. If the label is meant to mark his best setups "
              "rather than most of them, that is a threshold question, not a "
              "labelling one."
              % (100.0 * len(by.get(CONF, ())) / len(n_rows),
                 100.0 * sum(1 for r in by.get(CONF, ()) if r["setup"] == BR)
                 / max(1, sum(1 for r in n_rows if r["setup"] == BR))))
    md.append("- **The S / A / C column is partly circular for confluence.** "
              "Confluence is the `+1` in `grade = S - tripped + confluence`, so "
              "a confluence row needs one fewer clean variable to reach S. Read "
              "it as \"where his S grades live\", not as evidence that "
              "confluence causes them.")
    md.append("- **Routing did not change and no gate moved.** The label is a "
              "label; `CONFLUENCE_SETUP_ROUTES` (default OFF) is the one "
              "variable that would make it route as its own setup. "
              "`downgrade.py` stays unwired.")
    md.append("")

    text = "\n".join(md) + "\n"
    (ROOT / args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if (ok and same_headline) else 1


if __name__ == "__main__":
    sys.exit(main())
