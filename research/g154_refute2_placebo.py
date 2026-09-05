"""REFUTER #2 diagnostic for g154 stop-placement-routed.

Three tests:
  A. PLACEBO -- route every candidate to its OWN shipped stop (identity), then
     run the SAME replay_routed machinery. If the placebo moves $/day, the
     claimed delta is the replay, not the routing.
  B. Decompose the first-of-day delta: how many picked rows actually had a
     different stop, and how much $ each bucket contributed.
  C. Paired bootstrap over the 498 sessions on the real routed arm.
"""
import json, os, sys, random, statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

import importlib
g = importlib.import_module("g154_rule_stop-placement-routed".replace("-", "_")) \
    if False else None

# import the module by file (hyphens in name)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "g154mod", os.path.join(HERE, "g154_rule_stop-placement-routed.py"))
g154 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g154)

blob = json.load(open(g154.BOOK_PATH, encoding="utf-8"))
meta, rows = blob["meta"], blob["trades"]
byday = g154.by_day_candidates(rows)
n_days_total = meta.get("sessions") or len({r["day"] for r in rows})

# ---------------------------------------------------------------- A. PLACEBO
def build_placebo(byday):
    """Identity routing: routed stop == shipped stop, same replay."""
    out = defaultdict(list)
    for day in sorted(byday):
        for r in byday[day]:
            _routed, source = g154.routed_stop_for(r)
            if source.startswith("unchanged"):
                out[day].append(r)      # same fallback as the real arm
                continue
            new = g154.replay_routed(r, r["stop"])   # <-- IDENTITY stop
            out[day].append(new if new is not None else r)
    return out

def usd(firsts):
    days = sorted({r["day"] for r in firsts})
    return round(sum(r["pnl"] for r in firsts) / len(days), 2)

base_firsts = g154.pick_first_of_day(byday)
routed_byday, counts, dis_all, dis_tight = g154.build_routed_book(byday)
routed_firsts = g154.pick_first_of_day(routed_byday)
placebo_byday = build_placebo(byday)
placebo_firsts = g154.pick_first_of_day(placebo_byday)

def sc(f):
    h1, h2 = g154.split_h1_h2(f)
    return {"overall": g154.score(f), "H1": g154.score(h1), "H2": g154.score(h2)}

B, C, P = sc(base_firsts), sc(routed_firsts), sc(placebo_firsts)

print("=== A. PLACEBO (identity stop, same replay) ===")
for k in ("overall", "H1", "H2"):
    print("%-8s base $%8s  routed $%8s  PLACEBO $%8s   | win base %s routed %s placebo %s"
          % (k, B[k]["usd_day"], C[k]["usd_day"], P[k]["usd_day"],
             B[k]["win_pct"], C[k]["win_pct"], P[k]["win_pct"]))
print("placebo H1 delta %.2f  H2 delta %.2f"
      % (P["H1"]["usd_day"] - B["H1"]["usd_day"],
         P["H2"]["usd_day"] - B["H2"]["usd_day"]))

# ------------------------------------------------- B. decompose first-of-day
bmap = {(r["day"], r["et"], r["sym"]): r for r in base_firsts}
cmap = {(r["day"], r["et"], r["sym"]): r for r in routed_firsts}
pmap = {(r["day"], r["et"], r["sym"]): r for r in placebo_firsts}
print("\n=== B. first-of-day pick identity ===")
print("same picked rows base vs routed:", set(bmap) == set(cmap))
n_stopmoved = n_same = 0
d_moved = d_same = 0.0
for k, b in bmap.items():
    c = cmap.get(k)
    if c is None:
        continue
    if abs(c["stop"] - b["stop"]) > 1e-9:
        n_stopmoved += 1; d_moved += c["pnl"] - b["pnl"]
    else:
        n_same += 1; d_same += c["pnl"] - b["pnl"]
nd = len(sorted({r["day"] for r in base_firsts}))
print("picked rows whose STOP actually moved: %d  -> $%.2f total (%.2f/day)"
      % (n_stopmoved, d_moved, d_moved / nd))
print("picked rows whose stop is IDENTICAL:   %d  -> $%.2f total (%.2f/day)"
      % (n_same, d_same, d_same / nd))
# pnl changed at all?
n_pnlchanged = sum(1 for k, b in bmap.items()
                   if k in cmap and abs(cmap[k]["pnl"] - b["pnl"]) > 1e-9)
print("picked rows whose PNL changed:", n_pnlchanged, "of", len(bmap))
n_pnl_same_stop = sum(1 for k, b in bmap.items()
                      if k in cmap and abs(cmap[k]["stop"] - b["stop"]) <= 1e-9
                      and abs(cmap[k]["pnl"] - b["pnl"]) > 1e-9)
print("  ... of which the stop did NOT move:", n_pnl_same_stop)

# ------------------------------------------------- C. paired bootstrap (days)
random.seed(20260905)
days = sorted({r["day"] for r in base_firsts})
bday = defaultdict(float); cday = defaultdict(float); pday = defaultdict(float)
for r in base_firsts: bday[r["day"]] += r["pnl"]
for r in routed_firsts: cday[r["day"]] += r["pnl"]
for r in placebo_firsts: pday[r["day"]] += r["pnl"]
diff = [cday[d] - bday[d] for d in days]
pdiff = [pday[d] - bday[d] for d in days]

def boot(vec, n=20000):
    N = len(vec)
    ms = []
    for _ in range(n):
        ms.append(sum(vec[random.randrange(N)] for _ in range(N)) / N)
    ms.sort()
    return (statistics.fmean(vec), ms[int(0.025 * n)], ms[int(0.975 * n)],
            sum(1 for m in ms if m <= 0) / n)

print("\n=== C. paired bootstrap on %d sessions (20k resamples) ===" % len(days))
for name, vec in (("routed - baseline", diff), ("placebo - baseline", pdiff)):
    m, lo, hi, p = boot(vec)
    print("%-20s mean $%.2f/day  95%% CI [$%.2f, $%.2f]  P(delta<=0)=%.3f"
          % (name, m, lo, hi, p))

# split-half bootstrap
for lab, sel in (("H1", lambda d: d < g154.H_SPLIT), ("H2", lambda d: d >= g154.H_SPLIT)):
    sub = [cday[d] - bday[d] for d in days if sel(d)]
    m, lo, hi, p = boot(sub)
    print("%-20s mean $%.2f/day  95%% CI [$%.2f, $%.2f]  P(delta<=0)=%.3f"
          % ("routed " + lab, m, lo, hi, p))

json.dump({"base": B, "routed": C, "placebo": P}, open(
    os.path.join(HERE, "g154_refute2_placebo.json"), "w"), indent=2)
