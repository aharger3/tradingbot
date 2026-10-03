"""eye_report.py -- 4:30pm ET summary of today's eye-loop paper trades.

Reads eye_paper.daily_summary() off the eye loop's own journal (REPLAY-only
file until a live feed lands, see eye-live.md) and pushes one ntfy card.
Paper only; never touches a live journal or places an order.

Usage: python eye_report.py --title-prefix "OMEN REPLAY TEST"
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v3-eye4-paper"))
sys.path.insert(0, str(REPO / "research" / "agent_runs" / "v2-s07-data"))
sys.path.insert(0, str(REPO))

import eye_paper  # noqa: E402

ET = ZoneInfo("America/New_York")
REPLAY_JOURNAL = REPO / "research" / "paper_journal" / "acks_replay.jsonl"


def push(title: str, message: str):
    topic = os.environ.get("NTFY_TOPIC", "aharg-deadlines")
    base = os.environ.get("NTFY_BASE_URL", "https://ntfy.sh")
    url = f"{base.rstrip('/')}/{topic}"
    resp = requests.post(url, data=message.encode(),
                          headers={"Title": title, "Tags": "bar_chart,paper"}, timeout=10)
    return resp.ok, resp.status_code


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="default = today ET")
    ap.add_argument("--journal-path", default=str(REPLAY_JOURNAL))
    ap.add_argument("--title-prefix", default="OMEN REPLAY TEST")
    args = ap.parse_args(argv)

    date = args.date or datetime.now(ET).strftime("%Y-%m-%d")
    summary = eye_paper.daily_summary(date, path=Path(args.journal_path))
    if summary["n"] == 0:
        msg = f"{date}: 0 confirmed trades (no S-taps landed, or replay didn't run)."
    else:
        msg = (f"{date}: {summary['n']} confirmed  mean_r={summary['mean_r']}  "
               f"hit_rate={summary['hit_rate']}  usd={summary['usd']} (paper $)")
    title = f"{args.title_prefix} - daily report"
    ok, status = push(title, msg)
    print(f"report {date}: {msg} -> ntfy ok={ok} status={status}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
