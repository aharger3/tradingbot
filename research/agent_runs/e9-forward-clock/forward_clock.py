"""E9 forward shadow clock (omen-canon section 5, row E9). Paper only, no orders, no rule edits.

Replays each NEW Mon-Thu NQ session (2026-10-01 onward) through the FROZEN mantra
(v2-t01-orb-1m/orb1m.py via v2-paper-harness/paper_replay._one_cell: OR5, displacement >= 1 ATR,
wick retest, strong trigger, 2R, flat 10:30, same-bar = stop) and appends one row per session to
forward-clock.csv. Bar source: Yahoo Finance NQ=F 1-minute bars through yfinance (free; the same
source as futures_feed.py; Yahoo keeps ~7 days of 1m, so a missed night is caught up next run).

The replay is T+1 style: it runs after the bell on bars that are already final, never live.

data_ok column = the four frozen files match their pinned hashes (CRLF-normalised) AND >= 57 of 61
one-minute bars exist for 09:30-10:30. Anything else is DEGRADED and said so; the row is still logged.
It is a data-quality flag, NOT signal parity.

signal_match column = real signal parity: once the paid archive covers a logged date, that date is
replayed on the archive and the row gets Y when side and entry minute agree with the Yahoo replay (or
both have no signal), N otherwise. Blank = the archive does not cover the date yet. Gate: >= 95% match.

Frozen files (orb1m.py, paper_replay.py, omen_data.py, engine_lock.py) are hash-pinned; the clock
refuses to run on drift. Committed copies live in frozen_backup/ so a git clean in the main checkout
cannot lose them.

Weekly line: ONE summary line per ISO week goes to the ntfy topic named NTFY_TOPIC in the keys vault
(read via keys.py get; the value is never printed or logged). Sent on the Thu/Fri run, or on the next run
of any weekday if state has no push recorded for the previous week.

Rollover: Yahoo's NQ=F switches to the next NQ contract in mid-December (and mid Mar/Jun/Sep). Prices
shift by the calendar spread across that day. The replay is intra-session so signals are unaffected,
but expect a price gap vs the archive around it.

Usage:
    python forward_clock.py                 # catch up every unlogged Mon-Thu session, back-fill signal_match, push if due
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
HERE = Path(__file__).resolve().parent
BACKUP_DIR = HERE / "frozen_backup"
MAIN = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
ENGINE_PATH = MAIN / "v2-t01-orb-1m" / "orb1m.py"
FROZEN_SHA256 = "bafd7ce4e4f69250c0cef80acdbd26057ee04a6a658c95b11ed92bba08bc8ef1"  # == engine_lock.FROZEN_SHA256 (LF-normalised)
# Every frozen file the replay imports, pinned by sha256 after CRLF->LF. Drift in any one = refuse to run.
PINS = {
    ENGINE_PATH: FROZEN_SHA256,
    MAIN / "v2-paper-harness" / "paper_replay.py": "a84a35e1d350105daedfa8537d00fec01db8cfcd899c6c33a8af293289543556",
    MAIN / "v2-s07-data" / "omen_data.py": "d8c0c6ed92113bf6c1fdf0d6b4e4a20dc56038d2cc5e55403e1a5d35ac878d46",
    MAIN / "v2-paper-harness" / "engine_lock.py": "9ef5fc18149e9e32b397267d8ec3518b30c92df059b1ec1bd59fce628c9d8b4c",
}
OUT_DIR = Path(r"C:\Users\aharg\Desktop\life-plan\07-money\omen\night-1003")
CSV_PATH = OUT_DIR / "forward-clock.csv"
STATE_PATH = OUT_DIR / "forward-clock.state.json"
LOG_PATH = OUT_DIR / "forward-clock.log"
KEYS_PY = Path(r"C:\Users\aharg\.claude\sync-setup\keys.py")
START = dt.date(2026, 10, 1)
MIN_BARS = 57          # of 61 one-minute bars 09:30..10:30 inclusive
COMM_USD, USD_PT = 1.24, 2.0   # MNQ round trip, $ per point (same as paper_replay / mnq.py)
GOAL_SESSIONS = 17
# E9 pass test, LOCKED in night-1003/prereg-E9.md before session 17: 5th/95th percentile of summed net_R
# over 17 sessions (day bootstrap of the frozen in-sample replay; see e9_band.py for seed and draws).
BAND_LO, BAND_HI = -3.1276, 5.8555
SOURCE = "yahoo NQ=F 1m (front contract; Yahoo rolls to the next NQ contract mid-Dec)"
COLS = ["date", "signal", "side", "entry_min", "entry", "exit", "exit_reason", "gross_R", "net_R",
        "data_ok", "bars_0930_1030", "engine_sha12", "source", "signal_match", "logged_at_utc"]


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
    """sha256 of the file with CRLF folded to LF (git autocrlf checks it out as CRLF on Windows)."""
    path = path or ENGINE_PATH
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def assert_frozen(path=None, frozen=FROZEN_SHA256):
    path = path or ENGINE_PATH
    got = engine_sha(path)
    if got != frozen:
        raise EngineDriftError(f"REFUSING TO REPLAY: frozen engine hash changed. path={path} frozen={frozen} got={got}")
    return got


def assert_pins(pins=None):
    """All pinned frozen files must match (CRLF folded). Returns the orb1m engine sha. Raises on drift or loss."""
    pins = pins or PINS
    bad = []
    for path, want in pins.items():
        try:
            got = engine_sha(path)
        except OSError as e:
            bad.append(f"{path.name}: unreadable ({type(e).__name__})")
            continue
        if got != want:
            bad.append(f"{path.name}: frozen={want[:12]} got={got[:12]}")
    if bad:
        raise EngineDriftError("REFUSING TO REPLAY: frozen file drift: " + "; ".join(bad)
                               + f". Known-good copies: {BACKUP_DIR}")
    return pins.get(ENGINE_PATH, FROZEN_SHA256)


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
    data_ok = "OK" if present >= MIN_BARS else f"DEGRADED:bars={present}/61"
    base = dict(date=str(d), bars_0930_1030=present, data_ok=data_ok, engine_sha12=sha[:12],
                source=SOURCE, signal_match="",
                logged_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    if not rows:
        return {**base, "signal": "N", "side": "", "entry_min": "", "entry": "", "exit": "", "exit_reason": "",
                "gross_R": "", "net_R": ""}
    r = rows[0]
    cost_R = COMM_USD / (r["stop_R_pts"] * USD_PT)
    return {**base, "signal": "Y", "side": r["dir"], "entry_min": r["entry_bar_min"], "entry": r["entry_fill_px"],
            "exit": r["exit_px"], "exit_reason": r["exit_reason"], "gross_R": r["gross_R"],
            "net_R": round(r["gross_R"] - cost_R, 4)}


def archive_signal(archive, d, orb1m, paper_replay, sha):
    """Replay date d on the paid archive. None if the archive does not cover d; else {signal, side, entry_min}."""
    g = archive[archive["date"] == d][["ts", "open", "high", "low", "close"]].reset_index(drop=True)
    if g.empty:
        return None
    A = orb1m.day_arrays(g)
    if int(np.sum(~np.isnan(A["open"][:61]))) < 30:
        return None
    rows = paper_replay._one_cell([(str(d), {**A, "contract": "archive"})], sha, orb1m)
    if not rows:
        return {"signal": "N", "side": "", "entry_min": ""}
    return {"signal": "Y", "side": rows[0]["dir"], "entry_min": rows[0]["entry_bar_min"]}


def match_flag(row, ref):
    """Y when the archive replay agrees with the logged (Yahoo) replay on signal, side and entry minute."""
    if ref is None:
        return ""
    if row["signal"] != ref["signal"]:
        return "N"
    if ref["signal"] == "Y" and (row["side"] != ref["side"] or str(row["entry_min"]) != str(ref["entry_min"])):
        return "N"
    return "Y"


def load_archive_bars():
    from omen_data import load_fut
    return load_fut("MNQ", "09:30", "11:01")


def fill_signal_match(rows, orb1m, paper_replay, sha, archive_loader=None):
    """Fill blank signal_match cells whose date the archive now covers. Mutates rows; returns number filled."""
    pending = [r for r in rows if not r.get("signal_match")]
    if not pending:
        return 0
    try:
        archive = (archive_loader or load_archive_bars)()
    except Exception as e:      # archive missing/unreadable must never stop the clock
        log(f"signal parity: archive not readable ({type(e).__name__}), skipped")
        return 0
    filled = 0
    for r in pending:
        ref = archive_signal(archive, dt.date.fromisoformat(r["date"]), orb1m, paper_replay, sha)
        flag = match_flag(r, ref)
        if flag:
            r["signal_match"] = flag
            filled += 1
            log(f"{r['date']}: signal parity vs archive = {flag}")
    return filled


def read_rows(path=None):
    path = path or CSV_PATH
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if "parity" in r:           # schema v1 called data_ok "parity"
            r["data_ok"] = r.pop("parity")
        for c in COLS:
            r.setdefault(c, "")
    return rows


def write_rows(rows, path=None):
    """Rewrite the whole CSV atomically (schema migration and signal_match back-fill)."""
    path = path or CSV_PATH
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def migrate_csv(path=None):
    """If the file still has an old header (e.g. a parity column), rewrite it with the current columns."""
    path = path or CSV_PATH
    if not path.exists():
        return False
    with path.open(newline="", encoding="utf-8") as f:
        head = next(csv.reader(f), [])
    if head == COLS:
        return False
    write_rows(read_rows(path), path)
    return True


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


def band_text(rows):
    if len(rows) < GOAL_SESSIONS or BAND_LO is None:
        return ""
    first = sorted(rows, key=lambda r: r["date"])[:GOAL_SESSIONS]
    tot = sum(float(r["net_R"]) for r in first if r["signal"] == "Y")
    inside = "INSIDE" if BAND_LO <= tot <= BAND_HI else "OUTSIDE"
    return f" | first-{GOAL_SESSIONS} paper {tot:+.2f}R {inside} band [{BAND_LO:+.2f},{BAND_HI:+.2f}]"


def weekly_line(rows, week_start):
    end = week_start + dt.timedelta(days=7)
    wk = [r for r in rows if week_start <= dt.date.fromisoformat(r["date"]) < end]
    sig = [r for r in wk if r["signal"] == "Y"]
    wr = sum(float(r["net_R"]) for r in sig)
    allsig = [r for r in rows if r["signal"] == "Y"]
    allR = sum(float(r["net_R"]) for r in allsig)
    ok = sum(1 for r in rows if r["data_ok"] == "OK")
    comp = [r for r in rows if r.get("signal_match") in ("Y", "N")]
    hit = sum(1 for r in comp if r["signal_match"] == "Y")
    sm = (f"signal match {hit}/{len(comp)} ({hit / len(comp):.0%}, gate 95%)" if comp
          else "signal match 0/0 (archive lags)")
    return (f"OMEN E9 wk{week_start.isocalendar()[1]}: {len(wk)}/4 sessions, {len(sig)} signals, {wr:+.2f}R | "
            f"total {len(rows)} sessions (goal {GOAL_SESSIONS}), {len(allsig)} trades, {allR:+.2f}R | "
            f"data_ok {ok}/{len(rows)} | {sm}{band_text(rows)}")


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
    """One line per ISO week. This week's line goes out on the Thu/Fri run; the PREVIOUS week's line also goes
    out on the next run of any weekday when state has no push recorded for it. Returns lines sent/shown."""
    pusher = pusher or push
    state_path = state_path or STATE_PATH
    if not rows:
        return []
    this_ws = now.date() - dt.timedelta(days=now.date().weekday())
    prev_ws = this_ws - dt.timedelta(days=7)
    first_ws = START - dt.timedelta(days=START.weekday())
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    done = set(state.get("pushed_weeks", []))
    if state.get("last_push_week"):      # state schema v1
        done.add(state["last_push_week"])
    todo = []
    if prev_ws >= first_ws and str(prev_ws) not in done:
        todo.append(prev_ws)
    if now.weekday() in (3, 4) and str(this_ws) not in done:
        todo.append(this_ws)
    sent = []
    for ws in todo:
        line = weekly_line(rows, ws)
        if no_push:
            log("weekly line (not pushed, --no-push): " + line)
            sent.append(line)
            continue
        try:
            ok = pusher(line)
        except Exception as e:      # never crash the clock over a notification
            log(f"weekly push error: {type(e).__name__}")
            ok = False
        if ok:
            done.add(str(ws))
            state_path.write_text(json.dumps({"pushed_weeks": sorted(done)}))
            log("weekly line pushed: " + line)
            sent.append(line)
        else:
            log("weekly push FAILED (will retry next run)")
    return sent


def main(argv=None, fetcher=None, now=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="replay exactly this date (YYYY-MM-DD); never duplicates a logged row")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args(argv)
    fetcher = fetcher or fetch_yahoo_1m
    now = now or dt.datetime.now(ET)
    try:
        sha = assert_pins()
    except EngineDriftError as e:
        log(str(e))
        return 1
    migrate_csv()
    only = dt.date.fromisoformat(a.date) if a.date else None
    logged = {r["date"] for r in read_rows()}
    todo = due_dates(now, logged, only)
    orb1m, paper_replay = load_engine()
    rc = 0
    bars = None
    if todo:
        try:
            bars = fetcher()
        except Exception as e:
            log(f"bar fetch failed: {type(e).__name__}: {e}")
            rc = 2          # still back-fill signal_match and push a pending weekly line below
    else:
        log("nothing due")
    for d in (todo if bars is not None else []):
        row = replay_session(bars, d, orb1m, paper_replay, sha)
        if row is None:
            log(f"{d}: no regular-session bars (holiday or outside Yahoo 7d window), not logged")
            continue
        if str(d) in logged:
            log(f"{d}: already logged, not duplicated")
            continue
        append_row(row)
        logged.add(str(d))
        log(f"{d}: logged signal={row['signal']} netR={row['net_R']} data_ok={row['data_ok']}")
    rows = read_rows()
    if fill_signal_match(rows, orb1m, paper_replay, sha):
        write_rows(rows)
    maybe_weekly_push(now, rows, a.no_push)
    return rc


if __name__ == "__main__":
    sys.exit(main())
