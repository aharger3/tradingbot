"""eye_report.py -- 4:30pm ET summary of today's eye-loop paper trades.

Summarises today's rows in the eye loop's own journal (REPLAY-only
file until a live feed lands, see eye-live.md) and pushes one ntfy card.
Paper only; never touches a live journal or places an order.

Usage: python eye_report.py --title-prefix "OMEN REPLAY TEST"
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v3-eye4-paper"))
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v2-s07-data"))
sys.path.insert(0, str(REPO))


ET = ZoneInfo("America/New_York")
REPLAY_JOURNAL = REPO / "research" / "paper_journal" / "acks_replay.jsonl"


def logged_day_summary(day: str, path: Path) -> dict:
    """Paper trades JOURNALED on ET day `day`. Pool-mode replays journal rows under the replayed
    session's own date (a different day every card), so eye_paper.daily_summary(today) would always
    say 0; the row's `ts` is when the tap was scored, which is what 'today' means here."""
    import json
    rows = []
    try:
        for ln in path.read_text().splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            ts = datetime.fromisoformat(r["ts"]).astimezone(ET)
            if "r" in r and ts.strftime("%Y-%m-%d") == day:
                rows.append(r)
    except (OSError, ValueError, KeyError):
        pass
    n = len(rows)
    if not n:
        return {"date": day, "n": 0, "mean_r": None, "hit_rate": None, "usd": 0.0}
    rs = [r["r"] for r in rows]
    return {"date": day, "n": n, "mean_r": round(sum(rs) / n, 4),
            "hit_rate": round(sum(1 for x in rs if x > 0) / n, 4),
            "usd": round(sum(r.get("usd", 0.0) for r in rows), 2)}


def push(title: str, message: str):
    topic = os.environ.get("NTFY_TOPIC", "aharg-ev-eo5zvp")
    base = os.environ.get("NTFY_BASE_URL", "https://ntfy.sh")
    url = f"{base.rstrip('/')}/{topic}"
    resp = requests.post(url, data=message.encode(),
                          headers={"Title": title, "Tags": "bar_chart,paper"}, timeout=10)
    return resp.ok, resp.status_code


def push_retry(title: str, message: str, tries: int = 6, wait_s: float = 20.0, sleep=time.sleep):
    """push(), retried while the network is not up yet. After a reboot the scheduler's catch-up run
    can start before DNS is ready (10-02: 'Failed to resolve ntfy.sh', task result 1)."""
    for i in range(tries):
        try:
            return push(title, message)
        except requests.exceptions.ConnectionError:
            if i == tries - 1:
                raise
            sleep(wait_s)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="default = today ET")
    ap.add_argument("--journal-path", default=str(REPLAY_JOURNAL))
    ap.add_argument("--title-prefix", default="OMEN REPLAY TEST")
    args = ap.parse_args(argv)

    date = args.date or datetime.now(ET).strftime("%Y-%m-%d")
    summary = logged_day_summary(date, Path(args.journal_path))
    if summary["n"] == 0:
        msg = f"{date}: 0 confirmed trades (no S-taps landed, or replay didn't run)."
    else:
        msg = (f"{date}: {summary['n']} confirmed  mean_r={summary['mean_r']}  "
               f"hit_rate={summary['hit_rate']}  usd={summary['usd']} (paper $)")
    title = f"{args.title_prefix} - daily report"
    ok, status = push_retry(title, msg)
    print(f"report {date}: {msg} -> ntfy ok={ok} status={status}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
