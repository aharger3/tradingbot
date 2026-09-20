"""research/shipped_flags.py -- OMEN 10.0, Austin's 2026-09-20 card: "Adopt
shipped flags into the PAPER engine automatically -- only when $/day
improves AND green months hold."

WHAT THIS OWNS. research/loop_cycle.py's ship stage decides OFF-vs-ON on the
no-regression gate (green months may not fall, $/day may not fall more than
5% -- SWARM.md law 2). That gate is deliberately loose: a flag can ship
under it while still flat or slightly worse on $/day, as long as it is not
worse enough to fail. Auto-adopting a flag into the live PAPER engine is a
STRICTER, separate question -- Austin's own words above -- so it gets its
own verdict, `adopt`, computed here and never conflated with `decision`
("ship"/"hold") in cycles.md.

    adopt = per_day STRICTLY improves AND green months do not fall.

A flag that ships under the looser gate but is flat or worse on $/day
(tonight's BNR_DISPLACEMENT_GATE row: -52 -> -54, hold on the improvement
test) records adopt: False in research/tape/shipped_flags.json and never
touches the paper engine's environment -- it is recorded, not adopted.

WHO CALLS WHAT.
  * `record_ship()` -- called by loop_cycle.py's stage_gate(), once per
    "ship" decision (never for a "hold" -- holding is not a ship), appends
    one row to research/tape/shipped_flags.json.
  * `load_and_apply()` -- called ONLY by the PAPER engine's own start path
    (live_scanner.py, before it imports signal_runner -- see the comment
    there), never by any backtest/research script. Sets env[flag] = value
    for every adopt:True flag, but only when that env var is not already
    set -- an explicit override (a real .env line, an exported shell var,
    or a loop_cycle.py A/B override) always wins, so a human overriding a
    flag on the live box is never silently clobbered.

NEVER imported by backtest_2y.py, signal_runner.py, or any research/*.py rig
that produces a book -- research/test_shipped_flags.py's
baseline-never-reads-shipped-flags check locks this down as a text-level
grep, not just a behavioural test, because the whole point is that the
honest backtest baseline must stay reproducible with or without this file
existing.
"""
from __future__ import annotations

import json
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIPPED_FLAGS_JSON = ROOT / "research" / "tape" / "shipped_flags.json"


def decide_adopt(per_day_before, per_day_after, green_before, green_after) -> bool:
    """Strict improvement rule (Austin, 2026-09-20 card). Stricter than
    loop_cycle.py's own ship gate (which tolerates up to a 5% $/day drop)
    on purpose: shipping a flag behind a backtest ledger entry is one bar,
    changing what the live paper engine trades tonight is a higher one.
    Any missing/non-numeric input adopts nothing rather than raising --
    called from a nightly, unattended path (nightly_loop.py's own rule:
    a bad night must never stop the next one)."""
    try:
        return bool(per_day_after > per_day_before and green_after >= green_before)
    except TypeError:
        return False


def _load_entries(path: Path = SHIPPED_FLAGS_JSON) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def latest_by_flag(entries: list) -> dict:
    """Last entry per flag wins -- same "repairs append" convention as
    build_tape.py's flag_decision() reading cycles.md."""
    out = {}
    for e in entries:
        if isinstance(e, dict) and e.get("flag"):
            out[e["flag"]] = e
    return out


def record_ship(flag: str, value, per_day_before, per_day_after,
                 green_before, green_after, *, when: str = None,
                 path: Path = SHIPPED_FLAGS_JSON) -> dict:
    """Append one row to shipped_flags.json and return it. Called once per
    "ship" decision in loop_cycle.py's stage_gate() -- never for a "hold"."""
    entry = {
        "flag": flag,
        "value": value,
        "date": when or _date.today().isoformat(),
        "per_day_before": per_day_before,
        "per_day_after": per_day_after,
        "green_before": green_before,
        "green_after": green_after,
        "adopt": decide_adopt(per_day_before, per_day_after, green_before, green_after),
    }
    entries = _load_entries(path)
    entries.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return entry


def load_and_apply(env, *, path: Path = SHIPPED_FLAGS_JSON) -> list:
    """Mutate `env` (a MutableMapping -- os.environ in production, a plain
    dict in tests) in place: for every flag whose LATEST shipped_flags.json
    entry has adopt:True, set env[flag] = str(value) UNLESS that key is
    already present in env. Returns the "FLAG=value" strings actually
    applied, for the one-line startup log the caller prints. MUST NOT
    raise -- a missing or corrupt shipped_flags.json applies nothing rather
    than crashing the paper engine's startup."""
    applied = []
    try:
        latest = latest_by_flag(_load_entries(path))
        for flag, entry in latest.items():
            if not entry.get("adopt"):
                continue
            if flag in env:
                continue
            value = str(entry.get("value"))
            env[flag] = value
            applied.append("%s=%s" % (flag, value))
    except Exception:
        return applied
    return applied
