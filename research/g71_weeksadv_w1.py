"""ADVERSARIAL VERIFY of the `weeks` track's W1 claim.

Independent re-implementation. Does NOT import g71_firsts_policy or read
_g71_weeks.json for any number it reports. Rebuilds the counted stream, the
sequential one-position-at-a-time walker, the week walker, ISO weeks and
McNemar from research/bt2y_trades.json alone.

Three questions:
  1. Do the W1 numbers reproduce?
  2. Is the P0-vs-W1 McNemar test informative, or is W1's green-week win
     guaranteed by construction (optional stopping)?
  3. Does W1 still "win significantly" on a book with the edge removed?
"""
import json, math, random, statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
book = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
meta, trades = book["meta"], book["trades"]
RISK = meta.get("risk_dollars", 1000.0)
print("BOOK", {k: meta[k] for k in ("generated", "sessions", "signals", "traded", "halted")})

counted = [r for r in trades if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
shipped = [r for r in trades if r["traded"]]
print("counted", len(counted), "shipped", len(shipped))

def ek(r): return (r["entry_i"], r["et"], r["sym"])
def xk(r): return (r["entry_i"] + r["bars"], r["et"], r["sym"])
def wkof(d):
    y, w, _ = date.fromisoformat(d).isocalendar()
    return "%04d-W%02d" % (y, w)

by_day = defaultdict(list)
for r in counted:
    by_day[r["day"]].append(r)
for d in by_day:
    by_day[d].sort(key=ek)
all_days = sorted(by_day)
all_weeks = sorted({wkof(d) for d in all_days})
all_months = sorted({d[:7] for d in all_days})
wk_days = defaultdict(list)
for d in all_days:
    wk_days[wkof(d)].append(d)

# ---------- walkers (own implementation) ----------
def seq_week(days, rmap, stop):
    """Walk a whole week sequentially. stop(cum_week, cum_day) -> True to stand
    down for the rest of the WEEK. Returns list of taken rows."""
    taken = []
    cum = 0.0
    for d in days:
        free = None
        today = 0.0
        for c in by_day[d]:
            if stop(cum, today):
                return taken
            if free is not None and ek(c) < free:
                continue
            taken.append(c)
            free = xk(c)
            cum += rmap[id(c)]
            today += rmap[id(c)]
    return taken

def week_r(taken, rmap):
    w = defaultdict(float)
    for r in taken:
        w[wkof(r["day"])] += rmap[id(r)]
    return [w.get(x, 0.0) for x in all_weeks]

def greens(series): return [1 if v > 0 else 0 for v in series]

def mcnemar(ga, gb):
    b01 = sum(1 for x, y in zip(ga, gb) if x == 0 and y == 1)
    b10 = sum(1 for x, y in zip(ga, gb) if x == 1 and y == 0)
    n = b01 + b10
    if n == 0:
        return b10, b01, 1.0
    k = min(b01, b10)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return b10, b01, min(1.0, p)

RM = {id(r): r["r"] for r in counted}

def arm(name, stop, rmap=RM):
    taken = []
    for w in all_weeks:
        taken += seq_week(wk_days[w], rmap, stop)
    s = week_r(taken, rmap)
    mo = defaultdict(float)
    for r in taken:
        mo[r["day"][:7]] += rmap[id(r)]
    med = statistics.median(s)
    return {"name": name, "n": len(taken), "series": s, "green": sum(greens(s)),
            "total": sum(rmap[id(r)] for r in taken),
            "worst": min(s), "worst_wk": all_weeks[s.index(min(s))],
            "med": med, "recov": abs(min(s)) / med if med > 0 else None,
            "usd_wk": statistics.fmean(s) * RISK,
            "months": sum(1 for m in all_months if mo.get(m, 0.0) > 0)}

NEVER = lambda c, t: False
W1 = lambda c, t: c > 0
P0seq = arm("P0seq", NEVER)
w1 = arm("W1", W1)
w28 = arm("W2-8", lambda c, t: c > 0 or c <= -8.0)
w25 = arm("W2-5", lambda c, t: c > 0 or c <= -5.0)
w23 = arm("W2-3", lambda c, t: c > 0 or c <= -3.0)

# P0 shipped: concurrent, R31 on -- no walker, just sum the traded rows
p0w = defaultdict(float); p0mo = defaultdict(float)
for r in shipped:
    p0w[wkof(r["day"])] += r["r"]; p0mo[r["day"][:7]] += r["r"]
p0s = [p0w.get(x, 0.0) for x in all_weeks]
P0 = {"name": "P0 shipped", "n": len(shipped), "series": p0s, "green": sum(greens(p0s)),
      "total": sum(r["r"] for r in shipped), "worst": min(p0s),
      "worst_wk": all_weeks[p0s.index(min(p0s))], "med": statistics.median(p0s),
      "recov": abs(min(p0s)) / statistics.median(p0s),
      "usd_wk": statistics.fmean(p0s) * RISK,
      "months": sum(1 for m in all_months if p0mo.get(m, 0.0) > 0)}

print("\n%-8s %5s %8s %9s %8s %8s %7s %7s %8s %6s" %
      ("arm", "n", "t/wk", "green", "totalR", "worstR", "medR", "recov", "$/wk", "mo"))
for a in (P0, P0seq, w1, w28, w25, w23):
    print("%-8s %5d %8.2f %4d/%-4d %8.2f %8.2f %7.2f %7.2f %8.0f %3d/%d"
          % (a["name"], a["n"], a["n"] / 105, a["green"], len(all_weeks), a["total"],
             a["worst"], a["med"], a["recov"] or -1, a["usd_wk"], a["months"], len(all_months)))
print("worst weeks:", {a["name"]: (a["worst_wk"], round(a["worst"], 2)) for a in (P0, P0seq, w1)})

# ---------- 2. is the win guaranteed by construction? ----------
gp0, gseq, gw1 = greens(P0["series"]), greens(P0seq["series"]), greens(w1["series"])
viol = [all_weeks[i] for i in range(105) if gseq[i] == 1 and gw1[i] == 0]
print("\nNESTING: weeks P0seq green but W1 not green:", len(viol), viol)
# W1 green  <=>  the P0seq week path ever goes above 0
ever = 0
for w in all_weeks:
    cum = 0.0; hit = False
    for d in wk_days[w]:
        free = None
        for c in by_day[d]:
            if free is not None and ek(c) < free: continue
            free = xk(c); cum += RM[id(c)]
            if cum > 0: hit = True; break
        if hit: break
    ever += hit
print("weeks whose P0seq running path EVER goes >0:", ever, " W1 green:", w1["green"])

for lbl, a, b in (("P0 vs W1", gp0, gw1), ("P0seq vs W1", gseq, gw1),
                  ("P0seq vs W2-8", gseq, greens(w28["series"])),
                  ("P0seq vs W2-5", gseq, greens(w25["series"])),
                  ("P0 vs P0seq", gp0, gseq)):
    x = mcnemar(a, b)
    print("McNemar %-14s a_only=%2d b_only=%2d p=%.5f" % (lbl, x[0], x[1], x[2]))

# ---------- 3. the null test: same schedule, edge removed ----------
rs = [r["r"] for r in counted]
mu = statistics.fmean(rs)
print("\nper-trade mean R (counted stream) = %.4f  sd = %.4f  n=%d" % (mu, statistics.pstdev(rs), len(rs)))
rng = random.Random(20260829)
res = []
DR = 500
for _ in range(DR):
    # demeaned bootstrap: identical shape and schedule, ZERO edge
    rmap = {id(r): rng.choice(rs) - mu for r in counted}
    a = arm("seq", NEVER, rmap); b = arm("w1", W1, rmap)
    x = mcnemar(greens(a["series"]), greens(b["series"]))
    res.append((a["green"], b["green"], x[0], x[1], x[2], a["total"], b["total"]))
gs = sorted(r[0] for r in res); gw = sorted(r[1] for r in res)
ps = sorted(r[4] for r in res)
print("ZERO-EDGE BOOK, %d draws:" % DR)
print("  P0seq green weeks : median %d  [p05 %d, p95 %d]" % (gs[DR//2], gs[int(.05*DR)], gs[int(.95*DR)]))
print("  W1    green weeks : median %d  [p05 %d, p95 %d]" % (gw[DR//2], gw[int(.05*DR)], gw[int(.95*DR)]))
print("  McNemar p (P0seq vs W1): median %.5f   share p<0.05 = %.3f   share p<0.01 = %.3f"
      % (ps[DR//2], sum(1 for p in ps if p < .05)/DR, sum(1 for p in ps if p < .01)/DR))
print("  a_only (P0seq wins) max over all draws:", max(r[2] for r in res))
print("  total R  P0seq median %.2f   W1 median %.2f"
      % (sorted(r[5] for r in res)[DR//2], sorted(r[6] for r in res)[DR//2]))
