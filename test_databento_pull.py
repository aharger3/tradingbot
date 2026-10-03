"""test_databento_pull.py -- the Databento cost guard refuses before it spends.

Proves: a $30 cost estimate is refused (no download, logged as "refused");
a $5 estimate proceeds, writes a DBN file under data_archive/databento/, and
is logged as "allowed". Client is fully mocked -- no API key, no network.

    python -m pytest -q test_databento_pull.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.databento_pull import CostExceededError, pull_historical  # noqa: E402


def _make_client(cost: float) -> MagicMock:
    client = MagicMock()
    client.metadata.get_cost.return_value = cost
    store = MagicMock()
    client.timeseries.get_range.return_value = store
    return client


def test_refuses_over_cap(tmp_path: Path) -> None:
    client = _make_client(30.0)
    out_dir = tmp_path / "data_archive" / "databento"
    log_path = out_dir / "cost_log.csv"

    try:
        pull_historical(
            client,
            dataset="GLBX.MDP3",
            symbols=["ES.FUT"],
            schema="ohlcv-1m",
            start="2026-09-01",
            end="2026-09-02",
            out_dir=out_dir,
            cost_log_path=log_path,
            cap_usd=25.0,
        )
        raised = False
    except CostExceededError:
        raised = True

    assert raised, "a $30 estimate over a $25 cap must be refused"
    client.timeseries.get_range.assert_not_called()

    rows = list(csv.DictReader(open(log_path)))
    assert len(rows) == 1
    assert rows[0]["decision"] == "refused"
    assert float(rows[0]["cost_usd"]) == 30.0


def test_allows_under_cap_and_logs(tmp_path: Path) -> None:
    client = _make_client(5.0)
    out_dir = tmp_path / "data_archive" / "databento"
    log_path = out_dir / "cost_log.csv"

    result = pull_historical(
        client,
        dataset="GLBX.MDP3",
        symbols=["ES.FUT"],
        schema="ohlcv-1m",
        start="2026-09-01",
        end="2026-09-02",
        out_dir=out_dir,
        cost_log_path=log_path,
        cap_usd=25.0,
    )

    assert result.cost_usd == 5.0
    assert result.path.parent == out_dir
    client.timeseries.get_range.assert_called_once()
    store = client.timeseries.get_range.return_value
    store.to_file.assert_called_once_with(str(result.path))

    rows = list(csv.DictReader(open(log_path)))
    assert len(rows) == 1
    assert rows[0]["decision"] == "allowed"
    assert float(rows[0]["cost_usd"]) == 5.0


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        test_refuses_over_cap(Path(d) / "a")
    with tempfile.TemporaryDirectory() as d:
        test_allows_under_cap_and_logs(Path(d) / "b")
    print("OK: refused $30, allowed+logged $5")
