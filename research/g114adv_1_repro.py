"""ADVERSARIAL repro of g114: independent walk, independent first-of-day rule.
Writes a flat per-trade record so every later check reads one static file."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import signal_runner as sr
from research import g80_ordertype_grid as G

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT = os.path.join(HERE, "_adv_g114_pop.json")
WIN_END = "11:00:00"

def load(p):
    b = json.load(open(p, encoding="utf-8"))
    return b["trades"] if isinstance(b, dict) else b

rows = load(BOOK)
# independent first-of-day: fired&traded OR halted, earliest entry time per day
byday = {}
for r in rows:
    if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
        byday.setdefault(r["day"], []).append(r)
firsts = []
for d in sorted(byday):
    v = sorted(byday[d], key=lambda r: (r.get("et") or "99:99", r.get("entry_i") or 9999, r["sym"]))
    firsts.append(v[0])
print("days with a candidate: %d" % len(firsts))

out = []
no_bars = gated = 0
for k, r in enumerate(firsts, 1):
    bars, *_ = G.day_pack(r["sym"], r["day"])
    if not bars:
        no_bars += 1; continue
    entry, stop = r["entry"], r["stop"]
    risk = abs(entry - stop)
    if risk < sr.min_risk_floor(entry):
        gated += 1; continue
    i = r.get("entry_i")
    if i is None or i >= len(bars):
        gated += 1; continue
    long = r["dir"] == "call"
    mfe_alive = 0.0; mfe_alive_px = 0.0; stopped = False; last_close = entry; nb = 0
    for b in bars[i+1:]:
        if b.timestamp > WIN_END: break
        nb += 1
        last_close = b.close
        fav = ((b.high - entry) if long else (entry - b.low))
        adv = ((entry - b.low) if long else (b.high - entry))
        if adv / risk >= 1.0:
            stopped = True; break
        mfe_alive = max(mfe_alive, fav / risk)
        mfe_alive_px = max(mfe_alive_px, fav)
    mark = ((last_close - entry) if long else (entry - last_close)) / risk
    rec = dict(r)
    rec["_mfe_alive"] = mfe_alive
    rec["_mfe_alive_px"] = mfe_alive_px
    rec["_mfe_alive_pct"] = 100.0 * mfe_alive_px / entry
    rec["_stopped"] = stopped
    rec["_mark"] = mark
    rec["_risk"] = risk
    rec["_bars_walked"] = nb
    # flat-target counterfactuals, bar-ordered (target hit strictly before stop)
    for t in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
        rec["_t%.1f" % t] = t if mfe_alive >= t else (-1.0 if stopped else mark)
    out.append(rec)
    if k % 100 == 0: print("  %d/%d" % (k, len(firsts)))

n = len(out)
nr = sum(1 for r in out if r["_mfe_alive"] >= 3.0)
print("measured %d (no_bars %d, gated %d)  runners>=3R %d = %.1f%%" % (n, no_bars, gated, nr, 100*nr/n))
json.dump({"n": n, "no_bars": no_bars, "gated": gated, "rows": out}, open(OUT, "w", encoding="utf-8"))
print("->", OUT)
