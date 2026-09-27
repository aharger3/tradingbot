"""Tests for v3 eye4 paper execution. Run: python test_eye_paper.py"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eye_paper as ep

TICK = ep.TICK


def flat_array(n=91, base=100.0):
    return dict(open=np.full(n, base), high=np.full(n, base), low=np.full(n, base), close=np.full(n, base))


def cand(id="C1", side=1, signal_minute=7, stop=100.75, cutoff=90, symbol="MNQ",
         session_extreme=None, named_levels=None, sent="2026-09-26T09:41:00-04:00"):
    return dict(id=id, symbol=symbol, date="2026-09-26", side=side, signal_minute=signal_minute,
                stop=stop, cutoff_minute=cutoff, card_sent_ts=sent,
                session_extreme=session_extreme, named_levels=named_levels or {})


def tap(id="C1", grade="S", ts="2026-09-26T09:42:40-04:00"):
    return dict(candidate_id=id, grade=grade, tap_ts=ts)


def check(name, cond):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}")
    if not cond:
        raise SystemExit(1)


def test_confirm_window():
    c = cand()
    ok, reason, lat = ep.confirm(c, tap())
    check("S within window confirms", ok and reason == "confirmed" and 0 <= lat <= 120)

    ok, reason, _ = ep.confirm(c, tap(grade="not_s"))
    check("not_s rejected", not ok and reason == "grade_not_s")

    ok, reason, lat = ep.confirm(c, tap(ts="2026-09-26T09:43:05-04:00"))  # 125s
    check("late tap (>120s) rejected", not ok and reason == "late_tap")

    ok, reason, _ = ep.confirm(c, None)
    check("no tap rejected", not ok and reason == "no_tap")

    ok, reason, _ = ep.confirm(c, tap(id="OTHER"))
    check("mismatched candidate id rejected", not ok and reason == "tap_id_mismatch")


def test_flat_2r_matches_orb1m_self_test():
    # Exact synthetic from orb1m.py's own `test` block: entry at i=8, side=1,
    # dist=102.25-100.75=1.5, target = entry + 2*dist reached cleanly.
    n = 91
    O = np.full(n, 100.5); H = np.full(n, 101.0); L = np.full(n, 100.0); C = np.full(n, 100.5)
    for j in range(8, n):
        O[j] = 102.0 + (j - 8) * 0.5
        H[j] = 102.5 + (j - 8) * 0.5
        L[j] = 101.9 + (j - 8) * 0.5
        C[j] = 102.4 + (j - 8) * 0.5
    A = dict(open=O, high=H, low=L, close=C)
    entry = A["open"][8] + TICK  # matches orb1m's e = open[i] + TICK*side
    sim = ep.sim_flat_2r(A, 8, 1, entry, 100.75, 90, 5.0, 1.24)
    check("flat_2r sim returns a result", sim is not None)
    r, u, legs = sim
    expected_r = 2 - 1.24 / 7.5
    check(f"flat_2r R matches orb1m self-test ({r:.6f} vs {expected_r:.6f})", abs(r - expected_r) < 1e-9)
    check("flat_2r has a single FLAT_2R leg", legs == [{"name": "FLAT_2R", "weight": 1.0, "r": r}])


def test_run_confirmed_end_to_end_flat():
    # signal_minute=7 -> entry bar i=8, same array as above via day_array injection.
    n = 91
    O = np.full(n, 100.5); H = np.full(n, 101.0); L = np.full(n, 100.0); C = np.full(n, 100.5)
    for j in range(8, n):
        O[j] = 102.0 + (j - 8) * 0.5
        H[j] = 102.5 + (j - 8) * 0.5
        L[j] = 101.9 + (j - 8) * 0.5
        C[j] = 102.4 + (j - 8) * 0.5
    A = dict(open=O, high=H, low=L, close=C)
    c = cand(signal_minute=7, stop=100.75, cutoff=90)
    row = ep.run_confirmed(c, tap(), management="flat_2r", day_array=A)
    check("end-to-end confirmed trade has r/usd", row["confirmed"] and "r" in row and "usd" in row)
    mnq = ep.SPEC["MNQ"]
    expected = 2 - mnq["rt_comm"] / (1.5 * mnq["usd_pt"])  # dist=1.5, MNQ spec (usd_pt=2.0, comm=1.24)
    check("end-to-end R matches direct sim, MNQ spec applied", abs(row["r"] - expected) < 1e-3)


def test_unconfirmed_not_simulated_and_not_journaled():
    c = cand()
    row = ep.run_confirmed(c, tap(grade="not_s"), management="flat_2r", day_array=flat_array())
    check("not_s row is not confirmed and has no r", not row["confirmed"] and "r" not in row)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "acks.jsonl"
        n = ep.append_journal([row], path=path)
        check("unconfirmed row is not written to the journal", n == 0 and not path.exists())


def test_ladder_pt1_then_be_stop():
    # entry=100 (side long), stop=99 (risk=1). PT1 (session_extreme)=100.4 fills,
    # stop moves to BE=100, then price pulls back through BE.
    n = 20
    O = np.full(n, 99.75); H = np.full(n, 100.1); L = np.full(n, 99.7); C = np.full(n, 100.0)
    entry = O[1] + TICK  # = 100.0
    stop0 = 99.0
    rungs = ep.build_rungs(entry, stop0, 1, session_extreme=100.4, named_levels={})
    check("ladder has >=2 rungs for this setup", len(rungs) >= 2)
    check("rung weights sum to 1.0", abs(sum(r.weight for r in rungs) - 1.0) < 1e-9)

    # bar 2: touch PT1 (need = 100.4 + TICK)
    O[2], H[2], L[2], C[2] = 100.5, 100.7, 100.5, 100.6
    # bar 3: pull back through BE (100.0)
    O[3], H[3], L[3], C[3] = 100.6, 100.65, 99.9, 100.2
    A = dict(open=O, high=H, low=L, close=C)

    sim = ep.sim_ladder_4tier(A, 1, 1, entry, stop0, 15, 2.0, 1.24, 100.4, {})
    check("ladder sim returns a result", sim is not None)
    r, u, legs = sim
    names = [l["name"] for l in legs]
    check("nearest tier (T1) fills before the stop", names[0] == "T1")
    check("remainder exits at STOP (breakeven, not the original 99.0 stop)", names[-1] == "STOP")
    stop_leg = legs[-1]
    check(f"BE stop exits near entry, not original stop ({stop_leg['price']} vs entry {entry}, orig stop {stop0})",
          abs(stop_leg["price"] - entry) <= 2 * TICK and abs(stop_leg["price"] - stop0) > 0.5)
    # internal consistency: total R == sum of leg contributions
    recon = sum((l["price"] - entry) / abs(entry - stop0) * l["weight"] for l in legs)
    check("returned R reconciles against its own legs", abs(r - recon) < 1e-9)
    check("PT1 partial profit means total R beats a straight stop-out (-1R)", r > -1.0)


def test_ladder_runner_flat_at_cutoff():
    # Nothing ever touches a rung or the stop -> full weight exits at the
    # cutoff bar's open (the runner), per s04 sec 3 "11:00: flat except runner".
    n = 20
    O = np.full(n, 99.75); H = np.full(n, 100.1); L = np.full(n, 99.9); C = np.full(n, 100.0)
    entry = O[1] + TICK
    stop0 = 99.0
    cut = 10
    O[cut] = 100.05
    A = dict(open=O, high=H, low=L, close=C)
    r, u, legs = ep.sim_ladder_4tier(A, 1, 1, entry, stop0, cut, 2.0, 1.24, 100.4, {})
    check("only a RUNNER_FLAT leg fires", [l["name"] for l in legs] == ["RUNNER_FLAT"])
    check("runner leg carries full weight", abs(legs[0]["weight"] - 1.0) < 1e-9)


def test_degenerate_stop_skipped():
    c = cand(stop=101.9)  # entry ~101.15 for this array -> risk < 2 ticks region isn't guaranteed;
    # use an explicit near-entry stop instead, injected directly:
    A = flat_array()
    A["open"][8] = 100.0
    c2 = cand(signal_minute=7, stop=100.24)  # entry = 100.25, risk = 0.01 < 2 ticks
    row = ep.run_confirmed(c2, tap(), management="flat_2r", day_array=A)
    check("degenerate stop distance is skipped, not silently traded", not row["confirmed"] and row["reason"] == "degenerate_stop")


def test_journal_roundtrip_matches_daily_report_schema():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "acks.jsonl"
        row = {"id": "S0941-1", "date": "2026-09-26", "confirmed": True, "r": 0.42, "usd": 33.5}
        n = ep.append_journal([row], path=path)
        check("one confirmed row written", n == 1)
        written = json.loads(path.read_text().splitlines()[0])
        # this is exactly what daily_report.py's load_today_signals/main loop needs:
        check("journal row has 'date' and 'r' (daily_report.py compatible)",
              written.get("date") == "2026-09-26" and written.get("r", written.get("R")) is not None)
        summary = ep.daily_summary("2026-09-26", path=path)
        check("daily_summary aggregates the written row", summary["n"] == 1 and summary["mean_r"] == 0.42)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} test functions passed")
