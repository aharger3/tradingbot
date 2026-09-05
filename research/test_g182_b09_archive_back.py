"""B-09: run_daily.ps1 must call archive_1m.py with --back, not the bare default.

archive_1m.py:57 defaults `end = date.today()`, and its own docstring says Polygon
returns 403 for the CURRENT day on this plan (see `archive_day`'s docstring). Calling
it with no --back therefore asks for the one day guaranteed to 403 and never banks
anything. run_daily.ps1 runs after market close, so the just-finished session is
already a *completed* day -- --back 0 (today only, no lookback) still 403s; the fix
is to request at least one full day back so a completed session is actually asked for.

Root cause lives in the caller (run_daily.ps1), not in archive_1m.py itself --
archive_1m.py already supports --back correctly (see run_omen6_forward.ps1's
`--back 5`, the only other caller, which was never bitten by this).
"""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
RUN_DAILY = ROOT / "run_daily.ps1"


def _archive_1m_invocation_line() -> str:
    for line in RUN_DAILY.read_text(encoding="utf-8").splitlines():
        if "archive_1m.py" in line:
            return line
    raise AssertionError("run_daily.ps1 never calls archive_1m.py")


def test_run_daily_passes_back_flag_to_archive_1m():
    line = _archive_1m_invocation_line()
    assert re.search(r"archive_1m\.py\s+--back\s+\d+", line), (
        f"run_daily.ps1's archive_1m.py call has no --back flag, so it only ever "
        f"requests date.today() (guaranteed 403 on this Polygon plan): {line!r}"
    )


def test_back_value_is_at_least_1():
    line = _archive_1m_invocation_line()
    m = re.search(r"archive_1m\.py\s+--back\s+(\d+)", line)
    assert m, f"no --back flag found: {line!r}"
    assert int(m.group(1)) >= 1, (
        "--back 0 still only requests today (a 403), which is exactly this bug"
    )


if __name__ == "__main__":
    test_run_daily_passes_back_flag_to_archive_1m()
    test_back_value_is_at_least_1()
    print("2 passed")
