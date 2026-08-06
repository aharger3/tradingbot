#!/usr/bin/env python3
"""test_s_gate.py -- plain asserts, no pytest. Run: `python3 test_s_gate.py`.

Covers the S gate shipped in omen-3.6 / T6:
  * predicates.is_s_gate accepts / rejects from the spec's literal threshold
    (displacement >= 0.888, the X marks' 50th percentile -- research/s_gate_spec.md).
  * signal_runner.S_GATE defaults to False (shipped behaviour byte-identical).
  * the predicate exists in predicates.py.
"""
import predicates
from predicates import Candle, is_s_gate
import signal_runner


def _bar(price, rng, ts="09:30:00", vol=1000):
    """A zero-body candle with the given range, centred on `price`."""
    return Candle(timestamp=ts, open=price, high=price + rng / 2.0,
                  low=price - rng / 2.0, close=price, volume=vol)


def _series(prior_rng, entry_rng, n_prior=20):
    """n_prior bars of range `prior_rng` then one entry bar of range `entry_rng`."""
    bars = [_bar(100.0, prior_rng, ts=f"09:{30 + i:02d}:00") for i in range(n_prior)]
    bars.append(_bar(100.0, entry_rng, ts=f"09:{30 + n_prior:02d}:00"))
    return bars


# --- accept: displacement 2.0 (>= 0.888) ---
assert is_s_gate(_series(prior_rng=1.0, entry_rng=2.0)) is True, \
    "displacement 2.0 >= 0.888 must pass the gate"

# --- reject: displacement 0.5 (< 0.888) ---
assert is_s_gate(_series(prior_rng=2.0, entry_rng=1.0)) is False, \
    "displacement 0.5 < 0.888 must fail the gate"

# --- boundary at the literal threshold (inclusive) ---
assert is_s_gate(_series(prior_rng=1.0, entry_rng=0.888)) is True, \
    "displacement exactly 0.888 (the threshold) must pass"
assert is_s_gate(_series(prior_rng=1.0, entry_rng=0.887)) is False, \
    "displacement 0.887 just under the threshold must fail"

# --- undefined displacement (no usable prior bars) does not pass ---
assert is_s_gate([_bar(100.0, 2.0)]) is False, \
    "a lone bar with no prior history must not pass (displacement undefined)"
assert is_s_gate([_bar(100.0, 0.0)] + [_bar(100.0, 2.0)]) is False, \
    "zero-range entry bar must not pass"

# --- fewer than 20 prior bars still works (mirrors max(0, entry_i-20)) ---
short = [_bar(100.0, 1.0) for _ in range(5)] + [_bar(100.0, 2.0)]
assert is_s_gate(short) is True, \
    "displacement should be computable from <20 prior bars and pass at 2.0"

# --- the predicate exists in predicates.py ---
assert hasattr(predicates, "is_s_gate"), "predicates.is_s_gate must exist"
assert callable(predicates.is_s_gate)

# --- S_GATE defaults to False (shipped behaviour byte-identical to today) ---
assert signal_runner.S_GATE is False, \
    "S_GATE must default to False (shipped default OFF)"

print("test_s_gate: all assertions passed")
