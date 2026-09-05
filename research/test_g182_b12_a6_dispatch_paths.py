"""B-12: a6_dispatch.ps1 lines 5, 9 and 10 pointed at
C:\\Users\\aharg\\aharg\\Desktop\\projects\\tradingbot — a doubled 'aharg' and
lowercase 'projects', the junction tree dissolved 2026-08-06. The path never
existed under that name, so OmenA6PaperLog's Set-Location, prompt read and
log path were all dead; the task is Disabled (not a live outage) but the
committed script was wrong regardless.

Fix: repoint all three lines at the real working copy,
C:\\Users\\aharg\\Desktop\\Projects\\tradingbot.

    python research/test_g182_b12_a6_dispatch_paths.py
"""
from __future__ import annotations
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DISPATCH = REPO_ROOT / "a6_dispatch.ps1"
DEAD_PATH = r"C:\Users\aharg\aharg\Desktop\projects\tradingbot"
REAL_PATH = r"C:\Users\aharg\Desktop\Projects\tradingbot"


def check_a6_dispatch_paths_are_real() -> list[str]:
    """Return a list of failure descriptions; empty means all good."""
    failures = []
    text = DISPATCH.read_text(encoding="utf-8")
    if DEAD_PATH.lower() in text.lower():
        failures.append(
            f"a6_dispatch.ps1 still references the dissolved junction path "
            f"{DEAD_PATH!r}"
        )
    if REAL_PATH not in text:
        failures.append(
            f"a6_dispatch.ps1 does not reference the real working copy "
            f"{REAL_PATH!r}"
        )
    # every path literal the script relies on must actually exist on disk
    for name, target in {
        "Set-Location target": REPO_ROOT,
        "prompt file": REPO_ROOT / "a6-prompt.txt",
        "log directory": REPO_ROOT / "journal",
    }.items():
        if not target.exists():
            failures.append(f"{name} does not exist: {target}")
    return failures


if __name__ == "__main__":
    fails = check_a6_dispatch_paths_are_real()
    if fails:
        print("FAIL:")
        for f in fails:
            print(f"  - {f}")
        sys.exit(1)
    print("PASS: a6_dispatch.ps1 points at the real working copy and every referenced path exists.")
