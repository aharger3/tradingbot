"""Tests for the locked E9 band (e9_band.py). The locked numbers must reproduce from the saved day table."""
import csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e9_band as eb  # noqa: E402
import forward_clock as fc  # noqa: E402


def test_bootstrap_is_deterministic_and_ordered():
    r = [0.0] * 8 + [2.0, -1.0]
    a = eb.bootstrap_band(r, draws=2000)
    assert a == eb.bootstrap_band(r, draws=2000) and a[0][0] < a[0][1]


def test_bootstrap_known_case():
    (lo, hi), mean = eb.bootstrap_band([1.0] * 5, n=17, draws=500)
    assert lo == hi == 17.0 and mean == 17.0


def test_locked_band_matches_saved_day_table():
    with eb.DAYS_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 402 and all(dt.date.fromisoformat(x["date"]).weekday() <= 3 for x in rows)
    (lo, hi), _ = eb.bootstrap_band([float(x["net_R"]) for x in rows])
    assert (round(lo, 4), round(hi, 4)) == (fc.BAND_LO, fc.BAND_HI)
