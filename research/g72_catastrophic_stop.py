"""G72 -- WHERE THE CATASTROPHIC STOP GOES, measured.

Austin, 2026-08-29:

    "i want it to just be 1k max loss so each loss hits that on average, but
     whatever increases edge right now which was option 1. i just dont want to
     enter a trade and somehow lose 10000 you see what i mean so some parameter
     has to be out there"

Two halves, both binding:

  1. DELETE the resting order that sits at the level-stop price. That is his
     "option 1" -- it restores "wicks stop nothing", the stop triggers on the
     candle CLOSE and fills at that close (g71_board.md section 6: win rate
     49.5% -> 55.0%, worst drawdown $17,132 -> $13,700).
  2. A CATASTROPHIC backstop still has to exist, far enough out that it never
     touches a normal trade, so that one trade cannot cost $10,000.

THE THING THAT MAKES THIS MEASURABLE AT ALL
-------------------------------------------
`stop_rule.stop_fill_price` clamps every close-triggered fill at -1.25R
(`MAX_LOSS_R`). That clamp is NOT an order. It is a `max()` in the backtest
that books a better price than the market gave. So the shipped book -- and the
"resting order deleted" arm in `research/g71_stops.py` (`D_off`) -- both report
a worst single trade of exactly -$1,250 for a reason that has nothing to do
with the market. Sweeping a catastrophic level ABOVE $1,250 against a book
already clamped at $1,250 measures nothing: the clamp does all the work and the
new level is unreachable code, the exact failure mode
`research/x2_stop_floor_audit.md` found in the -1.25R floor itself.

So every arm here sets the clamp and the resting order to the SAME number, and
the `none` arm removes the clamp entirely (`floor_r = inf`) to show what the
close-only rule actually books when nothing is protecting it. That `none` book
is the honest loss distribution, and it is the first table in the report.

ARMS
----
    none         no resting order, NO clamp.  The truth: fill at the close.
    shipped      resting order at 1.00R + clamp 1.25R.  Today's engine.
    clamp1250    no resting order, clamp 1.25R.  = g71_stops `D_off`, the
                 "option 1" book as it was measured -- kept so this report and
                 the board agree, and so the clamp's contribution is visible.
    touch_XXXX   no order at the level stop; ONE resting order at $XXXX, filled
                 on an intrabar TOUCH, and the close-fill clamp moved out to the
                 same $XXXX so nothing else caps the trade.

1R = $1,000 (CLAUDE.md), and `r = pnl / RISK_DOLLARS` (backtest_2y.py:172), so a
$2,000 catastrophic level IS `DISASTER_STOP_R = 2.0`. Dollars and R are the same
axis here; the report speaks dollars because he does.

NO ENGINE FILE IS EDITED. `DISASTER_STOP` / `DISASTER_STOP_R` are the env knobs
`backtest_week.py` already ships. The clamp has no env knob, so the child
process rebinds `backtest_week.stop_fill_price` to the SAME
`stop_rule.stop_fill_price` with a different `floor_r` -- the fill definition is
never reimplemented, only its floor is moved.

REUSED, NEVER REIMPLEMENTED
---------------------------
    backtest_2y.main                        the replay
    stop_rule.stop_fill_price               the one fill definition
    research.g71_stops.book                 the money + durability read
    research.a2_bt2y_summary.book           (via the above) the whole-book read
    research.g71_losshalt_grid.walk_day     the 3-loss / -$2,000 governor

USAGE
-----
    python research/g72_catastrophic_stop.py run       # every arm, parallel
    python research/g72_catastrophic_stop.py analyse   # the tables -> json
    python research/g72_catastrophic_stop.py report    # the markdown tables
    python research/g72_catastrophic_stop.py --selfcheck
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ANALYSIS = os.path.join(HERE, "_g72_analysis.json")

# arm -> (resting order in R from entry or None, close-fill clamp in R)
INF = float("inf")
ARMS = {
    "none":       (None, INF),
    "shipped":    (1.00, 1.25),
    "clamp1250":  (None, 1.25),
    "touch_1250": (1.25, 1.25),
    "touch_1500": (1.50, 1.50),
    "touch_2000": (2.00, 2.00),
    "touch_2500": (2.50, 2.50),
    "touch_3000": (3.00, 3.00),
    "touch_4000": (4.00, 4.00),
    "touch_5000": (5.00, 5.00),
}
SWEEP = ["touch_1250", "touch_1500", "touch_2000", "touch_2500",
         "touch_3000", "touch_4000", "touch_5000", "none"]
LEVEL_USD = {"touch_1250": 1250, "touch_1500": 1500, "touch_2000": 2000,
             "touch_2500": 2500, "touch_3000": 3000, "touch_4000": 4000,
             "touch_5000": 5000, "none": None}
RISK_DOLLARS = 1000.0


def arm_out(arm):
    return os.path.join(HERE, "_g72_%s.json" % arm)


# ---------------------------------------------------------------------------
# child -- one full 2-year replay under one arm
# ---------------------------------------------------------------------------
def install_floor(floor_r):
    """Move the close-fill clamp WITHOUT touching stop_rule or backtest_week.

    `backtest_week` does `from stop_rule import ... stop_fill_price`, so the
    name it calls is `backtest_week.stop_fill_price`. Rebinding that module
    attribute to a wrapper around the REAL function moves the floor and nothing
    else -- the fill convention (fill at the close, clamped on the losing side
    only, denominated in the trade's ORIGINAL risk) is still stop_rule's."""
    import backtest_week as bw
    from stop_rule import stop_fill_price as real

    def wrapper(close, entry, risk, long, floor_r_arg=floor_r):
        return real(close, entry, risk, long, floor_r=floor_r)
    bw.stop_fill_price = wrapper


def child(arm, out):
    rest, floor_r = ARMS[arm]
    # env is read at backtest_week import time, so it must be set first
    if rest is None:
        os.environ["DISASTER_STOP"] = "0"
    else:
        os.environ["DISASTER_STOP"] = "1"
        os.environ["DISASTER_STOP_R"] = repr(rest)
    import backtest_week as bw
    assert bw.DISASTER_STOP == (rest is not None), "disaster flag did not take"
    if rest is not None:
        assert abs(bw.DISASTER_R - rest) < 1e-9, "disaster level did not take"
    install_floor(floor_r)
    import backtest_2y
    sys.argv = ["backtest_2y.py", "--out", out]
    backtest_2y.main()


def run(arms, jobs=5):
    import time
    todo = [a for a in arms if not os.path.exists(arm_out(a))]
    print("running %d arms, %d already on disk" % (len(todo), len(arms) - len(todo)),
          flush=True)
    procs = []
    for a in todo:
        while sum(1 for _, p, _ in procs if p.poll() is None) >= jobs:
            time.sleep(5)
        cmd = [sys.executable, os.path.join(HERE, "g72_catastrophic_stop.py"),
               "child", "--arm", a, "--out", arm_out(a)]
        log = open(os.path.join(HERE, "_g72_%s.log" % a), "w")
        procs.append((a, subprocess.Popen(cmd, cwd=ROOT, stdout=log,
                                          stderr=subprocess.STDOUT), log))
        print("launched %s" % a, flush=True)
    for a, p, log in procs:
        p.wait()
        log.close()
        print("%-12s rc=%s" % (a, p.returncode), flush=True)


def load(arm):
    with open(arm_out(arm)) as f:
        return json.load(f)["trades"]


# ---------------------------------------------------------------------------
# (a) the loss distribution
# ---------------------------------------------------------------------------
def pctl(xs, p):
    """Nearest-rank percentile, same convention as research/g71_stops.pct."""
    if not xs:
        return 0.0
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))
    return s[i]


def loss_dist(rows):
    """Every losing trade, in POSITIVE dollars. A loss is a trade whose booked
    P&L is negative -- that includes the handful of EOD scratches that closed
    below entry, because he loses the money either way."""
    tr = [r for r in rows if r["traded"]]
    lo = sorted(-r["r"] * RISK_DOLLARS for r in tr if r["r"] < 0)
    n_stop = sum(1 for r in tr if r["out"] == "loss")
    return {
        "n_trades": len(tr), "n_losing": len(lo), "n_out_loss": n_stop,
        "mean": round(statistics.fmean(lo), 1) if lo else 0.0,
        "median": round(statistics.median(lo), 1) if lo else 0.0,
        "p75": round(pctl(lo, 75), 1), "p90": round(pctl(lo, 90), 1),
        "p95": round(pctl(lo, 95), 1), "p99": round(pctl(lo, 99), 1),
        "worst": round(lo[-1], 1) if lo else 0.0,
        "over_1250": sum(1 for x in lo if x > 1250.0 + 1e-6),
        "over_1500": sum(1 for x in lo if x > 1500.0 + 1e-6),
        "over_2000": sum(1 for x in lo if x > 2000.0 + 1e-6),
        "over_3000": sum(1 for x in lo if x > 3000.0 + 1e-6),
        "over_5000": sum(1 for x in lo if x > 5000.0 + 1e-6),
        "over_10000": sum(1 for x in lo if x > 10000.0 + 1e-6),
        "tail_usd_over_1250": round(sum(max(0.0, x - 1250.0) for x in lo)),
        "total_loss_usd": round(sum(lo)),
    }


def tail_curve(rows):
    """(c) The knee, as a curve. For each candidate level: how many trades of
    the WHOLE book lost more than it, and how many dollars of loss sit beyond
    it. Read off the uncapped book, so it is the tail as it actually happened
    -- before any cap changes an outcome."""
    tr = [r for r in rows if r["traded"]]
    lo = [-r["r"] * RISK_DOLLARS for r in tr if r["r"] < 0]
    tot = sum(lo) or 1.0
    out = []
    for X in (1000, 1250, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000, 5000):
        k = sum(1 for x in lo if x > X)
        t = sum(max(0.0, x - X) for x in lo)
        out.append({"level": X, "trades_over": k,
                    "pct_of_book": round(k / len(tr) * 100, 2) if tr else 0.0,
                    "tail_usd": round(t), "pct_of_all_loss": round(t / tot * 100, 2)})
    return out


# ---------------------------------------------------------------------------
# (b) what a level costs: paired against the uncapped book
# ---------------------------------------------------------------------------
def key(r):
    return (r["sym"], r["day"], r["et"], r["setup"], r["dir"])


def binds(base_rows, arm_rows):
    """How many trades the cap actually TOUCHES, split into the two kinds.

    truncated -- the uncapped book lost more than the cap, so the cap cut a
                 real disaster short. This is what he is buying.
    killed    -- the uncapped book did NOT lose more than the cap, but the bar
                 WICKED through it. A resting order fills on a touch, so the
                 trade is out at the cap even though leaving it alone was
                 better (it may even have been a winner). This is what the cap
                 costs, and it is the reason a cap cannot simply be moved in.

    Rows are matched on (symbol, day, entry time, setup, direction). The two
    books do not hold identical rows: R31's 2-loss halt is causal on realised
    outcomes, so changing an outcome changes which later trades were blocked.
    only_base / only_arm count that drift rather than hiding it."""
    A = {key(r): r for r in base_rows if r["traded"]}
    B = {key(r): r for r in arm_rows if r["traded"]}
    both = set(A) & set(B)
    trunc = killed = 0
    trunc_saved = killed_cost = 0.0
    flips = 0
    for k in both:
        a, b = A[k]["r"], B[k]["r"]
        if abs(a - b) < 1e-6:
            continue
        if b > a:                    # the cap improved the row -> real disaster cut short
            trunc += 1
            trunc_saved += (b - a) * RISK_DOLLARS
        else:
            killed += 1
            killed_cost += (a - b) * RISK_DOLLARS
            if A[k]["r"] > 0:
                flips += 1
    n = len(both)
    return {"n_pair": n, "only_base": len(set(A) - set(B)),
            "only_arm": len(set(B) - set(A)),
            "binds": trunc + killed,
            "binds_pct": round((trunc + killed) / n * 100, 2) if n else 0.0,
            "truncated": trunc, "killed": killed, "killed_winners": flips,
            "saved_usd": round(trunc_saved), "cost_usd": round(killed_cost),
            "net_usd": round(trunc_saved - killed_cost)}


# ---------------------------------------------------------------------------
# (e) touch or close? -- the measurement, not the opinion
# ---------------------------------------------------------------------------
def gap_autopsy(rows, level_r=2.0):
    """For every trade that lost more than ``level_r`` R with nothing capping
    it, replay the two bars around the exit and ask what a CLOSE-checked
    catastrophic stop could have done.

    The exit bar index is `entry_i + bars`, the same arithmetic
    `research/g71_losshalt_grid.xkey` uses. Bars come from `polygon_feed.rth`
    off `data_archive/` -- no fetches, and no fill is recomputed: this only
    reads where price CLOSED.

    Three counts:
      prior_inside  the bar BEFORE the exit still closed inside 1R -- so the
                    whole overshoot happened in one candle and no close-checked
                    rule at any level between 1R and the loss could have fired
                    a bar earlier. The trade was already gone.
      touched_first the bar's LOW (HIGH for puts) reached the level BEFORE its
                    close did -- a resting order would have filled there.
      never_touched the level was never traded at all intrabar; only the close
                    got there. A resting order would not have filled either."""
    import polygon_feed as pf
    tr = [r for r in rows if r["traded"] and r["r"] < -level_r]
    cache = {}
    prior_inside = touched = never = skipped = 0
    prior_r = []
    for r in tr:
        k = (r["sym"], r["day"])
        if k not in cache:
            try:
                cache[k] = pf.rth(pf.fetch_day(*k))
            except Exception:
                cache[k] = []
        bars = cache[k]
        i = r.get("entry_i", 0) + r.get("bars", 0)
        risk = abs(r["entry"] - r["stop"])
        if not bars or i >= len(bars) or risk <= 0:
            skipped += 1
            continue
        long = r["side"] == "L"
        lv = r["entry"] - level_r * risk if long else r["entry"] + level_r * risk
        ext = bars[i].low if long else bars[i].high
        if (ext <= lv) if long else (ext >= lv):
            touched += 1
        else:
            never += 1
        if i - 1 > r.get("entry_i", 0):
            pc = bars[i - 1].close
            pr = ((pc - r["entry"]) if long else (r["entry"] - pc)) / risk
            prior_r.append(pr)
            if pr > -1.0:
                prior_inside += 1
    return {"level_r": level_r, "n": len(tr), "skipped": skipped,
            "touched_intrabar_first": touched, "never_touched_only_closed": never,
            "prior_bar_measured": len(prior_r),
            "prior_bar_still_inside_1R": prior_inside,
            "prior_bar_median_r": round(statistics.median(prior_r), 3) if prior_r else None}


def mae_scan(rows, n_sample=1200, seed=7):
    """(c) "far enough out that it never touches a normal trade", measured.

    A RESTING order does not care how the trade ended -- it fills the moment
    price reaches it. So the population that matters is not "trades that lost
    more than $X", it is "trades whose worst moment reached $X", winners
    included. This walks the bars each trade was actually open for
    (`entry_i` .. `entry_i + bars`, the same arithmetic
    `research/g71_losshalt_grid.xkey` uses) and takes the maximum adverse
    excursion in R. Sampled, because it is a bar read per trade."""
    import random
    import polygon_feed as pf
    tr = [r for r in rows if r["traded"]]
    random.Random(seed).shuffle(tr)
    tr = tr[:n_sample]
    cache = {}
    win, lose = [], []
    for r in tr:
        k = (r["sym"], r["day"])
        if k not in cache:
            try:
                cache[k] = pf.rth(pf.fetch_day(*k))
            except Exception:
                cache[k] = []
        bars = cache[k]
        i0 = r.get("entry_i", 0)
        i1 = i0 + r.get("bars", 0)
        risk = abs(r["entry"] - r["stop"])
        if not bars or risk <= 0 or i1 >= len(bars) or i1 < i0:
            continue
        seg = bars[i0:i1 + 1]
        long = r["side"] == "L"
        ext = min(b.low for b in seg) if long else max(b.high for b in seg)
        m = ((r["entry"] - ext) if long else (ext - r["entry"])) / risk
        (win if r["r"] > 0 else lose).append(m)
    allm = win + lose
    out = {"n": len(allm), "n_win": len(win), "levels": []}
    for X in (1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
        out["levels"].append({
            "level": int(X * RISK_DOLLARS),
            "all": sum(1 for x in allm if x >= X),
            "all_pct": round(sum(1 for x in allm if x >= X) / max(len(allm), 1) * 100, 2),
            "winners": sum(1 for x in win if x >= X),
            "winners_pct": round(sum(1 for x in win if x >= X) / max(len(win), 1) * 100, 2)})
    return out


# ---------------------------------------------------------------------------
# (f) the sequencing governor, on the UNCAPPED book
# ---------------------------------------------------------------------------
def governor(rows, halt_n=3, r_floor=-2.0):
    """Austin's chosen sequencing rule -- 3 closed losses in a row ends the day,
    and realised day P&L at or below -$2,000 ends the day -- run over this
    book with `research.g71_losshalt_grid.walk_day`, imported not copied.

    The candidate pool is rebuilt exactly as that module does: rows that fired
    and traded, plus rows R31 blocked, i.e. the unhalted book.

    The question this answers is narrow and it is the whole of (f): the floor is
    a gate on the NEXT entry, evaluated against trades that have already CLOSED.
    It cannot reach inside a position that is open right now."""
    from research.g71_losshalt_grid import walk_day
    cand = [r for r in rows
            if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
    by_day = defaultdict(list)
    for r in cand:
        by_day[r["day"]].append(r)
    taken = []
    for day in sorted(by_day):
        taken += walk_day(by_day[day], halt_n, False, r_floor)
    day_r = defaultdict(float)
    for r in taken:
        day_r[r["day"]] += r["r"]
    curve = [day_r[d] for d in sorted(day_r)]
    peak = cum = dd = 0.0
    for v in curve:
        cum += v
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    worst_trade = min((r["r"] for r in taken), default=0.0)
    worst_day = min(curve, default=0.0)
    return {"halt_n": halt_n, "r_floor": r_floor, "n": len(taken),
            "days": len(day_r),
            "total_usd": round(sum(r["r"] for r in taken) * RISK_DOLLARS),
            "worst_trade_usd": round(worst_trade * RISK_DOLLARS),
            "worst_day_usd": round(worst_day * RISK_DOLLARS),
            "maxdd_usd": round(dd * RISK_DOLLARS),
            "days_worse_than_2000": sum(1 for v in curve if v < -2.0),
            "trades_worse_than_2000": sum(1 for r in taken if r["r"] < -2.0),
            "trades_worse_than_5000": sum(1 for r in taken if r["r"] < -5.0)}


# ---------------------------------------------------------------------------
def analyse():
    from research.g71_stops import book
    out = {"arms": {}, "dist": {}, "binds": {}, "governor": {}}
    base = load("none")
    out["dist"]["none"] = loss_dist(base)
    for arm in ARMS:
        if not os.path.exists(arm_out(arm)):
            continue
        rows = load(arm)
        b = book(rows)
        b.pop("by_month", None)
        b["mean_usd_per_trade"] = round(b["meanr"] * RISK_DOLLARS)
        b["worst_trade_usd"] = round(b["worst"] * RISK_DOLLARS)
        out["arms"][arm] = b
        out["dist"][arm] = loss_dist(rows)
        if arm != "none":
            out["binds"][arm] = binds(base, rows)
    # (d) "each loss hits $1,000 on average". With close-only stops the average
    # loss is set by how far past the level the candle closes, and no stop
    # placement can move it back to $1,000. The one lever that CAN is size:
    # dollars are a sizing skin (CLAUDE.md), so risking $k instead of $1,000
    # scales every loss AND every win by k/1000 and leaves mean R untouched.
    for arm in ("none", "touch_2000", "touch_2500", "touch_3000", "clamp1250"):
        if arm in out["dist"] and out["dist"][arm]["mean"]:
            out["dist"][arm]["risk_for_1000_avg_loss"] = round(
                RISK_DOLLARS * 1000.0 / out["dist"][arm]["mean"])
    out["tail_curve"] = tail_curve(base)
    out["mae"] = mae_scan(base)
    out["gap_autopsy"] = [gap_autopsy(base, lv) for lv in (2.0, 2.5, 3.0)]
    from research.g71_stops import paired
    out["paired_vs_none"] = {}
    for arm in ARMS:
        if arm == "none" or not os.path.exists(arm_out(arm)):
            continue
        out["paired_vs_none"][arm] = paired(base, load(arm))
    out["governor"]["none_3loss_2000"] = governor(base)
    out["governor"]["none_nogov"] = {
        "worst_trade_usd": round(min(r["r"] for r in base if r["traded"]) * RISK_DOLLARS)}
    if os.path.exists(arm_out("touch_2000")):
        out["governor"]["touch2000_3loss_2000"] = governor(load("touch_2000"))
    with open(ANALYSIS, "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out["dist"]["none"], indent=1))
    return out


def report():
    with open(ANALYSIS) as f:
        an = json.load(f)
    A, D, B = an["arms"], an["dist"], an["binds"]

    print("\n### (a) every losing trade, resting order deleted, no clamp -- arm `none`\n")
    d = D["none"]
    print("| trades | losing trades | mean loss | median | 90th | 95th | 99th | worst |")
    print("|--:|--:|--:|--:|--:|--:|--:|--:|")
    print("| %d | %d | $%s | $%s | $%s | $%s | $%s | **$%s** |"
          % (d["n_trades"], d["n_losing"], f"{d['mean']:,.0f}", f"{d['median']:,.0f}",
             f"{d['p90']:,.0f}", f"{d['p95']:,.0f}", f"{d['p99']:,.0f}",
             f"{d['worst']:,.0f}"))
    print("\nlosses past $1,250: %d | past $1,500: %d | past $2,000: %d | past $3,000: %d "
          "| past $5,000: %d | past $10,000: %d"
          % (d["over_1250"], d["over_1500"], d["over_2000"], d["over_3000"],
             d["over_5000"], d["over_10000"]))
    print("total lost on losing trades $%s, of which $%s sits beyond $1,250"
          % (f"{d['total_loss_usd']:,}", f"{d['tail_usd_over_1250']:,}"))

    print("\n### (b) the sweep\n")
    print("| catastrophic level | binds on | of which real | of which wicked out | "
          "mean loss | $/trade | win% | months | weeks | worst trade | worst drawdown |")
    print("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for arm in SWEEP:
        if arm not in A:
            continue
        b, dd = A[arm], D[arm]
        lv = LEVEL_USD[arm]
        bd = B.get(arm)
        lab = ("$%s" % f"{lv:,}") if lv else "none (uncapped)"
        cells = ("%d (%.1f%%) | %d | %d" % (bd["binds"], bd["binds_pct"],
                                            bd["truncated"], bd["killed"])
                 if bd else "- | - | -")
        print("| %s | %s | $%s | $%s | %.1f%% | %d/%d | %d/%d | $%s | $%s |"
              % (lab, cells, f"{dd['mean']:,.0f}", f"{b['mean_usd_per_trade']:,}",
                 b["wr"], b["months_green"], b["months"], b["weeks_green"], b["weeks"],
                 f"{dd['worst']:,.0f}", f"{abs(b['maxdd_usd']):,}"))
    for arm in ("shipped", "clamp1250"):
        if arm not in A:
            continue
        b, dd = A[arm], D[arm]
        print("| _%s_ | - | - | - | $%s | $%s | %.1f%% | %d/%d | %d/%d | $%s | $%s |"
              % ({"shipped": "today's engine (order rests at the level stop)",
                  "clamp1250": "option 1 as the board measured it (clamp $1,250)"}[arm],
                 f"{dd['mean']:,.0f}", f"{b['mean_usd_per_trade']:,}", b["wr"],
                 b["months_green"], b["months"], b["weeks_green"], b["weeks"],
                 f"{dd['worst']:,.0f}", f"{abs(b['maxdd_usd']):,}"))

    print("\n### (b2) what each level buys and what it costs\n")
    print("| level | trades it touches | dollars of disaster it cuts | "
          "dollars it gives back on trades that would have survived | "
          "winners it turns into losses | net |")
    print("|---|--:|--:|--:|--:|--:|")
    for arm in SWEEP:
        if arm not in B:
            continue
        bd = B[arm]
        net = (("+$%s" % f"{bd['net_usd']:,}") if bd["net_usd"] >= 0
               else ("-$%s" % f"{-bd['net_usd']:,}"))
        print("| $%s | %d of %d (%.1f%%) | +$%s | -$%s | %d | %s |"
              % (f"{LEVEL_USD[arm]:,}", bd["binds"], bd["n_pair"], bd["binds_pct"],
                 f"{bd['saved_usd']:,}", f"{bd['cost_usd']:,}",
                 bd["killed_winners"], net))

    print("\n### (c) the tail, on the uncapped book\n")
    print("| a cap here | trades that lost more | share of the book | "
          "dollars of loss beyond it | share of all loss |")
    print("|---|--:|--:|--:|--:|")
    for x in an.get("tail_curve", []):
        print("| $%s | %d | %.2f%% | $%s | %.2f%% |"
              % (f"{x['level']:,}", x["trades_over"], x["pct_of_book"],
                 f"{x['tail_usd']:,}", x["pct_of_all_loss"]))

    m = an.get("mae", {})
    if m:
        print("\n### (c) how often a RESTING order at each level is reached at all "
              "(sample of %d trades, %d of them winners)\n" % (m["n"], m["n_win"]))
        print("| order here | trades whose worst moment reached it | share | "
              "WINNERS whose worst moment reached it | share of winners |")
        print("|---|--:|--:|--:|--:|")
        for x in m["levels"]:
            print("| $%s | %d | %.2f%% | %d | %.2f%% |"
                  % (f"{x['level']:,}", x["all"], x["all_pct"], x["winners"],
                     x["winners_pct"]))

    pv = an.get("paired_vs_none", {})
    if pv:
        print("\n### does the cap cost edge? paired against the uncapped book\n")
        print("| level | shared rows | change in mean R | SE | t |")
        print("|---|--:|--:|--:|--:|")
        for arm in SWEEP[:-1] + ["clamp1250", "shipped"]:
            if arm not in pv:
                continue
            p = pv[arm]
            lab = ("$%s" % f"{LEVEL_USD[arm]:,}") if LEVEL_USD.get(arm) else arm
            print("| %s | %d | %+0.4f | %0.4f | %+0.2f |"
                  % (lab, p["n_pair"], p["delta"], p["se"], p["t"]))

    print("\n### (e) touch or close\n")
    print("| level | trades that lost more than it | reached it intrabar first | "
          "only its close got there | the bar BEFORE still closed inside $1,000 | "
          "where the trade stood at that prior close |")
    print("|---|--:|--:|--:|--:|--:|")
    for g in an.get("gap_autopsy", []):
        print("| $%s | %d | %d | %d | %d of %d | %s |"
              % (f"{int(g['level_r'] * RISK_DOLLARS):,}", g["n"],
                 g["touched_intrabar_first"], g["never_touched_only_closed"],
                 g["prior_bar_still_inside_1R"], g["prior_bar_measured"],
                 ("-$%d" % round(-g["prior_bar_median_r"] * RISK_DOLLARS))
                 if g["prior_bar_median_r"] is not None else "-"))

    print("\n### (f) the sequencing governor on the uncapped book\n")
    g = an["governor"]["none_3loss_2000"]
    print("3-loss cap + a -$2,000 floor on the day, no per-trade cap: "
          "%d trades over %d days, worst single trade **$%s**, worst day $%s, "
          "worst drawdown $%s. Days that still finished worse than -$2,000: %d. "
          "Single trades that alone lost more than $2,000: %d (more than $5,000: %d)."
          % (g["n"], g["days"], f"{-g['worst_trade_usd']:,}", f"{-g['worst_day_usd']:,}",
             f"{-g['maxdd_usd']:,}", g["days_worse_than_2000"],
             g["trades_worse_than_2000"], g["trades_worse_than_5000"]))
    if "touch2000_3loss_2000" in an["governor"]:
        g2 = an["governor"]["touch2000_3loss_2000"]
        print("\nSame governor WITH a $2,000 per-trade cap: %d trades, worst single "
              "trade $%s, worst day $%s, worst drawdown $%s, days past -$2,000: %d."
              % (g2["n"], f"{-g2['worst_trade_usd']:,}", f"{-g2['worst_day_usd']:,}",
                 f"{-g2['maxdd_usd']:,}", g2["days_worse_than_2000"]))


def selfcheck():
    """Cheap invariants. No replay."""
    import stop_rule
    ok = []
    src = open(os.path.join(ROOT, "backtest_week.py"), encoding="utf-8").read()
    # 1. the clamp really is bound as a backtest_week module attribute
    ok.append(("backtest_week binds stop_fill_price by name",
               "stop_fill_price" in src and "from stop_rule import" in src))
    # 2. an infinite floor returns the raw close, both sides
    f = stop_rule.stop_fill_price
    ok.append(("floor=inf long -> the close",
               abs(f(94.0, 100.0, 1.0, True, floor_r=INF) - 94.0) < 1e-9))
    ok.append(("floor=inf short -> the close",
               abs(f(106.0, 100.0, 1.0, False, floor_r=INF) - 106.0) < 1e-9))
    # 3. floor=1.25 is the shipped clamp and it BINDS on that same close
    ok.append(("floor=1.25 clamps a -6R close to -1.25R",
               abs(f(94.0, 100.0, 1.0, True) - 98.75) < 1e-9))
    # 4. a $2,000 level is 2.0R because 1R = $1,000
    ok.append(("dollars and R share an axis", RISK_DOLLARS == 1000.0
               and LEVEL_USD["touch_2000"] / RISK_DOLLARS == ARMS["touch_2000"][0]))
    # 5. every touch arm moves the clamp WITH the order, or the level is
    #    unreachable code
    ok.append(("clamp travels with the resting order",
               all(rest == floor for a, (rest, floor) in ARMS.items()
                   if a.startswith("touch_"))))
    # 6. the disaster stop is an intrabar TOUCH, not a close
    ok.append(("disaster stop is a touch",
               stop_rule.disaster_stop_hit(101.0, 98.0, 99.0, True)
               and not stop_rule.stop_hit_on_close(100.5, 99.0, True)))
    # 7. binds() splits the two kinds the right way round
    mk = lambda r: {"sym": "X", "day": "d", "et": "09:40", "setup": "s",
                    "dir": "call", "traded": True, "r": r}
    bb = binds([mk(-3.0)], [mk(-2.0)])
    ok.append(("binds: a truncated disaster", bb["truncated"] == 1 and bb["killed"] == 0))
    bb2 = binds([mk(+3.0)], [mk(-2.0)])
    ok.append(("binds: a killed winner", bb2["killed"] == 1
               and bb2["killed_winners"] == 1))
    bad = [n for n, v in ok if not v]
    for n, v in ok:
        print("%s  %s" % ("ok  " if v else "FAIL", n))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="analyse",
                    choices=["child", "run", "analyse", "report"])
    ap.add_argument("--arm")
    ap.add_argument("--out")
    ap.add_argument("--jobs", type=int, default=5)
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        sys.exit(selfcheck())
    if a.cmd == "child":
        child(a.arm, a.out)
    elif a.cmd == "run":
        run(list(ARMS), jobs=a.jobs)
    elif a.cmd == "report":
        report()
    else:
        analyse()


if __name__ == "__main__":
    main()
