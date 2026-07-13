"""SPEC17 - Backtest OMEN signals over the last trading week.

Walk-forward: replay each session bar-by-bar through SignalRunner.detect_signals,
capture every signal (fired + D-grade/tight-stop skips), simulate outcomes
(2R target vs stop), and write backtest_report.md.

Data: yfinance 1-min bars (free tier covers ~7 days back). P&L assumes fixed
$1000 risk per trade: win = +$2000 (2R), loss = -$1000, scratch = R-multiple x $1000.

Usage: python backtest_week.py [YYYY-MM-DD ...]   (default: last week's sessions)
"""

import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd
import yfinance as yf

from omen_bot import Candle, TradeGrade
from signal_runner import SignalRunner

# Austin's watchlist 2026-07-11: all stocks with ~200k+ daily options volume
# (his rule — high options volume = cleaner moves, easier fills). SPY/QQQ stay
# as trend reference, rarely traded.
CORE_SYMBOLS = ["TSLA", "NVDA", "AAPL", "AMD", "META",
                "GOOGL", "AMZN", "MSFT", "PLTR", "QQQ"]  # A3: SPY removed (0-for-5)
EXPERIMENTAL_SYMBOLS = ["SOFI", "ORCL", "COIN", "HOOD", "IREN", "INTC",
                        "NFLX", "AVGO", "MU", "UBER", "BABA", "CRM",
                        "TSM", "MARA"]  # A3: SMCI/MSTR/RIVN removed (−$22k/12mo)
SYMBOLS = CORE_SYMBOLS + EXPERIMENTAL_SYMBOLS
RISK_DOLLARS = 1000.0
DEDUPE_BARS = 30  # same setup re-firing within 30 min = same trade idea
REPORT_PATH = Path(__file__).parent / "backtest_report.md"

# ---- Rule 6: Position Management (Scarface: scale 50% at HOD/breakeven) ----
# Austin 2026-07-10: "Mgmt: scale HOD / breakeven at post-entry red OB."
# When price hits entry + 1R (calls) / entry - 1R (puts), close 50% at breakeven,
# move runner stop to entry, let runner ride to 2R. Improves R:R by locking partial
# profit and reducing max-loss frequency (runner is free after breakeven).
RULE6_ENABLED = False     # toggle for backtest comparison; 12mo A/B 2026-07-12
                          # (backtest_rule6_comparison.md): stays OFF per synthesis
RULE6_SCALE_PCT = 0.5      # fraction of position closed at breakeven
RULE6_BE_MULT = 1.0        # breakeven level = entry +- 1R x this multiplier

# ---- F1: Liquidity-ladder exits (fable-spec-2026-07-12, audit #7) ----
# Source: "exit some at high of day every single time", then next draw of
# liquidity (PDH/PDL, psych whole numbers); "2:1 is the MINIMUM aggregate
# expectation, not the exit mechanism". Blind 2R was our invention.
#   None = blind 2R (current behavior)
#   "A"  = 50% off at first HOD/LOD touch after entry (session extremes as-of
#          entry bar, no lookahead); stop unchanged until scale; runner to
#          first key level beyond the scale point (PDH/PDL/PMH/PML/next whole
#          dollar; fallback = original 2R target); runner keeps original stop
#   "B"  = A + stop -> breakeven after the first scale
# W% note: scaled trades are labeled win/loss by SIGN of total P&L; EOD runners
# stay "scratch" (same as blind-2R). 84% arming: only FULL stop-outs (unscaled)
# arm a re-entry — a scaled trade already paid, "stop was wrong" doesn't apply.
LADDER_MODE = None  # F1 A/B 2026-07-11: A −$12k full-pop / tier $5.9k; B (BE
                    # after scale) 58%W tier but $5.7k vs blind-2R $25k. Ladder
                    # trades expectancy for win rate on our population — OFF.
                    # See research/f2f1_runs/session-notes.md.



@dataclass
class SimTrade:
    symbol: str
    day: str
    signal_type: str
    direction: str  # call/put
    grade: str
    status: str     # fired / skipped_d / skipped_tight_stop
    entry_time: str
    entry: float
    stop: float
    target: float
    outcome: str = "open"  # win / loss / scratch
    exit_price: float = 0.0
    reason: str = ""
    entry_idx: int = 0
    exit_idx: int = 0
    # Rule 6: breakeven scaling fields
    be_level: float = 0.0     # stock price where 50% is scaled out (0 = disabled)
    be_taken: bool = False     # whether breakeven scale already fired
    runner_stop: float = 0.0   # raised stop for runner after BE taken
    # F1 ladder fields
    scale_level: float = 0.0   # HOD/LOD as-of entry bar (50% scale trigger)
    runner_target: float = 0.0 # first key level beyond scale point
    scaled: bool = False       # ladder 50% scale fired

    @property
    def counted(self) -> bool:
        # C is alert-only in live_scanner (SPEC2) — excluded from traded P&L
        return self.status == "fired" and self.grade != "C"

    @property
    def is_alert(self) -> bool:
        return self.status == "fired" and self.grade == "C"

    @property
    def pnl(self) -> float:
        """Dollar P&L at RISK_DOLLARS risk per trade.

        Rule 6 (when enabled): if BE scale was taken, the scaled portion
        locks partial profit and the runner rides to breakeven stop/target.
        Without Rule 6, binary P&L as before (win = +2R, loss = -1R).

        84% 2x sizing REMOVED 2026-07-10: re-entries keep the ORIGINAL stop
        but only the REMAINING distance to target (avg 1.4R, some 0.6R)
        -- doubling size on degraded geometry was a martingale
        (12mo: -$8.7k at 2x, all losses -$2k)."""
        risk = abs(self.entry - self.stop)
        if risk == 0:
            return 0.0

        # F1 ladder: 50% filled at scale_level + 50% at exit_price
        if self.scaled:
            sign = 1 if self.direction == "call" else -1
            scale_r = sign * (self.scale_level - self.entry) / risk
            run_r = sign * (self.exit_price - self.entry) / risk
            return round((0.5 * scale_r + 0.5 * run_r) * RISK_DOLLARS, 2)

        # Rule 6: BE scale taken -> two-stage P&L
        if self.be_taken:
            be_r = 1.0  # always 1R at breakeven
            be_pnl = be_r * RISK_DOLLARS * RULE6_SCALE_PCT
            if self.outcome == "win":
                run_r = 2.0
                run_pnl = run_r * RISK_DOLLARS * (1 - RULE6_SCALE_PCT)
            else:
                run_pnl = 0.0
            return round(be_pnl + run_pnl, 2)

        # Original binary P&L (no Rule 6)
        move = (self.exit_price - self.entry) if self.direction == "call" else (self.entry - self.exit_price)
        return round(move / risk * RISK_DOLLARS * 1.0, 2)


def _arm_84(t: "SimTrade", runner: "BacktestRunner") -> None:
    """Arm one 84%-rule re-entry off a full stop-out (same gate as blind-2R path)."""
    from signal_runner import RULE84_ARM_BNR_ONLY
    arm_ok = t.signal_type == "break_and_retest" if RULE84_ARM_BNR_ONLY \
        else t.signal_type != "reentry_84_rule"
    if t.counted and arm_ok:
        runner.session.entry_price = t.entry
        runner.session.entry_direction = t.direction
        runner.session.entry_target = t.target
        runner.session.entry_stop = t.stop


def _ladder_bar(t: "SimTrade", c: Candle, i: int, open_trades: list,
                runner: "BacktestRunner") -> None:
    """F1 ladder position management for one bar. Conservative: stop wins ties."""
    long = t.direction == "call"
    if not t.scaled:
        if (c.low <= t.stop) if long else (c.high >= t.stop):
            t.outcome, t.exit_price, t.exit_idx = "loss", t.stop, i
            open_trades.remove(t)
            _arm_84(t, runner)  # full stop-out arms 84%, scaled trades never do
            return
        if (c.high >= t.scale_level) if long else (c.low <= t.scale_level):
            t.scaled = True
            if LADDER_MODE == "B":
                t.runner_stop = t.entry  # accelerator: BE after first scale
        return
    stop_lv = t.runner_stop if (LADDER_MODE == "B" and t.runner_stop) else t.stop
    if (c.low <= stop_lv) if long else (c.high >= stop_lv):
        t.exit_price, t.exit_idx = stop_lv, i
    elif (c.high >= t.runner_target) if long else (c.low <= t.runner_target):
        t.exit_price, t.exit_idx = t.runner_target, i
    else:
        return
    p = t.pnl
    t.outcome = "win" if p > 0 else ("loss" if p < 0 else "scratch")
    open_trades.remove(t)


class BacktestRunner(SignalRunner):
    """Capture ALL signals including D-grade and tight-stop skips."""

    def __init__(self, symbol: str):
        super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
        self.captured: List[dict] = []

    def _route(self, signals: List[dict], sig: dict) -> None:
        self._grade_for_levels(sig)
        self._calibration_grade(sig)
        if sig["grade"] == TradeGrade.D.value:
            sig["status"] = "skipped_d"
        elif sig["grade"] == "C" and not self._min_viable_stop(sig["entry"], sig["stop"], sig["direction"]):
            sig["status"] = "skipped_tight_stop"
        else:
            sig["status"] = "fired"
            self._dir_fired[sig["direction"]] = self._dir_fired.get(sig["direction"], 0) + 1
            signals.append(sig)
        self.captured.append(sig)


# ---- data ----

def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def fetch_week(symbol: str, days: int = 8) -> dict:
    """Return {date_iso: [Candle...]} of RTH 1-min candles, plus hourly closes.

    yfinance caps 1m data at 8 days/request and ~30 days of history, so longer
    ranges are fetched in 7-day chunks and concatenated.
    """
    if days <= 8:
        m1 = _flatten(yf.download(symbol, period=f"{days}d", interval="1m",
                                  prepost=True, progress=False, auto_adjust=False))
    else:
        chunks = []
        end = date.today() + timedelta(days=1)
        start = date.today() - timedelta(days=min(days, 29))
        cur = start
        while cur < end:
            nxt = min(cur + timedelta(days=7), end)
            try:
                df = _flatten(yf.download(symbol, start=cur.isoformat(), end=nxt.isoformat(),
                                          interval="1m", prepost=True, progress=False,
                                          auto_adjust=False))
                if len(df):
                    chunks.append(df)
            except Exception as e:
                print(f"  [{symbol}] chunk {cur} failed: {e}")
            cur = nxt
        m1 = pd.concat(chunks) if chunks else pd.DataFrame()
    h1 = _flatten(yf.download(symbol, period="3mo", interval="1h",
                              prepost=False, progress=False, auto_adjust=False))
    days = defaultdict(list)
    premkt = {}  # day -> [pm_high, pm_low] from 04:00-09:29 extended-hours bars
    rth_open = datetime.strptime("09:30", "%H:%M").time()
    rth_close = datetime.strptime("16:00", "%H:%M").time()
    for ts, row in m1.iterrows():
        if pd.isna(row["Open"]):
            continue
        t, d = ts.time(), ts.date().isoformat()
        if t < rth_open:
            hi, lo = float(row["High"]), float(row["Low"])
            if d in premkt:
                premkt[d][0] = max(premkt[d][0], hi)
                premkt[d][1] = min(premkt[d][1], lo)
            else:
                premkt[d] = [hi, lo]
            continue
        if t >= rth_close:
            continue
        days[d].append(Candle(
            timestamp=ts.strftime("%H:%M:%S"),
            open=float(row["Open"]), high=float(row["High"]),
            low=float(row["Low"]), close=float(row["Close"]),
            volume=int(row["Volume"] or 0),
        ))
    hourly = [(ts, float(row["Close"])) for ts, row in h1.iterrows() if not pd.isna(row["Close"])]
    return {"days": dict(days), "hourly": hourly,
            "premkt": {d: tuple(v) for d, v in premkt.items()}}


def htf_bias_for(hourly, day_iso: str) -> Optional[str]:
    """Close vs SMA20 of hourly closes before the session open (mirrors fetch_htf_bias)."""
    closes = [c for ts, c in hourly if ts.date().isoformat() < day_iso]
    if len(closes) < 20:
        return None
    sma20 = sum(closes[-20:]) / 20
    last = closes[-1]
    if last > sma20 * 1.001:
        return "bullish"
    if last < sma20 * 0.999:
        return "bearish"
    return "neutral"


# ---- simulation ----

ENTRY_CUTOFF = "11:00:00"  # Scarface trades 9:30-11 only (volume/volatility); None = all day


def simulate_day(symbol: str, day_iso: str, candles: List[Candle],
                 pdh: Optional[float], pdl: Optional[float], bias: Optional[str],
                 pmh: Optional[float] = None, pml: Optional[float] = None,
                 pdo: Optional[float] = None, pdc: Optional[float] = None,
                 qqq: Optional[dict] = None) -> List[SimTrade]:
    runner = BacktestRunner(symbol)
    runner.pdh, runner.pdl, runner.htf_bias = pdh, pdl, bias
    runner.pmh, runner.pml = pmh, pml
    runner.pd_open, runner.pd_close = pdo, pdc  # [pdwick] tag inputs
    runner.qqq_breaks = qqq  # F4 [qqqA]/[qqqX] tag input

    trades: List[SimTrade] = []
    open_trades: List[SimTrade] = []
    seen = {}  # dedupe key -> last bar index it appeared

    for i in range(5, len(candles)):
        c = candles[i]

        # 1. update open sim positions against this bar
        for t in list(open_trades):
            if LADDER_MODE:
                _ladder_bar(t, c, i, open_trades, runner)
                continue
            # Rule 6: check breakeven scale BEFORE stop/target
            if RULE6_ENABLED and not t.be_taken and t.be_level > 0:
                if (t.direction == "call" and c.high >= t.be_level) or                    (t.direction == "put" and c.low <= t.be_level):
                    t.be_taken = True
                    t.runner_stop = t.entry  # raise stop to breakeven
                    # BE scale recorded; runner continues below
            # Check stop (using runner_stop if BE taken)
            check_stop = t.runner_stop if t.be_taken else t.stop
            if t.direction == "call":
                stopped, targeted = c.low <= check_stop, c.high >= t.target
            else:
                stopped, targeted = c.high >= check_stop, c.low <= t.target
            if stopped:  # both in one bar -> conservative: loss
                t.outcome, t.exit_price, t.exit_idx = "loss", t.stop, i
                open_trades.remove(t)
                # Lesson 6 canonical: arm only off solid B&R stop-outs (Scarface:
                # "can't be a one-minute order block with nothing else")
                from signal_runner import RULE84_ARM_BNR_ONLY
                arm_ok = t.signal_type == "break_and_retest" if RULE84_ARM_BNR_ONLY \
                    else t.signal_type != "reentry_84_rule"
                if t.counted and arm_ok:
                    runner.session.entry_price = t.entry
                    runner.session.entry_direction = t.direction
                    runner.session.entry_target = t.target
                    runner.session.entry_stop = t.stop
            elif targeted:
                t.outcome, t.exit_price, t.exit_idx = "win", t.target, i
                open_trades.remove(t)

        # 2. detect signals as of this bar (open positions still managed after cutoff)
        if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
            continue
        runner.candles = candles[:i + 1]
        before = len(runner.captured)
        runner.detect_signals()

        for sig in runner.captured[before:]:
            # Dedupe by trade IDEA. For B&R that's the broken level (name is
            # unique per day) — keying on stop price breaks under F2 variable
            # stops (retest/buffer stops shift by the bar -> 760 tr became 1811).
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            if key in seen and i - seen[key] < DEDUPE_BARS:
                seen[key] = i  # still firing: extend suppression
                continue
            seen[key] = i
            risk = abs(sig["entry"] - sig["stop"])
            # 84% signals carry the ORIGINAL trade's target; everything else 2R
            target = sig.get("target") or (
                sig["entry"] + 2 * risk if sig["direction"] == "call" else sig["entry"] - 2 * risk)
            # Rule 6: breakeven scaling level at entry +- 1R
            if RULE6_ENABLED and risk > 0:
                if sig["direction"] == "call":
                    be_level = sig["entry"] + RULE6_BE_MULT * risk
                else:
                    be_level = sig["entry"] - RULE6_BE_MULT * risk
            else:
                be_level = 0.0
            # F1 ladder: scale trigger = session extreme as-of entry bar (no
            # lookahead); runner target = first key level beyond the scale point
            scale_level = runner_tgt = 0.0
            if LADDER_MODE and risk > 0:
                if sig["direction"] == "call":
                    scale_level = max(cd.high for cd in candles[:i + 1])
                    cands = [x for x in (pdh, pmh) if x is not None and x > scale_level]
                    cands.append(math.floor(scale_level) + 1.0)  # next psych whole $
                    runner_tgt = min(cands)
                else:
                    scale_level = min(cd.low for cd in candles[:i + 1])
                    cands = [x for x in (pdl, pml) if x is not None and x < scale_level]
                    cands.append(math.ceil(scale_level) - 1.0)
                    runner_tgt = max(cands)

            t = SimTrade(symbol=symbol, day=day_iso,
                         signal_type=sig["signal_type"].value,
                         direction=sig["direction"], grade=sig["grade"],
                         status=sig["status"], entry_time=c.timestamp,
                         entry=sig["entry"], stop=sig["stop"], target=target,
                         reason=sig["reason"], entry_idx=i, exit_idx=len(candles) - 1,
                         be_level=be_level, scale_level=scale_level,
                         runner_target=runner_tgt)
            trades.append(t)
            if risk > 0:
                open_trades.append(t)

    # EOD: whatever is open scratches at last close
    for t in open_trades:
        t.outcome, t.exit_price = "scratch", candles[-1].close
    return trades


# ---- report ----

def _stats(trades: List[SimTrade]) -> tuple:
    """(n, wins, losses, scratches, win_rate_pct, pnl)"""
    n = len(trades)
    wins = sum(1 for t in trades if t.outcome == "win")
    losses = sum(1 for t in trades if t.outcome == "loss")
    scr = n - wins - losses
    decided = wins + losses
    wr = round(wins / decided * 100, 1) if decided else 0.0
    pnl = round(sum(t.pnl for t in trades), 2)
    return n, wins, losses, scr, wr, pnl


def write_report(all_trades: List[SimTrade], days: List[str], notes: List[str]) -> str:
    fired = [t for t in all_trades if t.counted]
    alerts = [t for t in all_trades if t.is_alert]
    d_skips = [t for t in all_trades if t.status == "skipped_d"]
    tight = [t for t in all_trades if t.status == "skipped_tight_stop"]

    lines = [f"# Backtest Report: Week of {days[0]} to {days[-1]}" if days
             else "# Backtest Report", ""]
    lines += ["## Assumptions",
              "- Data: yfinance 1-min RTH bars; walk-forward replay through SignalRunner.detect_signals",
              f"- $1000 risk per trade, 2R target -> win +$2000, loss -$1000, scratch = R x $1000 at EOD close",
              "- Stop+target same bar counted as loss (conservative)",
              f"- Repeat fires of same setup within {DEDUPE_BARS} min deduped",
              ""]

    n, w, l, s, wr, pnl = _stats(fired)
    lines += ["## Summary",
              f"- Traded signals (A+/A/B, viable stop): **{n}** | {w}W {l}L {s} scratch | win rate {wr}% (of decided)",
              f"- Simulated P&L (traded all A+/A/B): **{'+' if pnl >= 0 else ''}${pnl}**",
              f"- C-grade alerts (alert-only per SPEC2): {len(alerts)} | D filtered: {len(d_skips)} | tight-stop skips: {len(tight)}",
              ""]

    lines += ["### By Grade", "| Grade | Signals | W | L | Scratch | Win rate | P&L |",
              "|-------|---------|---|---|---------|----------|-----|"]
    for g in ["A+", "A", "B"]:
        gt = [t for t in fired if t.grade == g]
        if gt:
            n, w, l, s, wr, pnl = _stats(gt)
            lines.append(f"| {g} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
    if alerts:
        n, w, l, s, wr, pnl = _stats(alerts)
        lines.append(f"| C (alert only) | {n} | {w} | {l} | {s} | {wr}% | (${pnl} if traded) |")
    if d_skips:
        n, w, l, s, wr, pnl = _stats(d_skips)
        lines.append(f"| D (filtered) | {n} | {w} | {l} | {s} | {wr}% | (${pnl} if traded) |")
    lines.append("")

    lines += ["### By Setup", "| Setup | Signals | W | L | Scratch | Win rate | P&L |",
              "|-------|---------|---|---|---------|----------|-----|"]
    for st in sorted({t.signal_type for t in fired}):
        stt = [t for t in fired if t.signal_type == st]
        n, w, l, s, wr, pnl = _stats(stt)
        lines.append(f"| {st} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
    lines.append("")

    lines += ["### By Symbol", "| Symbol | Signals | W | L | Scratch | Win rate | P&L |",
              "|--------|---------|---|---|---------|----------|-----|"]
    for sym in sorted({t.symbol for t in fired}):
        st_ = [t for t in fired if t.symbol == sym]
        n, w, l, s, wr, pnl = _stats(st_)
        lines.append(f"| {sym} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
    lines.append("")

    # Per entry-hour (2026-07-11): YouTube stat says 75% of Scarface trades
    # cluster ~10:00 AM — test our own hour-by-hour win rate. Entry cutoff is
    # 11:00, so every fired trade falls in one of these three 30-min buckets.
    def _hour_bucket(ts: str) -> Optional[str]:
        hhmm = ts[:5]  # "HH:MM"
        if "09:30" <= hhmm < "10:00":
            return "09:30-10:00"
        if "10:00" <= hhmm < "10:30":
            return "10:00-10:30"
        if "10:30" <= hhmm < "11:00":
            return "10:30-11:00"
        return None
    lines += ["### By Entry Hour", "| Hour | Signals | W | L | Scratch | Win rate | P&L |",
              "|------|---------|---|---|---------|----------|-----|"]
    for bucket in ["09:30-10:00", "10:00-10:30", "10:30-11:00"]:
        bt = [t for t in fired if _hour_bucket(t.entry_time) == bucket]
        if bt:
            n, w, l, s, wr, pnl = _stats(bt)
            lines.append(f"| {bucket} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
    lines.append("")

    # Austin 2026-07-10: clean first-break vs late/dirty-level B&R A/B
    br = [t for t in fired if t.signal_type == "break_and_retest"]
    clean = [t for t in br if "[clean]" in t.reason]
    late = [t for t in br if "[late]" in t.reason]
    if clean or late:
        lines += ["### B&R: clean first break vs late (level broken earlier)",
                  "| Bucket | Signals | W | L | Scratch | Win rate | P&L |",
                  "|--------|---------|---|---|---------|----------|-----|"]
        for name, ts in (("clean", clean), ("late", late)):
            if ts:
                n, w, l, s, wr, pnl = _stats(ts)
                lines.append(f"| {name} | {n} | {w} | {l} | {s} | {wr}% | ${pnl} |")
        lines.append("")

    # Rule 6: Breakeven Scale Analysis (when RULE6_ENABLED, show BE-scale stats)
    scaled = [t for t in fired if t.be_taken]
    if scaled:
        be_hit = len(scaled)
        be_then_win = sum(1 for t in scaled if t.outcome == "win")
        be_then_loss = sum(1 for t in scaled if t.outcome == "loss")
        be_then_scr = sum(1 for t in scaled if t.outcome == "scratch")
        be_pnl = sum(t.pnl for t in scaled)
        no_be = [t for t in fired if not t.be_taken]
        no_be_decided = [t for t in no_be if t.outcome in ("win", "loss")]
        no_be_wr = round(sum(1 for t in no_be if t.outcome == "win") / max(len(no_be_decided), 1) * 100, 1)
        be_decided = [t for t in scaled if t.outcome in ("win", "loss")]
        be_wr = round(be_then_win / max(be_then_win + be_then_loss, 1) * 100, 1)
        lines += ["### Rule 6: Breakeven Scale Analysis",
                  f"| Metric | Value |",
                  f"|--------|-------|",
                  f"| Trades that hit BE scale | {be_hit}/{len(fired)} ({round(be_hit/max(len(fired),1)*100)}%) |",
                  f"| BE scaled -> win | {be_then_win} |",
                  f"| BE scaled -> loss (stopped at breakeven) | {be_then_loss} |",
                  f"| BE scaled -> scratch | {be_then_scr} |",
                  f"| P&L from BE-scaled trades | ${be_pnl} |",
                  f"| Win rate (BE scaled) | {be_wr}% |",
                  f"| Win rate (no BE scale) | {no_be_wr}% |",
                  f"| Scaling improved returns | {'YES' if be_wr >= no_be_wr else 'NO'} |",
                  ""]

    lines += ["## By Day", "| Day | Signals | Wins | Losses | Scratch | P&L |",
              "|-----|---------|------|--------|---------|-----|"]
    for d in days:
        dt = [t for t in fired if t.day == d]
        n, w, l, s, wr, pnl = _stats(dt)
        lines.append(f"| {d} | {n} | {w} | {l} | {s} | ${pnl} |")
    lines.append("")

    r84 = [t for t in all_trades if t.signal_type == "reentry_84_rule"]
    n, w, l, s, wr, pnl = _stats([t for t in r84 if t.counted])
    lines += ["## 84% Rule Analysis",
              f"- Total triggers (incl. filtered): {len(r84)}",
              f"- Fired re-entry signals: {n}",
              f"- Win rate on re-entry: {wr}% | P&L ${pnl}",
              ""]

    lines += ["## Signal Log", "| Day | Time | Sym | Setup | Dir | Grade | Status | Entry | Stop | Outcome | P&L |",
              "|-----|------|-----|-------|-----|-------|--------|-------|------|---------|-----|"]
    for t in sorted(all_trades, key=lambda t: (t.day, t.entry_time)):
        lines.append(f"| {t.day} | {t.entry_time} | {t.symbol} | {t.signal_type} | {t.direction} "
                     f"| {t.grade} | {t.status} | {t.entry:.2f} | {t.stop:.2f} | {t.outcome} "
                     f"| {'$' + format(t.pnl, '.0f') if t.counted else '-'} |")
    lines.append("")

    lines += ["## Findings & Recommendations"] + [f"- {n_}" for n_ in notes] + [""]
    text = "\n".join(lines)
    REPORT_PATH.write_text(text, encoding="utf-8")
    return text


def build_notes(all_trades: List[SimTrade]) -> List[str]:
    notes = []
    fired = [t for t in all_trades if t.counted]

    def wr(ts):
        d = [t for t in ts if t.outcome in ("win", "loss")]
        return (sum(1 for t in d if t.outcome == "win") / len(d) * 100) if d else None

    top = wr([t for t in fired if t.grade in ("A+", "A")])
    low = wr([t for t in fired if t.grade in ("B", "C")])
    if top is not None and low is not None:
        verdict = "KEEP grading" if top >= low else "grading NOT predictive this week - review PA grade criteria"
        notes.append(f"A+/A win rate {top:.0f}% vs B/C {low:.0f}% -> {verdict}")

    d_wr = wr([t for t in all_trades if t.status == "skipped_d"])
    if d_wr is not None:
        notes.append(f"D-grade filter: filtered signals would have won {d_wr:.0f}% -> "
                     + ("filter justified (<50%)" if d_wr < 50 else "filter may be cutting winners, re-examine"))

    r84 = [t for t in all_trades if t.signal_type == "reentry_84_rule"]
    if r84:
        r = wr([t for t in r84 if t.counted])
        rtxt = f"{r:.0f}%" if r is not None else "n/a"
        notes.append(f"84% rule (Lesson 6 canonical 2026-07-06: solid B&R stop-out arms one "
                     f"re-entry on the reclaim close, ORIGINAL stop + target): "
                     f"{len(r84)} triggers, fired win rate {rtxt}.")
    notes.append("84% live wiring: armed per-symbol off paper stop-outs in live_scanner "
                 "(2026-07-05). Requires --paper mode; signal-only runs have no stop-out feedback.")

    by_setup = defaultdict(list)
    for t in fired:
        by_setup[t.signal_type].append(t)
    ranked = [(st, wr(ts)) for st, ts in by_setup.items() if wr(ts) is not None]
    if ranked:
        ranked.sort(key=lambda x: x[1], reverse=True)
        notes.append(f"Best setup: {ranked[0][0]} ({ranked[0][1]:.0f}%) | worst: {ranked[-1][0]} ({ranked[-1][1]:.0f}%)")

    alerts = [t for t in all_trades if t.is_alert]
    a_wr = wr(alerts)
    if a_wr is not None:
        notes.append(f"C-grade alerts ({len(alerts)}, alert-only per SPEC2) would have won {a_wr:.0f}% - "
                     + ("similar to traded grades; alert-only demotion costs little." if a_wr < 45
                        else "outperforming; consider trading C at reduced size."))

    scr = sum(1 for t in fired if t.outcome == "scratch")
    if fired and scr / len(fired) > 0.4:
        notes.append(f"{scr}/{len(fired)} trades never resolved by EOD - 2R target may be too far for 1-min setups; test 1.5R")
    return notes


def _load_news_days() -> set:
    """Load news_days.json -> set of date strings (empty on missing/error)."""
    import json
    try:
        nd = json.loads((Path(__file__).parent / "news_days.json").read_text())
        return set(nd.get("news_days", []))
    except (OSError, ValueError):
        return set()


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Backtest OMEN signals over the last trading week.")
    ap.add_argument("dates", nargs="*",
                    help="explicit dates YYYY-MM-DD (default: last week)")
    ap.add_argument("--days", type=int, default=None,
                    help="lookback days (e.g. --days 30; max 29)")
    ap.add_argument("--entry-cutoff", default=None, metavar="HH:MM",
                    help="override entry cutoff time (default 11:00)")
    ap.add_argument("--skip-news", action="store_true",
                    help="exclude dates listed in news_days.json")
    args = ap.parse_args()

    # Override ENTRY_CUTOFF before the day loop (module-level global read by
    # simulate_day). Spec: module-level assignment before the loop is fine.
    global ENTRY_CUTOFF
    if args.entry_cutoff:
        ENTRY_CUTOFF = f"{args.entry_cutoff}:00"

    news_days = _load_news_days() if args.skip_news else set()

    fetch_days = 8
    if args.days is not None:
        fetch_days = min(args.days, 29)
        target_days = None
        week_start = (date.today() - timedelta(days=fetch_days)).isoformat()
        week_end = (date.today() - timedelta(days=1)).isoformat()
    elif args.dates:
        target_days = args.dates
        week_start = week_end = None  # explicit dates only
    else:
        target_days = None  # last complete trading week (Mon..Fri of most recent Friday)
        today = date.today()
        last_friday = today - timedelta(days=(today.weekday() - 4) % 7 or 7)
        week_start = (last_friday - timedelta(days=4)).isoformat()
        week_end = last_friday.isoformat()

    all_trades: List[SimTrade] = []
    chart_records: List[dict] = []
    seen_days = set()

    for sym in SYMBOLS:
        try:
            data = fetch_week(sym, days=fetch_days)
        except Exception as e:
            print(f"[{sym}] fetch failed: {e}")
            continue
        day_keys = sorted(data["days"].keys())
        use = [d for d in day_keys
               if (target_days is None and week_start <= d <= week_end)
               or (target_days and d in target_days)]
        if news_days:
            use = [d for d in use if d not in news_days]
        prev_day = None
        for d in day_keys:  # iterate all so prev_day PDH/PDL is right
            candles = data["days"][d]
            if d in use and len(candles) >= 30:
                if prev_day:
                    pc = data["days"][prev_day]
                    pdh, pdl = max(c.high for c in pc), min(c.low for c in pc)
                    pdo, pdc = pc[0].open, pc[-1].close
                else:
                    pdh = pdl = pdo = pdc = None
                bias = htf_bias_for(data["hourly"], d)
                pmh, pml = data.get("premkt", {}).get(d, (None, None))
                trades = simulate_day(sym, d, candles, pdh, pdl, bias, pmh, pml, pdo, pdc)
                all_trades.extend(trades)
                orh = max(c.high for c in candles[:5])
                orl = min(c.low for c in candles[:5])
                levels = {k: v for k, v in [("PDH", pdh), ("PDL", pdl), ("PMH", pmh),
                                            ("PML", pml), ("ORH", orh), ("ORL", orl)]
                          if v is not None}
                for t in trades:
                    if t.counted or t.is_alert:
                        lo, hi = max(0, t.entry_idx - 25), min(len(candles), t.exit_idx + 11)
                        chart_records.append({
                            "symbol": t.symbol, "day": t.day, "setup": t.signal_type,
                            "direction": t.direction, "grade": t.grade,
                            "alert_only": t.is_alert, "outcome": t.outcome,
                            "entry": t.entry, "stop": t.stop, "target": t.target,
                            "exit_price": t.exit_price, "pnl": t.pnl,
                            "entry_i": t.entry_idx - lo, "exit_i": t.exit_idx - lo,
                            "reason": t.reason, "levels": levels,
                            "candles": [{"t": c.timestamp[:5], "o": c.open, "h": c.high,
                                         "l": c.low, "c": c.close} for c in candles[lo:hi]],
                        })
                seen_days.add(d)
                print(f"[{sym}] {d}: {len(candles)} bars, {len(trades)} signals "
                      f"({sum(1 for t in trades if t.counted)} fired)")
            prev_day = d

    days = sorted(seen_days)
    notes = build_notes(all_trades)
    write_report(all_trades, days, notes)
    import json
    charts_path = REPORT_PATH.with_name("backtest_charts.json")
    charts_path.write_text(json.dumps(chart_records), encoding="utf-8")
    print(f"Charts data -> {charts_path} ({len(chart_records)} trades)")
    print(f"\nReport -> {REPORT_PATH}")
    for n_ in notes:
        print(f"  * {n_}")


if __name__ == "__main__":
    main()
