"""g81_verify_0.py -- independent recompute of the two largest g81 numbers.

Written from the source data, not from g81_htf_thesis.py. Recomputes:
  1. STEP 1's prize: first setup of the day vs best setup of the day, and the
     gap between them ($3,458/day claimed).
  2. STEP 5's denominator: how many of Austin's 20 stated entry minutes had ANY
     earlier engine signal on the same chart (10 of 20 claimed).

Also audits, on its own terms:
  * the divisor used for $/day (meta sessions vs days actually holding
    candidates),
  * the trip rate of every gate the thesis introduces,
  * whether any daily/weekly/index window can see the bar it is judging,
  * whether the mark file was opened read-only (it is: 'r' mode only).

Read-only. Applies nothing.
"""
import json, os, re, statistics, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(HERE, "bt2y_trades.json")
MARKS = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")
CACHE = os.path.join(HERE, "g81_htf_cache.json")
RISK = 1000.0

b = json.load(open(BOOK, encoding="utf-8"))
meta, rows = b["meta"], b["trades"]

# ---- 1. the prize -----------------------------------------------------------
byday = defaultdict(list)
for r in rows:
    if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
        byday[r["day"]].append(r)
for v in byday.values():
    v.sort(key=lambda r: (r["day"], r["et"], r["sym"]))

n_meta = meta["sessions"]
n_have = len(byday)
tot_c = sum(len(v) for v in byday.values())
print("candidates %d over %d days; meta sessions = %d" % (tot_c, n_have, n_meta))
print("median candidates/day %.1f" % statistics.median(len(v) for v in byday.values()))

first = [v[0] for v in byday.values()]
best  = [max(v, key=lambda r: r["r"]) for v in byday.values()]
worst = [min(v, key=lambda r: r["r"]) for v in byday.values()]
coin  = statistics.fmean  # per-day mean

def line(tag, sel, div):
    tot = sum(r["pnl"] for r in sel)
    w = sum(1 for r in sel if r["pnl"] > 0); l = sum(1 for r in sel if r["pnl"] < 0)
    print("  %-7s $%6.0f/day  meanR %+0.3f  win %4.1f%%  (n=%d, div=%d)"
          % (tag, tot/div, tot/len(sel)/RISK, 100*w/(w+l), len(sel), div))
    return tot/div

for div in (n_meta, n_have):
    print(" divisor = %d" % div)
    f = line("first", first, div); bs = line("best", best, div); line("worst", worst, div)
    cf = sum(statistics.fmean(r["pnl"] for r in v) for v in byday.values())/div
    print("  coinflip $%.0f/day   GAP first->best $%.0f/day   arrival edge $%.0f/day"
          % (cf, bs - f, f - cf))

hit = sum(1 for v in byday.values() if v[0]["r"] >= max(r["r"] for r in v))
chance = statistics.fmean(1/len(v) for v in byday.values())
print("first IS best on %d of %d (%.1f%%); chance %.1f%%"
      % (hit, n_have, 100*hit/n_have, 100*chance))

# ---- 2. the twenty stated minutes -------------------------------------------
TIME = re.compile(r"\b(\d{1,2})[:%](\d{2})\b")
said = {}
for ln in open(MARKS, encoding="utf-8"):            # read-only
    ln = ln.strip()
    if not ln: continue
    row = json.loads(ln)
    if (row.get("answers", {}).get("is_s") or [None])[0] != "yes":
        continue
    note = " ".join(str(x) for x in (row.get("notes") or {}).values())
    m = TIME.search(note)
    if not m: continue
    said[row["card_id"]] = "%02d:%02d" % (int(m.group(1)), int(m.group(2)))
print("\nstated minutes: %d" % len(said))
print("  before 09:45: %d (%.0f%%)" % (sum(1 for v in said.values() if v < "09:45"),
                                       100*sum(1 for v in said.values() if v < "09:45")/len(said)))
print("  median %s ; after 10:00: %d"
      % (sorted(said.values())[len(said)//2 - 1],
         sum(1 for v in said.values() if v > "10:00")))

# every signal the engine emitted, at three widths of "signal"
DEFS = {"all rows (incl. skipped_d)": lambda r: True,
        "not skipped_d": lambda r: r["status"] != "skipped_d",
        "fired or halted": lambda r: r["status"] in ("fired", "halted")}
for tag, keep in DEFS.items():
    bysd = defaultdict(list)
    for r in rows:
        if keep(r): bysd["%s_%s" % (r["sym"], r["day"])].append(r)
    n = sum(1 for cid, mi in said.items()
            if any(r["et"] < mi for r in bysd.get(cid, [])))
    print("  earlier engine signal exists (%-26s): %d of %d" % (tag, n, len(said)))

# ---- 3. trip rates of every gate the thesis introduces ----------------------
if os.path.exists(CACHE):
    blob = json.load(open(CACHE, encoding="utf-8"))
    def ddir(p, db): return "bull" if p > db else ("bear" if p < -db else "flat")
    def daily_w(sym, day):
        cl = blob["daily"].get(sym) or {}
        ks = sorted(k for k in cl if k < day)
        if len(ks) < 21: return "flat", "flat"
        prev = cl[ks[-1]]; sma = statistics.fmean(cl[k] for k in ks[-20:])
        wk = cl[ks[-6]]
        return (ddir((prev-sma)/sma*100, 0.1), ddir((prev-wk)/wk*100, 0.1))
    def idx(day, et, db=0.05):
        p = blob["index"].get(day)
        if not p: return "flat"
        tot = int(et[:2])*60+int(et[3:5])-1
        best_ = None
        for k, vv in p.items():
            t = int(k[:2])*60+int(k[3:5])
            if t <= tot and (best_ is None or t > best_[0]): best_ = (t, vv)
        return "flat" if best_ is None else ddir(best_[1], db)
    HM = {"bullish":"bull","bearish":"bear","neutral":"flat","none":"flat"}
    trips = defaultdict(Counter); stack = Counter()
    for v in byday.values():
        for r in v:
            w = "bull" if r["dir"] == "call" else "bear"
            d, wk = daily_w(r["sym"], r["day"]); h = HM.get(r.get("bias","none"),"flat")
            i = idx(r["day"], r["et"])
            for nm, val in (("index", i), ("daily", d), ("hourly", h)):
                trips[nm]["agrees" if val == w else ("flat" if val == "flat" else "disagrees")] += 1
            stack[sum(1 for x in (wk, d, h, i) if x == w)] += 1
    print("\ntrip rates (n = %d candidates)" % tot_c)
    for nm, c in trips.items():
        print("  %-7s %s" % (nm, {k: "%d (%.1f%%)" % (n_, 100*n_/tot_c) for k, n_ in c.items()}))
    print("  stack   %s" % {k: "%d (%.1f%%)" % (n_, 100*n_/tot_c) for k, n_ in sorted(stack.items())})
    ge3 = sum(n_ for k, n_ in stack.items() if k >= 3)
    print("  stack agrees(>=3) trips on %d of %d = %.1f%%" % (ge3, tot_c, 100*ge3/tot_c))
    print("  hourly agrees trips on %.1f%% -- ABOVE the 60%% ceiling for a gate" %
          (100*trips["hourly"]["agrees"]/tot_c))
else:
    print("\n(no cache; skipping trip rates)")

# ---- 4. independent recompute of the "best arm" (hourly selector, +$41/day) --
# Rebuilt from the cache features above, not from g81_htf_thesis.py's helpers.
if os.path.exists(CACHE):
    def feat(r):
        w = "bull" if r["dir"] == "call" else "bear"
        d, wk = daily_w(r["sym"], r["day"]); h = HM.get(r.get("bias", "none"), "flat")
        i = idx(r["day"], r["et"])
        return w, d, wk, h, i
    F = {id(r): feat(r) for v in byday.values() for r in v}
    def sc(nm, r):
        w, d, wk, h, i = F[id(r)]
        val = {"index": i, "daily": d, "hourly": h}.get(nm)
        if nm == "stack":
            return sum(1 for x in (wk, d, h, i) if x == w)
        return 0 if val == "flat" else (1 if val == w else -1)
    print("\nindependent selector recompute (divisor %d)" % n_meta)
    base_tot = sum(v[0]["pnl"] for v in byday.values())
    base_hit = sum(1 for v in byday.values() if v[0]["r"] >= max(x["r"] for x in v))
    print("  arrival  $%4.0f/day  hit-best %.1f%%" % (base_tot/n_meta, 100*base_hit/n_have))
    for nm in ("index", "daily", "hourly", "stack"):
        picks = []
        for v in byday.values():
            m = max(sc(nm, r) for r in v)
            picks.append(next(r for r in v if sc(nm, r) == m))
        t = sum(r["pnl"] for r in picks)
        hh = sum(1 for p, v in zip(picks, byday.values()) if p["r"] >= max(x["r"] for x in v))
        w = sum(1 for r in picks if r["pnl"] > 0); l = sum(1 for r in picks if r["pnl"] < 0)
        print("  %-8s $%4.0f/day  vs base %+5.0f  hit-best %.1f%%  win %.1f%%"
              % (nm, t/n_meta, (t-base_tot)/n_meta, 100*hh/n_have, 100*w/(w+l)))
        print("     |diff| in R = %.4f  -- standing error bar is 1.5799R"
              % (abs(t-base_tot)/n_meta/RISK))

# ---- 5. S-day recall, independently ----------------------------------------
sys.path.insert(0, HERE)
import marks_pool
pool = marks_pool.canonical_pool(); s_keys = marks_pool.s_days(pool)
bysd = defaultdict(list)
for v in byday.values():
    for r in v:
        bysd["%s_%s" % (r["sym"], r["day"])].append(r)
for v in bysd.values():
    v.sort(key=lambda r: r["et"])
reached = [k for k in s_keys if k in bysd]
early = sum(1 for k in reached if bysd[k][0]["et"] < "09:45")
print("\nS days %d; book reaches %d; first entry before 09:45 on %d (%.1f%%)"
      % (len(s_keys), len(reached), early, 100*early/len(reached)))
if os.path.exists(CACHE):
    for nm, thr in (("index", 0), ("daily", 0), ("hourly", 0), ("stack", 3)):
        kept = sum(1 for k in reached
                   if bysd[k][0]["et"] >= "09:45"
                   or any((sc(nm, r) >= thr if nm == "stack" else sc(nm, r) > 0)
                          for r in bysd[k] if id(r) in F))
        print("  %-8s keeps %3d loses %3d" % (nm, kept, len(reached)-kept))
