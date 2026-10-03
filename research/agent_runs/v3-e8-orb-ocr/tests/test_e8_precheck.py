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


class Mnq:
    @staticmethod
    def signal(A, cut, dk, trig, tol, jmax): return (20, 1, 0, 19)   # ORB entry slot 20, long


def _day():
    m = np.arange(540, 661); x = np.ones(len(m)) * 10
    return dict(m=m, o=x, h=x, l=x, c=x)


def _run(monkeypatch, events):
    """events: list of (entry_slot, block_slot, break_slot) for the long side. m starts at 540 -> idx = slot + 30."""
    def fake(ocr, o, hh, ll, c, m, zone, confirm, orb, cutoff):
        if o[0] < 0: return []
        return [(e + 30, 0, 1, bi + 30, bj + 30) for e, bi, bj in events]
    monkeypatch.setattr(e8, "detect_ij", fake)
    return e8.precheck({"2025-01-02": _day()}, Mnq, object())


def test_causal_lag_window(monkeypatch):
    # OCR entry 3 bars BEFORE the ORB entry: counts (lag -3)
    r = _run(monkeypatch, [(17, 10, 14)])
    assert r["coinc_primary"] == 1 and r["primary_dates"] == ["2025-01-02"]
    assert r["causal_a_entry_le_orb"] == 1 and r["causal_b_break_lt_orb"] == 1 and r["causal_c_block_lt_orb"] == 1
    # same bar (lag 0) counts
    assert _run(monkeypatch, [(20, 10, 14)])["coinc_primary"] == 1


def test_ocr_after_orb_entry_never_counts(monkeypatch):
    # OCR entry 3 bars AFTER the ORB entry: legacy abs() counts it, causal must not
    r = _run(monkeypatch, [(23, 22, 22)])
    assert r["coinc_primary"] == 0 and r["legacy_abs_primary"] == 1
    assert r["causal_a_entry_le_orb"] == 0 and r["causal_b_break_lt_orb"] == 0 and r["causal_c_block_lt_orb"] == 0
    assert r["legacy_loose_primary"] == 1


def test_far_before_counts_only_in_level_rows(monkeypatch):
    # entry 12 bars before ORB entry: outside the 5-bar window but causal for rows a/b/c
    r = _run(monkeypatch, [(8, 5, 6)])
    assert r["coinc_primary"] == 0
    assert r["causal_a_entry_le_orb"] == 1 and r["causal_b_break_lt_orb"] == 1 and r["causal_c_block_lt_orb"] == 1


def test_block_before_but_break_after(monkeypatch):
    # block formed before ORB entry, break + entry after it: only row c counts
    r = _run(monkeypatch, [(30, 15, 25)])
    assert r["causal_c_block_lt_orb"] == 1 and r["causal_b_break_lt_orb"] == 0 and r["causal_a_entry_le_orb"] == 0


def test_detect_ij_matches_frozen_detect():
    import mnq, ocr1m
    days = {d: a for d, a in ocr1m.prep("MNQ").items() if "2025-01-13" <= d <= "2025-02-07"}
    assert days and e8.parity(days, ocr1m) == 0
