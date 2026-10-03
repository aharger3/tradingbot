"""Tests for omen_doctor + premarket card wiring. No Windows, no network."""
import sys
import types
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

import omen_doctor as d  # noqa: E402

NOW = datetime(2026, 10, 5, 9, 0)  # Monday 09:00, card time -> session day Fri 10-02
HEALTHY = {
    "tasks": lambda: {"OmenNightlyLoop": 0, "OmenPremarketCard": 0, "OmenSignalBot": 267009},
    "journal": lambda: 3,
    "nightly": lambda: True,
    "keys": lambda: set(d.KEYS) | {"PATH"},
    "disk": lambda: 120.0,
    "git": lambda: {"dirty": False, "worktrees": 0},
}


def run(**over):
    return d.run_doctor(NOW, {**HEALTHY, **over})


def test_healthy():
    assert run() == "DOCTOR OK"


def test_failing_task():
    out = run(tasks=lambda: {"OmenNightlyLoop": 1, "OmenSignalBot": 0})
    assert out == "DOCTOR 1 ISSUE: task OmenNightlyLoop rc=1"


def test_missing_key_names_only():
    out = run(keys=lambda: {"ALPACA_PAPER_KEY", "ALPACA_PAPER_SECRET"})
    assert "key missing DISCORD_WEBHOOK_URL" in out and "sekrit" not in out


def test_low_disk():
    assert "disk low 2.0GB" in run(disk=lambda: 2.0)


def test_misc_and_probe_error():
    out = run(journal=lambda: 0, nightly=lambda: False,
              git=lambda: {"dirty": True, "worktrees": 2},
              disk=lambda: (_ for _ in ()).throw(OSError("x")))
    for s in ("no journal rows 2026-10-02", "no nightly row 2026-10-02", "tree dirty",
              "2 stray worktree(s)", "disk probe error (OSError)"):
        assert s in out


def test_session_day_is_last_completed_session():
    assert d.session_day(NOW) == "2026-10-02"                         # Mon am -> Fri
    assert d.session_day(datetime(2026, 10, 6, 9, 0)) == "2026-10-05"  # Tue am -> Mon
    assert d.session_day(datetime(2026, 10, 6, 21, 30)) == "2026-10-06"  # after nightly
    assert d.session_day(datetime(2026, 10, 4, 22, 0)) == "2026-10-02"   # Sun -> Fri


def test_freshness_probes_get_session_day_not_today(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(d, "probe_journal_rows_today", lambda day: seen.append(day) or 1)
    monkeypatch.setattr(d, "probe_nightly_row_today", lambda day: seen.append(day) or True)
    over = {k: v for k, v in HEALTHY.items() if k not in ("journal", "nightly")}
    assert d.run_doctor(NOW, over) == "DOCTOR OK"
    assert seen == ["2026-10-02", "2026-10-02"]


def test_unknown_task_is_flagged_not_silent():
    out = run(tasks=lambda: {"OmenNightlyLoop": 0, "OmenTypo": None})
    assert out == "DOCTOR 1 ISSUE: task OmenTypo not found"


def test_no_schtasks_binary_is_one_probe_error(monkeypatch):
    monkeypatch.setattr(d.shutil, "which", lambda name: None)
    over = {k: v for k, v in HEALTHY.items() if k != "tasks"}
    assert d.run_doctor(NOW, over) == "DOCTOR 1 ISSUE: tasks probe error (FileNotFoundError)"


def test_git_probe_ignores_runtime_paths(tmp_path):
    import subprocess
    g = lambda *a: subprocess.run(["git", "-C", str(tmp_path), *a], check=True,
                                  capture_output=True)
    g("init", "-q")
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "j.jsonl").write_text("a\n")
    (tmp_path / "code.py").write_text("x = 1\n")
    g("add", "."); g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    (tmp_path / "journal" / "j.jsonl").write_text("a\nb\n")
    assert d.probe_git(tmp_path) == {"dirty": False, "worktrees": 0}
    (tmp_path / "code.py").write_text("x = 2\n")
    assert d.probe_git(tmp_path)["dirty"] is True


def test_key_probe_ignores_values(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("FOO_KEY=abc\nEMPTY=\n# C=1\n")
    names = d.probe_key_names(tmp_path)
    assert "FOO_KEY" in names and "EMPTY" not in names and "abc" not in names


def test_file_probes(tmp_path):
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "paper-trades.jsonl").write_text(
        '{"ts": "2026-10-05 10:35:00"}\n{"ts": "2026-10-04 10:00:00"}\nbad\n')
    (tmp_path / "research" / "tape").mkdir(parents=True)
    (tmp_path / "research" / "tape" / "nightly.md").write_text(
        "| date | flag |\n|---|---|\n| 2026-10-05 | X |\n")
    assert d.probe_journal_rows_today("2026-10-05", tmp_path) == 1
    assert d.probe_nightly_row_today("2026-10-05", tmp_path)
    assert not d.probe_nightly_row_today("2026-10-06", tmp_path)


def test_premarket_card_doctor_first(monkeypatch):
    live = types.ModuleType("live_scanner")
    live.DEFAULT_SYMBOLS = ["TSLA"]
    live._yf_daily_context = lambda s: (101.0, 99.0, None, 100.5, 99.5, None, 100.0)
    live._yf_history = lambda *a, **k: None
    live.now_et = lambda: NOW
    monkeypatch.setitem(sys.modules, "live_scanner", live)
    sr = types.ModuleType("signal_runner")
    sr._load_env_file = lambda p: None
    monkeypatch.setitem(sys.modules, "signal_runner", sr)
    monkeypatch.delitem(sys.modules, "premarket_card", raising=False)
    import premarket_card as pc
    real = pc._doctor_line()  # real wiring, real probes on this box: never raises
    assert real.startswith("DOCTOR ") and "unavailable" not in real, real
    monkeypatch.setattr(pc, "_doctor_line", lambda: "DOCTOR OK")
    fields = pc.build_card(["TSLA"])["embeds"][0]["fields"]
    assert fields[0] == {"name": "Doctor", "value": "DOCTOR OK", "inline": False}
    assert fields[1]["name"] == "QQQ Daily Bias"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
