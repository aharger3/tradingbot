"""T13 - candles beyond the hammer (R19: "not just hammers lol").

Two things, in order:

1. VALIDATE. Enumerate every named bullish/bearish candle formation and check
   each against research/corpus_index.jsonl (what the corpus actually teaches)
   and against Austin's own marks (research/*marks*.jsonl, research/marks/*).
   A formation that has zero hits in both does not ship - this repeats the
   method that already killed engulfing (research/hallucination-audit.md #14,
   "MENTIONED-ONCE, not a graded entry rule", killed 2026-07-11, net +$4k).

2. MEASURE. `omen_bot.py::PriceActionAnalyzer._grade_pa` already grades TWO
   corpus-validated shapes per direction (hammer/inverted-hammer at A+, large
   wick rejection at B) but `spec2_grading_check.py` - "the hammer-only test"
   the track brief names - only exercises the LONG side. Report trip rate and
   mean R per formation from the committed 2yr book
   (research/bt2y_trades.json, T0's post-ratified AFTER book) using the
   `grade` + `side` fields it already carries per signal.

Never touches a mark file. Never touches bt2y_trades.json - read only.

Usage:
  python research/t13_candle_formations.py
"""
from __future__ import annotations
import glob
import json
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CORPUS = os.path.join(HERE, "corpus_index.jsonl")
BT2Y = os.path.join(HERE, "bt2y_trades.json")

# Every named bullish/bearish candle formation worth checking. Regex, applied
# to corpus quotes and mark notes/reasons, case-insensitive.
FORMATIONS = {
    "hammer":              r"\bhammer\b",
    "inverted_hammer":     r"inverted hammer",
    "shooting_star":       r"shooting star",
    "bullish_engulfing":   r"bullish engulf|engulfs? the previous|engulf(ing|ed)?",
    "bearish_engulfing":   r"bearish engulf",
    "dragonfly_doji":      r"dragonfly doji",
    "gravestone_doji":     r"gravestone doji",
    "doji":                r"\bdoji\b",
    "marubozu":            r"marubozu",
    "piercing_line":       r"piercing( line)?",
    "dark_cloud_cover":    r"dark cloud cover",
    "three_line_strike":   r"three.line strike",
    "morning_star":        r"morning star",
    "evening_star":        r"evening star",
    "spinning_top":        r"spinning top",
    "harami":              r"harami",
    "tweezer":             r"tweezer",
    "belt_hold":           r"belt hold",
    "kicker":              r"\bkicker\b",
    "three_soldiers_crows": r"three white soldiers|three black crows",
    "island_reversal":     r"island reversal",
    "large_wick_rejection": r"\bwick\b.{0,40}reject|reject.{0,40}\bwick\b|large (lower|upper) wick",
    "pin_bar":             r"pin ?bar",
}

# Formations already coded in omen_bot.py::PriceActionAnalyzer, and where.
CODED = {
    "hammer": "is_hammer_stick -> A+ (long)",
    "inverted_hammer": "is_inverted_hammer -> A+ (short)",
    "shooting_star": "is_inverted_hammer -> A+ (short, same shape, corpus uses both names)",
    "large_wick_rejection": "has_large_lower_wick / has_large_upper_wick -> B (both directions)",
    "bullish_engulfing": "REMOVED 2026-07-11 (hallucination-audit #14) - kept out here too",
    "bearish_engulfing": "never coded",
}


def load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def corpus_hits():
    """formation -> list of (speaker, class, source_file, quote[:180])"""
    out = defaultdict(list)
    for d in load_jsonl(CORPUS):
        q = (d.get("quote") or "")
        ql = q.lower()
        for name, pat in FORMATIONS.items():
            if re.search(pat, ql):
                out[name].append((d.get("speaker"), d.get("class"),
                                   d.get("source_file"), q[:180]))
    return out


# Every human-judgement file this repo has (mirrors CLAUDE.md's mark-file
# table). Read-only; never written.
MARK_GLOBS = [
    "research/*marks*.jsonl",
    "research/*verdicts*.json",
    "research/marks/*.jsonl",
]


def mark_hits():
    out = defaultdict(int)
    seen_files = set()
    for pat in MARK_GLOBS:
        for fp in glob.glob(os.path.join(ROOT, pat)):
            if fp in seen_files:
                continue
            seen_files.add(fp)
            try:
                with open(fp, encoding="utf-8") as fh:
                    txt = fh.read()
            except OSError:
                continue
            txtl = txt.lower()
            for name, pat2 in FORMATIONS.items():
                out[name] += len(re.findall(pat2, txtl))
    return out


def formation_label(grade, side):
    """Map a bt2y_trades.json (grade, side) pair to the candle formation
    _grade_pa actually assigned it. 'A' is a context upgrade of B done later
    in signal_runner.py (clear-road / aplus_stack), NOT a candle shape -
    excluded from this table on purpose (see report)."""
    if grade == "A+":
        return "hammer (bullish A+)" if side == "L" else "inverted_hammer/shooting_star (bearish A+)"
    if grade == "B":
        return "large_lower_wick (bullish B)" if side == "L" else "large_upper_wick (bearish B)"
    if grade == "C":
        return "plain retest, no named shape (C)"
    if grade == "X":
        return "no bullish/bearish PA at all (X, skip)"
    return f"other ({grade}/{side})"


def bt2y_formation_table():
    d = json.load(open(BT2Y, encoding="utf-8"))
    trades = d["trades"]
    n_signals = len(trades)
    buckets = defaultdict(lambda: {"signals": 0, "traded": 0, "r_sum": 0.0})
    for t in trades:
        label = formation_label(t["grade"], t["side"])
        b = buckets[label]
        b["signals"] += 1
        if t.get("traded"):
            b["traded"] += 1
            b["r_sum"] += t.get("r", 0.0)
    rows = []
    for label, b in sorted(buckets.items(), key=lambda kv: -kv[1]["signals"]):
        mean_r = b["r_sum"] / b["traded"] if b["traded"] else None
        rows.append({
            "formation": label,
            "signals": b["signals"],
            "trip_rate_pct": round(b["signals"] / n_signals * 100, 3),
            "traded": b["traded"],
            "mean_r": round(mean_r, 4) if mean_r is not None else None,
        })
    return {"n_signals": n_signals, "n_traded": d["meta"]["traded"], "rows": rows}


def main():
    ch = corpus_hits()
    mh = mark_hits()
    print("=== corpus / mark support per formation ===")
    validated = []
    for name in FORMATIONS:
        c = len(ch.get(name, []))
        m = mh.get(name, 0)
        support = c > 0 or m > 0
        if support:
            validated.append(name)
        print(f"{name:26s} corpus={c:4d}  marks={m:3d}  {'VALIDATED' if support else 'no support'}")

    print("\n=== validated formations, coded status ===")
    for name in validated:
        print(f"{name:26s} {CODED.get(name, 'NOT CODED - candidate to add')}")

    print("\n=== bt2y_trades.json (T0 AFTER book, committed) - trip rate & mean R per formation ===")
    table = bt2y_formation_table()
    print(f"n_signals={table['n_signals']}  n_traded={table['n_traded']}")
    for r in table["rows"]:
        mr = "n/a" if r["mean_r"] is None else f"{r['mean_r']:+.4f}"
        print(f"{r['formation']:42s} signals={r['signals']:6d} "
              f"trip={r['trip_rate_pct']:6.3f}%  traded={r['traded']:5d}  mean_r={mr}")

    out = {
        "corpus_support": {k: len(v) for k, v in ch.items()},
        "mark_support": dict(mh),
        "validated_formations": validated,
        "bt2y_formation_table": table,
    }
    outp = os.path.join(HERE, "t13_candle_formations.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print("\nwrote " + outp)


if __name__ == "__main__":
    main()
