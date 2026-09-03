"""G71/rule84ocr: fire counts for the 84% rule and the one-candle rule.

Sources (read-only):
  research/bt2y_trades.json        - the 2-year book, 500 sessions, all signals
  research/marks/probe_s_sweep_2026-08-28.jsonl - the 100-card graded sample
No engine file is touched. Publishes every number quoted in research/g71_rule84ocr.md.
"""
import json, re, statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = json.load(open(ROOT / "research" / "bt2y_trades.json", encoding="utf-8"))
T = B["trades"]
print("META", B["meta"]["first"], B["meta"]["last"], B["meta"]["sessions"], "sessions,",
      len(T), "signals")

def blk(title): print("\n== " + title)

blk("setup x status (all 76k detections)")
tab = defaultdict(Counter)
for r in T:
    tab[r["setup"]][r["status"]] += 1
for s, c in tab.items():
    print(f"  {s:20s} n={sum(c.values()):6d}  " + " ".join(f"{k}={v}" for k, v in c.most_common()))

blk("setup: traded rows, mean R, win rate")
for s in ("break_and_retest", "one_candle_rule", "reentry_84_rule"):
    rr = [r for r in T if r["setup"] == s and r["traded"]]
    if not rr: print(f"  {s}: 0 traded"); continue
    R = [r["r"] for r in rr]
    w = sum(1 for r in rr if r["out"] == "win")
    print(f"  {s:20s} traded={len(rr):5d}  meanR={sum(R)/len(R):+.4f}  win={w/len(rr)*100:.1f}%"
          f"  days={len(set((r['sym'],r['day']) for r in rr))}")

blk("84% rule: per-session fire rate + arming")
r84 = [r for r in T if r["setup"] == "reentry_84_rule"]
print(f"  detections {len(r84)} over {B['meta']['sessions']} sessions "
      f"= {len(r84)/B['meta']['sessions']:.3f}/session")
print(f"  traded     {sum(1 for r in r84 if r['traded'])}")
print(f"  status     {Counter(r['status'] for r in r84).most_common()}")
print(f"  grade      {Counter(r['grade'] for r in r84).most_common()}")
print(f"  sgrade     {Counter(r['sgrade'] for r in r84).most_common()}")
losses = [r for r in T if r["traded"] and r["out"] == "loss"]
print(f"  full stop-out losses in book (the arming pool) = {len(losses)}")
print(f"  84% traded / arming pool = {sum(1 for r in r84 if r['traded'])}/{len(losses)}"
      f" = {sum(1 for r in r84 if r['traded'])/len(losses)*100:.1f}%")

blk("84%: the implicit rr_ok tolerance, measured on the book")
# reason carries "prior entry $X"; entry is the fill at that price.
# Reconstruct d = (reclaim close - prior entry)/R is not in the book, so instead
# prove the algebra holds for the shipped 2.000 R:R plan.
print("  every row plans target = entry + 2R exactly; check on traded BR rows:")
rat = [round((r["target"] - r["entry"]) / (r["entry"] - r["stop"]), 4)
       for r in T if r["traded"] and r["setup"] == "break_and_retest" and r["dir"] == "call"
       and r["entry"] != r["stop"]]
print("   ", Counter(rat).most_common(3), f"(n={len(rat)})")

blk("one-candle rule: detection funnel")
ocr = [r for r in T if r["setup"] == "one_candle_rule"]
print(f"  detections {len(ocr)}  ({len(ocr)/len(T)*100:.1f}% of all signals)")
print(f"  status     {Counter(r['status'] for r in ocr).most_common()}")
print(f"  grade      {Counter(r['grade'] for r in ocr).most_common()}")
print(f"  sgrade     {Counter(r['sgrade'] for r in ocr).most_common()}")
w = [r for r in ocr if r["status"] == "skipped_tight_stop"]
print(f"  skipped_tight_stop {len(w)} = {len(w)/len(ocr)*100:.1f}% of OCR detections")
allw = [r for r in T if r["status"] == "skipped_tight_stop"]
print(f"  ...of {len(allw)} such skips book-wide, OCR is {len(w)/len(allw)*100:.1f}%")
print(f"  OCR stop_pct median {st.median([r['stop_pct'] for r in ocr]):.3f}% "
      f"vs BR {st.median([r['stop_pct'] for r in T if r['setup']=='break_and_retest']):.3f}%")

blk("BR+OCR together: the `confluence` column (downgrade.has_confluence)")
print(f"  all detections  yes={sum(1 for r in T if r['confluence']=='yes')} "
      f"({sum(1 for r in T if r['confluence']=='yes')/len(T)*100:.1f}%)")
for s in ("break_and_retest", "one_candle_rule", "reentry_84_rule"):
    rr = [r for r in T if r["setup"] == s]
    y = sum(1 for r in rr if r["confluence"] == "yes")
    tr = [r for r in rr if r["traded"]]
    ty = sum(1 for r in tr if r["confluence"] == "yes")
    print(f"  {s:20s} det {y}/{len(rr)} = {y/len(rr)*100:.1f}%   "
          f"traded {ty}/{len(tr) or 1} = {ty/(len(tr) or 1)*100:.1f}%")
tr = [r for r in T if r["traded"]]
for lab, sel in (("BR+OCR (conf=yes)", lambda r: r["confluence"] == "yes"),
                 ("BR only (conf=no)", lambda r: r["confluence"] == "no")):
    rr = [r for r in tr if sel(r)]
    R = [r["r"] for r in rr]
    print(f"  {lab:20s} n={len(rr):5d} meanR={sum(R)/len(R):+.4f} "
          f"win={sum(1 for r in rr if r['out']=='win')/len(rr)*100:.1f}%")
print("  NOTE: no `setup_type`/`br_ocr` column exists in the book — backtest_2y.py:165")
print("        writes t.signal_type, and signal_type only becomes BR_OCR_CONFLUENCE")
print("        when CONFLUENCE_SETUP_ROUTES=1 (signal_runner.py:847, default OFF).")

blk("the 100-card graded sample")
M = [json.loads(l) for l in open(ROOT / "research" / "marks" /
                                 "probe_s_sweep_2026-08-28.jsonl", encoding="utf-8") if l.strip()]
print(f"  cards {len(M)}   keys {sorted(M[0].keys())}")
def notes(m):
    return " ".join(str(v) for k, v in m.items() if isinstance(v, str)).lower()
n84 = [m for m in M if re.search(r"84", notes(m))]
nocr = [m for m in M if re.search(r"\bocr\b|one candle", notes(m))]
nboth = [m for m in M if m in n84 and m in nocr]
print(f"  cards whose text mentions 84%      : {len(n84)}")
print(f"  cards whose text mentions OCR/1cdl : {len(nocr)}")
print(f"  cards mentioning both              : {len(nboth)}")
print(f"  grade dist: {Counter(str(m.get('grade')) for m in M).most_common()}")
for m in nocr[:12]:
    print("   OCR>", (m.get('symbol'), m.get('day'), m.get('grade'), notes(m)[:150]))
for m in n84[:6]:
    print("   84%>", (m.get('symbol'), m.get('day'), m.get('grade'), notes(m)[:150]))
