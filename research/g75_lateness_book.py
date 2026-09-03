"""g75_lateness_book.py -- does the 40-minute gap hold at book scale, and is
the cause the one I read off the seven cards?

The hypothesis from the case studies:
  a break-and-retest level (PDH/PDL/PMH/PML) EXISTS BEFORE THE BELL, so the
  detector can fire the first time price does the four-step dance on it.
  A one-candle-rule "level" is an order block -- a candle -- that has to be
  MANUFACTURED by the session first, and MarketStructure only ever keeps the
  block belonging to the MOST RECENT structure break. So the OCR entry is
  pinned a few bars behind the newest swing extreme, and the newest swing
  extreme keeps moving later all morning.

Testable consequences, all measured here on the whole 2-year book:
  1. OCR fires later in the session than B&R, at scale.
  2. The gap is NOT a few-bar confirmation lag: OCR entries sit only a handful
     of bars behind their own order block. The block itself is late.
  3. Every B&R level is old (born pre-market); every OCR level is young.
  4. The lateness is a property of the setup, not of the day: measured within
     the same symbol-day, on days where both setups fire.

Read-only. Reads research/bt2y_trades.json. Writes research/g75_lateness_book.json.
"""
from __future__ import annotations
import json, os, random, re, statistics as st
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g75_lateness_book.json")
RNG = random.Random(75)
J = {}


def med(x):
    return st.median(x) if x else float("nan")


def mins(et):
    return (int(et[:2]) - 9) * 60 + int(et[3:]) - 30


def boot_diff(a, b, iters=2000, cap=3000):
    """95% CI on median(a) - median(b) by resampling. `cap` bounds the resample
    size on huge arms; the CI it reports is therefore conservative (wider than
    the full-sample one), never flattering."""
    na, nb = min(len(a), cap), min(len(b), cap)
    ca, cb = RNG.choice, RNG.choice
    d = []
    for _ in range(iters):
        d.append(med([ca(a) for _ in range(na)]) - med([cb(b) for _ in range(nb)]))
    d.sort()
    return d[int(0.025 * iters)], d[int(0.975 * iters)]


rows = json.load(open(BOOK, encoding="utf-8"))["trades"]
print("book rows (every setup the engine looked at): %d ; traded: %d"
      % (len(rows), sum(1 for r in rows if r["traded"])))

NAME = {"one_candle_rule": "one-candle rule", "break_and_retest": "break-and-retest",
        "reentry_84_rule": "84% re-entry"}
ARMS = ["one_candle_rule", "break_and_retest", "reentry_84_rule"]

# ---------------------------------------------------------------- 1. clock
print()
print("=" * 88)
print("1. WHAT TIME OF DAY EACH SETUP FIRES -- whole book, not 7 cards")
print("=" * 88)
J["clock"] = {}
for scope, sel in (("every signal", lambda r: True),
                   ("only the ones it traded", lambda r: r["traded"])):
    print()
    print("  %s:" % scope)
    print("  %-18s %7s  %8s  %8s  %8s   %s"
          % ("setup", "n", "median", "mean", "25th-75th", "share firing after 10:00"))
    keep = {}
    for s in ARMS:
        v = [mins(r["et"]) for r in rows if r["setup"] == s and sel(r)]
        if not v:
            continue
        keep[s] = v
        q = sorted(v)
        print("  %-18s %7d  %8.0f  %8.1f  %3.0f-%-4.0f   %5.1f%%"
              % (NAME[s], len(v), med(v), st.fmean(v),
                 q[len(q) // 4], q[3 * len(q) // 4],
                 100.0 * sum(1 for x in v if x >= 30) / len(v)))
    if "one_candle_rule" in keep and "break_and_retest" in keep:
        a, b = keep["one_candle_rule"], keep["break_and_retest"]
        lo, hi = boot_diff(a, b)
        print("  --> one-candle rule is %+.0f min later than break-and-retest "
              "(95%% CI %+.0f to %+.0f min)" % (med(a) - med(b), lo, hi))
        J["clock"][scope] = {"ocr_med": med(a), "br_med": med(b),
                             "diff": med(a) - med(b), "ci": [lo, hi],
                             "n_ocr": len(a), "n_br": len(b)}

# ------------------------------------------------- 2. how old is the level?
print()
print("=" * 88)
print("2. HOW OLD IS THE LEVEL THE SETUP TRADES, AT THE MOMENT IT TRADES IT?")
print("=" * 88)
# The OCR reason string carries the order block candle's own timestamp:
#   "Order block long - block $X-$Y (at HH:MM:SS), wick_only retest, ..."
OBT = re.compile(r"\(at (\d{2}):(\d{2}):\d{2}\)")
lag, blockborn = [], []
for r in rows:
    if r["setup"] != "one_candle_rule":
        continue
    m = OBT.search(r.get("reason") or "")
    if not m:
        continue
    b = (int(m.group(1)) - 9) * 60 + int(m.group(2)) - 30
    blockborn.append(b)
    lag.append(mins(r["et"]) - b)
print("  one-candle rule, %d rows whose reason names the order block candle:" % len(lag))
print("    the order block candle itself prints at    median %s (%.0f min into the session)"
      % ("9:%02d" % (30 + med(blockborn)) if med(blockborn) < 30
         else "%d:%02d" % (9 + (30 + med(blockborn)) // 60, (30 + med(blockborn)) % 60),
         med(blockborn)))
print("    the entry comes                            median %.0f bars later "
      "(25th-75th: %.0f-%.0f)"
      % (med(lag), sorted(lag)[len(lag) // 4], sorted(lag)[3 * len(lag) // 4]))
print("    share of entries within 10 bars of their own block: %.1f%%"
      % (100.0 * sum(1 for x in lag if x <= 10) / len(lag)))
J["ob_lag"] = {"n": len(lag), "block_born_med": med(blockborn),
               "block_to_entry_med": med(lag),
               "within10": 100.0 * sum(1 for x in lag if x <= 10) / len(lag)}

lvl = Counter()
for r in rows:
    if r["setup"] != "break_and_retest":
        continue
    lvl[r.get("level_name") or "?"] += 1
tot = sum(lvl.values())
PREBELL = {"PDH", "PDL", "PMH", "PML", "HOD", "LOD"}
pre = sum(v for k, v in lvl.items() if k in PREBELL)
print()
print("  break-and-retest, what level it trades (%d rows):" % tot)
for k, v in lvl.most_common(8):
    print("    %-32s %6d  %5.1f%%   %s"
          % (k, v, 100.0 * v / tot,
             "drawn before the bell" if k in PREBELL else
             "drawn in-session" if k.startswith(("not-his: pivot",)) else
             "drawn 9:35 (opening range)" if "OR " in k else ""))
print("  --> %.1f%% of break-and-retest levels already exist at 9:30. "
      "0%% of one-candle-rule blocks do." % (100.0 * pre / tot))
J["br_levels"] = {"total": tot, "prebell_share": 100.0 * pre / tot,
                  "by_level": dict(lvl.most_common())}

# --------------------------------------- 3. paired, inside the same session
print()
print("=" * 88)
print("3. THE SAME DAY, THE SAME SYMBOL -- is it the setup or is it the day?")
print("=" * 88)
first = defaultdict(dict)
for r in rows:
    k = (r["sym"], r["day"])
    s = r["setup"]
    t = mins(r["et"])
    if s in ARMS and (s not in first[k] or t < first[k][s]):
        first[k][s] = t
pairs = [(v["one_candle_rule"], v["break_and_retest"]) for v in first.values()
         if "one_candle_rule" in v and "break_and_retest" in v]
d = [a - b for a, b in pairs]
lo, hi = boot_diff([x for x in d], [0] * len(d))
print("  %d symbol-days where BOTH setups fire at some point." % len(pairs))
print("  On those days the FIRST one-candle-rule signal comes %+.0f min after the"
      " FIRST break-and-retest signal (median; 95%% CI %+.0f to %+.0f)."
      % (med(d), lo, hi))
print("  It is later on %.1f%% of them." % (100.0 * sum(1 for x in d if x > 0) / len(d)))
J["paired"] = {"n": len(pairs), "median_diff": med(d), "ci": [lo, hi],
               "share_later": 100.0 * sum(1 for x in d if x > 0) / len(d)}

# traded-only version
firstT = defaultdict(dict)
for r in rows:
    if not r["traded"]:
        continue
    k = (r["sym"], r["day"])
    s, t = r["setup"], mins(r["et"])
    if s in ARMS and (s not in firstT[k] or t < firstT[k][s]):
        firstT[k][s] = t
pT = [(v["one_candle_rule"], v["break_and_retest"]) for v in firstT.values()
      if "one_candle_rule" in v and "break_and_retest" in v]
if pT:
    dT = [a - b for a, b in pT]
    print("  Traded rows only: %d such days, median %+.0f min." % (len(pT), med(dT)))
    J["paired_traded"] = {"n": len(pT), "median_diff": med(dT)}

# --------------------------------------------- 4. the 9:30-10:00 half hour
print()
print("=" * 88)
print("4. THE FIRST HALF HOUR -- the window he actually trades in")
print("=" * 88)
print("  %-18s %8s %10s %10s %12s" % ("setup", "signals", "9:30-10:00",
                                      "10:00-11:00", "share early"))
for s in ARMS:
    v = [mins(r["et"]) for r in rows if r["setup"] == s]
    e = sum(1 for x in v if x < 30)
    print("  %-18s %8d %10d %10d %11.1f%%"
          % (NAME[s], len(v), e, len(v) - e, 100.0 * e / len(v)))
    J.setdefault("first_half_hour", {})[s] = {"n": len(v), "early": e,
                                              "share": 100.0 * e / len(v)}

json.dump(J, open(OUT, "w"), indent=1)
print()
print("wrote", OUT)
