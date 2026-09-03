"""G7.1 / ruleaudit -- reachability + compliance counts for every codified rule.

Reads the committed 2-year book (research/bt2y_trades.json, 76,019 signals /
500 sessions / 28 symbols, generated 2026-08-29 03:14 by backtest_2y.py) and
prints one count per rule claim in research/g71_ruleaudit.md. Nothing here
re-runs the engine; every number is a count over the book the engine produced.

Usage:  python research/g71_ruleaudit_counts.py
"""
import json, collections, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = json.load(open(ROOT / "research" / "bt2y_trades.json"))
T = BOOK["trades"]
META = BOOK["meta"]
TR = [r for r in T if r["traded"]]

def pct(a, b):
    return "%.2f%%" % (100.0 * a / b) if b else "n/a"

def meanR(rows):
    return statistics.fmean(r["r"] for r in rows) if rows else float("nan")

print("book: %d signals, %d traded, %d sessions, %s..%s"
      % (len(T), len(TR), META["sessions"], META["first"], META["last"]))
print()

# ---- 1. downgrade-variable reachability (research/downgrade.py CHECKS) ------
print("== 1. downgrade variables: trips over all %d signals ==" % len(T))
dw = collections.Counter()
for r in T:
    dw.update(r["downgrades"])
ALL_VARS = ["no_displacement", "stale_retest", "level_not_respected", "exhausted",
            "counter_trend_not_respected", "break_then_rejection", "no_retest",
            "ocr_not_respected", "chase", "large_counter_body",
            "multi_level_confluence", "sequence_gate"]
for v in ALL_VARS:
    n = dw.get(v, 0)
    trip = [r for r in TR if v in r["downgrades"]]
    clean = [r for r in TR if v not in r["downgrades"]]
    delta = (meanR(trip) - meanR(clean)) if trip and clean else float("nan")
    print("  %-30s %6d  %8s   traded trip %4d  meanR %+.4f  clean %4d %+.4f  delta %+.4f"
          % (v, n, pct(n, len(T)), len(trip), meanR(trip), len(clean), meanR(clean), delta))
print()

# ---- 2. grade ladders side by side -----------------------------------------
print("== 2. two ladders ==")
print("  legacy grade, all:    ", dict(collections.Counter(r["grade"] for r in T).most_common()))
print("  legacy grade, traded: ", dict(collections.Counter(r["grade"] for r in TR).most_common()))
print("  sgrade  (his), all:   ", dict(collections.Counter(r["sgrade"] for r in T).most_common()))
print("  sgrade  (his), traded:", dict(collections.Counter(r["sgrade"] for r in TR).most_common()))
print("  traded rows whose sgrade is NOT S: %d of %d (%s)"
      % (sum(1 for r in TR if r["sgrade"] != "S"), len(TR),
         pct(sum(1 for r in TR if r["sgrade"] != "S"), len(TR))))
print()

# ---- 3. the 2R target -------------------------------------------------------
print("== 3. planned R:R ==")
rr = collections.Counter()
for r in T:
    risk = abs(r["entry"] - r["stop"])
    rr[round(abs(r["target"] - r["entry"]) / risk, 3) if risk else None] += 1
print("  planned |target-entry|/|entry-stop| histogram:", dict(rr.most_common(6)))
print()

# ---- 4. the clock ----------------------------------------------------------
print("== 4. the session clock ==")
et = sorted(r["et"] for r in TR)
print("  traded entries: first %s  last %s" % (et[0], et[-1]))
print("  before 09:40: %d (%s of traded)" % (sum(1 for e in et if e < "09:40"),
                                             pct(sum(1 for e in et if e < "09:40"), len(et))))
print("  at/after 11:00: %d" % sum(1 for e in et if e >= "11:00"))
b1045 = [r for r in TR if "10:45" <= r["et"] < "11:00"]
print("  10:45-11:00 window kept: %d traded, meanR %+.4f" % (len(b1045), meanR(b1045)))
print()

# ---- 5. the stop floor -----------------------------------------------------
print("== 5. the -1.25R floor ==")
worse = [r for r in TR if r["r"] < -1.2501]
at = [r for r in TR if -1.2501 <= r["r"] <= -1.2499]
print("  traded rows worse than -1.25R: %d" % len(worse))
print("  traded rows resting exactly at -1.2500R: %d (%s)" % (len(at), pct(len(at), len(TR))))
print("  worst traded R: %+.4f" % min(r["r"] for r in TR))
print()

# ---- 6. setup balance ------------------------------------------------------
print("== 6. setup / pool balance ==")
print("  detections:", dict(collections.Counter(r["setup"] for r in T).most_common()))
print("  traded:    ", dict(collections.Counter(r["setup"] for r in TR).most_common()))
print("  traded pool:", dict(collections.Counter(r["pool"] for r in TR).most_common()))
print("  traded per symbol (bottom 6):",
      collections.Counter(r["sym"] for r in TR).most_common()[-6:])
print()

# ---- 7. the HTF veto -------------------------------------------------------
print("== 7. htf bias alignment (the veto with no author) ==")
print("  all signals:", dict(collections.Counter(r["aligned"] for r in T).most_common()))
print("  traded:     ", dict(collections.Counter(r["aligned"] for r in TR).most_common()))
opp = [r for r in T if r["aligned"] == "against"]
print("  opposed signals: %d (%s of the book); traded among them: %d"
      % (len(opp), pct(len(opp), len(T)), sum(1 for r in opp if r["traded"])))
print()

# ---- 8. confluence ---------------------------------------------------------
print("== 8. confluence (+1) discrimination ==")
cy = [r for r in TR if r["confluence"] == "yes"]
cn = [r for r in TR if r["confluence"] != "yes"]
print("  handed to %s of all signals; traded yes n=%d meanR %+.4f / no n=%d meanR %+.4f"
      % (pct(sum(1 for r in T if r["confluence"] == "yes"), len(T)),
         len(cy), meanR(cy), len(cn), meanR(cn)))
print()

# ---- 9. status funnel ------------------------------------------------------
print("== 9. status funnel ==")
print(" ", dict(collections.Counter(r["status"] for r in T).most_common()))
print("  money: meanR %+.4f  win%% %s  n=%d"
      % (meanR(TR), pct(sum(1 for r in TR if r["out"] == "win"), len(TR)), len(TR)))
print("  outcomes:", dict(collections.Counter(r["out"] for r in TR).most_common()))

# ---- 10. THE HEADLINE: the disaster stop IS the level stop ------------------
# backtest_week._disaster_hit (:379) rests the order at
#   disaster_stop_price(entry, abs(entry - stop), long, DISASTER_R=1.0)
#   = entry -/+ 1.0 * abs(entry - stop)
#   = stop                                     <-- identically, for every row
# and disaster_stop_hit (stop_rule.py:139) is an INTRABAR TOUCH test, evaluated
# BEFORE the close-triggered _stop_hit (backtest_week.py:540-546). So the level
# stop's close trigger is unreachable, wicks stop trades out, and
# stop_fill_price's -1.25R floor can never bind.
print("== 10. disaster stop vs level stop ==")
eq = 0
for r in TR:
    risk = abs(r["entry"] - r["stop"])
    if risk <= 0:
        continue
    px = r["entry"] - risk if r["side"] == "L" else r["entry"] + risk
    if abs(px - r["stop"]) < 1e-9:
        eq += 1
L = [r for r in TR if r["out"] == "loss"]
print("  rows where disaster-stop price == level-stop price: %d of %d (%s)"
      % (eq, len(TR), pct(eq, len(TR))))
print("  losses booking exactly -1.0000R: %d of %d (%s)"
      % (sum(1 for r in L if abs(r["r"] + 1.0) < 1e-9), len(L),
         pct(sum(1 for r in L if abs(r["r"] + 1.0) < 1e-9), len(L))))
print("  losses booking worse than -1.0000R: %d   (the -1.25R floor's whole population)"
      % sum(1 for r in L if r["r"] < -1.0 - 1e-9))
print("  => stop_rule.stop_fill_price's floor is unreachable code on this book.")
