"""OMEN v2 live paper signal engine.

Wraps the FROZEN t01 detection logic (research/agent_runs/v2-t01-orb-1m/orb1m.py)
unmodified -- imported, never copied, so this can never silently drift from the
engine the backtest numbers in OMEN-SHIP-PLAN-v2.md were measured on.

Setup: ORB5 break + displacement (>=1.0x ATR14) + wick retest (no close-through)
+ strong/pin trigger candle. 1-min bars, 09:30-11:00 ET window, cutoff configurable
(10:30 default per the shipped MNQ-only verdict; 10:45/11:00 also testable).

Paper only. This module detects and formats signals -- it never places an order.
"""
from __future__ import annotations

import sys
import os
from dataclasses import dataclass, field
from typing import Optional

_T01_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "v2-t01-orb-1m",
)
if _T01_DIR not in sys.path:
    sys.path.insert(0, _T01_DIR)

from orb1m import signal as _orb_signal, TICK, CUTS  # noqa: E402  (frozen engine)

CUTOFF_MINUTES = CUTS  # {"10:30": 60, "10:45": 75, "11:00": 90}
OR_MINUTES = 5          # OR5 (t01's winning MNQ variant)
DISP_K = 1.0             # displacement filter, frozen -- required, do not tune
TRIGGER = "strong"       # strong/pin trigger candle, frozen


@dataclass
class BarWindow:
    """Rolling 09:30-11:00 1-min OHLC arrays for one session, one symbol.

    Index 0 = 09:30 bar, index 90 = 11:00 bar (matches orb1m.day_arrays()).
    Feed bars in one at a time as they close with `update()`.
    """
    open: list = field(default_factory=lambda: [float("nan")] * 91)
    high: list = field(default_factory=lambda: [float("nan")] * 91)
    low: list = field(default_factory=lambda: [float("nan")] * 91)
    close: list = field(default_factory=lambda: [float("nan")] * 91)
    last_idx: int = -1

    def update(self, minute_idx: int, o: float, h: float, l: float, c: float) -> None:
        if not (0 <= minute_idx <= 90):
            return  # outside the 09:30-11:00 window -- not our session
        self.open[minute_idx] = o
        self.high[minute_idx] = h
        self.low[minute_idx] = l
        self.close[minute_idx] = c
        self.last_idx = max(self.last_idx, minute_idx)

    def as_arrays(self):
        import numpy as np
        return {
            "open": np.array(self.open, dtype=float),
            "high": np.array(self.high, dtype=float),
            "low": np.array(self.low, dtype=float),
            "close": np.array(self.close, dtype=float),
        }


@dataclass
class Signal:
    entry_minute: int   # bar index at which entry happens (next-bar open)
    retest_minute: int  # bar index of the retest/trigger candle just closed
    side: int            # 1 = long, -1 = short
    stop: float
    entry_hint: Optional[float] = None  # last known price near entry, for display only


def check_for_signal(window: BarWindow, cutoff: str = "10:30") -> Optional[Signal]:
    """Call once per new closed 1-min bar. Fires the moment the ENTRY bar
    (next bar after the retest+trigger candle) has itself closed, so the card
    can report a real, already-known entry price -- the frozen engine's own
    `signal()` requires the entry bar's open to be non-NaN (it looks one bar
    past the retest by design), which is only true once that bar has arrived.
    """
    cut = CUTOFF_MINUTES[cutoff]
    if window.last_idx < OR_MINUTES:
        return None
    A = window.as_arrays()
    result = _orb_signal(A, OR_MINUTES, min(cut, window.last_idx + 1), DISP_K, TRIGGER)
    if not result:
        return None
    entry_i, side, stop = result
    if entry_i != window.last_idx:
        return None  # signal from an earlier bar already handled, or not yet reached
    return Signal(entry_minute=entry_i, retest_minute=entry_i - 1, side=side, stop=float(stop))
