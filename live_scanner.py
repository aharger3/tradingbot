"""Live scanner: poll TSLA + NVDA every 1 min during 9:30-11:00 ET, post Discord signals.

Usage:
    python3 live_scanner.py                       # production loop
    python3 live_scanner.py --once                # single scan now (testing)
    python3 live_scanner.py --symbols TSLA        # custom watchlist
    python3 live_scanner.py --window 09:30-11:00  # custom hours (ET)
    python3 live_scanner.py --paper               # paper-trade sim (logs to journal/paper-trades.jsonl)
"""

import os

from omen_bot import his_grade   # engine working state -> Austin's ladder
import json
import socket
import sys
import time
import argparse

# ============================================================================
# LIVE / BACKTEST PARITY — read before trusting any $/day figure against a
# live signal, and before touching any flag in this file. Audited 2026-09-03
# against research/MASTER_SPEC.md and research/bt2y_trades_retest_on.json's
# own stamp (meta.stamp.flags). Every module this file imports for signal
# detection and sizing (SignalRunner, stop_rule, loss_halt, options_sizer) is
# SHARED code — live and backtest_week.py both call it, so a flag neither
# process overrides is identical in both by construction. Grep confirms this
# file sets exactly ONE such flag (`git grep -n "os.environ\[" live_scanner.py`
# / `os.environ.setdefault` — one hit, below). Everything past item 1 is a
# live-only construct layered on top, with no flag and no backtest analog.
#
# 1. ENABLE_SAC_LADDER — forced to "1" two lines down, live-process-only.
#    signal_runner.py:724 defaults it "0". research/bt2y_trades_retest_on.json
#    — the book every $/day figure in MASTER_SPEC.md is measured on — was
#    built at that default (backtest_2y.py never sets the var either); its
#    own stamp does not even list ENABLE_SAC_LADDER among meta.stamp.flags
#    (research/book_stamp.py's FLAG_SOURCES omits it), so the book cannot be
#    checked after the fact for which arm produced it.
#    Effect: live grades every signal through the eight-variable S/A/C/X
#    downgrade ladder (research/downgrade.py::score); the book grades through
#    the legacy _grade_pa A+/A/B/C/X ladder — a different classifier scoring
#    a different thing (MASTER_SPEC §2.4: the SAC ladder is 33.0% precise
#    against a 28.5% base rate, and one of its eight variables,
#    counter_trend_not_respected, is wrong-signed on 63.7% of the book).
#    STATUS: NOT changed here — the comment on the setdefault line below is
#    Austin's own: "Flipping it changes what trades, which is Austin's
#    call." BLOCKER, money impact folded into item 2.
#
# 2. The live TRADE gate (`_tier`, further down) fires on `sac_grade == "S"`
#    alone. There is no backtest flag for this — SignalRunner never filters
#    by grade on its own; every rig that turns fired signals into a dollar
#    figure (backtest_week.py, research/g*.py) takes every signal that clears
#    routing + min_risk_floor, and MASTER_SPEC's reporting layer then slices
#    that down to "the first size-gated candidate of the day" as a RESEARCH
#    SELECTION, not an engine gate. `_tier`'s S-only filter is a second,
#    live-only, narrower selection stacked on top of item 1's ladder.
#    MASTER_SPEC §0 / bug 3: 88 of 498 sessions have a size-gated `S`
#    (0.18 trades/day, $14/day laddered) against $101/day for taking the
#    first size-gated candidate of any grade. −$87/day.
#    STATUS: not changed — this is Austin's "fire 1-3 times a day" (THE LANE)
#    implemented literally as "S only"; whether that is the right
#    operationalization is exactly what THE LANE is still deriving. BLOCKER,
#    not a bug to silently revert.
#
# 3. `_tier`'s `reentry_84_rule` branch returns TRADE/WATCH off
#    `s.consecutive_losses` BEFORE the `sac_grade == "S"` check runs — an
#    armed 84% re-entry trades regardless of its own grade. signal_runner.py
#    has no such bypass: S_ELIGIBLE_SETUPS (signal_runner.py:1042) lists
#    REENTRY_84_RULE as an ordinary member of the graded pool — a re-entry is
#    exempted from the *no-repeat-idea* skip there, never from grading
#    itself. Austin, T-84: "84 percent rule can fire on S, A or C, but we
#    only will trade S of course." 52 of 57 traded re-entries in the book are
#    non-S (39 C, 13 A) and book +$4,752 on the bypass (MASTER_SPEC bug 10).
#    STATUS: not changed. MASTER_SPEC's own instruction: "fix it by deciding,
#    not by reverting" — reordering the check silently discards $4,752 of
#    booked P&L on a call Austin has not confirmed against the live path.
#    BLOCKER.
#
# 4. HTF bias is a hardcoded `None` on the yfinance fallback (`_yf_daily_context`
#    below returns bias=None unconditionally) and on any `fetch_htf_bias`
#    exception. The backtest computes a real bias on 126,198 of 127,152 rows
#    (99.2%) via polygon_feed — there is no live yfinance equivalent for the
#    1h/4h HTF trend read at all; this is a missing capability, not a flag
#    divergence. The gate this starves is `omen_bot.HTF_BIAS_VETO` (default
#    ON), not `HTF_BIAS_GATE` (a different, unrelated flag in
#    signal_runner.py, default OFF) — the name this note used to give was
#    wrong. HTF_BIAS_VETO's `opposed` check (omen_bot.py:255) requires
#    `htf_bias in ('bullish', 'bearish')`, so a hardcoded `None` forecloses it
#    unconditionally: today this changes nothing live, same conclusion as
#    before, but for the reason above, not because the veto defaults off — it
#    does not. In the 2-year backtest, where a real bias is computed, this
#    same veto grades 1,699 of 4,022 traded rows (42.2%, aligned=='against')
#    down to D (research/bt2y_trades_retest_on.json). It means live can never
#    be tightened by it and any future HTF-conditioned rule is silently blind
#    live. See the fetch diagnosis near `main()` for WHY the fallback is
#    being hit on every symbol right now.
#    STATUS: cannot be fixed inside this file — needs either a Tastytrade
#    fetch_htf_bias that returns, or a real yfinance-sourced HTF computation,
#    which exists nowhere in this repo today. BLOCKER.
#
# Everything else this file touches at import time (MIN_STOP_PCT,
# RETEST_REQUIRED, BNR_DISPLACEMENT_GATE, X_LIFT, SAC_LADDER_VARSET,
# MESH_S_VETO, every other signal_runner.py flag; RISK_DOLLARS/DISASTER_R/
# stop-fill mechanics in stop_rule.py) is left at its module default, so it
# is byte-identical to whatever backtest_week.py/backtest_2y.py measured at
# their own defaults for everything except items 1-4 above.
#
# STOP_AFTER_WIN / ENTRY_CUTOFF / SKIP_NEWS / MANAGE_END / MAX_TRADES_PER_DAY
# / GOVERNOR_S_CAP (below) are live-only session-management knobs — when to
# stop SCANNING, not what to grade or trade — with no backtest_week.py
# analog; they are outside this parity audit.
# ============================================================================

# T25 (2026-08-28, Austin R-B: "governor changes to match the book"): the live
# path grades off Austin's S/A/C ladder, not the legacy A+/A tier. This must be
# set BEFORE signal_runner is imported below — ENABLE_SAC_LADDER is read once,
# at signal_runner's own module import time (os.getenv), not re-read per call.
# `setdefault` so an explicit env override (a real `.env` line, or an exported
# shell var) still wins; only the previously-unset live default moves.
# Backtest/research processes are separate Python processes with their own
# environment, so this does not touch signal_runner's OFF-by-default reader
# there, and research/g3_arm_ow1.json is byte-identical to before this edit —
# it was never produced by importing live_scanner.py in the first place.
os.environ.setdefault("ENABLE_SAC_LADDER", "1")

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
# Read the live-effective values of the ladder flags this process forced/left
# at default (see the LIVE / BACKTEST PARITY block above) so scanner_status.json
# and the startup banner can say which grading arm actually ran, instead of
# leaving every live figure impossible to compare to a backtest arm after the
# fact — the exact hole MASTER_SPEC.md bug 5 names. Reading, not gating:
# nothing below changes what trades.
from signal_runner import ENABLE_SAC_LADDER as _LIVE_ENABLE_SAC_LADDER
from signal_runner import SAC_LADDER_VARSET as _LIVE_SAC_LADDER_VARSET
# OMEN 9.0 O2: same read-only pattern as the SAC ladder flags above.
# DAY_POLICY/ENTRY_WINDOW_END genuinely change what fires (wired below);
# FIRE_A_WHEN_NO_S/VETO_1D are stamped for reporting only -- see
# signal_runner.py's flag block for why they do not gate live entries.
from signal_runner import DAY_POLICY as _LIVE_DAY_POLICY
from signal_runner import ENTRY_WINDOW_END as _LIVE_ENTRY_WINDOW_END
from signal_runner import FIRE_A_WHEN_NO_S as _LIVE_FIRE_A_WHEN_NO_S
from signal_runner import VETO_1D as _LIVE_VETO_1D
from tastytrade_feed import TastytradeFeed
import notify_ntfy                     # the phone lane; never raises (ticket 01)
from signal_tracker import log_signal
from regime_detector import (
    RegimeDetector, RegimeConfig,
    MODE_SMA, ACTION_STOP, ACTION_STOP_LONG, ACTION_STOP_SHORT,
    ACTION_NORMAL,
)
from market_data import fetch_spy_daily_closes


# A2 2026-07-13 (unified_backtest_synthesis §8.1): SMCI/SPY/RIVN removed
# (−$22.1k/12mo combined; SMCI worst symbol in book at −$12.4k, SPY 0-for-5).
# MicroStrategy removed from all pools per 2026-08-11 triage (universe.py).
from universe import MAJOR_15, INDEX_POOL, OTHER_POOL, POOL_OF
import loss_halt
DEFAULT_SYMBOLS = MAJOR_15 + INDEX_POOL + OTHER_POOL
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


# Replay clock (omen-8 ticket 01). When `--replay` is on, the whole scanner runs
# against an archived day with the wall clock simulated, so a full session plays
# through in seconds and the push logic is exercised end to end instead of
# unit-tested in pieces. None in every other mode, which is every real run.
_SIM_NOW: datetime | None = None


def now_et() -> datetime:
    """Current time in US Eastern, DST-aware — or the replay clock."""
    if _SIM_NOW is not None:
        return _SIM_NOW
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


# R13 (Austin, probe_master_2026-08-29, fact_session_end -> `manage`):
#   11:00 stops new ENTRIES; a runner that is still working keeps running.
#
# ENTRY_CUTOFF (above) already does the entry half -- scan_once sets
# `entries_ok = False` past it and keeps marking open paper positions. What was
# missing is that the scan LOOP itself slept outside `--window`, so at 11:00 the
# process stopped marking too and a live runner was flattened by the clock
# rather than by the chart. MANAGE_END keeps the loop alive to the RTH close for
# management only; it never re-opens entries.
MANAGE_END = os.getenv("MANAGE_END", "16:00")


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


# ---- L1: one batched bar fetch per scan (2026-09-05) ----
# The per-symbol yfinance fallback (_yf_recent_bars, still used by the single-
# symbol QQQ break check above) meant a bad Tastytrade session made N separate
# HTTP round trips per cycle -- on 2026-09-04 that path returned 0 bars for all
# 29 symbols (journal/scanner-2026-09-04.log, scanner_status.json.bars_fetched
# == 0). This does ONE yf.download() for every symbol that needs the fallback
# this cycle, cached 55s so a scan loop faster than that reuses the same pull.
_YF_BATCH_CACHE: dict = {"ts": 0.0, "frames": None, "symbols": frozenset()}


def _yf_batch_recent_bars(symbols, lookback_minutes: int = 60) -> dict:
    """One yf.download() for all `symbols`, cached 55s. Returns
    {symbol: [Candle...]} -- a symbol yfinance has no data for maps to []."""
    from omen_bot import Candle
    import time as _time
    symbols = list(symbols)
    now = _time.time()
    cached = _YF_BATCH_CACHE["frames"]
    if cached is not None and (now - _YF_BATCH_CACHE["ts"]) < 55 \
            and set(symbols) <= _YF_BATCH_CACHE["symbols"]:
        data = cached
    else:
        import yfinance as yf
        data = None
        for attempt in range(2):
            try:
                data = yf.download(symbols, period="1d", interval="1m",
                                    group_by="ticker", threads=False,
                                    progress=False, prepost=False)
                break
            except Exception as e:
                if attempt == 0 and "Too Many Requests" in str(e):
                    _time.sleep(5)
                    continue
                print(f"[batch] yf.download failed: {str(e)[:160]}")
                data = None
                break
        _YF_BATCH_CACHE["frames"] = data
        _YF_BATCH_CACHE["ts"] = now
        _YF_BATCH_CACHE["symbols"] = frozenset(symbols)
        cached = data

    out: dict = {}
    if cached is None or cached.empty:
        return {s: [] for s in symbols}
    multi = isinstance(cached.columns, __import__("pandas").MultiIndex)
    for s in symbols:
        try:
            df = cached[s] if multi else cached
        except KeyError:
            out[s] = []
            continue
        if df is None or df.empty:
            out[s] = []
            continue
        df = df.dropna(how="all")
        if df.empty:
            out[s] = []
            continue
        if df.index.tz is None:
            df = df.tz_localize("UTC")
        df = df.tz_convert("America/New_York").tail(lookback_minutes)
        out[s] = [Candle(timestamp=ts.strftime("%H:%M:%S"), open=float(r.Open),
                         high=float(r.High), low=float(r.Low), close=float(r.Close),
                         volume=int(r.Volume or 0))
                  for ts, r in zip(df.index, df.itertuples())
                  if r.Open == r.Open]  # drop NaN rows (holes in the frame)
    return out


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
                           bars_fetched=None):
    """Atomically write journal/scanner_status.json (temp + os.replace).

    Dashboard reads this file later — no UI work here, file only.

    `bars_fetched` (T13): count of symbols that returned >=1 candle this cycle,
    out of len(symbols). None means "not measured this call" (the early-halt
    return path never reaches the fetch loop). A scan that ran the loop and
    fetched bars for zero symbols is a BLIND cycle — see sentry_scanner.py,
    which trips on this even when the file itself is fresh.

    `grading_arm` (2026-09-03, see the LIVE / BACKTEST PARITY block at the top
    of this file): the live-effective values of the two flags that decide
    which classifier graded today's signals. Read-only stamp so a $/day figure
    quoted from this process can be matched to the correct backtest arm
    instead of being silently compared to the wrong one (MASTER_SPEC bug 5) —
    writing it here changes nothing about what trades.
    """
    status = {
        "timestamp": now_et().isoformat(),
        "symbols_scanned": list(symbols),
        "bars_fetched": bars_fetched,
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
        "grading_arm": {
            "enable_sac_ladder": _LIVE_ENABLE_SAC_LADDER,
            "sac_ladder_varset": _LIVE_SAC_LADDER_VARSET,
            "book_default_enable_sac_ladder": False,  # backtest_2y.py never sets it
            # OMEN 9.0 O2: day_policy/entry_window_end are live-effective
            # (wired via MAX_TRADES_PER_DAY/CONSECUTIVE_LOSS_HALT and the
            # entry-cutoff check below). fire_a_when_no_s/veto_1d are
            # stamped as read but do not gate live entries -- see
            # signal_runner.py's flag block.
            "day_policy": _LIVE_DAY_POLICY,
            "entry_window_end": _LIVE_ENTRY_WINDOW_END,
            "fire_a_when_no_s": _LIVE_FIRE_A_WHEN_NO_S,
            "veto_1d": _LIVE_VETO_1D,
        },
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
    broker=None,
) -> int:
    """Scan each symbol once, post novel signals, return count fired."""
    fired = 0
    # The push day rolls with the calendar date. The scanner sleeps outside the
    # window and is relaunched daily by its schtask, so the first scan of a
    # session is the first one after 09:30 ET -- which is where ticket 01 says
    # the once-a-day flag resets.
    _roll_session_push(now_et().date().isoformat())
    # The 11:00 summary, once, on the first cycle at or past the window end.
    # It sits ABOVE the session-halt gate below on purpose: two consecutive
    # losses return early from this function, and a halted day is exactly the
    # day Austin most needs the summary for.
    if now_et().strftime("%H:%M") >= SESSION_SUMMARY_AT:
        push_summary(paper)
    # Delivery counters (Task 1): reset per cycle, logged at end so scanner-*.log
    # shows Discord health even on quiet days.
    discord = getattr(runner, "discord", None)
    if discord is not None:
        discord.posted = discord.failed = 0
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
    else:
        # OMEN 9.0 O2: ENTRY_WINDOW_END can only tighten the cutoff, never
        # loosen it -- the effective cutoff is whichever fires first.
        # Default "11:00" == ENTRY_CUTOFF's own default, so this changes
        # nothing unless ENTRY_WINDOW_END=09:45 is set explicitly.
        _effective_cutoff = min(ENTRY_CUTOFF, _LIVE_ENTRY_WINDOW_END) \
            if ENTRY_CUTOFF else _LIVE_ENTRY_WINDOW_END
        if _effective_cutoff and not getattr(runner, "futures_mode", False) \
                and now_et().strftime("%H:%M") >= _effective_cutoff:
            entries_ok = False
            print(f"  Entry cutoff {_effective_cutoff} passed — marking only, no new entries")

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
    bars_fetched = 0  # T13: symbols that returned >=1 candle this cycle

    # L1: try Tastytrade per symbol first (unchanged); collect the failures
    # into ONE batched yfinance call per scan instead of one per symbol.
    tasty_candles: dict = {}
    yf_needed: list = []
    for symbol in symbols:
        try:
            tasty_candles[symbol] = tasty_feed.fetch_recent_bars(symbol, lookback_minutes=60)
        except Exception as e:
            print(f"[{symbol}] tasty fetch failed ({str(e)[:80]}), queued for yfinance batch")
            yf_needed.append(symbol)

    yf_candles: dict = {}
    if yf_needed:
        try:
            yf_candles = _yf_batch_recent_bars(yf_needed)
        except Exception as e2:
            print(f"[batch] yfinance batch fetch failed: {str(e2)[:160]}")
            yf_candles = {s: [] for s in yf_needed}

    for symbol in symbols:
        if symbol in tasty_candles:
            candles = tasty_candles[symbol]
        else:
            candles = yf_candles.get(symbol, [])
            if not candles:
                last_error = f"{symbol}: yfinance batch returned no bars"

        if candles:
            bars_fetched += 1

        if len(candles) < 5:
            print(f"[{symbol}] only {len(candles)} bars, skipping")
            continue

        # Mark/close any open paper positions against this fresh candle first.
        if paper is not None:
            last = candles[-1]
            # close= is the stop trigger (G11): a wick through the stop stops
            # nothing out. high/low still drive the target and the Rule 6 scale.
            _session_push["last_close"][symbol] = last.close
            for ev in paper.mark(symbol, high=last.high, low=last.low,
                                 close=last.close, ts=last.timestamp):
                print(f"   📕 PAPER CLOSE {ev['symbol']} {ev['direction'].upper()} "
                      f"{ev['outcome'].upper()} P&L ${ev['pnl']:.2f}")
                if broker is not None and ev.get("event") == "CLOSE":
                    xrec = _alpaca_submit_exit(broker, runner, ev)
                    if xrec is not None:
                        print(f"   🔶 ALPACA CLOSE {xrec['side'].upper()} "
                              f"{xrec['quantity']}x {xrec['order_symbol']} -> "
                              f"{xrec['broker_order_id']}")
                _on_paper_exit(runner, ev)
                if ev["outcome"] == "stop":
                    runner.session.record_loss()
                    # R31: the halt is ACCOUNT-wide, not per symbol.
                    # runner.session is one runner = one ticker, so the
                    # per-session counter above can never see two losses
                    # in a row on two different names. This one can.
                    _account_streak["n"] += 1
                    # Lesson 6 canonical (A/B 2026-07-06: B&R-only arm was the
                    # difference between -$2k and +$450 on 30d): solid B&R
                    # stop-out arms ONE re-entry at original stop + target
                    if ev.get("stock_entry") and ev.get("setup") == "break_and_retest":
                        armed_84[symbol] = (ev["stock_entry"], ev["direction"],
                                            ev.get("stock_target"), ev.get("stock_stop"))
                        print(f"   🔁 84% rule armed for {symbol} at ${ev['stock_entry']:.2f}")
                else:
                    runner.session.record_win()
                    _account_streak["n"] = 0      # R31: a win resets it

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
        # Tag every signal with its pool for per-pool tracking (omen-5.0 T5).
        pool_name = POOL_OF.get(symbol, "OTHER")
        for sig in signals:
            sig["pool"] = pool_name
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
            executed = _emit_signal(runner, tasty_feed, symbol, candles[-1], sig, paper, broker)
            fired += 1
            if executed:  # C-grade alerts don't count toward the daily trade cap
                runner.session.signals_today += 1

    if paper is not None:
        print("   " + paper.summary())
    if discord is not None:
        print(f"  Discord delivery: posted={discord.posted} failed={discord.failed}")
    _write_scanner_status(symbols, runner.session.signals_today, runner.session,
                          regime_action, last_error=last_error,
                          posted=discord.posted if discord else 0,
                          failed=discord.failed if discord else 0,
                          qqq_breaks=getattr(runner, "qqq_breaks", None),
                          bars_fetched=bars_fetched)
    return fired


def _emit_futures_signal(runner: SignalRunner, contract: str, candle, sig: dict) -> bool:
    """Futures mode (SPEC15): price-level stops, contract sizing, no premium.

    Same grade rules as options: C = alert-only, D filtered upstream.
    # ponytail: no paper-trade book for futures yet; add futures legs to PaperBook when needed
    """
    from options_sizer import build_futures_plan
    grade = sig.get("grade", "?")
    # 2026-08-30 (A+ retired): sac_grade is the untranslated S/A/C/X letter --
    # see the SAC_TIER comment in signal_runner.py. his_grade() needs it, not
    # the engine letter, or a true S now displays as "A" like his A does.
    display_grade = sig.get("sac_grade", grade)
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
    print(f"{icon} OMEN FUTURES {signal_type_val.upper()} {direction.upper()}  Grade: {his_grade(display_grade)}")
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
        ok = runner.discord.post_text(f"{icon} **OMEN** · Grade {his_grade(display_grade)}\n{sig['reason']}\n{plan.format_discord()}")
        print("   ✓ Posted" if ok else "   ✗ Discord post failed")
    return not alert_only


_last_alert: dict = {}  # (symbol, direction) -> minutes-since-midnight of last ding
ALERT_COOLDOWN_MIN = 20

# T25 (2026-08-28, R-B): the tier gate trades Austin's ladder, not the legacy
# engine grade. ENABLE_SAC_LADDER=1 (forced on above, live-process-only) makes
# `sig["grade"]` come off `research/downgrade.py::score` via SAC_TIER
# ({"S": "A", "A": "B", "C": "C", "X": "X"} -- signal_runner.py:620, A+ retired
# 2026-08-30) instead of `_grade_pa`'s candle-shape verdict, so "A" here
# already means his S, not the legacy A+/A pool the old two-tier system
# traded (14 trades in 500 sessions over the 2-year book,
# research/x7_entry_surface_map.md section 0).
#
# TRADE = S only. A and C are WATCH -- ding only, never auto-traded, same as
# before. 84% re-entry is exempt from the grade check entirely (unchanged).
#
# R12 (Austin, probe_master_2026-08-29, fact_trade_floor -> `drop`):
#   "Entries can happen any time in our window, I don't know where you got they
#    can't be before 9:40"
# TRADE_FLOOR is DELETED. It was never ratified, it cut 10 of his 34 S days
# (29%), and research/x8_time_blocks.md had already found 09:30-09:45 to be the
# single best 15-minute block (+1.1619R at 60.7% win). The window is
# SESSION_START..SESSION_END and nothing narrows it further. Note this gate is
# the LIVE path only -- backtest_week has no floor, so no published backtest
# figure moves with this commit.
#
# GOVERNOR_S_CAP replaces the old hard "first signal of the day, across ALL
# symbols" rule with a per-symbol daily cap, PARAMETERIZED per Austin
# 2026-08-27: "my cap is just the prediction, so why cap it? maybe see what
# happens then try to cap." Default None = uncapped -- every qualifying S
# signal on every symbol trades. His ballot gave three conflicting numbers for
# what the cap should be (batch 02: c3 "max 2 S trades per symbol", c4 "max 3"
# then "cap at .8 s trades a day per symbol") -- unresolved, carried to ballot
# batch 03 (research/t25_governor.md), not guessed at here.
GOVERNOR_S_CAP = os.getenv("GOVERNOR_S_CAP")
GOVERNOR_S_CAP = int(GOVERNOR_S_CAP) if GOVERNOR_S_CAP else None
WATCH_DAILY_CAP = 5
_watch_dings = {"n": 0}
_s_trades_today: dict = {}  # symbol -> count of TRADE-tier S signals today.
# R31: consecutive CLOSED losses across every symbol this session. Reset by
# a win or a scratch. The scanner process is one session, so this is day-scoped
# the same way _s_trades_today and _watch_dings are. loss_halt.py owns the rule.
_account_streak = {"n": 0}
                            # Scanner restarts daily via schtask, so this
                            # resets free, same as _last_alert / _watch_dings.


# ===========================================================================
# THE PHONE LANE (omen-8 ticket 01)
# ===========================================================================
# ONE push a day, at the moment OMEN would trade, because Austin is away from
# the keyboard when the window is open. Discord keeps everything it posts
# today -- this lane is strictly narrower and strictly additive.
#
# What reaches the phone, and nothing else:
#   1. the FIRST size-gated S promotion of the session,
#   2. that trade's exit (stop / target / 11:00 flat),
#   3. one 11:00 summary.
# Later S promotions still go to Discord exactly as they do now.
#
# Austin, 2026-09-03, on the prior-day-level veto that this ticket originally
# specified as unconditional: "PDH/PDL are good levels in my eyes." So the
# veto is a FLAG, default OFF -- the push goes to the first size-gated S
# regardless of which level it retested. The veto arm is still tracked every
# day and reported side by side in the 11:00 summary, so the two arms are
# compared on live data without ever having to ask him again.
OMEN_LIVE_1D_VETO = os.getenv("OMEN_LIVE_1D_VETO", "0") == "1"
# The window closes at 11:00 and the summary goes out on the first cycle at or
# past it. Not tied to ENTRY_CUTOFF: that one gates NEW ENTRIES and Austin has
# moved it before; this is when he reads the day.
SESSION_SUMMARY_AT = os.getenv("OMEN_SUMMARY_AT", "11:00")


def _level_tf(level_name: str) -> str:
    """The timeframe a retested level is DRAWN on -- "1D" for PDH/PDL.

    Single owner: `backtest_2y.LEVEL_TF`, added by commit 82f5639d ("Name the
    level a trade broke, and say which timeframe it was drawn on"). Imported
    lazily because backtest_2y pulls the whole offline stack (~2.6s) and this
    is only reached on a TRADE-tier promotion, a handful of times a session.

    A live signal carries `stop_level_name` -- a plain string like "PDH",
    "OR high", "Order block low". There is no `level_tf` field on a live
    signal; only the offline book has one. Anything that is not PDH/PDL is
    reported as not-1D, which is the honest read: those are the only two of
    his six levels drawn on the daily chart.
    """
    name = (level_name or "").strip()
    try:
        from backtest_2y import LEVEL_TF
    except Exception:                      # offline stack missing -> still safe
        LEVEL_TF = {"PDH": "1D", "PDL": "1D"}
    return LEVEL_TF.get(name, "intraday")


# Per-day push state. Reset on the date roll, which for this process is 09:30:
# the scanner is launched by a daily schtask and `scan_once` sleeps outside the
# window, so the first scan of a session is the first one after 09:30 ET.
_session_push: dict = {
    "date": None,
    "pushed": False,          # the one phone push has gone out
    "exit_pushed": False,     # ...and so has its exit
    "summary_pushed": False,
    "push_rec": None,         # the trade that went to the phone
    "veto_first": None,       # first S that is NOT on a 1D level (the other arm)
    "trades": [],             # every size-gated S promotion today, in order
    "exits": [],              # every closed paper leg today
    "last_close": {},         # symbol -> most recent close seen this session
}


def _roll_session_push(day: str) -> None:
    """Start a fresh push day. Idempotent within a session."""
    if _session_push["date"] == day:
        return
    _session_push.update(date=day, pushed=False, exit_pushed=False,
                         summary_pushed=False, push_rec=None, veto_first=None,
                         trades=[], exits=[], last_close={})


def _note_s_trade(rec: dict) -> bool:
    """Record a size-gated S promotion; True if it is the one for the phone."""
    _session_push["trades"].append(rec)
    if _session_push["veto_first"] is None and rec["level_tf"] != "1D":
        _session_push["veto_first"] = rec
    if _session_push["pushed"]:
        return False
    if OMEN_LIVE_1D_VETO and rec["level_tf"] == "1D":
        return False           # veto arm ON: wait for a non-prior-day level
    _session_push["pushed"] = True
    _session_push["push_rec"] = rec
    return True


def _push_s_signal(rec: dict) -> bool:
    """The one trade alert -- the WHOLE order, since no venue in
    `research/execution_prep_2026-09.md` has a pre-fillable deep link. Plain
    English, but every field a human needs to place the contract by hand
    without looking anything up: underlying, expiry, strike, right, the OCC
    symbol when Tastytrade resolved one, contracts, entry/stop/target, the
    1R dollar risk, and the Alpaca paper order id once L3 unblocks."""
    side = "CALL" if rec["direction"] == "call" else "PUT"
    title = f"OMEN S {rec['symbol']} {side}"
    strike = rec.get("strike") or 0.0
    expiration = rec.get("expiration") or "?"
    occ = rec.get("occ_symbol") or "(no listed contract resolved)"
    order_id = rec.get("alpaca_order_id") or "not placed (Alpaca paper unwired -- L3 blocked, keys 401)"
    body = (
        f"{rec['ts']} ET  ·  {rec['setup'].replace('_', ' ')}\n"
        f"Contract  {rec['symbol']} {expiration} ${strike:g} {side}\n"
        f"OCC       {occ}\n"
        f"Entry   {rec['entry']:.2f}\n"
        f"Stop    {rec['stop']:.2f}\n"
        f"Target  {rec['target']:.2f}\n"
        f"Size    {rec['contracts']} contracts\n"
        f"1R      ${rec.get('max_loss', 0.0):,.0f}\n"
        f"Tier    {rec['tier']} (his S)\n"
        f"Level   {rec['level']}"
        + (" (prior day)" if rec["level_tf"] == "1D" else "")
        + f"\nAlpaca  {order_id}"
    )
    return notify_ntfy.push(title, body, priority="high", tags="rocket")


def _push_exit(rec: dict, ev: dict) -> bool:
    """The pushed trade closed. Entry, exit, R."""
    r = ev.get("r")
    title = f"OMEN {rec['symbol']} {ev['outcome'].upper()}  {r:+.2f}R" \
        if r is not None else f"OMEN {rec['symbol']} {ev['outcome'].upper()}"
    body = (
        f"{ev.get('ts', '')} ET\n"
        f"Entry   ${ev.get('entry_premium', 0):.2f}\n"
        f"Exit    ${ev.get('exit_premium', 0):.2f}\n"
        f"P&L     ${ev.get('trade_pnl', ev.get('pnl', 0)):+,.2f}"
        + (f"  ({r:+.2f}R)" if r is not None else "")
    )
    tag = "white_check_mark" if (r or 0) > 0 else "x"
    return notify_ntfy.push(title, body, priority="high", tags=tag)


def _open_runner_lines(paper) -> list:
    """One line per still-open runner: symbol, entry, current R.

    Austin, 2026-09-03: "could still be active trades from runners, it would
    report that too." R is the STOCK-side R against the last close this
    scanner saw, which is the number he reads a chart in.
    """
    lines = []
    for pos in getattr(paper, "open_positions", []) or []:
        last = _session_push["last_close"].get(pos.symbol)
        risk = abs(pos.stock_entry - pos.stock_stop)
        if last is None or risk <= 0:
            lines.append(f"  {pos.symbol} {pos.direction.upper()} "
                         f"entry {pos.stock_entry:.2f} — still open, no mark")
            continue
        r = ((last - pos.stock_entry) if pos.direction == "call"
             else (pos.stock_entry - last)) / risk
        lines.append(f"  {pos.symbol} {pos.direction.upper()} "
                     f"entry {pos.stock_entry:.2f} — open, {r:+.2f}R")
    return lines


def build_summary_text(paper=None) -> str:
    """The 11:00 summary, as a plain string.

    Austin, 2026-09-03: AUGUR's daily structure (this text, the homework link,
    the evening reveal) goes to a Slack channel; the live S push stays on ntfy.
    So this returns a STRING and posts nothing -- the Slack poster reuses it
    verbatim when it exists. Nothing here builds a Slack payload.

    Both arms are always reported. Arm A is what actually fired (the first
    size-gated S of the day, any level). Arm B is the same rule with prior-day
    highs and lows vetoed. They differ only on days whose first S retested a
    PDH or a PDL, and reporting both every day is how the two get compared
    without asking him again.
    """
    day = _session_push["date"] or "today"
    out = [f"OMEN 11:00 — {day}", ""]

    trades = _session_push["trades"]
    if not trades:
        out.append("No S setup today. Nothing traded.")
    else:
        out.append(f"{len(trades)} S setup(s) fired:")
        for rec in trades:
            ex = rec.get("exit")
            if ex is None:
                tail = "still open"
            elif ex.get("r") is not None:
                tail = f"{ex['outcome']} {ex['r']:+.2f}R (${ex['pnl']:+,.2f})"
            else:
                tail = f"{ex['outcome']} ${ex['pnl']:+,.2f}"
            side = "CALL" if rec["direction"] == "call" else "PUT"
            out.append(f"  {rec['ts']} {rec['symbol']} {side} @ {rec['entry']:.2f}"
                       f"  [{rec['level']}] — {tail}")

    a = _session_push["push_rec"]
    b = _session_push["veto_first"]
    out += ["", "The one trade, both arms:"]
    out.append("  taken   (any level): " +
               (f"{a['symbol']} {a['direction'].upper()} @ {a['entry']:.2f} "
                f"[{a['level']}]" if a else "no trade"))
    out.append("  would-be (no prior-day levels): " +
               (f"{b['symbol']} {b['direction'].upper()} @ {b['entry']:.2f} "
                f"[{b['level']}]" if b else "no trade"))
    if a and b and a is b:
        out.append("  same trade either way today.")
    elif a and not b:
        out.append("  the prior-day veto would have sat this day out.")

    if paper is not None:
        open_lines = _open_runner_lines(paper)
        if open_lines:
            out += ["", "Still open (runners):"] + open_lines

    return "\n".join(out)


def push_summary(paper=None) -> bool:
    """Send the 11:00 summary once per session."""
    if _session_push["summary_pushed"]:
        return False
    _session_push["summary_pushed"] = True
    return notify_ntfy.push(f"OMEN 11:00 — {_session_push['date'] or 'today'}",
                            build_summary_text(paper),
                            priority="default", tags="bar_chart")


def _on_paper_exit(runner, ev: dict) -> None:
    """A live paper position closed: Discord, then the phone.

    `discord_bot.post_trade_result` has existed since the bot was written and
    had ZERO callers -- every closed paper trade was logged to the journal and
    nothing ever reported it. This is the event it was written for.

    Only a real CLOSE counts. A `SCALE` / `BE_SCALE` event is a leg coming off,
    not the trade ending, and pushing on one would spend the day's single exit
    notification on a partial.
    """
    if ev.get("event") not in (None, "CLOSE"):
        return

    # R, against the risk this card was actually sized to. `trade_pnl` is both
    # legs of a scaled trade; `pnl` is the runner leg alone (paper_trader.py).
    #
    # Pair with the EARLIEST still-unmatched promotion on that symbol. Matching
    # on symbol alone silently reported one trade's exit against every trade
    # that name fired today -- on 2026-09-02's replay AAPL fired twice and both
    # rows showed the first exit.
    rec = next((t for t in _session_push["trades"]
                if t["symbol"] == ev.get("symbol") and "exit" not in t), None)
    pnl = ev.get("trade_pnl", ev.get("pnl"))
    max_loss = (rec or {}).get("max_loss") or 0.0
    ev = dict(ev)
    ev["r"] = round(pnl / max_loss, 3) if (max_loss and pnl is not None) else None
    ev["pnl"] = pnl
    _session_push["exits"].append(ev)
    if rec is not None:
        rec["exit"] = ev

    discord = getattr(runner, "discord", None)
    if getattr(runner, "post_to_discord", False) and discord is not None:
        try:
            discord.post_trade_result(ev)
        except Exception as e:                       # never kill the scan cycle
            print(f"   ✗ Discord trade result failed: {e}")

    pushed = _session_push["push_rec"]
    if (pushed and not _session_push["exit_pushed"]
            and ev.get("symbol") == pushed["symbol"]):
        _session_push["exit_pushed"] = True
        _push_exit(pushed, ev)


def _tier(runner: SignalRunner, sig: dict, grade: str, ts: str, symbol: str) -> str:
    s = runner.session
    # R31 (verdict `both`) -- the two-consecutive-loss halt now runs in the
    # LIVE path account-wide as well as in the backtest. Before T23 the
    # only halt here was runner.session.consecutive_losses, and a runner is
    # one ticker: two losses on two different symbols never halted
    # anything. Open positions keep managing; this stops NEW entries only.
    if (loss_halt.LOSS_HALT
            and _account_streak["n"] >= loss_halt.HALT_AFTER_CONSECUTIVE_LOSSES):
        return "WATCH"
    if getattr(sig["signal_type"], "value", "") == "reentry_84_rule":
        return "TRADE" if s.consecutive_losses < 2 else "WATCH"
    # 2026-08-30 (A+ retired): `grade` alone can no longer tell S apart from
    # his A -- SAC_TIER now writes both to the engine's top grade `A`. Read
    # the untranslated letter `_sac_ladder_grade` also writes to
    # `sig["sac_grade"]` instead. R12: no time floor -- the whole window trades.
    if sig.get("sac_grade") != "S":
        return "WATCH"
    if s.consecutive_losses >= 2:
        return "WATCH"
    if GOVERNOR_S_CAP is not None and _s_trades_today.get(symbol, 0) >= GOVERNOR_S_CAP:
        return "WATCH"
    return "TRADE"


def _cooled_down(symbol: str, direction: str, ts: str) -> bool:
    """One ding per symbol+direction per 20 min — detector re-triggers every
    bar near a level (2026-07-06: GOOGL fired 4 alerts in 9 min)."""
    mins = int(ts[:2]) * 60 + int(ts[3:5])
    last = _last_alert.get((symbol, direction))
    if last is not None and mins - last < ALERT_COOLDOWN_MIN:
        return False
    _last_alert[(symbol, direction)] = mins
    return True


# ===========================================================================
# ALPACA PAPER-BROKER SUBMISSION (OMEN 9.0 W3, 2026-09-05)
# ===========================================================================
# `broker/alpaca.py` (L3) is hard-coded to Alpaca's PAPER endpoint; this block
# is the only place that ever calls `broker.place_order`. It piggybacks on the
# EXISTING paper book (`paper_trader.PaperBook`) rather than replacing it: the
# simulated book is still what the marking loop, the governor and the phone
# push read from. This is an additional, best-effort submission of the same
# trade to Alpaca's paper account, so Monday's book can be compared against a
# real (paper) fill. If a submission fails, the simulated book is unaffected
# -- see the try/except around `broker.place_order` below.
#
# Idempotency key / matching key: `f"{symbol}|{ts}"`, where `ts` is the same
# `candle.timestamp` PaperBook.open_from_plan stores as `PaperPosition.opened_at`
# and echoes back on every close event it returns from `.mark()`. That is the
# only link between an entry submission and its matching exit -- paper_trader.py
# is not on this row's edit list, so nothing was added to PaperPosition itself.
_ALPACA_LEDGER = Path(__file__).parent / "journal" / "alpaca-paper.jsonl"
_alpaca_open_orders: dict = {}  # f"{symbol}|{opened_at}" -> last entry record


def _alpaca_log(event: dict) -> None:
    _ALPACA_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with _ALPACA_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _alpaca_submit_entry(broker, runner: SignalRunner, symbol: str, sig: dict,
                          plan, ts: str, size_pct: float):
    """Submit the opening order for one fired S onto the Alpaca paper broker.

    Options first (`broker.resolve_option_contract` against Alpaca's own
    listed chain, NOT the Tastytrade-derived `plan.occ_symbol` -- Alpaca may
    not list the same contract); on `OptionsNotAvailable`, falls back to a
    share order sized so `shares * |entry - stop| == 1R` (`DEFAULT_MAX_LOSS *
    size_pct`), floored the same way the engine floors risk everywhere else
    (`signal_runner.min_risk_floor`) so a razor-thin stop can't blow the size
    up. Never called under replay -- see the assert, THE LAW's own words."""
    assert not getattr(runner, "replay", False), (
        "Alpaca submit attempted with runner.replay=True -- replay must "
        "never place an order, this is a bug at the call site, not here.")
    from broker.base import Order, OrderSide, OrderType
    from broker.alpaca import OptionsNotAvailable
    from options_sizer import DEFAULT_MAX_LOSS
    from signal_runner import min_risk_floor

    direction = sig["direction"]
    idem = f"{symbol}-{ts}-{direction}-entry"
    fallback = None
    order = None
    try:
        occ = broker.resolve_option_contract(
            underlying=symbol,
            expiration=plan.expiration,
            strike=plan.strike,
            direction=direction,
        )
        qty = int(getattr(plan, "contracts", 0) or 0)
        if qty > 0:
            order = Order(symbol=occ, side=OrderSide.BUY, quantity=qty,
                          order_type=OrderType.MARKET, idempotency_key=idem)
    except OptionsNotAvailable:
        fallback = "shares"
        risk_per_share = max(abs(sig["entry"] - sig["stop"]),
                              min_risk_floor(sig["entry"]))
        max_loss = DEFAULT_MAX_LOSS * size_pct
        qty = int(max_loss / risk_per_share) if risk_per_share > 0 else 0
        if qty > 0:
            side = OrderSide.BUY if direction == "call" else OrderSide.SELL
            order = Order(symbol=symbol, side=side, quantity=qty,
                          order_type=OrderType.MARKET, idempotency_key=idem)

    if order is None:
        _alpaca_log({"event": "entry_skip", "ts": ts, "symbol": symbol,
                     "direction": direction, "reason": "zero-quantity after sizing",
                     "fallback": fallback})
        return None

    try:
        handle = broker.place_order(order)
    except Exception as e:  # noqa: BLE001 - log and let the sim book stand alone
        _alpaca_log({"event": "entry_error", "ts": ts, "symbol": symbol,
                     "direction": direction, "order_symbol": order.symbol,
                     "error": str(e)[:200]})
        return None

    rec = {
        "event": "entry", "ts": ts, "symbol": symbol, "direction": direction,
        "order_symbol": order.symbol, "side": order.side.value,
        "quantity": order.quantity, "fallback": fallback,
        "broker_order_id": handle.broker_order_id,
        "status": handle.status.value, "idempotency_key": idem,
    }
    _alpaca_log(rec)
    _alpaca_open_orders[f"{symbol}|{ts}"] = rec
    return rec


def _alpaca_submit_exit(broker, runner: SignalRunner, ev: dict):
    """Submit the closing order that matches an entry the marking loop just
    booked a stop or target on. Looked up by the same `symbol|opened_at` key
    the entry was logged under; if no matching entry was submitted (e.g. the
    entry was WATCH-only, or Alpaca submission was off then), this is a no-op.
    Never called under replay -- see the assert."""
    assert not getattr(runner, "replay", False), (
        "Alpaca submit attempted with runner.replay=True -- replay must "
        "never place an order, this is a bug at the call site, not here.")
    key = f"{ev.get('symbol')}|{ev.get('opened_at')}"
    entry_rec = _alpaca_open_orders.pop(key, None)
    if entry_rec is None:
        return None
    from broker.base import Order, OrderSide, OrderType

    close_side = OrderSide.SELL if entry_rec["side"] == "buy" else OrderSide.BUY
    idem = f"{ev.get('symbol')}-{ev.get('opened_at')}-{ev.get('direction')}-exit"
    order = Order(symbol=entry_rec["order_symbol"], side=close_side,
                  quantity=entry_rec["quantity"], order_type=OrderType.MARKET,
                  idempotency_key=idem)
    try:
        handle = broker.place_order(order)
    except Exception as e:  # noqa: BLE001
        _alpaca_log({"event": "exit_error", "ts": ev.get("ts"),
                     "symbol": ev.get("symbol"), "order_symbol": order.symbol,
                     "error": str(e)[:200]})
        return None

    rec = {
        "event": "exit", "ts": ev.get("ts"), "symbol": ev.get("symbol"),
        "order_symbol": order.symbol, "side": close_side.value,
        "quantity": order.quantity, "outcome": ev.get("outcome"),
        "broker_order_id": handle.broker_order_id,
        "status": handle.status.value, "idempotency_key": idem,
    }
    _alpaca_log(rec)
    return rec


def _emit_signal(runner: SignalRunner, tasty_feed: TastytradeFeed, symbol: str, candle, sig: dict, paper=None, broker=None) -> bool:
    """Build OptionsPlan (Tastytrade real-time premium, fallback delta estimate) and post.

    Returns True for TRADE-tier signals (counted against the daily governor,
    paper-traded); False for WATCH dings and skips."""
    from options_sizer import build_options_plan, DEFAULT_MAX_LOSS
    if sig["entry"] == sig["stop"]:
        return False
    if getattr(sig["signal_type"], "value", "") != "reentry_84_rule" and \
            not _cooled_down(symbol, sig["direction"], candle.timestamp):
        print(f"  {symbol} {sig['direction']} suppressed: cooldown ({ALERT_COOLDOWN_MIN}m)")
        return False
    if getattr(runner, "futures_mode", False):
        return _emit_futures_signal(runner, symbol, candle, sig)
    grade = sig.get("grade", "?")
    # 2026-08-30 (A+ retired): sac_grade is the untranslated S/A/C/X letter --
    # see the SAC_TIER comment in signal_runner.py. his_grade() needs it, not
    # the engine letter, or a true S now displays as "A" like his A does.
    display_grade = sig.get("sac_grade", grade)
    # G144 (2026-09-05): size_pct used to come off GRADE_SIZE_PCT[grade] --
    # the legacy A+/A/B/C/X ladder -- but SAC_TIER maps BOTH "S" and "A" to
    # the engine letter "A" (signal_runner.py SAC_TIER), so a real S signal
    # sized at 0.8 (80% of RISK_DOLLARS = $800), never the full $1,000 R.
    # His 2026-09-01 call: only S trades live; A and C are watch-only and
    # carry no real budget. Sizing now keys off his ladder directly: S risks
    # exactly RISK_DOLLARS, everything else sizes at 0 (never reaches the
    # paper-trade branch below, since `_tier` already gates TRADE on
    # sac_grade == "S").
    # 84% re-entries are exempt from the grade check entirely (see the WATCH
    # cap block below) -- they always risk full size, so they are exempt from
    # the S-only sizing gate too, same as before this change.
    is_reentry = getattr(sig["signal_type"], "value", "") == "reentry_84_rule"
    size_pct = 1.0 if (display_grade == "S" or is_reentry) else 0.0
    # 84% re-entries run 2x size (Austin: double to recover first stop-out + profit)
    if is_reentry:
        size_pct *= 2.0
    tier = _tier(runner, sig, grade, candle.timestamp, symbol)
    alert_only = tier != "TRADE"
    if alert_only:
        if _watch_dings["n"] >= WATCH_DAILY_CAP:
            print(f"  {symbol} {sig['direction']} WATCH suppressed: daily cap ({WATCH_DAILY_CAP})")
            return False
        _watch_dings["n"] += 1
    elif getattr(sig["signal_type"], "value", "") != "reentry_84_rule":
        # 84% re-entries are exempt from the per-symbol S cap, same as they are
        # exempt from the grade check itself (unchanged behaviour).
        _s_trades_today[symbol] = _s_trades_today.get(symbol, 0) + 1
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
    print(f"{icon} {tag}{tier} {signal_type_val.upper()} {sig['direction'].upper()}  Grade: {his_grade(display_grade)}  Stop: {stop_level} ({stop_width}%)")
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
        # Ported from the cloud branch's OMEN 8.0 R5. `signal_tracker.log_signal`
        # has taken `austin_tier` since omen-3.9 T4 and `signal_runner` already
        # passes it, but this path -- the one that actually promotes to TRADE --
        # never did, so a live promotion (or refusal) was unauditable after the
        # fact from the signal log alone. The engine `grade` above cannot stand
        # in for it: A+ was retired 2026-08-30 and SAC_TIER writes both his S
        # and his A to the top letter `A`.
        austin_tier=sig.get("austin_tier"),
    )

    if paper is not None and not alert_only:
        pos = paper.open_from_plan(plan, ts=candle.timestamp, grade=grade,
                                   setup=signal_type_val)
        print(f"   📗 PAPER OPEN {pos.contracts}x {pos.symbol} ${pos.strike:g} "
              f"{pos.direction.upper()} @ ${pos.entry_premium:.2f}")
        if broker is not None:
            _alpaca_entry_rec = _alpaca_submit_entry(broker, runner, symbol, sig, plan,
                                                      candle.timestamp, size_pct)
            if _alpaca_entry_rec is not None:
                print(f"   🔷 ALPACA {_alpaca_entry_rec['side'].upper()} "
                      f"{_alpaca_entry_rec['quantity']}x "
                      f"{_alpaca_entry_rec['order_symbol']} -> "
                      f"{_alpaca_entry_rec['broker_order_id']}")
        else:
            _alpaca_entry_rec = None
    else:
        _alpaca_entry_rec = None
    if runner.post_to_discord and runner.discord:
        ok = runner.discord.post_signal(sig["signal_type"], candle, sig["reason"], plan,
                                         grade=display_grade, stop_level_name=stop_level, stop_width_pct=stop_width)
        print("   ✓ Posted" if ok else "   ✗ Discord post failed")

    # ---- the phone lane (ticket 01) ------------------------------------
    # Strictly after Discord, strictly additive: Discord posts every signal it
    # posts today, and this sends at most one of them on to Austin's phone.
    # `_tier` returns TRADE for an armed 84% re-entry regardless of its grade
    # (see the parity block at the top of this file, item 3), so the S check
    # here is explicit rather than inherited from `tier`.
    if (not alert_only and sig.get("sac_grade") == "S"
            and getattr(plan, "contracts", 0) >= 1):
        rec = {
            "symbol": symbol, "direction": sig["direction"],
            "ts": candle.timestamp, "setup": signal_type_val,
            "entry": sig["entry"], "stop": sig["stop"],
            "target": getattr(plan, "stock_target", 0.0),
            "contracts": plan.contracts, "tier": tier,
            "level": stop_level or "unnamed",
            "level_tf": _level_tf(stop_level),
            # The risk this card was sized against, carried so the exit can
            # report a real R instead of dividing by a hardcoded 1R.
            "max_loss": DEFAULT_MAX_LOSS * size_pct,
            # G145 (L6, 2026-09-05): no venue has a deep link
            # (`research/execution_prep_2026-09.md`), so the push is the only
            # place the whole order ever appears -- these carry the contract
            # itself, not just the stock-side numbers above.
            "expiration": getattr(plan, "expiration", ""),
            "strike": getattr(plan, "strike", 0.0),
            "occ_symbol": getattr(plan, "occ_symbol", "") or "",
            # Alpaca paper order id (W3, 2026-09-05): the real submission's
            # broker_order_id when `--paper-broker alpaca` is on and the
            # submit succeeded; None otherwise (no invented id).
            "alpaca_order_id": (_alpaca_entry_rec or {}).get("broker_order_id"),
        }
        if _note_s_trade(rec):
            _push_s_signal(rec)
    return not alert_only


# ===========================================================================
# REPLAY (omen-8 ticket 01)
# ===========================================================================
# There is no other replay mode in this file. `backtest_week.simulate_day` and
# `replay_scarface.py` replay the ENGINE, not the SCANNER -- neither one runs
# `scan_once`, so neither exercises the tier gate, the governor, the paper book
# or the push logic. This does: the same `scan_once` the live process runs,
# against archived 1-minute bars, with `now_et()` simulated. A whole session
# plays through in seconds.


class ReplayFeed:
    """A TastytradeFeed stand-in backed by `data_archive` CSVs.

    Implements only the four methods `scan_once` / `get_daily_context` call.
    It deliberately does NOT implement `fetch_option_quote`, so
    `options_sizer.build_options_plan` falls through to its delta estimate --
    there are no historical option quotes on disk, and inventing one would put
    a fabricated premium into a card that looks exactly like a real one.
    """

    def __init__(self, day: str, symbols):
        import polygon_feed as pf
        self._pf = pf
        self.day = day
        self.bars = {}
        for sym in symbols:
            try:
                allb = pf.fetch_day(sym, day)
            except Exception:
                allb = []
            if allb:
                self.bars[sym] = allb
        self.symbols = sorted(self.bars)

    def validate_credentials(self):
        return True

    def _now_hhmmss(self) -> str:
        return now_et().strftime("%H:%M:%S")

    def fetch_recent_bars(self, symbol: str, lookback_minutes: int = 60):
        allb = self.bars.get(symbol)
        if not allb:
            return []
        cut = self._now_hhmmss()
        seen = [c for c in self._pf.rth(allb) if c.timestamp <= cut]
        return seen[-lookback_minutes:]

    def _prior_day_bars(self, symbol: str):
        """The last archived session strictly before `self.day`."""
        import glob as _glob
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "data_archive", symbol)
        days = sorted(os.path.basename(p)[:-4]
                      for p in _glob.glob(os.path.join(d, "*.csv")))
        prior = [x for x in days if x < self.day]
        if not prior:
            return []
        try:
            return self._pf.fetch_day(symbol, prior[-1])
        except Exception:
            return []

    def fetch_daily_levels(self, symbol: str):
        """(pdh, pdl, pd_open, pd_close) off the prior archived session."""
        pb = self._pf.rth(self._prior_day_bars(symbol))
        if not pb:
            raise ValueError(f"no prior-day archive for {symbol}")
        return (max(c.high for c in pb), min(c.low for c in pb),
                pb[0].open, pb[-1].close)

    def fetch_premarket_levels(self, symbol: str):
        return self._pf.premarket_hi_lo(self.bars.get(symbol) or [])

    def fetch_htf_bias(self, symbol: str):
        # Same hardcoded None the live yfinance fallback returns (see the
        # parity block, item 4). HTF_BIAS_GATE is off in both paths, so this
        # changes nothing -- it just does not pretend to know.
        return None


def run_replay(day: str, symbols, paper_on: bool = True,
               start: str = "09:30", end: str = "11:05",
               ledger_path=None) -> int:
    """Play one archived session through `scan_once`, minute by minute.

    The paper book writes to `journal/replay-<day>.jsonl`, NEVER to the live
    `journal/paper-trades.jsonl`. A replayed session is a simulation of a day
    that already happened; letting it append to the real ledger would put
    invented fills in the book Austin reads his paper results out of.
    """
    global _SIM_NOW
    feed = ReplayFeed(day, symbols)
    if not feed.symbols:
        print(f"REPLAY {day}: no archived bars for any of {len(list(symbols))} "
              f"symbols — nothing to replay.")
        return 1
    print(f"REPLAY {day}: {len(feed.symbols)} symbols with archive "
          f"({', '.join(feed.symbols[:12])}{' ...' if len(feed.symbols) > 12 else ''})")

    runner = SignalRunner(post_to_discord=False)
    # W3 (2026-09-05): replay is a simulation of a day that already happened
    # -- it must NEVER place a real (even paper) order. `_alpaca_submit_entry`
    # / `_alpaca_submit_exit` assert this is False before calling
    # `broker.place_order`; run_replay never receives or constructs a broker,
    # so this is belt-and-suspenders, not the only guard.
    runner.replay = True
    paper = None
    if paper_on:
        from paper_trader import PaperBook
        paper = PaperBook(ledger_path=Path(ledger_path) if ledger_path else
                          (Path(__file__).parent / "journal" / f"replay-{day}.jsonl"))
        print(f"  replay paper ledger: {paper.ledger_path.name}")

    y, m, d = (int(x) for x in day.split("-"))
    tz = ZoneInfo("America/New_York")
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    cur = datetime(y, m, d, sh, sm, tzinfo=tz)
    stop_at = datetime(y, m, d, eh, em, tzinfo=tz)

    seen: Set[str] = set()
    fired = 0
    try:
        while cur <= stop_at:
            _SIM_NOW = cur
            fired += scan_once(runner, feed, feed.symbols, seen, paper,
                               max_trades=int(os.getenv("MAX_TRADES_PER_DAY", "3")),
                               max_consecutive_losses=int(
                                   os.getenv("CONSECUTIVE_LOSS_HALT", "2")),
                               regime_detector=None)
            cur += timedelta(minutes=1)
    finally:
        _SIM_NOW = None

    print(f"\nREPLAY {day} done: {fired} signals fired.")
    print("-" * 60)
    print(build_summary_text(paper))
    print("-" * 60)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Live Omen signal scanner")
    parser.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS,
                        help=f"Tickers to watch (default {DEFAULT_SYMBOLS})")
    parser.add_argument("--window", default=DEFAULT_WINDOW,
                        help="Trading window in ET HH:MM-HH:MM (default 09:30-11:00)")
    parser.add_argument("--once", action="store_true",
                        help="Run a single scan and exit (testing)")
    parser.add_argument("--no-discord", action="store_true", help="Skip Discord posting")
    parser.add_argument("--paper", action="store_true",
                        help="Paper-trade simulation: log fired signals + mark to stop/target in journal/paper-trades.jsonl")
    parser.add_argument("--paper-broker", default=None, choices=["alpaca"],
                        help="Additionally submit each fired S to a real paper broker "
                             "(logs journal/alpaca-paper.jsonl). Requires --paper. "
                             "PAPER endpoint only -- see broker/alpaca.py.")
    parser.add_argument("--futures", nargs="?", const="ES", default=None, metavar="CONTRACT",
                        help="Futures mode (SPEC15): trade ES/NQ/RTY via yfinance feed instead of stock options")
    parser.add_argument("--replay", metavar="YYYY-MM-DD", default=None,
                        help="Replay one archived session through the real scan loop "
                             "with the wall clock simulated (ticket 01)")
    parser.add_argument("--ntfy-topic", default=None,
                        help=f"ntfy topic for this run; overrides ${notify_ntfy.TOPIC_ENV}")
    args = parser.parse_args()

    # A topic given on the command line is the topic for the whole process --
    # notify_ntfy resolves from the env, so set it once here rather than
    # threading it through every call site.
    if args.ntfy_topic:
        os.environ[notify_ntfy.TOPIC_ENV] = args.ntfy_topic

    print(OMEN_LOGO)
    if args.replay:
        sys.exit(run_replay(args.replay, args.symbols, paper_on=True))
    start, end = parse_window(args.window)
    runner = SignalRunner(post_to_discord=not args.no_discord)
    runner.replay = False  # W3: the live/once path may submit; run_replay() never does.
    if args.futures:
        runner.futures_mode = True
        args.symbols = [args.futures.upper()]
        if args.window == DEFAULT_WINDOW:
            args.window = "09:30-16:00"  # main ES volume session
            start, end = parse_window(args.window)
    seen: Set[str] = set()
    max_trades = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
    max_losses = int(os.getenv("CONSECUTIVE_LOSS_HALT", "2"))
    # OMEN 9.0 O2: DAY_POLICY=one_and_done overrides both to 1 outright.
    # It cannot merely change what "unset" means the way ENTRY_WINDOW_END
    # does below (min() against ENTRY_CUTOFF) -- .env pins MAX_TRADES_PER_DAY
    # /CONSECUTIVE_LOSS_HALT to 3/2 unconditionally (`_load_env_file` only
    # fills a key that is not already in os.environ), so an "if unset"
    # override would never fire against a real deployment's .env. DAY_POLICY
    # =first3 (the default) leaves max_trades/max_losses exactly as they
    # were before this flag existed.
    if _LIVE_DAY_POLICY == "one_and_done":
        max_trades = 1
        max_losses = 1
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

    broker = None
    if args.paper_broker == "alpaca":
        if not args.paper:
            print("--paper-broker alpaca requires --paper. Exiting.")
            sys.exit(1)
        from broker.alpaca import AlpacaBroker
        broker = AlpacaBroker()
        print(f"🔷 Alpaca paper broker ON → {_ALPACA_LEDGER}")

    print(f"Scanner armed. Symbols: {args.symbols}  Window (ET): {args.window}")

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
                            regime_detector=regime_det, broker=broker)
        print(f"Done. {fired} signals fired.")
        return

    while True:
        now = now_et()
        if now.weekday() >= 5:  # Sat=5, Sun=6
            print(f"Weekend ({now.strftime('%a')}), sleeping 1h")
            time.sleep(3600)
            continue

        # R13: the loop stays alive to MANAGE_END so open positions keep marking
        # past 11:00. New entries are already stopped by ENTRY_CUTOFF inside
        # scan_once, so this widens management only.
        manage_end = max(end, parse_window("00:00-" + MANAGE_END)[1]) if MANAGE_END else end
        if not in_window(now, start, manage_end):
            # Sleep until next window open
            print(f"{now.strftime('%H:%M:%S')} ET outside window {args.window}"
                  f" (managing to {MANAGE_END}), sleeping 60s")
            time.sleep(60)
            continue

        print(f"\n=== {now.strftime('%H:%M:%S')} ET scan ===")
        fired = scan_once(runner, tasty_feed, args.symbols, seen, paper,
                            max_trades=max_trades, max_consecutive_losses=max_losses,
                            regime_detector=regime_det, broker=broker)
        if fired == 0:
            print("  no new signals")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScanner stopped.")
        sys.exit(0)
