"""omen_doctor.py -- one-line health check for the OMEN box (row R96).

Checks: scheduled-task last-run codes, journal rows and a nightly row for the
last completed session day (see session_day),
required key NAMES present (never values), disk free, dirty tree / stray
worktrees. Returns ONE status line, e.g.
    "DOCTOR OK" or "DOCTOR 2 ISSUES: task OmenNightlyLoop rc=1; key missing DISCORD_WEBHOOK_URL"

Read-only. Never places orders, never reads secret values. Windows-only probes
(schtasks, git, disk) are injectable: pass `probes={...}` to run_doctor.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS = ("OmenNightlyLoop", "OmenPremarketCard", "OmenSignalBot", "OmenHealthCheck")
KEYS = ("ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET", "DISCORD_WEBHOOK_URL")
MIN_FREE_GB = 5.0
# schtasks "Last Result" values that are not failures
OK_CODES = {0, 267009, 267011}  # success, running, never-run-yet
# Paths the scheduled jobs write on the production checkout (nightly.md row at
# 20:00, journal/*.json(l) during the session). Churn there is expected, not drift.
RUNTIME_PATHS = ("journal", "research/tape")
NIGHTLY_HOUR = 21  # OmenNightlyLoop runs weekdays 20:00; give it an hour


def session_day(now: datetime) -> str:
    """The last session whose journal + nightly row should already exist.

    The card runs 09:00 ET, before today's trades and today's 20:00 nightly, so
    "today" would flag both every morning. Before NIGHTLY_HOUR on a weekday the
    expected day is the previous weekday; after it, today.
    """
    d = now.date()
    if not (d.weekday() < 5 and now.hour >= NIGHTLY_HOUR):
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d.isoformat()


def probe_task_codes(tasks=TASKS) -> dict:
    """{task: last_result int, or None if not found / unparseable}. Windows schtasks.

    No schtasks binary (Linux) raises, so run_doctor reports one probe error
    instead of a "not found" per task.
    """
    if shutil.which("schtasks") is None:
        raise FileNotFoundError("schtasks")
    out = {}
    for t in tasks:
        try:
            txt = subprocess.run(["schtasks", "/query", "/tn", t, "/fo", "LIST", "/v"],
                                 capture_output=True, text=True, timeout=20).stdout
            val = None
            for ln in txt.splitlines():
                if ln.lower().startswith("last result"):
                    val = int(ln.split(":", 1)[1].strip(), 0)
            out[t] = val
        except Exception:
            out[t] = None
    return out


def probe_journal_rows_today(today: str, root: Path = ROOT) -> int:
    p = root / "journal" / "paper-trades.jsonl"
    if not p.exists():
        return 0
    n = 0
    for ln in p.read_text(errors="ignore").splitlines():
        try:
            if str(json.loads(ln).get("ts", "")).startswith(today):
                n += 1
        except Exception:
            continue
    return n


def probe_nightly_row_today(today: str, root: Path = ROOT) -> bool:
    p = root / "research" / "tape" / "nightly.md"
    if not p.exists():
        return False
    for ln in p.read_text(errors="ignore").splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if ln.strip().startswith("|") and cells and cells[0] == today:
            return True
    return False


def probe_key_names(root: Path = ROOT) -> set:
    """Names of keys present in env or .env. Values are never kept."""
    names = {k for k, v in os.environ.items() if v}
    envf = root / ".env"
    if envf.exists():
        for ln in envf.read_text(errors="ignore").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, _, v = ln.partition("=")
                if v.strip():
                    names.add(k.strip())
    return names


def probe_disk_free_gb(root: Path = ROOT) -> float:
    return shutil.disk_usage(root).free / 1e9


def probe_git(root: Path = ROOT) -> dict:
    """{'dirty': bool, 'worktrees': int (linked, beyond the main one)}.

    dirty = tracked files modified outside RUNTIME_PATHS (code drift, not data).
    """
    def g(*a):
        return subprocess.run(["git", "-C", str(root), *a], capture_output=True,
                              text=True, timeout=20).stdout
    try:
        dirty = bool(g("status", "--porcelain", "--untracked-files=no", "--", ".",
                       *(f":(exclude){x}" for x in RUNTIME_PATHS)).strip())
        wts = sum(1 for ln in g("worktree", "list", "--porcelain").splitlines()
                  if ln.startswith("worktree "))
        return {"dirty": dirty, "worktrees": max(wts - 1, 0)}
    except Exception:
        return {"dirty": False, "worktrees": 0}


def run_doctor(now: datetime | None = None, probes: dict | None = None) -> str:
    day = session_day(now or datetime.now())
    p = {
        "tasks": probe_task_codes,
        "journal": lambda: probe_journal_rows_today(day),
        "nightly": lambda: probe_nightly_row_today(day),
        "keys": probe_key_names,
        "disk": probe_disk_free_gb,
        "git": probe_git,
    }
    p.update(probes or {})
    issues = []

    def safe(name, default):
        try:
            return p[name]()
        except Exception as e:
            issues.append(f"{name} probe error ({type(e).__name__})")
            return default

    for t, rc in sorted(safe("tasks", {}).items()):
        if rc is None:
            issues.append(f"task {t} not found")
        elif rc not in OK_CODES:
            issues.append(f"task {t} rc={rc}")
    if safe("journal", 1) == 0:
        issues.append(f"no journal rows {day}")
    if not safe("nightly", True):
        issues.append(f"no nightly row {day}")
    have = safe("keys", set(KEYS))
    for k in KEYS:
        if k not in have:
            issues.append(f"key missing {k}")
    free = safe("disk", 1e9)
    if free < MIN_FREE_GB:
        issues.append(f"disk low {free:.1f}GB")
    git = safe("git", {"dirty": False, "worktrees": 0})
    if git.get("dirty"):
        issues.append("tree dirty")
    if git.get("worktrees"):
        issues.append(f"{git['worktrees']} stray worktree(s)")

    if not issues:
        return "DOCTOR OK"
    n = len(issues)
    return f"DOCTOR {n} ISSUE{'S' if n > 1 else ''}: " + "; ".join(issues)


if __name__ == "__main__":
    print(run_doctor())
