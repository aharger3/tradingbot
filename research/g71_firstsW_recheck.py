"""G7.1 / adversarial verify of track `firsts`.

Re-derives, from research/bt2y_trades.json alone and with an independent
implementation (minute arithmetic, not tuple keys), the three things the
`firsts` claim rests on:

  1. months green for P0 / P0seq / P1..P4 and the red-month list,
  2. 2025-09 under every arm,
  3. the shipped book's concurrency -- mean-of-daily-MAX (what the JSON key
     actually holds) vs a genuine time-weighted average.

Also probes robustness: month margins, and whether the 22/23-of-25 verdict
survives a stricter and a looser causality rule.
"""
import json, statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
T = B["trades"]
print("book meta:", {k: B["meta"][k] for k in ("generated", "sessions", "signals", "traded", "halted", "loss_halt")})

shipped = [r for r in T if r["traded"]]
counted = [r for r in T if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
print("shipped=%d counted=%d fired=%d halted=%d alert_only=%d"
      % (len(shipped), len(counted),
         sum(1 for r in T if r["status"] == "fired"),
         sum(1 for r in T if r["status"] == "halted"),
         sum(1 for r in T if r["status"] == "fired" and not r["traded"])))

byday = defaultdict(list)
for r in counted:
    byday[r["day"]].append(r)
for d in byday:
    byday[d].sort(key=lambda r: (r["entry_i"], r["sym"]))
days = sorted(byday)
months = sorted({d[:7] for d in days})
print("days=%d months=%d" % (len(days), len(months)))

def walk(rows, stop, gap=0):
    """stop(n,w,l,cum)->True halts BEFORE the next entry. One position at a
    time: next entry_i must be >= previous exit minute + gap."""
    out, free, w, l, cum = [], None, 0, 0, 0.0
    for c in rows:
        if stop(len(out), w, l, cum):
            break
        if free is not None and c["entry_i"] < free + gap:
            continue
        out.append(c)
        free = c["entry_i"] + c["bars"]
        if c["out"] == "win": w += 1
        elif c["out"] == "loss": l += 1
        cum += c["r"]
    return out

POL = {
    "P0seq": lambda n, w, l, c: False,
    "P1":    lambda n, w, l, c: n >= 1,
    "P2":    lambda n, w, l, c: w >= 1 or l >= 2,
    "P3":    lambda n, w, l, c: c > 0,
    "P4":    lambda n, w, l, c: c > 0 or l >= 3,
}

def monthly(dayr):
    m = defaultdict(float)
    for d, v in dayr.items():
        m[d[:7]] += v
    return {k: round(m.get(k, 0.0), 4) for k in months}

def summarize(name, taken_by_day):
    rows = [r for d in taken_by_day for r in taken_by_day[d]]
    dayr = {d: sum(r["r"] for r in rs) for d, rs in taken_by_day.items() if rs}
    mm = monthly(dayr)
    red = {k: v for k, v in mm.items() if v <= 0}
    w = sum(1 for r in rows if r["out"] == "win")
    l = sum(1 for r in rows if r["out"] == "loss")
    print("%-7s n=%-5d WR=%5.2f%% R/tr=%+.4f totR=%+8.1f green=%2d/%d red=%s"
          % (name, len(rows), 100*w/max(1, w+l), sum(r["r"] for r in rows)/max(1, len(rows)),
             sum(r["r"] for r in rows), sum(1 for k in months if mm[k] > 0), len(months),
             ", ".join("%s %+.1f" % (k, v) for k, v in sorted(red.items())) or "none"))
    return mm

res = {}
sh = defaultdict(list)
for r in shipped: sh[r["day"]].append(r)
res["P0"] = summarize("P0", sh)
res["P0u"] = summarize("P0u", byday)
for k, f in POL.items():
    res[k] = summarize(k, {d: walk(byday[d], f) for d in days})

# ---- 2025-09 under every arm
print("\n2025-09 by arm:", {k: v["2025-09"] for k, v in res.items()})
print("2025-05 by arm:", {k: v["2025-05"] for k, v in res.items()})

# oracle (look-ahead) -- also one trade/day, i.e. zero concurrency
orc = {d: [max(byday[d], key=lambda r: r["r"])] for d in days}
res["ORACLE"] = summarize("ORACLE", orc)

# ---- causality sensitivity: force a 1-minute gap, and a same-bar-allowed rule
for gap, lab in ((1, "gap=+1min"), (-99999, "overlap allowed")):
    line = []
    for k in ("P1", "P2", "P3", "P4"):
        mm = monthly({d: sum(r["r"] for r in walk(byday[d], POL[k], gap)) for d in days})
        line.append("%s %d/25" % (k, sum(1 for m in months if mm[m] > 0)))
    print("%-16s %s" % (lab, "  ".join(line)))

# ---- concurrency, done two ways
def conc_curve(rows):
    ev = sorted([(r["entry_i"], 1) for r in rows] + [(r["entry_i"] + r["bars"], -1) for r in rows])
    cur = mx = 0
    area = 0.0
    prev = ev[0][0]
    for t, v in ev:
        area += cur * (t - prev)
        prev = t
        cur += v
        mx = max(mx, cur)
    span = ev[-1][0] - ev[0][0]
    return mx, area, span

mx_list, area_tot, span_tot, minutes_tot = [], 0.0, 0, 0
for d, rs in sh.items():
    mx, area, span = conc_curve(rs)
    mx_list.append(mx)
    area_tot += area
    span_tot += span
    minutes_tot += 391  # 09:30-16:00 RTH minutes
print("\nP0 concurrency: days_with_trades=%d  mean(daily MAX)=%.2f  max=%d  days_max>=2=%d  days_max>=4=%d"
      % (len(mx_list), st.fmean(mx_list), max(mx_list),
         sum(1 for c in mx_list if c >= 2), sum(1 for c in mx_list if c >= 4)))
print("P0 TIME-WEIGHTED avg concurrent positions: over open-span=%.3f  over 391-min RTH day=%.3f"
      % (area_tot / span_tot, area_tot / (len(mx_list) * 391)))
print("P0 total position-minutes=%d over %d traded days" % (area_tot, len(mx_list)))

# how much of the shipped book is unreachable one-at-a-time
seqrows = sum(len(walk(byday[d], POL["P0seq"])) for d in days)
print("counted=%d  reachable one-at-a-time=%d (%.1f%%)" % (len(counted), seqrows, 100*seqrows/len(counted)))

# ---- margin of the durability verdict: how close are the green months to 0?
for k in ("P0", "P1", "P2", "P3", "P4"):
    v = sorted(res[k].items(), key=lambda kv: kv[1])[:4]
    print("%-6s 4 weakest months: %s" % (k, ", ".join("%s %+.1f" % (a, b) for a, b in v)))
