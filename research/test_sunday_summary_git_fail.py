"""research/test_sunday_summary_git_fail.py -- a failed vault git push must not
skip the status page rebuild or the weekly paper P&L report.

sunday_summary.main() used to `return 0` when git_commit_vault() was False,
before rebuild_status_page() and run_paper_pnl_report(). Both are independent
of the git result, so an offline run / index.lock / non-fast-forward silently
dropped them for a week.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research import sunday_summary as ss  # noqa: E402


def _run(git_ok: bool) -> list[str]:
    calls: list[str] = []
    saved = {k: getattr(ss, k) for k in (
        "read_nightly_lines", "load_baseline_figures", "make_summary_row",
        "append_to_summary", "git_commit_vault", "rebuild_status_page",
        "run_paper_pnl_report")}
    try:
        ss.read_nightly_lines = lambda days=7: ["x"]
        ss.load_baseline_figures = lambda: {}
        ss.make_summary_row = lambda lines, base: "| row |\n"
        ss.append_to_summary = lambda row: True
        ss.git_commit_vault = lambda: git_ok
        ss.rebuild_status_page = lambda: calls.append("status")
        ss.run_paper_pnl_report = lambda: calls.append("pnl")
        assert ss.main() == 0
    finally:
        for k, v in saved.items():
            setattr(ss, k, v)
    return calls


def main() -> int:
    ok = _run(True)
    assert ok == ["status", "pnl"], ok
    print("PASS git ok -> status + pnl run")
    bad = _run(False)
    assert bad == ["status", "pnl"], f"git failure skipped follow-ups: {bad}"
    print("PASS git fail -> status + pnl still run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
