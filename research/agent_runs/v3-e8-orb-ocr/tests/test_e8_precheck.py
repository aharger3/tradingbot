import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import e8_precheck as e8


def test_fit_window_guard():
    assert e8.in_fit("2024-09-26") and e8.in_fit("2026-09-25")
    assert not e8.in_fit("2024-09-25") and not e8.in_fit("2026-09-28")


def test_window_a_date_rejected():
    class M: pass
    try:
        e8.precheck({"2024-09-25": {}}, M, M)
    except AssertionError:
        return
    raise AssertionError("window A date was accepted")


def test_to_A_maps_minutes():
    m = np.array([569, 570, 571, 660, 661]); x = np.arange(5, dtype=float)
    A = e8.to_A(dict(m=m, o=x, h=x, l=x, c=x))
    assert A["open"][0] == 1 and A["open"][1] == 2 and A["open"][90] == 3 and np.isnan(A["open"][5])


def test_coincidence_counting():
    class Mnq:
        @staticmethod
        def signal(A, cut, dk, trig, tol, jmax): return (20, 1, 0, 19)
    class Ocr:
        calls = []
        @staticmethod
        def detect(o, hh, ll, c, m, zone, confirm, orb, cutoff):
            return [(22 - 0, 0, 1)] if o[0] > 0 else []   # long side only; entry idx 22 -> minute m[22]
    m = np.arange(540, 661); x = np.ones(len(m)) * 10
    a = dict(m=m, o=x, h=x, l=x, c=x)
    r = e8.precheck({"2025-01-02": a}, Mnq, Ocr)
    # OCR entry idx 22 -> minute 540+22=562 -> slot -8: not within 5 of ORB slot 20
    assert r["orb_primary"] == 1 and r["coinc_primary"] == 0 and r["coinc_loose_primary"] == 1
    class Ocr_far(Ocr):
        @staticmethod
        def detect(o, hh, ll, c, m, zone, confirm, orb, cutoff): return [(90, 0, 1)] if o[0] > 0 else []  # slot 60
    assert e8.precheck({"2025-01-02": a}, Mnq, Ocr_far)["coinc_primary"] == 0
    class Ocr_near(Ocr):
        @staticmethod
        def detect(o, hh, ll, c, m, zone, confirm, orb, cutoff): return [(52, 0, 1)] if o[0] > 0 else []  # slot 22
    r4 = e8.precheck({"2025-01-02": a}, Mnq, Ocr_near)
    assert r4["coinc_primary"] == 1 and r4["primary_dates"] == ["2025-01-02"]
