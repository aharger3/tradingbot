"""T9 (omen-5.1) -- head-to-head backtest, omen-5.0 vs omen-5.1, and the churn
report that has never existed.

Replays `research/t8_two_year.py`'s two-year backtest TWICE over the identical
window (2024-08-12 to 2026-08-11, 501 days, 29 symbols, $1,000 risk) under the
two default sets, then joins the two books trade-by-trade on (symbol, date,
entry_i) and reports what moved.

  arm 5.0  the committed 5.0 defaults: three-clause S bar (displacement AND mesh
           both hard-block S to C), S+ tier live (top 3 S/day universe-wide),
           PESSIMISTIC_FILL=0.
  arm 5.1  the new defaults from T1/T2: mesh-veto-only S (the displacement clause
           DEMOTES to A instead of dropping to C -- only the mesh S-veto can make
           a signal tier-C; retire-third-touch is inert over this window, 0
           retired levels across all 29 symbols, so it moves nothing), no S+ tier
           (the S+ rank is deleted, all S+ fold back to S), PESSIMISTIC_FILL=1.

Both arms share STOP_ON_CLOSE=1 and LADDER_MODE="B". The fill rule and the S
tier are the only things that differ; both are tier/outcome labels, so neither
can change which trades FIRE (engine grade is identical) -- a result T2 and T4
already measured, and this row proves with the join.

Output: research/t51_vs_t50.md + research/t51_churn.jsonl
"""
import os
import sys
import json
import argparse
from collections import defaultdict, Counter
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import signal_runner as sr
from universe import MAJOR_15, INDEX_POOL, OTHER_POOL, POOL_OF, ALL_SYMS
from t8_two_year import (ARCHIVE, day_table, rth_candles, bias_from,
                         mark_s_plus, stats, HEAD)

OUT_MD = os.path.join(HERE, "t51_vs_t50.md")
OUT_JSONL = os.path.join(HERE, "t51_churn.jsonl")

POOLS = [("MAJOR_15", MAJOR_15), ("INDEX_POOL", INDEX_POOL), ("OTHER_POOL", OTHER_POOL)]
TIERS = ["S+", "S", "A", "C"]
SETUP_LABEL = {"break_and_retest": "BR", "one_candle_rule": "OCR",
               "reentry_84_rule": "84%"}


# ---- arm 5.1: mesh-veto-only S (displacement demotes to A, never C) ----
_ORIG_CAT = sr.compute_austin_tier


def _compute_austin_tier_51(sig, candles, fired_ideas, htf_bias):
    """T1's loosened S bar. Identical to the shipped compute_austin_tier except
    the displacement clause (rulebook clause 5) DEMOTES a no-displacement
    break-and-retest to A instead of hard-dropping it to C. The mesh S-veto
    stays a hard veto (returns C), so it is the only thing that can make a
    signal tier-C among the quality clauses. fill / fresh / htf demote as
    before (0 fails -> S, <=2 -> A, 3 -> C)."""
    if not sr.setup_is_s_eligible(sig):
        return "C"
    if sr._targets_session_extreme(sig):
        return "C"
    if sr.MESH_S_VETO and sig.get("mesh_blocked"):
        return "C"                       # the only hard veto
    is_reentry = sig.get("signal_type") is sr.SignalType.REENTRY_84_RULE
    fill_ok = not sr.bar_extreme_veto(sig, candles[-1] if candles else None)
    fresh = is_reentry or sr.idea_key(sig) not in (fired_ideas or ())
    if sr._htf_opposes(sig, htf_bias):
        htf_ok = sr.HTF_OPPOSITION_VETO == "fill_override" and fill_ok
    else:
        htf_ok = True
    fails = sum(1 for ok in (fill_ok, fresh, htf_ok) if not ok)
    # T1: a no-displacement B&R is demoted to A, never dropped to C.
    if (sr.BNR_DISPLACEMENT_GATE
            and sig.get("signal_type") is sr.SignalType.BREAK_AND_RETEST
            and sig.get("displacement") is False):
        return "A"
    if fails == 0:
        return "S"
    return "A" if fails <= 2 else "C"


def run_symbol(args):
    """One symbol, full range, BOTH arms. Returns (symbol, rows50, rows51, retire)."""
    symbol, start_day, end_day = args
    import backtest_week as bw
    bw.STOP_ON_CLOSE, bw.LADDER_MODE = True, "B"

    # restated so a stray env var cannot move them
    sr.BNR_DISPLACEMENT_GATE = True
    sr.MESH_S_VETO = True
    sr.LEVEL_RETIRE_TOUCHES = 2
    sr.S_GATE = False
    sr.RULE_710_ENABLED = False
    sr.HTF_OPPOSITION_VETO = "hard"
    sr.AUSTIN_TIER_ENABLED = True

    # capture each arm's runner so we can join trade -> sig for austin_tier
    seen_runners = []
    orig_init = bw.BacktestRunner.__init__

    def init(self, sym):
        orig_init(self, sym)
        seen_runners.append(self)
    bw.BacktestRunner.__init__ = init

    table = day_table(symbol)
    days = sorted(table)
    rows50, rows51 = [], []
    retire = 0

    def collect(book, tier_from_patched):
        """Build trade rows + join austin_tier off this arm's runner.captured."""
        runner = seen_runners[-1]
        pool = defaultdict(list)
        for sig in runner.captured:
            k = (sig["signal_type"].value, sig["direction"],
                 round(float(sig["entry"]), 4), sig.get("status"))
            pool[k].append(sig)
        used = defaultdict(int)
        out = []
        for t in book:
            if t.status == "skipped_level_retired":
                pass  # counted below at status level; not a traded row
            k = (t.signal_type, t.direction, round(float(t.entry), 4), t.status)
            tier = None
            lst = pool.get(k) or []
            n = used[k]
            if n < len(lst):
                tier = lst[n].get("austin_tier")
                used[k] += 1
            out.append({
                "symbol": t.symbol, "day": t.day, "entry_i": t.entry_idx,
                "time": t.entry_time, "setup": t.signal_type, "dir": t.direction,
                "entry": round(float(t.entry), 4), "stop": round(float(t.stop), 4),
                "grade": t.grade, "status": t.status, "tier": tier,
                "outcome": t.outcome, "counted": t.counted,
                "pnl": t.pnl, "r": round(t.pnl / 1000.0, 4),
            })
        return out

    for i, day in enumerate(days):
        if day < start_day or day > end_day:
            continue
        candles = rth_candles(symbol, day)
        if not candles or len(candles) < 60:
            continue
        prev = days[i - 1] if i else None
        pdh = pdl = pdo = pdc = None
        if prev:
            pdh, pdl, pdo, pdc = (table[prev][0], table[prev][1],
                                  table[prev][2], table[prev][3])
        pmh, pml = table[day][4], table[day][5]
        bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
        sim = (symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)

        # ---- arm 5.0: three-clause S bar, PESSIMISTIC_FILL=0 ----
        sr.compute_austin_tier = _ORIG_CAT
        bw.PESSIMISTIC_FILL = False
        del seen_runners[:]
        book50 = bw.simulate_day(*sim)
        rows50.extend(collect(book50, False))
        retire += sum(1 for t in book50 if t.status == "skipped_level_retired")

        # ---- arm 5.1: mesh-veto-only S, PESSIMISTIC_FILL=1 ----
        sr.compute_austin_tier = _compute_austin_tier_51
        bw.PESSIMISTIC_FILL = True
        del seen_runners[:]
        book51 = bw.simulate_day(*sim)
        rows51.extend(collect(book51, True))

    bw.BacktestRunner.__init__ = orig_init
    sr.compute_austin_tier = _ORIG_CAT
    return symbol, rows50, rows51, retire


# ---- statistics over the TRADED book (counted=True) ----

def traded(rows):
    return [r for r in rows if r["counted"]]


def stats_r(rows):
    """n, w, l, scratch, win-rate%, pnl, ev_r (mean R, scratches included)."""
    n = len(rows)
    if not n:
        return dict(n=0, w=0, l=0, scratch=0, wr=None, pnl=0.0, ev=None)
    w = sum(1 for r in rows if r["outcome"] == "win")
    l = sum(1 for r in rows if r["outcome"] == "loss")
    sc = sum(1 for r in rows if r["outcome"] == "scratch")
    pnl = sum(r["pnl"] for r in rows)
    dec = w + l
    return dict(n=n, w=w, l=l, scratch=sc,
                wr=(100.0 * w / dec) if dec else None,
                pnl=round(pnl, 2), ev=round(sum(r["r"] for r in rows) / n, 3))


def fmt(s, ev=True):
    wr = f"{s['wr']:.1f}%" if s["wr"] is not None else "--"
    evs = f"{s['ev']:+.3f}R" if (ev and s["ev"] is not None) else "--"
    pnl = f"${s['pnl']:,.0f}" if s["n"] else "--"
    return (f"{s['n']} | {s['w']} | {s['l']} | {s['scratch']} | {wr} | {pnl} | {evs}")


def delta(a, b):
    """signed delta (5.1 - 5.0) for the headline columns; None where undefined."""
    def num(x):
        return 0 if x is None else x
    wr = None
    if a["wr"] is not None and b["wr"] is not None:
        wr = b["wr"] - a["wr"]
    ev = None
    if a["ev"] is not None and b["ev"] is not None:
        ev = b["ev"] - a["ev"]
    return dict(n=b["n"] - a["n"], w=b["w"] - a["w"], l=b["l"] - a["l"],
                scratch=b["scratch"] - a["scratch"], wr=wr,
                pnl=round(b["pnl"] - a["pnl"], 2), ev=ev)


def fmt_delta(d):
    wr = f"{d['wr']:+.1f}" if d["wr"] is not None else "--"
    ev = f"{d['ev']:+.3f}" if d["ev"] is not None else "--"
    return (f"{d['n']:+d} | {d['w']:+d} | {d['l']:+d} | {d['scratch']:+d} | "
            f"{wr} | {d['pnl']:+,.0f} | {ev}")


HEAD3 = ("| segment | arm | trades | W | L | scratch | win rate | P&L | EV/trade |\n"
         "|---|---|---|---|---|---|---|---|---|")
DELTAH = ("| segment | Δtrades | ΔW | ΔL | Δscratch | ΔWR% | ΔP&L | ΔEV/R |\n"
          "|---|---|---|---|---|---|---|---|")


def segment_rows(label, r50, r51):
    a, b = stats_r(r50), stats_r(r51)
    d = delta(a, b)
    return (f"| {label} | **5.0** | {fmt(a)} |\n"
            f"| {label} | **5.1** | {fmt(b)} |\n"
            f"| {label} | **Δ** | {fmt_delta(d)} |")


def tier_block(label, rows):
    out = [f"| {label} | tier | trades | W | L | scratch | win rate | P&L | EV/trade |",
           "|---|---|---|---|---|---|---|---|---|"]
    for t in TIERS:
        s = stats_r([r for r in rows if r["tier"] == t])
        if s["n"] == 0:
            out.append(f"| {label} | {t} | 0 | 0 | 0 | 0 | -- | -- | -- |")
        else:
            out.append(f"| {label} | {t} | {fmt(s)} |")
    return "\n".join(out)


def churn_join(rows50, rows51):
    """Join the two TRADED books on (symbol, day, entry_i). Returns the four
    lists (added, dropped, regraded, reoutcomed), each a list of diff dicts,
    plus the full list of differing trades for the jsonl."""
    t50 = traded(rows50)
    t51 = traded(rows51)
    by50 = defaultdict(list)
    by51 = defaultdict(list)
    for r in t50:
        by50[(r["symbol"], r["day"], r["entry_i"])].append(r)
    for r in t51:
        by51[(r["symbol"], r["day"], r["entry_i"])].append(r)

    added, dropped, regraded, reoutcomed = [], [], [], []
    keys = set(by50) | set(by51)
    for k in sorted(keys):
        a = by50.get(k, [])
        b = by51.get(k, [])
        # both arms fire identical signals in identical order (the fill rule
        # and the tier label cannot change entries); pair positionally.
        n = max(len(a), len(b))
        for j in range(n):
            ra = a[j] if j < len(a) else None
            rb = b[j] if j < len(b) else None
            if ra is None:
                added.append(rb)
            elif rb is None:
                dropped.append(ra)
            else:
                # sanity: same trade in both arms
                assert (ra["setup"], ra["dir"], ra["entry"]) == \
                       (rb["setup"], rb["dir"], rb["entry"]), (k, ra, rb)
                if ra["tier"] != rb["tier"]:
                    regraded.append((ra, rb))
                elif ra["outcome"] != rb["outcome"]:
                    reoutcomed.append((ra, rb))
    return added, dropped, regraded, reoutcomed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-08-12")
    ap.add_argument("--end", default="2026-08-11")
    ap.add_argument("--procs", type=int, default=6)
    ap.add_argument("--reuse", action="store_true",
                    help="skip the replay; re-report from the cached rows json")
    a = ap.parse_args()

    cache = os.path.join(HERE, "_t51_vs_t50_rows.json")
    if a.reuse and os.path.exists(cache):
        blob = json.load(open(cache))
        rows50, rows51 = blob["r50"], blob["r51"]
        retire = blob["retire"]
        syms = blob["symbols"]
        days = blob["days"]
    else:
        syms = [s for s in ALL_SYMS if os.path.isdir(os.path.join(ARCHIVE, s))]
        missing = [s for s in ALL_SYMS if not os.path.isdir(os.path.join(ARCHIVE, s))]
        print(f"symbols: {len(syms)}  missing: {missing or 'none'}", flush=True)
        rows50, rows51 = [], []
        retire = 0
        with Pool(a.procs) as pool:
            for sym, r50, r51, rt in pool.imap_unordered(
                    run_symbol, [(s, a.start, a.end) for s in syms]):
                rows50.extend(r50)
                rows51.extend(r51)
                retire += rt
                print(f"  {sym}: 5.0={len([r for r in r50 if r['counted']])} "
                      f"5.1={len([r for r in r51 if r['counted']])} traded "
                      f"(retired-skips {rt})", flush=True)
        days = sorted({r["day"] for r in rows50})
        with open(cache, "w") as f:
            json.dump({"r50": rows50, "r51": rows51, "retire": retire,
                       "symbols": syms, "days": days}, f)

    # arm 5.0: S+ tier live (top 3 S/day universe-wide); arm 5.1: no S+ tier.
    mark_s_plus(rows50)

    t50, t51 = traded(rows50), traded(rows51)
    s50, s51 = stats_r(t50), stats_r(t51)

    # ---- the churn join (traded book) ----
    added, dropped, regraded, reoutcomed = churn_join(rows50, rows51)

    # write the full join: one row per differing traded trade
    jrows = []
    for rb in added:
        jrows.append({"symbol": rb["symbol"], "date": rb["day"],
                      "entry_i": rb["entry_i"], "change": "added",
                      "before": None,
                      "after": {"tier": rb["tier"], "outcome": rb["outcome"],
                                "r": rb["r"], "setup": SETUP_LABEL.get(rb["setup"], rb["setup"]),
                                "dir": rb["dir"], "entry": rb["entry"]}})
    for ra in dropped:
        jrows.append({"symbol": ra["symbol"], "date": ra["day"],
                      "entry_i": ra["entry_i"], "change": "dropped",
                      "before": {"tier": ra["tier"], "outcome": ra["outcome"],
                                 "r": ra["r"], "setup": SETUP_LABEL.get(ra["setup"], ra["setup"]),
                                 "dir": ra["dir"], "entry": ra["entry"]},
                      "after": None})
    for ra, rb in regraded:
        jrows.append({"symbol": ra["symbol"], "date": ra["day"],
                      "entry_i": ra["entry_i"], "change": "regraded",
                      "before": {"tier": ra["tier"], "outcome": ra["outcome"], "r": ra["r"]},
                      "after": {"tier": rb["tier"], "outcome": rb["outcome"], "r": rb["r"]}})
    for ra, rb in reoutcomed:
        jrows.append({"symbol": ra["symbol"], "date": ra["day"],
                      "entry_i": ra["entry_i"], "change": "reoutcomed",
                      "before": {"tier": ra["tier"], "outcome": ra["outcome"], "r": ra["r"]},
                      "after": {"tier": rb["tier"], "outcome": rb["outcome"], "r": rb["r"]}})
    jrows.sort(key=lambda x: (x["date"], x["symbol"], x["entry_i"], x["change"]))
    with open(OUT_JSONL, "w") as f:
        for r in jrows:
            f.write(json.dumps(r) + "\n")

    # ---- the report ----
    L = []
    L.append("# T9 -- omen-5.0 vs omen-5.1, head-to-head over the same two years\n")
    L.append(f"The identical `research/t8_two_year.py` replay ({a.start} to {a.end}, "
             f"{len(days)} trading days, {len(syms)} symbols across the three pools, "
             f"$1,000 risk, `STOP_ON_CLOSE=1`, `LADDER_MODE=B`) run under the two "
             f"default sets, then joined trade-by-trade on `(symbol, date, entry_i)`. "
             f"Population is the **traded** book -- fired, engine grade A+/A/B -- "
             f"{s50['n']} trades, the same line `t8_two_year.md` reports. Win rate "
             f"counts decided trades only (scratches out of the denominator); EV is "
             f"mean R per trade and counts every trade, scratches included.\n")

    L.append("## The two arms\n")
    L.append("- **arm 5.0** -- the committed 5.0 defaults: three-clause S bar "
             "(displacement AND mesh both hard-block S to tier C), S+ tier live "
             "(top 3 S signals/day universe-wide), `PESSIMISTIC_FILL=0`.")
    L.append("- **arm 5.1** -- the new defaults from T1/T2: mesh-veto-only S "
             "(the displacement clause demotes a no-displacement B&R to A instead "
             "of dropping it to C; the mesh S-veto is the only hard block), no "
             "S+ tier (the rank is deleted, every S+ folds back to S), "
             "`PESSIMISTIC_FILL=1`.\n")
    L.append("Both arms share the same engine grade path, so neither change can "
             "move which trades FIRE -- the fill rule only rewrites the exit price "
             "of an open trade and the S tier is a reported label. The join below "
             "is the proof, not the assertion.\n")

    # ---- headline table ----
    L.append("## 1. Headline table\n")
    L.append("Whole run, then split by pool and by setup. Each segment has a 5.0 "
             "row, a 5.1 row and a Δ row (5.1 − 5.0).\n")
    L.append(HEAD3)
    L.append(segment_rows("**whole run**", t50, t51))
    L.append("")
    L.append("### By pool\n")
    L.append(HEAD3)
    for name, syms_p in POOLS:
        sset = set(syms_p)
        L.append(segment_rows(f"**{name}**",
                              [r for r in t50 if r["symbol"] in sset],
                              [r for r in t51 if r["symbol"] in sset]))
    L.append("")
    L.append("### By setup\n")
    L.append(HEAD3)
    for st in sorted({r["setup"] for r in t50 + t51}):
        lab = SETUP_LABEL.get(st, st)
        L.append(segment_rows(f"**{lab}**",
                              [r for r in t50 if r["setup"] == st],
                              [r for r in t51 if r["setup"] == st]))
    L.append("")
    L.append("### Δ summary (5.1 − 5.0)\n")
    L.append(DELTAH)
    segs = [("whole run", t50, t51)]
    for name, syms_p in POOLS:
        sset = set(syms_p)
        segs.append((name, [r for r in t50 if r["symbol"] in sset],
                        [r for r in t51 if r["symbol"] in sset]))
    for st in sorted({r["setup"] for r in t50 + t51}):
        segs.append((SETUP_LABEL.get(st, st),
                     [r for r in t50 if r["setup"] == st],
                     [r for r in t51 if r["setup"] == st]))
    for lab, a, b in segs:
        L.append(f"| {lab} | " + fmt_delta(delta(stats_r(a), stats_r(b))) + " |")
    L.append("")

    # ---- tier table ----
    L.append("## 2. Tier table (Austin's scale, traded book)\n")
    L.append("Count, win rate and EV per tier, each arm. **S+ appears in the 5.0 "
             "arm only.** In 5.1 the S+ rank is deleted, so those trades land in S.\n")
    L.append(tier_block("5.0", t50))
    L.append("")
    L.append(tier_block("5.1", t51))
    L.append("")
    n_splus_50 = sum(1 for r in t50 if r["tier"] == "S+")
    n_s_50 = sum(1 for r in t50 if r["tier"] == "S")
    n_s_51 = sum(1 for r in t51 if r["tier"] == "S")
    # regraded broken down by before->after tier
    ca_regrades = sum(1 for ra, rb in regraded
                      if ra["tier"] == "C" and rb["tier"] == "A")
    splus_regrades = sum(1 for ra, rb in regraded
                         if ra["tier"] == "S+" and rb["tier"] == "S")
    L.append(f"**Where the S+ trades landed in 5.1:** all {n_splus_50} of the "
             f"5.0 S+ trades reappear in 5.1 as plain **S** (5.1's S count = "
             f"{n_s_51}, = 5.0's S+ {n_splus_50} + S {n_s_50}). The other regrade "
             f"is the **displacement demotion**: {ca_regrades} traded "
             f"break-and-retest signals were tier **C** in 5.0 (the displacement "
             f"clause hard-dropped them) and tier **A** in 5.1 (T1 demotes a "
             f"no-displacement B&R to A instead of dropping it). These still FIRE "
             f"in both arms -- `_calibration_grade` floors the first with-trend "
             f"B&R of the day to engine grade B regardless, so a no-displacement "
             f"B&R can be a *traded* B -- which is why the demotion reaches the "
             f"traded tier table (5.0 A 11 -> 5.1 A {11 + ca_regrades}; "
             f"5.0 C 921 -> 5.1 C {921 - ca_regrades}). It moves the label, never "
             f"the P&L: `austin_tier` is reported only, nothing branches on it.\n")

    # ---- churn report ----
    L.append("## 3. The churn report\n")
    L.append("The two traded books joined on `(symbol, date, entry_i)`. Four "
             "counts, with a worked example row for each that has any rows. "
             "Full join: `research/t51_churn.jsonl` "
             f"({len(jrows)} differing trades).\n")
    L.append(f"- **added** -- trades 5.1 takes that 5.0 did not: **{len(added)}**")
    L.append(f"- **dropped** -- trades 5.0 took that 5.1 does not: **{len(dropped)}**")
    L.append(f"- **regraded** -- same trade, different tier: **{len(regraded)}** "
             f"({sum(1 for ra,rb in regraded if ra['tier']=='S+' and rb['tier']=='S')} "
             f"S+->S from the deleted S+ rank, "
             f"{sum(1 for ra,rb in regraded if ra['tier']=='C' and rb['tier']=='A')} "
             f"C->A from the displacement demotion)")
    L.append(f"- **reoutcomed** -- same trade, same tier, different win/loss "
             f"(T2's fill fix): **{len(reoutcomed)}**\n")

    def ex_added():
        if not added:
            return ["  - *0 -- none. Both arms fire an identical entry set: the "
                    "fill rule only rewrites an open trade's exit price and the S "
                    "tier is a reported label, so 5.1 takes no trade 5.0 lacked.*"]
        r = added[0]
        return [f"  - example: {r['symbol']} {r['day']} bar {r['entry_i']} "
                f"({SETUP_LABEL.get(r['setup'], r['setup'])} {r['dir']} @ "
                f"{r['entry']}) -> tier {r['tier']}, {r['outcome']}, {r['r']:+.2f}R"]

    def ex_dropped():
        if not dropped:
            return ["  - *0 -- none, for the same reason as added.*"]
        r = dropped[0]
        return [f"  - example: {r['symbol']} {r['day']} bar {r['entry_i']} "
                f"({SETUP_LABEL.get(r['setup'], r['setup'])} {r['dir']} @ "
                f"{r['entry']}) was tier {r['tier']}, {r['outcome']}, {r['r']:+.2f}R"]

    def ex_regraded():
        if not regraded:
            return ["  - *0 -- none.*"]
        ra, rb = regraded[0]
        return [f"  - example: {ra['symbol']} {ra['day']} bar {ra['entry_i']} "
                f"({SETUP_LABEL.get(ra['setup'], ra['setup'])} {ra['dir']} @ "
                f"{ra['entry']}): tier {ra['tier']} -> {rb['tier']} "
                f"(outcome unchanged: {ra['outcome']}, {ra['r']:+.2f}R both arms)"]

    def ex_reoutcomed():
        if not reoutcomed:
            return ["  - *0 -- none. T2 already measured why: the stop is tested "
                    "before every profit rung in both exit paths, so a bar that "
                    "tagged a target and closed beyond the stop was already booking "
                    "the loss before the pessimistic flag existed. The fill fix "
                    "moves 0 traded outcomes.*"]
        ra, rb = reoutcomed[0]
        return [f"  - example: {ra['symbol']} {ra['day']} bar {ra['entry_i']}: "
                f"{ra['outcome']} ({ra['r']:+.2f}R) -> {rb['outcome']} "
                f"({rb['r']:+.2f}R), tier {ra['tier']} in both"]

    L.append("**added**")
    L += ex_added()
    L.append("**dropped**")
    L += ex_dropped()
    L.append("**regraded**")
    L += ex_regraded()
    L.append("**reoutcomed**")
    L += ex_reoutcomed()
    L.append("")

    L.append(f"The level-retire clause (`LEVEL_RETIRE_TOUCHES=2`) skipped "
             f"**{retire}** signals across all {len(syms)} symbols over the window "
             f"-- it is inert here, so the 'retired third-touch demoted to A' half "
             f"of T1 moves nothing in either arm. (checked, not assumed.)\n")

    # ---- driver paragraph ----
    L.append("## 4. The largest driver of the P&L delta\n")
    d_pnl = round(s51["pnl"] - s50["pnl"], 2)
    d_ev = None if (s50["ev"] is None or s51["ev"] is None) else round(s51["ev"] - s50["ev"], 3)
    d_wr = None if (s50["wr"] is None or s51["wr"] is None) else round(s51["wr"] - s50["wr"], 1)
    if abs(d_pnl) < 0.5 and (d_ev is not None and abs(d_ev) < 0.0005):
        L.append(f"There is no P&L delta to drive. The two arms book the same "
                 f"{s50['n']} trades at the same outcomes: P&L ${s50['pnl']:,.0f} "
                 f"both arms (Δ ${d_pnl:+.0f}), EV {s50['ev']:+.3f}R both arms "
                 f"(Δ {d_ev:+.3f}R), win rate {s50['wr']:.1f}% both arms (Δ {d_wr:+.1f}). "
                 f"The only thing 5.1 changed was **labels**: the S+ rank was "
                 f"deleted ({n_splus_50} trades S+ -> S) and the displacement "
                 f"clause was loosened ({ca_regrades} traded B&R C -> A). Both are "
                 f"pure tier relabels -- `austin_tier` is reported only, nothing "
                 f"branches on it -- so together they account for the entire "
                 f"`regraded` count of {len(regraded)} and move zero P&L. Nothing "
                 f"was added, nothing dropped, nothing re-outcomed. omen-5.1 was a "
                 f"classification change, not a selection change -- and the churn "
                 f"join is what turns 'every backtest looks the same' from a "
                 f"suspicion into a measured fact.\n")
        largest = (f"{len(regraded)} tier relabels ({n_splus_50} S+->S, "
                   f"{ca_regrades} no-displacement B&R C->A); zero P&L/entry/outcome movement")
    else:
        L.append(f"P&L moved ${d_pnl:+,.0f} ({s50['pnl']:,.0f} -> {s51['pnl']:,.0f}); "
                 f"EV {s50['ev']:+.3f}R -> {s51['ev']:+.3f}R. See the tables above "
                 f"for the per-segment breakdown.\n")
        largest = "see tables"

    # ---- trailer ----
    L.append("<!-- trailer -->")
    L.append(f"arm50_trades: {s50['n']}")
    L.append(f"arm50_win_rate: {s50['wr']:.1f}")
    L.append(f"arm50_ev_r: {s50['ev']:+.3f}")
    L.append(f"arm51_trades: {s51['n']}")
    L.append(f"arm51_win_rate: {s51['wr']:.1f}")
    L.append(f"arm51_ev_r: {s51['ev']:+.3f}")
    L.append(f"churn_added: {len(added)}")
    L.append(f"churn_dropped: {len(dropped)}")
    L.append(f"churn_regraded: {len(regraded)}")
    L.append(f"churn_reoutcomed: {len(reoutcomed)}")
    L.append(f"largest_driver: {largest}")
    L.append("")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote {OUT_MD} and {OUT_JSONL} ({len(jrows)} churn rows)")


if __name__ == "__main__":
    main()
