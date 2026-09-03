"""G7.1/labels -- the distribution and sample for the setup+level fix.

Austin, 2026-08-29: "so in homework also tell me what setup you think it is",
"remember BR and OCR is also a setup when both of them are together."

This reads the two new columns straight off `research/bt2y_trades.json`
(`setup_label`, `level_name`, `level_tf`, `entry_tf`, `bias_tf`, `level_px`) --
nothing is re-derived here. Those columns are written by `backtest_2y.py` off
fields `signal_runner.py` already stamps on every signal and
`backtest_week.SimTrade` now carries through (see research/g71_labeller.md for
the diagnosis and research/g72_labels_report.md for the write-up this script
produces).

Usage:
    python research/g72_labels_report.py                # print + write .md
    python research/g72_labels_report.py --n 20          # sample size
"""
import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades.json"
OUT_MD = ROOT / "research" / "g72_labels_report.md"


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=str(BOOK))
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", default=str(OUT_MD))
    a = ap.parse_args()

    book = json.loads(Path(a.book).read_text())
    meta = book["meta"]
    rows = [r for r in book["trades"] if r["traded"]]
    n = len(rows)

    setup_ct = Counter(r["setup_label"] for r in rows)
    # Distribution buckets pivots together (each carries its own @HH:MM in
    # level_name so the per-row sample below can show the exact swing point --
    # 150+ one-off rows is not a distribution). Every other level_name value is
    # already a fixed, small vocabulary and is left exactly as written.
    def bucket_level(name):
        if name.startswith("not-his: pivot high"):
            return "not-his: pivot high"
        if name.startswith("not-his: pivot low"):
            return "not-his: pivot low"
        return name
    level_ct = Counter(bucket_level(r["level_name"]) for r in rows)
    his_six = {"PDH", "PDL", "PMH", "PML", "HOD", "LOD"}
    his_ct = sum(v for k, v in level_ct.items() if k in his_six)

    # round-robin sample across setup classes, oldest first, so every class
    # is represented rather than the sample being dominated by BR+OCR (60%
    # of the book)
    by_setup = {}
    for r in sorted(rows, key=lambda r: (r["day"], r["et"])):
        by_setup.setdefault(r["setup_label"], []).append(r)
    order = [k for k, _ in setup_ct.most_common()]
    sample, i = [], 0
    while len(sample) < a.n:
        progressed = False
        for k in order:
            bucket = by_setup.get(k, [])
            if i < len(bucket):
                sample.append(bucket[i])
                progressed = True
                if len(sample) >= a.n:
                    break
        if not progressed:
            break
        i += 1
    sample.sort(key=lambda r: (r["day"], r["et"]))

    lines = []
    lines.append("# G7.1/labels -- the setup name and the level name, on every trade row")
    lines.append("")
    lines.append('> *"so in homework also tell me what setup you think it is"*')
    lines.append('> *"remember BR and OCR is also a setup when both of them are together."*')
    lines.append("> -- Austin, 2026-08-29")
    lines.append("")
    lines.append("**What changed.** Both fields already existed on every signal inside the "
                 "engine and were thrown away one line later, when the signal was turned "
                 "into a trade row (`research/g71_labeller.md`). Nothing new is computed. "
                 "`backtest_week.SimTrade` now carries `setup_type` and `stop_level_name` "
                 "through instead of dropping them, and `backtest_2y.py` writes them onto "
                 "every row as `setup_label` and `level_name` (plus `level_tf`, `entry_tf`, "
                 "`bias_tf`, `level_px`). No fill, no grade and no P&L moved -- this is a "
                 "relabelling of the same %d trades." % n)
    lines.append("")
    lines.append("**Correction to the earlier diagnosis:** `research/g71_labeller.md` still "
                 "guessed the opening range belonged in Austin's six levels. Asked directly "
                 "later the same day, his answer is **PDH, PDL, PMH, PML, HOD, LOD** -- the "
                 "opening range is not one of them (`Projects/omen-rulebook.md`, \"The six "
                 "levels, named at last\"). This report uses the corrected six.")
    lines.append("")
    lines.append("Book: `%s`, generated %s, %d sessions %s..%s, %d traded rows."
                 % (a.book, meta.get("generated", "?"), meta.get("sessions", "?"),
                    meta.get("first", "?"), meta.get("last", "?"), n))
    lines.append("")
    lines.append("## Setup, across the 2-year book")
    lines.append("")
    lines.append("| setup | trades | share |")
    lines.append("|---|---:|---:|")
    for k, v in setup_ct.most_common():
        lines.append("| %s | %d | %.1f%% |" % (k, v, pct(v, n)))
    lines.append("| **all** | **%d** | |" % n)
    lines.append("")
    lines.append("## Level, against his six")
    lines.append("")
    lines.append("| level | trades | share |")
    lines.append("|---|---:|---:|")
    for k, v in sorted(level_ct.items(), key=lambda kv: -kv[1]):
        lines.append("| %s | %d | %.1f%% |" % (k, v, pct(v, n)))
    lines.append("")
    lines.append("**His six coverage: %d / %d = %.1f%%.**" % (his_ct, n, pct(his_ct, n)))
    lines.append("")
    lines.append("## %d-row sample" % len(sample))
    lines.append("")
    lines.append("Round-robin across setup classes, oldest first, so no class is crowded out "
                 "by BR+OCR's 60% share. `eng` = legacy A+/A/B/C/X ladder, `aus` = Austin's "
                 "S/A/C ladder -- both, never mixed.")
    lines.append("")
    lines.append("| sym | day | et | side | setup | level | level px | entry TF | level TF | eng | aus | R | out |")
    lines.append("|---|---|---|---|---|---|---:|---|---|---|---|---:|---|")
    for r in sample:
        lines.append("| %s | %s | %s | %s | %s | %s | %.2f | %s | %s | %s | %s | %+.3f | %s |"
                     % (r["sym"], r["day"], r["et"], r["side"], r["setup_label"],
                        r["level_name"], r["level_px"], r["entry_tf"], r["level_tf"],
                        r["grade"], r["sgrade"], r["r"], r["out"]))
    lines.append("")
    lines.append("Reproduce with `python research/g72_labels_report.py`.")

    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("setup:")
    for k, v in setup_ct.most_common():
        print("   %-24s %6d  %5.1f%%" % (k, v, pct(v, n)))
    print()
    print("level:")
    for k, v in sorted(level_ct.items(), key=lambda kv: -kv[1]):
        print("   %-28s %6d  %5.1f%%" % (k, v, pct(v, n)))
    print()
    print("his six coverage: %d / %d = %.1f%%" % (his_ct, n, pct(his_ct, n)))
    print()
    print("wrote", a.out)


if __name__ == "__main__":
    main()
