"""Append S / Not S taps to labels.csv. Every row is PAPER."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

# `channel` = where the tap came from: "ntfy" (default) or "discord" (fallback card).
FIELDS = ["logged_at", "candidate_id", "label", "mode", "source_ip", "channel"]

_lock = Lock()


def _migrate_header(csv_path: Path) -> None:
    """Pre-channel labels.csv files get the column added (old rows = ntfy)."""
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
        fh.seek(0)
        header = next(csv.reader(fh), [])
    if header == FIELDS:
        return
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r.setdefault("channel", "ntfy")
            r["channel"] = r.get("channel") or "ntfy"
            w.writerow(r)


def append_label(csv_path: str | Path, candidate_id: str, label: str,
                  source_ip: str = "", channel: str = "ntfy") -> dict:
    if label not in ("S", "notS"):
        raise ValueError(f"bad label {label!r}, expected 'S' or 'notS'")
    row = {
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_id": candidate_id,
        "label": label,
        "mode": "PAPER",
        "source_ip": source_ip,
        "channel": channel if channel in ("ntfy", "discord") else "ntfy",
    }
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        is_new = not csv_path.exists() or csv_path.stat().st_size == 0
        if not is_new:
            _migrate_header(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if is_new:
                w.writeheader()
            w.writerow(row)
    return row
