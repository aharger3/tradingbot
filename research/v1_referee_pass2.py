"""research/v1_referee_pass2.py -- V1 referee, pass 2.

Pass 1 (`research/v1_referee.py`, commit c7d52853) upheld the row and found one
reporting defect (the builder named the wrong commit). This pass re-checks the
one thing pass 1 explicitly did not: whether the numbers the 09:25 push carries
are actually TODAY's premarket.

They are not, and the failure is silent.

`research/premarket_list.py::_yf_batch_premarket_today` calls

    yf.download(symbols, period="1d", interval="1m", prepost=True, ...)

and then selects premarket bars with

    pm = df[df.index.time < dt.time(9, 30)]

That filter is on the CLOCK ONLY. There is no date filter anywhere in the
function, and `period="1d"` returns the most recent session that HAS data --
not today. So whenever today has no bars yet (a market holiday, a weekend run,
or yfinance simply not having populated the current session at 09:25), the
prior session's premarket high/low are returned, and `format_message` prints
them under the title "OMEN premarket <today>" with no marker. The row's only
"n/a" path is `value is None`, which this never produces.

Checks below are offline and deterministic (synthetic frames), plus two
observed facts recorded from the live dry-run on 2026-09-06.

    python research/v1_referee_pass2.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ET = ZoneInfo("America/New_York")

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))


# ---------------------------------------------------------------- check 1
# The premarket selector has no date filter: prove it by feeding a frame that
# contains ONLY the prior session and asking for "today's" premarket.
def _stale_frame(session_day: dt.date) -> pd.DataFrame:
    idx = [dt.datetime.combine(session_day, dt.time(h, m), tzinfo=ET)
           for h in (4, 5, 6, 7, 8, 9) for m in (0, 30)]
    idx = [t for t in idx if t.time() < dt.time(9, 30)]
    n = len(idx)
    return pd.DataFrame(
        {"Open": [100.0] * n, "High": [110.0 + i for i in range(n)],
         "Low": [90.0 - i for i in range(n)], "Close": [100.0] * n,
         "Volume": [1000] * n},
        index=pd.DatetimeIndex(idx, name="Datetime"),
    )


def _replay_selector(df: pd.DataFrame):
    """Byte-for-byte the selection premarket_list._yf_batch_premarket_today
    performs after the download (lines ~127-137 of that file)."""
    df = df.dropna(how="all")
    if df.empty:
        return None, None
    if df.index.tz is None:
        df = df.tz_localize("UTC")
    df = df.tz_convert(ET)
    pm = df[df.index.time < dt.time(9, 30)]
    if pm.empty:
        return None, None
    return float(pm["High"].max()), float(pm["Low"].min())


today = dt.date(2026, 9, 7)                  # Labor Day 2026, markets closed
stale_day = dt.date(2026, 9, 4)              # the Friday before
pmh, pml = _replay_selector(_stale_frame(stale_day))
check(
    "premarket selector rejects a frame that holds no bars from today",
    pmh is None and pml is None,
    f"asked for {today}, frame holds only {stale_day}; selector returned "
    f"PMH={pmh} PML={pml} (expected None/None -> the message would print 'n/a')",
)

# ---------------------------------------------------------------- check 2
# Source-level: the function body contains no comparison against today's date.
src = (ROOT / "research" / "premarket_list.py").read_text(encoding="utf-8")
start = src.index("def _yf_batch_premarket_today")
end = src.index("def _yf_batch_prevday")
body = src[start:end]
# strip the def line, the docstring and every comment: only executable code counts.
_code = body.split('"""')[2] if body.count('"""') >= 2 else body
_code = "\n".join(ln for ln in _code.splitlines() if not ln.strip().startswith("#"))
has_date_guard = any(tok in _code for tok in (".date()", "day_iso", "today_iso",
                                              "index.date", "today ="))
check(
    "_yf_batch_premarket_today filters its bars by date, not only by clock",
    has_date_guard,
    "the function body contains no date comparison at all: its only filter is "
    "`df.index.time < dt.time(9, 30)`",
)

# ---------------------------------------------------------------- check 3
# The formatter has no way to say 'stale' -- n/a is reachable only via None.
fmt_src = src[src.index("def format_message"):src.index("def main")]
check(
    "format_message can mark a level as stale/unavailable for a reason other "
    "than a missing value",
    ("stale" in fmt_src or "date" in fmt_src),
    "format_message's only fallback is `'n/a' if x is None`; a stale-but-present "
    "number is printed as if it were today's",
)

# ---------------------------------------------------------------- check 4
# fetch_levels never validates that the yfinance leg returned today's session.
fl = src[src.index("def fetch_levels"):src.index("def format_message")]
check(
    "fetch_levels validates the yfinance premarket leg against today's date",
    "yf_pm.get" in fl and any(
        tok in fl.split("yf_pm.get")[1][:400]
        for tok in (".date()", "today_iso", "stale", "index.date")),
    "fetch_levels assigns `levels[s]['pmh'], levels[s]['pml'] = yf_pm.get(s, ...)` "
    "with no date check on what came back",
)

# ---------------------------------------------------------------- observed
OBSERVED = [
    ("live dry-run 2026-09-06 printed title 'OMEN premarket 2026-09-06'", True),
    ("the TSLA PMH/PML it printed (376.37 / 361.65) are 2026-09-04 bars "
     "(yf.download(period='1d') returned 2026-09-04 04:00 -> 19:59 ET, 330 "
     "premarket rows, all dated 2026-09-04)", True),
    ("scheduled task OmenPremarketList Next Run Time = 2026-09-07 09:25, "
     "which is Labor Day (first Monday of September 2026) -- US markets closed", True),
]

print("V1 referee pass 2 -- the premarket leg has no date guard\n")
fails = 0
for name, ok, detail in RESULTS:
    tag = "PASS" if ok else "FAIL"
    if not ok:
        fails += 1
    print(f"[{tag}] {name}")
    if detail:
        print(f"       {detail}")
print("\nobserved (from the live dry-run and schtasks, this box, 2026-09-06):")
for text, _ in OBSERVED:
    print(f"  - {text}")
print(f"\n{len(RESULTS) - fails}/{len(RESULTS)} checks pass, {fails} fail.")
print("verdict: refuted" if fails else "verdict: upheld")
sys.exit(0)
