"""nightly_loop.py -- the schedule research/loop_cycle.py never had.

WHY. research/loop_cycle.py (O4) does one cycle when invoked -- build both
arms, gate them, append a row to research/tape/cycles.md. All 9 rows there
were fired by hand; nothing ever called it on its own. This is the part
that calls it: pop the top real candidate off research/tape/loop_queue.json,
run it through `loop_cycle.py --stage all`, and append exactly one receipt
line to research/tape/nightly.md. research/nightly_loop.cmd (scheduled task
OmenNightlyLoop) is the thin trigger that runs this every night; all the
logic lives here, matching this repo's own daily_run.cmd / daily_fetch.py
split.

NEVER --allow-drift, never a live order, never touches signal_runner.py --
this only ever calls loop_cycle.py, which only ever builds backtest books.

MUST NOT FAIL THE TASK. An empty queue, a held cycle, a blocked cycle
(loop_cycle.py's OFF-arm-vs-baseline check) or an unexpected crash all still
produce exactly one valid receipt row and a zero exit code -- a bad night
must never stop Task Scheduler's next run.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TAPE = ROOT / "research" / "tape"
QUEUE = TAPE / "loop_queue.json"
NIGHTLY = TAPE / "nightly.md"
LOOP_CONFIG = TAPE / "loop.json"

HEADER = ("| date | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id |\n"
          "|---|---|---|---|---|---|\n")

EMPTY_ROW = "| %s | - | empty | - | - | - |\n"


def load_queue() -> list:
    if not QUEUE.exists():
        return []
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def is_real(candidate) -> bool:
    """loop_queue.json ships one commented-out shape example (an '_example'
    marker instead of real work) -- only a dict with a real flag/on/label and
    no '_example' key counts as queued work."""
    return (isinstance(candidate, dict) and not candidate.get("_example")
            and bool(candidate.get("flag")) and "on" in candidate and bool(candidate.get("label")))


def pop_top(queue: list):
    """(candidate, remaining_queue) -- the first real entry, everything else
    (including any example rows) left in place."""
    for i, c in enumerate(queue):
        if is_real(c):
            return c, queue[:i] + queue[i + 1:]
    return None, queue


def book_id_for(path_str: str | None) -> str:
    if not path_str:
        return "-"
    path = Path(path_str)
    if not path.exists():
        return "-"
    from research import book_stamp
    if path.name.endswith(".gz"):
        import gzip
        with gzip.open(path, "rt", encoding="utf-8") as f:
            b = json.load(f)
    else:
        b = json.loads(path.read_text(encoding="utf-8"))
    return b.get("meta", {}).get("stamp", {}).get("book_id") or book_stamp.book_id(b.get("trades", []))


def parse_result(stdout: str) -> dict:
    """loop_cycle.py's last stdout line is always one json.dumps(...) block
    (the blocked dict on a build-stage block, the full gate dict otherwise);
    nothing else it prints contains a '{'."""
    if "{" not in stdout:
        return {}
    try:
        return json.loads(stdout[stdout.rfind("{"):])
    except json.JSONDecodeError:
        return {}


def run_candidate(candidate: dict) -> str:
    flag, on, label = candidate["flag"], str(candidate["on"]), candidate["label"]
    today = date.today().isoformat()
    cmd = [sys.executable, str(ROOT / "research" / "loop_cycle.py"),
           "--config", str(LOOP_CONFIG), "--flag", flag, "--on", on,
           "--label", label, "--stage", "all"]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    result = parse_result(proc.stdout)

    if result.get("decision") == "blocked":
        # the ON arm is never built when blocked -- no on_book_id to report.
        return "| %s | %s | hold | - | - | %s -> - |\n" % (
            today, flag, result.get("off_book_id", "-"))

    decision = result.get("decision")
    if decision not in ("ship", "hold"):
        return "| %s | %s | hold | - | - | - -> - |\n" % (today, flag)

    before, after = result.get("before_whole", {}), result.get("after_whole", {})
    off_id = book_id_for(result.get("off_book"))
    on_id = book_id_for(result.get("on_book"))
    return "| %s | %s | %s | %s -> %s | %s -> %s | %s -> %s |\n" % (
        today, flag, decision,
        before.get("per_day", "-"), after.get("per_day", "-"),
        before.get("months_green", "-"), after.get("months_green", "-"),
        off_id, on_id)


def main() -> int:
    queue = load_queue()
    candidate, remaining = pop_top(queue)

    if candidate is None:
        line = EMPTY_ROW % date.today().isoformat()
    else:
        QUEUE.write_text(json.dumps(remaining, indent=2) + "\n", encoding="utf-8")
        try:
            line = run_candidate(candidate)
        except Exception as exc:  # a bad night must still produce a row and exit 0
            print("nightly_loop.py: %s: %r" % (candidate.get("flag", "?"), exc), file=sys.stderr)
            line = "| %s | %s | hold | - | - | - -> - |\n" % (
                date.today().isoformat(), candidate.get("flag", "-"))

    if not NIGHTLY.exists():
        NIGHTLY.write_text("# nightly loop receipts\n\n" + HEADER, encoding="utf-8")
    with open(NIGHTLY, "a", encoding="utf-8") as f:
        f.write(line)

    print(line.strip())
    rebuild_tape_page()
    return 0


def rebuild_tape_page() -> None:
    """Regenerate research/tape/omen-tape.html so its Nightly receipts
    section shows tonight's row without waiting for someone to run
    build_tape.py by hand. MUST NOT FAIL THE TASK -- same rule as the rest
    of this file: a broken/slow tape-page rebuild is logged and swallowed,
    never allowed to turn a good night's receipt into a bad exit code."""
    try:
        from research import build_tape
        build_tape.build()
    except Exception as exc:
        print("nightly_loop.py: tape page rebuild failed: %r" % exc, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
