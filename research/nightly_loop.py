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
CYCLES_MD = TAPE / "cycles.md"

HEADER = ("| date | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id | "
          "adopt (paper) |\n"
          "|---|---|---|---|---|---|---|\n")

EMPTY_ROW = "| %s | - | empty | - | - | - | - |\n"


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
    """loop_cycle.py prints exactly one pretty-printed json.dumps(..., indent=2)
    block as its last output (the blocked dict on a build-stage block, the
    full gate dict otherwise). Pretty-printing means every nested dict inside
    it (before_whole, after_whole, h1, h2, ...) opens with its own '{', so
    anchoring on `stdout.rfind("{")` (the previous approach) lands on the
    LAST nested brace instead of the block's own -- slicing from there yields
    a truncated fragment (e.g. just the "h2" sub-dict) that either fails to
    parse or parses "successfully" without "decision"/"before_whole"/
    "after_whole", silently producing an empty-looking result. Anchor on the
    FIRST '{' instead and let raw_decode stop at that object's own matching
    close brace, ignoring whatever text (if any) follows it."""
    start = stdout.find("{")
    if start == -1:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(stdout, start)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def cycles_md_row(flag: str, today: str) -> dict | None:
    """Fallback source of truth for run_candidate(). research/tape/cycles.md
    is the file research/loop_cycle.py's append_cycle_row() writes the real
    verdict to -- unconditionally, and before it ever prints the summary JSON
    parse_result() above reads. If that JSON still comes back unusable (a
    future loop_cycle.py change breaks its stdout contract, a crash between
    the two writes, whatever), re-derive tonight's line from the newest
    cycles.md row for this flag+date instead of falling back to an empty
    receipt while the real numbers sit one file over."""
    if not CYCLES_MD.exists():
        return None
    match = None
    for line in CYCLES_MD.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) != 12:
            continue
        row_date, _label, row_flag, decision = parts[0], parts[1], parts[2], parts[3]
        if row_flag == flag and row_date == today and decision in ("ship", "hold"):
            match = {"decision": decision, "per_day": parts[4], "green": parts[5],
                     "off_book": parts[9], "on_book": parts[10]}
    return match


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
        row = cycles_md_row(flag, today)
        if row is None:
            return "| %s | %s | hold | - | - | - -> - |\n" % (today, flag)
        off_id = book_id_for(str(TAPE / row["off_book"])) if row["off_book"] not in ("-", "") else "-"
        on_id = book_id_for(str(TAPE / row["on_book"])) if row["on_book"] not in ("-", "") else "-"
        return "| %s | %s | %s | %s | %s | %s -> %s |\n" % (
            today, flag, row["decision"], row["per_day"], row["green"], off_id, on_id)

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
    rebuild_status_page()
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


def rebuild_status_page() -> None:
    """Regenerate the small phone status page (research/build_status.py) so
    tonight's receipt, queue and V5/bar-deck numbers are on it without
    waiting for someone to run it by hand. Same MUST NOT FAIL THE TASK rule
    as rebuild_tape_page() above."""
    try:
        from research import build_status
        build_status.build()
    except Exception as exc:
        print("nightly_loop.py: status page rebuild failed: %r" % exc, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
