"""g80_verify_0 - adversarial recompute of research/g80_ordertype_grid.md.

Written from scratch to try to REFUTE the order-type grid. Nothing in
research/g80_ordertype_grid.py is imported. The only shared code is the SHIPPED
engine (backtest_week._ladder_bar, signal_runner.intrabar_stop /
min_risk_floor, polygon_feed), which is the thing both reports claim to route
through.

Three independent recomputes:

  1. THE CONTROL, WITHOUT SIMULATING ANYTHING. The published book already
     carries a pnl for every traded row. One-trade-a-day on the book's own
     numbers needs no harness at all, so it is the cleanest possible check of
     the two biggest headline figures ($720/day ungated, $683/day gated).
  2. THE SIZE GATE, recomputed from the book's own entry/stop and the shipped
     min_risk_floor read off the signal bar's close.
  3. POLICIES B (market at the signal close), C (next open) and D (chase once),
     re-simulated with my own driver over the shipped ladder.

Plus: a PAIRED per-day bootstrap of control-minus-policy (the grid bootstraps
the two arms separately, which is the wrong test for paired days), and a
mean-R / win-rate consistency check.

Usage: python research/g80_verify_0.py [--fast]
Writes: research/g80_verify_0.json
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf                        # noqa: E402
import backtest_week as bw                       # noqa: E402
import signal_runner as sr                       # noqa: E402
from backtest_week import SimTrade, _ladder_bar  # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT = ROOT / "research" / "g80_verify_0.json"
RISK = 1000.0
EPS = 0.005
CUTOFF = "11:00:00"
SEED = 7
BOOTS = 10000


# ------------------------------------------------------------------ bar cache

_bars: dict = {}
_prevhl: dict = {}
_daylist: dict = {}


def sym_days(sym):
    if sym not in _daylist:
        d = ROOT / "data_archive" / sym
        _daylist[sym] = sorted(f.stem for f in d.glob("*.csv")) if d.is_dir() else []
    return _daylist[sym]


def load(sym, day):
    """(rth bars, pdh, pdl, pmh, pml). Same derivation backtest_2y makes."""
    k = (sym, day)
    if k in _bars:
        return _bars[k]
    if len(_bars) > 300:
        _bars.clear()
    try:
        raw = pf.fetch_day(sym, day)
        rth = pf.rth(raw)
    except Exception:
        raw, rth = [], []
    pmh, pml = pf.premarket_hi_lo(raw) if raw else (None, None)
    pdh = pdl = None
    ds = sym_days(sym)
    if day in ds:
        for prev in reversed(ds[:ds.index(day)]):
            pk = (sym, prev)
            if pk in _prevhl:
                hi, lo, ok = _prevhl[pk]
                if ok:
                    pdh, pdl = hi, lo
                    break
                continue
            try:
                p = pf.rth(pf.fetch_day(sym, prev))
            except Exception:
                p = []
            ok = len(p) >= 30
            hl = (max(c.high for c in p), min(c.low for c in p)) if ok else (None, None)
            _prevhl[pk] = (hl[0], hl[1], ok)
            if ok:
                pdh, pdl = hl
                break
    _bars[k] = (rth, pdh, pdl, pmh, pml)
    return _bars[k]


# --------------------------------------------------------------- my own driver

class _Runner:
    def __init__(self, bars, bias):
        self.candles, self.htf_bias = bars, bias
        self.session = type("S", (), {"entry_price": 0.0, "entry_direction": "",
                                      "entry_target": 0.0, "entry_stop": 0.0})()


def simulate(row, bars, open_i, entry_px, pdh, pdl, pmh, pml):
    """Open at entry_px, position live from bar open_i+1. Returns dict or None."""
    long = row["dir"] == "call"
    stop = sr.intrabar_stop(entry_px, row["stop"], bars[open_i], long)
    risk = (entry_px - stop) if long else (stop - entry_px)
    if risk <= EPS:
        return None
    floor = sr.min_risk_floor(bars[open_i].close)
    if row["setup"] == "reentry_84_rule":
        target = row["target"]
    else:
        target = entry_px + 2 * risk if long else entry_px - 2 * risk
    scale_level = runner_tgt = 0.0
    if bw.SCALE_PLAN:
        pre = bars[:open_i + 1]
        if long:
            scale_level = max(c.high for c in pre)
            cs = [x for x in (pdh, pmh) if x is not None and x > scale_level]
            cs.append(math.floor(scale_level) + 1.0)
            runner_tgt = min(cs)
        else:
            scale_level = min(c.low for c in pre)
            cs = [x for x in (pdl, pml) if x is not None and x < scale_level]
            cs.append(math.ceil(scale_level) - 1.0)
            runner_tgt = max(cs)
    t = SimTrade(symbol=row["sym"], day=row["day"], signal_type=row["setup"],
                 direction=row["dir"], grade=row["grade"], status=row["status"],
                 entry_time=bars[open_i].timestamp, entry=entry_px, stop=stop,
                 target=target, reason=row["reason"], entry_idx=open_i,
                 exit_idx=len(bars) - 1, be_level=0.0, scale_level=scale_level,
                 runner_target=runner_tgt, setup_type=row["setup"],
                 stop_level_name=row.get("level_name") or "")
    t.level_price = row["level_px"]
    rn = _Runner(bars, row.get("bias") if row.get("bias") != "none" else None)
    live = [t]
    for j in range(open_i + 1, len(bars)):
        if not live:
            break
        _ladder_bar(t, bars[j], j, live, rn)
    if live:
        t.outcome, t.exit_price, t.exit_idx = "scratch", bars[-1].close, len(bars) - 1
    return {"pnl": t.pnl, "r": t.pnl / RISK, "out": t.outcome,
            "risk": risk, "floor": floor, "sizeable": risk >= floor}


def cut_i(bars):
    for j, c in enumerate(bars):
        if c.timestamp >= CUTOFF:
            return j
    return len(bars)


# ------------------------------------------------------------------- reporting

def stats(rows, n_days, all_days):
    if not rows:
        return {"trades": 0}
    p = [r["pnl"] for r in rows]
    w = sum(1 for x in p if x > 0)
    l = sum(1 for x in p if x < 0)
    bm, bwk = defaultdict(float), defaultdict(float)
    for r in rows:
        bm[r["day"][:7]] += r["pnl"]
        y, wk, _ = date.fromisoformat(r["day"]).isocalendar()
        bwk[(y, wk)] += r["pnl"]
    am = {d[:7] for d in all_days}
    aw = {date.fromisoformat(d).isocalendar()[:2] for d in all_days}
    tot = sum(p)
    return {"trades": len(rows),
            "win_pct": round(w / (w + l) * 100, 1) if w + l else 0.0,
            "total_dollars": round(tot),
            "mean_r": round(tot / len(rows) / RISK, 4),
            "per_day": round(tot / n_days),
            "months_green": sum(1 for k in am if bm.get(k, 0) > 0),
            "months": len(am),
            "weeks_green": sum(1 for k in aw if bwk.get(k, 0) > 0),
            "weeks": len(aw)}


def day_vec(rows, all_days):
    d = {x: 0.0 for x in all_days}
    for r in rows:
        d[r["day"]] = d.get(r["day"], 0.0) + r["pnl"]
    return [d[k] for k in sorted(d)]


def boot_ci(v, seed=SEED):
    rng = random.Random(seed)
    n = len(v)
    m = sorted(sum(rng.choices(v, k=n)) / n for _ in range(BOOTS))
    return [round(sum(v) / n), round(m[int(BOOTS * .025)]), round(m[int(BOOTS * .975)])]


def policy_a_probe():
    """Does 'a resting limit at the level loses' survive killing the arming model?

    The grid dates policy A's order from an arming bar traced by a replay of the
    break-and-retest state machine. That replay computes its tolerance from the
    average range of a window that ENDS AT THE SIGNAL BAR, so bars after the
    'leave' bar help decide when the order could have rested - a small
    look-ahead. Two arming models that contain no look-ahead at all bracket it:

      A_open   the order rests from the FIRST RTH bar of the day (earliest any
               order could exist), cancelled at 11:00. Fills soonest.
      A_after  the order rests only from the bar AFTER the signal, so no fill
               can precede the signal that justified it. Fills latest.

    If the resting limit loses under both, the grid's -$252 does not come from
    its arming model.
    """
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, rows = book["meta"], book["trades"]
    n_days, all_days = meta["sessions"], sorted({r["day"] for r in rows})
    traded_idx = [i for i, r in enumerate(rows) if r.get("traded")]
    cand = defaultdict(list)
    for i, r in enumerate(rows):
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            cand[r["day"]].append(i)
    for d in cand:
        cand[d].sort(key=lambda i: (rows[i]["et"], rows[i]["sym"]))
    order = defaultdict(list)
    for i in set(traded_idx) | {i for v in cand.values() for i in v}:
        order[(rows[i]["sym"], rows[i]["day"])].append(i)
    need = sorted(order)
    print("policy-A probe over %d symbol-days ..." % len(need), flush=True)
    pri = {"A_open": {}, "A_after": {}}
    for n, k in enumerate(need):
        if n and n % 1000 == 0:
            print("   %d / %d" % (n, len(need)), flush=True)
        bars, pdh, pdl, pmh, pml = load(*k)
        if not bars:
            continue
        cu, nb = cut_i(bars), len(bars)
        for i in order[k]:
            r = rows[i]
            ei, lvl, long = r["entry_i"], r["level_px"], r["dir"] == "call"
            if ei >= nb:
                continue
            for tag, j0 in (("A_open", 0), ("A_after", ei + 1)):
                fi = px = None
                for j in range(max(j0, 0), min(cu, nb)):
                    c = bars[j]
                    if long and c.low <= lvl + EPS:
                        fi, px = j, min(lvl, c.open)
                        break
                    if (not long) and c.high >= lvl - EPS:
                        fi, px = j, max(lvl, c.open)
                        break
                if fi is None or fi >= nb - 1:
                    continue
                o = simulate(r, bars, fi, px, pdh, pdl, pmh, pml)
                if o:
                    pri[tag][i] = o
    out = {}
    for tag in ("A_open", "A_after"):
        for gated in (False, True):
            def ok(i, _t=tag, _g=gated):
                o = pri[_t].get(i)
                return o is not None and (o["sizeable"] or not _g)
            ev_ = [{"day": rows[i]["day"], "pnl": pri[tag][i]["pnl"]}
                   for i in traded_idx if ok(i)]
            one_, miss = [], 0
            for d in sorted(cand):
                t = next((i for i in cand[d] if ok(i)), None)
                if t is None:
                    miss += 1
                else:
                    one_.append({"day": d, "pnl": pri[tag][t]["pnl"]})
            key = "%s_%s" % (tag, "GATED" if gated else "ungated")
            out[key] = {"everything": stats(ev_, n_days, all_days),
                        "one_a_day": stats(one_, n_days, all_days),
                        "one_a_day_days_missed": miss, "fills": len(ev_),
                        "one_a_day_ci": boot_ci(day_vec(one_, all_days))}
            s = out[key]["one_a_day"]
            print("   %-16s one-a-day %d trades (%d missed) %.1f%% win $%d/day ci%s "
                  "meanR %+.4f  %d/%d months"
                  % (key, s["trades"], miss, s["win_pct"], s["per_day"],
                     out[key]["one_a_day_ci"], s["mean_r"], s["months_green"],
                     s["months"]), flush=True)
    p = ROOT / "research" / "g80_verify_0_policyA.json"
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote %s" % p.relative_to(ROOT))


def main():
    if "--policyA" in sys.argv:
        return policy_a_probe()
    fast = "--fast" in sys.argv
    book = json.load(open(BOOK, encoding="utf-8"))
    meta, rows = book["meta"], book["trades"]
    n_days = meta["sessions"]
    all_days = sorted({r["day"] for r in rows})
    traded_idx = [i for i, r in enumerate(rows) if r.get("traded")]

    cand = defaultdict(list)
    for i, r in enumerate(rows):
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            cand[r["day"]].append(i)
    for d in cand:
        cand[d].sort(key=lambda i: (rows[i]["et"], rows[i]["sym"]))

    res = {"meta": {"sessions": n_days, "days_in_book": len(all_days),
                    "traded_rows": len(traded_idx), "candidate_days": len(cand),
                    "candidates": sum(len(v) for v in cand.values())}}
    print("book: %d traded rows, %d sessions, %d days, %d candidate days, %d candidates"
          % (len(traded_idx), n_days, len(all_days), len(cand),
             sum(len(v) for v in cand.values())), flush=True)

    # ---- 1. CONTROL from the book's own pnl, no simulation ------------------
    one = [rows[cand[d][0]] for d in sorted(cand)]
    res["control_book_pnl_one_a_day_UNGATED"] = stats(one, n_days, all_days)
    res["control_book_pnl_one_a_day_UNGATED"]["ci"] = boot_ci(day_vec(one, all_days))
    ev = [rows[i] for i in traded_idx]
    res["control_book_pnl_everything_UNGATED"] = stats(ev, n_days, all_days)
    print("\n1. CONTROL straight off the published book (no harness):")
    s = res["control_book_pnl_one_a_day_UNGATED"]
    print("   one-a-day  %d trades  %.1f%% win  $%d/day  ci%s  meanR %+.4f  "
          "%d/%d months  %d/%d weeks"
          % (s["trades"], s["win_pct"], s["per_day"], s["ci"], s["mean_r"],
             s["months_green"], s["months"], s["weeks_green"], s["weeks"]), flush=True)
    s = res["control_book_pnl_everything_UNGATED"]
    print("   everything %d trades  %.1f%% win  $%d/day  meanR %+.4f"
          % (s["trades"], s["win_pct"], s["per_day"], s["mean_r"]), flush=True)

    # ---- 2. the size gate, recomputed --------------------------------------
    order = defaultdict(list)
    for i in set(traded_idx) | {i for v in cand.values() for i in v}:
        order[(rows[i]["sym"], rows[i]["day"])].append(i)
    need = sorted(order)
    print("\n2. size gate: loading %d symbol-days ..." % len(need), flush=True)
    sizeable = {}
    nobars = 0
    for n, k in enumerate(need):
        if n and n % 1500 == 0:
            print("   %d / %d" % (n, len(need)), flush=True)
        bars = load(*k)[0]
        for i in order[k]:
            r = rows[i]
            if not bars or r["entry_i"] >= len(bars):
                nobars += 1
                continue
            risk = abs(r["entry"] - r["stop"])
            sizeable[i] = risk >= sr.min_risk_floor(bars[r["entry_i"]].close)
    res["gate"] = {"rows_with_no_bars": nobars,
                   "traded_rows_scored": sum(1 for i in traded_idx if i in sizeable),
                   "traded_rows_sizeable": sum(1 for i in traded_idx if sizeable.get(i)),
                   "traded_rows_dropped": sum(1 for i in traded_idx
                                              if not sizeable.get(i, False))}
    oneg, missed = [], 0
    for d in sorted(cand):
        took = next((rows[i] for i in cand[d] if sizeable.get(i)), None)
        if took is None:
            missed += 1
        else:
            oneg.append(took)
    res["control_book_pnl_one_a_day_GATED"] = stats(oneg, n_days, all_days)
    res["control_book_pnl_one_a_day_GATED"]["ci"] = boot_ci(day_vec(oneg, all_days))
    res["control_book_pnl_one_a_day_GATED"]["days_missed"] = missed
    evg = [rows[i] for i in traded_idx if sizeable.get(i)]
    res["control_book_pnl_everything_GATED"] = stats(evg, n_days, all_days)
    print("   gate drops %d of %d traded rows"
          % (res["gate"]["traded_rows_dropped"], len(traded_idx)), flush=True)
    s = res["control_book_pnl_one_a_day_GATED"]
    print("   one-a-day GATED  %d trades (%d days missed)  %.1f%% win  $%d/day  ci%s  "
          "meanR %+.4f  %d/%d months  %d/%d weeks"
          % (s["trades"], missed, s["win_pct"], s["per_day"], s["ci"], s["mean_r"],
             s["months_green"], s["months"], s["weeks_green"], s["weeks"]), flush=True)
    s = res["control_book_pnl_everything_GATED"]
    print("   everything GATED %d trades  %.1f%% win  $%d/day  meanR %+.4f"
          % (s["trades"], s["win_pct"], s["per_day"], s["mean_r"]), flush=True)

    if fast:
        OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
        print("\nwrote %s (fast)" % OUT.relative_to(ROOT))
        return

    # ---- 3. policies B, C and D, my own driver over the shipped ladder ------
    print("\n3. re-simulating B (market @ signal close), C (next open), D (chase once) ...",
          flush=True)
    pri = {"B": {}, "C": {}, "D": {}}
    for n, k in enumerate(need):
        if n and n % 1000 == 0:
            print("   %d / %d" % (n, len(need)), flush=True)
        bars, pdh, pdl, pmh, pml = load(*k)
        if not bars:
            continue
        cu = cut_i(bars)
        for i in order[k]:
            r = rows[i]
            ei, nb = r["entry_i"], len(bars)
            if ei >= nb:
                continue
            long = r["dir"] == "call"
            lvl = r["level_px"]
            if ei < nb - 1:
                o = simulate(r, bars, ei, bars[ei].close, pdh, pdl, pmh, pml)
                if o:
                    pri["B"][i] = o
            if ei + 1 < nb:
                o = simulate(r, bars, ei, bars[ei + 1].open, pdh, pdl, pmh, pml)
                if o:
                    pri["C"][i] = o
            fi = px = None
            j = ei + 1
            if j < min(ei + 2, cu) and j < nb:
                c = bars[j]
                if long and c.low <= lvl + EPS:
                    fi, px = j, min(lvl, c.open)
                elif (not long) and c.high >= lvl - EPS:
                    fi, px = j, max(lvl, c.open)
            if fi is None and ei + 2 < nb:
                fi, px = ei + 1, bars[ei + 2].open
            if fi is not None and fi < nb - 1:
                o = simulate(r, bars, fi, px, pdh, pdl, pmh, pml)
                if o:
                    pri["D"][i] = o

    res["policies"] = {}
    dayvecs = {}
    for p in ("B", "C", "D"):
        for gated in (False, True):
            def ok(i, _p=p, _g=gated):
                o = pri[_p].get(i)
                return o is not None and (o["sizeable"] or not _g)
            ev_ = [{"day": rows[i]["day"], "pnl": pri[p][i]["pnl"]}
                   for i in traded_idx if ok(i)]
            one_, miss = [], 0
            for d in sorted(cand):
                t = next((i for i in cand[d] if ok(i)), None)
                if t is None:
                    miss += 1
                else:
                    one_.append({"day": d, "pnl": pri[p][t]["pnl"]})
            tag = "%s_%s" % (p, "GATED" if gated else "ungated")
            res["policies"][tag] = {"everything": stats(ev_, n_days, all_days),
                                    "one_a_day": stats(one_, n_days, all_days),
                                    "one_a_day_days_missed": miss,
                                    "fills": len(ev_),
                                    "no_fills": len(traded_idx) - len(ev_)}
            v = day_vec(one_, all_days)
            res["policies"][tag]["one_a_day_ci"] = boot_ci(v)
            if gated:
                dayvecs[p] = v
            s = res["policies"][tag]["one_a_day"]
            print("   %-10s one-a-day %d trades (%d missed) %.1f%% win $%d/day ci%s "
                  "meanR %+.4f  %d/%d months  %d/%d weeks"
                  % (tag, s["trades"], miss, s["win_pct"], s["per_day"],
                     res["policies"][tag]["one_a_day_ci"], s["mean_r"],
                     s["months_green"], s["months"], s["weeks_green"], s["weeks"]),
                  flush=True)

    # ---- 4. PAIRED bootstrap: control minus policy, same days --------------
    ctrl = day_vec(oneg, all_days)
    res["paired_control_minus_policy_one_a_day_GATED"] = {}
    print("\n4. PAIRED per-day bootstrap, control minus policy "
          "(the grid does not do this):", flush=True)
    for p in ("B", "C", "D"):
        diff = [a - b for a, b in zip(ctrl, dayvecs[p])]
        m, lo, hi = boot_ci(diff)
        res["paired_control_minus_policy_one_a_day_GATED"][p] = {
            "mean_dollars_per_day": m, "ci95": [lo, hi],
            "excludes_zero": bool(lo > 0 or hi < 0)}
        print("   control - %s : $%d/day  95%% [$%d, $%d]  excludes zero: %s"
              % (p, m, lo, hi, lo > 0 or hi < 0), flush=True)

    # ---- 5. mean R vs win rate arithmetic ----------------------------------
    def rsplit(rs):
        wn = [x for x in rs if x > 0]
        ls = [x for x in rs if x < 0]
        sc = [x for x in rs if x == 0]
        w = len(wn) / max(1, len(wn) + len(ls))
        return {"n": len(rs), "wins": len(wn), "losses": len(ls), "scratches": len(sc),
                "mean_winner_R": round(statistics.fmean(wn), 4) if wn else None,
                "mean_loser_R": round(statistics.fmean(ls), 4) if ls else None,
                "worst_R": round(min(rs), 4), "best_R": round(max(rs), 4),
                "mean_R_actual": round(statistics.fmean(rs), 4),
                "mean_R_from_wT_minus_1mw": round(
                    w * (statistics.fmean(wn) if wn else 0)
                    + (1 - w) * (statistics.fmean(ls) if ls else 0), 4),
                "win_pct": round(w * 100, 1)}
    res["arithmetic"] = {
        "control_one_a_day_GATED": rsplit([r["pnl"] / RISK for r in oneg]),
        "control_everything_GATED": rsplit([r["pnl"] / RISK for r in evg]),
        "control_everything_book": rsplit([rows[i]["r"] for i in traded_idx]),
    }
    print("\n5. mean R arithmetic (w*avgWinner + (1-w)*avgLoser, actual not assumed):",
          flush=True)
    for k, v in res["arithmetic"].items():
        print("   %-28s win %.1f%%  avg winner %+.3fR  avg loser %+.3fR  -> %+0.4f "
              "(actual %+0.4f)  worst %.3fR  scratches %d"
              % (k, v["win_pct"], v["mean_winner_R"] or 0, v["mean_loser_R"] or 0,
                 v["mean_R_from_wT_minus_1mw"], v["mean_R_actual"], v["worst_R"],
                 v["scratches"]), flush=True)

    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("\nwrote %s" % OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
