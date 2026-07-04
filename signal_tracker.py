"""Signal logging + daily session review"""

import json
from datetime import date
from pathlib import Path
from typing import Optional

SIGNAL_LOG_DIR = Path(__file__).parent / "journal"


def _log_path(date_str: str) -> Path:
    SIGNAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return SIGNAL_LOG_DIR / f"signal_log_{date_str}.jsonl"


def log_signal(
    symbol: str,
    signal_type: str,
    direction: str,
    entry: float,
    stop: float,
    target: float,
    grade: str,
    reason: str,
    stop_width_pct: Optional[float] = None,
    quote_source: str = "estimated",
    status: str = "fired",
    skip_reason: Optional[str] = None,
):
    """Append one signal record to date's jsonl file."""
    record = {
        "status": status,
        "skip_reason": skip_reason,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "symbol": symbol,
        "signal_type": signal_type,
        "direction": direction,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "grade": grade,
        "reason": reason,
        "stop_width_pct": stop_width_pct,
        "quote_source": quote_source,
    }
    path = _log_path(date.today().isoformat())
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def review_session(date_str: str) -> dict:
    """Count signals by type/grade/symbol for daily review."""
    path = _log_path(date_str)
    if not path.exists():
        return {"date": date_str, "total": 0, "fired": 0, "skipped": 0,
                "by_type": {}, "by_grade": {}, "by_symbol": {}, "by_skip_reason": {}}

    by_type = {}
    by_grade = {}
    by_symbol = {}
    by_skip_reason = {}
    total = fired = skipped = 0

    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        # pre-status records (before 2026-07-03) have no status field -> fired
        if r.get("status", "fired") == "skipped":
            skipped += 1
            sr = r.get("skip_reason") or "?"
            by_skip_reason[sr] = by_skip_reason.get(sr, 0) + 1
        else:
            fired += 1
        st = r.get("signal_type", "unknown")
        by_type[st] = by_type.get(st, 0) + 1
        g = r.get("grade", "?")
        by_grade[g] = by_grade.get(g, 0) + 1
        s = r.get("symbol", "?")
        by_symbol[s] = by_symbol.get(s, 0) + 1

    return {
        "date": date_str,
        "total": total,
        "fired": fired,
        "skipped": skipped,
        "by_type": by_type,
        "by_grade": by_grade,
        "by_symbol": by_symbol,
        "by_skip_reason": by_skip_reason,
    }
