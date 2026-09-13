"""Freeze data_archive's current state -- every symbol's first/last session,
session count and a content hash -- into research/tape/archive_manifest_<date>.json.

WHY. research/tape/cycles.md (C1/C4/C5, 2026-09-13) found the 2026-09-05
baseline's window cannot be reproduced even with --start/--end pinned:
individual symbols' archives have been backfilled piecemeal since the baseline
build (AMZN to 2026-09-10, QQQ to 2026-09-10, CRM to 2026-09-09, and four
weekday sessions -- 2026-08-12, 08-13, 08-24, 08-25 -- filled in for some
symbols but not others, inside the pinned window itself, widening it from 499
to 501 distinct sessions). Fable's ruling the same day: chasing an archive
that keeps moving is not reproducibility, so freeze it as it is today and
re-baseline honestly on that frozen state, rather than pretending the old
fingerprint can still be hit.

`backtest_2y.py --manifest PATH` calls `check(PATH)` before it builds anything
and refuses to run (exit 2) if any symbol's hash has moved, unless
`--allow-drift` is also passed. This is the ONE place both sides of that
check live -- do not re-hash an archive file anywhere else.

    python research/build_archive_manifest.py [--out PATH]
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


def symbol_manifest(sym: str) -> dict | None:
    """first/last session, session count and a combined content hash for one
    symbol's whole archive -- None if the symbol has no archived days at all.
    The hash folds in every file's name AND bytes, so a session added,
    removed or silently rewritten all move it.
    """
    d = ARCHIVE / sym
    files = sorted(d.glob("*.csv")) if d.is_dir() else []
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode("utf-8"))
        h.update(hashlib.sha256(f.read_bytes()).digest())
    days = [f.stem for f in files]
    return {"first": days[0], "last": days[-1], "sessions": len(days),
            "hash": h.hexdigest()}


def build() -> dict:
    out = {}
    for sym in universe.ALL_SYMS:
        m = symbol_manifest(sym)
        if m:
            out[sym] = m
    return out


def check(manifest_path: str) -> list[str]:
    """Diff the archive on disk against a frozen manifest.

    Returns a list of plain-English mismatch lines (empty = archive matches).
    Only checks symbols the manifest names -- a symbol added to the universe
    after the freeze is not a drift, it's new coverage.
    """
    frozen = json.loads(Path(manifest_path).read_text(encoding="utf-8"))["symbols"]
    now = build()
    problems = []
    for sym, want in frozen.items():
        got = now.get(sym)
        if got is None:
            problems.append(f"{sym}: archive missing entirely (manifest had "
                            f"{want['sessions']} sessions {want['first']}..{want['last']})")
        elif got["hash"] != want["hash"]:
            problems.append(f"{sym}: {want['first']}..{want['last']} "
                            f"({want['sessions']} sessions) -> "
                            f"{got['first']}..{got['last']} ({got['sessions']} sessions)")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    today = date.today().isoformat()
    manifest = {"generated": today, "symbols": build()}
    out = Path(args.out) if args.out else ROOT / "research" / "tape" / f"archive_manifest_{today}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out} -- {len(manifest['symbols'])} symbols")


if __name__ == "__main__":
    main()
