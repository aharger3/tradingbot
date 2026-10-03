import numpy as np, pytest
from firm_mc import FIRMS, sim, eval_fee

def det(rs, stops=20.0):
    r = np.array(rs, float)[:, None]; st = np.full_like(r, stops)
    sess = np.arange(1, len(rs) + 1, dtype=float)[:, None]
    return r, st, sess

def test_steady_wins_pass_lucid_at_expected_session():
    # 12 cts x 2R x 20pt x $2 = $960 - comm; 4 wins > $3K, each day < 50% of profit
    r, st, sess = det([2.0] * 6)
    out = sim(FIRMS['LucidFlex'], [[12, 12, 12]], r, st, sess)
    assert out['pass_s'][0, 0] == 4

def test_consistency_blocks_single_big_day():
    # one huge day then small days: best-day share must fall to <=40% before Tradeify pass
    r, st, sess = det([8.0] + [1.0] * 20)
    lu = sim(FIRMS['LucidFlex'], [[12, 12, 12]], r, st, sess)['pass_s'][0, 0]
    tr = sim(FIRMS['Tradeify'], [[12, 12, 12]], r, st, sess)['pass_s'][0, 0]
    assert (lu, tr) == (10, 14)

def test_topstep_dll_caps_loss_not_fail():
    r, st, sess = det([-3.0], stops=30.0)   # 12 x 3R x 30 x 2 = $2160 loss uncapped
    out = sim(FIRMS['Topstep'], [[12, 12, 12]], r, st, sess, h_eval=1)
    assert out['phase'][0, 0] != 2           # capped at $1000, cushion $2000 -> survives
    out2 = sim(FIRMS['LucidFlex'], [[12, 12, 12]], r, st, sess, h_eval=1)
    assert out2["phase"][0, 0] == 2          # no DLL at Lucid -> trail breached

def test_min_days_topstep():
    r, st, sess = det([2.0] * 6)
    f = dict(FIRMS['LucidFlex'], min_days=5)
    assert sim(f, [[12, 12, 12]], r, st, sess)['pass_s'][0, 0] == 5

def test_topstep_fee_monthly_plus_activation():
    f = FIRMS['Topstep']
    assert eval_fee(f, np.array([10.0]), np.array([True]))[0] == 49 + 149
    assert eval_fee(f, np.array([40.0]), np.array([False]))[0] == 49 * 3
    assert eval_fee(FIRMS['LucidFlex'], np.array([150.0]), np.array([True]))[0] == 146

def test_quit_horizon_stops_eval():
    r, st, sess = det([0.0] * 100)          # flat forever -> timeout
    out = sim(FIRMS['Topstep_q60'], [[12, 12, 12]], r, st, sess)
    assert out['phase'][0, 0] == 3 and out['end_s'][0, 0] == 60
