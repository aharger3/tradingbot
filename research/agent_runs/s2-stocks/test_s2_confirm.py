import csv, numpy as np, s2_lib as L, s2_confirm as K


def test_tap_window():
    r = dict(sig_close_ts="2026-10-05T09:36:00-04:00", tap_ts="2026-10-05T09:37:30-04:00")
    assert K.tap_ok(r) == 90
    assert K.tap_ok(dict(r, tap_ts="2026-10-05T09:38:30-04:00")) is None
    assert K.tap_ok(dict(r, tap_ts="2026-10-05T09:35:59-04:00")) is None


def test_no_look_before_100():
    import tempfile, pathlib
    tmp_path = pathlib.Path(tempfile.mkdtemp())
    t = tmp_path / "t.csv"; c = tmp_path / "c.csv"
    t.write_text("sym,day,sig_t,side,stop,label,sig_close_ts,tap_ts\nAAPL,2026-10-05,10:00,L,99,S,2026-10-05T10:01:00-04:00,2026-10-05T10:02:00-04:00\n")
    c.write_text("sym,day,sig_t,side,stop\n")
    res = K.main(str(t), str(c), str(tmp_path / "o"))
    assert res["status"].startswith("NOT_YET") and "result" not in res
