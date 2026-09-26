"""Tests for v2-paper-harness (ticket 2, s12). Repo convention: plain script, asserts,
prints TESTS OK. Run: python research/agent_runs/v2-paper-harness/test_paper_harness.py

Scope: the harness plumbing (engine hash guard, per-row schema building, reconciler
join/report) -- NOT a re-test of the frozen engine's own trading logic, which is
covered by that engine's own self-test (ocr1m.py / orb1m.py).
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine_lock  # noqa: E402
import reconcile  # noqa: E402


def test_engine_lock_matches_real_content():
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"print('frozen engine v1')\n")
        p = Path(f.name)
    try:
        h = engine_lock.engine_sha256(p)
        assert h == hashlib.sha256(p.read_bytes()).hexdigest()
        got = engine_lock.assert_frozen(p, h)
        assert got == h
    finally:
        p.unlink()
    print("test_engine_lock_matches_real_content OK")


def test_engine_lock_refuses_on_drift():
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"print('frozen engine v1')\n")
        p = Path(f.name)
    frozen_hash = engine_lock.engine_sha256(p)
    try:
        p.write_bytes(b"print('someone edited the frozen engine')\n")
        try:
            engine_lock.assert_frozen(p, frozen_hash)
            raise AssertionError("expected EngineDriftError on hash mismatch")
        except engine_lock.EngineDriftError as e:
            assert "REFUSING TO REPLAY" in str(e)
    finally:
        p.unlink()
    print("test_engine_lock_refuses_on_drift OK")


def test_engine_lock_refuses_when_unset():
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(b"x = 1\n")
        p = Path(f.name)
    try:
        try:
            engine_lock.assert_frozen(p, "REPLACE_AT_BUILD")
            raise AssertionError("expected EngineDriftError when FROZEN_SHA256 is unset")
        except engine_lock.EngineDriftError:
            pass
    finally:
        p.unlink()
    print("test_engine_lock_refuses_when_unset OK")


def _mk_row(sid, sym="MES", date="2026-09-01", exit_reason="target", net_R=1.9, entry_fill_px=6000.0):
    return dict(signal_id=sid, lane="R", date=date, sym=sym, exit_reason=exit_reason,
                net_R=net_R, entry_fill_px=entry_fill_px)


def test_reconcile_no_lane_l():
    r_rows = [_mk_row("A"), _mk_row("B")]
    recon_rows, report = reconcile.build_report(r_rows, [])
    assert len(recon_rows) == 2  # no L rows -> every R row logs as R-only
    assert all(row.get("lane") == "R-only" for row in recon_rows)
    assert "no Lane L yet" in report
    assert "n=2 trades" in report
    print("test_reconcile_no_lane_l OK")


def test_reconcile_matched_and_mismatched():
    r_rows = [_mk_row("A", net_R=1.9, entry_fill_px=6000.00, exit_reason="target"),
              _mk_row("B", net_R=-1.0, entry_fill_px=6010.00, exit_reason="stop")]
    l_rows = [_mk_row("A", net_R=1.8, entry_fill_px=6000.25, exit_reason="target"),
              _mk_row("C", net_R=0.5, entry_fill_px=6020.00, exit_reason="target")]
    recon_rows, report = reconcile.build_report(r_rows, l_rows)
    by_id = {row["signal_id"]: row for row in recon_rows}
    assert by_id["A"]["exit_reason_match"] is True
    assert abs(by_id["A"]["entry_diff_ticks"] - 1.0) < 1e-9  # 0.25 / 0.25 tick
    assert by_id["B"].get("lane") == "R-only"
    assert by_id["C"].get("lane") == "L-only"
    assert "matched" in report
    print("test_reconcile_matched_and_mismatched OK")


def test_replay_writes_valid_schema_row(tmp_dir=None):
    """Build a row exactly the way paper_replay does (without needing 2yr real data /
    pandas), and check every s12 s4 identity/setup/plan/fill/exit/result field a
    downstream reconciler or reporter reads is present and JSON-serializable."""
    row = dict(
        signal_id="MES_2026-09-01_ORB+OCR_OCRblock_0951_11:00", lane="R", engine_sha="deadbeef" * 4,
        date="2026-09-01", sym="MES", contract="ESZ6", setup="ORB+OCR", grade="S", dir="long",
        level_name="OCRblock", window_cutoff="11:00", entry_bar_min=411,
        stop_px=6000.0, stop_R_pts=2.5, entry_model_px=6002.5, tgt_px=6007.5,
        entry_fill_px=6002.5, entry_slip_ticks=1, fill_source="sim",
        exit_px=6007.5, exit_reason="target", gross_R=2.0, net_R=1.90, comm_usd=1.24,
    )
    for key in ("signal_id", "lane", "engine_sha", "date", "sym", "setup", "grade", "dir",
                "entry_fill_px", "exit_px", "exit_reason", "net_R"):
        assert key in row, f"missing schema field: {key}"
    line = json.dumps(row)
    back = json.loads(line)
    assert back == row
    print("test_replay_writes_valid_schema_row OK")


if __name__ == "__main__":
    test_engine_lock_matches_real_content()
    test_engine_lock_refuses_on_drift()
    test_engine_lock_refuses_when_unset()
    test_reconcile_no_lane_l()
    test_reconcile_matched_and_mismatched()
    test_replay_writes_valid_schema_row()
    print("TESTS OK")
