"""pytest research/databento -q  (no key, no databento package needed)."""
import glob, os, sys, json
from pathlib import Path
import numpy as np, pandas as pd, pytest

HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import pull, oos_db

REC = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t01-orb5\fut"


def test_jobs_cover_window_and_priority():
    J = pull.jobs()
    assert J[0]["name"] == "NQ_2019" and J[0]["start"] == "2019-01-01"
    assert all(j["end"] <= "2024-09-26" for j in J)
    assert [s for s, _ in J[0]["contracts"]] == ["NQH9", "NQM9", "NQU9", "NQZ9", "NQH0"]
    assert dict(J[0]["contracts"])["NQH0"] == "NQH20"
    assert {j["root"] for j in J} == {"NQ", "ES", "MNQ", "MES"} and len(J) == 6 + 6 + 9 + 9 + 6 + 6
    assert next(j for j in J if j["name"] == "NQ_2010")["start"] == "2010-06-06"


def test_frozen_engine_untouched():
    oos_db.assert_frozen()


def test_holidays_are_weekdays_and_unique_to_gap():
    d = pd.to_datetime(sorted(oos_db.HOL_EXTRA))
    assert (d.dayofweek < 5).all() and len(d) == len(oos_db.HOL_EXTRA)


def test_gate():
    ok = dict(n=100, R=0.2, h1=0.1, h2=0.3, p=0.01)
    assert oos_db.gate(ok).startswith("SHIP")
    for bad in (dict(ok, R=0.14), dict(ok, h1=-0.01), dict(ok, p=0.05), dict(ok, n=10)):
        assert oos_db.gate(bad) == "NO-SHIP"


def _as_databento(files):
    """Recovered t01 CSVs re-shaped exactly like databento DBNStore.to_df() (UTC ts_event index, symbol column)."""
    sets = []
    for f in files:
        d = pd.read_csv(f)
        if d.empty: continue
        sym = Path(f).stem.split("_")[0]                      # NQZ4
        key = sym[:-1] + Path(f).stem.split("_")[1][2:]        # NQZ24
        idx = pd.DatetimeIndex(pd.to_datetime(d.ts_ns, unit="ns", utc=True), name="ts_event")
        df = pd.DataFrame(dict(rtype=33, publisher_id=1, instrument_id=1, open=d.open.values, high=d.high.values,
                               low=d.low.values, close=d.close.values, volume=d.volume.values, symbol=sym), index=idx)
        sets.append(pull.to_rows(df, {sym: key}))
    return sets


@pytest.mark.skipif(not os.path.isdir(REC), reason="recovered NQ bars not on this box")
def test_databento_path_reproduces_is_cell(tmp_path, monkeypatch):
    """End-to-end: recovered bars -> Databento-shaped df -> pull.write -> oos_db (frozen mnq) == v3-t-mnq IS cell."""
    counts = pull.write(_as_databento(sorted(glob.glob(REC + r"\NQ*.csv"))), tmp_path)
    assert sum(counts.values()) > 390_000
    monkeypatch.setitem(oos_db.WINDOWS, "IS", ("2024-09-26", "2026-09-25"))
    monkeypatch.setenv("OOS_OUT", str(tmp_path))
    out = oos_db.main("IS", nshuf=0, db_root=str(tmp_path))
    assert out["n"] == 105 and round(out["R"], 3) == 0.309
    assert round(out["h1"], 3) == 0.382 and round(out["h2"], 3) == 0.226
