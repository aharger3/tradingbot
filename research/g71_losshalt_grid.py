"""G7.1 / losshalt — the full loss-governor grid on the 2-year book.

Austin: "i see your right so 2 consecutive halts is bad, but overtrading is too,
subagents will find the medium" / "we dont know if 2 losers in a row is a
stopping point, keep trading s trades until youve hit profit."

WHAT THIS SWEEPS
----------------
Three day-governors, crossed, 5 x 2 x 4 = 40 cells:

  halt_n     N consecutive CLOSED losses ends new entries for the day.
             N in {1, 2, 3, 4, none}.   (loss_halt.py ships N=2)
  stop_win   first CLOSED win ends new entries for the day. {yes, no}
             (live_scanner STOP_AFTER_WIN, never measured on the 2y book)
  r_floor    realised day R at or below the floor ends new entries.
             floor in {-1R, -2R, -3R, none}

Plus a supplementary S-CONTINUATION sweep answering his second sentence
literally: once the halt trips, keep taking Austin-ladder S cards only.

CAUSALITY — the whole point
---------------------------
Every gate is evaluated at the CANDIDATE'S OWN ENTRY MOMENT against trades that
had already CLOSED by then. Sorting a day by entry time and reading off the
eventual outcomes (research/t20_loss_halt_postprocess.py) is one bar of
look-ahead: when you place trade #3 you do not yet know trade #2 loses. This
walker copies loss_halt.halt_day's exit-clock discipline and extends it to the
win counter and the R floor. A blocked trade never happened, so it never feeds
the streak, the win counter, or the realised R either.

INPUT
-----
research/bt2y_trades.json, which is written by backtest_2y.py with R31 ALREADY
APPLIED (857 rows flipped status "fired" -> "halted", traded -> False). The
candidate pool is rebuilt as
    (status == "fired" and traded)  OR  status == "halted"
= 3,294 trades / 496 traded sessions, i.e. the unhalted book. Rows that fired
but were never counted (alert-only) stay out.

NO ENGINE FILE IS TOUCHED. Read-only over the committed book.

Usage:  python research/g71_losshalt_grid.py [--boot 2000]
Writes: research/g71_losshalt_grid.json  (every cell, machine-readable)
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades.json"
OUT = ROOT / "research" / "g71_losshalt_grid.json"

# 1R = $1,000 (CLAUDE.md). A prop daily-loss limit of P% of an account of size
# A is breached when the day's realised R is at or below -(A * P) / 1000.
PROP = [("50k@2%", 1.00), ("50k@3%", 1.50), ("100k@2%", 2.00), ("100k@3%", 3.00)]

HALT_NS = [1, 2, 3, 4, None]
STOP_WINS = [False, True]
R_FLOORS = [-1.0, -2.0, -3.0, None]


# --------------------------------------------------------------------------
# the book
# --------------------------------------------------------------------------
def load():
    d = json.loads(BOOK.read_text(encoding="utf-8"))
    rows = d["trades"]
    cand = [r for r in rows
            if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
    sessions = sorted({r["day"] for r in rows})
    return d["meta"], cand, sessions


def ekey(r):
    return (r["entry_i"], r["et"], r["sym"])


def xkey(r):
    return (r["entry_i"] + r["bars"], r["et"], r["sym"])


# --------------------------------------------------------------------------
# the causal day walker
# --------------------------------------------------------------------------
def walk_day(rows, halt_n, stop_win, r_floor, s_continue=False,
             s_until_profit=False):
    """Return the rows actually TAKEN on this day under the governor.

    halt_n     — block once this many already-closed trades have lost in a row.
                 None / <=0 disables.
    stop_win   — block once at least one already-closed trade has won.
    r_floor    — block once realised (closed-only) day R is <= this. None off.
    s_continue — when a gate is tripped, still take rows whose Austin-ladder
                 grade is "S". Those S trades still feed the counters.
    s_until_profit — the same, but the S exemption switches off as soon as the
                 day's realised R is back above zero. This is his sentence
                 taken literally: "keep trading s trades until youve hit
                 profit."
    """
    order = sorted(rows, key=ekey)
    pending = []          # (exit_key, is_loss, r), kept sorted by exit
    streak = wins = 0
    realised = 0.0
    taken = []
    for row in order:
        at = ekey(row)
        while pending and pending[0][0] <= at:
            _x, lost, r = pending.pop(0)
            streak = streak + 1 if lost else 0
            if not lost and r > 0:
                wins += 1
            realised += r
        gated = False
        if halt_n and streak >= halt_n:
            gated = True
        if stop_win and wins >= 1:
            gated = True
        if r_floor is not None and realised <= r_floor:
            gated = True
        exempt = False
        if row.get("sgrade") == "S":
            if s_continue:
                exempt = True
            elif s_until_profit and realised <= 0:
                exempt = True
        if gated and not exempt:
            continue                       # a blocked trade never happened
        taken.append(row)
        pending.append((xkey(row), row["out"] == "loss", row["r"]))
        pending.sort(key=lambda p: p[0])
    return taken


def run_arm(cand, halt_n, stop_win, r_floor, s_continue=False,
            s_until_profit=False):
    by_day = defaultdict(list)
    for r in cand:
        by_day[r["day"]].append(r)
    taken = []
    for day in sorted(by_day):
        taken += walk_day(by_day[day], halt_n, stop_win, r_floor,
                          s_continue, s_until_profit)
    return taken


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def iso_week(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return "%04d-W%02d" % (y, w)


def max_dd(daily_r, sessions):
    """Peak-to-trough drawdown in R on the cumulative day-by-day equity curve."""
    peak = cum = 0.0
    dd = 0.0
    for d in sessions:
        cum += daily_r.get(d, 0.0)
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    return dd


def metrics(taken, sessions):
    n = len(taken)
    total = sum(r["r"] for r in taken)
    wins = sum(1 for r in taken if r["out"] == "win")
    losses = sum(1 for r in taken if r["out"] == "loss")
    scr = n - wins - losses

    daily = defaultdict(float)
    for r in taken:
        daily[r["day"]] += r["r"]
    tdays = len(daily)

    by_m, by_w = defaultdict(float), defaultdict(float)
    for d, v in daily.items():
        by_m[d[:7]] += v
        by_w[iso_week(d)] += v
    # months/weeks the BOOK covers, not just the ones this arm traded — an arm
    # that trades nothing in a month is flat (0R), which is not green.
    all_m = sorted({d[:7] for d in sessions})
    all_w = sorted({iso_week(d) for d in sessions})

    breaches = {name: sum(1 for v in daily.values() if v <= -thr)
                for name, thr in PROP}

    return {
        "trades": n,
        "total_r": round(total, 2),
        "mean_r_trade": round(total / n, 4) if n else 0.0,
        "sd_r_trade": round(statistics.pstdev([r["r"] for r in taken]), 4) if n > 1 else 0.0,
        "se_mean_r": round(statistics.pstdev([r["r"] for r in taken]) / (n ** 0.5), 4) if n > 1 else 0.0,
        "win_rate": round(wins / n * 100, 1) if n else 0.0,
        "wins": wins, "losses": losses, "scratches": scr,
        "traded_days": tdays,
        "mean_r_traded_day": round(total / tdays, 3) if tdays else 0.0,
        "mean_r_session": round(total / len(sessions), 3),
        "trades_per_traded_day": round(n / tdays, 2) if tdays else 0.0,
        "months_green": sum(1 for m in all_m if by_m.get(m, 0.0) > 0),
        "months_total": len(all_m),
        "weeks_green": sum(1 for w in all_w if by_w.get(w, 0.0) > 0),
        "weeks_total": len(all_w),
        "max_dd_r": round(max_dd(daily, sessions), 2),
        "worst_day_r": round(min(daily.values()), 2) if daily else 0.0,
        "best_day_r": round(max(daily.values()), 2) if daily else 0.0,
        "prop_breaches": breaches,
        "_daily": {d: round(v, 4) for d, v in daily.items()},
    }


# --------------------------------------------------------------------------
# paired day-block bootstrap
# --------------------------------------------------------------------------
def bootstrap(daily_a, daily_b, sessions, n_boot, seed=7):
    """95% CI on (total R of A - total R of B), resampling whole SESSIONS.

    Days are the natural block: every governor here is a within-day rule, so
    the arms are perfectly paired day by day and the only sampling unit that
    is even close to independent is the trading session.
    """
    rnd = random.Random(seed)
    k = len(sessions)
    deltas = []
    da = [daily_a.get(d, 0.0) for d in sessions]
    db = [daily_b.get(d, 0.0) for d in sessions]
    diff = [a - b for a, b in zip(da, db)]
    for _ in range(n_boot):
        s = 0.0
        for _i in range(k):
            s += diff[rnd.randrange(k)]
        deltas.append(s)
    deltas.sort()
    lo = deltas[int(0.025 * n_boot)]
    hi = deltas[int(0.975 * n_boot) - 1]
    return round(sum(diff), 2), round(lo, 2), round(hi, 2)


# --------------------------------------------------------------------------
def label(halt_n, stop_win, r_floor):
    return "halt=%s stopwin=%s floor=%s" % (
        halt_n if halt_n else "none",
        "Y" if stop_win else "N",
        ("%gR" % r_floor) if r_floor is not None else "none")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=2000)
    args = ap.parse_args()

    meta, cand, sessions = load()
    print("book %s..%s — %d sessions, %d candidate trades (unhalted pool)"
          % (meta["first"], meta["last"], len(sessions), len(cand)))

    cells = {}
    for hn in HALT_NS:
        for sw in STOP_WINS:
            for fl in R_FLOORS:
                key = label(hn, sw, fl)
                taken = run_arm(cand, hn, sw, fl)
                cells[key] = metrics(taken, sessions)
                cells[key]["arm"] = {"halt_n": hn, "stop_win": sw, "r_floor": fl}

    base = cells[label(None, False, None)]

    # ---- table ----
    hdr = ("%-26s %6s %9s %8s %8s %6s %6s %7s %8s %9s %6s  %s"
           % ("cell", "n", "totalR", "R/trade", "R/day", "win%", "mo", "wk",
              "maxDD", "worstDay", "R/DD", "prop 50@2/50@3/100@2/100@3"))
    print("\n" + hdr)
    print("-" * len(hdr))
    order = sorted(cells, key=lambda k: -cells[k]["total_r"])
    for k in order:
        c = cells[k]
        b = c["prop_breaches"]
        c["r_per_dd"] = round(c["total_r"] / abs(c["max_dd_r"]), 1) if c["max_dd_r"] else 0.0
        print("%-26s %6d %9.1f %8.4f %8.3f %6.1f %4d/%d %5d/%d %8.1f %9.2f %6.1f  %d/%d/%d/%d"
              % (k, c["trades"], c["total_r"], c["mean_r_trade"], c["mean_r_traded_day"],
                 c["win_rate"], c["months_green"], c["months_total"],
                 c["weeks_green"], c["weeks_total"],
                 c["max_dd_r"], c["worst_day_r"], c["r_per_dd"],
                 b["50k@2%"], b["50k@3%"], b["100k@2%"], b["100k@3%"]))

    # ---- paired bootstrap vs the no-governor arm ----
    print("\npaired day-block bootstrap vs `%s` (%d resamples) — total R delta"
          % (label(None, False, None), args.boot))
    print("%-26s %10s %10s %10s %s" % ("cell", "delta", "lo95", "hi95", "readable?"))
    for k in order:
        if k == label(None, False, None):
            continue
        d, lo, hi = bootstrap(cells[k]["_daily"], base["_daily"], sessions, args.boot)
        cells[k]["boot_total_r"] = {"delta": d, "lo95": lo, "hi95": hi}
        print("%-26s %10.1f %10.1f %10.1f %s"
              % (k, d, lo, hi, "YES" if lo * hi > 0 else "no (spans 0)"))

    # ---- supplementary: S-continuation, and "S until profit" ----
    print("\nS-CONTINUATION — once the gate trips, what gets to keep trading")
    print("  (plain)   nothing.   (+Scont) Austin-ladder S cards, all day.")
    print("  (+Sprof)  S cards ONLY while the day's realised R is still <= 0 —")
    print("            his sentence taken literally: keep trading S until profit.")
    h2 = ("%-36s %6s %9s %8s %6s %6s %8s %9s %6s  %s"
          % ("cell", "n", "totalR", "R/trade", "win%", "mo", "maxDD", "worstDay",
             "R/DD", "prop 50@2/50@3/100@2/100@3"))
    print("\n" + h2)
    print("-" * len(h2))
    scont = {}
    for hn in [1, 2, 3, None]:
        for fl in [None, -2.0]:
            for mode in ("", " +Scont", " +Sprof"):
                if hn is None and fl is None and mode == "":
                    continue
                k = label(hn, False, fl) + mode
                taken = run_arm(cand, hn, False, fl,
                                s_continue=(mode == " +Scont"),
                                s_until_profit=(mode == " +Sprof"))
                m = metrics(taken, sessions)
                m["r_per_dd"] = round(m["total_r"] / abs(m["max_dd_r"]), 1) if m["max_dd_r"] else 0.0
                scont[k] = m
                b = m["prop_breaches"]
                print("%-36s %6d %9.1f %8.4f %6.1f %4d/%d %8.1f %9.2f %6.1f  %d/%d/%d/%d"
                      % (k, m["trades"], m["total_r"], m["mean_r_trade"], m["win_rate"],
                         m["months_green"], m["months_total"], m["max_dd_r"],
                         m["worst_day_r"], m["r_per_dd"],
                         b["50k@2%"], b["50k@3%"], b["100k@2%"], b["100k@3%"]))
            print()

    # ---- head-to-heads that decide the recommendation ----
    print("head-to-head, paired day-block bootstrap on total R")
    pairs = [
        (label(None, False, -2.0), label(2, False, None), "R floor -2R  vs  the shipped halt=2"),
        (label(3, False, -2.0), label(2, False, None), "halt=3 + -2R  vs  the shipped halt=2"),
        (label(3, False, -2.0), label(None, False, None), "halt=3 + -2R  vs  no governor"),
        (label(None, False, -2.0), label(None, False, None), "R floor -2R  vs  no governor"),
    ]
    print("%-46s %10s %10s %10s %s" % ("comparison", "delta", "lo95", "hi95", "readable?"))
    h2h = {}
    for a, b, name in pairs:
        d, lo, hi = bootstrap(cells[a]["_daily"], cells[b]["_daily"], sessions, args.boot)
        h2h[name] = {"a": a, "b": b, "delta": d, "lo95": lo, "hi95": hi}
        print("%-46s %10.1f %10.1f %10.1f %s"
              % (name, d, lo, hi, "YES" if lo * hi > 0 else "no (spans 0)"))

    # ---- is "2 in a row" a real signal at all? ----
    # The direct test of Austin's question. For every candidate trade, what was
    # the consecutive CLOSED-loss streak at its own entry moment, and what did
    # it go on to make? If the edge after a 2-loss streak is still positive,
    # the streak is not a stopping point — it is just a streak.
    print("\nCONDITIONAL EDGE — what a trade makes GIVEN the streak at its entry")
    print("(streak counted on the unhalted book, closes only, no look-ahead)")
    by_day = defaultdict(list)
    for r in cand:
        by_day[r["day"]].append(r)
    buckets = defaultdict(list)
    rbuckets = defaultdict(list)
    for day in sorted(by_day):
        order = sorted(by_day[day], key=ekey)
        pending, streak, realised = [], 0, 0.0
        for row in order:
            at = ekey(row)
            while pending and pending[0][0] <= at:
                _x, lost, rr = pending.pop(0)
                streak = streak + 1 if lost else 0
                realised += rr
            buckets[min(streak, 4)].append(row["r"])
            rbuckets[("<=-3R" if realised <= -3 else "-3..-2R" if realised <= -2 else
                      "-2..-1R" if realised <= -1 else "-1..0R" if realised <= 0
                      else "green")].append(row["r"])
            pending.append((xkey(row), row["out"] == "loss", row["r"]))
            pending.sort(key=lambda p: p[0])
    print("%-14s %7s %10s %10s %8s" % ("streak at entry", "n", "mean R", "se", "win%"))
    streak_tab = {}
    for k in sorted(buckets):
        v = buckets[k]
        se = statistics.pstdev(v) / len(v) ** 0.5 if len(v) > 1 else 0
        w = sum(1 for x in v if x > 0) / len(v) * 100
        streak_tab[str(k)] = {"n": len(v), "mean_r": round(statistics.fmean(v), 4),
                              "se": round(se, 4), "win_rate": round(w, 1)}
        print("%-14s %7d %10.4f %10.4f %8.1f"
              % ("%d in a row" % k if k < 4 else "4+ in a row", len(v),
                 statistics.fmean(v), se, w))
    print("\n%-14s %7s %10s %10s %8s" % ("realised day R", "n", "mean R", "se", "win%"))
    dayr_tab = {}
    for k in ["<=-3R", "-3..-2R", "-2..-1R", "-1..0R", "green"]:
        v = rbuckets.get(k, [])
        if not v:
            continue
        se = statistics.pstdev(v) / len(v) ** 0.5
        w = sum(1 for x in v if x > 0) / len(v) * 100
        dayr_tab[k] = {"n": len(v), "mean_r": round(statistics.fmean(v), 4),
                       "se": round(se, 4), "win_rate": round(w, 1)}
        print("%-14s %7d %10.4f %10.4f %8.1f" % (k, len(v), statistics.fmean(v), se, w))

    # ---- prop-firm sizing: the honest read ----
    # A daily-loss limit is a hard kill. Over 500 sessions, "how many days
    # breached" matters less than "what 1R size makes a breach impossible".
    print("\nPROP SIZING — largest 1R ($) that never breaches, = limit / |worst day R|")
    print("%-26s %9s %9s %9s %9s %9s" % ("cell", "worstDay", "50k@2%", "50k@3%",
                                         "100k@2%", "100k@3%"))
    for k in [label(None, False, None), label(2, False, None), label(None, False, -2.0),
              label(3, False, -2.0), label(2, False, -2.0), label(1, False, None)]:
        c = cells[k]
        wd = abs(c["worst_day_r"]) or 1.0
        c["max_1r_dollars"] = {n: int(a / wd) for n, a in
                               [("50k@2%", 1000), ("50k@3%", 1500),
                                ("100k@2%", 2000), ("100k@3%", 3000)]}
        m = c["max_1r_dollars"]
        print("%-26s %9.2f %9d %9d %9d %9d"
              % (k, c["worst_day_r"], m["50k@2%"], m["50k@3%"],
                 m["100k@2%"], m["100k@3%"]))

    print("\npaired day-block bootstrap of the S-exemptions vs the SAME gate without one")
    print("%-36s %10s %10s %10s %s" % ("cell", "delta", "lo95", "hi95", "readable?"))
    for k, m in scont.items():
        if not k.endswith(("+Scont", "+Sprof")):
            continue
        plain = k.rsplit(" +", 1)[0]
        ref = scont.get(plain) or cells.get(plain)
        if not ref:
            continue
        d, lo, hi = bootstrap(m["_daily"], ref["_daily"], sessions, args.boot)
        m["boot_vs_plain"] = {"delta": d, "lo95": lo, "hi95": hi}
        print("%-36s %10.1f %10.1f %10.1f %s"
              % (k, d, lo, hi, "YES" if lo * hi > 0 else "no (spans 0)"))

    for c in list(cells.values()) + list(scont.values()):
        c.pop("_daily", None)
    OUT.write_text(json.dumps({"meta": meta, "sessions": len(sessions),
                               "candidates": len(cand), "grid": cells,
                               "s_continuation": scont, "head_to_head": h2h,
                               "edge_by_streak": streak_tab,
                               "edge_by_day_r": dayr_tab},
                              indent=1), encoding="utf-8")
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
