"""B-11: OmenWeeklyDigest was enabled (State Ready) and pointed at
run_weekly_digest.ps1, a script that does not exist in the repo — it and the
weekly_digest.py it called were both deleted at ce2a98d6 without the Task
Scheduler entry ever being cleaned up. It had failed every week since
2026-08-30 (LastTaskResult 4294770688) with nothing to notice.

This is the general check, not a one-off: for every scheduled task whose name
starts with "Omen", if the task is enabled (State != Disabled) its Action's
-File target must exist on disk. A task that is Disabled is exempt — B-12
(a6_dispatch.ps1 / OmenA6PaperLog) is exactly that shape and must stay green.

Root-cause fix shipped: OmenWeeklyDigest disabled via
`Disable-ScheduledTask -TaskName OmenWeeklyDigest` (task kept, not deleted —
restoring run_weekly_digest.ps1 would mean resurrecting weekly_digest.py too,
which is new feature work, not a bug fix, and out of scope for B3).

    python research/test_g182_b11_weekly_digest_task.py
"""
from __future__ import annotations
import re
import subprocess
import sys


def _list_omen_tasks() -> list[dict]:
    """Return [{name, state, file}] for every scheduled task named Omen*."""
    out = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-Command",
            "Get-ScheduledTask | Where-Object { $_.TaskName -like 'Omen*' } | "
            "ForEach-Object { "
            "  $act = $_.Actions | Select-Object -First 1; "
            "  [pscustomobject]@{Name=$_.TaskName; State=$_.State.ToString(); Arguments=$act.Arguments} "
            "} | ConvertTo-Json -Compress",
        ],
        capture_output=True, text=True, timeout=30,
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"Get-ScheduledTask failed: {out.stderr.strip()}")
    import json
    data = json.loads(out.stdout)
    if isinstance(data, dict):
        data = [data]
    tasks = []
    for row in data:
        args = row.get("Arguments") or ""
        m = re.search(r'-File\s+"?([^"\s]+\.ps1)"?', args)
        tasks.append({
            "name": row["Name"],
            "state": row["State"],
            "file": m.group(1) if m else None,
        })
    return tasks


def check_enabled_omen_tasks_target_real_scripts() -> list[str]:
    """Return a list of failure descriptions; empty means all good."""
    import os
    failures = []
    for t in _list_omen_tasks():
        if t["state"] == "Disabled":
            continue
        if t["file"] and not os.path.exists(t["file"]):
            failures.append(f"{t['name']}: State={t['state']}, missing target {t['file']}")
    return failures


if __name__ == "__main__":
    failures = check_enabled_omen_tasks_target_real_scripts()
    if failures:
        print("FAIL: enabled Omen* scheduled task(s) point at a missing script:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("PASS: every enabled Omen* scheduled task's -File target exists on disk.")
    sys.exit(0)
