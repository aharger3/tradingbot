"""E9 forward shadow clock (omen-canon section 5, row E9). Paper only, no orders, no rule edits.

Replays each NEW Mon-Thu NQ session (2026-10-01 onward) through the FROZEN mantra
(v2-t01-orb-1m/orb1m.py via v2-paper-harness/paper_replay._one_cell: OR5, displacement >= 1 ATR,
wick retest, strong trigger, 2R, flat 10:30, same-bar = stop) and appends one row per session to
forward-clock.csv. Bar source: Yahoo Finance NQ=F 1-minute bars through yfinance (free; the same
source as futures_feed.py; Yahoo keeps ~7 days of 1m, so a missed night is caught up next run).

The replay is T+1 style: it runs after the bell on bars that are already final, never live.

Parity check column = engine hash is the frozen value (CRLF-normalised) AND >= 57 of 61 one-minute
bars exist for 09:30-10:30. Anything else is DEGRADED and said so; the row is still logged.

Weekly line: on the Thursday run (or the first run after it) ONE summary line goes to the ntfy topic
named NTFY_TOPIC in the keys vault (read via keys.py get; the value is never printed or logged).

Usage:
    python forward_clock.py                 # catch up every unlogged Mon-Thu session, push weekly line if due
    python forward_clock.py --date 2026-10-01 --no-push
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

ET = ZoneInfo("America/New_York")
MAIN = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
ENGINE_PATH = MAIN / "v2-t01-orb-1m" / "orb1m.py"
FROZEN_SHA256 = "bafd7ce4e4f69250c0cef80acdbd26057ee04a6a658c95b11ed92bba08bc8ef1"  # == engine_lock.FROZEN_SHA256 (LF-normalised)
OUT_DIR = Path(r"C:\Users\aharg\Desktop\life-plan\07-money\omen\night-1003")
CSV_PATH = OUT_DIR / "forward-clock.csv"
STATE_PATH = OUT_DIR / "forward-clock.state.json"
LOG_PATH = OUT_DIR / "forward-clock.log"
KEYS_PY = Path(r"C:\Users\aharg\.claude\sync-setup\keys.py")
START = dt.date(2026, 10, 1)
MIN_BARS = 57          # of 61 one-minute bars 09:30..10:30 inclusive
COMM_USD, USD_PT = 1.24, 2.0   # MNQ round trip, $ per point (same as paper_replay / mnq.py)
COLS = ["date", "signal", "side", "entry", "exit", "exit_reason", "gross_R", "net_R",
        "parity", "bars_0930_1030", "engine_sha12", "source", "logged_at_utc"]


class EngineDriftError(RuntimeError):
    pass


def log(msg):
    line = f"{dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def engine_sha(path=None):
    """sha256 of the engine with CRLF folded to LF (git autocrlf checks it out as CRLF on Windows)."""
    path = path or ENGINE_PATH
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def assert_frozen(path=None, frozen=FROZEN_SHA256):
    path = path or ENGINE_PATH
    got = engine_sha(path)
    if got != frozen:
        raise EngineDriftError(f"REFUSING TO REPLAY: frozen engine hash changed. path={path} frozen={frozen} got={got}")
    return got


def load_engine():
    for sub in ("v2-t01-orb-1m", "v2-s07-data", "v2-paper-harness"):
        p = str(MAIN / sub)
        if p not in sys.path:
            sys.path.insert(0, p)
    import orb1m
    import paper_replay
    return orb1m, paper_replay


def fetch_yahoo_1m():
    """DataFrame with ts (tz-aware ET, bar open), open, high, low, close. ~7 days of 1m NQ=F."""
    import yfinance as yf
    df = yf.Ticker("NQ=F").history(period="7d", interval="1m")
    if df is None or df.empty:
        raise RuntimeError("yahoo returned no 1m bars")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close"]]
    df["ts"] = df.index.tz_convert(ET)
    return df.reset_index(drop=True)


def session_frame(bars, d):
    ts = bars["ts"]
    mins = ts.dt.hour * 60 + ts.dt.minute
    return bars[(ts.dt.date == d) & (mins >= 570) & (mins <= 660)].copy()


def replay_session(bars, d, orb1m, paper_replay, sha):
    """Returns a CSV row dict for session d, or None if Yahoo has no regular-session bars for it."""
    g = session_frame(bars, d)
    if g.empty:
        return None
    A = orb1m.day_arrays(g)
    present = int(np.sum(~np.isnan(A["open"][:61])))
    if present < 30:     # holiday / closed / junk: not a session
        return None
    rows = paper_replay._one_cell([(str(d), {**A, "contract": "NQ=F"})], sha, orb1m)
    parity = "OK" if present >= MIN_BARS else f"DEGRADED:bars={present}/61"
    base = dict(date=str(d), bars_0930_1030=present, parity=parity, engine_sha12=sha[:12],
                source="yahoo NQ=F 1m", logged_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    if not rows:
        return {**base, "signal": "N", "side": "", "entry": "", "exit": "", "exit_reason": "", "gross_R": "", "net_R": ""}
    r = rows[0]
    cost_R = COMM_USD / (r["stop_R_pts"] * USD_PT)
    return {**base, "signal": "Y", "side": r["dir"], "entry": r["entry_fill_px"], "exit": r["exit_px"],
            "exit_reason": r["exit_reason"], "gross_R": r["gross_R"], "net_R": round(r["gross_R"] - cost_R, 4)}


def read_rows(path=None):
    path = path or CSV_PATH
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_row(row, path=None):
    path = path or CSV_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow(row)


def due_dates(now, logged, only=None):
    """Mon-Thu dates >= START, with their 10:30 window finished, not yet logged."""
    if only:
        return [only]
    out, d = [], START
    while d <= now.date():
        done = now >= dt.datetime.combine(d, dt.time(10, 35), tzinfo=ET)
        if d.weekday() <= 3 and done and str(d) not in logged:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def weekly_line(rows, week_start):
    end = week_start + dt.timedelta(days=7)
    wk = [r for r in rows if week_start <= dt.date.fromisoformat(r["date"]) < end]
    sig = [r for r in wk if r["signal"] == "Y"]
    wr = sum(float(r["net_R"]) for r in sig)
    allsig = [r for r in rows if r["signal"] == "Y"]
    allR = sum(float(r["net_R"]) for r in allsig)
    ok = sum(1 for r in rows if r["parity"] == "OK")
    return (f"OMEN E9 wk{week_start.isocalendar()[1]}: {len(wk)}/4 sessions, {len(sig)} signals, {wr:+.2f}R | "
            f"total {len(rows)} sessions (goal 17), {len(allsig)} trades, {allR:+.2f}R, parity {ok}/{len(rows)}")


def get_topic():
    out = subprocess.run([sys.executable, str(KEYS_PY), "get", "NTFY_TOPIC"], capture_output=True, text=True, timeout=60)
    t = out.stdout.strip()
    if out.returncode != 0 or not t:
        raise RuntimeError("could not read NTFY_TOPIC from the keys vault")
    return t


def push(text, topic=None):
    import requests
    topic = topic or get_topic()
    r = requests.post(f"https://ntfy.sh/{topic}", data=text.encode("utf-8"),
                      headers={"Title": "OMEN E9 forward clock", "Priority": "low", "Tags": "chart_with_upwards_trend"}, timeout=15)
    return r.ok


def maybe_weekly_push(now, rows, no_push, pusher=None, state_path=None):
    """One line per ISO week, on Thursday or Friday, once. Returns the line sent/skipped or None."""
    pusher = pusher or push
    state_path = state_path or STATE_PATH
    week_start = now.date() - dt.timedelta(days=now.date().weekday())
    if now.weekday() not in (3, 4) or not rows:   # Thursday run = last session of the week; Friday = catch-up
        return None
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    key = str(week_start)
    if state.get("last_push_week") == key:
        return None
    line = weekly_line(rows, week_start)
    if no_push:
        log("weekly line (not pushed, --no-push): " + line)
        return line
    try:
        ok = pusher(line)
    except Exception as e:      # never crash the clock over a notification
        log(f"weekly push error: {type(e).__name__}")
        ok = False
    if ok:
        state_path.write_text(json.dumps({"last_push_week": key}))
        log("weekly line pushed: " + line)
    else:
        log("weekly push FAILED (will retry next run)")
    return line


def main(argv=None, fetcher=None, now=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="replay exactly this date (YYYY-MM-DD); never duplicates a logged row")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args(argv)
    fetcher = fetcher or fetch_yahoo_1m
    now = now or dt.datetime.now(ET)
    try:
        sha = assert_frozen()
    except EngineDriftError as e:
        log(str(e))
        return 1
    only = dt.date.fromisoformat(a.date) if a.date else None
    logged = {r["date"] for r in read_rows()}
    todo = due_dates(now, logged, only)
    if todo:
        try:
            bars = fetcher()
        except Exception as e:
            log(f"bar fetch failed: {type(e).__name__}: {e}")
            return 2
        orb1m, paper_replay = load_engine()
        for d in todo:
            row = replay_session(bars, d, orb1m, paper_replay, sha)
            if row is None:
                log(f"{d}: no regular-session bars (holiday or outside Yahoo 7d window), not logged")
                continue
            if str(d) in logged:
                log(f"{d}: already logged, not duplicated")
                continue
            append_row(row)
            logged.add(str(d))
            log(f"{d}: logged signal={row['signal']} netR={row['net_R']} parity={row['parity']}")
    else:
        log("nothing due")
    maybe_weekly_push(now, read_rows(), a.no_push)
    return 0


if __name__ == "__main__":
    sys.exit(main())
