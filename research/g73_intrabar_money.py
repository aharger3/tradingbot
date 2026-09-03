"""G73 / intrabar -- CLOSE-ONLY vs INTRABAR-TOUCH, priced on the two-year book.

Austin, 2026-08-29:

    "stop loss is not on candle close i dont like that, stop happen when they do
     in middle of timeframes."

Five full 2-year replays. Nothing in the shipped engine is edited: `STOP_ON_CLOSE`
and `DISASTER_STOP` / `DISASTER_STOP_R` are env knobs `backtest_week.py` already
ships, and the close-fill clamp is moved by rebinding the module attribute
`backtest_week.stop_fill_price` to the SAME `stop_rule.stop_fill_price` with a
different `floor_r` -- the same seam `research/g72_catastrophic_stop.py` uses.

THE ARMS
--------
    shipped        what runs today. Level stop triggers on the CLOSE, but a
                   resting order sits at -1.00R and fills on a TOUCH, so in
                   practice the book is already intrabar. Clamp -1.25R.
    close_nowall   close-only, honestly: trigger on the close, FILL at that
                   close, nothing capping it (floor_r = inf).
    close_wall     close-only + Austin's $2,500 catastrophic wall as a REAL
                   resting order filled on a touch, with the clamp moved out to
                   the same number so nothing else caps the trade
                   (= research/g72_catastrophic_stop.py's `touch_2500`).
    intra_nowall   intrabar: the LEVEL stop triggers on the WICK
                   (`STOP_ON_CLOSE=0`), and fills where the resting order sits
                   -- unless the bar OPENED already past it, in which case it
                   fills at that open. Nothing capping it.
    intra_wall     the same, with the $2,500 wall as the fill floor.

WHY THE INTRABAR FILL IS PATCHED, AND WHAT IT IS PATCHED TO
-----------------------------------------------------------
`backtest_week._stop_fill_px` short-circuits to `t.stop` whenever
`STOP_ON_CLOSE=0` (the retired wick trigger kept only so `t4_stop_on_close`'s
A/B reproduces). Two things are wrong with that as a model of a live resting
order, and both flatter the intrabar arm:

  1. It books the ORIGINAL stop even when the stop that FIRED was the runner's
     break-even stop. A break-even wick-out would book -1.000R instead of 0R.
  2. A bar that OPENS below the stop cannot fill at the stop. A resting order
     fills at the open. Booking `t.stop` makes every intrabar loss exactly
     -1.000R by construction -- which is the same unreachable-rule fingerprint
     `research/x2_stop_floor_audit.md` found in the -1.25R floor.

So the intrabar arms rebind `backtest_week._stop_fill_px` to
`_intrabar_fill_px` below, which takes whichever stop level was working, fills
at it, degrades to the bar's open on a gap, and then routes the result through
`stop_rule.stop_fill_price` for the floor. The fill definition is still
stop_rule's; only the price handed to it changes.

1R = $1,000 (CLAUDE.md), so a $2,500 wall IS 2.5R.

REUSED, NEVER REIMPLEMENTED
---------------------------
    backtest_2y.main                              the replay
    stop_rule.stop_fill_price                     the one fill definition
    research.g72_suppress_price.stats             win rate / months / weeks / DD
    research.g72_suppress_price.shipped_rows      the all-trades stream
    research.g72_suppress_price.oneaday_rows      the one-trade-a-day stream

USAGE
-----
    python research/g73_intrabar_money.py run       # every arm (parallel)
    python research/g73_intrabar_money.py analyse   # the tables -> json
    python research/g73_intrabar_money.py --selfcheck
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for _p in (str(HERE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

INF = float("inf")
RISK = 1000.0
WALL_R = 2.5          # Austin's $2,500 catastrophic wall, G72
ANALYSIS = HERE / "_g73_money.json"

# Big books go to the scratchpad, not into research/ -- g72_after.md flags
# 654 MB of uncovered measurement files there already.
BOOKDIR = Path(os.environ.get(
    "G73_BOOKDIR",
    r"C:\Users\aharg\AppData\Local\Temp\claude\C--Users-aharg-Desktop-Projects-tradingbot"
    r"\ac6fe5fc-d9ec-4428-bfd3-077695d1bca4\scratchpad"))

# arm -> (stop_on_close, resting order in R or None, close-fill clamp in R, patch fill?)
ARMS = {
    "shipped":      (True,  1.00,   1.25, False),
    "close_nowall": (True,  None,   INF,  False),
    "close_wall":   (True,  WALL_R, WALL_R, False),
    "intra_nowall": (False, None,   INF,  True),
    "intra_wall":   (False, None,   WALL_R, True),
}
ORDER = ["shipped", "close_nowall", "close_wall", "intra_nowall", "intra_wall"]


def arm_out(arm):
    return BOOKDIR / ("g73_%s.json" % arm)


# ---------------------------------------------------------------------------
# the intrabar fill
# ---------------------------------------------------------------------------
def _intrabar_fill_px(t, c, long, floor_r=INF):
    """What a resting stop order books on the bar that touched it.

    ``t`` is a backtest_week.SimTrade, ``c`` an omen_bot.Candle. The working
    level is the runner's stop once it has moved, else the trade's original
    stop -- the same expression every call site in `backtest_week._ladder_bar`
    uses to decide what to test. The order fills AT that level, unless the bar
    opened already beyond it, in which case a resting order fills at the open.
    The floor is applied by `stop_rule.stop_fill_price`, never re-derived here.
    """
    from stop_rule import stop_fill_price
    lv = t.runner_stop if getattr(t, "runner_stop", None) else t.stop
    px = min(lv, c.open) if long else max(lv, c.open)
    return stop_fill_price(px, t.entry, abs(t.entry - t.stop), long, floor_r=floor_r)


def install(stop_on_close, rest, floor_r, patch_fill):
    """Set every knob for one arm. Env first -- backtest_week reads it at import."""
    os.environ["STOP_ON_CLOSE"] = "1" if stop_on_close else "0"
    if rest is None:
        os.environ["DISASTER_STOP"] = "0"
    else:
        os.environ["DISASTER_STOP"] = "1"
        os.environ["DISASTER_STOP_R"] = repr(rest)
    import backtest_week as bw
    from stop_rule import stop_fill_price as real
    assert bw.STOP_ON_CLOSE == stop_on_close, "STOP_ON_CLOSE did not take"
    assert bw.DISASTER_STOP == (rest is not None), "DISASTER_STOP did not take"
    if rest is not None:
        assert abs(bw.DISASTER_R - rest) < 1e-9, "DISASTER_STOP_R did not take"

    def clamp(close, entry, risk, long, floor_r_arg=None):
        return real(close, entry, risk, long, floor_r=floor_r)
    bw.stop_fill_price = clamp
    if patch_fill:
        def fill(t, c, long):
            return _intrabar_fill_px(t, c, long, floor_r=floor_r)
        bw._stop_fill_px = fill


def child(arm, out):
    install(*ARMS[arm])
    import backtest_2y
    sys.argv = ["backtest_2y.py", "--out", str(out)]
    backtest_2y.main()


def run(arms, jobs=5):
    import time
    BOOKDIR.mkdir(parents=True, exist_ok=True)
    todo = [a for a in arms if not arm_out(a).exists()]
    print("running %d arms, %d already on disk" % (len(todo), len(arms) - len(todo)),
          flush=True)
    procs = []
    for a in todo:
        while sum(1 for _, p, _ in procs if p.poll() is None) >= jobs:
            time.sleep(5)
        cmd = [sys.executable, str(HERE / "g73_intrabar_money.py"),
               "child", "--arm", a, "--out", str(arm_out(a))]
        log = open(BOOKDIR / ("g73_%s.log" % a), "w")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        procs.append((a, subprocess.Popen(cmd, cwd=str(ROOT), stdout=log,
                                          stderr=subprocess.STDOUT, env=env), log))
        print("launched %s" % a, flush=True)
    for a, p, log in procs:
        p.wait()
        log.close()
        print("%-14s rc=%s" % (a, p.returncode), flush=True)


# ---------------------------------------------------------------------------
# analysis
# ---------------------------------------------------------------------------
def load(arm):
    with open(arm_out(arm), encoding="utf-8") as fh:
        b = json.load(fh)
    return b["meta"], b["trades"]


def loss_read(rows):
    """Average loss and worst single trade, in POSITIVE dollars, over the
    stream handed in (all-trades or one-a-day)."""
    lo = sorted(-r["pnl"] for r in rows if r["pnl"] < 0)
    return {
        "n_losing": len(lo),
        "avg_loss": round(statistics.fmean(lo), 0) if lo else 0.0,
        "median_loss": round(statistics.median(lo), 0) if lo else 0.0,
        "worst_trade": round(lo[-1], 0) if lo else 0.0,
        "losses_over_2500": sum(1 for x in lo if x > 2500.0 + 1e-6),
    }


def key(r):
    return (r["sym"], r["day"], r["et"], r["setup"], r["dir"])


def paired(a_rows, b_rows):
    """B minus A on the rows both books hold. Rows are matched on
    (symbol, day, entry time, setup, direction). The two books do NOT hold the
    same rows -- R31's loss halt is causal on realised outcomes, so changing an
    outcome changes which later trades were blocked. only_a / only_b count that
    drift rather than hiding it."""
    A = {key(r): r for r in a_rows}
    B = {key(r): r for r in b_rows}
    both = sorted(set(A) & set(B))
    d = [B[k]["r"] - A[k]["r"] for k in both]
    if not d:
        return {}
    m = statistics.fmean(d)
    se = (statistics.stdev(d) / math.sqrt(len(d))) if len(d) > 1 else 0.0
    return {"n": len(d), "delta_mean_r": round(m, 4), "se": round(se, 4),
            "t": round(m / se, 2) if se else None,
            "delta_per_trade_usd": round(m * RISK, 0),
            "only_a": len(set(A) - set(B)), "only_b": len(set(B) - set(A))}


def analyse():
    from g72_suppress_price import stats, shipped_rows, oneaday_rows

    out = {"arms": {}, "wall_r": WALL_R, "risk_dollars": RISK}
    books = {}
    for a in ORDER:
        if not arm_out(a).exists():
            print("MISSING %s" % arm_out(a))
            continue
        meta, rows = load(a)
        nd = meta["sessions"]
        allr, one = shipped_rows(rows), oneaday_rows(rows)
        books[a] = (meta, rows, allr, one)
        out["arms"][a] = {
            "meta": {k: meta.get(k) for k in ("generated", "sessions", "signals",
                                              "traded", "halted")},
            "all": dict(stats(allr, nd), **loss_read(allr)),
            "one_a_day": dict(stats(one, nd), **loss_read(one)),
        }

    # paired A/B: intrabar minus close-only, all trades, both wall settings
    out["paired"] = {}
    for a, b in (("close_nowall", "intra_nowall"),
                 ("close_wall", "intra_wall"),
                 ("close_nowall", "close_wall"),
                 ("intra_nowall", "intra_wall"),
                 ("shipped", "intra_nowall"),
                 ("shipped", "close_nowall")):
        if a in books and b in books:
            out["paired"]["%s->%s" % (a, b)] = paired(books[a][2], books[b][2])

    ANALYSIS.write_text(json.dumps(out, indent=1), encoding="utf-8")
    _print(out)
    print("\nwrote %s" % ANALYSIS)
    return out


F = [("trades", "%d"), ("win_pct", "%.1f%%"), ("mean_r", "%.4f"),
     ("per_day", "$%.0f"), ("months_green", "%d"), ("weeks_green", "%d"),
     ("worst_drawdown", "$%.0f"), ("worst_trade", "$%.0f"), ("avg_loss", "$%.0f")]


def _print(out):
    for stream in ("all", "one_a_day"):
        print("\n=== %s ===" % stream.upper())
        hdr = "%-14s" % "arm" + "".join("%14s" % f for f, _ in F)
        print(hdr)
        for a in ORDER:
            if a not in out["arms"]:
                continue
            s = out["arms"][a][stream]
            print("%-14s" % a + "".join(("%14s" % (fmt % s[f])) if s.get(f) is not None
                                        else "%14s" % "-" for f, fmt in F))
    print("\n=== PAIRED (B minus A, mean R per trade, all trades) ===")
    for k, v in out["paired"].items():
        if not v:
            continue
        print("  %-28s n=%5d  %+0.4f R  SE %0.4f  t %+0.2f   (%+d $/trade)  only_a=%d only_b=%d"
              % (k, v["n"], v["delta_mean_r"], v["se"], v["t"] or 0,
                 v["delta_per_trade_usd"], v["only_a"], v["only_b"]))


def _selfcheck():
    class T:
        entry, stop, runner_stop = 100.0, 99.0, None

    class C:
        def __init__(s, o):
            s.open = o
    t = T()
    # long, no gap: the resting order fills AT the stop -> -1.000R
    assert abs(_intrabar_fill_px(t, C(100.2), True) - 99.0) < 1e-9
    # long, bar opened 2R below: a resting order fills at the open, unfloored
    assert abs(_intrabar_fill_px(t, C(98.0), True) - 98.0) < 1e-9
    # ... and the 2.5R wall does not bind at 2R
    assert abs(_intrabar_fill_px(t, C(98.0), True, floor_r=2.5) - 98.0) < 1e-9
    # ... but does at 4R
    assert abs(_intrabar_fill_px(t, C(96.0), True, floor_r=2.5) - 97.5) < 1e-9
    # a moved (break-even) runner stop is honoured, not the original
    t2 = T(); t2.runner_stop = 100.0
    assert abs(_intrabar_fill_px(t2, C(100.4), True) - 100.0) < 1e-9
    # short side, mirrored
    class S:
        entry, stop, runner_stop = 100.0, 101.0, None
    s = S()
    assert abs(_intrabar_fill_px(s, C(99.8), False) - 101.0) < 1e-9
    assert abs(_intrabar_fill_px(s, C(102.0), False) - 102.0) < 1e-9
    assert abs(_intrabar_fill_px(s, C(104.0), False, floor_r=2.5) - 102.5) < 1e-9
    # the arm table is self-consistent: only the intrabar arms patch the fill
    for a, (soc, rest, fl, patch) in ARMS.items():
        assert patch == (not soc), a
    print("g73 money selfcheck ok: 9 checks")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="analyse",
                    choices=["run", "child", "analyse"])
    ap.add_argument("--arm")
    ap.add_argument("--out")
    ap.add_argument("--jobs", type=int, default=5)
    if "--selfcheck" in sys.argv:
        _selfcheck()
        sys.exit(0)
    a = ap.parse_args()
    if a.cmd == "child":
        child(a.arm, a.out)
    elif a.cmd == "run":
        run(ORDER, jobs=a.jobs)
    else:
        analyse()
