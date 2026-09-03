"""research/test_runner_stop.py — the stop the SHIPPED book actually runs.

Rewritten 2026-09-03 (Austin's R1 ruling; see CLAUDE.md and MASTER_SPEC.md
section 1). The old version of this file imported only `research/exit_lab.py`,
which has ZERO occurrences of the word "disaster" and fills every stop off the
bar's close alone. `backtest_week.py` — the module that built every $/day
figure in this repo, including `research/bt2y_trades_retest_on.json` — never
calls exit_lab. This file ran three times on 2026-09-03 and printed PASS on
`research/exit_lab.py` while the code that actually manages the shipped book's
trades (`backtest_week._ladder_bar`, `backtest_week._disaster_hit`,
`backtest_week._stop_hit`) went completely unexercised by the `verify:` gate.

R1, Austin, 2026-09-03, verbatim: "MAX LOSS IS -1R HARD. THE LEVEL STOP IS
FINAL. If price closes past the level you retested, you're out at that close,
full stop. The '-1.25R floor' is FICTION and has never fired: 0 of 2,216
losses in the book are worse than -1.000R, because DISASTER_R=1.0 puts the
disaster stop exactly on the level stop. He chose this option knowing it means
the book's two years of results stay valid. So: DELETE the -1.25R rule
everywhere it is claimed... Do not 'wire the floor'. Remove the claim, keep
the behaviour."

That mechanism, in one line of algebra: `disaster_stop_price(entry, risk,
long, 1.0)` IS `stop`, because 1R *is* `abs(entry - stop)` by definition. The
resting disaster order therefore sits exactly at the level, fires on an
intrabar TOUCH (not a close), and books exactly -1.000R no matter how far the
bar guns past it. That also means CLAUDE.md's OLD claim "wicks stop nothing
out" is not what the shipped book does either — MASTER_SPEC section 1: "the
book's stops fill on a wick, at the level, at exactly -1.000R." Section 1
below proves both halves: the close-only trigger would NOT have fired on a
wick-and-close-back bar, and the trade is stopped out anyway, at the level,
because a resting order fills where it rests.

THREE SECTIONS:

  1. THE SHIPPED PATH. Drives `backtest_week`'s own functions directly --
     `stop_rule.disaster_stop_price`, `backtest_week._disaster_hit`,
     `backtest_week._stop_hit`, and `backtest_week._ladder_bar` itself (the
     function that actually built the 2-year book: `OMEN_LADDER_MODE`
     defaults to "B" = `SCALE_PLAN="hod_then_runner_be"` = `_ladder_bar`) --
     plus a check against the real book on disk. THIS is the section that
     must go red if the floor becomes reachable again or the stop trigger
     changes.
  2. EXIT_LAB — LAB COVERAGE, NOT THE SHIPPED PATH. `research/exit_lab.py` is
     a real, actively-used research module (~20 other scripts import it) for
     exploring ATR-trail / break-even-runner scale-out POLICIES that
     `backtest_week.py` does not ship. It genuinely has no disaster stop, so
     its own -1.25R floor genuinely is reachable in ITS model -- that is not
     a bug, it is a different, simpler world than the one the shipped book
     runs in. Kept here so nobody again mistakes it for section 1.
  3. STOP PLACEMENT (signal_runner, the live path). Unrelated to the trigger/
     fill bug above -- WHERE the stop sits (structural / candle-entered /
     level / OCR wick), not when it fires. Real, shipped, untouched by this
     rewrite.

Run:  python research/test_runner_stop.py
"""

from __future__ import annotations
import json
import os
import subprocess
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backtest_week as bw                        # noqa: E402
import stop_rule                                   # noqa: E402
from omen_bot import Candle                         # noqa: E402
from research.exit_lab import (                     # noqa: E402
    CLOCK_BAR,
    MAX_LOSS_R,
    hod_only,
    policy_30_30_30_10,
    policy_50_20_20_10,
)

EPS = 1e-9


# ===========================================================================
# SECTION 1 -- THE SHIPPED PATH (R1)
# ===========================================================================

def _candle(o, h, l, c):
    return Candle("09:46:00", o, h, l, c, 1000)


def _mktrade(entry=100.0, stop=99.0, direction="call",
            scale_far=50.0, runner_far=80.0):
    """A real `backtest_week.SimTrade`, scale/runner rungs placed far away so
    a stop-out case can never accidentally clip a scale rung instead."""
    risk = abs(entry - stop)
    target = entry + 2 * risk if direction == "call" else entry - 2 * risk
    sign = 1.0 if direction == "call" else -1.0
    return bw.SimTrade(symbol="TEST", day="2026-01-02", signal_type="break_and_retest",
                       direction=direction, grade="B", status="fired",
                       entry_time="09:45:00", entry=entry, stop=stop, target=target,
                       reason="test", entry_idx=10, exit_idx=10,
                       scale_level=entry + sign * scale_far,
                       runner_target=entry + sign * runner_far)


def _flat_runner(entry, n=11):
    return [_candle(entry, entry + 0.2, entry - 0.2, entry) for _ in range(n)]


def _run_ladder_bar(entry, stop, direction, bar_):
    """Fires the REAL `backtest_week._ladder_bar` -- the function that
    manages every open trade in `research/bt2y_trades_retest_on.json` --
    against one hand-built bar. Returns the trade after it is processed."""
    t = _mktrade(entry, stop, direction)
    open_trades = [t]
    runner = bw.BacktestRunner("TEST")
    runner.candles = _flat_runner(entry)
    bw._ladder_bar(t, bar_, 11, open_trades, runner)
    return t, open_trades


def shipped_path_checks():
    """Every row here drives real `backtest_week`/`stop_rule` code, never a
    reimplementation of it. Returns (rows, failures)."""
    rows, failures = [], []

    def check(name, cond, detail=""):
        rows.append((name, cond))
        if not cond:
            failures.append("  %s%s" % (name, (": " + detail) if detail else "")
                            + "  [SECTION 1: THE SHIPPED PATH]")

    # ---- the algebra R1 depends on: disaster price IS the level stop -----
    # `disaster_stop_price(entry, risk, long, 1.0)` is `stop`, not "usually
    # close to it" -- exactly it, because 1R *is* abs(entry - stop). This is
    # the whole mechanism the rest of this section measures; if it stops
    # being true the two stops are no longer the same order.
    for direction, entry, stop in (("call", 100.0, 99.0), ("put", 50.0, 51.0),
                                   ("call", 7.31, 7.19)):
        long = direction == "call"
        risk = abs(entry - stop)
        px = stop_rule.disaster_stop_price(entry, risk, long, bw.DISASTER_R)
        check("disaster price == level stop when DISASTER_R=1.0 (%s %.2f/%.2f)"
             % (direction, entry, stop),
             bw.DISASTER_R != 1.0 or abs(px - stop) < EPS,
             "disaster=%.4f level=%.4f DISASTER_R=%.3f" % (px, stop, bw.DISASTER_R))

    # ---- the shipped config itself, not only its consequences ------------
    # A silent flag flip (someone edits a default in backtest_week.py, or
    # runs this file under a different env) must show up HERE first.
    check("DISASTER_STOP is ON by default (the ratified R1/R2 config)",
         bw.DISASTER_STOP is True, "got %r" % bw.DISASTER_STOP)
    check("DISASTER_R == 1.0 (the number that makes the floor unreachable)",
         bw.DISASTER_R == 1.0, "got %r" % bw.DISASTER_R)
    check("STOP_ON_CLOSE is ON by default (the level stop's own trigger)",
         bw.STOP_ON_CLOSE is True, "got %r" % bw.STOP_ON_CLOSE)
    check("shipped SCALE_PLAN is the ladder that built the real book",
         bw.SCALE_PLAN == "hod_then_runner_be", "got %r" % bw.SCALE_PLAN)

    # ---- the flagship R1 proof: gap straight through, book exactly -1R ---
    # A bar whose CLOSE lands roughly -9R away -- if the old (wrong) module's
    # -1.25R floor were live, this is exactly the shape that would reach it.
    # Fired through the real `_ladder_bar`, not a reimplementation.
    for direction, entry, stop, bar_ in (
        ("call", 100.0, 99.0, _candle(95.0, 95.5, 90.0, 91.0)),
        ("put", 100.0, 101.0, _candle(105.0, 110.0, 104.5, 109.0)),
    ):
        t, open_trades = _run_ladder_bar(entry, stop, direction, bar_)
        risk = abs(entry - stop)
        r = (t.exit_price - entry) / risk if direction == "call" \
            else (entry - t.exit_price) / risk
        check("gap-through books exactly -1.000R, never -1.25R (%s)" % direction,
             abs(r - (-1.0)) < EPS,
             "booked %.4fR at exit_price %.4f -- the -1.25R floor fired, which "
             "R1 says must never happen under the shipped DISASTER_R=1.0"
             % (r, t.exit_price))
        check("gap-through closes the trade, not left open (%s)" % direction,
             t not in open_trades)

    # ---- R2, corrected: a wick that reaches the level stops the trade even
    # though the CLOSE never does. The resting disaster order fills where it
    # rests, on touch -- CLAUDE.md's retired "wicks stop nothing out" is not
    # what the shipped book does once DISASTER_R=1.0 sits under it. -------
    for direction, entry, stop, bar_ in (
        ("call", 100.0, 99.0, _candle(100.2, 100.3, 98.5, 99.5)),   # wick to 98.5, closes 99.5 (above stop)
        ("put", 100.0, 101.0, _candle(99.8, 101.5, 99.7, 100.5)),   # wick to 101.5, closes 100.5 (below stop)
    ):
        long = direction == "call"
        close_would_not_trigger = not stop_rule.stop_hit_on_close(bar_.close, stop, long)
        t, open_trades = _run_ladder_bar(entry, stop, direction, bar_)
        check("the close-only trigger would NOT have fired (%s)" % direction,
             close_would_not_trigger)
        check("the resting disaster order stops it out on the wick anyway (%s)"
             % direction,
             abs(t.exit_price - stop) < EPS and t not in open_trades,
             "exit_price=%r still_open=%s" % (t.exit_price, t in open_trades))

    # ---- and a wick that never reaches the level stops nothing at all ----
    bar_short = _candle(100.2, 100.3, 99.2, 100.1)   # low 99.2, stop is 99.0 -- never touched
    t, open_trades = _run_ladder_bar(100.0, 99.0, "call", bar_short)
    check("a wick that never reaches the level stops nothing", t in open_trades)

    # ---- Austin, 2026-09-03: -1R HARD, INCLUDING AFTER THE BE MOVE -------
    # "1r is simpler so why not go with that? no stocks should be running to
    # -10R."
    #
    # THE HOLE THIS CLOSES. Once `runner_stop` is raised to break-even,
    # `_ladder_bar` stops testing the disaster order (`dz = _disaster_hit(...)
    # if stop_lv == t.stop else None`) -- correct on any continuous path,
    # because a resting BE order sits between price and -1R and fills first.
    # A GAP crosses both at once. The BE-raised stop then filled at the CLOSE
    # with only the -1.25R floor beneath it, so a bar that gapped ~9R booked
    # -1.25R, and with DISASTER_STOP off it booked the whole gap. That is the
    # "-10R" shape. `_stop_fill_px` now floors every close-triggered fill at
    # DISASTER_R.
    #
    # NOT tested here, because it is deliberately NOT the behaviour: re-arming
    # the disaster order on touch after the BE move. A bar that wicks through
    # BE and -1R and closes back above BE must NOT be stopped out -- firing the
    # disaster order there would manufacture a -1R loss on a trade whose stop
    # was at break-even. The ruling caps losses; it does not invent them.
    for direction, entry, stop, bar_ in (
        ("call", 100.0, 99.0, _candle(95.0, 95.5, 90.0, 91.0)),
        ("put", 100.0, 101.0, _candle(105.0, 110.0, 104.5, 109.0)),
    ):
        t = _mktrade(entry, stop, direction)
        t.runner_stop = t.entry            # the BE move, as _ladder_bar sets it
        open_trades = [t]
        runner = bw.BacktestRunner("TEST")
        runner.candles = _flat_runner(entry)
        bw._ladder_bar(t, bar_, 11, open_trades, runner)
        risk = abs(entry - stop)
        r = (t.exit_price - entry) / risk if direction == "call" \
            else (entry - t.exit_price) / risk
        check("BE-raised stop, bar gaps straight through: books no worse than "
              "-1.000R (%s)" % direction,
              r >= -1.0 - EPS,
              "booked %.4fR at exit_price %.4f -- a gap through a break-even "
              "stop fell past -1R, which Austin's 2026-09-03 ruling forbids"
              % (r, t.exit_price))
        check("BE-raised stop, gap-through closes the trade (%s)" % direction,
              t not in open_trades)

    # A BE-raised stop that fires on a NORMAL bar must still book its own
    # (near-scratch) result -- the floor is a cap, not a replacement.
    t = _mktrade(100.0, 99.0, "call")
    t.runner_stop = t.entry
    open_trades = [t]
    runner = bw.BacktestRunner("TEST")
    runner.candles = _flat_runner(100.0)
    bw._ladder_bar(t, _candle(100.1, 100.2, 99.8, 99.95), 11, open_trades, runner)
    check("a BE stop firing normally still books ~breakeven, not -1R",
          t not in open_trades and (t.exit_price - 100.0) / 1.0 > -0.5,
          "exit_price=%r" % t.exit_price)

    return rows, failures


def real_book_checks():
    """The loss distribution R1 cites, checked against the actual 2-year
    book on disk. Loud SKIP if the archive isn't present locally -- the same
    convention `research/test_retest_gate.py`'s `_real_book_cap` uses --
    never a silent pass."""
    rows, failures = [], []
    path = os.path.join(_REPO_ROOT, "research", "bt2y_trades_retest_on.json")
    if not os.path.exists(path):
        print("  SKIP  real-book check: %s not found locally "
              "(it is currently untracked in git -- commit it, or this "
              "check never runs on a fresh clone)" % path)
        return rows, failures

    with open(path) as f:
        book = json.load(f)
    traded = [t for t in book.get("trades", []) if t.get("traded")]
    if not traded:
        print("  SKIP  real-book check: 0 traded rows in %s" % path)
        return rows, failures
    rs = [t["r"] for t in traded]
    losses = [r for r in rs if r < 0]
    n_below = sum(1 for r in rs if r < -1.0 - EPS)
    n_between = sum(1 for r in rs if -1.25 + EPS < r < -1.0 - EPS)

    def check(name, cond, detail=""):
        rows.append((name, cond))
        if not cond:
            failures.append("  %s%s" % (name, (": " + detail) if detail else "")
                            + "  [SECTION 1: THE SHIPPED PATH]")

    check("real book (%d traded rows): min(r) == -1.000 exactly" % len(traded),
         abs(min(rs) - (-1.0)) < EPS, "min(r)=%.6f" % min(rs))
    check("real book: 0 rows worse than -1.000R", n_below == 0,
         "%d rows < -1.0" % n_below)
    check("real book: 0 rows between -1.25R and -1.000R -- the floor never binds",
         n_between == 0, "%d rows in (-1.25,-1.0)" % n_between)
    print("  (reachability: %d real losses on the book, none worse than "
          "-1.000R -- the disaster-stop branch this section tests is not a "
          "hypothetical, it is what actually happened 4,022 times)"
         % len(losses))
    return rows, failures


# ===========================================================================
# SECTION 2 -- EXIT_LAB: LAB COVERAGE, NOT THE SHIPPED PATH
# ===========================================================================
# `research/exit_lab.py` explores scale-out POLICIES (ATR trail, HOD-only,
# laddered break-even runners) that `backtest_week.py` does not ship, and it
# has no disaster stop at all -- zero occurrences of the word in the module.
# Its own -1.25R clamp is therefore genuinely reachable IN THIS MODEL'S OWN
# WORLD, which is not a contradiction of R1: R1 is about the book that
# actually trades. The 5.2 scale-out table reported a worst trade of
# -12.46R on `30_30_30_10`; if exit_lab's break-even-after-tranche-1 rule is
# actually enforced, the runner leg can never realise worse than 0R, so a
# laddered policy's floor is tranche 1's weight on a full stop-out.

LADDERED = {
    "30_30_30_10": policy_30_30_30_10,
    "50_20_20_10": policy_50_20_20_10,
}

FLOOR = -MAX_LOSS_R  # exit_lab's own floor -- real in ITS model, see above.


def _bar(o, h, l, c):
    """exit_lab's own bar shape: a plain dict, not a `Candle`. Every
    exit_lab function below indexes bars as `bars[i]["h"]`, never `.high` --
    do not swap this for section 1's `_candle`."""
    return {"o": o, "h": h, "l": l, "c": c, "v": 1000}


def wide_atr_collapse(side="L"):
    """New extreme, then one bar craters straight through entry.

    The base is deliberately wide-range so ATR is large (~30). After tranche 1
    exits on the new high, the ATR trail sits ``highest - 1.0*ATR``, which is
    far BELOW the entry price. The break-even stop is meant to sit at entry and
    fire first. If it is not enforced, the runner fills at the ATR trail
    instead -- tens of R below break-even. This is the -12.46R shape.
    """
    bars = []
    for _ in range(20):
        bars.append(_bar(100.0, 120.0, 80.0, 100.0))
    bars.append(_bar(100.0, 100.5, 99.5, 100.0))  # 20: entry bar
    for i in range(3):                            # 21..23: new highs
        t = 121.0 + i
        bars.append(_bar(t - 1, t, t - 2, t - 0.5))
    bars.append(_bar(120.0, 120.5, 40.0, 45.0))   # 24: the crater
    while len(bars) <= CLOCK_BAR:
        bars.append(_bar(45.0, 46.0, 44.0, 45.0))
    if side == "S":
        bars = [_bar(200 - b["o"], 200 - b["l"], 200 - b["h"], 200 - b["c"]) for b in bars]
    return bars


def wick_through_stop(side="L"):
    """Every bar spikes through the stop and closes back on the right side.

    This is the shape Austin described five times in one batch of marks: the
    wick takes out the level, the close does not. IN EXIT_LAB'S OWN MODEL
    (no disaster stop, close-only trigger) this books a winner. Section 1
    above measures the SAME shape against `backtest_week` and gets the
    opposite answer -- the resting disaster order stops it out anyway,
    because it rests exactly at the level. Both are correct, for the model
    each one is testing; that is the entire point of splitting this file
    into two sections.

    Built per side rather than by mirroring -- the mirror of a rising day is
    not a falling day with the same wick geometry, and getting that wrong
    silently turns the short case into a different test.
    """
    bars = [_bar(100.0, 100.4, 99.6, 100.0) for _ in range(21)]
    for k in range(10):
        if side == "L":
            top = 100.6 + k * 0.5
            # low 98.5 is well through the 99.00 stop; the close never is
            bars.append(_bar(100.2 + k * 0.5, top, 98.5, top - 0.1))
        else:
            bot = 99.4 - k * 0.5
            # high 101.5 is well through the 101.00 stop; the close never is
            bars.append(_bar(99.8 - k * 0.5, 101.5, bot, bot + 0.1))
    last = bars[-1]["c"]
    while len(bars) <= CLOCK_BAR:
        bars.append(_bar(last, last + 0.2, last - 0.2, last))
    return bars


def stop_then_rally(side="L"):
    """The close goes through the stop on the very next bar, then price rips.

    This is the shape `research/h1_2y_nowatch.py` found on PLTR 2026-06-01 and
    45 rows of the 2-year book: the ORIGINAL stop fires before tranche 1
    ever reaches its HOD rung, so the WHOLE position is flat -- there is no
    runner left to move to break-even. `scale_out` was moving one anyway and
    booking the rally that followed, which turned a full stop-out into a
    profit. Third instance of ticket 02's bug class (a stop that is computed
    and then not applied to the tranche it governs).
    """
    bars = [_bar(100.0, 100.4, 99.6, 100.0) for _ in range(21)]
    # 21: closes at 98.50, well below the 99.00 stop -> whole position out
    bars.append(_bar(99.8, 99.9, 98.4, 98.50))
    for k in range(10):                      # 22..31: the rally that must not count
        t = 100.0 + k
        bars.append(_bar(t - 0.5, t + 0.5, t - 0.8, t))
    last = bars[-1]["c"]
    while len(bars) <= CLOCK_BAR:
        bars.append(_bar(last, last + 0.2, last - 0.2, last))
    if side == "S":
        bars = [_bar(200 - b["o"], 200 - b["l"], 200 - b["h"], 200 - b["c"])
                for b in bars]
    return bars


def hod_bar_craters(side="L"):
    """The causal-HOD exit bar itself closes far beyond the stop.

    `causal_hod_exit_bar` returns the first bar after the new session extreme
    that fails to extend it. That bar is where tranche 1 exits -- and its own
    close can be anywhere. Here it closes 4R the wrong way.

    `hod_only` scanned for the stop over `range(entry_i + 1, end)` with
    `end = min(hod_i, n)`, EXCLUSIVE of hod_i, so the stop was not live on the
    one bar the policy actually exits on: the -4R close was booked in full and
    never floored. `scale_out` carried the identical off-by-one and it was
    fixed at `f5ff006a` ("tranche 1: fixed stop until the HOD exit bar,
    INCLUSIVE"); `hod_only` was left behind. Measured on the real book by
    `research/w13_scaling.py --selfcheck`: 5 of 1,017 traded rows, worst
    -1.4013R on MU 2026-06-16.

    Bar 21 prints the new extreme, so hod_bar = 21. Bar 22 fails to extend it,
    so the exit bar is 22 -- and bar 22 closes 4R the wrong way.

    Built per side rather than by mirroring -- the mirror of a rising day is
    not a falling day with the same HOD/LOD geometry, and getting that wrong
    silently turns the short case into a different test. Same reason
    `wick_through_stop` is built this way.
    """
    bars = [_bar(100.0, 100.4, 99.6, 100.0) for _ in range(21)]
    if side == "L":
        bars.append(_bar(100.0, 101.0, 99.8, 100.8))  # 21: new session high
        bars.append(_bar(100.6, 100.5, 95.5, 96.00))  # 22: exit bar, craters
        tail = 96.0
    else:
        bars.append(_bar(100.0, 100.2, 99.0, 99.20))  # 21: new session low
        bars.append(_bar(99.40, 104.5, 99.5, 104.00))  # 22: exit bar, craters
        tail = 104.0
    while len(bars) <= CLOCK_BAR:
        bars.append(_bar(tail, tail + 0.4, tail - 0.4, tail))
    return bars


# `hod_only` is not a laddered policy, so it gets its own list. The floor is
# the same one every other case in this section asserts: nothing books below
# -1.25R, in exit_lab's own (disaster-stop-free) model.
HOD_CASES = [
    ("hod_bar_craters long", hod_bar_craters, 20, 100.0, 99.00, "L"),
    ("hod_bar_craters short", hod_bar_craters, 20, 100.0, 101.00, "S"),
]

# Cases where the original stop fires first: the whole position is out, so the
# realised R must be a LOSS. Booking anything above 0 means a stopped-out trade
# kept running.
STOPPED_CASES = [
    ("stop_then_rally long", stop_then_rally, 20, 100.0, 99.00, "L"),
    ("stop_then_rally short", stop_then_rally, 20, 100.0, 101.00, "S"),
]

# Cases that must NOT stop out at all in exit_lab's own model -- the close
# never goes beyond the stop, and exit_lab has no touch-based stop underneath.
POSITIVE_CASES = [
    ("wick_through_stop long", wick_through_stop, 20, 100.0, 99.00, "L"),
    ("wick_through_stop short", wick_through_stop, 20, 100.0, 101.00, "S"),
]


CASES = [
    # name, bars_fn, entry_i, entry, stop, side
    ("wide_atr_collapse long, 1.00 stop", wide_atr_collapse, 20, 100.0, 99.00, "L"),
    ("wide_atr_collapse short, 1.00 stop", wide_atr_collapse, 20, 100.0, 101.00, "S"),
    ("wide_atr_collapse long, hairline stop", wide_atr_collapse, 20, 100.0, 99.90, "L"),
    ("wide_atr_collapse short, hairline stop", wide_atr_collapse, 20, 100.0, 100.10, "S"),
]


def exit_lab_checks():
    """(rows, failures) over every exit_lab case above -- section 2 only."""
    rows, failures = [], []

    for name, bars_fn, entry_i, entry, stop, side in CASES:
        bars = bars_fn(side)
        if side == "S":
            entry, stop = 200 - entry, 200 - stop
        for pid, fn in LADDERED.items():
            r = fn(bars, entry_i, entry, stop, side)
            rows.append((name, pid, r))
            if r < FLOOR - EPS:
                failures.append(
                    f"  {name} / {pid}: realised {r:+.4f}R, exit_lab's own floor "
                    f"is {FLOOR:+.2f}R (break-even stop on the runner was not "
                    f"enforced)  [SECTION 2: exit_lab, not the shipped path]"
                )

    for name, bars_fn, entry_i, entry, stop, side in STOPPED_CASES:
        bars = bars_fn(side)
        if side == "S":
            entry, stop = 200 - entry, 200 - stop
        for pid, fn in LADDERED.items():
            r = fn(bars, entry_i, entry, stop, side)
            rows.append((name, pid, r))
            if r > -1.0 + EPS:
                failures.append(
                    f"  {name} / {pid}: realised {r:+.4f}R on a trade whose close "
                    f"went through the ORIGINAL stop before any tranche exited -- "
                    f"100% of the position is out at that close, so this must be a "
                    f"full stop-out (<= -1.00R), not a partial one  "
                    f"[SECTION 2: exit_lab, not the shipped path]"
                )
            if r < FLOOR - EPS:
                failures.append(
                    f"  {name} / {pid}: realised {r:+.4f}R, exit_lab's own floor "
                    f"is {FLOOR:+.2f}R  [SECTION 2: exit_lab, not the shipped path]"
                )

    for name, bars_fn, entry_i, entry, stop, side in HOD_CASES:
        bars = bars_fn(side)          # already side-correct, do not mirror
        r = hod_only(bars, entry_i, entry, stop, side)
        rows.append((name, "hod_only", r))
        if r < FLOOR - EPS:
            failures.append(
                f"  {name} / hod_only: realised {r:+.4f}R, exit_lab's own floor "
                f"is {FLOOR:+.2f}R (the stop was not live on the HOD exit bar "
                f"itself)  [SECTION 2: exit_lab, not the shipped path]"
            )

    for name, bars_fn, entry_i, entry, stop, side in POSITIVE_CASES:
        bars = bars_fn(side)          # already side-correct, do not mirror
        for pid, fn in LADDERED.items():
            r = fn(bars, entry_i, entry, stop, side)
            rows.append((name, pid, r))
            if r <= 0:
                failures.append(
                    f"  {name} / {pid}: realised {r:+.4f}R on a day whose closes "
                    f"never went beyond the stop, in exit_lab's own (disaster-"
                    f"stop-free) model -- a wick stopped it out  "
                    f"[SECTION 2: exit_lab, not the shipped path]"
                )

    return rows, failures


# ===========================================================================
# SECTION 3 -- STOP PLACEMENT (signal_runner, the live path)
# ===========================================================================
# Unrelated to the trigger/fill bug sections 1-2 are about: WHERE the stop
# sits (structural / candle-entered / broken level / OCR wick / routed), not
# WHEN it fires. Real, shipped, untouched by this rewrite.
#
# Austin, 2026-08-28: "stops are wherever makes sense live... examples wick of
# OCR, candle entered on, break and retest of a level stop loss that level."
# Three placements, and the setup picks. `signal_runner.placed_stop` implements
# them behind STOP_PLACEMENT, and this asserts each one lands on the structure
# point it names -- and, first, that the DEFAULT returns the detector's own stop
# untouched, which is the byte-identity claim stated as an assert.
#
# RED BEFORE: at 246873b7 `signal_runner.placed_stop` does not exist, so every
# case below raises AttributeError. Reproduce with
#   git show 246873b7:signal_runner.py > <tmp>/signal_runner.py
# and importing that file: `hasattr(m, "placed_stop")` is False.
#
# One CHILD PROCESS per placement, because STOP_PLACEMENT is read once at import
# of signal_runner -- the same shape as research/g13_floor_fix_ab.py's arms.

_REPO = _REPO_ROOT

# The synthetic bar every placement case is asked about. Four distinguishable
# prices so no two placements can accidentally agree:
#   structural 99.95   what the detector picked for itself
#   bar low   100.05   the candle entered on
#   level     100.10   the level a break-and-retest broke
#   ocr wick   99.60   the far wick of the one-candle-rule candle
_PLACEMENT_DRIVER = r"""
import json, sys
sys.path.insert(0, %r)
import signal_runner as sr


class C:
    def __init__(s, o, h, l, c):
        s.open, s.high, s.low, s.close = o, h, l, c


bar = C(100.20, 100.90, 100.05, 100.80)
sbar = C(99.80, 99.95, 99.10, 99.20)
out = {
    "placement": sr.STOP_PLACEMENT,
    "fill_order": sr.STOP_FILL_ORDER,
    "br": sr.placed_stop(sr.SignalType.BREAK_AND_RETEST, 99.95, bar, True,
                         level_stop=100.10, ocr_stop=99.60),
    "ocr": sr.placed_stop(sr.SignalType.ONE_CANDLE_RULE, 99.95, bar, True,
                          level_stop=100.10, ocr_stop=99.60),
    "r84": sr.placed_stop(sr.SignalType.REENTRY_84_RULE, 99.95, bar, True,
                          level_stop=100.10, ocr_stop=99.60),
    "br_short": sr.placed_stop(sr.SignalType.BREAK_AND_RETEST, 100.05, sbar, False,
                               level_stop=99.90, ocr_stop=100.40),
    # a candidate on the WRONG side of the close is not a stop: the detector's
    # own structural stop must stand instead.
    "wrong_side": sr.placed_stop(sr.SignalType.BREAK_AND_RETEST, 99.95, bar, True,
                                 level_stop=100.95, ocr_stop=None),
    "fill": sr.order_fill(100.10, bar, True),
}
print(json.dumps(out))
"""


def _placement_probe(placement, fill_order="as_booked", entry_fill=None):
    env = dict(os.environ, STOP_PLACEMENT=placement, STOP_FILL_ORDER=fill_order)
    # ENTRY_FILL decides what `as_booked` actually books (entry_fill.py,
    # 2026-08-30). Passed explicitly wherever this file cares, popped otherwise,
    # for the same isolation reason every probe here runs in a child at all.
    env.pop("ENTRY_FILL", None)
    if entry_fill:
        env["ENTRY_FILL"] = entry_fill
    res = subprocess.run([sys.executable, "-c", _PLACEMENT_DRIVER % _REPO],
                         cwd=_REPO, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError("STOP_PLACEMENT=%s child failed:\n%s"
                             % (placement, res.stderr[-1500:]))
    return json.loads(res.stdout.strip().splitlines()[-1])


def _shipped_default_probe():
    """What `signal_runner` actually ships when NOTHING sets the two flags.

    Every other check in this file drives `STOP_PLACEMENT`/`STOP_FILL_ORDER`
    explicitly in a child process, so it cannot be fooled by whatever the
    CURRENT interpreter happens to have imported. This one used to be the
    exception: it did `import signal_runner as sr` in-process and trusted
    `sr.STOP_PLACEMENT`/`sr.STOP_FILL_ORDER` -- module-level constants latched
    once, at first import, from `os.environ`. A host process that already
    imported `signal_runner` earlier (or that exports either variable for an
    unrelated arm) makes that assertion pass or fail on THAT stale state, not
    on the shipped default -- the exact "stale assumption" bug class this file
    exists to catch elsewhere. Popping both from the child's env forces the
    isolated read `_placement_probe` already relies on for every other case.
    """
    env = dict(os.environ)
    env.pop("STOP_PLACEMENT", None)
    env.pop("STOP_FILL_ORDER", None)
    res = subprocess.run([sys.executable, "-c", _PLACEMENT_DRIVER % _REPO],
                         cwd=_REPO, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError("default-env child failed:\n%s" % res.stderr[-1500:])
    return json.loads(res.stdout.strip().splitlines()[-1])


# placement -> {field: expected stop}. `br_short` mirrors the call side on a
# short: bar high 99.95, level 99.90, ocr wick 100.40, structural 100.05.
PLACEMENT_CASES = {
    "entry_bar":      {"br": 99.95, "ocr": 99.95, "r84": 99.95,
                       "br_short": 100.05, "wrong_side": 99.95},
    "candle_entered": {"br": 100.05, "ocr": 100.05, "r84": 100.05,
                       "br_short": 99.95, "wrong_side": 100.05},
    # `wrong_side` hands ocr_stop=None, so ocr_wick falls back to the candle
    # entered on (100.05) rather than to the structural stop -- the fallback is
    # a real placement, not a failure, and it is asserted here on purpose.
    "ocr_wick":       {"br": 99.60, "ocr": 99.60, "r84": 99.60,
                       "br_short": 100.40, "wrong_side": 100.05},
    "broken_level":   {"br": 100.10, "ocr": 100.10, "r84": 100.10,
                       "br_short": 99.90, "wrong_side": 99.95},
    "routed":         {"br": 100.10, "ocr": 99.60, "r84": 99.95,
                       "br_short": 99.90, "wrong_side": 99.95},
}


def placement_failures():
    """One case per placement. Returns (rows, failures)."""
    rows, failures = [], []
    for placement, want in PLACEMENT_CASES.items():
        got = _placement_probe(placement)
        if got["placement"] != placement:
            failures.append("  STOP_PLACEMENT=%s: child reported %r  "
                            "[SECTION 3: stop placement]"
                            % (placement, got["placement"]))
            continue
        for field, expect in want.items():
            actual = got[field]
            rows.append(("STOP_PLACEMENT=%s %s" % (placement, field),
                         placement, actual))
            if abs(actual - expect) > EPS:
                failures.append(
                    "  STOP_PLACEMENT=%s %s: stop %.4f, expected %.4f -- the "
                    "placement did not land on the structure point it names  "
                    "[SECTION 3: stop placement]"
                    % (placement, field, actual, expect))
    # the DEFAULT must be `entry_bar` / `as_booked`, or the shipped book moved.
    # Read in an isolated child with both env vars unset -- see
    # `_shipped_default_probe` for why this cannot be an in-process import.
    default = _shipped_default_probe()
    if default["placement"] != "entry_bar":
        failures.append("  shipped default STOP_PLACEMENT is %r, must be "
                        "'entry_bar' -- any other default changes the shipped "
                        "book  [SECTION 3: stop placement]" % default["placement"])
    if default["fill_order"] != "as_booked":
        failures.append("  shipped default STOP_FILL_ORDER is %r, must be "
                        "'as_booked' -- order type is PARKED, not decided  "
                        "[SECTION 3: stop placement]" % default["fill_order"])
    # Order type is parked: both conventions must be expressible, and the
    # default one must be `fill_price` itself.
    #
    # 2026-08-30: `as_booked` means "whatever fill_price ships", and what
    # fill_price ships CHANGED -- it now delegates to `entry_fill`, whose
    # default is the signal minute's CLOSE (entry_fill.py, research/g85_entry_
    # fill.md). So on the shipped default the two conventions agree, by design
    # and not by breakage: both are the close. The distinctness this check
    # exists to prove is now checked where the two genuinely differ, under
    # ENTRY_FILL=published -- the old, unobtainable clamp.
    as_booked = _placement_probe("entry_bar", "as_booked", "published")["fill"]
    on_close = _placement_probe("entry_bar", "market_on_close", "published")["fill"]
    rows.append(("STOP_FILL_ORDER=as_booked fill (ENTRY_FILL=published)", "fill", as_booked))
    rows.append(("STOP_FILL_ORDER=market_on_close fill", "fill", on_close))
    if abs(on_close - 100.80) > EPS:
        failures.append("  STOP_FILL_ORDER=market_on_close filled at %.4f, the "
                        "bar's close is 100.80  [SECTION 3: stop placement]" % on_close)
    if abs(as_booked - on_close) < EPS:
        failures.append("  the two order-type conventions produced the same "
                        "fill on a bar that closes at its extreme -- one of "
                        "them is not wired  [SECTION 3: stop placement]")
    # ...and the flip itself is asserted, so nobody can quietly put the
    # unobtainable clamp back as the default without this going red.
    shipped_fill = _placement_probe("entry_bar", "as_booked")["fill"]
    rows.append(("shipped entry fill (ENTRY_FILL unset)", "fill", shipped_fill))
    if abs(shipped_fill - 100.80) > EPS:
        failures.append("  the SHIPPED entry fill is %.4f; it must be the signal "
                        "minute's close, 100.80. ENTRY_FILL flipped to `close` on "
                        "2026-08-30 because only 105 of 4,508 trades were "
                        "obtainable at the old clamp  [SECTION 3: stop placement]"
                        % shipped_fill)
    return rows, failures


def main():
    failures = []

    print("SECTION 1 -- THE SHIPPED PATH (backtest_week + stop_rule, R1)")
    print("-" * 72)
    s1_rows, s1_fail = shipped_path_checks()
    rb_rows, rb_fail = real_book_checks()
    failures += s1_fail + rb_fail
    for name, ok in s1_rows + rb_rows:
        print(("  ok  " if ok else "  FAIL") + "  " + name)
    print()

    print("SECTION 2 -- EXIT_LAB (lab coverage, NOT the shipped path)")
    print("-" * 72)
    s2_rows, s2_fail = exit_lab_checks()
    failures += s2_fail
    width = max(len(n) for n, _, _ in s2_rows)
    for name, pid, r in s2_rows:
        positive = any(name == pn for pn, _, _, _, _, _ in POSITIVE_CASES)
        bad = (r <= 0) if positive else (r < FLOOR - EPS)
        flag = "  FAIL" if bad else ""
        print(f"{name:<{width}}  {pid:<12} {r:+8.4f}R{flag}")
    print()

    print("SECTION 3 -- STOP PLACEMENT (signal_runner, the live path)")
    print("-" * 72)
    s3_rows, s3_fail = placement_failures()
    failures += s3_fail
    pw = max(len(n) for n, _, _ in s3_rows)
    for name, _pid, px in s3_rows:
        print("%-*s  %8.4f" % (pw, name, px))
    print()

    total_checks = len(s1_rows) + len(rb_rows) + len(s2_rows) + len(s3_rows)
    if failures:
        print(f"RUNNER-STOP SELFTEST FAILED: {len(failures)} of {total_checks} "
              f"checks are wrong.")
        print("\n".join(failures))
        sys.exit(1)

    print(f"runner-stop selftest ok: {total_checks} checks across 3 sections. "
          f"Section 1 (the shipped path): max loss is -1R hard, the level "
          f"stop is final, the -1.25R floor is fiction and did not fire "
          f"(R1). Section 2 (exit_lab, its own model): floored at "
          f"{FLOOR:+.2f}R, wick-only days never stopped out. Section 3: "
          f"stop placement lands on the structure point it names.")


if __name__ == "__main__":
    main()
