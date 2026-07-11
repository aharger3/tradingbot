"""SPEC17 - Backtest OMEN signals over the last trading week.

Walk-forward: replay each session bar-by-bar through SignalRunner.detect_signals,
capture every signal (fired + D-grade/tight-stop skips), simulate outcomes
(2R target vs stop), and write backtest_report.md.

Data: yfinance 1-min bars (free tier covers ~7 days back). P&L assumes fixed
$1000 risk per trade: win = +$2000 (2R), loss = -$1000, scratch = R-multiple x $1000.

Usage: python backtest_week.py [YYYY-MM-DD ...]   (default: last week's sessions)
"""

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

# Austin's watchlist 2026-07-06. Core = Scarface/JW's stocks + SPY/QQQ (trend
# reference, rarely traded). Experimental = Austin's adds to evaluate per-stock.
CORE_SYMBOLS = ["TSLA", "NVDA", "AAPL", "AMD", "META",
                "GOOGL", "AMZN", "MSFT", "PLTR", "SPY", "QQQ"]
EXPERIMENTAL_SYMBOLS = ["SOFI", "ORCL", "COIN", "HOOD", "IREN", "INTC", "SMCI"]
SYMBOLS = CORE_SYMBOLS + EXPERIMENTAL_SYMBOLS
RISK_DOLLARS = 1000.0
DEDUPE_BARS = 30  # same setup re-firing within 30 min = same trade idea
REPORT_PATH = Path(__file__).parent / "backtest_report.md"

# ---- Rule 6: Position Management (Scarface: scale 50% at HOD/breakeven) ----
# Austin 2026-07-10: "Mgmt: scale HOD / breakeven at post-entry red OB."
# When price hits entry + 1R (calls) / entry - 1R (puts), close 50% at breakeven,
# move runner stop to entry, let runner ride to 2R. Improves R:R by locking partial
# profit and reducing max-loss frequency (runner is free after breakeven).
RULE6_ENABLED = False      # toggle for backtest comparison
RULE6_SCALE_PCT = 0.5      # fraction of position closed at breakeven
RULE6_BE_MULT = 1.0        # breakeven level = entry +- 1R x this multiplier



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
                 pmh: Optional[float] = None, pml: Optional[float] = None) -> List[SimTrade]:
    runner = BacktestRunner(symbol)
    runner.pdh, runner.pdl, runner.htf_bias = pdh, pdl, bias
    runner.pmh, runner.pml = pmh, pml

    trades: List[SimTrade] = []
    open_trades: List[SimTrade] = []
    seen = {}  # dedupe key -> last bar index it appeared

    for i in range(5, len(candles)):
        c = candles[i]

        # 1. update open sim positions against this bar
        for t in list(open_trades):
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
            key = (sig["signal_type"].value, sig["direction"], round(sig["stop"], 2))
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

            t = SimTrade(symbol=symbol, day=day_iso,
                         signal_type=sig["signal_type"].value,
                         direction=sig["direction"], grade=sig["grade"],
                         status=sig["status"], entry_time=c.timestamp,
                         entry=sig["entry"], stop=sig["stop"], target=target,
                         reason=sig["reason"], entry_idx=i, exit_idx=len(candles) - 1,
                         be_level=be_level)
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


def main():
    fetch_days = 8
    if "--days" in sys.argv:  # e.g. --days 30: backtest everything yfinance still has
        fetch_days = min(int(sys.argv[sys.argv.index("--days") + 1]), 29)
        target_days = None
        week_start = (date.today() - timedelta(days=fetch_days)).isoformat()
        week_end = (date.today() - timedelta(days=1)).isoformat()
    elif len(sys.argv) > 1:
        target_days = sys.argv[1:]
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
        prev_day = None
        for d in day_keys:  # iterate all so prev_day PDH/PDL is right
            candles = data["days"][d]
            if d in use and len(candles) >= 30:
                if prev_day:
                    pc = data["days"][prev_day]
                    pdh, pdl = max(c.high for c in pc), min(c.low for c in pc)
                else:
                    pdh = pdl = None
                bias = htf_bias_for(data["hourly"], d)
                pmh, pml = data.get("premkt", {}).get(d, (None, None))
                trades = simulate_day(sym, d, candles, pdh, pdl, bias, pmh, pml)
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
