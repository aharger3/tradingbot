"""R2 referee, PASS 2 -- independent re-derivation of the REPAIRED
research/g211_reconcile_ladder.py (builder commit 15a729ce, repairing 3ae279a0
after referee b746e45e).

Pass 1's script is research/r2_referee.py and is untouched. Nothing here
imports the builder's script for any statistic; every number is recomputed
from the committed stamped books with local code.

WHAT THIS ADDS OVER PASS 1:

1. Re-derives every forward-ladder row off its own committed book (own stats
   code) and re-runs both spec verify assertions.

2. Checks the repair's NEW H1/H2 table for the biggest step against the
   halves actually computed from the step-1 and step-2 books.

3. SIM D -- the experiment neither the builder nor pass 1 ran, and the one
   that decides the row's headline. The headline sentence says the
   scale-out-and-trail exit costs $5,550/day. But the step-1 book is NOT the
   shipped engine on a flat target: it is g90_fill_arms._walk, a custom arm
   whose stop triggers on a CLOSE beyond the level and fills AT the level, with
   no disaster stop and no stop_rule.stop_fill_price(). The step-2 book is the
   real backtest_week.simulate_day. Step 1 -> step 2 therefore swaps the exit
   ladder AND the whole trade-management substrate at once.

   SIM D holds the substrate at step 2's value and the exit at step 1's:
   the REAL engine, ENTRY_FILL=next_open, OMEN_SCALE_PLAN=none (backtest_week's
   own blind-2R target, its line ~1447), same window, same 29 symbols, 84%
   re-entries excluded, every grade.

     fwd_1 -> SIM D  = the substrate alone
     SIM D -> fwd_2  = the scale-out ladder alone   (single flag: SCALE_PLAN)

4. Replays backtest_week's dedupe loop offline on SIM D's captured candidates,
   to answer "could a FILTERED step have needed re-simulation?" -- the
   suppression claim at backtest_week ~line 1400 is grade-blind, so a C-grade
   fire claims the window. Counts how many NON-C signals a genuine C-gated
   engine run would release that a post-hoc row filter can never produce.

Usage:  python research/r2_referee_pass2.py --procs 8
        python research/r2_referee_pass2.py --no-simd
"""
import os
import sys
import json
import gzip
import argparse
import time
from collections import defaultdict
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

TAPE = os.path.join(HERE, "tape")
FWD = [
    (0, "start_next_open_blind2r_noC_no84"),
    (1, "add_C_grades"),
    (2, "swap_exit_shipped_ladder"),
    (3, "add_84_reentries"),
    (4, "switch_fill_close"),
    (5, "apply_size_gate"),
    (6, "dedupe_day_policy_shipped_noop"),
    (7, "window_500_to_498"),
    (8, "universe_29_to_11"),
]


def book(n, name):
    p = os.path.join(TAPE, f"reconcile_fwd_{n}_{name}.json.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def stats(rows, denom_rows=None):
    """$/day = sum(pnl) / distinct trading days in `denom_rows` (default: the
    rows themselves) -- g90_fill_arms.arm_stats's convention."""
    dr = rows if denom_rows is None else denom_rows
    f = [r for r in rows if r.get("r") is not None]
    n = len(f)
    if not n:
        return dict(n=0)
    w = sum(1 for r in f if r.get("outcome") == "win")
    l = sum(1 for r in f if r.get("outcome") == "loss")
    tot_r = sum(r["r"] for r in f)
    tot_pnl = sum(r["pnl"] for r in f)
    pos = [r["r"] for r in f if r["r"] > 0]
    neg = [r["r"] for r in f if r["r"] <= 0]
    mon = defaultdict(float)
    for r in f:
        mon[r["day"][:7]] += r["r"]
    days = len({r["day"] for r in dr})
    mu = tot_r / n
    var = sum((r["r"] - mu) ** 2 for r in f) / (n - 1) if n > 1 else 0.0
    return dict(
        n=n, wins=w, losses=l,
        wr=round(100.0 * w / (w + l), 1) if (w + l) else None,
        mean_r=round(mu, 4), ci95=round(1.96 * (var / n) ** 0.5, 4),
        avg_win=round(sum(pos) / len(pos), 4) if pos else None,
        avg_loss=round(sum(neg) / len(neg), 4) if neg else None,
        months=len(mon), green=sum(1 for v in mon.values() if v > 0),
        days=days, dollar_day=round(tot_pnl / days, 2) if days else None,
        worst_r=round(min(r["r"] for r in f), 4),
    )


def halves(rows, denom_rows=None):
    dr = rows if denom_rows is None else denom_rows
    ds = sorted({r["day"] for r in dr})
    if len(ds) < 2:
        return None, None, None
    mid = ds[len(ds) // 2]
    return (stats([r for r in rows if r["day"] < mid], [r for r in dr if r["day"] < mid]),
            stats([r for r in rows if r["day"] >= mid], [r for r in dr if r["day"] >= mid]),
            mid)


# ------------------------------------------------------------------ SIM D
def run_symbol_simd(args):
    symbol, start_day, end_day = args
    os.environ["ENTRY_FILL"] = "next_open"
    os.environ["OMEN_SCALE_PLAN"] = "none"
    for _m in ("entry_fill", "signal_runner", "backtest_week"):
        sys.modules.pop(_m, None)
    import backtest_week as bw
    import entry_fill as ef
    from t8_two_year import day_table, rth_candles, bias_from

    assert bw.SCALE_PLAN is None, "SCALE_PLAN should be None, got %r" % bw.SCALE_PLAN
    assert ef.ENTRY_FILL == "next_open", "ENTRY_FILL=%r" % ef.ENTRY_FILL

    seen_runners = []
    base_runner = bw.BacktestRunner

    class RefRunner(base_runner):
        def __init__(self, sym):
            super().__init__(sym)
            self._marks = []
            seen_runners.append(self)

        def detect_signals(self):
            bar_idx = len(self.candles) - 1
            before = len(self.captured)
            out = super().detect_signals()
            for sig in self.captured[before:]:
                idea = (sig.get("stop_level_name")
                        if sig["signal_type"].value == "break_and_retest"
                        else round(sig["stop"], 2))
                self._marks.append((bar_idx,
                                    (sig["signal_type"].value, sig["direction"], idea),
                                    sig.get("status"), sig.get("grade")))
            return out

    bw.BacktestRunner = RefRunner

    table = day_table(symbol)
    days = sorted(table)
    rows, marks = [], []
    for i, day in enumerate(days):
        if day < start_day or day > end_day:
            continue
        candles = rth_candles(symbol, day)
        if not candles or len(candles) < 60:
            continue
        prev = days[i - 1] if i else None
        pdh = pdl = pdo = pdc = None
        if prev:
            pdh, pdl, pdo, pdc = table[prev][0], table[prev][1], table[prev][2], table[prev][3]
        pmh, pml = table[day][4], table[day][5]
        bias = bias_from([table[d][3] for d in days[max(0, i - 40):i]])
        del seen_runners[:]
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, None)
        if seen_runners:
            marks.append(list(seen_runners[-1]._marks))
        for t in trades:
            if t.status != "fired" or t.signal_type == "reentry_84_rule":
                continue
            rows.append({
                "sym": symbol, "day": day, "entry_time": t.entry_time,
                "side": t.direction, "setup": t.signal_type, "grade": t.grade,
                "reentry": False, "filled": True,
                "entry": round(t.entry, 4), "stop": round(t.stop, 4),
                "exit": round(t.exit_price, 4) if t.exit_price is not None else None,
                "outcome": t.outcome,
                "r": round(t.pnl / bw.RISK_DOLLARS, 4), "pnl": round(t.pnl, 2),
            })
    bw.BacktestRunner = base_runner
    return symbol, rows, marks


def dedupe_replay(marks, contig=2, drop_c=False):
    """backtest_week's dedupe loop, offline. Returns (all_survivors,
    non_c_survivors). drop_c=True models a real C-gated engine run: a C fire no
    longer claims or extends its suppression window."""
    tot = non_c = 0
    for ms in marks:
        seen = {}
        for i, key, status, grade in ms:
            fired = (status == "fired")
            if drop_c and grade == "C":
                fired = False
            if key in seen and i - seen[key] < contig:
                if fired:
                    seen[key] = i
                continue
            if fired:
                seen[key] = i
                tot += 1
                if grade != "C":
                    non_c += 1
    return tot, non_c


SIMD_PATH = os.path.join(TAPE, "r2ref_simd_next_open_blind2r_real_engine.json.gz")


def stamp_with_env(hash_rows, fill, exit_plan, **kw):
    """book_stamp.stamp() re-derives its flag block by importing entry_fill /
    backtest_week fresh in the CALLING process, so a stamp taken in main (which
    never set ENTRY_FILL / OMEN_SCALE_PLAN -- only the workers did) records
    main's env-unset defaults, not the book's. Same defect the builder hit and
    fixed; my first SIM D book hit it too. Set the env, evict the cached
    modules, stamp, restore."""
    from book_stamp import stamp as bstamp
    prev_ef = os.environ.get("ENTRY_FILL")
    prev_sp = os.environ.get("OMEN_SCALE_PLAN")
    if fill == "next_open":
        os.environ["ENTRY_FILL"] = "next_open"
    else:
        os.environ.pop("ENTRY_FILL", None)
    if exit_plan.startswith("blind_2R"):
        os.environ["OMEN_SCALE_PLAN"] = "none"
    else:
        os.environ.pop("OMEN_SCALE_PLAN", None)
    for _m in ("entry_fill", "signal_runner", "backtest_week"):
        sys.modules.pop(_m, None)
    try:
        return bstamp(hash_rows, entry_fill=fill, exit_plan=exit_plan, **kw)
    finally:
        for k, v in (("ENTRY_FILL", prev_ef), ("OMEN_SCALE_PLAN", prev_sp)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for _m in ("entry_fill", "signal_runner", "backtest_week"):
            sys.modules.pop(_m, None)


def restamp_simd():
    """Re-stamp an already-written SIM D book with the correct flag block,
    without re-running the 75s replay."""
    with gzip.open(SIMD_PATH, "rt", encoding="utf-8") as f:
        d = json.load(f)
    rows = d["trades"]
    m = d["meta"]
    hash_rows = [dict(r, status="fired") for r in rows]
    m["stamp"] = stamp_with_env(
        hash_rows, m["fill"], m["exit_plan"], pool=m["pool"], window=m["window"],
        step=m["step"], step_name=m["step_name"], script=m["script"])
    with gzip.open(SIMD_PATH, "wt", encoding="utf-8") as f:
        json.dump(d, f)
    fl = m["stamp"]["flags"]
    print(f"restamped {SIMD_PATH}")
    print(f"  ENTRY_FILL={fl.get('entry_fill.ENTRY_FILL')!r} "
          f"SCALE_PLAN={fl.get('backtest_week.SCALE_PLAN')!r} "
          f"commit={m['stamp']['git']['commit'][:8]} "
          f"dirty_py={m['stamp']['git']['dirty_py_count']} "
          f"dirty_engine={m['stamp']['git']['dirty_engine_py']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--no-simd", action="store_true")
    ap.add_argument("--restamp", action="store_true",
                    help="re-stamp the existing SIM D book and exit")
    a = ap.parse_args()
    if a.restamp:
        restamp_simd()
        return

    print("=" * 78)
    print("1. FORWARD LADDER RE-DERIVED FROM THE COMMITTED BOOKS (own stats code)")
    print("=" * 78)
    books = {}
    for n, name in FWD:
        d = book(n, name)
        books[n] = d
        s = stats(d["trades"])
        m = d["meta"]
        print(f"step {n} {name:38s} fill={m['fill']:9s} exit={m['exit_plan']:14s} "
              f"pool={m['pool']:7s} n={s['n']:6d} wr={s['wr']}% meanR={s['mean_r']:+.4f} "
              f"(+/-{s['ci95']}) aw={s['avg_win']} al={s['avg_loss']} "
              f"green={s['green']}/{s['months']} days={s['days']} "
              f"$/day=${s['dollar_day']:,.2f} worstR={s['worst_r']}")

    print()
    print("=" * 78)
    print("2. STAMP DIFF fwd_1 -> fwd_2 (the biggest step's two endpoints)")
    print("=" * 78)
    f1, f2 = books[1]["meta"]["stamp"], books[2]["meta"]["stamp"]
    for k in sorted(set(f1["flags"]) | set(f2["flags"])):
        v1, v2 = f1["flags"].get(k, "<absent>"), f2["flags"].get(k, "<absent>")
        if v1 != v2:
            print(f"  FLAG DIFFERS  {k}: {v1!r} -> {v2!r}")
    print(f"  stamp commit fwd_1={f1['git']['commit'][:8]} fwd_2={f2['git']['commit'][:8]} "
          f"dirty_py={f1['git']['dirty_py_count']} engine_dirty={f1['git']['dirty_engine_py']}")
    print("  CAVEAT: the stamp records env-derived flags only. fwd_0/fwd_1's rows were")
    print("  not produced by backtest_week at all -- g90_fill_arms._walk made them.")
    print("  The stamp still prints DISASTER_STOP=True / STOP_ON_CLOSE=True /")
    print("  PESSIMISTIC_FILL=True for those books; none of the three ran.")

    print()
    print("=" * 78)
    print("3. BIGGEST-STEP CLAIM AND THE REPAIR'S NEW H1/H2 TABLE")
    print("=" * 78)
    s1, s2 = stats(books[1]["trades"]), stats(books[2]["trades"])
    print(f"  step1 ${s1['dollar_day']:,.2f}/day  step2 ${s2['dollar_day']:,.2f}/day  "
          f"delta ${s2['dollar_day'] - s1['dollar_day']:,.2f}/day")
    deltas = []
    for (n0, _), (n1, nm1) in zip(FWD, FWD[1:]):
        d0 = stats(books[n0]["trades"])["dollar_day"]
        d1 = stats(books[n1]["trades"])["dollar_day"]
        deltas.append((d1 - d0, n0, n1, nm1))
        print(f"    step {n0}->{n1} {nm1:38s} {d1 - d0:+12,.2f} $/day")
    print(f"  biggest drop: step {min(deltas)[1]}->{min(deltas)[2]} ({min(deltas)[3]})")
    print()
    print("  halves, computed per step from its own book (midpoint of its own window):")
    for n in (1, 2, 7):
        h1, h2, mid = halves(books[n]["trades"])
        print(f"    step {n} (mid {mid}): H1 ${h1['dollar_day']:,.2f} "
              f"(n={h1['n']}, {h1['months']}mo)  H2 ${h2['dollar_day']:,.2f} "
              f"(n={h2['n']}, {h2['months']}mo)")
    print("  The repaired report prints, for the biggest step, 'before' = H1 $-85 /")
    print("  H2 $-1,518. Compare step 7's halves above, and step 1's.")

    print()
    print("=" * 78)
    print("4. VERIFY ASSERTIONS, RE-RUN INDEPENDENTLY")
    print("=" * 78)
    with gzip.open(os.path.join(TAPE, "fillarms_next_open_full29.json.gz"), "rt",
                   encoding="utf-8") as f:
        r1_rows = json.load(f)["trades"]

    def ids(rows):
        return sorted((r["sym"], r["day"], r["entry_time"],
                       round(r.get("entry") or 0, 4),
                       round(r["r"], 4) if r.get("r") is not None else None)
                      for r in rows)
    step0 = books[0]["trades"]
    print(f"  verify 1 full29: step0 {len(step0)} vs R1 {len(r1_rows)} -- "
          f"{'MATCH' if ids(step0) == ids(r1_rows) else 'MISMATCH'}")
    from universe import CORE_SYMBOLS
    core = set(CORE_SYMBOLS)
    s0c = [r for r in step0 if r["sym"] in core]
    r1c = [r for r in r1_rows if r["sym"] in core]
    print(f"  verify 1 core11: step0 {len(s0c)} vs R1 {len(r1c)} -- "
          f"{'MATCH' if ids(s0c) == ids(r1c) else 'MISMATCH'}")

    with open(os.path.join(HERE, "bt2y_trades_retest_on.json"), encoding="utf-8") as f:
        ro = json.load(f)
    ro_fired = [r for r in ro["trades"] if r.get("status") == "fired"]
    ro_dd = sum(r["pnl"] for r in ro_fired) / ro["meta"]["sessions"]
    win = (ro["meta"]["first"], ro["meta"]["last"])
    s7u = stats([r for r in books[4]["trades"] if win[0] <= r["day"] <= win[1]])
    gap = abs(s7u["dollar_day"] - ro_dd) / abs(ro_dd)
    print(f"  verify 2: step7 unsized ${s7u['dollar_day']:,.2f}/day ({s7u['n']} rows) vs "
          f"retest_on ${ro_dd:,.2f}/day ({len(ro_fired)} fired / {ro['meta']['sessions']} "
          f"sessions) -- gap {gap*100:.1f}% -- "
          f"{'WITHIN 1%' if gap <= 0.01 else 'DOES NOT RECONCILE'}")
    print(f"    retest_on meta: commit={ro['meta'].get('commit')} "
          f"halted={ro['meta'].get('halted')} of signals={ro['meta'].get('signals')}")

    if a.no_simd:
        return

    print()
    print("=" * 78)
    print("5. SIM D -- real engine, next_open fill, blind 2R target, NO ladder")
    print("=" * 78)
    from universe import ARCHIVE_DIR
    import g211_reconcile_ladder as g
    syms = [s for s in g.FULL_POOL if os.path.isdir(os.path.join(ARCHIVE_DIR, s))]
    end_day = g.latest_archived_day(syms)
    start_day = g.two_years_back(end_day)
    print(f"  window {start_day} -> {end_day}, {len(syms)} symbols")
    assert (start_day, end_day) == (books[1]["meta"]["window"]["start"],
                                    books[1]["meta"]["window"]["end"]), \
        "window drifted from the committed books -- cannot compare"

    t0 = time.time()
    rows, marks = [], []
    with Pool(a.procs) as pool:
        for sym, r, m in pool.imap_unordered(
                run_symbol_simd, [(s, start_day, end_day) for s in syms]):
            rows.extend(r)
            marks.extend(m)
            print(f"    {sym}: {len(r)} rows", flush=True)
    print(f"  SIM D done in {time.time()-t0:.0f}s: {len(rows)} rows")

    sd = stats(rows)
    print(f"  SIM D: n={sd['n']} wr={sd['wr']}% meanR={sd['mean_r']:+.4f} "
          f"(+/-{sd['ci95']}) aw={sd['avg_win']} al={sd['avg_loss']} "
          f"green={sd['green']}/{sd['months']} days={sd['days']} "
          f"$/day=${sd['dollar_day']:,.2f} worstR={sd['worst_r']}")

    hash_rows = [dict(r, status="fired") for r in rows]
    meta = {"step": "D", "step_name": "referee_next_open_blind2r_REAL_ENGINE",
            "fill": "next_open", "exit_plan": "blind_2R_engine", "pool": "full29",
            "signals": len(rows), "window": {"start": start_day, "end": end_day},
            "script": "research/r2_referee_pass2.py",
            "stamp": stamp_with_env(hash_rows, "next_open", "blind_2R_engine",
                                    pool="full29",
                                    window={"start": start_day, "end": end_day},
                                    step="D",
                                    step_name="referee_next_open_blind2r_REAL_ENGINE",
                                    script="research/r2_referee_pass2.py")}
    outp = SIMD_PATH
    with gzip.open(outp, "wt", encoding="utf-8") as f:
        json.dump({"meta": meta, "trades": rows}, f)
    print(f"  wrote {outp}")
    print(f"  SIM D stamp: ENTRY_FILL={meta['stamp']['flags'].get('entry_fill.ENTRY_FILL')!r} "
          f"SCALE_PLAN={meta['stamp']['flags'].get('backtest_week.SCALE_PLAN')!r} "
          f"commit={meta['stamp']['git']['commit'][:8]} "
          f"dirty_py={meta['stamp']['git']['dirty_py_count']}")

    print()
    print("  DECOMPOSITION of the row's headline -$5,550/day step:")
    d1, dd, d2 = s1["dollar_day"], sd["dollar_day"], s2["dollar_day"]
    print(f"    fwd_1 custom _walk + blind 2R        ${d1:>10,.2f}/day  "
          f"n={s1['n']} wr={s1['wr']}% green={s1['green']}/25")
    print(f"    SIM D real engine + blind 2R         ${dd:>10,.2f}/day  "
          f"n={sd['n']} wr={sd['wr']}% green={sd['green']}/25   "
          f"SUBSTRATE leg ${dd - d1:,.2f} ({100*(dd-d1)/(d2-d1):.1f}% of the step)")
    print(f"    fwd_2 real engine + shipped ladder   ${d2:>10,.2f}/day  "
          f"n={s2['n']} wr={s2['wr']}% green={s2['green']}/25   "
          f"LADDER leg    ${d2 - dd:,.2f} ({100*(d2-dd)/(d2-d1):.1f}% of the step)")
    hd1, hd2, mid = halves(rows)
    print(f"    SIM D halves (mid {mid}): H1 ${hd1['dollar_day']:,.2f} "
          f"(n={hd1['n']}, {hd1['months']}mo)  H2 ${hd2['dollar_day']:,.2f} "
          f"(n={hd2['n']}, {hd2['months']}mo)")
    print(f"    LADDER leg by half: H1 ${stats([r for r in books[2]['trades'] if r['day'] < mid])['dollar_day'] - hd1['dollar_day']:,.2f}"
          f"  H2 ${stats([r for r in books[2]['trades'] if r['day'] >= mid])['dollar_day'] - hd2['dollar_day']:,.2f}")

    print()
    print("=" * 78)
    print("6. DEDUPE REPLAY -- could the FILTERED 'add C grades' step have needed")
    print("   re-simulation? (backtest_week ~1400: the suppression claim is")
    print("   grade-blind; DEDUPE_MODE='level' -> window = DEDUPE_CONTIG = 2 bars)")
    print("=" * 78)
    tot_b, nonc_b = dedupe_replay(marks, contig=2, drop_c=False)
    tot_c, nonc_c = dedupe_replay(marks, contig=2, drop_c=True)
    print(f"  C fires claim the window (as simulated): survivors {tot_b}, of which "
          f"non-C {nonc_b}")
    print(f"  C fires gated off (a real no-C run)    : survivors {tot_c}, of which "
          f"non-C {nonc_c}")
    print(f"  NON-C signals a real C-gated run would release that a post-hoc row "
          f"filter cannot produce: {nonc_c - nonc_b} "
          f"({100.0*(nonc_c - nonc_b)/max(nonc_b,1):.1f}% more non-C fires)")


if __name__ == "__main__":
    main()
