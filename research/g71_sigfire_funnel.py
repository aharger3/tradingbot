"""G71/sigfire — the signal-to-trade funnel, counted on the shipped 2-year book.

Counts every stage `research/bt2y_trades.json` can see. A book ROW is a routed
candidate that ALSO survived backtest_week.py:830's R16 dedupe -- the book is
post-dedupe, so 76,019 rows come from 137,587 routed candidates. Every stage
above that (bar scans, raw `_emit` candidates, the two pre-route vetoes, the
dedupe itself) is counted by g71_sigfire_upstream.py, which instruments the
same engine and reproduces this book exactly.

Usage: python research/g71_sigfire_funnel.py [book.json]
"""
import json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
book = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "research" / "bt2y_trades.json"
d = json.loads(book.read_text())
meta, rows = d["meta"], d["trades"]

print("book      : %s" % book.name)
print("meta      : %s" % {k: v for k, v in meta.items() if k != "symbols"})
print("sessions  : %d   symbols: %d" % (meta["sessions"], len(meta["symbols"])))
print()

n = len(rows)
print("STAGE COUNTS (a book row = routed candidate that survived R16 dedupe)")
print("  book rows (reported as `signals`)  %7d  100.00%%" % n)

st = Counter(r["status"] for r in rows)
for k, v in st.most_common():
    print("    status=%-24s %7d  %6.2f%%" % (k, v, 100.0 * v / n))
print()

# loss_halt.apply_to_book overwrites status "fired" -> "halted" IN PLACE
# (loss_halt.py:110), so every pre-halt count has to read both.
fired = [r for r in rows if r["status"] in ("fired", "halted")]
wanted = [r for r in fired if r["grade"] != "C"]
print("  PRE-HALT fired (accepted by _route)%7d  %6.2f%%" % (len(fired), 100.0 * len(fired) / n))
print("  PRE-HALT wanted (fired, grade!=C)  %7d  %6.2f%%   <-- 'the engine wanted to trade this'"
      % (len(wanted), 100.0 * len(wanted) / n))
print("  post-halt fired                    %7d" % sum(1 for r in rows if r["status"] == "fired"))
gr = Counter(r["grade"] for r in rows)
print("  engine grade over ALL routed rows: %s" % dict(gr.most_common()))
grf = Counter(r["grade"] for r in fired)
print("  engine grade over FIRED rows:      %s" % dict(grf.most_common()))
print()

traded = [r for r in rows if r["traded"]]
alert = [r for r in rows if r["alert"]]
print("  TRADE  (fired and grade != C)      %7d  %6.2f%%" % (len(traded), 100.0 * len(traded) / n))
print("  ALERT  (fired and grade == C)      %7d  %6.2f%%" % (len(alert), 100.0 * len(alert) / n))
print()

# the live gate: live_scanner._tier promotes only grade == "A+"
aplus = [r for r in traded if r["grade"] == "A+"]
a_or_better = [r for r in traded if r["grade"] in ("A+", "A")]
print("LIVE GATE (live_scanner._tier: TRADE iff grade == 'A+')")
print("  traded rows graded A+              %7d" % len(aplus))
print("  traded rows graded A+ or A         %7d" % len(a_or_better))
print()

print("AUSTIN'S LADDER (research/downgrade.py, measured only)")
sg = Counter(r["sgrade"] for r in rows)
print("  over ALL routed rows:   %s" % dict(sg.most_common()))
sgt = Counter(r["sgrade"] for r in traded)
print("  over TRADED rows:       %s" % dict(sgt.most_common()))
print()

print("PER-SESSION / PER-SYMBOL-DAY DENSITY")
days = {r["day"] for r in rows}
symdays = {(r["sym"], r["day"]) for r in rows}
print("  distinct sessions with >=1 routed  %7d" % len(days))
print("  distinct symbol-days with >=1      %7d" % len(symdays))
print("  routed per session                 %10.1f" % (n / max(1, len(days))))
print("  routed per symbol-day              %10.1f" % (n / max(1, len(symdays))))
tdays = {r["day"] for r in traded}
print("  sessions with >=1 TRADE            %7d" % len(tdays))
print("  TRADEs per trading session         %10.2f" % (len(traded) / max(1, len(tdays))))
print()

# how much of the pool is the SAME idea re-detected on later bars
print("DUPLICATION INSIDE THE ROUTED POOL")
idea = Counter((r["sym"], r["day"], r["setup"], r["dir"], r["level"]) for r in rows)
print("  distinct (sym,day,setup,dir,level) %7d" % len(idea))
print("  mean routed rows per distinct idea %10.2f" % (n / max(1, len(idea))))
print("  ideas with >1 routed row           %7d" % sum(1 for v in idea.values() if v > 1))
print("  largest single idea                %7d rows" % max(idea.values()))
print()

print("X ROWS -- 'the engine should not have fired'")
x = [r for r in rows if r["grade"] == "X"]
print("  grade X rows                       %7d  %6.2f%%" % (len(x), 100.0 * len(x) / n))
print("  of which status                    %s" % dict(Counter(r["status"] for r in x).most_common()))
