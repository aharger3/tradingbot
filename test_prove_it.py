"""Fixture test for research/prove_it.py -- no real replay run, no network."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "research"))
import prove_it  # noqa: E402


BASELINE = {"mean_r": -0.11, "n": 46, "config_hash": "abc123"}


def test_no_drift_same_hash_small_r_move(monkeypatch, tmp_path):
    """R moves less than tolerance, hash unchanged -> exit 0, no alarm."""
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(BASELINE))
    monkeypatch.setattr(prove_it, "run_replay", lambda script: {"mean_r": -0.115, "n": 46})
    monkeypatch.setattr(prove_it, "config_hash", lambda script: "abc123")
    pushed = []
    monkeypatch.setattr(prove_it, "send_ntfy", lambda msg: pushed.append(msg))

    rc = prove_it.main(["--baseline", str(baseline_path), "--replay-script", str(tmp_path / "fake.py")])

    assert rc == 0
    assert pushed == []


def test_drift_same_hash_big_r_move_fails_and_pushes(monkeypatch, tmp_path):
    """R moves past tolerance with the config hash unchanged -> exit 1 + ntfy."""
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(BASELINE))
    monkeypatch.setattr(prove_it, "run_replay", lambda script: {"mean_r": -0.20, "n": 46})
    monkeypatch.setattr(prove_it, "config_hash", lambda script: "abc123")
    pushed = []
    monkeypatch.setattr(prove_it, "send_ntfy", lambda msg: pushed.append(msg))

    rc = prove_it.main(["--baseline", str(baseline_path), "--replay-script", str(tmp_path / "fake.py")])

    assert rc == 1
    assert len(pushed) == 1


def test_drift_n_changed_same_hash_fails(monkeypatch, tmp_path):
    """n changes with the config hash unchanged -> exit 1, even if R is stable."""
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(BASELINE))
    monkeypatch.setattr(prove_it, "run_replay", lambda script: {"mean_r": -0.11, "n": 39})
    monkeypatch.setattr(prove_it, "config_hash", lambda script: "abc123")
    monkeypatch.setattr(prove_it, "send_ntfy", lambda msg: None)

    rc = prove_it.main(["--baseline", str(baseline_path), "--replay-script", str(tmp_path / "fake.py")])

    assert rc == 1


def test_hash_changed_big_r_move_is_not_drift(monkeypatch, tmp_path):
    """Flags/engine changed (hash differs) -> expected drift, no alarm even if R moved a lot."""
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(BASELINE))
    monkeypatch.setattr(prove_it, "run_replay", lambda script: {"mean_r": -0.50, "n": 46})
    monkeypatch.setattr(prove_it, "config_hash", lambda script: "different-hash")
    pushed = []
    monkeypatch.setattr(prove_it, "send_ntfy", lambda msg: pushed.append(msg))

    rc = prove_it.main(["--baseline", str(baseline_path), "--replay-script", str(tmp_path / "fake.py")])

    assert rc == 0
    assert pushed == []


def test_missing_replay_script_soft_skips():
    """Harness not present yet (unmerged v3 branch) -> soft-skip, exit 0."""
    rc = prove_it.main(["--replay-script", "/nonexistent/paper_replay.py"])
    assert rc == 0
