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


# ---- phone taps (S / Not S / Skip) -------------------------------------------------------

TAP_CHOICES = {"s": "S", "nots": "notS", "not s": "notS", "skip": "skip"}


def skips_path(labels_csv: str | Path) -> Path:
    return Path(labels_csv).with_name("skips.csv")


def already_tapped(labels_csv: str | Path, card_id: str) -> bool:
    for p in (Path(labels_csv), skips_path(labels_csv)):
        try:
            with open(p, newline="", encoding="utf-8") as fh:
                if any(r.get("candidate_id") == card_id for r in csv.DictReader(fh)):
                    return True
        except OSError:
            pass
    return False


def record_tap(labels_csv: str | Path, card_id: str, choice: str, source_ip: str = "") -> dict | None:
    """One phone tap -> one row: S / notS in labels.csv, skip in skips.csv (same columns).
    First tap per card wins across both files; a repeat returns None. Raises ValueError on a bad choice."""
    label = TAP_CHOICES.get(str(choice).strip().lower())
    if label is None:
        raise ValueError(f"bad choice {choice!r}")
    path = Path(labels_csv) if label != "skip" else skips_path(labels_csv)
    with _lock:
        if already_tapped(labels_csv, card_id):
            return None
        row = {"logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "candidate_id": card_id, "label": label, "mode": "PAPER", "source_ip": source_ip}
        path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if is_new:
                w.writeheader()
            w.writerow(row)
    return row
