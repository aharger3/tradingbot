"""Append-only JSONL files in DATA_DIR. Restart-safe: the cap and the duplicate check read them back.

  candidates.jsonl   every candidate seen (carded or not) with the reason; the source of the S2 candidate pool
  cards_sent.jsonl   cards actually pushed (mode 'live')
  cards_dry.jsonl    cards that WOULD have been pushed (mode 'dry'): kept apart so a dry run never uses the live cap
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import DATA_DIR

CANDIDATES = "candidates.jsonl"
SENT = {"live": "cards_sent.jsonl", "dry": "cards_dry.jsonl"}


def _read(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def candidates(day: str | None = None, data_dir: Path = DATA_DIR) -> list[dict]:
    rows = _read(Path(data_dir) / CANDIDATES)
    return [r for r in rows if day is None or r.get("day") == day]


def seen_keys(day: str, data_dir: Path = DATA_DIR) -> set:
    return {r["key"] for r in candidates(day, data_dir) if "key" in r}


def log_candidate(c: dict, action: str, seen_at: str, data_dir: Path = DATA_DIR) -> None:
    _append(Path(data_dir) / CANDIDATES, {**c, "action": action, "seen_at": seen_at})


def cards(mode: str, day: str | None = None, data_dir: Path = DATA_DIR) -> list[dict]:
    rows = _read(Path(data_dir) / SENT[mode])
    return [r for r in rows if day is None or r.get("day") == day]


def n_sent(mode: str, day: str, data_dir: Path = DATA_DIR) -> int:
    return len(cards(mode, day, data_dir))


def log_card(mode: str, row: dict, data_dir: Path = DATA_DIR) -> None:
    _append(Path(data_dir) / SENT[mode], row)
