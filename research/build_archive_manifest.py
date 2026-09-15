"""Freeze data_archive's state INSIDE THE PINNED WINDOW -- every symbol's
first/last in-window session, in-window session count and a content hash over
only those sessions -- into research/tape/archive_manifest_<date>.json.

WHY WINDOW-SCOPED. research/tape/cycles.md (C1/C4/C5, 2026-09-13) found the
2026-09-05 baseline's window cannot be reproduced even with --start/--end
pinned: individual symbols' archives have been backfilled piecemeal since the
baseline build. The first manifest (2026-09-13) hashed each symbol's WHOLE
archive file, which fixed that -- but research/daily_fetch.py legitimately
appends new sessions after the pinned window's end date every weekday, and
that also moves the whole-file hash, tripping the guard on every cycle for a
change nobody made inside the window. A session dated after the pinned end is
not drift; it's daily_fetch doing its job. So the manifest now hashes ONLY
the sessions with start <= date <= end from research/tape/loop.json's pinned
window -- a session appended after the window is invisible to it by design,
and a session mutated or removed INSIDE the window still trips the guard.

`backtest_2y.py --manifest PATH` calls `check(PATH)` before it builds anything
and refuses to run (exit 2) if any symbol's in-window hash has moved, unless
`--allow-drift` is also passed. This is the ONE place both sides of that
check live -- do not re-hash an archive file anywhere else.

    python research/build_archive_manifest.py [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--out PATH]

--start/--end default to research/tape/loop.json's rebuild.args window.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import universe                                    # noqa: E402

ARCHIVE = ROOT / "data_archive"
LOOP_JSON = ROOT / "research" / "tape" / "loop.json"


def default_window() -> tuple[str, str]:
    """The pinned window backtest_2y.py's active baseline rebuild uses,
    read off research/tape/loop.json's rebuild.args (--start/--end)."""
    data = json.loads(LOOP_JSON.read_text(encoding="utf-8"))
    rebuild_args = data["rebuild"]["args"]
    start = rebuild_args[rebuild_args.index("--start") + 1]
    end = rebuild_args[rebuild_args.index("--end") + 1]
    return start, end


def symbol_manifest(sym: str, start: str, end: str) -> dict | None:
    """first/last in-window session, in-window session count and a combined
    content hash over ONLY the sessions with start <= date <= end -- None if
    the symbol has no archived days in that window. A session dated after
    `end` (daily_fetch's legitimate appends) is not read at all, by design.
    The hash folds in every in-window file's name AND bytes, so a session
    inside the window that is added, removed or silently rewritten moves it.
    """
    d = ARCHIVE / sym
    all_files = sorted(d.glob("*.csv")) if d.is_dir() else []
    files = [f for f in all_files if start <= f.stem <= end]
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode("utf-8"))
        h.update(hashlib.sha256(f.read_bytes()).digest())
    days = [f.stem for f in files]
    return {"first": days[0], "last": days[-1], "sessions": len(days),
            "hash": h.hexdigest()}


def build(start: str, end: str) -> dict:
    out = {}
    for sym in universe.ALL_SYMS:
        m = symbol_manifest(sym, start, end)
        if m:
            out[sym] = m
    return out


def check(manifest_path: str) -> list[str]:
    """Diff the archive on disk, inside the manifest's own pinned window,
    against a frozen manifest.

    Returns a list of plain-English mismatch lines (empty = archive matches).
    Only checks symbols the manifest names -- a symbol added to the universe
    after the freeze is not a drift, it's new coverage. A session dated after
    the manifest's `window.end` is never looked at, so daily_fetch.py's
    routine appends past the pinned end never trip this.
    """
    frozen_doc = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    window = frozen_doc["window"]
    start, end = window["start"], window["end"]
    frozen = frozen_doc["symbols"]
    now = build(start, end)
    problems = []
    for sym, want in frozen.items():
        got = now.get(sym)
        if got is None:
            problems.append(f"{sym}: archive missing entirely in-window (manifest had "
                            f"{want['sessions']} sessions {want['first']}..{want['last']})")
        elif got["hash"] != want["hash"]:
            problems.append(f"{sym}: {want['first']}..{want['last']} "
                            f"({want['sessions']} in-window sessions) -> "
                            f"{got['first']}..{got['last']} ({got['sessions']} in-window sessions)")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", default=None,
                    help="YYYY-MM-DD, pinned window start (default: "
                         "research/tape/loop.json's rebuild.args)")
    ap.add_argument("--end", default=None,
                    help="YYYY-MM-DD, pinned window end (default: "
                         "research/tape/loop.json's rebuild.args)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    start, end = args.start, args.end
    if start is None or end is None:
        d_start, d_end = default_window()
        start = start or d_start
        end = end or d_end
    today = date.today().isoformat()
    manifest = {"generated": today, "window": {"start": start, "end": end},
                "symbols": build(start, end)}
    out = Path(args.out) if args.out else ROOT / "research" / "tape" / f"archive_manifest_{today}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out} -- {len(manifest['symbols'])} symbols, window {start}..{end}")


if __name__ == "__main__":
    main()
