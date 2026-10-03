"""R-EBP1: the blind-test pass bar (life-plan 07-money/omen/v3/blind-test-prereg.md) as tests.

Four fixture tap ledgers (tests/fixtures/passbar_*.jsonl, synthetic R, no real taps) -> one
verdict each, plus the prereg's edges. Also the R98 invariants: no card bar after the decision
bar, no pool session date from s_trades.csv, and a fixture session writes a scored row.
"""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "eye_blind" / "tests"))

from research.eye import passbar as P  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
S_TRADES = REPO / "research" / "agent_runs" / "eye1" / "s_trades.csv"


def ledger(name):
    return [json.loads(x) for x in (FIX / f"passbar_{name}.jsonl").read_text().splitlines() if x.strip()]


def rows(n_s, n_n, r_s, r_n):
    # Not-S first: the ledger locks on the 30th S tap, so it must be the last row used
    return [dict(label="notS", R=r_n)] * n_n + [dict(label="S", R=r_s)] * n_s


# ---- the 4 ledger cases ------------------------------------------------------------------
def test_ledger_pass():
    r = P.passbar(ledger("pass_s30"))
    assert r["verdict"] == "PASS" and r["n_S"] == 30
    assert r["mean_R_S"] >= 0.25 and r["p_perm"] < 0.05


def test_ledger_fail_mean_below_bar():  # real gap (p < .05) but S mean < +0.25R -> FAIL
    r = P.passbar(ledger("fail_mean_below_bar"))
    assert r["verdict"] == "FAIL" and r["n_S"] == 30
    assert r["mean_R_S"] < 0.25 and r["p_perm"] < 0.05


def test_ledger_fail_p_above_bar():  # S mean >= +0.25R but p >= .05 -> FAIL
    r = P.passbar(ledger("fail_p_above_bar"))
    assert r["verdict"] == "FAIL" and r["n_S"] == 30
    assert r["mean_R_S"] >= 0.25 and r["p_perm"] >= 0.05


def test_ledger_pending_under_30_s():  # 29 S, huge edge, still not a verdict
    r = P.passbar(ledger("pending_29s"))
    assert r["verdict"] == "PENDING" and r["n_S"] == 29 and r["p_perm"] is None


# ---- prereg edges ------------------------------------------------------------------------
def test_prereg_numbers_are_the_locked_ones():
    assert (P.MIN_S_TAPS, P.PASS_MEAN_R, P.ALPHA, P.N_SHUFFLES, P.MAX_SESSIONS) == (30, 0.25, 0.05, 10_000, 60)


def test_mean_exactly_at_bar_passes_and_just_under_fails():
    # S all +0.25 vs Not-S all -1.0: p tiny, so only the mean bar decides
    assert P.passbar(rows(30, 10, 0.25, -1.0), n_shuffles=500)["verdict"] == "PASS"
    assert P.passbar(rows(30, 10, 0.2499, -1.0), n_shuffles=500)["verdict"] == "FAIL"


def test_inconclusive_at_60_sessions_with_few_s_not_a_pass():
    r = P.passbar(rows(10, 50, 3.0, -1.0))
    assert r["verdict"] == "INCONCLUSIVE" and r["n_S"] == 10
    assert P.passbar(rows(10, 49, 3.0, -1.0))["verdict"] == "PENDING"  # 59 sessions


def test_verdict_freezes_at_30th_s_tap():
    early = rows(30, 20, 0.0, 0.0)
    late = [dict(label="S", R=9.0)] * 40  # hindsight taps after the lock must not flip it
    r = P.passbar(early + late)
    assert r["verdict"] == "FAIL" and r["n_post_lock"] == 40 and r["mean_R_S"] == 0.0


def test_bad_label_rejected():
    with pytest.raises(ValueError):
        P.passbar([dict(label="L", R=1.0)])


# ---- R98 invariants on the blind pool ----------------------------------------------------
@pytest.fixture(scope="module")
def pool():
    pytest.importorskip("pandas")
    from test_blind import KINDS, make_bars
    from eye_blind import core
    return core.build_pool(make_bars(KINDS), seed=1, salt="t")


def test_no_card_bar_after_decision_bar(pool):
    from eye_blind import core
    for sid in pool["order"][:5]:
        s = pool["sessions"][sid]
        svg = core.render_svg(s, pool["cfg"])
        assert len(re.findall(r'<rect class="(?:up|dn)', svg)) == s["i"]  # bars 0..i-1; decision bar last
        # same session with every later bar rewritten renders byte-identical
        alt = dict(s, A={k: v[:s["i"]] + [(v[s["i"]] or 0) + 500.0] * (len(v) - s["i"]) for k, v in s["A"].items()})
        assert core.render_svg(alt, pool["cfg"]) == svg


def test_no_pool_session_date_is_in_s_trades(pool):
    if not S_TRADES.exists():  # research/**/*.csv is not checked out in sparse clones
        pytest.skip("s_trades.csv not checked out")
    import csv
    seen = {r["date"] for r in csv.DictReader(S_TRADES.open())}
    assert seen, "s_trades.csv has no dates"
    assert {s["date"] for s in pool["sessions"].values()}.isdisjoint(seen)


def test_fixture_session_writes_a_scored_row(pool, tmp_path):
    from eye_blind import core
    sid = pool["order"][0]
    taps = [dict(session_id=sid, label="S")]
    out = tmp_path / "acks_blind_scored.jsonl"
    with open(out, "w") as fh:
        for row in core.scored_rows(pool, taps):
            fh.write(json.dumps(row) + "\n")
    got = [json.loads(x) for x in out.read_text().splitlines()]
    assert len(got) == 1 and got[0]["session_id"] == sid and got[0]["label"] == "S"
    assert got[0]["R"] == core.trade_r(pool["sessions"][sid], pool["cfg"])
    assert set(got[0]) == {"session_id", "label", "R"}  # no date / price leaks into the log


def test_passbar_agrees_with_core_scorer(pool):
    from eye_blind import core
    # S on every winner, Not-S on losers: both scorers must give the same verdict and p
    taps = [dict(session_id=sid, label="S" if core.trade_r(pool["sessions"][sid], pool["cfg"]) > 0 else "notS")
            for sid in pool["order"]]
    ref = core.score(pool, taps)
    mine = P.passbar(core.scored_rows(pool, taps))
    assert mine["verdict"] == ref["verdict"] == "PASS"
    assert mine["p_perm"] == ref["p_perm"] and mine["n_S"] == ref["S"]["n"]
