"""G71/rule84ocr ADVERSARIAL VERIFY: can the book group by BR+OCR confluence?

The claim under test: "the BR_OCR_CONFLUENCE label dies at the SimTrade
boundary, so no book, report or A/B can group by it."

The mechanical half is true (SimTrade carries no setup_type/br_ocr field).
The consequence is false. `backtest_2y.py:198` writes a `confluence` column
from `dg.score(...)["confluence"]`; with `ENABLE_MULTI_LEVEL_CONFLUENCE=False`
(research/downgrade.py:91) that reduces to `has_confluence()` exactly -- the
same predicate `_label_confluence` applies (signal_runner.py:2410-2421), on the
same inputs (t.stop as the level proxy, same direction, same bar).

So SignalType.BR_OCR_CONFLUENCE is reconstructible from the shipped book as
  setup in CONFLUENCE_BASE_SETUPS  AND  confluence == "yes"
where CONFLUENCE_BASE_SETUPS = {break_and_retest, one_candle_rule}
(signal_runner.py:852) -- reentry_84_rule is excluded by the detector and must
be excluded here, which the naive `confluence == "yes"` filter gets wrong.

Read-only. Touches no engine file, no mark file.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = json.load(open(ROOT / "research" / "bt2y_trades.json", encoding="utf-8"))
T, M = B["trades"], B["meta"]
BASE = {"break_and_retest", "one_candle_rule"}      # CONFLUENCE_BASE_SETUPS

print("BOOK", M["first"], "->", M["last"], M["sessions"], "sessions",
      M["signals"], "signals", M["traded"], "traded  gen", M["generated"])
print("setup values in book:", Counter(r["setup"] for r in T).most_common())
print("setup_type column present:", any("setup_type" in r for r in T),
      "  br_ocr column present:", any("br_ocr" in r for r in T))
print("confluence column present:", "confluence" in T[0],
      Counter(r["confluence"] for r in T).most_common())

is_brocr = lambda r: r["setup"] in BASE and r["confluence"] == "yes"
lab = [r for r in T if is_brocr(r)]
print("\nreconstructed BR_OCR_CONFLUENCE detections: %d / %d (%.1f%%)"
      % (len(lab), len(T), 100 * len(lab) / len(T)))
naive = [r for r in T if r["confluence"] == "yes"]
print("naive confluence=='yes' over-counts by %d rows, all reentry_84_rule "
      "(the detector never labels it -- signal_runner.py:852)"
      % (len(naive) - len(lab)))

print("\nthe A/B the claim says is impossible, on traded rows:")
tr = [r for r in T if r["traded"]]
for lbl, sel in (("BR+OCR", is_brocr), ("not BR+OCR", lambda r: not is_brocr(r))):
    g = [r for r in tr if sel(r)]
    R = [r["r"] for r in g]
    print("  %-11s n=%5d  meanR=%+.4f  win=%.1f%%  days=%d"
          % (lbl, len(g), sum(R) / len(R),
             100 * sum(1 for r in g if r["out"] == "win") / len(g),
             len(set((r["sym"], r["day"]) for r in g))))

print("\nper-base-setup split (detections / traded):")
for s in sorted(BASE) + ["reentry_84_rule"]:
    rr = [r for r in T if r["setup"] == s]
    y = sum(1 for r in rr if r["confluence"] == "yes")
    t2 = [r for r in rr if r["traded"]]
    ty = sum(1 for r in t2 if r["confluence"] == "yes")
    print("  %-18s det %6d/%6d = %5.1f%%   traded %4d/%4d = %5.1f%%%s"
          % (s, y, len(rr), 100 * y / len(rr), ty, len(t2),
             100 * ty / max(len(t2), 1),
             "   <- NOT labelled by the detector" if s not in BASE else ""))
