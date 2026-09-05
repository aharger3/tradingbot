"""B3 B-10: run_daily.ps1 must not launch live_scanner.py on code that can't parse.

Reproduces 2026-09-03: a bad commit lands via `git pull`, the module doesn't
import. Before the fix there was no guard at all -- this test exercises the
guard function itself (`pull_guard.run_guarded_pull`) and fails on import if
the file doesn't exist yet, which is exactly the state before this bug fix.
"""
import subprocess
import sys
import tempfile
import shutil
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pull_guard import run_guarded_pull  # noqa: E402


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _make_repo(tmp):
    upstream = os.path.join(tmp, "upstream")
    work = os.path.join(tmp, "work")
    os.makedirs(upstream)
    _git(upstream, "init", "-q")
    _git(upstream, "config", "user.email", "test@example.com")
    _git(upstream, "config", "user.name", "test")

    good = "print('scanning')\n"
    with open(os.path.join(upstream, "live_scanner.py"), "w") as f:
        f.write(good)
    _git(upstream, "add", "live_scanner.py")
    _git(upstream, "commit", "-q", "-m", "good commit")
    good_sha = _git(upstream, "rev-parse", "HEAD").stdout.strip()

    _git(upstream, "clone", "-q", upstream, work) if False else None
    subprocess.run(["git", "clone", "-q", upstream, work], capture_output=True, text=True, check=True)
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "test")

    # A second, syntactically broken commit lands on the remote (Hermes push).
    bad = "opposed trend — broken\nprint(\n"
    with open(os.path.join(upstream, "live_scanner.py"), "w") as f:
        f.write(bad)
    _git(upstream, "add", "live_scanner.py")
    _git(upstream, "commit", "-q", "-m", "bad commit: syntax error")

    return work, good_sha


def test_guarded_pull_rolls_back_a_broken_commit():
    tmp = tempfile.mkdtemp(prefix="pull_guard_test_")
    try:
        work, good_sha = _make_repo(tmp)
        ok, rolled_back, message = run_guarded_pull(
            python_exe=sys.executable, smoke_module="live_scanner", cwd=work
        )
        assert rolled_back is True, f"expected rollback, got ok={ok} msg={message}"
        assert ok is False

        head = _git(work, "rev-parse", "HEAD").stdout.strip()
        assert head == good_sha, f"expected rollback to {good_sha}, still at {head}"

        # After rollback, the code must actually import clean.
        smoke = subprocess.run(
            [sys.executable, "-c", "import live_scanner"], cwd=work, capture_output=True, text=True
        )
        assert smoke.returncode == 0, smoke.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_guarded_pull_leaves_a_good_pull_alone():
    tmp = tempfile.mkdtemp(prefix="pull_guard_test_ok_")
    try:
        upstream = os.path.join(tmp, "upstream")
        work = os.path.join(tmp, "work")
        os.makedirs(upstream)
        _git(upstream, "init", "-q")
        _git(upstream, "config", "user.email", "test@example.com")
        _git(upstream, "config", "user.name", "test")
        with open(os.path.join(upstream, "live_scanner.py"), "w") as f:
            f.write("print('v1')\n")
        _git(upstream, "add", "live_scanner.py")
        _git(upstream, "commit", "-q", "-m", "v1")
        subprocess.run(["git", "clone", "-q", upstream, work], capture_output=True, text=True, check=True)
        _git(work, "config", "user.email", "test@example.com")
        _git(work, "config", "user.name", "test")

        with open(os.path.join(upstream, "live_scanner.py"), "w") as f:
            f.write("print('v2, still valid python')\n")
        _git(upstream, "add", "live_scanner.py")
        _git(upstream, "commit", "-q", "-m", "v2, still good")
        good_sha = _git(upstream, "rev-parse", "HEAD").stdout.strip()

        ok, rolled_back, message = run_guarded_pull(
            python_exe=sys.executable, smoke_module="live_scanner", cwd=work
        )
        assert ok is True, message
        assert rolled_back is False
        head = _git(work, "rev-parse", "HEAD").stdout.strip()
        assert head == good_sha
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_guarded_pull_rolls_back_a_broken_commit()
    test_guarded_pull_leaves_a_good_pull_alone()
    print("OK: pull_guard rolls back a broken pull, leaves a good one alone")
