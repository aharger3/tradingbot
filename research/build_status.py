"""build_status.py -- OMEN phone status page (row: nightly status page, 2026-09-20).

Small mobile-first companion to research/build_tape.py's big desktop tape
page. Does NOT duplicate omen-tape.html's tables -- one screen, five status
lines, answering "what did the loop do last night and what's next", meant to
be read on a phone. Pure stdlib (json/re/glob/pathlib/datetime/html) --
no template engine, no external JS; the one chart is inline SVG.

Reads (every source is optional -- a missing file degrades one line to a
placeholder, it never raises):
  research/tape/summary_data.json  -- honest baseline $/day and green months
  research/tape/cycles.md          -- $/day per cycle, for the sparkline
  research/tape/nightly.md         -- last night's receipt row
  research/tape/loop_queue.json    -- rows still queued
  research/tape/shipped_flags.json -- whether last night's "ship" flag was
                                       actually flipped on in code. Added by
                                       a separate builder the same night as
                                       this file -- schema not yet known, so
                                       this reads it defensively and reports
                                       "unknown" rather than guessing wrong.
  journal/alpaca-paper.jsonl       -- V5 paper arm: unique sessions + fills
  journal/bar-deck-*.log           -- last night's homework-deck card count

Writes:
  research/tape/omen-status.html
  C:\\Users\\aharg\\Desktop\\AI-Outputs\\omen\\omen-status.html -- a copy, so
  a dispatcher elsewhere on the box can publish it as an artifact without
  reading inside this repo.

Usage: python research/build_status.py [--out research/tape/omen-status.html]
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import shutil
import sys
from datetime import datetime
from html import escape as esc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TAPE = ROOT / "research" / "tape"
JOURNAL = ROOT / "journal"

SUMMARY_DATA = TAPE / "summary_data.json"
CYCLES_MD = TAPE / "cycles.md"
NIGHTLY_MD = TAPE / "nightly.md"
LOOP_QUEUE = TAPE / "loop_queue.json"
SHIPPED_FLAGS = TAPE / "shipped_flags.json"
ALPACA_PAPER = JOURNAL / "alpaca-paper.jsonl"
BAR_DECK_GLOB = str(JOURNAL / "bar-deck-*.log")

DEFAULT_OUT = TAPE / "omen-status.html"
DISPATCH_COPY = Path(r"C:\Users\aharg\Desktop\AI-Outputs\omen\omen-status.html")

# Fixed schedule facts (not derived from any data file -- this is the
# standing OmenNightlyLoop / sunday_summary.py cadence, not a per-run number).
NEXT_SCHEDULE = "Mon 20:00 loop, Sun 09:00 weekly"
# Static milestone note: no ledger row has ever carried a non-V5 ("legacy")
# fire as of 2026-09-19 (markets closed the weekend this page shipped) --
# Monday 09-21 is the next session it could happen on. Update by hand (or
# make this line data-driven) once the ledger actually shows one.
V5_LEGACY_NOTE = "first legacy fire Mon 09-21"

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_DOLLAR_PAIR_RE = re.compile(r"^(-?[\d.]+)\s*->\s*(-?[\d.]+)$")
_BAR_DECK_CARDS_RE = re.compile(r":\s*(\d+)\s*cards\b")


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path: Path):
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


# ---- headline: the honest baseline -----------------------------------------

def honest_baseline(summary_path: Path = SUMMARY_DATA) -> tuple[int, int, int]:
    """(per_day, green_months, months) from summary_data.json's baseline.whole
    -- the same honest numbers quoted everywhere else in this project. Falls
    back to the known figures (-52/day, 11/25) if the file is missing."""
    data = _read_json(summary_path) or {}
    whole = data.get("baseline", {}).get("whole", {})
    per_day = whole.get("per_day", -52)
    green = whole.get("green_months", 11)
    months = whole.get("months", 25)
    return int(round(per_day)), int(green), int(months)


# ---- sparkline: $/day per cycle, from cycles.md ----------------------------

def cycle_dollars_after(cycles_path: Path = CYCLES_MD) -> list[float]:
    """One $/day-after value per real cycles.md row, oldest first. Skips the
    header, the separator, and every HTML-comment repair/blocked note --
    only lines that parse as a 12-column table row with a numeric
    '<before> -> <after>' $/day cell count (matches research/nightly_loop.py's
    own cycles_md_row() column-count check)."""
    text = _read_text(cycles_path)
    if not text:
        return []
    out: list[float] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) != 12 or parts[0].lower() == "date":
            continue
        m = _DOLLAR_PAIR_RE.match(parts[4])
        if not m:
            continue
        out.append(float(m.group(2)))
    return out


def sparkline_svg(values: list[float], width: int = 320, height: int = 48) -> str:
    if len(values) < 2:
        return ('<svg viewBox="0 0 %d %d" class="spark" role="img" '
                'aria-label="not enough cycles yet"></svg>' % (width, height))
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = i / (n - 1) * (width - 4) + 2
        y = height - 2 - (v - lo) / span * (height - 4)
        pts.append("%.1f,%.1f" % (x, y))
    trend = "good" if values[-1] >= values[0] else "bad"
    return (
        '<svg viewBox="0 0 %d %d" class="spark" role="img" '
        'aria-label="%d cycles, %.0f to %.0f dollars per day">'
        '<polyline points="%s" fill="none" class="spark-%s" stroke-width="2" '
        'stroke-linejoin="round" stroke-linecap="round"/></svg>'
    ) % (width, height, n, lo, hi, " ".join(pts), trend)


# ---- last night: nightly.md's most recent row + shipped_flags.json --------

def last_night_row(nightly_path: Path = NIGHTLY_MD) -> dict | None:
    """The most recently appended row of nightly.md (nightly_loop.py always
    appends, never reorders -- so the last data row is last night's)."""
    text = _read_text(nightly_path)
    if not text:
        return None
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or line.lower().startswith("| date"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) != 6:
            continue
        rows.append(parts)
    if not rows:
        return None
    date, flag, decision, per_day, green, books = rows[-1]
    return {"date": date, "flag": flag, "decision": decision, "per_day": per_day, "green": green}


def adopted_status(flag: str, decision: str, shipped_path: Path = SHIPPED_FLAGS) -> str:
    """'yes'/'no' if shipped_flags.json says so, 'n/a' when last night was not
    a ship, 'unknown' if the file is absent or doesn't mention this flag.

    research/shipped_flags.py (a separate 2026-09-20 row, landing the same
    night as this page) is the real writer: a list of append-only entries
    `{"flag": ..., "adopt": bool, ...}`, one row per "ship" decision, latest
    entry per flag wins (its own latest_by_flag()). This reads that shape
    directly but also tolerates a couple of simpler ones ({"FLAG": true},
    {"FLAG": {"adopt": true}}) in case the schema still moves, and reports
    'unknown' rather than guessing when it doesn't recognize what it read."""
    if decision != "ship":
        return "n/a"
    data = _read_json(shipped_path)
    if data is None:
        return "unknown"
    val = None
    if isinstance(data, dict):
        entry = data.get(flag)
        if isinstance(entry, bool):
            val = entry
        elif isinstance(entry, dict):
            val = entry.get("adopt", entry.get("adopted"))
    elif isinstance(data, list):
        for item in data:  # last matching entry wins (append-only ledger)
            if isinstance(item, dict) and item.get("flag") == flag:
                val = item.get("adopt", item.get("adopted"))
    if val is None:
        return "unknown"
    return "yes" if val else "no"


def last_night_line(nightly_path: Path = NIGHTLY_MD, shipped_path: Path = SHIPPED_FLAGS) -> str:
    row = last_night_row(nightly_path)
    if row is None:
        return "no receipt yet"
    if row["decision"] == "empty":
        return "%s: queue was empty" % row["date"]
    adopted = adopted_status(row["flag"], row["decision"], shipped_path)
    return "%s: %s %s %s, adopted %s" % (row["date"], row["flag"], row["decision"], row["per_day"], adopted)


# ---- queue: loop_queue.json's real (non-example) rows ----------------------

def queue_labels(queue_path: Path = LOOP_QUEUE) -> list[str]:
    data = _read_json(queue_path)
    if not isinstance(data, list):
        return []
    return [c.get("label", c.get("flag", "?")) for c in data
            if isinstance(c, dict) and not c.get("_example") and c.get("flag") and c.get("label")]


def queue_line(queue_path: Path = LOOP_QUEUE) -> str:
    labels = queue_labels(queue_path)
    if not labels:
        return "0 left"
    return "%d left (%s)" % (len(labels), "; ".join(labels))


# ---- V5 paper: unique sessions + real fills, from alpaca-paper.jsonl -------

def _record_date(rec: dict) -> str | None:
    ts = rec.get("ts") or rec.get("timestamp")
    if isinstance(ts, str):
        m = _DATE_RE.search(ts)
        if m:
            return m.group(1)
    cid = rec.get("candidate_id")
    if isinstance(cid, str):
        m = _DATE_RE.search(cid)
        if m:
            return m.group(1)
    return None


def v5_paper_stats(alpaca_path: Path = ALPACA_PAPER) -> tuple[int, int]:
    """(unique sessions, fills). Sessions counts unique calendar dates behind
    an arm=="engine"/"austin" record -- the same dedup research/
    v5_session_counter.py uses to track progress toward its 25-session
    verdict floor. Fills counts booked entries ("event": "entry"), across
    both arms -- dry_fire/entry_error/pass/cancel rows are not fills."""
    text = _read_text(alpaca_path)
    if not text:
        return 0, 0
    sessions: set[str] = set()
    fills = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("event") == "entry":
            fills += 1
        if rec.get("arm") in ("engine", "austin"):
            d = _record_date(rec)
            if d:
                sessions.add(d)
    return len(sessions), fills


def v5_paper_line(alpaca_path: Path = ALPACA_PAPER) -> str:
    sessions, fills = v5_paper_stats(alpaca_path)
    return "%d sessions, %d fills, %s" % (sessions, fills, V5_LEGACY_NOTE)


# ---- bar deck: last night's homework-deck card count -----------------------

def bar_deck_cards(log_glob: str = BAR_DECK_GLOB) -> int | None:
    logs = sorted(glob.glob(log_glob))  # filenames carry YYYY-MM-DD -> lexical sort is chronological
    if not logs:
        return None
    text = _read_text(Path(logs[-1])) or ""
    m = _BAR_DECK_CARDS_RE.search(text)
    return int(m.group(1)) if m else None


def bar_deck_line(log_glob: str = BAR_DECK_GLOB) -> str:
    n = bar_deck_cards(log_glob)
    if n is None:
        return "no deck log found"
    return "%d cards last night (ntfy)" % n


# ---- page -------------------------------------------------------------

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>OMEN status</title>
<style>
  :root {
    --bg: #0b0d10; --fg: #e8e8e8; --dim: #9aa0a6; --card: #14171a;
    --good: #3ddc84; --bad: #ff6b6b; --line: #262a2e;
  }
  @media (prefers-color-scheme: light) {
    :root { --bg: #f7f7f8; --fg: #1b1e21; --dim: #5b6167; --card: #ffffff;
            --good: #178a4c; --bad: #c8372f; --line: #e2e4e7; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 16px; background: var(--bg); color: var(--fg);
         font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  h1 { font-size: 17px; margin: 0 0 6px; color: var(--dim); font-weight: 600; }
  .headline { font-size: 20px; font-weight: 700; margin: 0 0 12px; }
  .headline .green { color: var(--good); font-weight: 700; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
          padding: 12px 14px; margin-bottom: 10px; }
  .label { color: var(--dim); font-size: 11px; text-transform: uppercase;
           letter-spacing: .04em; margin-bottom: 4px; }
  .value { font-size: 15px; word-wrap: break-word; }
  .spark { width: 100%; height: 48px; display: block; }
  .spark-good { stroke: var(--good); }
  .spark-bad { stroke: var(--bad); }
  .yes { color: var(--good); font-weight: 600; }
  .no { color: var(--bad); font-weight: 600; }
  .gen { color: var(--dim); font-size: 12px; margin-top: 14px; text-align: center; }
</style>
</head>
<body>
  <h1>OMEN loop</h1>
  <div class="headline">$/day honest: <b>__PER_DAY__</b> (<span class="green">__GREEN__/__MONTHS__ green</span>)</div>
  <div class="card">__SPARKLINE__</div>
  <div class="card"><div class="label">Last night</div><div class="value">__LAST_NIGHT__</div></div>
  <div class="card"><div class="label">Queue</div><div class="value">__QUEUE__</div></div>
  <div class="card"><div class="label">V5 paper</div><div class="value">__V5_PAPER__</div></div>
  <div class="card"><div class="label">Bar deck</div><div class="value">__BAR_DECK__</div></div>
  <div class="card"><div class="label">Next</div><div class="value">__NEXT__</div></div>
  <div class="gen">generated __GENERATED__</div>
</body>
</html>
"""


def render(sources: dict | None = None) -> str:
    """Build the page HTML. `sources` lets tests point every input at a temp
    fixture instead of the real repo files; omitted keys fall back to the
    real paths in this module."""
    s = sources or {}
    per_day, green, months = honest_baseline(s.get("summary_data", SUMMARY_DATA))
    spark = sparkline_svg(cycle_dollars_after(s.get("cycles_md", CYCLES_MD)))
    last_night = esc(last_night_line(s.get("nightly_md", NIGHTLY_MD), s.get("shipped_flags", SHIPPED_FLAGS)))
    queue = esc(queue_line(s.get("loop_queue", LOOP_QUEUE)))
    v5 = esc(v5_paper_line(s.get("alpaca_paper", ALPACA_PAPER)))
    bar_deck = esc(bar_deck_line(s.get("bar_deck_glob", BAR_DECK_GLOB)))
    generated = datetime.now().isoformat(timespec="seconds").replace("T", " ")

    return (_TEMPLATE
            .replace("__PER_DAY__", str(per_day))
            .replace("__GREEN__", str(green))
            .replace("__MONTHS__", str(months))
            .replace("__SPARKLINE__", spark)
            .replace("__LAST_NIGHT__", last_night)
            .replace("__QUEUE__", queue)
            .replace("__V5_PAPER__", v5)
            .replace("__BAR_DECK__", bar_deck)
            .replace("__NEXT__", esc(NEXT_SCHEDULE))
            .replace("__GENERATED__", generated))


def build(out: str | Path = DEFAULT_OUT, dispatch_copy: str | Path | None = DISPATCH_COPY) -> Path:
    """Rebuild the status page and write it to `out`, then copy it to
    `dispatch_copy` (AI-Outputs, so a dispatcher outside this repo can
    publish it) unless dispatch_copy is None. Pulled out of main() so
    nightly_loop.py and sunday_summary.py can call this in-process."""
    html = render()
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print("wrote %s (%d bytes)" % (out_path, out_path.stat().st_size))

    if dispatch_copy is not None:
        copy_path = Path(dispatch_copy)
        copy_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out_path, copy_path)
        print("copied to %s" % copy_path)

    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--no-dispatch-copy", action="store_true",
                     help="skip the C:\\...\\AI-Outputs\\omen\\ copy (for local testing)")
    args = ap.parse_args()
    build(args.out, None if args.no_dispatch_copy else DISPATCH_COPY)
    return 0


if __name__ == "__main__":
    sys.exit(main())
