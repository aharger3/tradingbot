"""omen-v5-session-counter: daily count of unique V5 trading dates.

Reads journal/alpaca-paper.jsonl and journal/signal_log_*.jsonl, counts unique
calendar dates that carry an event/record with arm == "engine" or
arm == "austin", appends {date, count, pct_to_25} to research/tape/v5_progress.json,
and queues a card in research/tape/card_queue.json the first time count >= 25.

Usage:
    python research/v5_session_counter.py            # real run, writes progress file
    python research/v5_session_counter.py --test      # self-check on mock data, no writes
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL_DIR = os.path.join(ROOT, "journal")
ALPACA_PAPER = os.path.join(JOURNAL_DIR, "alpaca-paper.jsonl")
SIGNAL_LOG_GLOB = os.path.join(JOURNAL_DIR, "signal_log_*.jsonl")
TAPE_DIR = os.path.join(ROOT, "research", "tape")
PROGRESS_PATH = os.path.join(TAPE_DIR, "v5_progress.json")
CARD_QUEUE_PATH = os.path.join(TAPE_DIR, "card_queue.json")
TARGET = 25

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _date_from_record(rec: dict, fallback_date: str | None) -> str | None:
    """Best-effort calendar date for one alpaca-paper.jsonl record."""
    ts = rec.get("ts") or rec.get("timestamp")
    if isinstance(ts, str):
        m = _DATE_RE.search(ts)
        if m:
            return m.group(1)
    # candidate_id often embeds the date, e.g. "AAPL_2026-09-11_0952"
    cid = rec.get("candidate_id")
    if isinstance(cid, str):
        m = _DATE_RE.search(cid)
        if m:
            return m.group(1)
    # signal_log filenames carry the date; caller passes it as fallback
    return fallback_date


def collect_trading_dates(alpaca_path: str = ALPACA_PAPER, signal_log_glob: str = SIGNAL_LOG_GLOB) -> set:
    """Return the set of unique dates with an arm=engine or arm=austin record."""
    dates: set[str] = set()

    if os.path.isfile(alpaca_path):
        with open(alpaca_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("arm") not in ("engine", "austin"):
                    continue
                d = _date_from_record(rec, None)
                if d:
                    dates.add(d)

    for path in sorted(glob.glob(signal_log_glob)):
        fname = os.path.basename(path)
        m = _DATE_RE.search(fname)
        file_date = m.group(1) if m else None
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("arm") not in ("engine", "austin"):
                    continue
                d = _date_from_record(rec, file_date)
                if d:
                    dates.add(d)

    return dates


def load_progress(path: str = PROGRESS_PATH) -> list:
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def already_ran_today(progress: list, today: str) -> bool:
    return any(row.get("date") == today for row in progress)


def queue_card(card_queue_path: str, count: int) -> bool:
    """Append a verdict-due card, once. Returns True if a new card was queued."""
    queue = []
    if os.path.isfile(card_queue_path):
        try:
            with open(card_queue_path, "r", encoding="utf-8") as f:
                queue = json.load(f)
            if not isinstance(queue, list):
                queue = []
        except (json.JSONDecodeError, OSError):
            queue = []

    if any(c.get("id") == "v5-verdict-due" for c in queue):
        return False

    queue.append({
        "id": "v5-verdict-due",
        "text": f"V5 verdict due: {count} sessions fired, next: Opus referee",
        "queued_at": datetime.now(timezone.utc).isoformat(),
    })
    os.makedirs(os.path.dirname(card_queue_path), exist_ok=True)
    with open(card_queue_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
    return True


def run(alpaca_path: str = ALPACA_PAPER, signal_log_glob: str = SIGNAL_LOG_GLOB,
        progress_path: str = PROGRESS_PATH, card_queue_path: str = CARD_QUEUE_PATH,
        today: str | None = None) -> dict:
    today = today or date.today().isoformat()
    dates = collect_trading_dates(alpaca_path, signal_log_glob)
    count = len(dates)
    pct_to_25 = round(min(count, TARGET) / TARGET * 100, 1)

    progress = load_progress(progress_path)
    if not already_ran_today(progress, today):
        progress.append({"date": today, "count": count, "pct_to_25": pct_to_25})
        os.makedirs(os.path.dirname(progress_path), exist_ok=True)
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2)

    queued = False
    if count >= TARGET:
        queued = queue_card(card_queue_path, count)

    return {"date": today, "count": count, "pct_to_25": pct_to_25, "queued_card": queued}


def _self_test() -> bool:
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix="v5_session_counter_test_")
    try:
        journal_dir = os.path.join(tmp, "journal")
        tape_dir = os.path.join(tmp, "tape")
        os.makedirs(journal_dir)
        os.makedirs(tape_dir)

        alpaca_path = os.path.join(journal_dir, "alpaca-paper.jsonl")
        rows = [
            {"event": "entry", "ts": "2026-09-01T10:35:00", "arm": "engine"},
            {"event": "entry", "ts": "09:52:00", "arm": "engine", "candidate_id": "AAPL_2026-09-02_0952"},
            {"event": "entry", "ts": "2026-09-02T10:35:00", "arm": "austin"},  # same day as row 2 -> dedup
            {"event": "entry_error", "ts": "2026-09-03T11:07:37"},  # no arm -> excluded
            {"event": "dry_fire", "ts": "2026-09-04T09:00:00", "arm": "other"},  # wrong arm -> excluded
        ]
        with open(alpaca_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

        signal_glob = os.path.join(journal_dir, "signal_log_*.jsonl")
        with open(os.path.join(journal_dir, "signal_log_2026-09-05.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"status": "fired", "arm": "engine"}) + "\n")

        progress_path = os.path.join(tape_dir, "v5_progress.json")
        card_queue_path = os.path.join(tape_dir, "card_queue.json")

        result = run(alpaca_path, signal_glob, progress_path, card_queue_path, today="2026-09-06")
        assert result["count"] == 3, f"expected 3 unique dates, got {result['count']}"
        assert result["queued_card"] is False

        # idempotent: running again for the same "today" must not duplicate the progress row
        run(alpaca_path, signal_glob, progress_path, card_queue_path, today="2026-09-06")
        progress = load_progress(progress_path)
        assert len(progress) == 1, f"expected 1 progress row after re-run, got {len(progress)}"

        # threshold: 25+ unique dates should queue exactly one card
        with open(alpaca_path, "a", encoding="utf-8") as f:
            for i in range(6, 30):
                f.write(json.dumps({"event": "entry", "ts": f"2026-09-{i:02d}T10:00:00", "arm": "engine"}) + "\n")
        result2 = run(alpaca_path, signal_glob, progress_path, card_queue_path, today="2026-09-07")
        assert result2["count"] >= 25, f"expected >=25 unique dates, got {result2['count']}"
        assert result2["queued_card"] is True
        with open(card_queue_path, encoding="utf-8") as f:
            cq = json.load(f)
        assert len(cq) == 1

        # second threshold run must not queue a duplicate card
        result3 = run(alpaca_path, signal_glob, progress_path, card_queue_path, today="2026-09-08")
        assert result3["queued_card"] is False
        with open(card_queue_path, encoding="utf-8") as f:
            cq2 = json.load(f)
        assert len(cq2) == 1

        print("PASS: v5_session_counter self-test (dedup, idempotent daily write, card queue at 25)")
        return True
    except AssertionError as e:
        print(f"FAIL: {e}")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if "--test" in sys.argv:
        ok = _self_test()
        sys.exit(0 if ok else 1)
    out = run()
    print(json.dumps(out))
