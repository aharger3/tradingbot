"""G7.1 / track `firsts` -- day-policy A/B on the two-year book.

Austin, 2026-08-29:
  "all these s trades would not be done in one day, what would happen is we
   trade the s trade that comes up first, and if it wins, were done for the
   day. the 2 trades losses done for the day is a scarface rule... keep
   trading s trades until youve hit profit."

That is a DAY policy, not a signal filter. The engine currently takes every
counted signal a day produces (minus R31's two-consecutive-loss halt). This
script re-selects, per day, which of the already-simulated signals a
day-policy would actually have entered, and re-scores the book.

Input: `research/bt2y_trades.json` (the money/durability rig, `backtest_2y.py`).
Nothing is re-simulated. Every trade's R is a property of that signal alone --
entry, stop, target and fill are fixed at detection -- so a day policy is pure
SELECTION over the existing rows. No engine file is touched.

CANDIDATE STREAM
----------------
The counted stream = rows the engine would enter with R31 off:
`status == "fired" and traded` (2,437) plus `status == "halted"` (857) -- the
857 are counted rows that R31 flipped to traded=False, and they keep every
measured field. Legacy-`C` rows (`alert`, 1,050) are alert-only and are NOT
in the stream, except in the P5b arm which is explicit about it.

CAUSALITY
---------
Ordering and one-position-at-a-time use the same tuple keys `loss_halt.py`
uses, for the same reason (`loss_halt.py` docstring, "CAUSAL, NOT THE
POST-PROCESS APPROXIMATION"):

    entry_key = (entry_i, et, sym)
    exit_key  = (entry_i + bars, et, sym)

A policy may only take a candidate whose entry_key >= the last taken trade's
exit_key. You cannot decide the second trade of the day before the first one
has closed, and you cannot hold two at once under a "trade it, then see"
rule.

POLICIES
--------
P0  the book as it ships today (traded==True), all concurrent signals, R31 on.
P0u the same with R31 off -- the raw counted stream, the ceiling of "take
    everything".
P1  first signal of the day only.
P2  first; win -> done; loss -> next; done after 2 losses.      (his sentence)
P3  first; keep going until the DAY is net green. No loss cap.
P4  P3 with a 3-loss cap.
P5  P2 restricted to S.  S proxy = `sgrade == "S"`, the `research/downgrade.py`
    ladder already attached to every row by `backtest_2y.py:152`. There is no
    S gate in detection (`signal_runner.S_GATE = False`, line 380;
    `ENABLE_SAC_LADDER = 0`, line 660), so this is a proxy, and it is the same
    one P4/R3 would wire in. downgrade.score() reads only bars <= entry_idx,
    so it is causal.
P5b P5 over the S rows of the FULL fired set, i.e. including the legacy-C
    alerts whose sgrade is S -- what "trade S" routing would actually enter.

ORACLE
------
Best single trade per day over the counted stream (perfect foresight, one
trade a day). DIRECTION.md cites +2.2125R at 76.6% for this; recomputed here
on the current book.

Usage: python research/g71_firsts_policy.py [--book research/bt2y_trades.json]
"""
from __future__ import annotations

import argparse, json, statistics
from collections import defaultdict, Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ekey(r):
    return (r["entry_i"], r["et"], r["sym"])


def xkey(r):
    return (r["entry_i"] + r["bars"], r["et"], r["sym"])


# ---------------------------------------------------------------- policies

def walk(cands, decide):
    """Take candidates in entry order, one at a time, until `decide` stops.

    `decide(state)` -> True to STOP before taking the next trade. `state` is
    (n_taken, wins, losses, scratches, cum_r).
    """
    taken, free = [], None
    wins = losses = scr = 0
    cum = 0.0
    for c in cands:
        if decide((len(taken), wins, losses, scr, cum)):
            break
        if free is not None and ekey(c) < free:
            continue                      # position still open
        taken.append(c)
        free = xkey(c)
        o = c["out"]
        if o == "win":
            wins += 1
        elif o == "loss":
            losses += 1
        else:
            scr += 1
        cum += c["r"]
    return taken


P_FIRST = lambda s: s[0] >= 1
P_2LOSS = lambda s: s[1] >= 1 or s[2] >= 2          # a win ends it; 2 losses end it
P_GREEN = lambda s: s[4] > 0                        # keep going until net green
P_GREEN3 = lambda s: s[4] > 0 or s[2] >= 3


# ---------------------------------------------------------------- scoring

def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


def score(name, taken_by_day, all_days, all_months, all_weeks, note=""):
    rows = [r for d in sorted(taken_by_day) for r in taken_by_day[d]]
    n = len(rows)
    wins = sum(1 for r in rows if r["out"] == "win")
    losses = sum(1 for r in rows if r["out"] == "loss")
    scr = n - wins - losses
    dec = wins + losses
    total = sum(r["r"] for r in rows)

    day_r = {d: sum(r["r"] for r in taken_by_day[d]) for d in taken_by_day if taken_by_day[d]}
    mon, wk = defaultdict(float), defaultdict(float)
    for d, v in day_r.items():
        mon[d[:7]] += v
        wk[iso_week(d)] += v

    # equity curve on the CALENDAR of candidate days: a day the policy sat out
    # is a flat day, not a missing one.
    cum, peak, dd = 0.0, 0.0, 0.0
    for d in all_days:
        cum += day_r.get(d, 0.0)
        peak = max(peak, cum)
        dd = max(dd, peak - cum)

    # longest run of red days, counted over the days the policy TRADED
    run = best = 0
    for d in sorted(day_r):
        if day_r[d] < 0:
            run += 1
            best = max(best, run)
        else:
            run = 0

    return {
        "policy": name, "note": note,
        "trades": n, "wins": wins, "losses": losses, "scratch": scr,
        "win_rate": round(wins / dec * 100, 2) if dec else 0.0,
        "mean_r_trade": round(total / n, 4) if n else 0.0,
        "mean_r_day_all": round(total / len(all_days), 4),
        "mean_r_day_active": round(total / len(day_r), 4) if day_r else 0.0,
        "total_r": round(total, 2),
        "days_traded": len(day_r),
        "green_days": sum(1 for v in day_r.values() if v > 0),
        "months_green": sum(1 for m in all_months if mon.get(m, 0.0) > 0),
        "months_total": len(all_months),
        "weeks_green": sum(1 for w in all_weeks if wk.get(w, 0.0) > 0),
        "weeks_total": len(all_weeks),
        "max_dd_r": round(dd, 2),
        "max_red_streak_days": best,
        "trades_per_active_day": round(n / len(day_r), 2) if day_r else 0.0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="research/bt2y_trades.json")
    ap.add_argument("--out", default="research/_g71_firsts.json")
    a = ap.parse_args()

    book = json.loads((ROOT / a.book).read_text(encoding="utf-8"))
    meta, trades = book["meta"], book["trades"]

    counted = [r for r in trades if (r["status"] == "fired" and r["traded"])
               or r["status"] == "halted"]
    shipped = [r for r in trades if r["traded"]]
    fired_any = [r for r in trades if r["status"] in ("fired", "halted")]

    by_day = defaultdict(list)
    for r in counted:
        by_day[r["day"]].append(r)
    for d in by_day:
        by_day[d].sort(key=ekey)

    s_by_day = defaultdict(list)
    for d, rs in by_day.items():
        ss = [r for r in rs if r["sgrade"] == "S"]
        if ss:
            s_by_day[d] = ss

    s_all_by_day = defaultdict(list)
    for r in fired_any:
        if r["sgrade"] == "S":
            s_all_by_day[r["day"]].append(r)
    for d in s_all_by_day:
        s_all_by_day[d].sort(key=ekey)

    all_days = sorted(by_day)
    all_months = sorted({d[:7] for d in all_days})
    all_weeks = sorted({iso_week(d) for d in all_days})

    def group(rows):
        g = defaultdict(list)
        for r in rows:
            g[r["day"]].append(r)
        return g

    def run(stream, decide):
        return {d: walk(rs, decide) for d, rs in stream.items()}

    res = []
    res.append(score("P0 shipped (all signals, R31 halt ON)", group(shipped),
                     all_days, all_months, all_weeks,
                     "the book as it ships today"))
    res.append(score("P0u all counted (R31 halt OFF)", by_day,
                     all_days, all_months, all_weeks,
                     "take everything, no halt"))
    res.append(score("P1 first signal only", run(by_day, P_FIRST),
                     all_days, all_months, all_weeks,
                     "one trade a day, whatever came first"))
    res.append(score("P2 first; win=done; 2 losses=done", run(by_day, P_2LOSS),
                     all_days, all_months, all_weeks,
                     "his sentence, literally"))
    res.append(score("P3 until day is net green (no cap)", run(by_day, P_GREEN),
                     all_days, all_months, all_weeks,
                     "keep trading until youve hit profit"))
    res.append(score("P4 until net green, 3-loss cap", run(by_day, P_GREEN3),
                     all_days, all_months, all_weeks, ""))
    res.append(score("P5 P2 on S only (counted stream)", run(s_by_day, P_2LOSS),
                     all_days, all_months, all_weeks,
                     "S proxy = downgrade.py sgrade=='S'"))
    res.append(score("P5b P2 on S only (incl. legacy-C alerts)",
                     run(s_all_by_day, P_2LOSS),
                     all_days, all_months, all_weeks,
                     "what 'trade S' routing would enter"))
    res.append(score("P3s until net green, S only", run(s_by_day, P_GREEN),
                     all_days, all_months, all_weeks, "P3 on the S stream"))
    # CONTROL: sequential, one position at a time, but NO stopping rule. This
    # separates the two things P1-P4 change at once -- the stop rule, and the
    # fact that a human holds one position where the book holds five.
    res.append(score("P0seq every counted signal, 1 at a time",
                     run(by_day, lambda s: False),
                     all_days, all_months, all_weeks,
                     "control: concurrency removed, no stop rule"))

    # ---- oracle: best single trade per day, perfect foresight
    orc = {d: [max(rs, key=lambda r: r["r"])] for d, rs in by_day.items()}
    oracle = score("ORACLE best-single-trade/day", orc,
                   all_days, all_months, all_weeks, "ceiling, look-ahead")
    res.append(oracle)
    wrs = {d: [min(rs, key=lambda r: r["r"])] for d, rs in by_day.items()}
    res.append(score("ANTI-ORACLE worst-single-trade/day", wrs,
                     all_days, all_months, all_weeks, "floor, look-ahead"))

    # "is FIRST special?" -- the expected value of one uniformly random
    # candidate per day, and the last one, as controls for P1.
    rnd = score("RANDOM one-per-day (EV control)",
                {d: rs for d, rs in by_day.items()}, all_days, all_months,
                all_weeks, "scaled below; EV of a random single pick")
    rnd["trades"] = len(all_days)
    rnd["total_r"] = round(sum(statistics.fmean([x["r"] for x in rs])
                               for rs in by_day.values()), 2)
    rnd["mean_r_trade"] = round(rnd["total_r"] / len(all_days), 4)
    rnd["mean_r_day_all"] = rnd["mean_r_trade"]
    rnd["win_rate"] = round(statistics.fmean(
        [sum(1 for x in rs if x["out"] == "win")
         / max(1, sum(1 for x in rs if x["out"] in ("win", "loss")))
         for rs in by_day.values()]) * 100, 2)
    for k in ("wins", "losses", "scratch", "months_green", "weeks_green",
              "max_dd_r", "max_red_streak_days", "green_days", "days_traded",
              "mean_r_day_active", "trades_per_active_day"):
        rnd[k] = -1
    res.append(rnd)
    res.append(score("LAST signal of the day only",
                     {d: [rs[-1]] for d, rs in by_day.items()},
                     all_days, all_months, all_weeks, "control for P1"))

    for r in res:
        r["pct_of_oracle_totalR"] = (round(r["total_r"] / oracle["total_r"] * 100, 1)
                                     if oracle["total_r"] else 0.0)

    # ---- supporting reads
    firsts = [rs[0] for rs in by_day.values()]
    extra = {
        "book_meta": {k: meta[k] for k in
                      ("generated", "first", "last", "sessions", "signals",
                       "traded", "loss_halt", "halted")},
        "counted_stream": len(counted),
        "shipped_traded": len(shipped),
        "candidate_days": len(all_days),
        "months": len(all_months), "weeks": len(all_weeks),
        "first_signal_outcome": dict(Counter(r["out"] for r in firsts)),
        "first_signal_mean_r": round(statistics.fmean(r["r"] for r in firsts), 4),
        "first_signal_sgrade": dict(Counter(r["sgrade"] for r in firsts)),
        "first_signal_grade": dict(Counter(r["grade"] for r in firsts)),
        "counted_per_day_mean": round(len(counted) / len(all_days), 2),
        "days_with_S_counted": len(s_by_day),
        "days_with_S_anyfired": len(s_all_by_day),
        "S_counted_rows": sum(len(v) for v in s_by_day.values()),
        "sgrade_counted": dict(Counter(r["sgrade"] for r in counted)),
        "mean_r_by_sgrade_counted": {
            g: round(statistics.fmean(r["r"] for r in counted if r["sgrade"] == g), 4)
            for g in ("S", "A", "C")},
        "winrate_by_sgrade_counted": {
            g: round(sum(1 for r in counted if r["sgrade"] == g and r["out"] == "win")
                     / max(1, sum(1 for r in counted if r["sgrade"] == g
                                  and r["out"] in ("win", "loss"))) * 100, 2)
            for g in ("S", "A", "C")},
        "seq_position_mean_r": {},
        "mean_r_by_legacy_grade_counted": {
            g: {"n": sum(1 for r in counted if r["grade"] == g),
                "mean_r": round(statistics.fmean([r["r"] for r in counted
                                                  if r["grade"] == g] or [0.0]), 4)}
            for g in ("A+", "A", "B", "C")},
    }
    # P0 concurrency: how many positions the shipped book holds at once.
    conc = []
    for d, rs in group(shipped).items():
        ev = sorted([(ekey(r), 1) for r in rs] + [(xkey(r), -1) for r in rs])
        cur = mx = 0
        for _k, v in ev:
            cur += v
            mx = max(mx, cur)
        conc.append(mx)
    # Paired day-level deltas against the P0seq control, with a standard error.
    # The standing method finding (DIRECTION.md) is that every A/B this project
    # runs moves less than its own error bar; check it here rather than assume.
    arms = {"P1": run(by_day, P_FIRST), "P2": run(by_day, P_2LOSS),
            "P3": run(by_day, P_GREEN), "P4": run(by_day, P_GREEN3),
            "P5": run(s_by_day, P_2LOSS), "P0seq": run(by_day, lambda s: False),
            "P0": group(shipped), "ORACLE": orc}

    def dayvec(t):
        return {d: sum(x["r"] for x in rs) for d, rs in t.items()}

    ctrl = dayvec(arms["P0seq"])
    paired = {}
    for k, t in arms.items():
        if k == "P0seq":
            continue
        v = dayvec(t)
        diffs = [v.get(d, 0.0) - ctrl.get(d, 0.0) for d in all_days]
        m = statistics.fmean(diffs)
        se = statistics.pstdev(diffs) / (len(diffs) ** 0.5)
        paired[k] = {"mean_day_delta_vs_P0seq": round(m, 4),
                     "se": round(se, 4), "t": round(m / se, 2) if se else 0.0,
                     "significant_2se": abs(m) > 2 * se}
    extra["paired_vs_P0seq"] = paired
    extra["red_months"] = {}
    for k, t in arms.items():
        v = dayvec(t)
        mm = defaultdict(float)
        for d, x in v.items():
            mm[d[:7]] += x
        extra["red_months"][k] = sorted(
            "%s %+.1fR" % (m, mm.get(m, 0.0)) for m in all_months
            if mm.get(m, 0.0) <= 0)
    extra["p0_max_concurrent_positions"] = {
        "mean": round(statistics.fmean(conc), 2), "max": max(conc),
        "days_with_2plus": sum(1 for c in conc if c >= 2),
        "days_with_4plus": sum(1 for c in conc if c >= 4)}
    pos = defaultdict(list)
    for rs in by_day.values():
        for i, r in enumerate(rs):
            pos[min(i + 1, 6)].append(r["r"])
    extra["seq_position_mean_r"] = {
        ("%d+" % k if k == 6 else str(k)):
        {"n": len(v), "mean_r": round(statistics.fmean(v), 4),
         "win_rate": round(sum(1 for x in v if x > 0) / len(v) * 100, 1)}
        for k, v in sorted(pos.items())}

    out = {"meta": extra, "policies": res}
    (ROOT / a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")

    hdr = ("policy", "trades", "WR%", "R/trade", "R/day", "totalR",
           "mo", "wk", "maxDD", "redrun", "%orc")
    print("%-42s %7s %7s %8s %7s %9s %7s %8s %8s %7s %6s" % hdr)
    for r in res:
        print("%-42s %7d %6.2f%% %8.4f %7.4f %9.1f %3d/%-3d %4d/%-3d %8.1f %7d %6.1f"
              % (r["policy"], r["trades"], r["win_rate"], r["mean_r_trade"],
                 r["mean_r_day_all"], r["total_r"], r["months_green"],
                 r["months_total"], r["weeks_green"], r["weeks_total"],
                 r["max_dd_r"], r["max_red_streak_days"], r["pct_of_oracle_totalR"]))
    print()
    print(json.dumps(extra, indent=1))
    print("\nwrote %s" % (ROOT / a.out))


if __name__ == "__main__":
    main()
