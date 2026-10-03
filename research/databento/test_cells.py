"""pytest research/databento -q : cells.py == prereg-next-cells.md (no unregistered cell), window A guarded."""
import os, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent)); import cells

REC = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t01-orb5\fut"
PREREG = ["1 frozen MNQ mantra", "2P mantra + PDH/PDL within 1 ATR"]  # arm Z = oos_z.py, not here
IS = {PREREG[0]: (105, 0.309), PREREG[1]: (14, 1.197)}  # in-sample 2024-09..2026-09 (fit window, not A)


def test_cell_list_equals_prereg():
    assert list(cells.CELLS) == PREREG


def test_no_unregistered_machinery():
    for gone in ("NEWS", "NCELLS", "no_news", "news_covered", "zar_cell"): assert not hasattr(cells, gone)
    assert "p_bonf" not in cells.stats([dict(date="2025-01-01", R=1.0)], __import__("numpy").array([0.0]), ("a", "b", "2025-06-01"))


def test_unregistered_name_rejected():
    for bad in ("3 mantra, stop 0.5 ATR beyond level", "4 mantra, skip FOMC/CPI/NFP days", "5 Zarattini NQ925 flat 11:00"):
        with pytest.raises(KeyError): cells.run(bad, [], ("2025-01-01", "2025-02-01"))


def test_window_a_refused_without_lock():
    for w in (("2019-09-26", "2024-09-25"), ("2024-01-01", "2024-12-31"), ("2015-01-01", "2020-01-01")):
        with pytest.raises(PermissionError): cells.run(PREREG[0], [], w)
    assert not cells.touches_window_a(("2024-09-26", "2026-09-25"))


def test_gate_no_bonferroni():
    s = dict(n=40, R=0.2, h1=0.1, h2=0.3, p=0.04)
    assert cells.gate(s) == "SHIP-ELIGIBLE" and cells.gate({**s, "n": 29}) == "NO-SHIP" and cells.gate({**s, "p": 0.06}) == "NO-SHIP"


@pytest.fixture(scope="module")
def days():
    if not os.path.isdir(REC): pytest.skip("recovered NQ bars not on this box")
    return cells._mnq().load_real()


@pytest.mark.parametrize("name", PREREG)
def test_cell_reproduces_is(days, name):
    T, s = cells.run(name, days, (days[0]["date"], days[-1]["date"]), nshuf=0)
    assert (s["n"], round(s["R"], 3)) == IS[name]
