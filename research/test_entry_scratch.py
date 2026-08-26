"""P8/G2 — the failed-entry scratch: what the engine can and cannot express.

Austin, 2026-08-11:

    an entry taken intrabar that then closes back beyond the level is not a
    loss — scratch out at close, no 84 percent, this rule and previous applys
    to BR and OCR as well.

`backtest_week.simulate_day` used to implement that at the trade-creation site
by testing the ENTRY bar's own close against ``sig["stop"]``. That branch never
fired in a 2-year replay, and cannot: every detector requires the entry bar to
CLOSE through the retested level, and the stop sits at or beyond that level on
the losing side, so the entry bar's close is on the good side of both lines.

The first four cases pin that down. The rest pin down `ENTRY_SCRATCH`, the
flag-gated replacement, which asks the same question one bar later — the
earliest bar on which it CAN be true on a close-driven engine.

Synthetic bars, no archive needed. Run:

    python research/test_entry_scratch.py
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ["SCRATCH_PROBE"] = "1"        # read at import, below

from omen_bot import Candle              # noqa: E402
import backtest_week as bw               # noqa: E402

EPS = 1e-9
FAILS: list = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        FAILS.append(msg)


# ------------------------------------------------------------------ the day

def _bar(i, o, h, l, c, v=200_000):
    m = 30 + i
    return Candle(timestamp="%02d:%02d:00" % (9 + m // 60, m % 60),
                  open=o, high=h, low=l, close=c, volume=v)


def long_day(after: Candle):
    """A clean bullish B&R off the opening-range high, then `after`.

    Opening range (bars 0-4) tops at 100.50, so OR high = the level. Bar 10
    breaks it on a close, 11-12 LEAVE it, 13 retests and closes back UNDER it
    (so it cannot confirm), and bar 14 is the confirmation entry. Bar 15 is the
    caller's — the bar on which Austin's rule may or may not scratch.

    Bar 14 closes at its own high, so `fill_price` fills at the LEVEL and
    `intrabar_stop` drops the stop to the bar's low: this is the engine's ONLY
    model of "taken intrabar", and it is also the shape where the level and the
    stop are two different prices.
    """
    b = [_bar(i, 100.00, 100.50, 99.80, 100.10) for i in range(5)]
    b += [_bar(i, 100.10, 100.30, 99.90, 100.05) for i in range(5, 10)]
    b.append(_bar(10, 100.05, 101.10, 100.00, 101.00))   # BREAK on the close
    b.append(_bar(11, 101.00, 101.60, 100.80, 101.40))   # LEAVE
    b.append(_bar(12, 101.40, 101.50, 100.70, 100.80))
    b.append(_bar(13, 100.80, 100.90, 100.40, 100.45))   # RETEST, closes under
    b.append(_bar(14, 100.45, 101.10, 100.00, 101.00))   # CONFIRM -> entry
    b.append(after)
    b += [_bar(i, 100.20, 100.30, 100.10, 100.20) for i in range(16, 90)]
    return b


def short_day(after: Candle):
    """The long day mirrored about $200 — a real short, not a sign flip on R."""
    src = long_day(after)
    return [Candle(timestamp=c.timestamp, open=200 - c.open, high=200 - c.low,
                   low=200 - c.high, close=200 - c.close, volume=c.volume)
            for c in src]


# bar 15 in the three bands that matter, long side
BAND = {
    # closes back through the LEVEL but stays above the STOP: today the trade
    # is still open, so this is the band where the rule moves money
    "between":   _bar(15, 101.00, 101.05, 100.30, 100.45),
    # closes back through both: today a -1.00R stop-out that arms the 84% rule
    "thru_stop": _bar(15, 101.00, 101.05, 99.50, 99.60),
    # holds above the level: no scratch under any reading
    "holds":     _bar(15, 101.00, 101.40, 100.80, 101.30),
}


def run(day, mode=""):
    """One replay at one ENTRY_SCRATCH setting. Returns (trades, probe rows)."""
    prev, bw.ENTRY_SCRATCH = bw.ENTRY_SCRATCH, mode
    bw.SCRATCH_PROBE.clear()
    try:
        tr = bw.simulate_day("TEST", "2026-01-05", day, pdh=None, pdl=None,
                             bias="bullish" if day[0].close < 150 else "bearish")
    finally:
        bw.ENTRY_SCRATCH = prev
    return tr, list(bw.SCRATCH_PROBE)


def only(trades):
    assert len(trades) == 1, "expected exactly one signal, got %d" % len(trades)
    return trades[0]


# ------------------------------------------------- 1. the branch is unreachable

print("\nthe dead branch: can the ENTRY bar close back through the level?")
for label, day in (("long", long_day(BAND["thru_stop"])),
                   ("short", short_day(BAND["thru_stop"]))):
    trades, rows = run(day)
    check(len(rows) >= 1, "%s: the day produces a signal to measure" % label)
    for r in rows:
        check(r["d0_level"] > 0,
              "%s: entry bar closes THROUGH the level (d0_level=%+.4f > 0)"
              % (label, r["d0_level"]))
        check(r["d0_stop"] > 0,
              "%s: entry bar closes through the stop too — the dead branch's own "
              "test (d0_stop=%+.4f > 0)" % (label, r["d0_stop"]))

# The same statement as code rather than as one example: the T4(b) condition is
# `close < stop` (long), and every emitting detector requires `close > level`
# with `stop <= level`. Two years of replay agree — research/p8_scratch.md
# records min(d0_stop) over every trade the engine ever created.
t = only(run(long_day(BAND["thru_stop"]))[0])
check(t.entry > 0 and t.stop <= t.level_price + EPS,
      "the stop sits at or below the retested level on a long (%.2f <= %.2f)"
      % (t.stop, t.level_price))

# ------------------------------------------------------- 2. shipped default OFF

print("\nshipped default")
check(os.getenv("ENTRY_SCRATCH") is not None or bw.ENTRY_SCRATCH == "",
      "ENTRY_SCRATCH is OFF unless the env var asks for it")
t = only(run(long_day(BAND["thru_stop"]), mode="")[0])
check(t.outcome == "loss" and abs(t.pnl / 1000 + 1.0) < EPS,
      "OFF: the close-back bar is a -1.00R stop-out, unchanged (%s %.3fR)"
      % (t.outcome, t.pnl / 1000))

# --------------------------------------------- 3. ON, the band that moves money

print("\nENTRY_SCRATCH=level — closes back through the level, holds the stop")
for label, day in (("long", long_day(BAND["between"])),
                   ("short", short_day(BAND["between"]))):
    off = only(run(day, mode="")[0])
    on = only(run(day, mode="level")[0])
    check(off.outcome != "loss" and off.exit_idx - off.entry_idx > 1,
          "%s: OFF the trade survives the bar and runs on (%s, %d bars)"
          % (label, off.outcome, off.exit_idx - off.entry_idx))
    check(on.outcome == "scratch" and on.exit_idx == on.entry_idx + 1,
          "%s: ON it scratches on the very next bar (%s, %d bars)"
          % (label, on.outcome, on.exit_idx - on.entry_idx))
    check(abs(on.exit_price - day[15].close) < EPS,
          "%s: 'scratch out at close' — exit is that bar's close (%.2f)"
          % (label, on.exit_price))
    check(on.pnl > off.pnl,
          "%s: the scratch is worth more than letting it run (%+.3fR vs %+.3fR)"
          % (label, on.pnl / 1000, off.pnl / 1000))

# ------------------------------------- 4. ON, the band that only changes a label

print("\nENTRY_SCRATCH=level — closes back through the stop as well")
arms = []
real_arm = bw._arm_84
bw._arm_84 = lambda *a, **k: arms.append(a[0])
try:
    off = only(run(long_day(BAND["thru_stop"]), mode="")[0])
    n_off = len(arms)
    arms.clear()
    on = only(run(long_day(BAND["thru_stop"]), mode="level")[0])
    n_on = len(arms)
finally:
    bw._arm_84 = real_arm
check(on.outcome == "scratch" and off.outcome == "loss",
      "loss -> scratch (%s -> %s)" % (off.outcome, on.outcome))
check(abs(on.exit_price - on.stop) < EPS and abs(on.pnl - off.pnl) < EPS,
      "never worse than the stop-out it replaced — his stop order still fills "
      "at the level (%+.3fR both ways)" % (on.pnl / 1000))
check(n_off == 1 and n_on == 0,
      "'no 84 percent': the stop-out arms it, the scratch does not (%d -> %d)"
      % (n_off, n_on))

# ------------------------------------------------- 5. ON, the bar that holds up

print("\nENTRY_SCRATCH=level — the next bar holds above the level")
off = only(run(long_day(BAND["holds"]), mode="")[0])
on = only(run(long_day(BAND["holds"]), mode="level")[0])
check(on.outcome == off.outcome and abs(on.pnl - off.pnl) < EPS,
      "a bar that holds the level changes nothing (%s %+.3fR)"
      % (on.outcome, on.pnl / 1000))

# ------------------------------------- 6. the stop reading, measured not shipped

print("\nENTRY_SCRATCH=stop — the dead branch's own line, one bar later")
off = only(run(long_day(BAND["between"]), mode="")[0])
on = only(run(long_day(BAND["between"]), mode="stop")[0])
check(on.exit_idx == off.exit_idx and abs(on.pnl - off.pnl) < EPS,
      "the 'between' bar never reaches the stop, so this reading ignores it "
      "(%s %+.3fR, same as OFF)" % (on.outcome, on.pnl / 1000))
on = only(run(long_day(BAND["thru_stop"]), mode="stop")[0])
check(on.outcome == "scratch",
      "and it re-labels the ordinary close-based stop-out as a scratch — which "
      "is why it is measured and not shipped (%s)" % on.outcome)

print("\n%d checks failed" % len(FAILS))
sys.exit(1 if FAILS else 0)
