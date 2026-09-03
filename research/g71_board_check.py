"""G7.1 board -- independent re-derivation of the ONE headline dollar number.

Does not import g71_firsts_policy or g71_rtarget_model. Rebuilds the candidate
stream and the causal one-position-at-a-time walk from scratch, then prices
"first signal of the day, one trade, done" two ways:

  LIVE   -- every winner clipped at +2.0R, because options_sizer.DEFAULT_RR = 2.0
            is the live path's only exit and paper_trader closes the WHOLE
            position there (research/g71_rrcap.md, verified).
  BOOK   -- the backtest's shipped ladder exit (50% at the session extreme,
            runner to the next level), i.e. the R the book actually booked.

1R = $1,000 (CLAUDE.md). Monthly = 21 trading days.
"""
import json, statistics as st

B = json.load(open("research/bt2y_trades.json"))
meta = B["meta"]
rows = B["trades"]

# candidate stream: what a human COULD have taken = fired-and-traded plus the
# rows R31's account-wide halt blocked (they carry every measured field).
cand = [r for r in rows if (r["status"] == "fired" and r.get("traded"))
        or r["status"] == "halted"]

def ekey(r):   # entry moment
    return (r["day"], r["et"], r["sym"])
def xkey(r):   # exit moment -- entry bar + bars held, same clock
    h, m = r["et"].split(":")
    tot = int(h) * 60 + int(m) + int(r.get("bars", 0))
    return (r["day"], "%02d:%02d" % (tot // 60, tot % 60), r["sym"])

byday = {}
for r in cand:
    byday.setdefault(r["day"], []).append(r)

def walk(clip=None):
    """One trade a day: take the FIRST candidate of the day, then stop."""
    out = []
    for day in sorted(byday):
        c = sorted(byday[day], key=ekey)[0]
        r = c["r"]
        if clip is not None and r > clip:
            r = clip
        out.append(r)
    return out

for label, clip in (("BOOK exit (scale + runner)", None),
                    ("LIVE exit (whole position out at 2R)", 2.0)):
    rs = walk(clip)
    n = len(rs)
    tot = sum(rs)
    mean = tot / n
    wr = sum(1 for x in rs if x > 0) / n * 100
    print("%-38s n=%d  win %.2f%%  meanR %+0.4f  totalR %+0.1f  "
          "$/day %s  $/month(21d) %s"
          % (label, n, wr, mean, tot,
             "${:,.0f}".format(mean * 1000),
             "${:,.0f}".format(mean * 1000 * 21)))

rs_book = walk(None)
above = [x for x in rs_book if x > 2.0]
excess = sum(x - 2.0 for x in above)
print()
print("trades that ran past 2R: %d of %d = %.2f%%" % (len(above), len(rs_book),
                                                      100 * len(above) / len(rs_book)))
print("R booked ABOVE the 2R line: %+0.2f of %+0.2f total = %.1f%% of all profit"
      % (excess, sum(rs_book), 100 * excess / sum(rs_book)))
print()
print("book:", meta["generated"], meta["sessions"], "sessions,",
      meta["signals"], "signals,", meta["traded"], "traded, 1R = $%.0f" % meta["risk_dollars"])
