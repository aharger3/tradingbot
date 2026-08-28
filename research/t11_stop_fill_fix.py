"""t11_stop_fill_fix.py — the stop FILL convention, pinned in every rig that books one.

Austin, 2026-08-28: *"fix stop out 1.25 max slippage this needs to be fixed now."*
Rule ballot batch 01 q1, his words: *"a 1m candle close below is exit, max
slippage -1.25r which is 1.25k based on current position sizing."*

THE RULE, and it is settled:

    A stop TRIGGERS on a candle CLOSE. It FILLS AT THAT CLOSE. The realised loss
    is FLOORED at -1.25R. Wicks stop nothing.

`research/x2_stop_floor_audit.md` measured what the repo was doing instead:
`backtest_week.py` triggered on the close (`:284`) and then filled at `t.stop`
(`:416`, `:611`), so **458 of the book's 474 stop-outs (96.6%) were triggered by
a candle that had already CLOSED past 1R** — median -1.3500R, mean -1.4915R,
worst -4.3571R — and every one was recorded as exactly -1.000R. 0 of 45,193 rows
were worse than -1.0R. The -1.25R floor was unreachable code: the 6th instance
of this repo's unreachable-rule class.

This file is the guard. It asserts, in every rig that books a stop:

  1. a stop triggered by a candle closing **1.6R** past entry books **-1.25R** —
     not -1.000R (the old fill) and not -1.6R (no floor at all);
  2. a stop triggered by a candle closing **1.1R** past books **-1.1R exactly** —
     the floor does not bind, so it is a clamp and not a constant;
  3. a **WICK** through the stop with the close inside books **NOTHING** — the
     trade is still open;
  4. the floor applies to the runner and to **every tranche after a scale-out**,
     measured against the **ORIGINAL** ``abs(entry - stop)``, never a risk
     re-based on the moved stop.

Synthetic bars throughout, no archive and no network. Run:

    python research/t11_stop_fill_fix.py

Red before `stop_rule.stop_fill_price` was routed into the callers, green after.
Companion finding: `research/t11_stop_fill_fix.md`.
"""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import stop_rule                                    # noqa: E402
from omen_bot import Candle                         # noqa: E402
import backtest_week as bw                          # noqa: E402
from research import exit_lab as xl                 # noqa: E402
import paper_trader as pt                           # noqa: E402
from options_sizer import OptionsPlan               # noqa: E402

EPS = 1e-6
FLOOR_R = 1.25
FAILS: list = []
ROWS: list = []


def check(cond, msg):
    ROWS.append(("PASS" if cond else "FAIL", msg))
    if not cond:
        FAILS.append(msg)


def close_to(got, want, msg):
    check(abs(got - want) < EPS, "%s  (got %+.4fR, want %+.4fR)" % (msg, got, want))


# ---------------------------------------------------------------------------
# 0. one definition of the fill, in one place
# ---------------------------------------------------------------------------

print("\n0. the shared helper")

check(hasattr(stop_rule, "stop_fill_price"),
      "stop_rule.stop_fill_price exists — one fill definition, not one per rig")

if hasattr(stop_rule, "stop_fill_price"):
    f = stop_rule.stop_fill_price
    # long: entry 100, risk 1.0 -> floor at 98.75
    close_to((f(98.40, 100.0, 1.0, True) - 100.0) / 1.0, -FLOOR_R,
             "helper long: a close 1.6R past floors at -1.25R")
    close_to((f(98.90, 100.0, 1.0, True) - 100.0) / 1.0, -1.1,
             "helper long: a close 1.1R past is booked in full, unfloored")
    close_to((100.0 - f(101.60, 100.0, 1.0, False)) / 1.0, -FLOOR_R,
             "helper short: a close 1.6R past floors at -1.25R")
    close_to((100.0 - f(101.10, 100.0, 1.0, False)) / 1.0, -1.1,
             "helper short: a close 1.1R past is booked in full, unfloored")
    check(abs(f(50.0, 100.0, 0.0, True) - 50.0) < EPS,
          "helper: a zero-width stop has no floor to compute, close passes through")
    check(abs(f(99.5, 100.0, 1.0, True) - 99.5) < EPS,
          "helper: the clamp is one-sided — it never improves a fill inside the floor")
    check(getattr(stop_rule, "MAX_LOSS_R", None) == 1.25,
          "stop_rule.MAX_LOSS_R is 1.25 — Austin's stated worst case")
    check(getattr(xl, "MAX_LOSS_R", None) == getattr(stop_rule, "MAX_LOSS_R", None),
          "exit_lab.MAX_LOSS_R has not forked from stop_rule.MAX_LOSS_R")


# ---------------------------------------------------------------------------
# the shared fixture: a clean bullish B&R the engine really fires on
#
# Lifted from research/test_entry_scratch.py::long_day so the entry geometry is
# the one the detector actually produces, not one invented here. Bar 14 closes
# at its own high, so fill_price fills at the LEVEL (100.50) and intrabar_stop
# drops the stop onto the bar's low (100.00): entry 100.50, stop 100.00,
# risk = 0.50 exactly, target 101.50. Every R below is that 0.50.
# ---------------------------------------------------------------------------

ENTRY = 100.50
STOP = 100.00
RISK = 0.50


def _bar(i, o, h, l, c, v=200_000):
    m = 30 + i
    return Candle(timestamp="%02d:%02d:00" % (9 + m // 60, m % 60),
                  open=o, high=h, low=l, close=c, volume=v)


def long_day(*after: Candle):
    b = [_bar(i, 100.00, 100.50, 99.80, 100.10) for i in range(5)]
    b += [_bar(i, 100.10, 100.30, 99.90, 100.05) for i in range(5, 10)]
    b.append(_bar(10, 100.05, 101.10, 100.00, 101.00))   # BREAK on the close
    b.append(_bar(11, 101.00, 101.60, 100.80, 101.40))   # LEAVE (sets HOD 101.60)
    b.append(_bar(12, 101.40, 101.50, 100.70, 100.80))
    b.append(_bar(13, 100.80, 100.90, 100.40, 100.45))   # RETEST, closes under
    b.append(_bar(14, 100.45, 101.10, 100.00, 101.00))   # CONFIRM -> entry
    b.extend(after)
    tail_from = 15 + len(after)
    tailpx = after[-1].close if after else 100.20
    b += [_bar(i, tailpx, tailpx + 0.10, tailpx - 0.10, tailpx)
          for i in range(tail_from, 90)]
    return b


def short_day(*after: Candle):
    """Mirrored about $200 — a real short, not a sign flip on R."""
    src = long_day(*after)
    return [Candle(timestamp=c.timestamp, open=200 - c.open, high=200 - c.low,
                   low=200 - c.high, close=200 - c.close, volume=c.volume)
            for c in src]


def _px(r_past):
    """The close that sits ``r_past`` R below ENTRY, i.e. on a long's losing side.

    Only the long orientation is ever built. ``short_day`` mirrors the whole
    session about $200, bars and all, so a short fixture is the long one
    reflected -- never a sign flip applied twice.
    """
    return round(ENTRY - r_past * RISK, 4)


def run(day, scale_plan=None):
    """One replay. ``scale_plan=None`` keeps the shipped default."""
    prev = bw.SCALE_PLAN
    if scale_plan is not None:
        bw.SCALE_PLAN = scale_plan
    try:
        return bw.simulate_day("TEST", "2026-01-05", day, pdh=None, pdl=None,
                               bias="bullish" if day[0].close < 150 else "bearish")
    finally:
        bw.SCALE_PLAN = prev


def only(trades):
    assert len(trades) == 1, "expected exactly one signal, got %d" % len(trades)
    return trades[0]


# a bar whose CLOSE is `r_past` R beyond the stop, and whose low goes further
def crater(i, r_past):
    c = _px(r_past)
    return _bar(i, 101.00, 101.05, c - 0.30, c)


# a bar that WICKS through the stop and closes back on the good side
def wick_only(i):
    return _bar(i, 100.80, 100.90, 99.20, 100.70)       # low 99.20 << stop 100.00


# the bar that tags the entry-bar session high (101.60) and so fires the 50%
# scale rung, leaving a runner with its stop raised to break-even
SCALE_BAR = _bar(15, 101.00, 101.70, 100.80, 101.20)


# ---------------------------------------------------------------------------
# 1. backtest_week — the shipped rig, ladder path (SCALE_PLAN default)
# ---------------------------------------------------------------------------

print("\n1. backtest_week, ladder path (`_ladder_bar`, backtest_week.py:415)")

for label, mk_day in (("long", long_day), ("short", short_day)):
    t = only(run(mk_day(crater(15, 1.6))))
    close_to(t.pnl / bw.RISK_DOLLARS, -FLOOR_R,
             "%s: close 1.6R past the stop -> the FLOOR, not the stop price" % label)
    check(t.outcome == "loss", "%s: and it is a loss (%s)" % (label, t.outcome))

    t = only(run(mk_day(crater(15, 1.1))))
    close_to(t.pnl / bw.RISK_DOLLARS, -1.1,
             "%s: close 1.1R past books -1.1R exactly — the floor does not bind"
             % label)

    t = only(run(mk_day(wick_only(15))))
    check(t.outcome != "loss" and t.exit_idx != 15,
          "%s: a wick through the stop with the close inside books NOTHING "
          "(outcome=%s, exit_idx=%d)" % (label, t.outcome, t.exit_idx))


# ---------------------------------------------------------------------------
# 2. backtest_week — non-ladder path (backtest_week.py:611)
# ---------------------------------------------------------------------------

print("\n2. backtest_week, non-ladder path (SCALE_PLAN='')")

for label, mk_day in (("long", long_day), ("short", short_day)):
    t = only(run(mk_day(crater(15, 1.6)), scale_plan=""))
    close_to(t.pnl / bw.RISK_DOLLARS, -FLOOR_R,
             "%s: close 1.6R past -> -1.25R on the binary path too" % label)
    t = only(run(mk_day(crater(15, 1.1)), scale_plan=""))
    close_to(t.pnl / bw.RISK_DOLLARS, -1.1,
             "%s: close 1.1R past -> -1.1R on the binary path too" % label)
    t = only(run(mk_day(wick_only(15)), scale_plan=""))
    check(t.outcome != "loss" and t.exit_idx != 15,
          "%s: wick-only stops nothing on the binary path (outcome=%s)"
          % (label, t.outcome))


# ---------------------------------------------------------------------------
# 3. the runner, after a scale-out — floored against the ORIGINAL risk
# ---------------------------------------------------------------------------

print("\n3. the runner after a scale-out (SCALE_PLAN='hod_then_runner_be')")

# scale_level = the session high as of the entry bar = 101.60 (bar 11).
# Bar 15 tags it (high 101.70) so 50% comes off there and runner_stop -> entry.
# Bar 16 then closes 1.6R below the ORIGINAL entry.
#   scale leg  : (101.60 - 100.50) / 0.50 = +2.20R on 50%
#   runner leg : floored at -1.25R on 50%
#   book       : 0.5*(+2.20) + 0.5*(-1.25) = +0.475R
SCALE_R = (101.60 - ENTRY) / RISK

for label, mk_day in (("long", long_day), ("short", short_day)):
    t = only(run(mk_day(SCALE_BAR, crater(16, 1.6))))
    check(t.scaled, "%s: the 50%% scale rung actually fired (scaled=%s)"
          % (label, t.scaled))
    want = 0.5 * SCALE_R + 0.5 * (-FLOOR_R)
    close_to(t.pnl / bw.RISK_DOLLARS, want,
             "%s: scale leg +%.2fR, runner floored at -1.25R against the "
             "ORIGINAL |entry-stop|" % (label, SCALE_R))
    # the denominator must NOT be re-based on the moved (break-even) stop
    rebased = 0.5 * SCALE_R + 0.5 * (-FLOOR_R) * 0.0
    check(abs(t.pnl / bw.RISK_DOLLARS - rebased) > EPS,
          "%s: the runner is not booked at 0R just because its stop sat at "
          "break-even" % label)


# ---------------------------------------------------------------------------
# 4. research/exit_lab — the policy family (already correct; pinned here so a
#    later edit cannot fork it back)
# ---------------------------------------------------------------------------

print("\n4. research/exit_lab policies")

XL_POLICIES = {
    "flat_2r": xl.flat_2r,
    "hod_only": xl.hod_only,
    "30_30_30_10": xl.policy_30_30_30_10,
    "50_20_20_10": xl.policy_50_20_20_10,
}


def _xlbar(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c, "v": 1000}


def xl_day(kind, side):
    """21 flat bars, entry at 20 (entry 100.0, stop 99.0/101.0, risk 1.0)."""
    bars = [_xlbar(100.0, 100.2, 99.8, 100.0) for _ in range(21)]
    if kind == "wick":
        for _ in range(12):
            bars.append(_xlbar(100.0, 100.6, 98.2, 100.4) if side == "L"
                        else _xlbar(100.0, 101.8, 99.4, 99.6))
    else:
        r = 1.6 if kind == "far" else 1.1
        c = 100.0 - r if side == "L" else 100.0 + r
        bars.append(_xlbar(99.9, 100.0, c - 0.4, c) if side == "L"
                    else _xlbar(100.1, c + 0.4, 100.0, c))
        for _ in range(12):
            bars.append(_xlbar(c, c + 0.2, c - 0.2, c))
    while len(bars) <= xl.CLOCK_BAR:
        last = bars[-1]["c"]
        bars.append(_xlbar(last, last + 0.2, last - 0.2, last))
    return bars


for side, entry, stop in (("L", 100.0, 99.0), ("S", 100.0, 101.0)):
    for name, fn in XL_POLICIES.items():
        r = fn(xl_day("far", side), 20, entry, stop, side)
        close_to(r, -FLOOR_R, "exit_lab %s/%s: close 1.6R past floors at -1.25R"
                 % (side, name))
        r = fn(xl_day("near", side), 20, entry, stop, side)
        close_to(r, -1.1, "exit_lab %s/%s: close 1.1R past books -1.1R exactly"
                 % (side, name))
        r = fn(xl_day("wick", side), 20, entry, stop, side)
        check(r > -1.0 + EPS,
              "exit_lab %s/%s: wicks through the stop book nothing (%+.4fR)"
              % (side, name, r))


# ---------------------------------------------------------------------------
# 5. paper_trader — the LIVE path
# ---------------------------------------------------------------------------

print("\n5. paper_trader (the live path)")

# The same two plans research/test_paper_trader_stop.py and
# research/test_x2_stop_floor.py use, so the three files cannot drift apart on
# what a TSLA call costs. Risk is 0.70 of stock / $0.35 of premium on the call,
# 2.50 of stock / $0.50 of premium on the put -- so the plan's own delta map is
# exactly premium_risk per stock_risk, and 1.6R of stock is 1.6R of premium.
CALL_PLAN = OptionsPlan(
    symbol="TSLA", direction="call", expiration="2026-06-10", strike=440.0,
    entry_premium=2.00, stop_premium=1.65, target_premium=2.70, contracts=5,
    max_loss=175.0, max_reward=350.0,
    stock_entry=440.0, stock_stop=439.3, stock_target=441.4,
    quote_source="estimated_delta", occ_symbol="TSLA260610C00440000",
)
PUT_PLAN = OptionsPlan(
    symbol="NVDA", direction="put", expiration="2026-06-10", strike=850.0,
    entry_premium=3.00, stop_premium=2.50, target_premium=4.00, contracts=4,
    max_loss=200.0, max_reward=400.0,
    stock_entry=850.0, stock_stop=852.5, stock_target=845.0,
    quote_source="estimated_delta", occ_symbol="NVDA260610P00850000",
)


def _paper_pos(plan):
    return pt.PaperPosition(
        symbol=plan.symbol, direction=plan.direction, strike=plan.strike,
        expiration=plan.expiration, contracts=plan.contracts,
        entry_premium=plan.entry_premium, stop_premium=plan.stop_premium,
        target_premium=plan.target_premium, stock_entry=plan.stock_entry,
        stock_stop=plan.stock_stop, stock_target=plan.stock_target,
        occ_symbol=plan.occ_symbol, opened_at="2026-01-05 09:40:00",
    )


for label, plan in (("call", CALL_PLAN), ("put", PUT_PLAN)):
    risk_prem = plan.entry_premium - plan.stop_premium
    long = plan.direction == "call"
    srisk = abs(plan.stock_entry - plan.stock_stop)

    for r_past, want in ((1.6, -FLOOR_R), (1.1, -1.1)):
        close = (plan.stock_entry - r_past * srisk if long
                 else plan.stock_entry + r_past * srisk)
        got = pt.PaperPosition._check_stop(_paper_pos(plan), close)
        if got is None:
            check(False, "paper_trader %s: no stop at a close %.1fR past the stop"
                  % (label, r_past))
            continue
        prem, _ = got
        r = (prem - plan.entry_premium) / risk_prem
        close_to(r, want, "paper_trader %s: stock close %.1fR past books %+.2fR "
                 "on the premium" % (label, r_past, want))

    # a wick through the stop is not handed to _check_stop at all; the close is.
    inside = plan.stock_entry - 0.5 * srisk if long else plan.stock_entry + 0.5 * srisk
    check(pt.PaperPosition._check_stop(_paper_pos(plan), inside) is None,
          "paper_trader %s: a close INSIDE the stop books nothing" % label)


# ---------------------------------------------------------------------------
# 6. no rig may keep a private fill convention
# ---------------------------------------------------------------------------

print("\n6. single-source: nobody re-implements the fill")

import re                                            # noqa: E402

# `_stop_fill_px` is backtest_week's Candle-shaped wrapper over the same
# helper, so a rig that imports IT is routed too -- g10 replays the book's own
# position management and must not grow a private copy.
SITES = ("backtest_week.py", "paper_trader.py", "research/exit_lab.py",
         "research/g10_arming_funnel.py")
for rel in SITES:
    src = open(os.path.join(_REPO_ROOT, rel), encoding="utf-8").read()
    check("stop_fill_price" in src or "_stop_fill_px" in src,
          "%s routes its stop fill through stop_rule.stop_fill_price" % rel)

bw_src = open(os.path.join(_REPO_ROOT, "backtest_week.py"), encoding="utf-8").read()
check(not re.search(r'exit_price(?:, t\.exit_idx)? = "?loss"?, t\.stop', bw_src)
      and '= "loss", t.stop' not in bw_src,
      "backtest_week.py no longer books a stop-out AT t.stop")


# ---------------------------------------------------------------------------

def main():
    width = max(len(m) for _, m in ROWS)
    for flag, msg in ROWS:
        print("  %-4s  %-*s" % (flag, width, msg))
    print()
    if FAILS:
        print("T11 STOP-FILL SELFTEST FAILED: %d of %d checks are wrong."
              % (len(FAILS), len(ROWS)))
        for m in FAILS:
            print("  - " + m)
        sys.exit(1)
    print("t11 stop-fill selftest ok: %d checks. Stops trigger on the close, "
          "fill at that close, floored at -%.2fR; wicks stop nothing."
          % (len(ROWS), FLOOR_R))


if __name__ == "__main__":
    main()
