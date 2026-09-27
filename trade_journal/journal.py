"""trade_journal.journal -- one SQLite table for every eye-loop card.

Every phone card the eye loop sends becomes one row, whether Austin tapped S
or not. That is deliberate: the weekly review compares what he TOOK against
what he PASSED ("shadow R" = the honest-fill R the setup would have made had
it been taken), which is the only way to measure whether his eye adds edge.

Paper only. Nothing here places orders. The DB lives under
research/paper_journal/ (gitignored), next to acks*.jsonl.

Columns (table `trades`, primary key (id, mode)):
  id, mode            candidate id (e.g. S11-1-20260917), REPLAY | PAPER | LIVE_PAPER
  session_date        YYYY-MM-DD (market session), iso_week YYYY-Www
  signal_time         HH:MM ET, minutes_after_open int
  instrument          MNQ / NQ / ...
  direction           long | short
  setup               e.g. orb-retest
  engine_grade        S | one-off | two-off   (candidate generator's hint)
  austin_grade        S | not_s | none        (his tap; none = no tap)
  tap_latency_s       seconds card-sent -> tap (NULL if no tap)
  taken               1 iff S tap inside the confirm window AND simulated
  reason              eye_paper reason (confirmed, grade_not_s, late_tap, no_tap, ...)
  management          flat_2r | ladder_4tier
  entry, stop, risk_pts
  r, usd              realised paper R / $ (NULL unless taken)
  shadow_r            R had it been taken (== r when taken; NULL if not simulable)
  screenshot          path of the archived card PNG, relative to the DB folder
  screenshot_sha256
  tags                JSON list, auto (S, eng:, setup:, inst:, dir:, time:) + extra
  notes, created_at
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import date as _date, datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

REPO = Path(__file__).resolve().parents[1]
JOURNAL_DIR = REPO / "research" / "paper_journal"
DB_PATH = JOURNAL_DIR / "journal.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id TEXT NOT NULL,
    mode TEXT NOT NULL,
    session_date TEXT NOT NULL,
    iso_week TEXT NOT NULL,
    signal_time TEXT,
    minutes_after_open INTEGER,
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long','short')),
    setup TEXT NOT NULL,
    engine_grade TEXT,
    austin_grade TEXT NOT NULL CHECK (austin_grade IN ('S','not_s','none')),
    tap_latency_s REAL,
    taken INTEGER NOT NULL CHECK (taken IN (0,1)),
    reason TEXT,
    management TEXT,
    entry REAL,
    stop REAL,
    risk_pts REAL,
    r REAL,
    usd REAL,
    shadow_r REAL,
    screenshot TEXT,
    screenshot_sha256 TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    notes TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (id, mode),
    CHECK (taken = 0 OR r IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS trades_week ON trades (iso_week, mode);
"""

COLUMNS = ("id", "mode", "session_date", "iso_week", "signal_time", "minutes_after_open",
           "instrument", "direction", "setup", "engine_grade", "austin_grade", "tap_latency_s",
           "taken", "reason", "management", "entry", "stop", "risk_pts", "r", "usd", "shadow_r",
           "screenshot", "screenshot_sha256", "tags", "notes", "created_at")

GRADE_BY_PREFIX = {"S": "S", "O": "one-off", "T": "two-off"}


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def iso_week(session_date: str) -> str:
    y, w, _ = _date.fromisoformat(session_date).isocalendar()
    return f"{y}-W{w:02d}"


def time_bucket(minutes_after_open: Optional[int]) -> str:
    if minutes_after_open is None:
        return "unknown"
    if minutes_after_open < 15:
        return "0930-0945"
    if minutes_after_open < 30:
        return "0945-1000"
    if minutes_after_open < 60:
        return "1000-1030"
    return "1030+"


def auto_tags(row: dict) -> list:
    tags = []
    if row.get("austin_grade") == "S":
        tags.append("S")
    if row.get("engine_grade"):
        tags.append(f"eng:{row['engine_grade']}")
    tags.append(f"setup:{row['setup']}")
    tags.append(f"inst:{row['instrument']}")
    tags.append(f"dir:{row['direction']}")
    tags.append(f"time:{time_bucket(row.get('minutes_after_open'))}")
    return tags


def archive_screenshot(png: Optional[Path], session_date: str, cid: str, mode: str,
                       journal_dir: Path) -> tuple:
    """Copy the card PNG into journal_dir/shots/<week>/ so later sends (which
    overwrite eye_card/sent_charts/<id>.png) can't change what was journaled.
    Returns (relative_path, sha256) or (None, None) if the PNG is missing."""
    if png is None or not Path(png).exists():
        return None, None
    dest = journal_dir / "shots" / iso_week(session_date) / f"{mode}_{cid}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(png, dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    return dest.relative_to(journal_dir).as_posix(), sha


def record(con: sqlite3.Connection, *, cid: str, mode: str, session_date: str, instrument: str,
           direction: str, setup: str, engine_grade: Optional[str], austin_grade: str,
           paper_row: dict, shadow_r: Optional[float] = None,
           minutes_after_open: Optional[int] = None, screenshot_png: Optional[Path] = None,
           extra_tags: Iterable[str] = (), notes: Optional[str] = None,
           journal_dir: Optional[Path] = None, now: Optional[datetime] = None) -> dict:
    """Upsert one card. `paper_row` is eye_paper.run_confirmed()'s dict.
    Idempotent on (id, mode): re-recording replaces the row."""
    if direction not in ("long", "short"):
        raise ValueError(f"direction must be long/short, got {direction!r}")
    if austin_grade not in ("S", "not_s", "none"):
        raise ValueError(f"austin_grade must be S/not_s/none, got {austin_grade!r}")
    journal_dir = Path(journal_dir) if journal_dir else Path(con.execute("PRAGMA database_list").fetchone()[2]).parent
    taken = 1 if (paper_row.get("confirmed") and paper_row.get("r") is not None) else 0
    r = paper_row.get("r") if taken else None
    if taken:
        shadow_r = r  # a taken trade's shadow is its real paper R
    entry, stop = paper_row.get("entry"), paper_row.get("stop")
    shot, sha = archive_screenshot(screenshot_png, session_date, cid, mode, journal_dir)
    sig_time = None
    if minutes_after_open is not None:
        sig_time = f"{9 + (30 + minutes_after_open) // 60:02d}:{(30 + minutes_after_open) % 60:02d}"
    row = {
        "id": cid, "mode": mode, "session_date": session_date, "iso_week": iso_week(session_date),
        "signal_time": sig_time, "minutes_after_open": minutes_after_open,
        "instrument": instrument, "direction": direction, "setup": setup,
        "engine_grade": engine_grade, "austin_grade": austin_grade,
        "tap_latency_s": paper_row.get("tap_latency_s"), "taken": taken,
        "reason": paper_row.get("reason"), "management": paper_row.get("management"),
        "entry": entry, "stop": stop,
        "risk_pts": abs(entry - stop) if entry is not None and stop is not None else None,
        "r": r, "usd": paper_row.get("usd") if taken else None,
        "shadow_r": None if shadow_r is None else round(float(shadow_r), 4),
        "screenshot": shot, "screenshot_sha256": sha, "notes": notes,
        "created_at": (now or datetime.now(timezone.utc)).isoformat(),
    }
    tags = auto_tags(row) + [t for t in extra_tags if t]
    row["tags"] = json.dumps(sorted(set(tags), key=tags.index))
    con.execute(f"INSERT OR REPLACE INTO trades ({','.join(COLUMNS)}) "
                f"VALUES ({','.join('?' * len(COLUMNS))})", [row[c] for c in COLUMNS])
    con.commit()
    return row


def rows_for_week(con: sqlite3.Connection, week: str, mode: Optional[str] = None) -> list:
    q = "SELECT * FROM trades WHERE iso_week = ?"
    args = [week]
    if mode:
        q += " AND mode = ?"
        args.append(mode)
    q += " ORDER BY session_date, minutes_after_open, id"
    out = []
    for r in con.execute(q, args):
        d = dict(r)
        d["tags"] = json.loads(d["tags"])
        out.append(d)
    return out


def ingest_acks(con: sqlite3.Connection, acks_jsonl: Path, chart_dir: Path, mode: str = "REPLAY",
                setup: str = "orb-retest", journal_dir: Optional[Path] = None) -> int:
    """Backfill from an eye_paper acks*.jsonl (confirmed trades only -- that
    file never held skipped cards). Engine grade comes from the id prefix
    eye_runner writes (S/O/T + minute)."""
    n = 0
    for line in Path(acks_jsonl).read_text().splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        cid = a["id"]
        head = cid.split("-")[0]
        minute = int(head[1:]) if head[1:].isdigit() else None
        record(con, cid=cid, mode=mode, session_date=a["date"], instrument=a["symbol"],
               direction="long" if a["side"] == 1 else "short", setup=setup,
               engine_grade=GRADE_BY_PREFIX.get(head[:1]), austin_grade="S", paper_row=a,
               minutes_after_open=minute, screenshot_png=Path(chart_dir) / f"{cid}.png",
               journal_dir=journal_dir, notes="backfilled from acks jsonl")
        n += 1
    return n
