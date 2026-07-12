"""Regime detection filters for OMEN trading bot.

Three methods (configurable via MODE):
  1. SMA crossover   — SPY daily SMA50 vs SMA200; price distance measures melt-up
  2. VIX regime      — VIX<14 = low-vol / melt-up territory; VIX>25 = fear
  3. Rolling P&L     — trailing N-day aggregate P&L; negative = kill switch

Each method returns a (regime, action) tuple per day.
Action: NORMAL | CAUTION (size down / alert-only) | STOP (no trades)
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import math


# --- public constants ---

# Modes
MODE_NONE = "none"
MODE_SMA = "sma_crossover"
MODE_VIX = "vix"
MODE_PNL = "rolling_pnl"
MODE_PNL_DIRECTIONAL = "rolling_pnl_directional"

# Regime labels
REGIME_TRENDING_BULL = "trending_bull"
REGIME_TRENDING_BEAR = "trending_bear"
REGIME_MELT_UP = "melt_up"
REGIME_MELT_DOWN = "melt_down"
REGIME_CHOP = "chop"
REGIME_HIGH_VOL = "high_vol"
REGIME_PANIC = "panic"
REGIME_NORMAL = "normal"
REGIME_UNKNOWN = "unknown"

# Actions
ACTION_NORMAL = "normal"
ACTION_CAUTION = "caution"     # cap grade at C (alert-only), reduce size
ACTION_STOP = "stop"           # no trades at all
ACTION_STOP_LONG = "stop_long"   # no call entries (melt-up defense)
ACTION_STOP_SHORT = "stop_short" # no put entries (melt-down defense)


# --- defaults / tunables ---

DEFAULT_SMA_FAST = 50
DEFAULT_SMA_SLOW = 200
DEFAULT_MELT_UP_THRESHOLD = 0.05    # price > SMA50 by 5% = melt-up
DEFAULT_MELT_DOWN_THRESHOLD = -0.05 # price < SMA50 by 5% = melt-down
DEFAULT_CHOP_BAND = 0.02            # SMA50 within 2% of SMA200 = chop

DEFAULT_VIX_LOW = 14    # below this = melt-up territory
DEFAULT_VIX_HIGH = 25   # above this = fear
DEFAULT_VIX_PANIC = 35

DEFAULT_PNL_WINDOW = 5          # trailing N days
DEFAULT_PNL_THRESHOLD = 0      # stop when trailing sum < this


@dataclass
class RegimeConfig:
    """Per-mode configuration.

    mode       — which detector to use. Empty string / MODE_NONE = no filter.
    sma_fast   — fast SMA period (default 50)
    sma_slow   — slow SMA period (default 200)
    melt_up    — price > SMAfast by this fraction = melt-up (STOP long entries)
    melt_down  — price < SMAfast by this fraction = melt-down (STOP short entries)
    chop_band  — SMAfast within this fraction of SMAslow = chop (CAUTION)
    vix_low    — VIX below this = low vol / melt-up territory (STOP long)
    vix_high   — VIX above this = high vol (CAUTION)
    vix_panic  — VIX above this = panic (STOP all)
    pnl_window — trailing days for kill switch
    pnl_threshold — trailing sum below this = STOP
    """
    mode: str = MODE_NONE
    directional: bool = True    # True: melt-up stops only longs, melt-down stops only shorts
    sma_fast: int = DEFAULT_SMA_FAST
    sma_slow: int = DEFAULT_SMA_SLOW
    melt_up_threshold: float = DEFAULT_MELT_UP_THRESHOLD
    melt_down_threshold: float = DEFAULT_MELT_DOWN_THRESHOLD
    chop_band: float = DEFAULT_CHOP_BAND
    vix_low: float = DEFAULT_VIX_LOW
    vix_high: float = DEFAULT_VIX_HIGH
    vix_panic: float = DEFAULT_VIX_PANIC
    pnl_window: int = DEFAULT_PNL_WINDOW
    pnl_threshold: float = DEFAULT_PNL_THRESHOLD


# --- core detector ---

class RegimeDetector:
    """Compute a daily regime signal from market-wide data.

    Caller (backtest or live_scanner) is responsible for:
      - supplying SPY daily closes (or hourly -> daily resample)
      - supplying VIX closes (daily)
      - feeding per-day aggregate P&L when MODE_PNL is active

    Primary interface: get_action(day_iso) -> str (NORMAL / CAUTION / STOP)
    """

    def __init__(self, config: Optional[RegimeConfig] = None):
        self.cfg = config or RegimeConfig()
        self._daily_closes: List[float] = []          # ordered oldest→newest
        self._daily_dates: List[str] = []              # parallel to closes
        self._vix_closes: List[float] = []             # parallel to dates
        self._vix_dates: List[str] = []
        # Rolling P&L: maps day_iso -> total P&L for that day across all symbols
        self._daily_pnl: dict = {}
        # Directional P&L: per-side trailing tracking
        self._daily_call_pnl: dict = {}
        self._daily_put_pnl: dict = {}
        self._computed: dict = {}  # day_iso -> (regime, action) cache

    # ---- data feeding ----

    def feed_daily_closes(self, dates: List[str], closes: List[float]) -> None:
        """Set SPY daily closes (oldest first). Call once before backtest loop."""
        self._daily_dates = dates
        self._daily_closes = closes

    def feed_vix_closes(self, dates: List[str], closes: List[float]) -> None:
        """Set VIX daily closes. Must be aligned to SPY dates (oldest first)."""
        self._vix_dates = dates
        self._vix_closes = closes

    def record_daily_pnl(self, day_iso: str, pnl: float) -> None:
        """Feed one day's aggregate P&L (summed across all symbols)."""
        self._daily_pnl[day_iso] = self._daily_pnl.get(day_iso, 0.0) + pnl

    def record_daily_directional_pnl(self, day_iso: str, call_pnl: float, put_pnl: float) -> None:
        """Feed one day's per-side P&L for directional kill switch."""
        self._daily_call_pnl[day_iso] = self._daily_call_pnl.get(day_iso, 0.0) + call_pnl
        self._daily_put_pnl[day_iso] = self._daily_put_pnl.get(day_iso, 0.0) + put_pnl

    # ---- core logic ----

    def _sma(self, closes: List[float], period: int) -> Optional[float]:
        if len(closes) < period:
            return None
        return sum(closes[-period:]) / period

    def _regime_sma(self, day_idx: int) -> Tuple[str, str]:
        """SMA crossover regime detection on SPY daily closes."""
        closes = self._daily_closes[:day_idx + 1]
        if len(closes) < self.cfg.sma_slow:
            return REGIME_UNKNOWN, ACTION_NORMAL

        current = closes[-1]
        sma_fast = self._sma(closes, self.cfg.sma_fast)
        sma_slow = self._sma(closes, self.cfg.sma_slow)
        if sma_fast is None or sma_slow is None:
            return REGIME_UNKNOWN, ACTION_NORMAL

        pct_vs_fast = (current - sma_fast) / sma_fast

        # Melt-up: price well above SMA50 (blow-off top — breaks don't retrace down)
        # STOP_SHORT: in a strong bull, short/B&R-puts can't form (the task's bleed)
        if pct_vs_fast > self.cfg.melt_up_threshold:
            action = ACTION_STOP_SHORT if self.cfg.directional else ACTION_STOP
            return REGIME_MELT_UP, action

        # Melt-down: price well below SMA50 (capitulation — breaks don't retrace up)
        # STOP_LONG: in a strong bear, long/B&R-calls can't form
        if pct_vs_fast < self.cfg.melt_down_threshold:
            action = ACTION_STOP_LONG if self.cfg.directional else ACTION_STOP
            return REGIME_MELT_DOWN, action

        # Chop: SMAs tight together
        sma_spread = abs(sma_fast - sma_slow) / sma_slow
        if sma_spread < self.cfg.chop_band:
            return REGIME_CHOP, ACTION_CAUTION

        # Trending bull: price > SMA50 > SMA200 (orderly uptrend — good for B&R)
        if current > sma_fast > sma_slow:
            return REGIME_TRENDING_BULL, ACTION_NORMAL

        # Trending bear
        if current < sma_fast < sma_slow:
            return REGIME_TRENDING_BEAR, ACTION_NORMAL

        # Everything else = normal
        return REGIME_NORMAL, ACTION_NORMAL

    def _regime_vix(self, day_idx: int) -> Tuple[str, str]:
        """VIX-based regime."""
        if not self._vix_closes or day_idx >= len(self._vix_closes):
            return REGIME_UNKNOWN, ACTION_NORMAL

        vix = self._vix_closes[day_idx]

        # Panic: extreme fear — STOP all trades
        if vix > self.cfg.vix_panic:
            return REGIME_PANIC, ACTION_STOP

        # High vol: elevated fear — CAUTION (wider stops, tighter size)
        if vix > self.cfg.vix_high:
            return REGIME_HIGH_VOL, ACTION_CAUTION

        # Low vol / complacency: melt-up territory — STOP long entries
        if vix < self.cfg.vix_low:
            return REGIME_MELT_UP, ACTION_CAUTION

        return REGIME_NORMAL, ACTION_NORMAL

    def _regime_pnl(self, day_idx: int) -> Tuple[str, str]:
        """Rolling P&L kill switch."""
        if not self._daily_pnl:
            return REGIME_UNKNOWN, ACTION_NORMAL

        dates = self._daily_dates[:day_idx + 1]
        window = self.cfg.pnl_window
        if len(dates) < window:
            return REGIME_UNKNOWN, ACTION_NORMAL

        trailing = 0.0
        for d in dates[-window:]:
            trailing += self._daily_pnl.get(d, 0.0)

        if trailing < self.cfg.pnl_threshold:
            return f"drawdown_${trailing:.0f}", ACTION_STOP

        return REGIME_NORMAL, ACTION_NORMAL

    def _regime_pnl_directional(self, day_idx: int) -> Tuple[str, str]:
        """Directional rolling P&L kill switch — stops only the losing side.

        Separately tracks trailing call P&L and put P&L. When one side's
        trailing N-day sum is negative, stops that side only. The winning
        side keeps trading.
        """
        if not self._daily_call_pnl:
            return REGIME_UNKNOWN, ACTION_NORMAL

        dates = self._daily_dates[:day_idx + 1]
        window = self.cfg.pnl_window
        if len(dates) < window:
            return REGIME_UNKNOWN, ACTION_NORMAL

        trailing_calls = 0.0
        trailing_puts = 0.0
        for d in dates[-window:]:
            trailing_calls += self._daily_call_pnl.get(d, 0.0)
            trailing_puts += self._daily_put_pnl.get(d, 0.0)

        call_bad = trailing_calls < self.cfg.pnl_threshold
        put_bad = trailing_puts < self.cfg.pnl_threshold

        if call_bad and put_bad:
            return f"both_sides_bleeding_c${trailing_calls:.0f}_p${trailing_puts:.0f}", ACTION_STOP
        if call_bad:
            return f"calls_bleeding_${trailing_calls:.0f}", ACTION_STOP_LONG
        if put_bad:
            return f"puts_bleeding_${trailing_puts:.0f}", ACTION_STOP_SHORT

        return REGIME_NORMAL, ACTION_NORMAL

    # ---- public interface ----

    def get_action(self, day_iso: str) -> Tuple[str, str]:
        """Return (regime_label, action) for this day.

        If mode is NONE / empty, returns (REGIME_NORMAL, ACTION_NORMAL) — no filter.
        """
        if self.cfg.mode == MODE_NONE:
            return REGIME_NORMAL, ACTION_NORMAL

        cached = self._computed.get(day_iso)
        if cached:
            return cached

        # Find this day's index
        try:
            day_idx = self._daily_dates.index(day_iso)
        except ValueError:
            return REGIME_UNKNOWN, ACTION_NORMAL

        if self.cfg.mode == MODE_SMA:
            result = self._regime_sma(day_idx)
        elif self.cfg.mode == MODE_VIX:
            result = self._regime_vix(day_idx)
        elif self.cfg.mode == MODE_PNL:
            result = self._regime_pnl(day_idx)
        elif self.cfg.mode == MODE_PNL_DIRECTIONAL:
            result = self._regime_pnl_directional(day_idx)
        else:
            result = REGIME_UNKNOWN, ACTION_NORMAL

        self._computed[day_iso] = result
        return result


# --- convenience: build the 3 standard configs ---

def sma_config() -> RegimeConfig:
    return RegimeConfig(mode=MODE_SMA)

def vix_config() -> RegimeConfig:
    return RegimeConfig(mode=MODE_VIX)

def pnl_config(window: int = 5, threshold: float = 0) -> RegimeConfig:
    return RegimeConfig(mode=MODE_PNL, pnl_window=window, pnl_threshold=threshold)

def directional_pnl_config(window: int = 5, threshold: float = 0) -> RegimeConfig:
    return RegimeConfig(mode=MODE_PNL_DIRECTIONAL, pnl_window=window, pnl_threshold=threshold)
