"""front_month.py -- which quarterly contract is "the" MNQ/NQ contract on a date.

Calendar rule (CME equity index quarterly cycle):
  * listed months H (Mar), M (Jun), U (Sep), Z (Dec)
  * last trading day = third Friday of the contract month
    (CME Micro/E-mini Nasdaq-100 contract specs; expiration calendar
    https://www.cmegroup.com/tools-information/calendars/expiration-calendar.html)
  * ROLL DAY = the Monday before the third-Friday expiry (4 calendar days
    prior); on and after the roll day the NEXT quarterly is the front month.
    Source: CME "Equity Index Roll Dates" --
    https://www.cmegroup.com/trading/equity-index/rolldates.html -- "the Monday
    prior to the third Friday of the expiration month" (read via CME search
    result; the page itself timed out from this box 2026-09-27 -> [A]).
    The task brief's "Thursday 8 days before expiry" convention is REFUTED by
    our own bars: real NQ RTH volume stayed on the old contract Thu 2025-12-11,
    Fri 12-12, Thu 2026-09-10, Fri 09-11 and crossed on Mon 2025-12-15 and
    Mon 2026-09-14 -- matching the Monday rule on all 11 dates probed.

Volume cross-check: when per-contract 1-min CSVs exist
({ROOT}{M}{Y}_{YYYY}.csv, ts_ns UTC, under research/agent_runs/t01-orb5/fut --
the same files omen_data.load_fut reads), volume_front() returns the contract
with the most RTH (09:30-16:00 ET) volume that session, same rule as load_fut.

Paper-only research helper. No network, no orders.
"""
from __future__ import annotations

import csv
from datetime import date as Date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
QUARTERLY = {3: "H", 6: "M", 9: "U", 12: "Z"}
DATA_ROOT = {"MNQ": "NQ", "NQ": "NQ", "MES": "ES", "ES": "ES"}  # micros trade the same months as the minis
DEFAULT_FUT_DIR = Path(__file__).resolve().parent / "agent_runs" / "t01-orb5" / "fut"


def _as_date(d) -> Date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, Date):
        return d
    return Date.fromisoformat(str(d)[:10])


def third_friday(year: int, month: int) -> Date:
    first = Date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 14)


ROLL_DAYS_BEFORE_EXPIRY = 4  # Monday of expiry week (CME); see module docstring


def roll_day(year: int, month: int) -> Date:
    """Monday before the third-Friday expiry (CME equity index roll date)."""
    return third_friday(year, month) - timedelta(days=ROLL_DAYS_BEFORE_EXPIRY)


def contract_code(root: str, year: int, month: int) -> str:
    return f"{root}{QUARTERLY[month]}{year % 10}"


def front_month(root: str, date) -> str:
    """e.g. front_month('MNQ', '2025-12-15') -> 'MNQH6' (roll day switches)."""
    d = _as_date(date)
    y = d.year
    for m in (3, 6, 9, 12):
        if d < roll_day(y, m):
            return contract_code(root, y, m)
    return contract_code(root, y + 1, 3)


def volume_front(root: str, date, fut_dir: Path | str | None = None) -> str | None:
    """Contract (data symbol, e.g. 'NQH6') with the most RTH volume on `date`,
    or None when no per-contract bars cover that session."""
    d = _as_date(date)
    fut_dir = Path(fut_dir) if fut_dir else DEFAULT_FUT_DIR
    data_root = DATA_ROOT.get(root, root)
    if not fut_dir.is_dir():
        return None
    vols: dict[str, int] = {}
    for f in sorted(fut_dir.glob(f"{data_root}*_*.csv")):
        sym = f.stem.split("_")[0]
        if sym[:-2] != data_root:  # NQ must not match e.g. NQX*
            continue
        total = 0
        with open(f, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                ts = datetime.fromtimestamp(int(row["ts_ns"]) / 1e9, tz=timezone.utc).astimezone(ET)
                if ts.date() == d and "09:30" <= ts.strftime("%H:%M") < "16:00":
                    total += int(float(row["volume"]))
        if total:
            vols[sym] = total
    if not vols:
        return None
    return max(vols, key=vols.get)


def to_root(contract: str, root: str) -> str:
    """'NQH6' -> 'MNQH6' for root MNQ (swap the data root for the traded root)."""
    return f"{root}{contract[-2:]}"


def check(root: str, date, fut_dir: Path | str | None = None) -> dict:
    """Calendar vs volume. agree is None when there are no bars for the date."""
    cal = front_month(root, date)
    vol = volume_front(root, date, fut_dir)
    vol_root = to_root(vol, root) if vol else None
    return {"date": str(_as_date(date)), "calendar": cal, "volume": vol_root,
            "agree": None if vol_root is None else vol_root == cal}


if __name__ == "__main__":
    import sys
    r = sys.argv[1] if len(sys.argv) > 1 else "MNQ"
    for ds in sys.argv[2:] or [str(datetime.now(ET).date())]:
        print(check(r, ds))
