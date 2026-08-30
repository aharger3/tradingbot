"""Adversarial recompute of research/g82_stop_ab.py's headline numbers.

Independent arithmetic: does NOT import g72_suppress_price. Reads the six replay
books in research/_g82_books/ and recomputes, from scratch:
  * dollars per session for every arm (all-trades and one-a-day)
  * the paired-by-session difference vs shipped, with a fresh bootstrap CI
  * the per-trade R delta against the standing +/-1.5799R bar
  * the touch vs touch_floor byte-identity claim
  * whether the "shipped" arm reproduces the committed book (bt2y_trades.json)
1R = $1,000.
"""
import json, hashlib, random, sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "research" / "_g82_books"
RISK = 1000.0
BAR = 1.5799

def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return b["meta"], b["trades"]

def traded(rows):
    return sorted([r for r in rows if r.get("traded")], key=lambda r: (r["day"], r["et"], r["sym"]))

def oneaday(rows):
    byday = {}
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday.setdefault(r["day"], []).append(r)
    return [sorted(v, key=lambda r: (r["day"], r["et"], r["sym"]))[0] for _, v in sorted(byday.items())]

def dd(pnls):
    cum = peak = worst = 0.0
    for p in pnls:
        cum += p; peak = max(peak, cum); worst = max(worst, peak - cum)
    return worst

def summ(rows, n_days):
    pn = [r["pnl"] for r in rows]
    w = sum(1 for x in pn if x > 0); l = sum(1 for x in pn if x < 0)
    bym = {}
    for r in rows: bym[r["day"][:7]] = bym.get(r["day"][:7], 0.0) + r["pnl"]
    return dict(trades=len(rows), total=sum(pn), per_day=sum(pn)/n_days,
                per_trade=sum(pn)/len(pn), mean_r=sum(pn)/len(pn)/RISK,
                win=100.0*w/(w+l), dd=dd(pn),
                months_green=sum(1 for v in bym.values() if v > 0), months=len(bym),
                worst_r=min(pn)/RISK, n_past_floor=sum(1 for x in pn if x/RISK < -1.2500001))

def boot(diff, n=10000, seed=99991):
    rnd = random.Random(seed); k = len(diff); m = []
    for _ in range(n):
        m.append(sum(diff[rnd.randrange(k)] for _ in range(k))/k)
    m.sort()
    return sum(diff)/k, m[int(.025*n)], m[int(.975*n)]

def bydayd(rows):
    d = {}
    for r in rows: d[r["day"]] = d.get(r["day"], 0.0) + r["pnl"]
    return d

ARMS = ["shipped","close_floor","close_nofloor","touch","touch_floor","target_close"]
books, metas = {}, {}
for a in ARMS:
    p = BOOKS / ("g82_%s.json" % a)
    if not p.exists():
        print("MISSING", p); continue
    metas[a], books[a] = load(p)

print("=== arm summary (recomputed independently) ===")
for a in ARMS:
    if a not in books: continue
    nd = metas[a]["sessions"]
    s = summ(traded(books[a]), nd); o = summ(oneaday(books[a]), nd)
    print("%-14s sessions=%d  all: $%.0f/day n=%d meanR=%.4f win=%.1f%% dd=$%.0f mg=%d/%d worst=%.4fR past_floor=%d | 1aday: $%.0f/day mg=%d/%d"
          % (a, nd, s["per_day"], s["trades"], s["mean_r"], s["win"], s["dd"],
             s["months_green"], s["months"], s["worst_r"], s["n_past_floor"],
             o["per_day"], o["months_green"], o["months"]))

print()
print("=== paired-by-session vs shipped, fresh bootstrap (seed differs from theirs) ===")
base = books["shipped"]
for a in ARMS[1:]:
    if a not in books: continue
    for lbl, fn in (("all", traded), ("one_a_day", oneaday)):
        da, db = bydayd(fn(base)), bydayd(fn(books[a]))
        days = sorted(set(da) | set(db))
        diff = [db.get(d,0.0)-da.get(d,0.0) for d in days]
        m, lo, hi = boot(diff)
        print("  %-14s %-9s mean $%+.0f  CI [$%+.0f, $%+.0f]  %s"
              % (a, lbl, m, lo, hi, "TIE(straddles 0)" if lo <= 0 <= hi else "moves"))

print()
print("=== per-trade R delta vs the standing +/-%.4fR bar ===" % BAR)
bs = summ(traded(base), metas["shipped"]["sessions"])
for a in ARMS[1:]:
    if a not in books: continue
    cs = summ(traded(books[a]), metas[a]["sessions"])
    d = cs["mean_r"] - bs["mean_r"]
    print("  %-14s %+.4fR/trade  %s" % (a, d, "BEATS BAR" if abs(d) >= BAR else "TIE"))

print()
print("=== touch vs touch_floor identity ===")
def sig(rows):
    t = traded(rows)
    h = hashlib.md5()
    for r in t:
        h.update(("%s|%s|%s|%.6f|%.6f\n" % (r["sym"], r["day"], r["et"],
                  r.get("exit", r.get("exit_price", 0.0)), r["pnl"]/RISK)).encode())
    return len(t), h.hexdigest()
for a in ("touch","touch_floor"):
    if a in books: print("  %-12s %s" % (a, sig(books[a])))

print()
print("=== is the 'shipped' arm the COMMITTED book? ===")
bt = ROOT / "research" / "bt2y_trades.json"
if bt.exists():
    bm, br = load(bt)
    c = summ(traded(br), bm["sessions"])
    print("  bt2y_trades.json : sessions=%d traded=%d $%.0f/day meanR=%.4f worst=%.4fR generated=%s"
          % (bm["sessions"], c["trades"], c["per_day"], c["mean_r"], c["worst_r"], bm.get("generated")))
    print("  g82_shipped.json : sessions=%d traded=%d $%.0f/day meanR=%.4f worst=%.4fR generated=%s"
          % (metas["shipped"]["sessions"], bs["trades"], bs["per_day"], bs["mean_r"],
             bs["worst_r"], metas["shipped"].get("generated")))
    losses = [r["pnl"]/RISK for r in traded(br) if r["pnl"] < 0]
    print("  committed book losses: n=%d  worse than -1.000R: %d  exactly -1.0000R: %d"
          % (len(losses), sum(1 for x in losses if x < -1.0000001),
             sum(1 for x in losses if abs(x+1.0) < 1e-6)))
else:
    print("  bt2y_trades.json missing")

# --------------------------------------------------------------------------
# ADVERSARIAL EXTRA 1: paired by TRADE, not by session.
# close_floor's win is claimed to be part "better trades", part "more trades".
# Take only the trades that exist in BOTH books (same sym/day/entry-time/entry)
# and ask whether the stop rule alone moved them.
# --------------------------------------------------------------------------
def idk(r):
    return (r["sym"], r["day"], r["et"], round(r["entry"], 2), round(r["stop"], 2), r["dir"])

print()
print("=== ADVERSARIAL: paired by TRADE (common entries only) ===")
bs_rows = {idk(r): r for r in traded(books["shipped"])}
for a in ARMS[1:]:
    if a not in books: continue
    ar = {idk(r): r for r in traded(books[a])}
    common = sorted(set(bs_rows) & set(ar))
    d = [ar[k]["pnl"] - bs_rows[k]["pnl"] for k in common]
    if not d: continue
    m, lo, hi = boot(d)
    print("  %-14s n_common=%d (%d shipped-only, %d arm-only)  mean $%+.1f/trade = %+.4fR  CI [$%+.1f, $%+.1f]  %s"
          % (a, len(common), len(bs_rows)-len(common), len(ar)-len(common),
             m, m/RISK, lo, hi, "TIE" if lo <= 0 <= hi else "moves"))

# --------------------------------------------------------------------------
# ADVERSARIAL EXTRA 2: halt counts, and where the extra trades live.
# --------------------------------------------------------------------------
print()
print("=== halts / signal counts per arm (from book meta) ===")
for a in ARMS:
    if a not in books: continue
    m = metas[a]
    print("  %-14s signals=%s traded=%s halted=%s" % (a, m.get("signals"), m.get("traded"), m.get("halted")))
