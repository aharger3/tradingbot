import numpy as np, fto
T = fto.TICK
def day(h, l, c, o=None):
    A = {k: np.full(91, np.nan) for k in ("open", "high", "low", "close")}
    n = len(h); A["high"][:n] = h; A["low"][:n] = l; A["close"][:n] = c
    A["open"][:n] = o if o is not None else c; return A

def test_stop_before_hod_is_minus_1r():
    A = day([101, 101, 100, 99], [99, 99.5, 97, 96], [100, 100, 98, 97])
    pts, why = fto.orig_exit(A, 1, 1, 100.0, 98.0, 2.0, 4, 3, 0.30)
    assert why == "stop" and abs(pts - 3 * (98 - T - 100)) < 1e-9

def test_t1_on_causal_hod_then_be_floor():
    # entry bar1 @100, HOD so far 101; bar2 new high 103, bar3 fails (102.5) -> T1 at close 102.
    # runner: bar4 closes at 99.5 (<= entry BE floor) -> exits at max(close-tick, stop)
    A = day([101, 101, 103, 102.5, 102.6, 102], [99, 99.5, 100.5, 101.5, 101.9, 99], [100, 100, 102.8, 102, 102.4, 99.5])
    pts, why = fto.orig_exit(A, 1, 1, 100.0, 98.0, 2.0, 6, 10, 0.30)
    assert why in ("trail", "struct"), why
    assert pts > 3 * (102 - T - 100) - 7 * 2.0 - 1e-9   # runner never worse than -1R on 7 cts
    assert pts < 3 * (102 - T - 100) + 7 * 3

def test_short_mirror_symmetry():
    L = day([101, 100.5, 99.5, 98.5], [99, 99, 97, 97.5], [100, 100, 97.2, 98])
    S = day([-x for x in [99, 99, 97, 97.5]], [-x for x in [101, 100.5, 99.5, 98.5]], [-x for x in [100, 100, 97.2, 98]])
    a = fto.orig_exit(L, 1, -1, 100.0 - T, 102.0, 2.0, 4, 4, 0.30)
    b = fto.orig_exit(S, 1, 1, -100.0 + T, -102.0, 2.0, 4, 4, 0.30)
    assert a[1] == b[1] and abs(a[0] - b[0]) < 1e-9

def test_n1_single_contract_exits_at_t1():
    A = day([101, 101, 103, 102.5], [99, 99.5, 100.5, 101.5], [100, 100, 102.8, 102])
    pts, why = fto.orig_exit(A, 1, 1, 100.0, 98.0, 2.0, 4, 1, 0.30)
    assert why == "t1" and abs(pts - (102 - T - 100)) < 1e-9
