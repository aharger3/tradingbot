"""Entry point.

  python -m stock_cards.run_day                    # the scheduled task: today's morning, Mon-Thu, 09:36-11:01 ET
  python -m stock_cards.run_day --replay 2026-10-02 --ignore-weekday    # dry run on a stored session, sends nothing

Live mode only pushes if DATA_DIR/SEND_ENABLED exists (created after Austin subscribes to the topic). Without it the
run is a dry run: every card that would be sent is written to cards_dry.jsonl with its masked payload.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import polygon_feed as pf

from . import alpaca_bars, context, ledger, session
from .config import (DATA_DIR, ET, LOG_DIR, MAX_CARDS_PER_DAY, load_watchlist, send_enabled)
from .policy import schedule_ok


def make_log(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        line = f"[{datetime.now(ET):%Y-%m-%d %H:%M:%S}] {msg}"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        if sys.stdout is not None:
            try:
                print(line, flush=True)
            except Exception:
                pass
    return log


def build_contexts(syms: list[str], day: str, data_dir: Path, log) -> dict:
    prior = context.load_prior(syms, day, data_dir=data_dir)
    ctxs, src = {}, {}
    for s in syms:
        ctxs[s] = context.build_context(prior[s])
        for d, how in ctxs[s].sources.items():
            src[how] = src.get(how, 0) + 1
    thin = [s for s in syms if ctxs[s].pdh is None or len(ctxs[s].sources) < 3]
    log(f"context: {len(syms)} symbols, prior-session sources {src}, thin/missing {thin}")
    return ctxs


def _lock(data_dir: Path, day: str):
    p = data_dir / f"run-{day}.lock"
    if p.exists() and (datetime.now().timestamp() - p.stat().st_mtime) < 3 * 3600:
        return None
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(os.getpid()), encoding="utf-8")
    return p


def run_live_day(day: str, log) -> int:
    ok, why = schedule_ok(datetime.now(ET))
    if not ok:
        log(f"no run: {why}")
        return 0
    lock = _lock(DATA_DIR, day)
    if lock is None:
        log("no run: another run today holds the lock")
        return 0
    try:
        live = send_enabled()
        syms = load_watchlist()
        log(f"day {day} mode={'LIVE (SEND_ENABLED present)' if live else 'DRY (no SEND_ENABLED flag)'} watchlist={len(syms)} cap={MAX_CARDS_PER_DAY}")
        ctxs = build_contexts(syms, day, DATA_DIR, log)
        scan = session.Scan(day, syms, ctxs, session.LiveFetcher(day, syms), live=live, data_dir=DATA_DIR, log=log)
        n = session.run_live(scan)
        if not any(len(pf.rth(c)) for c in scan.last_bars.values()):
            log("no RTH bars all morning: market closed or feed down")
        log(f"done: {n} scans, {ledger.n_sent(scan.mode, day, DATA_DIR)} cards ({scan.mode})")
        return 0
    finally:
        lock.unlink(missing_ok=True)


def run_replay(day: str, ignore_weekday: bool, log, data_root: Path | None = None) -> dict:
    """Dry run of a stored session. Sends nothing, writes to DATA_DIR/replay/<day>/ only."""
    syms = load_watchlist()
    rdir = (data_root or DATA_DIR) / "replay" / day
    if rdir.exists():
        shutil.rmtree(rdir)
    rdir.mkdir(parents=True)
    start = datetime.fromisoformat(day + "T04:00:00").replace(tzinfo=ET)
    end = datetime.fromisoformat(day + "T11:05:00").replace(tzinfo=ET)
    raw = alpaca_bars.fetch_bars(syms, start, end)
    full = {s: alpaca_bars.to_candles(raw.get(s) or []) for s in syms}
    log(f"replay {day}: IEX bars fetched for {sum(1 for s in syms if full[s])} of {len(syms)} symbols, "
        f"RTH bars/sym median {sorted(len(pf.rth(full[s])) for s in syms)[len(syms) // 2]}")
    ctxs = build_contexts(syms, day, rdir, log)
    scan = session.Scan(day, syms, ctxs, session.ReplayFetcher(full), live=False, data_dir=rdir, out_dir=rdir / "charts",
                        log=log, check_schedule=not ignore_weekday)
    for now in session.minute_times(day):
        scan.step(now)
    cands = ledger.candidates(day, rdir)
    by = {}
    for c in cands:
        by[c["action"]] = by.get(c["action"], 0) + 1
    sent = ledger.cards("dry", day, rdir)
    summary = {"day": day, "weekday": datetime.fromisoformat(day).strftime("%a"), "feed": "alpaca-iex",
               "candidates_in_window_or_not": len(cands), "by_action": by, "would_send": [
                   {k: r[k] for k in ("seq", "card_id", "sym", "side", "sig_t", "sig_close_ts", "sent_at", "stop", "entry")}
                   for r in sent]}
    (rdir / "dryrun-summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    log(f"replay summary: {json.dumps(summary['by_action'])}; would-send {len(sent)} cards")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m stock_cards.run_day")
    ap.add_argument("--replay", metavar="YYYY-MM-DD", help="dry-run a stored session instead of running live")
    ap.add_argument("--ignore-weekday", action="store_true", help="replay only: skip the Mon-Thu gate")
    ap.add_argument("--day", help="live only: override today (testing)")
    a = ap.parse_args(argv)
    day = a.replay or a.day or datetime.now(ET).strftime("%Y-%m-%d")
    log = make_log(LOG_DIR / f"{'replay-' if a.replay else 'run-'}{day}.log")
    try:
        if a.replay:
            run_replay(a.replay, a.ignore_weekday, log)
            return 0
        return run_live_day(day, log)
    except Exception as e:
        log(f"FATAL {type(e).__name__}: {str(e)[:200]}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
