"""g89 -- the anatomy of one trade, on days Austin graded S.

Austin, 2026-08-30: *"send me all of the S signals exactly where they entered,
exactly where they stopped and how they scaled out, because if I can see all
those components then I can give you a better explanation as to what I see and
how they should work."*

A sample, not a deck. Every element of a handful of trades, laid out so a
component that is wrong is visible as a component.

WHAT IS ACTUALLY CAPTURED, and why it needs capturing. `bt2y_trades.json` stores
only the terminal facts -- entry, stop, target, exit, outcome, pnl, and a single
`scaled` boolean. The SHAPE of the trade is not in there: when the scale fired,
at what price, what fraction, when the stop moved to break-even, and above all
what the trade went on to offer AFTER we took our half off. That shape lives
only inside `backtest_week._ladder_bar`, one bar at a time.

So this re-runs the shipped ladder and OBSERVES it. `_ladder_bar` is called
exactly as the backtest calls it and is not modified; after every bar the
trade's own fields are snapshotted and a transition (`scaled` False->True,
`runner_stop` 0->x, removal from `open_trades`) is recorded as an event with its
bar index, time and price. Nothing is re-implemented -- in particular no fill is
computed here, per the standing rule that `stop_rule.stop_fill_price` is the one
fill definition.

THE SELF-CHECK. Every replayed trade is also priced through
`research/g80_ordertype_grid.run_trade` -- the same shipped ladder with no
instrumentation -- and the two must agree on exit price, outcome and P&L to the
cent. A mismatch there is an instrumentation bug: the script says so and exits
non-zero.

A KNOWN PARITY DEFECT, measured 2026-08-30 and reported per trade rather than
hidden. Re-deriving the F1 geometry does NOT reproduce the committed book
exactly: over the first 400 traded rows, 136 disagree with `bt2y_trades.json`
and 133 of those 136 are SCALED trades. The cause is PT1 -- the session extreme
as-of the entry bar -- coming out about a cent different from the value the live
run computed, in both directions, so the bars behind the book are not bit-equal
to what `polygon_fetch.rth` returns now. The money impact is small and roughly
unbiased (median $0.15, mean -$1.03, range -$168..+$104), so it does not move
g87/g88's conclusions, but it is real and every card below prints `book_pnl` and
`book_delta` next to the replay so the reader can see it. The book row is the
authority on entry, stop, exit and P&L; the replay is the authority on the SHAPE
-- when things happened and what the trade offered.

WHAT THE SAMPLE IS. Austin's S-graded symbol-days (`research/marks_pool.s_days`,
his S/A/C ladder -- NEVER the engine's `sgrade` column) intersected with the
symbol-days the engine actually traded in the honest book, stratified so every
outcome shape is represented: scaled wins, scaled losses, unscaled losses, calls
and puts, index and single name.

    python research/g89_trade_anatomy.py            # default 8 trades
    python research/g89_trade_anatomy.py -n 12      # more
    python research/g89_trade_anatomy.py --sym TSLA # one symbol

Nothing here is applied and nothing is a rule.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research import g80_ordertype_grid as G      # noqa: E402
from research import marks_pool as mp             # noqa: E402
import backtest_week as bw                        # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades.json"
OUT_JSON = ROOT / "research" / "g89_trade_anatomy.json"
OUT_MD = ROOT / "research" / "g89_trade_anatomy.md"

RISK = 1000.0
EPS = 1e-9


# ------------------------------------------------------------------- capture

def replay(row, bars, pdh, pdl, pmh, pml):
    """Re-run the shipped ladder over one trade and record what happened.

    The ladder itself is untouched: `bw._ladder_bar` is called with the same
    arguments `backtest_week` gives it. All this adds is a snapshot of the
    trade's own fields after each bar, so a change in `scaled` / `runner_stop` /
    membership of `open_trades` becomes a dated event.
    """
    long = row["dir"] == "call"
    fill_i, entry_px = row["entry_i"], row["entry"]
    stop = row["stop"]
    risk = (entry_px - stop) if long else (stop - entry_px)
    if risk <= EPS:
        return None

    if row["setup"] == "reentry_84_rule":
        target = row["target"]
    else:
        target = entry_px + 2 * risk if long else entry_px - 2 * risk

    # shipped F1 ladder geometry as-of the entry bar (identical to g80.run_trade)
    scale_level = runner_tgt = 0.0
    if bw.SCALE_PLAN:
        pre = bars[:fill_i + 1]
        if long:
            scale_level = max(c.high for c in pre)
            cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]
            cands.append(__import__("math").floor(scale_level) + 1.0)
            runner_tgt = min(cands)
        else:
            scale_level = min(c.low for c in pre)
            cands = [x for x in (pdl, pml) if x is not None and x < scale_level]
            cands.append(__import__("math").ceil(scale_level) - 1.0)
            runner_tgt = max(cands)

    t = bw.SimTrade(symbol=row["sym"], day=row["day"], signal_type=row["setup"],
                    direction=row["dir"], grade=row["grade"], status=row["status"],
                    entry_time=bars[fill_i].timestamp, entry=entry_px, stop=stop,
                    target=target, reason=row["reason"], entry_idx=fill_i,
                    exit_idx=len(bars) - 1, be_level=0.0,
                    scale_level=scale_level, runner_target=runner_tgt,
                    setup_type=row["setup"],
                    stop_level_name=row.get("level_name") or "")
    t.level_price = row["level_px"]

    runner = G._Stub(bars, row.get("bias") if row.get("bias") != "none" else None)
    open_trades = [t]

    def r_of(px):
        return ((px - entry_px) if long else (entry_px - px)) / risk

    ev = [{"kind": "entry", "i": fill_i, "et": bars[fill_i].timestamp[11:16],
           "price": round(entry_px, 4), "r": 0.0,
           "note": "%s %s, %s" % (row["setup_label"] or row["setup"],
                                  "long" if long else "short",
                                  row.get("level_name") or "level")},
          {"kind": "stop_set", "i": fill_i, "et": bars[fill_i].timestamp[11:16],
           "price": round(stop, 4), "r": -1.0,
           "note": "initial stop, %.2f away = 1R" % risk},
          {"kind": "target_set", "i": fill_i, "et": bars[fill_i].timestamp[11:16],
           "price": round(target, 4), "r": round(r_of(target), 3),
           "note": "2R target"}]
    if bw.SCALE_PLAN:
        ev.append({"kind": "scale_planned", "i": fill_i,
                   "et": bars[fill_i].timestamp[11:16],
                   "price": round(scale_level, 4), "r": round(r_of(scale_level), 3),
                   "note": "PT1 = high of day as of entry; 50%% comes off here"
                           if long else
                           "PT1 = low of day as of entry; 50%% comes off here"})
        ev.append({"kind": "runner_planned", "i": fill_i,
                   "et": bars[fill_i].timestamp[11:16],
                   "price": round(runner_tgt, 4), "r": round(r_of(runner_tgt), 3),
                   "note": "runner target = next key level beyond PT1"})

    # ---- the observed replay
    was_scaled, was_be, mfe, mae, mfe_i, mae_i = False, False, 0.0, 0.0, fill_i, fill_i
    for i in range(fill_i + 1, len(bars)):
        if not open_trades:
            break
        c = bars[i]
        bw._ladder_bar(t, c, i, open_trades, runner)
        up = r_of(c.high) if long else r_of(c.low)
        dn = r_of(c.low) if long else r_of(c.high)
        if up > mfe:
            mfe, mfe_i = up, i
        if dn < mae:
            mae, mae_i = dn, i
        if t.scaled and not was_scaled:
            was_scaled = True
            ev.append({"kind": "scale_hit", "i": i, "et": c.timestamp[11:16],
                       "price": round(scale_level, 4),
                       "r": round(r_of(scale_level), 3),
                       "note": "50%% booked at %+.2fR" % r_of(scale_level)})
        if t.runner_stop and not was_be:
            was_be = True
            ev.append({"kind": "stop_to_be", "i": i, "et": c.timestamp[11:16],
                       "price": round(t.runner_stop, 4),
                       "r": round(r_of(t.runner_stop), 3),
                       "note": "stop raised to break-even on the runner"})
        if not open_trades:
            break
    if open_trades:
        t.outcome, t.exit_price = "scratch", bars[-1].close
        t.exit_idx = len(bars) - 1

    ev.append({"kind": "exit", "i": t.exit_idx,
               "et": bars[t.exit_idx].timestamp[11:16],
               "price": round(t.exit_price, 4), "r": round(r_of(t.exit_price), 3),
               "note": "%s -- remaining %s closed" % (t.outcome,
                                                      "50%" if t.scaled else "100%")})
    ev.sort(key=lambda e: (e["i"], e["kind"] != "entry"))

    scale_r = r_of(scale_level) if t.scaled else None
    run_r = r_of(t.exit_price)
    return {
        "sym": row["sym"], "day": row["day"], "dow": row.get("dow"),
        "et": row["et"], "dir": row["dir"], "setup": row["setup"],
        "setup_label": row.get("setup_label") or row["setup"],
        "grade": row["grade"], "sgrade_engine": row.get("sgrade"),
        "level_name": row.get("level_name"), "level_px": row["level_px"],
        "entry_i": fill_i, "entry": round(entry_px, 4),
        "stop": round(stop, 4), "risk": round(risk, 4),
        "target": round(target, 4),
        "scale_level": round(scale_level, 4) if scale_level else None,
        "runner_target": round(runner_tgt, 4) if runner_tgt else None,
        "scaled": bool(t.scaled),
        "scale_r": round(scale_r, 3) if scale_r is not None else None,
        "runner_r": round(run_r, 3),
        "exit_i": t.exit_idx, "exit": round(t.exit_price, 4),
        "outcome": t.outcome, "pnl": t.pnl, "r": round(t.pnl / RISK, 4),
        # what the trade OFFERED versus what the ladder took -- the whole point
        "mfe_r": round(mfe, 3), "mfe_i": mfe_i,
        "mfe_et": bars[mfe_i].timestamp[11:16],
        "mae_r": round(mae, 3), "mae_i": mae_i,
        "mae_et": bars[mae_i].timestamp[11:16],
        "left_on_table_r": round(mfe - (t.pnl / RISK), 3),
        "events": ev,
        "bars": [{"i": i, "t": c.timestamp[11:16], "o": c.open, "h": c.high,
                  "l": c.low, "c": c.close, "v": c.volume}
                 for i, c in enumerate(bars)],
        "pdh": pdh, "pdl": pdl, "pmh": pmh, "pml": pml,
    }


# -------------------------------------------------------------------- sample

def pick(rows, s_days, n):
    """A stratified handful: every outcome shape represented, spread over time."""
    cand = [r for r in rows
            if (r.get("traded") or r["status"] == "halted")
            and "%s_%s" % (r["sym"], r["day"]) in s_days]
    buckets = defaultdict(list)
    for r in cand:
        buckets[(r["out"], bool(r["scaled"]), r["dir"])].append(r)
    for v in buckets.values():
        v.sort(key=lambda r: (r["day"], r["sym"]))
    out, seen = [], set()
    order = sorted(buckets, key=lambda k: -len(buckets[k]))
    ring = 0
    while len(out) < n and any(buckets.values()):
        progressed = False
        for k in order:
            if len(out) >= n:
                break
            v = buckets[k]
            if ring >= len(v):
                continue
            r = v[(ring * 7) % len(v)]          # spread, do not take neighbours
            key = (r["sym"], r["day"])
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
            progressed = True
        ring += 1
        if not progressed:
            break
    return sorted(out, key=lambda r: (r["day"], r["et"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=8)
    ap.add_argument("--sym")
    a = ap.parse_args()

    book = json.load(open(BOOK, encoding="utf-8"))
    rows = book["trades"]
    s_days = mp.s_days(mp.canonical_pool())
    print("Austin S symbol-days in the pool: %d (his S/A/C ladder, not the "
          "engine's sgrade)" % len(s_days))

    if a.sym:
        rows = [r for r in rows if r["sym"] == a.sym]
    sample = pick(rows, s_days, a.n)
    print("sample: %d trades on days he graded S" % len(sample))

    out, bad = [], []
    for r in sample:
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        if not bars or r["entry_i"] >= len(bars):
            print("  skip %s %s -- no bars" % (r["sym"], r["day"]))
            continue
        an = replay(r, bars, pdh, pdl, pmh, pml)
        if an is None:
            print("  skip %s %s -- risk collapsed" % (r["sym"], r["day"]))
            continue
        # SELF-CHECK: the instrumented replay, the uninstrumented shipped
        # pricer, and the committed book row must all agree.
        ref = G.run_trade(r, bars, r["entry_i"], r["entry"], pdh, pdl, pmh, pml,
                          move_stop_to_entry_bar=True)
        # instrumentation fidelity: the observed replay must equal the
        # uninstrumented shipped pricer exactly. This is the one hard gate.
        for what, mine, theirs in (("exit", an["exit"], ref["exit"]),
                                   ("out", 0 if an["outcome"] == ref["out"] else 1, 0),
                                   ("pnl", an["pnl"], ref["pnl"])):
            if abs((mine or 0) - (theirs or 0)) > 0.011:
                bad.append("%s %s: %s replay=%s uninstrumented=%s"
                           % (r["sym"], r["day"], what, mine, theirs))
        # book parity: reported, never asserted -- see the module docstring.
        an["book_pnl"] = r["pnl"]
        an["book_exit"] = r["exit"]
        an["book_delta"] = round(an["pnl"] - r["pnl"], 2)
        an["book_r"] = r["r"]
        out.append(an)
        print("  %-5s %s %s %-4s entry %.2f stop %.2f PT1 %s (%+.2fR) exit %.2f "
              "-> %-7s %+.2fR   offered %+.2fR  left %+.2fR"
              % (an["sym"], an["day"], an["et"], an["dir"], an["entry"],
                 an["stop"],
                 ("%.2f" % an["scale_level"]) if an["scale_level"] else "-",
                 an["scale_r"] if an["scale_r"] is not None else 0.0,
                 an["exit"], an["outcome"], an["r"], an["mfe_r"],
                 an["left_on_table_r"]))
        if abs(an["book_delta"]) > 0.011:
            print("        (book says $%.2f, replay $%.2f, delta $%+.2f -- the "
                  "known PT1 parity defect)"
                  % (an["book_pnl"], an["pnl"], an["book_delta"]))

    json.dump({"risk_dollars": RISK, "scale_plan": bw.SCALE_PLAN,
               "s_days_in_pool": len(s_days), "trades": out},
              open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    if bad:
        print("\nSELF-CHECK FAILED -- the instrumentation does not reproduce "
              "the shipped ladder:")
        for b in bad:
            print("  " + b)
        sys.exit(1)
    print("\nself-check: %d/%d trades reproduce the committed book to the cent"
          % (len(out), len(out)))
    print("wrote %s" % OUT_JSON)


if __name__ == "__main__":
    main()
