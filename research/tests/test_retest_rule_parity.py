"""Retest-rule parity: Austin's words vs the frozen v2-t01 engine (orb1m.py, sha256 bafd7ce4...).

His rule, verbatim (00-austin-spec-0926): "price comes back and touches the level, usually a wick;
no candle should close through/below the level; enter on the retest with strong PA (hammer/pin)".
Thresholds per a4-mantra v3: OR5, disp >= 1 ATR, retest within 30 bars, close <= level = void, re-arm.

Every test asserts what HIS rule (or a4 where his words are silent) expects. Where the frozen
engine disagrees the test is xfail(strict=True): the xfail IS the divergence record, and it turns
into a hard failure (XPASS) if the engine ever changes. Tests marked "info" pin engine behaviour
on points his words do not decide.

orb1m.py is untracked research output, so it is loaded read-only from its frozen path (override
with ORB1M_PATH) and its LF-normalised sha256 is checked before any test runs. Never edited here.
"""
import hashlib
import importlib.util
import os
import sys
import types

import numpy as np
import pytest

FROZEN_SHA = "bafd7ce4e4f69250c0cef80acdbd26057ee04a6a658c95b11ed92bba08bc8ef1"
DEFAULT_PATH = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-t01-orb-1m\orb1m.py"
ENGINE_PATH = os.environ.get("ORB1M_PATH", DEFAULT_PATH)

if not os.path.exists(ENGINE_PATH):
    pytest.skip(f"frozen engine not present at {ENGINE_PATH}", allow_module_level=True)


def _load_engine():
    raw = open(ENGINE_PATH, "rb").read()
    sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    assert sha == FROZEN_SHA, f"orb1m.py drifted: {sha}"
    # orb1m imports omen_data (bar loader) at module level; the tests never touch it, so stub it
    # to keep the suite hermetic and data-free.
    saved = sys.modules.get("omen_data")
    sys.modules["omen_data"] = types.SimpleNamespace(load_fut=None, SPEC={})
    try:
        spec = importlib.util.spec_from_file_location("orb1m_frozen", ENGINE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if saved is None:
            sys.modules.pop("omen_data", None)
        else:
            sys.modules["omen_data"] = saved
    return mod


E = _load_engine()
LVL = 101.0          # OR5 high; OR5 low = 100.0; tick 0.25; OR bar range 1.0 -> ATR ~1.0
BREAK = 5            # first bar after OR5
CUT_1030, CUT_1100 = 60, 90

# long-side bar shapes (open, high, low, close) around the 101.0 level
PIN = (101.90, 102.00, 101.00, 101.95)         # lower wick 0.9 of 1.0 range, touches by wick
RED_HAMMER = (101.95, 102.00, 101.00, 101.90)  # same shape, closes below its open
STRONG = (101.10, 102.10, 101.00, 102.05)      # big body, close in top 5%, 0.1 lower wick: not a pin
BODY_TOUCH = (101.00, 102.05, 101.00, 102.00)  # opens ON the level, zero lower wick
WEAK = (101.30, 102.00, 101.00, 101.60)        # green, body 30% of range: neither pin nor strong
NEAR_MISS = (101.90, 102.00, 101.25, 101.95)   # low 1 tick ABOVE the level: never touched it
TWO_TICK_MISS = (101.90, 102.00, 101.50, 101.95)
DEEP_WICK = (101.90, 102.00, 100.20, 101.95)   # wick 0.8 below level (~1 ATR), closes back above
CLOSE_THROUGH = (101.50, 101.60, 100.50, 100.80)
CLOSE_AT_LEVEL = (101.50, 101.60, 100.90, 101.00)
REBREAK = (100.90, 103.00, 100.90, 102.90)     # same shape as the day's first break


def day(retests=None, direction=1):
    """91 one-minute bars 09:30-11:00. OR 100-101, displaced break at bar 5, then filler that
    holds above (below) the level without touching it. `retests` = {bar_index: ohlc}."""
    n = 91
    O = np.full(n, 100.5); H = np.full(n, 101.0); L = np.full(n, 100.0); C = np.full(n, 100.5)
    if direction > 0:
        O[5], H[5], L[5], C[5] = REBREAK
        O[6:], H[6:], L[6:], C[6:] = 102.5, 102.8, 102.2, 102.6
    else:
        O[5], H[5], L[5], C[5] = 100.1, 100.1, 98.0, 98.1
        O[6:], H[6:], L[6:], C[6:] = 98.5, 98.8, 98.2, 98.4
    for j, (o, h, l, c) in (retests or {}).items():
        O[j], H[j], L[j], C[j] = o, h, l, c
    return dict(open=O, high=H, low=L, close=C)


def sig(A, trig="strong", cut=CUT_1030, disp_k=1.0):
    return E.signal(A, 5, cut, disp_k, trig)


# ---- clause 1: "comes back and touches the level, usually a wick" + holds -> signal ----------
@pytest.mark.parametrize("trig", ["pin", "strong"])
def test_wick_touch_then_hold_signals(trig):
    assert sig(day({8: PIN}), trig) == (9, 1, 100.75)  # entry next bar, stop = trigger low - 1 tick


def test_short_side_mirror_signals():
    short_pin = (99.10, 100.00, 99.00, 99.05)  # upper wick tags OR low 100.0, closes low
    assert sig(day({8: short_pin}, direction=-1), "pin") == (9, -1, 100.25)


def test_two_tick_miss_is_not_a_touch():
    assert sig(day({8: TWO_TICK_MISS}), "pin") is None


@pytest.mark.xfail(strict=True, reason="DIVERGENCE D1: engine counts low <= level + 1 tick as a "
                   "touch; his words say price touches the level. a4 documents the +-1 tick.")
def test_one_tick_near_miss_is_not_a_touch():
    assert sig(day({8: NEAR_MISS}), "pin") is None


def test_body_touch_no_wick_info():
    """'usually a wick' is soft: engine accepts a body touch in strong mode, rejects it in pin mode."""
    assert sig(day({8: BODY_TOUCH}), "strong") == (9, 1, 100.75)
    assert sig(day({8: BODY_TOUCH}), "pin") is None


def test_deep_wick_info():
    """His words set no depth limit; engine accepts any depth if the close holds (v3 finding:
    shallow <=0.35 ATR retests are the ones he grades S)."""
    assert sig(day({8: DEEP_WICK}), "pin") == (9, 1, 100.20 - 0.25)


# ---- clause 2: "no candle should close through/below the level" -----------------------------
def test_close_through_voids_first_setup():
    s = sig(day({7: CLOSE_THROUGH, 8: PIN}), "pin")
    assert s is None or s[0] != 9  # the pin right after the close-through must not trade


def test_close_exactly_at_level_voids():
    s = sig(day({7: CLOSE_AT_LEVEL, 8: PIN}), "pin")
    assert s is None or s[0] != 9


def test_close_through_then_rebreak_rearms_and_clean_retest_signals():
    """a4: 'Re-arms after a void'. New displaced break at 8, clean wick retest at 10."""
    assert sig(day({7: CLOSE_THROUGH, 8: REBREAK, 10: PIN}), "pin") == (11, 1, 100.75)


# ---- clause 3: "enter on the retest with strong PA (hammer/pin)" -----------------------------
def test_weak_trigger_does_not_signal():
    assert sig(day({8: WEAK}), "strong") is None
    assert sig(day({8: WEAK}), "any") == (9, 1, 100.75)  # control: trigger filter is what blocks it


def test_pin_vs_strong_modes():
    assert sig(day({8: PIN}), "pin") == (9, 1, 100.75)
    assert sig(day({8: STRONG}), "pin") is None          # strong body is not a pin
    assert sig(day({8: STRONG}), "strong") == (9, 1, 100.75)


def test_red_hammer_counts_as_pin():
    assert sig(day({8: RED_HAMMER}), "pin") == (9, 1, 100.75)


def test_weak_first_touch_then_strong_second_touch_info():
    """'enter on the retest' (singular). Engine keeps waiting and fires on a later strong touch."""
    assert sig(day({8: WEAK, 12: PIN}), "strong") == (13, 1, 100.75)


def test_no_displacement_no_signal():
    A = day({7: PIN})
    A["open"][5], A["high"][5], A["low"][5], A["close"][5] = 100.9, 101.5, 100.9, 101.4
    A["open"][6], A["high"][6], A["low"][6], A["close"][6] = 101.4, 101.6, 101.3, 101.5
    for j in range(8, 91):
        A["open"][j], A["high"][j], A["low"][j], A["close"][j] = 101.5, 101.8, 101.3, 101.6
    assert sig(A, "pin") is None


# ---- clause 4 (a4): retest must come within 30 bars of the break ----------------------------
def test_retest_at_bar_30_signals():
    assert sig(day({BREAK + 30: PIN}), "pin", cut=CUT_1100) == (BREAK + 31, 1, 100.75)


@pytest.mark.xfail(strict=True, reason="DIVERGENCE D2: off-by-one. Expiry (j - bi > 30) is checked "
                   "AFTER the trigger check, so a retest 31 bars after the break still trades.")
def test_retest_at_bar_31_is_void():
    assert sig(day({BREAK + 31: PIN}), "pin", cut=CUT_1100) is None


@pytest.mark.xfail(strict=True, reason="DIVERGENCE D3: after the 30-bar expiry the next bar still "
                   "closing above ORH is taken as a NEW break (no real break happened), so a late "
                   "retest at bar 40 trades.")
def test_expired_setup_does_not_rearm_without_a_real_break():
    assert sig(day({BREAK + 40: PIN}), "pin", cut=CUT_1100) is None
