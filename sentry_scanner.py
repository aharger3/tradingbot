"""E4 sentry — alert if scanner_status.json goes stale (>15 min) during RTH.

RTH = weekdays 09:30–16:00 ET. If the scanner's heartbeat file is older than
15 min during RTH, post a Discord alert. Exits silently otherwise (cron-style).

Usage:
    py -3.13 sentry_scanner.py            # check + alert if stale
    py -3.13 sentry_scanner.py --dry-run # print what would happen, no post
    py -3.13 sentry_scanner.py --test    # force-fire alert (proves Discord path)
"""
import argparse
import json
import sys
from datetime import time as dtime
from pathlib import Path

from signal_runner import _load_env_file
_load_env_file(Path(__file__).parent / ".env")

from live_scanner import SCANNER_STATUS_PATH, now_et
from discord_bot import DiscordSignalBot

STALE_MIN = 15  # ponytail: const here, promote to config.yaml if more thresholds land
# Watch window = the scanner's trading window (config trading_hours 09:30-11:00),
# not full RTH — the scanner EXITS after 11:00, so alerting until 16:00 just
# spams "stale" every 15 min all afternoon (2026-07-13 incident).
RTH_START = dtime(9, 35)
RTH_END = dtime(11, 10)


def _in_rth(now) -> bool:
    if now.weekday() >= 5:  # Sat/Sun
        return False
    return RTH_START <= now.time() < RTH_END


def staleness() -> tuple:
    """Return (age_minutes:int|None, timestamp_str:str, last_error:str|None).
    age_minutes=None when the file is missing/unreadable."""
    if not SCANNER_STATUS_PATH.exists():
        return None, "", "scanner_status.json missing"
    try:
        data = json.loads(SCANNER_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return None, "", f"unreadable: {type(e).__name__}: {e}"
    ts = data.get("timestamp", "")
    if not ts:
        return None, "", "no timestamp field"
    try:
        from datetime import datetime
        stamp = datetime.fromisoformat(ts)
    except Exception as e:
        return None, ts, f"bad timestamp: {e}"
    if stamp.tzinfo is None:  # assume ET if naive
        from zoneinfo import ZoneInfo
        stamp = stamp.replace(tzinfo=ZoneInfo("America/New_York"))
    age_min = int((now_et() - stamp).total_seconds() // 60)
    return age_min, ts, data.get("last_error")


def build_alert(age_min, ts, last_error, reason: str) -> dict:
    desc = (f"Scanner heartbeat **{age_min if age_min is not None else '?'} min** old"
            f" during RTH — scanner may be down.\n"
            f"last timestamp: `{ts or 'none'}`\n"
            f"last_error: `{last_error or 'none'}`")
    return {"embeds": [{
        "title": "🚨 OMEN Scanner Stale",
        "description": desc,
        "color": 15158332,  # red
        "footer": {"text": f"sentry_scanner · trigger={reason}"},
    }]}


def main():
    p = argparse.ArgumentParser(description="E4 scanner staleness sentry")
    p.add_argument("--dry-run", action="store_true",
                   help="print alert JSON, no post")
    p.add_argument("--test", action="store_true",
                   help="force-fire alert (verifies Discord path, ignores RTH/age)")
    args = p.parse_args()

    now = now_et()
    age_min, ts, last_error = staleness()

    if args.test:
        reason = "test"
        if age_min is None:
            age_min, ts, last_error = 99, ts or "2026-07-13T00:00:00-04:00", last_error
    elif age_min is None:
        reason = "missing-file"
        if not _in_rth(now):
            print("stale(none) but outside RTH — no alert")
            return
    elif age_min < STALE_MIN:
        print(f"fresh ({age_min} min) — no alert")
        return
    elif not _in_rth(now):
        print(f"stale ({age_min} min) but outside RTH — no alert")
        return
    else:
        reason = "stale-during-rth"

    payload = build_alert(age_min, ts, last_error, reason)
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return
    ok = DiscordSignalBot()._post_with_retry(payload)
    print(f"sentry alert ({reason}): {'posted' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
