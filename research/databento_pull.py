"""research/databento_pull.py -- Databento cost guard.

Wraps every Databento historical pull so a cost estimate is checked BEFORE
any data is downloaded. Austin's credit is $125 total; this caps any single
pull at $25 (override via DATABENTO_MAX_USD env var) and refuses anything
over that instead of silently spending it.

Every attempt (allowed or refused) is logged to
`data_archive/databento/cost_log.csv`. DBN files are written only under
`data_archive/databento/`, which is already covered by the repo's
`data_archive/` gitignore entry.

Needs no Databento API key to import or test -- the `databento` package is
imported lazily inside `historical_client()` only, and all tests pass in a
mock client.

    python -m pytest -q test_databento_pull.py
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
DATA_ARCHIVE_DIR = ROOT / "data_archive" / "databento"
COST_LOG_PATH = DATA_ARCHIVE_DIR / "cost_log.csv"
COST_LOG_FIELDS = [
    "timestamp_utc",
    "dataset",
    "symbols",
    "schema",
    "start",
    "end",
    "cost_usd",
    "max_usd",
    "decision",
]

DEFAULT_MAX_USD = 25.0


def max_usd() -> float:
    """Cap for a single pull. Env override, else $25 of the $125 credit."""
    return float(os.environ.get("DATABENTO_MAX_USD", DEFAULT_MAX_USD))


class CostExceededError(RuntimeError):
    """Raised when a pull's estimated cost is over the allowed cap."""


def historical_client() -> Any:
    """Real Databento client. Imports databento lazily -- tests never hit this."""
    import databento  # noqa: PLC0415

    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise RuntimeError("DATABENTO_API_KEY not set")
    return databento.Historical(key)


def log_cost(
    dataset: str,
    symbols: Any,
    schema: str,
    start: str,
    end: str,
    cost_usd: float,
    decision: str,
    log_path: Path = COST_LOG_PATH,
) -> None:
    """Append one row to the cost log CSV, writing the header if new."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not log_path.exists()
    with open(log_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COST_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "dataset": dataset,
                "symbols": symbols,
                "schema": schema,
                "start": start,
                "end": end,
                "cost_usd": f"{cost_usd:.4f}",
                "max_usd": f"{max_usd():.4f}",
                "decision": decision,
            }
        )


@dataclass
class PullResult:
    path: Path
    cost_usd: float


def pull_historical(
    client: Any,
    dataset: str,
    symbols: Any,
    schema: str,
    start: str,
    end: str,
    out_dir: Path = DATA_ARCHIVE_DIR,
    cost_log_path: Path = COST_LOG_PATH,
    cap_usd: Optional[float] = None,
    **timeseries_kwargs: Any,
) -> PullResult:
    """Cost-check, then pull. Refuses and logs instead of downloading over cap.

    `client` is any object exposing `.metadata.get_cost(...)` and
    `.timeseries.get_range(...)` (the real `databento.Historical`, or a mock).
    """
    cap = cap_usd if cap_usd is not None else max_usd()

    cost = client.metadata.get_cost(
        dataset=dataset, symbols=symbols, schema=schema, start=start, end=end
    )
    cost = float(cost)

    if cost > cap:
        log_cost(dataset, symbols, schema, start, end, cost, "refused", cost_log_path)
        raise CostExceededError(
            f"Databento pull estimated at ${cost:.2f} exceeds cap ${cap:.2f} "
            f"(dataset={dataset}, schema={schema}, {start}..{end})"
        )

    log_cost(dataset, symbols, schema, start, end, cost, "allowed", cost_log_path)

    data = client.timeseries.get_range(
        dataset=dataset,
        symbols=symbols,
        schema=schema,
        start=start,
        end=end,
        **timeseries_kwargs,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"{dataset}_{schema}_{ts}.dbn"
    data.to_file(str(out_path))

    return PullResult(path=out_path, cost_usd=cost)
