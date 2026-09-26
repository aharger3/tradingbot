"""u01-his-eye: honest re-fill of Austin's hand-marked trades. Read-only."""
import sys, os, json, csv, random, statistics as st
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, RES); sys.path.insert(0, os.path.dirname(RES))
import types as _t
sys.modules.setdefault("yfinance", _t.ModuleType("yfinance"))
from t4_engine_recall import rth_candles
sys.path.insert(0, RES)
from w6_tz_recall import parse_rows

SLIP = 0.01      # $/share per side
COMM = 0.005     # $/share per side
TGT_R = 2.0
FLAT = "10:59"
_cache = {}
def bars(sym, day):
    k = (sym, day)
    if k not in _cache:
        _cache[k] = rth_candles(sym, day)
    return _cache[k]

def sim(c, i_sig, d, stop, flat=FLAT):
    """signal bar index i_sig; fill = open of i_sig+1 (+slip). intrabar stop, 2R limit, flat by `flat`."""
    if i_sig + 1 >= len(c): return None
    fill = c[i_sig+1].open + d*SLIP
    risk = (fill - stop)*d
    if risk <= 0.0: return {"r": -1.0, "why": "stop_through_fill"}  # already past stop: treat as full loss
    tgt = fill + d*TGT_R*risk
    cost = 2*(COMM) + SLIP  # exit slip + comms (entry slip already in fill)
    for j in range(i_sig+1, len(c)):
        b = c[j]
        hit_stop = (b.low <= stop) if d > 0 else (b.high >= stop)
        hit_tgt = (b.high >= tgt) if d > 0 else (b.low <= tgt)
        if hit_stop:
            ex = stop if ((b.open - stop)*d > 0) else b.open  # gap through -> open
            return {"r": ((ex - fill)*d - cost)/risk, "why": "stop"}
        if hit_tgt and j > i_sig+1 or (hit_tgt and j == i_sig+1):
            return {"r": ((tgt - fill)*d - cost)/risk, "why": "tgt"}
        if b.timestamp[:5] >= flat:
            return {"r": ((b.close - fill)*d - SLIP - cost)/risk, "why": "time"}
    b = c[-1]
    return {"r": ((b.close - fill)*d - SLIP - cost)/risk, "why": "eod"}

def idx_of(c, hhmm):
    for i, b in enumerate(c):
        if b.timestamp[:5] == hhmm: return i
    return None

def summ(rs):
    if not rs: return {"n": 0}
    w = sum(1 for r in rs if r > 0)
    return {"n": len(rs), "win": round(100*w/len(rs),1), "meanR": round(st.mean(rs),3),
            "sumR": round(sum(rs),1)}

out = {}
# ---- A. TradeZella hand-replay book
tz = parse_rows(os.path.join(os.path.dirname(RES), "data", "tradezella_trades.csv"))
raw = list(csv.DictReader(open(os.path.join(os.path.dirname(RES), "data", "tradezella_trades.csv"), encoding="utf-8-sig")))
logged = []
for r in raw:
    try: logged.append(float(r["Net P&L"]) / abs(float(r["Trade Risk"])))
    except: pass
out["tz_as_logged_R"] = summ(logged)
out["tz_as_logged_netpnl"] = round(sum(float(r["Net P&L"] or 0) for r in raw), 0)
rows = []
for r in tz:
    r["dir"] = 1 if r["side"]=="long" else -1 if r["side"]=="short" else None
    if r["dir"] is None or r["stop_p"] is None: continue
    c = bars(r["symbol"], r["date"])
    if not c: continue
    i = idx_of(c, r["hhmm"])
    if i is None: continue
    ratio = c[i].close / r["entry_p"]
    if 0.08 < ratio < 0.12:  # NVDA pre-2024-06-07 10:1 split: CSV unadjusted, archive adjusted
        r["entry_p"] *= 0.1; r["stop_p"] *= 0.1; r["split_fixed"] = True
    elif not (0.9 < ratio < 1.1):
        continue
    res = sim(c, i, r["dir"], r["stop_p"])
    if res is None: continue
    rows.append({**r, "i": i, "R": res["r"], "why": res["why"],
                 "stop_frac": (r["entry_p"] - r["stop_p"]) / r["entry_p"]})
out["tz_honest"] = summ([x["R"] for x in rows])
out["tz_honest_eod"] = summ([sim(bars(x["symbol"],x["date"]), x["i"], x["dir"], x["stop_p"], flat="15:59")["r"] for x in rows])
out["tz_split_fixed_rows"] = sum(1 for x in rows if x.get("split_fixed"))
out["tz_honest_excl_stop_through_fill"] = summ([x["R"] for x in rows if x["why"] != "stop_through_fill"])
out["tz_exit_mix"] = dict(sorted({k: sum(1 for x in rows if x["why"]==k) for k in set(x["why"] for x in rows)}.items()))
# first trade per symbol-day only
firsts = {}
for x in sorted(rows, key=lambda x: (x["symbol"], x["date"], x["hhmm"])):
    firsts.setdefault((x["symbol"], x["date"]), x)
out["tz_honest_first_per_day"] = summ([x["R"] for x in firsts.values()])
# time buckets
def bucket(h):
    return "0930-0944" if h < "09:45" else "0945-0959" if h < "10:00" else "1000-1029" if h < "10:30" else "1030+"
tb = defaultdict(list)
for x in rows: tb[bucket(x["hhmm"])].append(x["R"])
out["tz_by_time"] = {k: summ(v) for k, v in sorted(tb.items())}
# split half by date
ds = sorted(set(x["date"] for x in rows)); mid = ds[len(ds)//2]
out["tz_split_half"] = {"H1<"+mid: summ([x["R"] for x in rows if x["date"] < mid]),
                        "H2>="+mid: summ([x["R"] for x in rows if x["date"] >= mid])}
out["tz_by_symbol"] = {s: summ([x["R"] for x in rows if x["symbol"] == s]) for s in sorted(set(x["symbol"] for x in rows))}
out["tz_by_side"] = {s: summ([x["R"] for x in rows if x["side"] == s]) for s in ("long","short")}
# day-shuffle: same symbol, same minute, same side, same stop fraction, random other day
random.seed(20260926)
alldays = {}
for s in set(x["symbol"] for x in rows):
    dd = [f[:-4] if f.endswith(".csv") else f for f in []]
alldays = defaultdict(list)
for x in rows: alldays[x["symbol"]].append(x["date"])
pool = {s: sorted(set(v)) for s, v in alldays.items()}
shuf_means = []
for k in range(200):
    rs = []
    for x in rows:
        d2 = random.choice(pool[x["symbol"]])
        if d2 == x["date"]: continue
        c = bars(x["symbol"], d2)
        if not c: continue
        i = idx_of(c, x["hhmm"])
        if i is None: continue
        f = c[i].close
        stop = f*(1 - x["stop_frac"]) if x["dir"] > 0 else f*(1 + abs(x["stop_frac"]))
        res = sim(c, i, x["dir"], stop)
        if res: rs.append(res["r"])
    shuf_means.append(st.mean(rs))
real = out["tz_honest"]["meanR"]
out["tz_day_shuffle"] = {"iters": 200, "shuffle_meanR_mean": round(st.mean(shuf_means),3),
    "shuffle_p95": round(sorted(shuf_means)[189],3), "real_meanR": real,
    "p_shuffle_ge_real": round(sum(1 for m in shuf_means if m >= real)/200, 3)}
# direction-flip control: same minute, opposite side, mirrored stop
flip = []
for x in rows:
    c = bars(x["symbol"], x["date"]); f = c[x["i"]].close; dist = abs(x["entry_p"] - x["stop_p"])
    res = sim(c, x["i"], -x["dir"], f + x["dir"]*dist)
    if res: flip.append(res["r"])
out["tz_opposite_side_control"] = summ(flip)

byd = defaultdict(list)
for x in rows: byd[x["date"]].append(x["R"])
dks = list(byd); bs = []
for _ in range(5000):
    smp = [random.choice(dks) for _ in dks]
    rr = [r for d in smp for r in byd[d]]
    bs.append(st.mean(rr))
bs.sort()
out["tz_day_bootstrap_meanR_95"] = [round(bs[124],3), round(bs[4874],3)]
out["tz_sd_R"] = round(st.pstdev([x["R"] for x in rows]),3)
out["tz_span"] = [min(x["date"] for x in rows), max(x["date"] for x in rows), len(byd)]
# ---- B. deck trade marks (hindsight marks with side+stop)
deck = []
for fn in ("deck_marks_index_2026-08-19.jsonl", "deck_marks_tsla_2026-08-20.jsonl"):
    for ln in open(os.path.join(RES, "marks", fn)):
        r = json.loads(ln)
        if r.get("type") != "trade" or r.get("entry_i") is None or r.get("stop_p") is None: continue
        c = bars(r["symbol"], r["date"])
        if not c: continue
        d = 1 if str(r.get("side","")).lower() in ("l","long","call","calls","buy") else -1 if str(r.get("side","")).lower() in ("s","short","put","puts","sell") else None
        if d is None: continue
        i = idx_of(c, str(r.get("entry_t",""))[:5])
        if i is None: continue
        if i >= len(c): continue
        res = sim(c, i, d, float(r["stop_p"]))
        if res: deck.append({"sym": r["symbol"], "date": r["date"], "R": res["r"], "logged": r.get("r_multiple"), "t": c[i].timestamp[:5], "why": res["why"]})
out["deck_marks_honest"] = summ([x["R"] for x in deck])
out["deck_marks_honest_excl_through"] = summ([x["R"] for x in deck if x["why"] != "stop_through_fill"])
out["deck_marks_logged_tranche1"] = summ([x["logged"] for x in deck if x["logged"] is not None])
json.dump(out, open(os.path.join(HERE, "his_eye_honest.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
