"""Profit legs fill on TOUCH, never on a candle close. Austin, 2026-08-30.

    "A profit target is a resting limit order and it fills the moment price
     touches it."

Ratified, so this is a guard, not an A/B arm. A stop is the opposite kind of
order and is NOT tested here: the stop trigger is a separate question Austin has
explicitly not re-ratified, and every stop fill in this repo routes through
`stop_rule.stop_fill_price`. Nothing below touches a stop rule.

Four profit legs exist, and each one is checked on the shape that separates the
two rules -- a bar whose HIGH (long) or LOW (short) reaches the level and whose
CLOSE does not:

  1. the blind 2R target            backtest_week.simulate_day  (inline)
  2. the ladder's first scale rung  backtest_week._ladder_bar
  3. the runner target              backtest_week._ladder_bar
  4. the break-even move            backtest_week._ladder_bar (SCALE_PLAN
                                    "hod_then_runner_be") -- the stop only
                                    MOVES here; where it fires is untouched

and their live counterparts in `paper_trader.PaperPosition`, plus
`research/exit_lab.flat_target`, the third rig that books a target.

Leg 1 lives inline inside `simulate_day`'s bar loop, so it has no seam a test
can drive without replaying a real session. It is covered by a source guard
instead -- the forbidden shape (`c.close` compared against a profit level) must
not appear, and the trigger that is there must read the bar's extremes. Legs
2-4 and the whole live path are driven behaviourally on synthetic bars.

Synthetic bars only, no archive, no network. Run:

    python research/test_scaleout_touch.py
"""

from __future__ import annotations

import inspect
import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import backtest_week as bw                      # noqa: E402
import paper_trader as pt                       # noqa: E402
from omen_bot import Candle                     # noqa: E402
from research.exit_lab import flat_target       # noqa: E402

EPS = 1e-9
FAILURES: list[str] = []
CHECKS: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok)))
    if not ok:
        FAILURES.append(f"  {name}: {detail}" if detail else f"  {name}")


def _c(o, h, l, cl, ts="2026-08-30 09:45:00"):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=1000)


# ---------------------------------------------------------------------------
# Geometry. One long shape and its mirror, built so that every profit level is
# TOUCHED by the wick and NOT reached by the close, while the close stays on the
# safe side of both the level stop and the resting -1R disaster order. Nothing
# here can be resolved by a stop rule, so a failure means a profit leg waited.
# ---------------------------------------------------------------------------

LONG = dict(entry=100.00, stop=99.00, target=102.00,
            scale_level=100.80, runner_target=101.50)
SHORT = dict(entry=100.00, stop=101.00, target=98.00,
             scale_level=99.20, runner_target=98.50)

# unscaled bar: tags the scale rung, closes back under it, low nowhere near -1R
BAR_SCALE_LONG = _c(100.05, 100.85, 99.70, 100.10)
BAR_SCALE_SHORT = _c(99.95, 100.30, 99.15, 99.90)
# runner bar: tags the runner target, closes back under it
BAR_RUN_LONG = _c(100.90, 101.55, 100.40, 100.60)
BAR_RUN_SHORT = _c(99.10, 99.60, 98.45, 99.40)
# blind-2R bar: tags the 2R target, closes back under it
BAR_TGT_LONG = _c(100.90, 102.05, 100.40, 100.95)
BAR_TGT_SHORT = _c(99.10, 99.60, 97.95, 99.05)


def _trade(side: str) -> "bw.SimTrade":
    g = LONG if side == "L" else SHORT
    return bw.SimTrade(
        symbol="TEST", day="2026-08-30", signal_type="break_retest",
        direction="call" if side == "L" else "put", grade="B", status="fired",
        entry_time="09:45", entry=g["entry"], stop=g["stop"], target=g["target"],
        scale_level=g["scale_level"], runner_target=g["runner_target"],
        entry_idx=10,
    )


class _RunnerStub:
    """`_ladder_bar` only reads the runner on a STOP path (`_arm_84`). Every
    case here is a pure profit-leg touch, so reaching this is itself the bug."""
    candles: list = []
    htf_bias = None

    def __getattr__(self, name):
        raise AssertionError(
            f"_ladder_bar reached the stop/arming path (asked for {name!r}) on a "
            f"bar that only touched a profit level")


# ---------------------------------------------------------------------------
# Leg 2 -- the ladder's first scale rung, and Leg 4 -- the break-even move
# ---------------------------------------------------------------------------

def test_scale_rung_and_be_move():
    for side, bar in (("L", BAR_SCALE_LONG), ("S", BAR_SCALE_SHORT)):
        for plan in ("hod_then_runner_be", "hod_then_runner"):
            saved = bw.SCALE_PLAN
            bw.SCALE_PLAN = plan
            try:
                t = _trade(side)
                book = [t]
                bw._ladder_bar(t, bar, 11, book, _RunnerStub())
            finally:
                bw.SCALE_PLAN = saved

            lv = t.scale_level
            close = bar.close
            check(
                f"scale rung fills on touch [{side}/{plan}]",
                t.scaled,
                f"bar {'high' if side == 'L' else 'low'} "
                f"{bar.high if side == 'L' else bar.low:.2f} reached the rung at "
                f"{lv:.2f} and the close was {close:.2f} -- the rung did not fill, "
                f"so this leg is waiting for a close",
            )
            check(
                f"scale rung keeps the runner open [{side}/{plan}]",
                t in book and t.outcome == "open",
                "the scale rung closed the whole position",
            )
            if plan == "hod_then_runner_be":
                check(
                    f"break-even move happens on the touch [{side}]",
                    abs(t.runner_stop - t.entry) < EPS,
                    f"runner_stop is {t.runner_stop!r}, expected the entry "
                    f"{t.entry:.2f} -- the BE move waited for a close",
                )
            else:
                check(
                    f"no break-even move without the be plan [{side}]",
                    t.runner_stop == 0.0,
                    f"runner_stop is {t.runner_stop!r} under SCALE_PLAN={plan!r}",
                )


# ---------------------------------------------------------------------------
# Leg 3 -- the runner target
# ---------------------------------------------------------------------------

def test_runner_target():
    for side, bar in (("L", BAR_RUN_LONG), ("S", BAR_RUN_SHORT)):
        t = _trade(side)
        t.scaled = True
        t.runner_stop = t.entry          # where the "be" plan leaves it
        book = [t]
        bw._ladder_bar(t, bar, 12, book, _RunnerStub())
        check(
            f"runner target fills on touch [{side}]",
            abs(t.exit_price - t.runner_target) < EPS and t.outcome == "win",
            f"outcome {t.outcome!r} at {t.exit_price!r}; the bar tagged "
            f"{t.runner_target:.2f} and closed at {bar.close:.2f}",
        )
        check(f"runner target closes the position [{side}]", t not in book,
              "the trade is still open after its target filled")


# ---------------------------------------------------------------------------
# Leg 1 -- the blind 2R target, and the Rule 6 break-even scale. Both are
# inline in `simulate_day`, so this is a source guard on the trigger shape.
# ---------------------------------------------------------------------------

_LEVELS = r"(?:t\.target|t\.scale_level|t\.runner_target|t\.be_level|" \
          r"self\.stock_target|self\.be_scale_level|self\.scale_level|" \
          r"self\.runner_target)"
_CLOSE = r"(?:c\.close|\bclose\b)"
FORBIDDEN = [
    re.compile(_CLOSE + r"\s*[<>]=?\s*" + _LEVELS),
    re.compile(_LEVELS + r"\s*[<>]=?\s*" + _CLOSE),
]


def _forbidden_hits(src: str) -> list[str]:
    return [ln.strip() for ln in src.splitlines()
            if any(p.search(ln) for p in FORBIDDEN)]


def test_no_close_triggered_profit_leg_in_source():
    for label, obj in (("backtest_week.simulate_day", bw.simulate_day),
                       ("backtest_week._ladder_bar", bw._ladder_bar),
                       ("paper_trader.PaperPosition", pt.PaperPosition)):
        hits = _forbidden_hits(inspect.getsource(obj))
        check(f"no close-triggered profit leg in {label}", not hits,
              "a profit level is compared against a candle CLOSE: "
              + " | ".join(hits))

    # and the trigger that IS there reads the bar's extremes.
    src = inspect.getsource(bw.simulate_day)
    tgt = [ln.strip() for ln in src.splitlines()
           if re.search(r"\btargeted\s*=", ln)]
    check("blind-2R target trigger exists", len(tgt) == 1,
          f"found {len(tgt)} `targeted =` lines in simulate_day: {tgt}")
    if len(tgt) == 1:
        check("blind-2R target triggers on the bar extremes",
              ("_target_hit(" in tgt[0]) or ("c.high" in tgt[0] and "c.low" in tgt[0]),
              tgt[0])

    be = [ln.strip() for ln in src.splitlines() if "t.be_level" in ln
          and ("c.high" in ln or "c.low" in ln or "c.close" in ln)]
    check("rule 6 break-even scale triggers on the bar extremes",
          bool(be) and all("c.close" not in ln for ln in be),
          " | ".join(be) or "no t.be_level trigger found")


# ---------------------------------------------------------------------------
# The live path -- paper_trader.PaperPosition
# ---------------------------------------------------------------------------

def _position(side: str, ladder: bool = False) -> "pt.PaperPosition":
    g = LONG if side == "L" else SHORT
    return pt.PaperPosition(
        symbol="TEST", direction="call" if side == "L" else "put",
        strike=100.0, expiration="2026-08-30", contracts=10,
        entry_premium=1.00, stop_premium=0.50, target_premium=2.00,
        stock_entry=g["entry"], stock_stop=g["stop"], stock_target=g["target"],
        occ_symbol="TEST260830C00100000", opened_at="2026-08-30T09:45:00",
        premium_risk=0.50,
        be_scale_level=g["scale_level"],
        scale_level=g["scale_level"] if ladder else 0.0,
        runner_target=g["runner_target"] if ladder else 0.0,
        scale_pct=0.5 if ladder else 0.0,
    )


def test_live_target_and_breakeven():
    for side, bar in (("L", BAR_TGT_LONG), ("S", BAR_TGT_SHORT)):
        p = _position(side)
        hit = p._check_target(bar.high, bar.low)
        check(f"live 2R target fills on touch [{side}]",
              hit is not None and hit[1] == "target",
              f"got {hit!r}; the bar tagged {p.stock_target:.2f} and closed "
              f"at {bar.close:.2f}")

        # exit_for is the real entry point: stop first, then target, both on the
        # same bar's numbers. The close never reaches the target here.
        p2 = _position(side)
        got = p2.exit_for(bar.high, bar.low, bar.close)
        check(f"live exit_for books the touched target [{side}]",
              got is not None and got[1] == "target", f"got {got!r}")

    for side, bar in (("L", BAR_SCALE_LONG), ("S", BAR_SCALE_SHORT)):
        p = _position(side)
        lv = p._check_breakeven(bar.high, bar.low)
        check(f"live break-even scale fills on touch [{side}]",
              lv is not None and abs(lv - p.be_scale_level) < EPS,
              f"got {lv!r}; the bar tagged {p.be_scale_level:.2f} and closed "
              f"at {bar.close:.2f}")


def test_live_ladder_rungs():
    for side, bar in (("L", BAR_SCALE_LONG), ("S", BAR_SCALE_SHORT)):
        p = _position(side, ladder=True)
        got = p._ladder_exit(bar.high, bar.low, bar.close)
        check(f"live ladder scale rung fills on touch [{side}]",
              got is not None and got[1] == "scale",
              f"got {got!r}; the bar tagged {p.scale_level:.2f} and closed "
              f"at {bar.close:.2f}")

    for side, bar in (("L", BAR_RUN_LONG), ("S", BAR_RUN_SHORT)):
        p = _position(side, ladder=True)
        p.scaled = True
        p.runner_stop = p.stock_entry
        got = p._ladder_exit(bar.high, bar.low, bar.close)
        check(f"live ladder runner target fills on touch [{side}]",
              got is not None and got[1] == "target",
              f"got {got!r}; the bar tagged {p.runner_target:.2f} and closed "
              f"at {bar.close:.2f}")


# ---------------------------------------------------------------------------
# The third rig that books a target -- research/exit_lab
# ---------------------------------------------------------------------------

def test_exit_lab_flat_target():
    for side in ("L", "S"):
        entry, stop = 100.0, (99.0 if side == "L" else 101.0)
        flat = {"o": entry, "h": entry + 0.05, "l": entry - 0.05,
                "c": entry, "v": 1000}
        bars = [dict(flat) for _ in range(11)]
        if side == "L":
            bars.append({"o": 100.9, "h": 102.05, "l": 100.4, "c": 100.95,
                         "v": 1000})
        else:
            bars.append({"o": 99.1, "h": 99.6, "l": 97.95, "c": 99.05,
                         "v": 1000})
        bars += [dict(flat) for _ in range(40)]
        r = flat_target(bars, 10, entry, stop, side, 2.0)
        check(f"exit_lab flat 2R fills on touch [{side}]", abs(r - 2.0) < 1e-6,
              f"realised {r:+.4f}R on a bar that tagged 2R and closed at "
              f"{bars[11]['c']:.2f}; a close-triggered target books ~0R here")


def main():
    test_scale_rung_and_be_move()
    test_runner_target()
    test_no_close_triggered_profit_leg_in_source()
    test_live_target_and_breakeven()
    test_live_ladder_rungs()
    test_exit_lab_flat_target()

    width = max(len(n) for n, _ in CHECKS)
    for name, ok in CHECKS:
        print(f"{name:<{width}}  {'ok' if ok else 'FAIL'}")

    if FAILURES:
        print()
        print(f"SCALE-OUT TOUCH SELFTEST FAILED: {len(FAILURES)} of "
              f"{len(CHECKS)} checks are wrong.")
        print("\n".join(FAILURES))
        sys.exit(1)

    print()
    print(f"scale-out touch selftest ok: {len(CHECKS)} checks -- every profit "
          f"leg fills the moment price touches it, in the backtest, the live "
          f"path and exit_lab")


if __name__ == "__main__":
    main()
