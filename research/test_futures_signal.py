"""Plain asserts for futures_signal.py.

    python research/test_futures_signal.py

Needs the NQ bars already fetched into
research/agent_runs/t02-break-retest/bars/*.json.gz (they are -- fetch_nq.py's
output from the B1/t02 work). If that directory is empty on a fresh clone,
this test says so and exits nonzero rather than silently passing.

Checks:
 1. futures_signal's find_signal_for_day() picks the SAME signal, on the
    SAME sessions, as calling bt.py's own signals()/trade() directly --
    trade-for-trade, for every session in the first 5 that fire (satisfies
    ship-plan B2's "signals match bt.py trade-for-trade" replay check).
 2. price_levels() is consistent with trade()'s own `dist`: entry-stop and
    target-entry distances equal dist and 3*dist exactly.
 3. build_push() always carries the EXPERIMENTAL/PAPER flag, never omits it,
    and never claims a confirmed edge.
 4. journal_line()/append_journal() round-trips through JSON with the
    honest-fill fields (R, usd, exit_reason) intact.
 5. live() with no feed configured is a clean no-op: no exception, no
    journal write, no push -- checked by monkeypatching notify_ntfy.push to
    fail the test if it is ever called.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import futures_signal as fs  # noqa: E402


def _bars_available():
    bars_dir = fs.BT_PATH.parent / "bars"
    return bars_dir.is_dir() and any(bars_dir.glob("NQ_*.json.gz"))


def main():
    if not _bars_available():
        print("SKIP-FAIL: no NQ bars at "
              f"{fs.BT_PATH.parent / 'bars'} -- fetch_nq.py must run first. "
              "Cannot verify trade-for-trade parity without them.")
        sys.exit(1)

    bt = fs._load_bt()
    sessions = bt.sessions(fs.ROOT)
    dates = sorted(sessions)
    assert len(dates) >= 20, f"expected a real multi-month NQ book, got {len(dates)} sessions"

    # 1 & 2: trade-for-trade parity against bt.py's own functions, on the
    # first 5 sessions that actually fire a signal.
    checked = 0
    for D in dates:
        S = sessions[D]
        direct_sigs = bt.signals(S, fs.LEVELSET)
        direct = None
        for sig in direct_sigs:
            t = bt.trade(S, sig, fs.STOPMODE, fs.TARGET_K, fs.ROOT, net=True)
            if t:
                direct = (sig, t)
                break
        via_module = fs.find_signal_for_day(bt, S)

        if direct is None and via_module is None:
            continue  # both agree: no trade this session
        assert direct is not None and via_module is not None, (
            f"{D}: bt.py direct={direct} but futures_signal={via_module} -- disagreement")
        (di, dd, dl, dri, dname), dt = direct
        (mi, md, ml, mri, mname), mt = via_module
        assert (di, dd, dl, dri, dname) == (mi, md, ml, mri, mname), (
            f"{D}: signal mismatch direct={direct[0]} module={via_module[0]}")
        assert dt["R"] == mt["R"] and dt["usd"] == mt["usd"] and dt["n"] == mt["n"], (
            f"{D}: trade outcome mismatch direct={dt} module={mt}")

        px = fs.price_levels(S, via_module[0], mt)
        # entry-to-stop distance must equal trade()'s own `dist` (direction-adjusted)
        d = via_module[0][1]
        assert abs((px["entry"] - px["stop"]) * d - mt["dist"]) < 1e-6, (
            f"{D}: stop distance {px['entry']-px['stop']} != trade() dist {mt['dist']}")
        assert abs((px["target"] - px["entry"]) * d - fs.TARGET_K * mt["dist"]) < 1e-6, (
            f"{D}: target distance != {fs.TARGET_K} x dist")

        checked += 1
        if checked >= 5:
            break
    assert checked >= 1, (
        "no NQ session in the whole book produced a fireable B&R signal -- "
        "either the bars window is too short or something upstream broke")
    print(f"ok   futures_signal matches bt.py trade-for-trade on {checked} "
          f"fired session(s), price levels agree with trade()'s own dist")

    # 3. build_push always flags EXPERIMENTAL/PAPER, never silent.
    fired_date = None
    for D in dates:
        if fs.find_signal_for_day(bt, sessions[D]) is not None:
            fired_date = D
            break
    S = sessions[fired_date]
    sig, t = fs.find_signal_for_day(bt, S)
    push = fs.build_push(fired_date, S, sig, t)
    assert "EXPERIMENTAL" in push["title"], push["title"]
    assert "PAPER" in push["body"] and "no confirmed edge" in push["body"], push["body"]
    assert push["entry"] and push["stop"] and push["target"] and push["size_mnq"] > 0
    print("ok   build_push() always carries EXPERIMENTAL + PAPER + no-confirmed-edge flags")

    # 4. journal round-trip.
    rec = fs.journal_line(fired_date, S, sig, t, source="replay")
    assert rec["flag"] == "EXPERIMENTAL_PAPER_ONLY"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "paper_nq.jsonl"
        fs.append_journal(rec, path=p)
        lines = p.read_text().splitlines()
        assert len(lines) == 1
        back = json.loads(lines[0])
        assert back["r_multiple"] == round(t["R"], 4)
        assert back["usd"] == round(t["usd"], 2)
        assert back["exit_reason"] == t["why"]
    print("ok   journal_line()/append_journal() round-trips the honest-fill fields")

    # 5. live() with no feed configured never pushes, never journals, never raises.
    calls = []
    import notify_ntfy
    orig_push = notify_ntfy.push
    notify_ntfy.push = lambda *a, **k: calls.append((a, k)) or (_ for _ in ()).throw(
        AssertionError("live() must never push with no feed configured"))
    try:
        class _Args:
            pass
        fs.cmd_live(_Args())
    finally:
        notify_ntfy.push = orig_push
    assert calls == []
    print("ok   live() with no feed configured is a clean no-op (no push, no crash)")

    print("ALL OK")


if __name__ == "__main__":
    main()
