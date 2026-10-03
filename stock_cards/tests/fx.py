"""Fixture loader: PLTR and QQQ on 2026-08-04 (archive bars), their prior-day context, and the tape's PLTR rows."""
import json
from pathlib import Path

import polygon_feed as pf

from stock_cards.context import Context

HERE = Path(__file__).parent / "fixtures"
DAY = "2026-08-04"


def bars(sym):
    return pf._read_csv(HERE / f"{sym}_{DAY}.csv")


def ctx(sym):
    j = json.loads((HERE / "context.json").read_text())[sym]
    return Context(pdh=j["pdh"], pdl=j["pdl"], pdo=j["pdo"], pdc=j["pdc"], bias=j["bias"], prev_day=j["prev_day"])


def expected():
    return json.loads((HERE / "expected.json").read_text())


def upto(candles, hhmm):
    """Bars whose START is before hhmm (what is known once the bar before hhmm has closed)."""
    return [c for c in candles if c.timestamp < hhmm + ":00"]
