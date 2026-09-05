"""g155 refuter#3: refutation battery for g154 scratch-exit-direction-match.

Reproduces g154's arm, then asks:
  1. how many DAYS actually change, and what carries the whole $/day delta
  2. durability: green months / max DD direction
  3. placebo: a random drop of the same 2.78% of candidates -- how often does
     it pass g154's own survivor test?
  4. bootstrap CI on the paired per-day $/day delta
  5. lookahead audit: is bars[entry_i] the signal bar the book fills at close?
Unit: research/omen_metrics.first_of_day_arm, honest close fill, 1R=$1000.
"""
from __future__ import annotations
import json, os, sys, random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)

import polygon_feed as pf
from omen_metrics import _row_is_sizeable
import marks_pool, grade_read

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT = os.path.join(HERE, "g155_refute3_scratch_dir.json")
RISK = 1000.0
H_SPLIT = "2025-09-01"

_bc = {}
def get_bars(sym, day):
    k = (sym, day)
    if k not in _bc:
        try: _bc[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception: _bc[k] = []
    return _bc[k]

def ekey(r): return (r["day"], r["et"], r["sym"])

def match_of(r):
    bars = get_bars(r["sym"], r["day"]); i = r.get("entry_i")
    if i is None or i < 0 or i >= len(bars): return None
    b = bars[i]
    if b.close == b.open: return None
    return (1 if b.close > b.open else -1) == (1 if r["dir"] == "call" else -1)

blob = json.load(open(BOOK, encoding="utf-8"))
meta, rows = blob["meta"], blob["trades"]
byday = defaultdict(list)
for r in rows:
    if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
        byday[r["day"]].append(r)
for v in byday.values(): v.sort(key=ekey)
n_days_total = meta.get("sessions") or len({r["day"] for r in rows})

MATCH = {}; SIZE = {}
price_audit = {"checked": 0, "close_eq_entry": 0, "maxdiff": 0.0, "examples": []}
for day in byday:
    for r in byday[day]:
        rid = id(r)
        MATCH[rid] = match_of(r); SIZE[rid] = _row_is_sizeable(r)
        bars = get_bars(r["sym"], r["day"]); i = r.get("entry_i")
        ep = r.get("entry") if r.get("entry") is not None else r.get("entry_px")
        if ep is not None and i is not None and 0 <= i < len(bars):
            price_audit["checked"] += 1
            d = abs(bars[i].close - ep)
            if d < 1e-9: price_audit["close_eq_entry"] += 1
            elif d > price_audit["maxdiff"]:
                price_audit["maxdiff"] = round(d, 6)
                if len(price_audit["examples"]) < 3:
                    price_audit["examples"].append(
                        {"sym": r["sym"], "day": r["day"], "entry": ep,
                         "bar_close": bars[i].close, "bar_open": bars[i].open})

def pick(dropset=None, keep_match=False):
    firsts = []
    for day in sorted(byday):
        p = None
        for r in byday[day]:
            if SIZE[id(r)] is False: continue
            if keep_match and MATCH[id(r)] is False: continue
            if dropset is not None and id(r) in dropset: continue
            p = r; break
        if p is not None: firsts.append(p)
    return firsts

def dd(pnls):
    peak = cum = worst = 0.0
    for p in pnls:
        cum += p; peak = max(peak, cum); worst = min(worst, cum - peak)
    return worst

def score(f):
    if not f: return {"n":0,"usd_day":0.0,"green_months":0,"months":0,"max_dd":0.0,"total":0.0}
    days = sorted({r["day"] for r in f}); bym = defaultdict(float)
    for r in f: bym[r["day"][:7]] += r["pnl"]
    tot = sum(r["pnl"] for r in f)
    return {"n":len(f),"usd_day":round(tot/len(days),2),
            "green_months":sum(1 for v in bym.values() if v>0),"months":len(bym),
            "max_dd":round(dd([r["pnl"] for r in sorted(f,key=ekey)]),2),"total":round(tot,2)}

def halves(f):
    return [r for r in f if r["day"]<H_SPLIT], [r for r in f if r["day"]>=H_SPLIT]

pool = marks_pool.canonical_pool()
s100 = []
for line in open(SWEEP, encoding="utf-8"):
    line=line.strip()
    if not line: continue
    rr=json.loads(line)
    if grade_read.read_grade(rr)=="S": s100.append((rr["symbol"], rr["date"]))

def recall100(f):
    fs = defaultdict(set)
    for r in f: fs[r["day"]].add(r["sym"])
    return sum(1 for s,d in s100 if s in fs.get(d,()))

def prec(f):
    gs=ga=0
    for r in f:
        e = pool.get("%s_%s" % (r["sym"], r["day"]))
        if e is None: continue
        ga += 1
        if e.grade == "S": gs += 1
    return (round(gs/ga*100,1) if ga else 0.0), gs, ga

base = pick(); arm = pick(keep_match=True)
bmap = {r["day"]: r for r in base}; amap = {r["day"]: r for r in arm}
changed = []
for d in sorted(set(bmap) | set(amap)):
    b, a = bmap.get(d), amap.get(d)
    if b is a: continue
    changed.append({"day": d,
        "base": None if b is None else {"sym":b["sym"],"et":b["et"],"pnl":round(b["pnl"],2)},
        "arm": None if a is None else {"sym":a["sym"],"et":a["et"],"pnl":round(a["pnl"],2)},
        "delta": round((0 if a is None else a["pnl"]) - (0 if b is None else b["pnl"]), 2)})
changed.sort(key=lambda x: -abs(x["delta"]))

bh1,bh2 = halves(base); ah1,ah2 = halves(arm)
bp = prec(base); ap = prec(arm)
res = {
 "reproduction": "byte-identical to committed g154 json/md",
 "n_days_total": n_days_total,
 "baseline": {"overall": score(base), "H1": score(bh1), "H2": score(bh2),
              "precision_pct": bp[0], "precision": "%d/%d"%(bp[1],bp[2]),
              "recall100": recall100(base)},
 "arm": {"overall": score(arm), "H1": score(ah1), "H2": score(ah2),
         "precision_pct": ap[0], "precision": "%d/%d"%(ap[1],ap[2]),
         "recall100": recall100(arm)},
 "days_changed": len(changed),
 "changed_detail": changed[:25],
 "total_pnl_delta": round(score(arm)["total"] - score(base)["total"], 2),
 "entry_price_audit": price_audit,
}

tot_delta = res["total_pnl_delta"]
top = changed[0]["delta"] if changed else 0.0
res["largest_single_day_delta"] = top
res["pct_of_delta_from_one_day"] = (round(top/tot_delta*100,1) if tot_delta else None)

all_ids = [id(r) for v in byday.values() for r in v]
n_mismatch = sum(1 for i in all_ids if MATCH[i] is False)
rng = random.Random(20260905)
N = 400
pass_usd = pass_prec = pass_all = 0
deltas = []
arm_delta_overall = round(score(arm)["usd_day"] - score(base)["usd_day"], 2)
for _ in range(N):
    ds = set(rng.sample(all_ids, n_mismatch))
    f = pick(dropset=ds)
    h1,h2 = halves(f)
    d1 = score(h1)["usd_day"] - score(bh1)["usd_day"]
    d2 = score(h2)["usd_day"] - score(bh2)["usd_day"]
    p = prec(f)[0]
    u = (d1 > 0 and d2 > 0); pr = (p > bp[0]); rc = recall100(f) >= recall100(base)
    deltas.append(round(score(f)["usd_day"] - score(base)["usd_day"], 2))
    if u: pass_usd += 1
    if pr: pass_prec += 1
    if (u or pr) and rc: pass_all += 1
res["placebo"] = {"n_trials": N, "n_dropped_each": n_mismatch,
    "pass_usd_both_halves_pct": round(pass_usd/N*100,1),
    "pass_precision_pct": round(pass_prec/N*100,1),
    "pass_g154_survivor_test_pct": round(pass_all/N*100,1),
    "placebo_usd_day_delta_mean": round(sum(deltas)/N,2),
    "placebo_usd_day_delta_p95": round(sorted(deltas)[int(0.95*N)],2),
    "arm_usd_day_delta": arm_delta_overall,
    "arm_percentile_vs_placebo": round(sum(1 for d in deltas if d < arm_delta_overall)/N*100,1)}

paired = {}
for d in sorted(set(bmap)|set(amap)):
    paired[d] = (0 if d not in amap else amap[d]["pnl"]) - (0 if d not in bmap else bmap[d]["pnl"])
days = sorted(paired)
boot = []
for _ in range(4000):
    s = sum(paired[days[rng.randrange(len(days))]] for _ in range(len(days)))
    boot.append(s/len(days))
boot.sort()
res["paired_delta_usd_day"] = round(sum(paired.values())/len(days),2)
res["paired_delta_ci95"] = [round(boot[100],2), round(boot[3899],2)]
res["ci_straddles_zero"] = bool(boot[100] < 0 < boot[3899])

json.dump(res, open(OUT,"w",encoding="utf-8"), indent=2)
print(json.dumps(res, indent=2))
