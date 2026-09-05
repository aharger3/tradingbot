"""B3 B-15: OmenSignalBot's scheduled-task ExecutionTimeLimit vs. its real run window.

WHY THIS EXISTS. B-15 found three scheduled tasks returning failure. OmenSignalBot's
LastTaskResult was 267014 decimal == 0x41306 == SCHED_S_TASK_TERMINATED -- Task
Scheduler's own code for "I killed this because it hit its time limit", not an
error from the script itself.

run_daily.ps1 starts at 09:25 ET and runs `live_scanner.py --paper`, which manages
open positions through `MANAGE_END` (live_scanner.py, default "16:00" ET) before
archive_1m.py ever runs -- a real window of ~6h35m. The task's ExecutionTimeLimit
was PT4H (4 hours), so Task Scheduler terminated the process every session around
13:25 ET, mid-day, before positions were managed to close and before the end-of-day
archive step ran. This is not a live_scanner.py bug -- MANAGE_END is documented and
intentional -- the task's own time budget just didn't cover it.

This test reads the live task's ExecutionTimeLimit via `schtasks /query /xml` and
asserts it comfortably covers StartBoundary's clock time through MANAGE_END plus a
safety margin. It fails against the task as found (PT4H) and passes once the task
is widened.
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess

TASK = "OmenSignalBot"
MANAGE_END = "16:00"          # live_scanner.py's default MANAGE_END
MIN_MARGIN_MIN = 30           # buffer past MANAGE_END before archive_1m.py runs


def _task_xml(task: str) -> str:
    out = subprocess.run(
        ["schtasks", "/query", "/tn", task, "/xml"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def _iso8601_duration_to_minutes(s: str) -> int:
    """Parse a subset of ISO-8601 durations Task Scheduler emits, e.g. 'PT4H30M'."""
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", s)
    assert m, f"unrecognized duration format: {s!r}"
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    return hours * 60 + minutes


def required_minutes(xml: str) -> int:
    m = re.search(r"<StartBoundary>[^<]*T(\d{2}):(\d{2}):\d{2}", xml)
    assert m, "no StartBoundary found in task XML"
    start = dt.time(int(m.group(1)), int(m.group(2)))
    end_h, end_m = (int(x) for x in MANAGE_END.split(":"))
    end = dt.time(end_h, end_m)
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    return (end_min - start_min) + MIN_MARGIN_MIN


def configured_minutes(xml: str) -> int:
    m = re.search(r"<ExecutionTimeLimit>([^<]+)</ExecutionTimeLimit>", xml)
    assert m, "no ExecutionTimeLimit found in task XML"
    return _iso8601_duration_to_minutes(m.group(1))


def test_execution_time_limit_covers_manage_end():
    xml = _task_xml(TASK)
    need = required_minutes(xml)
    have = configured_minutes(xml)
    assert have >= need, (
        f"{TASK}: ExecutionTimeLimit covers {have} min but the run window "
        f"(start -> MANAGE_END {MANAGE_END} + {MIN_MARGIN_MIN} min margin) "
        f"needs {need} min -- Task Scheduler will SCHED_S_TASK_TERMINATE "
        f"(0x41306) the scan before it manages the day's positions to close."
    )


if __name__ == "__main__":
    test_execution_time_limit_covers_manage_end()
    print("PASS -- OmenSignalBot's ExecutionTimeLimit covers its run window")
