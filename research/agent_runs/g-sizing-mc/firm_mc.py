# Per-firm eval pass Monte Carlo: LucidFlex / Topstep / Tradeify 50K, MNQ ladders (paper only).
# Extends mc.py (LucidFlex-only) with a FIRMS rule table. R shape = empirical S trades
# (eye1/s_trades.csv R2_eng); edge per scenario with per-path N(mu,se) uncertainty.
import numpy as np, pandas as pd, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
PT, COMM, SLIP = 2.0, 1.24, 0.5          # MNQ $/pt, RT commission, cushion slack per ct
SESS_PER_MONTH = 17.3                    # Mon-Thu sessions per month
H_EVAL, H_FUND = 200, 120
# Rules: u06-prop-firms.md (2026-09-26). lock = floor stops trailing at start+lock.
FIRMS = {
  'LucidFlex': dict(target=3000, dd=2000, lock=100, dll=None, cons=0.50, min_days=0, cap=40,
                    fee_once=146, fee_month=0, activation=0,
                    f_lock=100, f_dll=None, f_winday=150, f_frac=0.50, f_cap=2000),
  'Topstep':   dict(target=3000, dd=2000, lock=0, dll=1000, cons=0.50, min_days=2, cap=50,
                    fee_once=0, fee_month=49, activation=149,
                    f_lock=0, f_dll=1000, f_winday=150, f_frac=0.50, f_cap=5000),
  'Tradeify':  dict(target=3000, dd=2000, lock=100, dll=None, cons=0.40, min_days=3, cap=40,
                    fee_once=165, fee_month=0, activation=0,
                    f_lock=100, f_dll=None, f_winday=150, f_frac=0.50, f_cap=3000),
}
FIRMS['Topstep_q60'] = dict(FIRMS['Topstep'], h_eval=60)   # quit the subscription after 60 sessions
LADDERS = ['12/10/6', '12/8/6', '10/8/4', '6/6/6']
EDGES = {'B_allS': (0.38, 0.127), 'C_half': (0.19, 0.127), 'D_zero': (0.0, 0.127)}

def eval_fee(firm, sessions_used, passed):
    """Fee paid for one eval: one-time + monthly subscription for months touched + activation on pass."""
    months = np.ceil(np.maximum(sessions_used, 1) / SESS_PER_MONTH)
    return firm['fee_once'] + firm['fee_month'] * months + firm['activation'] * passed

def sim(firm, LAD, r, stop, sess, h_eval=H_EVAL, h_fund=H_FUND):
    """Core path sim. LAD (L,3) contracts at profit <1k / 1-2k / >=2k; r, stop, sess (NT,P).
    One trade per trade-session. Returns dict of (L,P) arrays."""
    h_eval = firm.get('h_eval', h_eval)
    LAD = np.asarray(LAD); L = len(LAD); NT, P = r.shape; Lx = LAD[:, :, None]
    bal = np.full((L, P), 50000.); hi = bal.copy(); floor = bal - firm['dd']
    best = np.zeros((L, P)); nd = np.zeros((L, P))
    phase = np.zeros((L, P), np.int8)   # 0 eval 1 funded 2 bust-eval 3 timeout 4 paid 5 bust-funded
    end_s = np.full((L, P), float(h_eval)); pass_s = np.full((L, P), np.nan)
    fstart = np.zeros((L, P)); pdays = np.zeros((L, P)); payout = np.zeros((L, P))
    for k in range(NT):
        sk = np.broadcast_to(sess[k][None, :], (L, P))
        phase[(phase == 0) & (sk > h_eval)] = 3
        act0 = (phase == 0); act1 = (phase == 1) & (sk - fstart <= h_fund)
        act = act0 | act1
        if not act.any(): break
        prof = bal - 50000
        tier = np.where(prof < 1000, Lx[:, 0], np.where(prof < 2000, Lx[:, 1], Lx[:, 2]))
        per = stop[k][None, :] * PT + COMM + SLIP
        cap = firm['cap']
        n = np.minimum(np.minimum(tier, cap), np.floor((bal - floor - 50) / per)).clip(0)
        pnl = n * (r[k][None, :] * stop[k][None, :] * PT - COMM)
        dll = np.where(phase == 1, firm['f_dll'] or np.inf, firm['dll'] or np.inf)
        pnl = np.maximum(pnl, -dll)                      # soft DLL: flattened, not failed
        pnl = np.where(act, pnl, 0.)
        busted = act & (bal + pnl <= floor)
        bal = bal + pnl; hi = np.maximum(hi, bal)
        best = np.where(act0, np.maximum(best, pnl), best); nd += act0
        lockv = 50000. + np.where(phase == 1, firm['f_lock'], firm['lock'])
        floor = np.where(act, np.maximum(floor, np.minimum(hi - firm['dd'], lockv)), floor)
        be = busted & (phase == 0); phase[be] = 2; end_s[be] = sk[be]
        phase[busted & (phase == 1)] = 5
        tp = bal - 50000
        passed = act0 & ~busted & (tp >= firm['target']) & (best <= firm['cons'] * tp) & (nd >= firm['min_days'])
        pass_s[passed] = sk[passed]; end_s[passed] = sk[passed]; phase[passed] = 1
        fstart[passed] = sk[passed]; bal[passed] = 50000.; hi[passed] = 50000.
        floor[passed] = 50000. - firm['dd']
        good = act1 & ~busted & (pnl >= firm['f_winday']); pdays += good
        pay = act1 & ~busted & (pdays >= 5) & (bal > 50000)
        payout[pay] = np.minimum(firm['f_frac'] * (bal - 50000)[pay], firm['f_cap']) * 0.9; phase[pay] = 4
    return dict(phase=phase, pass_s=pass_s, end_s=end_s, payout=payout)

def draws(mu, se, freq, P, rng, R, ex):
    flatR, thruR = R[ex == 'flat'], R[ex == 'stop_thru_fill']
    sf, st = len(flatR) / len(R), len(thruR) / len(R)
    WIN, LOSS = R[ex == 'tgt'].mean(), R[ex == 'stop'].mean()
    rest = 1 - sf - st; base = sf * flatR.mean() + st * thruR.mean()
    mu_p = mu + rng.normal(0, se, P)
    pw = np.clip((mu_p - base - rest * LOSS) / (WIN - LOSS), 0.02, rest - 0.02)
    NT = int((H_EVAL + H_FUND) * freq * 2) + 20
    sess = np.cumsum(rng.geometric(freq, (NT, P)), 0)
    u = rng.random((NT, P))
    r = np.where(u < sf, rng.choice(flatR, (NT, P)),
        np.where(u < sf + st, rng.choice(thruR, (NT, P)),
        np.where(u < sf + st + pw, WIN, LOSS)))
    stop = np.clip(np.exp(rng.normal(np.log(21), 0.45, (NT, P))), 6, 70)
    return r, stop, sess

def summarize(firm, res, lads):
    ps = ~np.isnan(res['pass_s']); res['end_s'] = np.minimum(res['end_s'], firm.get('h_eval', H_EVAL)); fee = eval_fee(firm, res['end_s'], ps)
    return pd.DataFrame({'lad': lads, 'pass': ps.mean(1), 'pass60': (res['pass_s'] <= 60).mean(1),
        'med': np.nanmedian(np.where(ps, res['pass_s'], np.nan), 1),
        'bust': (res['phase'] == 2).mean(1), 'payP': (res['phase'] == 4).mean(1),
        'fee': fee.mean(1), 'EV': res['payout'].mean(1) - fee.mean(1)})

if __name__ == '__main__':
    P = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    d = pd.read_csv(os.path.join(HERE, '..', 'eye1', 's_trades.csv'))
    s = d[d.grade == 'S'].dropna(subset=['R2_eng']); R, ex = s.R2_eng.values, s.exit2_eng.values
    LAD = [list(map(int, x.split('/'))) for x in LADDERS]
    rows = []
    for en, (mu, se) in EDGES.items():
        rng = np.random.default_rng(7)                   # common random numbers across firms
        r, stop, sess = draws(mu, se, 0.25, P, rng, R, ex)
        for fn, f in FIRMS.items():
            o = summarize(f, sim(f, LAD, r, stop, sess), LADDERS); o['firm'] = fn; o['edge'] = en; rows.append(o)
    out = pd.concat(rows); out.to_csv(os.path.join(HERE, 'firm_mc.csv'), index=False)
    pd.set_option('display.width', 200)
    print(out.round(3).to_string(index=False))
