"""g214_perfect_marks.py — Analyze S marks by comment presence and content.

Hypothesis (Austin, 2026-09-05): "the ones where im like 'perfect' or dont have
any comments are the higher leverage ones and they likely happen earlier in the day."

Splits S marks into three groups:
  (A) No comment / empty notes
  (B) Comment contains "perfect"/"clean"/"textbook"/"beautiful"/"great" (case-insensitive)
  (C) All other S

Reports per group:
  - Count, share by symbol (index QQQ/SPY/IWM vs single names)
  - Entry time of day (from entry_t, emin, or entry_i mapping)
  - Setup (BR/OCR/84%) where present
  - Engine mean R and win rate on traded days (from bt2y_trades_retest_on.json)
  - Duplicate count (same symbol-day graded twice) and agreement
"""
from __future__ import annotations

import glob
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import grade_read
import build_deck
from universe import INDEX_POOL

INDEX_SYMBOLS = frozenset(INDEX_POOL)
PERFECT_KEYWORDS = {"perfect", "clean", "textbook", "beautiful", "great"}


def _rows(path: str):
    """Yield dict rows from a .jsonl or a .json list."""
    if not os.path.exists(path):
        return
    if path.endswith(".json"):
        try:
            data = json.load(open(path, encoding="utf-8"))
        except ValueError:
            return
        for row in data if isinstance(data, list) else data.values():
            if isinstance(row, dict):
                yield row
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                yield row


def _get_symbol_day(row: dict) -> tuple[str, str] | None:
    """Extract (symbol, day) from a mark row."""
    symbol = row.get("symbol")
    day = row.get("date") or row.get("day")
    if symbol and day:
        return (symbol, day)

    ident = row.get("card_id") or row.get("id") or row.get("card")
    if ident:
        m = re.search(r"(?:^|_)([A-Z][A-Z0-9.\-]{0,7})_(\d{4}-\d{2}-\d{2})(?:_|$)", str(ident))
        if m:
            return (m.group(1), m.group(2))
    return None


def _get_note_text(row: dict) -> str:
    """Extract note text from various possible fields."""
    for key in ["note", "notes", "comment", "comment_text"]:
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()

    answers = row.get("answers")
    if isinstance(answers, dict):
        for key in ["note", "notes", "comment"]:
            val = answers.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip().lower()

    return ""


def _get_entry_time(row: dict) -> str | None:
    """Extract entry time in HH:MM format."""
    if "entry_t" in row and isinstance(row["entry_t"], str):
        t = row["entry_t"]
        if ":" in t:
            return t[:5]
        if len(t) == 4:
            return t[:2] + ":" + t[2:]
        if len(t) >= 5:
            return t[:2] + ":" + t[2:4]

    if "emin" in row:
        emin = row["emin"]
        if isinstance(emin, (int, str)):
            try:
                emin = int(emin)
                h = 9 + (emin // 60)
                m = emin % 60
                return f"{h:02d}:{m:02d}"
            except (ValueError, TypeError):
                pass

    return None


def _get_setup(row: dict) -> str | None:
    """Extract setup type."""
    setup = row.get("setup") or row.get("kind")
    if isinstance(setup, str):
        s = setup.lower()
        if "break" in s or "brt" in s or "br" in s.split("_")[0]:
            return "BR"
        if "ocr" in s or "retest" in s:
            return "OCR"
        if "84" in s or "rule84" in s or "reclaim" in s:
            return "84%"
    return None


def load_trades() -> dict:
    """Load bt2y_trades_retest_on.json.gz, index by (symbol, day)."""
    trades_by_day = defaultdict(list)

    gz_path = os.path.join(ROOT, "research", "bt2y_trades_retest_on.json.gz")
    if not os.path.exists(gz_path):
        return trades_by_day

    try:
        with gzip.open(gz_path, "rt") as f:
            data = json.load(f)
            for trade in data.get("trades", []):
                sym = trade.get("sym")
                day = trade.get("day")
                if sym and day and trade.get("traded"):
                    trades_by_day[(sym, day)].append(trade)
    except Exception as e:
        print(f"Error loading trades: {e}", file=sys.stderr)

    return trades_by_day


def compute_day_stats(trades: list) -> dict:
    """Compute mean R and win rate from a list of trades for one day."""
    if not trades:
        return {}

    r_vals = [t.get("r") for t in trades if isinstance(t.get("r"), (int, float))]
    if r_vals:
        mean_r = sum(r_vals) / len(r_vals)
    else:
        mean_r = None

    out_vals = [t.get("out") for t in trades if isinstance(t.get("out"), str)]
    if out_vals:
        wins = sum(1 for o in out_vals if "win" in o.lower() or "profit" in o.lower())
        win_rate = wins / len(out_vals) if out_vals else None
    else:
        win_rate = None

    return {
        "mean_r": mean_r,
        "win_rate": win_rate,
        "n_trades": len(trades),
    }


def categorize_mark(row: dict) -> str:
    """Categorize a mark as 'no_comment', 'perfect', or 'other'."""
    note = _get_note_text(row)

    if not note:
        return "no_comment"

    note_lower = note.lower()
    if any(kw in note_lower for kw in PERFECT_KEYWORDS):
        return "perfect"

    return "other"


def main():
    """Load all marks, categorize, and report."""
    trades_by_day = load_trades()

    marks_by_category = {
        "no_comment": [],
        "perfect": [],
        "other": [],
    }

    all_s_marks = []
    duplicate_pairs = []

    for path in build_deck.mark_sources():
        for row in _rows(path):
            if not grade_read.is_s(row):
                continue

            sym_day = _get_symbol_day(row)
            if not sym_day:
                continue

            symbol, day = sym_day
            category = categorize_mark(row)
            entry_time = _get_entry_time(row)
            setup = _get_setup(row)
            is_index = symbol in INDEX_SYMBOLS

            mark_obj = {
                "path": path,
                "symbol": symbol,
                "day": day,
                "category": category,
                "entry_time": entry_time,
                "setup": setup,
                "is_index": is_index,
                "row": row,
            }

            marks_by_category[category].append(mark_obj)
            all_s_marks.append((symbol, day, mark_obj))

    for category in marks_by_category:
        marks_by_category[category].sort(key=lambda m: (m["symbol"], m["day"]))

    all_s_marks.sort(key=lambda x: (x[0], x[1]))

    for i in range(len(all_s_marks)):
        for j in range(i + 1, len(all_s_marks)):
            sym1, day1, mark1 = all_s_marks[i]
            sym2, day2, mark2 = all_s_marks[j]
            if sym1 == sym2 and day1 == day2:
                duplicate_pairs.append((mark1, mark2))

    print("Duplicate symbol-days (graded multiple times):", len(duplicate_pairs))
    for m1, m2 in duplicate_pairs:
        cat1 = m1["category"]
        cat2 = m2["category"]
        agree = "✓ same category" if cat1 == cat2 else f"✗ {cat1} vs {cat2}"
        print(f"  {m1['symbol']} {m1['day']}: {agree}")

    for category in ["no_comment", "perfect", "other"]:
        marks = marks_by_category[category]
        print(f"\n=== Category: {category} ===")
        print(f"Count: {len(marks)}")

        index_count = sum(1 for m in marks if m["is_index"])
        print(f"Index (QQQ/SPY/IWM): {index_count}")
        print(f"Single names: {len(marks) - index_count}")

        times = [m["entry_time"] for m in marks if m["entry_time"]]
        if times:
            times_sorted = sorted(times)
            median_time = times_sorted[len(times_sorted) // 2]
            print(f"Entry times available: {len(times)} of {len(marks)}")
            print(f"Time range: {min(times)} to {max(times)}, median: {median_time}")
        else:
            print(f"Entry times available: 0 of {len(marks)}")

        setups = defaultdict(int)
        for m in marks:
            if m["setup"]:
                setups[m["setup"]] += 1
        if setups:
            print(f"Setups: {dict(setups)}")
        else:
            print(f"Setups: not available")

        rs = []
        wins = []
        n_traded_days = 0
        for m in marks:
            trades = trades_by_day.get((m["symbol"], m["day"]))
            if trades:
                n_traded_days += 1
                stats = compute_day_stats(trades)
                if stats.get("mean_r") is not None:
                    rs.append(stats["mean_r"])
                if stats.get("win_rate") is not None:
                    wins.append(stats["win_rate"])

        if n_traded_days > 0:
            print(f"Traded days (in backtest): {n_traded_days} of {len(marks)}")
            if rs:
                mean_r = sum(rs) / len(rs)
                print(f"Engine mean R on those days: {mean_r:.3f}")
            if wins:
                mean_wr = sum(wins) / len(wins)
                print(f"Engine win rate on those days: {mean_wr:.1%}")


if __name__ == "__main__":
    main()
