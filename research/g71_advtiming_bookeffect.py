"""Book-level accounting of the nearest-candidate swap.

For the 60 rows whose 'earlier candidate' is a trade the book ALREADY holds,
a swap does not add a trade -- it DELETES the later row, because the earlier one
is already booked. Prices that, against the report's +6.8R."""
import json, os, statistics, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import g71_timing as G
from signal_runner import min_risk_floor
from backtest_week import RISK_DOLLARS

book = json.load(open(G.BOOK, encoding="utf-8"))
rows = [r for r in book["trades"] if r["status"] == "fired" and r["traded"]]
G.load_or_build_index(rows)
support = []
for n, row in enumerate(rows):
    src = G.match(n)
    if src is None: continue
    ctx = G.day_ctx(row["sym"], row["day"])
    if ctx is None: continue
    L = len(ctx[0]); i0 = src.entry_idx
    if all(5 <= i0 + k < L - 1 for k in (-2,-1,0,1,2)) and i0 < L: support.append(n)
fp = {(r["sym"], r["day"], r["entry_i"], r["dir"]) for r in rows}
add, drop = [], []
for n in support:
    keep = [c for c in G._CANDS.get(n, [])
            if c["status"] != "skipped_tight_stop"
            and abs(c["entry"] - c["stop"]) >= min_risk_floor(c["entry"])]
    if not keep: continue
    c = keep[0]; row = rows[n]
    ctx = G.day_ctx(row["sym"], row["day"])
    t = G.build(G._Src(c), ctx[0], ctx[1], ctx[2], ctx[3], ctx[4], 0, "T")
    if t is None: continue
    G.manage(t, ctx[0], G._StubRunner(ctx[0]))
    if (c["symbol"], c["day"], c["entry_idx"], c["direction"]) in fp:
        drop.append(row["r"])                    # earlier trade already booked
    else:
        add.append(t.pnl / RISK_DOLLARS - row["r"])
tot_book = sum(r["r"] for r in rows)
delta = sum(add) - sum(drop)
n_after = len(rows) - len(drop)
print("book: n=%d totR %+.1f meanR %+.4f" % (len(rows), tot_book, tot_book / len(rows)))
print("swap rows: %d replaced (delta %+.1fR), %d DELETED (their booked R %+.1fR is lost)"
      % (len(add), sum(add), len(drop), sum(drop)))
print("report's headline total: +6.8R  |  honest book-level total: %+.1fR" % delta)
print("book after swap: n=%d totR %+.1f meanR %+.4f (was %+.4f, delta %+.4f)"
      % (n_after, tot_book + delta, (tot_book + delta) / n_after,
         tot_book / len(rows), (tot_book + delta) / n_after - tot_book / len(rows)))
