"""Rotating pool of real, liquid NQ sessions for the eye-loop replay.

The loop used to replay one hard-coded day (2026-09-07, Labor Day, about 10% of normal volume) every run.
Now every card comes from its own session, drawn from this pool, and a session is never shown twice.

Pool rules (all checked in tests, no I/O in the pure functions):
  * window   2024-09-27 .. 2026-09-25 (the fit window; 2024-09-26 is skipped like s-matcher does, its
             bars sit next to the reserved 2024-09-25 evening data)
  * liquid   09:30-11:00 volume at least MIN_VOL_RATIO x the window median, and at least MIN_BARS bars
  * unseen   not in used_days(): any session already sent as a card, tapped, skipped, journaled, shown in
             an earlier test run, or one where Austin marked an index ETF (SPY/QQQ/DIA/IWM) in the
             blind marking set (he saw that same tape)
  * order    fixed seeded shuffle of the eligible sessions, so the order does not depend on the day of
             the week and does not change as sessions are used up
"""
from __future__ import annotations

import csv
import json
import random
import re
from pathlib import Path
from typing import Callable, Iterable

FIT_START = "2024-09-27"
FIT_END = "2026-09-25"
MIN_VOL_RATIO = 0.6
MIN_BARS = 85                      # of the 91 one-minute bars 09:30..11:00
SEED = 20261003
# Sessions shown by the old hard-coded replay (09-07) and the endpoint test tap (09-17).
LEGACY_USED = frozenset({"2026-09-07", "2026-09-17"})
INDEX_ETFS = ("SPY", "QQQ", "DIA", "IWM")

_DATE_IN_ID = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")


def date_from_id(card_or_candidate_id: str) -> str | None:
    """'S43-1-20260907' or 'EYE-S43-1-20260907-ab12' -> '2026-09-07'. None if there is no date in it."""
    m = _DATE_IN_ID.search(card_or_candidate_id or "")
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def liquid_sessions(bars, *, start: str = FIT_START, end: str = FIT_END,
                    ratio: float = MIN_VOL_RATIO, min_bars: int = MIN_BARS) -> list[str]:
    """Sorted 'YYYY-MM-DD' sessions in [start, end] that are liquid.

    `bars` has columns date and volume, one row per 1-minute bar from 09:30 to 11:00 (what load_fut
    returns). The median is taken over every session in the window, so a quiet year does not move the bar
    for a busy one."""
    per_day: dict[str, list[float]] = {}
    for d, v in zip(bars["date"], bars["volume"]):
        ds = str(d)[:10]
        if start <= ds <= end:
            per_day.setdefault(ds, []).append(float(v))
    if not per_day:
        return []
    vols = sorted(sum(v) for v in per_day.values())
    mid = len(vols) // 2
    median = vols[mid] if len(vols) % 2 else (vols[mid - 1] + vols[mid]) / 2
    return sorted(d for d, v in per_day.items() if len(v) >= min_bars and sum(v) >= ratio * median)


def _csv_ids(path: Path | None) -> list[str]:
    if not path:
        return []
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return [r.get("candidate_id", "") for r in csv.DictReader(fh)]
    except OSError:
        return []


def _jsonl(path: Path | None) -> list[dict]:
    out = []
    if not path:
        return out
    try:
        for ln in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                if isinstance(r, dict):
                    out.append(r)
            except ValueError:
                continue
    except OSError:
        pass
    return out


def used_days(*, labels_csv: Path | None = None, skips_csv: Path | None = None,
              ledger: Path | None = None, journal: Path | None = None,
              marks_json: Path | None = None) -> set[str]:
    """Every session Austin has already seen or labeled (see the module docstring)."""
    used = set(LEGACY_USED)
    ledger_rows = _jsonl(ledger)
    by_card = {r.get("card_id"): r.get("candidate_id", "") for r in ledger_rows}
    for r in ledger_rows:                                   # a card that was sent
        d = date_from_id(r.get("candidate_id", ""))
        if d:
            used.add(d)
    for cid in _csv_ids(labels_csv) + _csv_ids(skips_csv):  # a tap (blind ids resolve through the ledger)
        d = date_from_id(by_card.get(cid) or cid)
        if d:
            used.add(d)
    for r in _jsonl(journal):
        d = str(r.get("date", ""))[:10]
        if d:
            used.add(d)
    if marks_json:
        try:
            marks = json.loads(Path(marks_json).read_text(encoding="utf-8"))
            used |= {str(m["d"])[:10] for m in marks.get("days", []) if m.get("s") in INDEX_ETFS}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    return used


def pick_sessions(sessions: Iterable[str], used: set[str], n: int, *,
                  usable: Callable[[str], bool] = lambda d: True, seed: int = SEED) -> list[str]:
    """Next `n` sessions: seeded shuffle of the pool, skip used ones and ones `usable` rejects
    (for example, a session with no sendable candidate). Never returns a used session or a repeat."""
    order = sorted(set(sessions))
    random.Random(seed).shuffle(order)
    out: list[str] = []
    for d in order:
        if len(out) >= n:
            break
        if d in used or d in out or not usable(d):
            continue
        out.append(d)
    return out
