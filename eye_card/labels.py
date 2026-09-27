"""Append S / Not S taps to labels.csv. Every row is PAPER."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

FIELDS = ["logged_at", "candidate_id", "label", "mode", "source_ip"]

_lock = Lock()


def append_label(csv_path: str | Path, candidate_id: str, label: str,
                  source_ip: str = "") -> dict:
    if label not in ("S", "notS"):
        raise ValueError(f"bad label {label!r}, expected 'S' or 'notS'")
    row = {
        "logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_id": candidate_id,
        "label": label,
        "mode": "PAPER",
        "source_ip": source_ip,
    }
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not csv_path.exists()
    with _lock:
        with open(csv_path, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if is_new:
                w.writeheader()
            w.writerow(row)
    return row
