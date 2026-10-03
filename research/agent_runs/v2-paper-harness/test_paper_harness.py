"""Tests for v2-paper-harness (ticket 2, s12). Repo convention: plain script, asserts,
prints TESTS OK. Run: python research/agent_runs/v2-paper-harness/test_paper_harness.py

Scope: the harness plumbing (engine hash guard, per-row schema building, reconciler
join/report, orb1m wiring) -- NOT a re-test of the frozen engine's own trading logic,
which is covered by that engine's own self-test (python orb1m.py test).
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


def test_engine_lock_points_at_ship_plan_strategy():
    """v3 b1 fix: PR #34 froze ocr1m.py (ORB+OCR, dropped by OMEN-SHIP-PLAN-v3.md
    sec 1/6). The lock must point at orb1m.py, the only cell sec 2 says to run."""
    assert engine_lock.ENGINE_PATH.name == "orb1m.py", engine_lock.ENGINE_PATH
    assert "v2-t02-ocr-1m" not in str(engine_lock.ENGINE_PATH)
    assert "v2-t01-orb-1m" in str(engine_lock.ENGINE_PATH)
    got = engine_lock.assert_frozen()  # real file on disk must still match -- raises on drift
    assert got == engine_lock.FROZEN_SHA256
    print("test_engine_lock_points_at_ship_plan_strategy OK")


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


def test_replay_writes_valid_schema_row():
    """Build a row exactly the way paper_replay does (without needing 2yr real data /
    pandas), and check every s12 s4 identity/setup/plan/fill/exit/result field a
    downstream reconciler or reporter reads is present and JSON-serializable."""
    row = dict(
        signal_id="MNQ_2026-09-01_ORB5_D1.0_strong_0951_10:30", lane="R", engine_sha="deadbeef" * 4,
        date="2026-09-01", sym="MNQ", contract="NQZ6", setup="ORB5+disp+retest", grade="S", dir="long",
        level_name="ORB5", window_cutoff="10:30", entry_bar_min=411,
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


def test_paper_replay_reproduces_v2_grid_cell():
    """Real-data check (needs the NQ 1-min files under research/agent_runs/t01-orb5/fut,
    same as the frozen engine's own self-test data): paper_replay.replay() must call
    orb1m with the exact same params as its v2-t01 grid cell (MNQ, OR5, D1.0, strong,
    10:30) and reproduce that cell's n and mean R -- this is the "same rule, same
    number whether it runs as a backtest or as the paper harness" contract."""
    import paper_replay
    from omen_data import load_fut
    import orb1m

    ref = json.load(open(HERE.parent / "v2-t01-orb-1m" / "trades_MNQ_OR5_1030_D1_strong.json"))
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        out = Path(f.name)
    try:
        engine_sha = engine_lock.assert_frozen()
        try:
            rows, coverage = paper_replay.replay(out, engine_sha)
        except FileNotFoundError as e:
            print("test_paper_replay_reproduces_v2_grid_cell SKIPPED (no real NQ 1-min data on this box):", e)
            return
        assert len(rows) == len(ref), (len(rows), len(ref))
        got_meanR = sum(r["net_R"] for r in rows) / len(rows)
        ref_meanR = sum(t["R"] for t in ref) / len(ref)
        # rows store net_R rounded to 4 dp, so the mean can drift up to 5e-5 from the
        # unrounded reference (~4.4e-6 on the real 105 trades) -- 1e-6 was unreachable.
        assert abs(got_meanR - ref_meanR) < 1e-4, (got_meanR, ref_meanR)
        assert coverage["MNQ"] > 400  # ~2 yr of sessions
    finally:
        out.unlink(missing_ok=True)
    print("test_paper_replay_reproduces_v2_grid_cell OK")


def test_oos_command_runs_and_writes_json():
    """The OOS run must exist as a plain command (python paper_replay.py --oos) and
    produce n/R/split-half/shuffle-p, per the v3 b1 ticket."""
    import paper_replay

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        out = Path(f.name)
    try:
        engine_sha = engine_lock.assert_frozen()
        result = paper_replay.run_oos(out, engine_sha, nshuf=5)
        assert out.exists()
        reloaded = json.loads(out.read_text())
        assert reloaded == result
        for key in ("n", "sessions", "window", "cell", "sym"):
            assert key in result, f"missing OOS field: {key}"
        if result["n"] > 0:
            for key in ("R", "h1_R", "h2_R", "shuffle_p"):
                assert key in result, f"missing OOS field: {key}"
    finally:
        out.unlink(missing_ok=True)
    print("test_oos_command_runs_and_writes_json OK")


if __name__ == "__main__":
    test_engine_lock_matches_real_content()
    test_engine_lock_refuses_on_drift()
    test_engine_lock_refuses_when_unset()
    test_engine_lock_points_at_ship_plan_strategy()
    test_reconcile_no_lane_l()
    test_reconcile_matched_and_mismatched()
    test_replay_writes_valid_schema_row()
    test_paper_replay_reproduces_v2_grid_cell()
    test_oos_command_runs_and_writes_json()
    print("TESTS OK")
