"""loop_supervisor.py -- watchdog for scheduled task OmenNightlyLoop.

WHY. OmenNightlyLoop (weekdays 20:00) can die silently -- Task Scheduler
itself failing to fire, or the process hanging past its normal length --
and nobody notices until research/tape/nightly.md has gone stale. This is
the watchdog: run later (weekdays 21:30, scheduled task
OmenLoopSupervisor), it never edits loop_queue.json and never calls
loop_cycle.py or signal_runner.py -- it only reads nightly.md, queries
Task Scheduler's own status for OmenNightlyLoop, and:

  - no row dated today AND OmenNightlyLoop is not Running -> restart it
    once (`schtasks /run`), log "supervisor: restarted".
  - OmenNightlyLoop has been Running > LONG_RUN_HOURS -> log
    "supervisor: long run" only, never restart (it may still finish).
  - otherwise -> log a no-op line.

One ntfy line per event, capped at once per calendar day (state file
research/tape/.supervisor_ntfy_sent), reusing the topic/helper already
wired in Projects/ev-dashboard/ntfy_push.py -- no new topic. If that
topic/helper is unavailable for any reason, this degrades to log-only and
still exits 0 (MUST NOT FAIL THE TASK -- same rule as nightly_loop.py).

Usage:
    python research/loop_supervisor.py            # real run
    python research/loop_supervisor.py --selftest  # pure-logic assertions, no file/schtasks I/O
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAPE = ROOT / "research" / "tape"
NIGHTLY = TAPE / "nightly.md"
SUPERVISOR_LOG = TAPE / "supervisor.log"
NTFY_SENT_STATE = TAPE / ".supervisor_ntfy_sent"

TASK_NAME = "OmenNightlyLoop"
LONG_RUN_HOURS = 5.0

EV_DASHBOARD = ROOT.parent / "ev-dashboard"


def today_str(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d")


def nightly_has_row_today(text: str, today: str) -> bool:
    """True if any markdown-table row in `text` (research/tape/nightly.md's
    shape: '| date | flag | decision | ... |') has `date` as its first
    column. Header/separator rows are skipped the same way loop_alert.py
    skips them."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or cells[0].lower() == "date" or set(cells[0]) <= {"-"}:
            continue
        if cells[0] == today:
            return True
    return False


def parse_schtasks_verbose(stdout: str) -> dict:
    """Pull Status / Last Run Time out of `schtasks /query /tn X /fo LIST /v`
    output. Returns {} if the fields aren't found (task missing, unexpected
    format, etc.) -- callers treat that as "unknown", never as "not running"."""
    fields = {}
    for line in stdout.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if key == "Status":
            fields["status"] = val
        elif key == "Last Run Time":
            fields["last_run_time"] = val
    return fields


def parse_last_run_time(s: str):
    """schtasks prints e.g. '9/20/2026 12:31:39 AM'; 'N/A' or an unparsable
    value returns None rather than raising."""
    if not s or s.strip().upper() == "N/A":
        return None
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        return None


def query_task(task_name: str = TASK_NAME):
    """(status, elapsed_hours_since_last_run) for `task_name`, or (None,
    None) if the query fails or fields can't be parsed -- an unknown state
    never triggers a restart."""
    try:
        proc = subprocess.run(
            ["schtasks", "/query", "/tn", task_name, "/fo", "LIST", "/v"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    if proc.returncode != 0:
        return None, None
    fields = parse_schtasks_verbose(proc.stdout)
    status = fields.get("status")
    last_run = parse_last_run_time(fields.get("last_run_time", ""))
    elapsed_hours = None
    if last_run is not None:
        elapsed_hours = (datetime.now() - last_run).total_seconds() / 3600.0
    return status, elapsed_hours


def decide(has_row_today: bool, status: str | None, elapsed_hours: float | None,
           long_run_hours: float = LONG_RUN_HOURS) -> str:
    """Pure decision, no I/O -- one of "restart" / "long_run" / "noop".
    `status` is the raw schtasks Status string ("Running", "Ready", ...) or
    None when the query failed/was unparsable (treated as "unknown, do not
    restart" to avoid restart storms on a flaky query)."""
    is_running = (status or "").strip().lower() == "running"
    if is_running and elapsed_hours is not None and elapsed_hours > long_run_hours:
        return "long_run"
    if not has_row_today and status is not None and not is_running:
        return "restart"
    return "noop"


def start_task(task_name: str = TASK_NAME) -> bool:
    try:
        proc = subprocess.run(["schtasks", "/run", "/tn", task_name],
                               capture_output=True, text=True, timeout=30)
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"loop_supervisor: start_task failed: {exc!r}", file=sys.stderr)
        return False


def append_log(line: str, path: Path = SUPERVISOR_LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{stamp} {line}\n")


def _ntfy_already_sent_today(today: str, state_path: Path = NTFY_SENT_STATE) -> bool:
    try:
        return state_path.read_text(encoding="utf-8").strip() == today
    except OSError:
        return False


def _mark_ntfy_sent(today: str, state_path: Path = NTFY_SENT_STATE) -> None:
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(today, encoding="utf-8")
    except OSError:
        pass


def send_ntfy_once_per_day(title: str, body: str, today: str) -> bool:
    """Reuses Projects/ev-dashboard/ntfy_push.py's `_post` + topic -- never a
    new topic. Capped at one send per calendar day across all supervisor
    events. Any failure (module missing, topic unset, network) degrades to
    a no-op and returns False; callers must still exit 0."""
    if _ntfy_already_sent_today(today):
        return False
    try:
        if str(EV_DASHBOARD) not in sys.path:
            sys.path.insert(0, str(EV_DASHBOARD))
        import ntfy_push  # type: ignore
        ok = ntfy_push._post(title, body, priority="high", tags=["warning"])
    except Exception as exc:  # noqa: BLE001 -- ntfy is best-effort, never fatal
        print(f"loop_supervisor: ntfy unavailable, log-only ({exc!r})", file=sys.stderr)
        return False
    if ok:
        _mark_ntfy_sent(today)
    return ok


def main() -> int:
    today = today_str()
    text = NIGHTLY.read_text(encoding="utf-8") if NIGHTLY.exists() else ""
    has_row_today = nightly_has_row_today(text, today)
    status, elapsed_hours = query_task()
    action = decide(has_row_today, status, elapsed_hours)

    if action == "restart":
        started = start_task()
        if started:
            append_log("supervisor: restarted")
            send_ntfy_once_per_day(
                "OMEN loop supervisor",
                f"{TASK_NAME} had no row today and was not running -- restarted.",
                today,
            )
        else:
            append_log("supervisor: restart attempt failed")
            send_ntfy_once_per_day(
                "OMEN loop supervisor",
                f"{TASK_NAME} had no row today and was not running -- restart FAILED.",
                today,
            )
    elif action == "long_run":
        hours = f"{elapsed_hours:.1f}h" if elapsed_hours is not None else "?"
        append_log(f"supervisor: long run ({hours})")
        send_ntfy_once_per_day(
            "OMEN loop supervisor",
            f"{TASK_NAME} has been running {hours} -- past the {LONG_RUN_HOURS:g}h watch mark, not restarted.",
            today,
        )
    else:
        append_log(f"supervisor: noop (row_today={has_row_today} status={status!r})")

    print(f"loop_supervisor: {action}")
    return 0


def self_test() -> bool:
    ok = True

    # nightly_has_row_today
    mock = (
        "# nightly loop receipts\n\n"
        "| date | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id |\n"
        "|---|---|---|---|---|---|\n"
        "| 2026-09-17 | - | empty | - | - | - |\n"
        "| 2026-09-19 | BNR_DISPLACEMENT_GATE | ship | -52.0 -> -54.0 | 11 -> 11 | a -> b |\n"
    )
    if nightly_has_row_today(mock, "2026-09-19") is not True:
        print("FAIL: existing row not detected"); ok = False
    if nightly_has_row_today(mock, "2026-09-20") is not False:
        print("FAIL: missing row falsely detected"); ok = False

    # parse_schtasks_verbose + parse_last_run_time
    stdout = (
        "Folder: \\\n"
        "HostName:                             DESKTOP-X\n"
        "TaskName:                             \\OmenNightlyLoop\n"
        "Status:                               Running\n"
        "Last Run Time:                        9/20/2026 12:31:39 AM\n"
    )
    fields = parse_schtasks_verbose(stdout)
    if fields.get("status") != "Running":
        print(f"FAIL: status parse, got {fields}"); ok = False
    last_run = parse_last_run_time(fields.get("last_run_time", ""))
    if last_run is None or last_run.hour != 0 or last_run.minute != 31:
        print(f"FAIL: last_run_time parse, got {last_run}"); ok = False
    if parse_last_run_time("N/A") is not None:
        print("FAIL: N/A should parse to None"); ok = False
    if parse_last_run_time("garbage") is not None:
        print("FAIL: unparsable string should parse to None"); ok = False

    # decide()
    cases = [
        # (has_row_today, status, elapsed_hours, long_run_hours) -> expected
        ((True, "Ready", None, LONG_RUN_HOURS), "noop"),
        ((False, "Ready", None, LONG_RUN_HOURS), "restart"),
        ((False, "Running", None, LONG_RUN_HOURS), "noop"),
        ((True, "Running", 6.0, LONG_RUN_HOURS), "long_run"),
        ((False, "Running", 6.0, LONG_RUN_HOURS), "long_run"),
        ((False, "Running", 2.0, LONG_RUN_HOURS), "noop"),
        ((False, None, None, LONG_RUN_HOURS), "noop"),  # unknown query -> never restart
    ]
    for args, expected in cases:
        got = decide(*args)
        if got != expected:
            print(f"FAIL: decide{args} = {got!r}, expected {expected!r}"); ok = False

    print("PASS" if ok else "SELFTEST FAILED")
    return ok


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if self_test() else 1)
    sys.exit(main())
