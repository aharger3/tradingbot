import datetime as dt, pandas as pd
from zoneinfo import ZoneInfo
from calls_nq import simulate, setup_tag
ET = ZoneInfo('America/New_York')

def bars(rows):
    t0 = dt.datetime(2025, 1, 2, 9, 30, tzinfo=ET)
    return pd.DataFrame(rows, columns=['open', 'high', 'low', 'close'],
                        index=[t0 + dt.timedelta(minutes=i) for i in range(len(rows))])

def test_long_hits_target():
    b = bars([(100, 101, 99, 100)] * 8 + [(100, 101, 99, 100.5), (100.5, 120, 100.5, 119)] + [(119, 119, 119, 119)] * 5)
    r = simulate(b, dt.datetime(2025, 1, 2, 9, 37, 30, tzinfo=ET), 'long', 'NQ')
    assert r['entry'] == 100.25 and r['stop'] == 98.75 and r['exit'] == 'target'
    assert abs(r['R'] - (2 - 4.5 / 20 / 1.5)) < 1e-6

def test_stop_first_when_both_in_bar():
    b = bars([(100, 101, 99, 100)] * 8 + [(100, 130, 90, 100)] * 3)
    r = simulate(b, dt.datetime(2025, 1, 2, 9, 37, tzinfo=ET), 'long', 'NQ')
    assert r['exit'] == 'stop' and r['R'] < -1

def test_no_bars_after_message():
    assert simulate(bars([(1, 1, 1, 1)] * 3), dt.datetime(2025, 1, 2, 12, 0, tzinfo=ET), 'long', 'ES') is None

def test_setup_tags():
    assert setup_tag('got back in 84% rule') == '84-reclaim'
    assert setup_tag('TOOK TSLA 184 CALLS') == 'unstated'
    assert setup_tag('5 min retest + OB') == 'OB'
    assert setup_tag('Took 461 puts on qqq retest') == 'retest'
    assert setup_tag('TOOK TSLA 225 CALLS for HOD') == 'HOD/LOD'
