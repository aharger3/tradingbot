"""pytest research/test_front_month.py -- Dec-2025 roll week + volume crossover."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import front_month as fm  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "front_month_fut"


def test_dec_2025_expiry_and_roll_day():
    assert fm.third_friday(2025, 12).isoformat() == "2025-12-19"
    assert fm.roll_day(2025, 12).isoformat() == "2025-12-15"


@pytest.mark.parametrize("day,expected", [
    ("2025-12-11", "MNQZ5"),   # Thu: brief's Thursday rule would say H6; real volume says Z5
    ("2025-12-12", "MNQZ5"),   # Fri before expiry week: still Dec
    ("2025-12-15", "MNQH6"),   # roll Monday (CME): Mar is front
    ("2025-12-18", "MNQH6"),
    ("2025-12-19", "MNQH6"),   # Dec expiry Friday
])
def test_roll_week(day, expected):
    assert fm.front_month("MNQ", day) == expected


def test_nq_root_and_year_wrap():
    assert fm.front_month("NQ", "2026-09-28") == "NQZ6"
    assert fm.front_month("NQ", "2026-12-17") == "NQH7"   # Dec 2026 roll = Mon 12-14
    assert fm.front_month("NQ", "2026-12-11") == "NQZ6"


def test_volume_crossover_fixture():
    # fixture (shape of the real Dec-2025 roll): NQZ5 out-trades NQH6 in RTH
    # on Fri 12-12 (a 03:00 ET overnight NQZ5 spike must be ignored), NQH6
    # out-trades NQZ5 on roll Monday 12-15.
    assert fm.volume_front("MNQ", "2025-12-12", FIX) == "NQZ5"
    assert fm.volume_front("MNQ", "2025-12-15", FIX) == "NQH6"
    assert fm.check("MNQ", "2025-12-12", FIX)["agree"] is True
    assert fm.check("MNQ", "2025-12-15", FIX)["agree"] is True
    assert fm.volume_front("MNQ", "2025-12-16", FIX) is None
    assert fm.check("MNQ", "2025-12-16", FIX)["agree"] is None
