"""Pre-flight guard for run_daily.ps1 (B3 B-10).

`run_daily.ps1` used to run `git pull --rebase --autostash` and then launch
`live_scanner.py` with nothing in between. On 2026-09-03 the pull brought in
an `omen_bot.py` that did not parse (`SyntaxError: invalid character '—'`)
and the entire daily pass died -- scanner and archiver both
(`journal/scanner-2026-09-03.log`, 80 lines against ~8,000 on a normal day).

`run_guarded_pull` is the one function every caller (today: `run_daily.ps1`)
routes through: pull, smoke-test that the live-scanning code still imports,
and if it doesn't, reset back to the pre-pull commit so the day scans on
yesterday's known-good code instead of not scanning at all.
"""
import subprocess
import sys


def run_guarded_pull(python_exe="python", smoke_module="live_scanner", cwd=None):
    """Pull, smoke-test the import, and roll back on failure.

    Returns (pulled_ok, rolled_back, message).
    pulled_ok=True means the new code passed the smoke test and is in place.
    rolled_back=True means the pull was reverted and yesterday's commit is checked out.
    """
    pre = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True
    ).stdout.strip()

    pull = subprocess.run(
        ["git", "pull", "--rebase", "--autostash"], cwd=cwd, capture_output=True, text=True
    )
    if pull.stdout:
        print(pull.stdout, end="")
    if pull.stderr:
        print(pull.stderr, end="", file=sys.stderr)

    smoke = subprocess.run(
        [python_exe, "-c", f"import {smoke_module}"], cwd=cwd, capture_output=True, text=True
    )
    if smoke.returncode != 0:
        print(f"=== pull broke the build; rolling back to {pre} ===")
        if smoke.stdout:
            print(smoke.stdout, end="")
        if smoke.stderr:
            print(smoke.stderr, end="", file=sys.stderr)
        reset = subprocess.run(
            ["git", "reset", "--hard", pre], cwd=cwd, capture_output=True, text=True
        )
        if reset.stdout:
            print(reset.stdout, end="")
        return False, True, f"rolled back to {pre}: {smoke.stderr.strip().splitlines()[-1] if smoke.stderr.strip() else 'import failed'}"

    return True, False, "pull ok, import smoke test passed"


if __name__ == "__main__":
    python_exe = sys.argv[1] if len(sys.argv) > 1 else "python"
    ok, rolled_back, message = run_guarded_pull(python_exe=python_exe)
    print(message)
    # Never fail the pipeline: run_daily.ps1 must still launch live_scanner.py
    # afterward whether we pulled clean or rolled back to yesterday's code.
    sys.exit(0)
