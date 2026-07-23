"""Live scanner: poll TSLA + NVDA every 1 min during 9:30-11:00 ET, post Discord signals.

Usage:
    python3 live_scanner.py                       # production loop
    python3 live_scanner.py --once                # single scan now (testing)
    python3 live_scanner.py --symbols TSLA        # custom watchlist
    python3 live_scanner.py --window 09:30-11:00  # custom hours (ET)
    python3 live_scanner.py --paper               # paper-trade sim (logs to journal/paper-trades.jsonl)
"""

import os
import json
import socket
import sys
import time
import argparse

# 2026-07-10: a stalled yfinance read hung the 10:59 scan for 26 min until the
# schtask 2h limit killed the process — archive_1m never ran. Hard-cap every
# socket so a dead feed raises instead of hanging the scan loop.
socket.setdefaulttimeout(30)
from datetime import datetime, time as dtime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Optional, Set, Tuple

# Force UTF-8 stdout/stderr so emoji in signal output (📝🚀📕📗✓✗) don't crash
# with UnicodeEncodeError when run under Windows/PowerShell (cp1252 pipes).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from signal_runner import _load_env_file
_load_env_file(Path(__file__).parent / ".env")

from signal_runner import SignalRunner
from tastytrade_feed import TastytradeFeed
from signal_tracker import log_signal
from regime_detector import (
    RegimeDetector, RegimeConfig,
    MODE_SMA, ACTION_STOP, ACTION_STOP_LONG, ACTION_STOP_SHORT,
    ACTION_NORMAL,
)
from market_data import fetch_spy_daily_closes


# A2 2026-07-13 (unified_backtest_synthesis §8.1): SMCI/SPY/MSTR/RIVN removed
# (−$22.1k/12mo combined; SMCI worst symbol in book at −$12.4k, SPY 0-for-5).
DEFAULT_SYMBOLS = [
    "TSLA", "NVDA", "AAPL", "AMD", "META",
    "GOOGL", "AMZN", "MSFT", "PLTR", "QQQ",
    "SOFI", "ORCL", "COIN", "HOOD", "IREN", "INTC",
    # 2026-07-11 Austin: expand to ~200k+ options-volume names (cleaner fills)
    "NFLX", "AVGO", "MU", "UBER", "BABA", "CRM",
    "TSM", "MARA",
]
DEFAULT_WINDOW = "09:30-11:00"

# OPUS-SPEC #5: Scarface session stop (2026-07-12)
# fable_rules.yaml / strategy-scarface-trades.md: stop after 1 win ("1 win /
# 2 attempts"). Prior: session halted only on 2 consecutive losses or max
# trades (config max_trades_per_day=3, consecutive_loss_halt=2). Change: first
# recorded win also ends the day. Win feedback exists only in --paper mode
# (paper.mark -> session.record_win), so signal-only runs are unaffected.
# config.yaml stop_after_win mirrors this; env STOP_AFTER_WIN=0 disables.
# C10 verdict 2026-07-13: default OFF. B2 audit found stop-after-win UNSOURCED
# in all 5 rulebooks (36 extraction groups); C10 sweep measured it costing the
# v2 tier $18k/yr (156tr 50.6%W $81k -> 132tr 49.2%W $63k). STOP_AFTER_WIN=1
# re-enables.
STOP_AFTER_WIN = os.getenv("STOP_AFTER_WIN", "0") == "1"

# A2 2026-07-13 (synthesis §8.2 + task queue): entry cutoff 10:30 — the
# 10:30-11:00 tail is 32.1%W / −$8,303 per 12mo. Scan window stays 09:30-11:00
# so open paper positions keep marking to stop/target; only NEW entries stop.
# Options book evidence only — futures mode unaffected. ENTRY_CUTOFF= to move,
# empty string to disable.
# C10 verdict 2026-07-13: reverted 10:30 -> 11:00 (rulebook window). The 10:30
# cutoff was a full-pop lever; at the v2 tier it costs $7k/yr (A4 showed the
# same direction on the v1 tier). 09:30-11:00 stands.
ENTRY_CUTOFF = os.getenv("ENTRY_CUTOFF", "11:00")

# A2: skip-news ON — news days run 30.6%W vs 37.2% clean (12mo). Was
# warn-only; now blocks new entries all day (marking continues).
# SKIP_NEWS=0 reverts to warn-only.
SKIP_NEWS = os.getenv("SKIP_NEWS", "1") == "1"
NEWS_HALT = {"active": False}  # set at startup from news_days.json

POLL_INTERVAL_SECONDS = 60

OMEN_LOGO = r"""
   ____  __  ___ ______ _   __
  / __ \/  |/  // ____// | / /
 / / / / /|_/ // __/  /  |/ /
/ /_/ / /  / // /___ / /|  /
\____/_/  /_//_____//_/ |_/   signal engine
"""


def now_et() -> datetime:
    """Current time in US Eastern, DST-aware."""
    return datetime.now(ZoneInfo("America/New_York"))


def parse_window(spec: str) -> Tuple[dtime, dtime]:
    """'09:30-11:00' -> (time(9,30), time(11,0))"""
    start_s, end_s = spec.split("-")
    sh, sm = map(int, start_s.split(":"))
    eh, em = map(int, end_s.split(":"))
    return dtime(sh, sm), dtime(eh, em)


def in_window(now: datetime, start: dtime, end: dtime) -> bool:
    t = now.time()
    return start <= t <= end


# ---- yfinance fallback (Tastytrade device-challenge outage 2026-07-06) ----
# ~1 min delayed; fine for paper. Used whenever the Tastytrade call throws.

def _yf_history(symbol: str, **kw):
    import yfinance as yf
    df = yf.Ticker(symbol).history(**kw)
    return df.tz_convert("America/New_York") if df is not None and not df.empty else None


def _yf_recent_bars(symbol: str, lookback_minutes: int = 60):
    from omen_bot import Candle
    df = _yf_history(symbol, period="1d", interval="1m", prepost=False)
    if df is None:
        return []
    df = df.tail(lookback_minutes)
    return [Candle(timestamp=ts.strftime("%H:%M:%S"), open=float(r.Open),
                   high=float(r.High), low=float(r.Low), close=float(r.Close),
                   volume=int(r.Volume or 0))
            for ts, r in zip(df.index, df.itertuples())]


def _yf_daily_context(symbol: str):
    """(pdh, pdl, bias, pmh, pml, pdo, pdc) — bias None (PA-only grading on fallback)."""
    pdh = pdl = pmh = pml = pdo = pdc = None
    d = _yf_history(symbol, period="5d", interval="1d")
    if d is not None and len(d) >= 2:
        pdh, pdl = float(d.High.iloc[-2]), float(d.Low.iloc[-2])
        pdo, pdc = float(d.Open.iloc[-2]), float(d.Close.iloc[-2])
    m = _yf_history(symbol, period="1d", interval="1m", prepost=True)
    if m is not None:
        pm = m[m.index.time < dtime(9, 30)]
        if not pm.empty:
            pmh, pml = float(pm.High.max()), float(pm.Low.min())
    return pdh, pdl, None, pmh, pml, pdo, pdc


# symbol -> {"date", "pdh", "pdl", "bias", "bias_at"} — PDH/PDL cached per day,
# HTF bias refreshed every 15 min (1h trend moves slowly; saves a ws call/scan)
_daily_ctx: dict = {}


def get_daily_context(tasty_feed, symbol: str):
    """Returns (pdh, pdl, htf_bias, pmh, pml, pd_open, pd_close); any element
    None when unavailable."""
    import time as _time
    today = __import__("datetime").date.today().isoformat()
    ctx = _daily_ctx.get(symbol)
    if ctx is None or ctx["date"] != today:
        try:
            levels = tasty_feed.fetch_daily_levels(symbol)
        except Exception:
            pdh, pdl, bias, pmh, pml, pdo, pdc = _yf_daily_context(symbol)
            ctx = {"date": today, "pdh": pdh, "pdl": pdl, "pmh": pmh,
                   "pml": pml, "pdo": pdo, "pdc": pdc,
                   "bias": bias, "bias_at": _time.time()}
            _daily_ctx[symbol] = ctx
            return pdh, pdl, bias, pmh, pml, pdo, pdc
        pm = None
        if hasattr(tasty_feed, "fetch_premarket_levels"):  # FuturesFeed lacks it
            try:
                pm = tasty_feed.fetch_premarket_levels(symbol)
            except Exception:
                pm = None
        ctx = {"date": today, "pdh": levels[0] if levels else None,
               "pdl": levels[1] if levels else None,
               "pdo": levels[2] if levels and len(levels) > 2 else None,
               "pdc": levels[3] if levels and len(levels) > 3 else None,
               "pmh": pm[0] if pm else None, "pml": pm[1] if pm else None,
               "bias": None, "bias_at": 0.0}
        _daily_ctx[symbol] = ctx
    if _time.time() - ctx["bias_at"] > 900:
        try:
            ctx["bias"] = tasty_feed.fetch_htf_bias(symbol)
        except Exception:
            ctx["bias"] = None
        ctx["bias_at"] = _time.time()
    return (ctx["pdh"], ctx["pdl"], ctx["bias"], ctx["pmh"], ctx["pml"],
            ctx.get("pdo"), ctx.get("pdc"))


# F4 Rule 4 (qqq-alignment-rules.md) — QQQ's first RTH close through a PD/PM
# key level, in each direction. Ported from backtest_12mo.qqq_level_breaks
# (offline uses polygon_feed; live reuses the same yfinance/tasty context).
# Once a direction's break time is found it stays locked for the session, so
# a level touched early still counts after price pulls back. runner.qqq_breaks
# reads {"up","dn"} → _qqq_aligned tag ([qqqA]/[qqqX]) + S+1; None = no QQQ data.
_qqq_state: dict = {"date": None, "up": None, "dn": None}


def compute_qqq_breaks(tasty_feed):
    """{"up": first RTH close above QQQ PDH/PMH, "dn": first below PDL/PML} as
    HH:MM:SS (None until it breaks). Returns None only when QQQ data is missing."""
    today = now_et().date().isoformat()
    if _qqq_state["date"] != today:
        _qqq_state.update(date=today, up=None, dn=None)
    if _qqq_state["up"] and _qqq_state["dn"]:
        return {"up": _qqq_state["up"], "dn": _qqq_state["dn"]}  # both locked, skip fetch

    pdh, pdl, _bias, pmh, pml, _o, _c = get_daily_context(tasty_feed, "QQQ")
    ups = [l for l in (pdh, pmh) if l is not None]
    dns = [l for l in (pdl, pml) if l is not None]
    if not ups and not dns:
        return None  # no QQQ levels → S-input simply absent (same as offline no-data)

    # Full RTH day so far — 60-min lookback misses an early break, so size the
    # window to minutes since 09:30 (+5 buffer).
    open_et = now_et().replace(hour=9, minute=30, second=0, microsecond=0)
    mins = max(1, int((now_et() - open_et).total_seconds() // 60) + 5)
    try:
        bars = tasty_feed.fetch_recent_bars("QQQ", lookback_minutes=mins)
    except Exception:
        bars = []
    if not bars:
        try:
            bars = _yf_recent_bars("QQQ", lookback_minutes=mins)
        except Exception:
            return None
    rth = [c for c in bars if c.timestamp >= "09:30:00"]
    if _qqq_state["up"] is None and ups:
        _qqq_state["up"] = next((c.timestamp for c in rth if any(c.close > l for l in ups)), None)
    if _qqq_state["dn"] is None and dns:
        _qqq_state["dn"] = next((c.timestamp for c in rth if any(c.close < l for l in dns)), None)
    return {"up": _qqq_state["up"], "dn": _qqq_state["dn"]}


SCANNER_STATUS_PATH = Path(__file__).parent / "journal" / "scanner_status.json"


def _write_scanner_status(symbols, signals_today, session, regime_action,
                           last_error=None, posted=0, failed=0, qqq_breaks=None,
                           ntfy_posted=0, ntfy_failed=0):
    """Atomically write journal/scanner_status.json (temp + os.replace).

    Dashboard reads this file later — no UI work here, file only.
    """
    status = {
        "timestamp": now_et().isoformat(),
        "symbols_scanned": list(symbols),
        "signals_fired_today": signals_today,
        "session_halt": {
            "halted": session.day_ended(),
            "consecutive_losses": session.consecutive_losses,
            "signals_today": session.signals_today,
            "max_trades": session.max_signals_per_day,
        },
        "regime_state": regime_action,
        "qqq_state": qqq_breaks,  # F4 Rule 4: {"up","dn"} break times or None
        "last_error": last_error,
        "webhooks": {"posted": posted, "failed": failed},
        "ntfy": {"posted": ntfy_posted, "failed": ntfy_failed},
    }
    SCANNER_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SCANNER_STATUS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(SCANNER_STATUS_PATH))


def scan_once(
    runner: SignalRunner,
    tasty_feed: TastytradeFeed,
    symbols: List[str],
    seen_signal_keys: Set[str],
    paper=None,
    max_trades: int = 3,
    max_consecutive_losses: int = 2,
    regime_detector: RegimeDetector = None,
) -> int:
    """Scan each symbol once, post novel signals, return count fired."""
    fired = 0
    # Delivery counters (Task 1): reset per cycle, logged at end so scanner-*.log
    # shows Discord health even on quiet days.
    discord = getattr(runner, "discord", None)
    if discord is not None:
        discord.posted = discord.failed = 0
    ntfy = getattr(runner, "ntfy", None)
    if ntfy is not None:
        ntfy.posted = ntfy.failed = 0
    # symbol -> (entry, direction, target) of stopped-out trade awaiting one 84%
    # re-entry (needs --paper for stop-out feedback; signal-only mode has none)
    armed_84 = getattr(runner, "armed_84", None)
    if armed_84 is None:
        armed_84 = runner.armed_84 = {}

    # Check daily limits (OPUS-SPEC #5: a win also ends the day)
    if runner.session.day_ended() or (STOP_AFTER_WIN and runner.session.consecutive_wins >= 1):
        print(f"  Session halted: {runner.session.signals_today}/{max_trades} signals, "
              f"{runner.session.consecutive_losses}/{max_consecutive_losses} consecutive losses, "
              f"{runner.session.consecutive_wins} wins (stop_after_win={'on' if STOP_AFTER_WIN else 'off'})")
        _write_scanner_status(symbols, runner.session.signals_today, runner.session,
                              ACTION_NORMAL, last_error="session halted",
                              qqq_breaks=getattr(runner, "qqq_breaks", None))
        return 0

    # Regime filter: check today's market regime once per scan cycle.
    # SMA Directional (5%) stops short/put entries in melt-ups and
    # stops long/call entries in melt-downs — the 24mo winner.
    today = __import__("datetime").date.today().isoformat()
    regime_action = ACTION_NORMAL
    if regime_detector is not None:
        _, regime_action = regime_detector.get_action(today)
        if regime_action in (ACTION_STOP, ACTION_STOP_LONG, ACTION_STOP_SHORT):
            msg = f"Regime filter: {regime_action} — "
            if regime_action == ACTION_STOP:
                msg += "all trades halted (melt-up AND melt-down detected)"
            elif regime_action == ACTION_STOP_LONG:
                msg += "CALL trades blocked (melt-up regime)"
            elif regime_action == ACTION_STOP_SHORT:
                msg += "PUT trades blocked (melt-down regime)"
            print(f"  {msg}")

    # A2: entry gates — paper marking continues below, only NEW entries stop.
    entries_ok = True
    if NEWS_HALT["active"]:
        entries_ok = False
        print("  News-day halt (skip-news ON) — marking only, no new entries")
    elif ENTRY_CUTOFF and not getattr(runner, "futures_mode", False) \
            and now_et().strftime("%H:%M") >= ENTRY_CUTOFF:
        entries_ok = False
        print(f"  Entry cutoff {ENTRY_CUTOFF} passed — marking only, no new entries")

    # F4 Rule 4: QQQ key-level break state, once per cycle, shared across the
    # watchlist (skip in futures mode — QQQ context irrelevant there).
    if not getattr(runner, "futures_mode", False):
        try:
            runner.qqq_breaks = compute_qqq_breaks(tasty_feed)
        except Exception as e:
            print(f"  QQQ break check failed: {e}")
            runner.qqq_breaks = None
        if runner.qqq_breaks:
            print(f"  QQQ breaks: up={runner.qqq_breaks['up']} dn={runner.qqq_breaks['dn']}")

    last_error = None
    for symbol in symbols:
        try:
            candles = tasty_feed.fetch_recent_bars(symbol, lookback_minutes=60)
        except Exception as e:
            print(f"[{symbol}] tasty fetch failed ({str(e)[:80]}), trying yfinance")
            try:
                candles = _yf_recent_bars(symbol)
            except Exception as e2:
                print(f"[{symbol}] yfinance fallback failed: {e2}")
                last_error = f"{symbol}: {str(e2)[:120]}"
                continue

        if len(candles) < 5:
            print(f"[{symbol}] only {len(candles)} bars, skipping")
            continue

        # Mark/close any open paper positions against this fresh candle first.
        if paper is not None:
            last = candles[-1]
            for ev in paper.mark(symbol, high=last.high, low=last.low, ts=last.timestamp):
                print(f"   📕 PAPER CLOSE {ev['symbol']} {ev['direction'].upper()} "
                      f"{ev['outcome'].upper()} P&L ${ev.get('pnl', ev.get('be_pnl', 0.0)):.2f}")
                if runner.post_to_ntfy and runner.ntfy:
                    runner.ntfy.post_paper_close(ev)
                if ev["outcome"] == "be_scale":
                    continue  # partial scale, position still open — no win/loss yet
                if ev["outcome"] == "stop":
                    runner.session.record_loss()
                    # Lesson 6 canonical (A/B 2026-07-06: B&R-only arm was the
                    # difference between -$2k and +$450 on 30d): solid B&R
                    # stop-out arms ONE re-entry at original stop + target
                    if ev.get("stock_entry") and ev.get("setup") == "break_and_retest":
                        armed_84[symbol] = (ev["stock_entry"], ev["direction"],
                                            ev.get("stock_target"), ev.get("stock_stop"))
                        print(f"   🔁 84% rule armed for {symbol} at ${ev['stock_entry']:.2f}")
                else:
                    runner.session.record_win()

        runner.candles = candles
        runner.symbol = symbol  # so detect_signals logs correct ticker
        try:
            (runner.pdh, runner.pdl, runner.htf_bias, runner.pmh, runner.pml,
             runner.pd_open, runner.pd_close) = get_daily_context(tasty_feed, symbol)
        except Exception as e:
            print(f"[{symbol}] daily context fetch failed: {e}")
            runner.pdh = runner.pdl = runner.htf_bias = runner.pmh = runner.pml = None
            runner.pd_open = runner.pd_close = None
        if runner.pdh:
            print(f"[{symbol}] PDH {runner.pdh:.2f} / PDL {runner.pdl:.2f} / HTF {runner.htf_bias or 'unknown'}")
        # 84% state is per-symbol; runner is shared across the watchlist
        armed = armed_84.get(symbol)
        (runner.session.entry_price, runner.session.entry_direction,
         runner.session.entry_target, runner.session.entry_stop) = \
            armed if armed else (None, None, None, None)
        signals = runner.detect_signals()
        if runner.session.entry_price is None:  # detector fired its one re-entry -> disarm
            armed_84.pop(symbol, None)

        # A2 entry gates (cutoff / news halt) drop signals same as regime STOP
        if not entries_ok:
            signals = []
        # Apply regime filter per signal (filter at signal level)
        if regime_action == ACTION_STOP:
            signals = []  # all trades halted
        elif regime_action == ACTION_STOP_LONG:
            signals = [s for s in signals if s.get("direction") != "call"]
        elif regime_action == ACTION_STOP_SHORT:
            signals = [s for s in signals if s.get("direction") != "put"]

        for sig in signals:
            if runner.session.day_ended():
                break
            key = f"{symbol}:{sig['signal_type'].value}:{sig['direction']}:{candles[-1].timestamp}"
            if key in seen_signal_keys:
                continue
            seen_signal_keys.add(key)
            sig["reason"] = f"[{symbol}] {sig['reason']}"
            executed = _emit_signal(runner, tasty_feed, symbol, candles[-1], sig, paper)
            fired += 1
            if executed:  # C-grade alerts don't count toward the daily trade cap
                runner.session.signals_today += 1

    if paper is not None:
        print("   " + paper.summary())
    if discord is not None:
        print(f"  Discord delivery: posted={discord.posted} failed={discord.failed}")
    if ntfy is not None:
        print(f"  ntfy delivery: posted={ntfy.posted} failed={ntfy.failed}")
    _write_scanner_status(symbols, runner.session.signals_today, runner.session,
                          regime_action, last_error=last_error,
                          posted=discord.posted if discord else 0,
                          failed=discord.failed if discord else 0,
                          qqq_breaks=getattr(runner, "qqq_breaks", None),
                          ntfy_posted=ntfy.posted if ntfy else 0,
                          ntfy_failed=ntfy.failed if ntfy else 0)
    return fired


def _emit_futures_signal(runner: SignalRunner, contract: str, candle, sig: dict) -> bool:
    """Futures mode (SPEC15): price-level stops, contract sizing, no premium.

    Same grade rules as options: C = alert-only, D filtered upstream.
    # ponytail: no paper-trade book for futures yet; add futures legs to PaperBook when needed
    """
    from options_sizer import build_futures_plan
    grade = sig.get("grade", "?")
    alert_only = grade == "C"
    direction = "long" if sig["direction"] == "call" else "short"
    try:
        plan = build_futures_plan(contract, direction, sig["entry"], sig["stop"], grade=grade)
    except ValueError as e:
        print(f"  futures sizing skip: {e}")
        return False
    if plan.contracts < 1:
        print(f"  futures sizing skip: 0 contracts at grade {grade}")
        return False

    signal_type_val = sig["signal_type"].value if hasattr(sig["signal_type"], "value") else str(sig["signal_type"])
    icon = "⚠" if alert_only else "🚀"
    print(f"{icon} OMEN FUTURES {signal_type_val.upper()} {direction.upper()}  Grade: {grade}")
    if alert_only:
        print("   C GRADE — ALERT ONLY, manual review (not auto-traded)")
    print(f"   {sig['reason']}")
    print(plan.format_discord())

    log_signal(
        symbol=contract, signal_type=signal_type_val, direction=direction,
        entry=sig["entry"], stop=sig["stop"], target=plan.target, grade=grade,
        reason=sig["reason"], stop_width_pct=sig.get("stop_width_pct", 0.0),
        quote_source="futures_yfinance", status="alert" if alert_only else "fired",
    )
    if runner.post_to_discord and runner.discord:
        ok = runner.discord.post_text(f"{icon} **OMEN** · Grade {grade}\n{sig['reason']}\n{plan.format_discord()}")
        print("   ✓ Posted" if ok else "   ✗ Discord post failed")
    return not alert_only


_last_alert: dict = {}  # (symbol, direction) -> minutes-since-midnight of last ding
ALERT_COOLDOWN_MIN = 20

# Two-tier (Austin 2026-07-07): quality over quantity, one trade and done.
# TRADE = first A/A+ of the day across ALL symbols, at or after 09:40 ET
# (30d sim 2026-07-07: 12tr 58% +$10.8k; first-B+-anytime was 20tr 25% -$6k —
# the 09:30-09:40 chop and B-grade spray are what governor must skip).
# 84% re-entry exempt while consecutive losses < 2. Everything else fired =
# WATCH, ding only, capped per day. Scanner restarts daily via schtask,
# so counters reset free.
WATCH_DAILY_CAP = 5
TRADE_FLOOR = "09:40"
_watch_dings = {"n": 0}


def _tier(runner: SignalRunner, sig: dict, grade: str, ts: str) -> str:
    s = runner.session
    if getattr(sig["signal_type"], "value", "") == "reentry_84_rule":
        return "TRADE" if s.consecutive_losses < 2 else "WATCH"
    if grade not in ("A+", "A") or ts[:5] < TRADE_FLOOR:
        return "WATCH"
    return "TRADE" if s.signals_today == 0 and s.consecutive_losses < 2 else "WATCH"


def _cooled_down(symbol: str, direction: str, ts: str) -> bool:
    """One ding per symbol+direction per 20 min — detector re-triggers every
    bar near a level (2026-07-06: GOOGL fired 4 alerts in 9 min)."""
    mins = int(ts[:2]) * 60 + int(ts[3:5])
    last = _last_alert.get((symbol, direction))
    if last is not None and mins - last < ALERT_COOLDOWN_MIN:
        return False
    _last_alert[(symbol, direction)] = mins
    return True


def _emit_signal(runner: SignalRunner, tasty_feed: TastytradeFeed, symbol: str, candle, sig: dict, paper=None) -> bool:
    """Build OptionsPlan (Tastytrade real-time premium, fallback delta estimate) and post.

    Returns True for TRADE-tier signals (counted against the daily governor,
    paper-traded); False for WATCH dings and skips."""
    from options_sizer import build_options_plan, GRADE_SIZE_PCT, DEFAULT_MAX_LOSS
    if sig["entry"] == sig["stop"]:
        return False
    if getattr(sig["signal_type"], "value", "") != "reentry_84_rule" and \
            not _cooled_down(symbol, sig["direction"], candle.timestamp):
        print(f"  {symbol} {sig['direction']} suppressed: cooldown ({ALERT_COOLDOWN_MIN}m)")
        return False
    if getattr(runner, "futures_mode", False):
        return _emit_futures_signal(runner, symbol, candle, sig)
    grade = sig.get("grade", "?")
    size_pct = GRADE_SIZE_PCT.get(grade, 0.6)
    # 84% re-entries run 2x size (Austin: double to recover first stop-out + profit)
    if getattr(sig["signal_type"], "value", "") == "reentry_84_rule":
        size_pct *= 2.0
    tier = _tier(runner, sig, grade, candle.timestamp)
    alert_only = tier != "TRADE"
    if alert_only:
        if _watch_dings["n"] >= WATCH_DAILY_CAP:
            print(f"  {symbol} {sig['direction']} WATCH suppressed: daily cap ({WATCH_DAILY_CAP})")
            return False
        _watch_dings["n"] += 1
    sig["reason"] = f"{tier} · {sig['reason']}"
    try:
        plan = build_options_plan(
            symbol=symbol,
            direction=sig["direction"],
            stock_entry=sig["entry"],
            stock_stop=sig["stop"],
            tasty_feed=tasty_feed,
            max_loss=DEFAULT_MAX_LOSS * size_pct,
        )
    except ValueError as e:
        print(f"  sizing skip: {e}")
        return False

    stop_level = sig.get("stop_level_name", "")
    stop_width = sig.get("stop_width_pct", 0.0)
    signal_type_val = sig["signal_type"].value if hasattr(sig["signal_type"], "value") else str(sig["signal_type"])

    tag = "[PAPER] " if paper is not None else ""
    icon = "🎯" if tier == "TRADE" else "👀"
    print(f"{icon} {tag}{tier} {signal_type_val.upper()} {sig['direction'].upper()}  Grade: {grade}  Stop: {stop_level} ({stop_width}%)")
    if alert_only:
        print("   WATCH — ding only, not traded")
    print(f"   {sig['reason']}")
    print(plan.format_discord())

    # Log signal
    log_signal(
        symbol=symbol,
        signal_type=signal_type_val,
        direction=sig["direction"],
        entry=sig["entry"],
        stop=sig["stop"],
        target=plan.stock_target if hasattr(plan, "stock_target") else 0,
        grade=grade,
        reason=sig["reason"],
        stop_width_pct=stop_width,
        quote_source=plan.quote_source if hasattr(plan, "quote_source") else "estimated",
        status="alert" if alert_only else "fired",
    )

    if paper is not None and not alert_only:
        pos = paper.open_from_plan(plan, ts=candle.timestamp, grade=grade,
                                   setup=signal_type_val)
        print(f"   📗 PAPER OPEN {pos.contracts}x {pos.symbol} ${pos.strike:g} "
              f"{pos.direction.upper()} @ ${pos.entry_premium:.2f}")
        if runner.post_to_ntfy and runner.ntfy:
            runner.ntfy.post_paper_open(pos)
    if runner.post_to_discord and runner.discord:
        ok = runner.discord.post_signal(sig["signal_type"], candle, sig["reason"], plan,
                                         grade=grade, stop_level_name=stop_level, stop_width_pct=stop_width)
        print("   ✓ Posted" if ok else "   ✗ Discord post failed")
    if runner.post_to_ntfy and runner.ntfy:
        ok = runner.ntfy.post_signal(sig["signal_type"], candle, sig["reason"], plan,
                                     grade=grade, stop_level_name=stop_level,
                                     stop_width_pct=stop_width, tier=tier)
        print("   ✓ ntfy" if ok else "   ✗ ntfy push failed")
    return not alert_only


def main():
    parser = argparse.ArgumentParser(description="Live Omen signal scanner")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help=f"Tickers to watch (default {DEFAULT_SYMBOLS})")
    parser.add_argument("--window", default=DEFAULT_WINDOW,
                        help="Trading window in ET HH:MM-HH:MM (default 09:30-11:00)")
    parser.add_argument("--once", action="store_true",
                        help="Run a single scan and exit (testing)")
    # Discord retired 2026-07-23 — ntfy is the alert channel. Discord is OFF by
    # default now; --discord opts back in. --no-discord kept as an accepted
    # no-op so old invocations don't error.
    parser.add_argument("--discord", action="store_true",
                        help="Opt back into Discord posting (retired; ntfy is the default channel)")
    parser.add_argument("--no-discord", action="store_true",
                        help="(deprecated no-op — Discord is already off by default)")
    parser.add_argument("--no-ntfy", action="store_true",
                        help="Skip ntfy push (ntfy is the primary channel — usually leave on)")
    parser.add_argument("--paper", action="store_true",
                        help="Paper-trade simulation: log fired signals + mark to stop/target in journal/paper-trades.jsonl")
    parser.add_argument("--futures", nargs="?", const="ES", default=None, metavar="CONTRACT",
                        help="Futures mode (SPEC15): trade ES/NQ/RTY via yfinance feed instead of stock options")
    args = parser.parse_args()

    print(OMEN_LOGO)
    start, end = parse_window(args.window)
    runner = SignalRunner(post_to_discord=args.discord,
                          post_to_ntfy=not args.no_ntfy)
    if args.futures:
        runner.futures_mode = True
        args.symbols = [args.futures.upper()]
        if args.window == DEFAULT_WINDOW:
            args.window = "09:30-16:00"  # main ES volume session
            start, end = parse_window(args.window)
    seen: Set[str] = set()
    max_trades = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
    max_losses = int(os.getenv("CONSECUTIVE_LOSS_HALT", "2"))
    runner.session.max_signals_per_day = max_trades

    # Feed: futures (yfinance) or Tastytrade (candles + real-time option quotes).
    tasty_feed = None
    if args.futures:
        from futures_feed import FuturesFeed
        tasty_feed = FuturesFeed()
        print(f"Futures mode: {args.symbols[0]}")
    else:
        try:
            tasty_feed = TastytradeFeed()
            tasty_feed.validate_credentials()
        except Exception as e:
            print(f"  Tastytrade init failed: {e}")

    if tasty_feed is None:
        print("No data feed available (Tastytrade init failed). Exiting.")
        sys.exit(1)

    paper = None
    if args.paper:
        from paper_trader import PaperBook
        paper = PaperBook()
        print(f"📝 Paper mode ON → {paper.ledger_path}")

    print(f"Scanner armed. Symbols: {args.symbols}  Window (ET): {args.window}")
    _ntfy_label = f"on → {runner.ntfy.topic}" if runner.post_to_ntfy and runner.ntfy else "off"
    print(f"   Channels: ntfy={_ntfy_label}  "
          f"Discord={'on' if runner.post_to_discord else 'off (retired)'}  "
          f"Paper={'on' if paper else 'off'}")
    # Startup ping so the user confirms push delivery before the first signal.
    if runner.post_to_ntfy and runner.ntfy:
        runner.ntfy.post_text(
            f"Omen armed · {len(args.symbols)} symbols · {args.window} ET"
            f"{' · PAPER' if paper else ''}",
            title="Omen scanner armed", tags="rocket", priority="low")

    # News-day warning (12mo: news days 30.6%W −$12k vs clean 37.2%W; tier
    # skipping them 44.8% vs 43.4%). Warn once at startup — Austin sizes
    # down or skips per Scarface red-folder rule.
    try:
        import json as _json
        _nd = _json.loads((Path(__file__).parent / "news_days.json").read_text())
        _today = now_et().date().isoformat()
        if _today in set(_nd.get("news_days", [])):
            kind = _nd.get("by_date", {}).get(_today, "red-folder")
            if SKIP_NEWS:
                NEWS_HALT["active"] = True
                msg = (f"⚠ NEWS DAY ({kind}) — skip-news ON: no new entries today "
                       f"(12mo: 30.6%W on these days). SKIP_NEWS=0 to override.")
            else:
                msg = (f"⚠ NEWS DAY ({kind}) — 12mo: 30.6%W on these days. "
                       f"Scarface rule: size down or skip.")
            print(msg)
            if runner.post_to_discord and runner.discord:
                runner.discord.post_text(msg)
            if runner.post_to_ntfy and runner.ntfy:
                runner.ntfy.post_text(msg, title="Omen · news day", tags="warning",
                                      priority="high")
    except (OSError, ValueError) as e:
        print(f"  news-day check skipped: {e}")

    # Regime filter: SMA Directional (5%) — 24mo best +30.6% over baseline
    print("Loading market data for regime filter...")
    try:
        spy_raw = fetch_spy_daily_closes(days_back=400)
        spy_dates = sorted(d for d in spy_raw)
        spy_closes = [spy_raw[d] for d in spy_dates if d in spy_raw]
        regime_cfg = RegimeConfig(mode=MODE_SMA, directional=True,
                                  melt_up_threshold=0.05, melt_down_threshold=-0.05)
        regime_det = RegimeDetector(regime_cfg)
        regime_det.feed_daily_closes(spy_dates, spy_closes)
        print(f"  Regime filter active: SMA Directional (5%) — {len(spy_dates)} days loaded")
    except Exception as e:
        print(f"  Regime filter init failed: {e} — running unfiltered")
        regime_det = None

    if args.once:
        print(f"Single scan @ {now_et().strftime('%H:%M:%S')} ET")
        fired = scan_once(runner, tasty_feed, args.symbols, seen, paper,
                            max_trades=max_trades, max_consecutive_losses=max_losses,
                            regime_detector=regime_det)
        print(f"Done. {fired} signals fired.")
        return

    while True:
        now = now_et()
        if now.weekday() >= 5:  # Sat=5, Sun=6
            print(f"Weekend ({now.strftime('%a')}), sleeping 1h")
            time.sleep(3600)
            continue

        if not in_window(now, start, end):
            # Sleep until next window open
            print(f"{now.strftime('%H:%M:%S')} ET outside window {args.window}, sleeping 60s")
            time.sleep(60)
            continue

        print(f"\n=== {now.strftime('%H:%M:%S')} ET scan ===")
        fired = scan_once(runner, tasty_feed, args.symbols, seen, paper,
                            max_trades=max_trades, max_consecutive_losses=max_losses,
                            regime_detector=regime_det)
        if fired == 0:
            print("  no new signals")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScanner stopped.")
        sys.exit(0)
