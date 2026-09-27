"""OMEN v2 shared 1-min loader (s07). Read-only over files already on disk; no network, no keys.

RESTORED 2026-09-26 (v2-paper-harness build): the original file described in
s07-data-1min.md was missing from research/agent_runs/v2-s07-data/ (only its
__pycache__ survived) when this ticket started -- likely lost because that
directory was never committed (git status showed it untracked, then absent).
Reconstructed from the s07 doc's documented behavior and self-test numbers.
Rebuilding this is in scope for this Build ticket: the paper-harness (and the
frozen v2-t01/t02 engines it drives) cannot run without it, and nothing outside
research/agent_runs is touched.

Usage (from any agent_runs script):
    import sys; sys.path.insert(0, r"C:\\Users\\aharg\\Desktop\\Projects\\tradingbot\\research\\agent_runs\\v2-s07-data")
    from omen_data import load_fut, SPEC
    df = load_fut("MES")                      # real ES 1-min, front month per session, RTH 09:30-15:59 ET
    df = load_fut("MNQ", start="09:30", end="11:00")

Columns: ts (tz-aware America/New_York, bar OPEN time), date, open, high, low, close, volume, contract.
MES/ES share ES bars, MNQ/NQ share NQ bars (same index; only the $ spec differs) -> use SPEC[sym].
"""
from pathlib import Path
import pandas as pd

RUNS = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
FUT_DIR = RUNS / "t01-orb5" / "fut"          # {ROOT}{M}{Y}_{YYYY}.csv, ts_ns UTC, from Massive futures/v1/aggs
ET = "America/New_York"

# NYSE holidays where CME trades but NYSE is closed (drop_nyse_closed=True skips these sessions).
_NYSE_HOLIDAYS = {
    "2024-11-28", "2024-12-25", "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17",
    "2025-04-18", "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27",
    "2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07",
}

SPEC = {
    "MES": dict(root="ES", usd_pt=5.0,  tick=0.25, rt_comm=1.24, proxy="SPY"),
    "ES":  dict(root="ES", usd_pt=50.0, tick=0.25, rt_comm=4.50, proxy="SPY"),
    "MNQ": dict(root="NQ", usd_pt=2.0,  tick=0.25, rt_comm=1.24, proxy="QQQ"),
    "NQ":  dict(root="NQ", usd_pt=20.0, tick=0.25, rt_comm=4.50, proxy="QQQ"),
}

_cache = {}


def _raw(root):
    if root in _cache:
        return _cache[root]
    parts = []
    for f in sorted(FUT_DIR.glob(f"{root}*_*.csv")):
        d = pd.read_csv(f)
        if d.empty:
            continue
        d["contract"] = f.stem.split("_")[0]
        parts.append(d)
    if not parts:
        raise FileNotFoundError(f"no {root}*_*.csv under {FUT_DIR}")
    d = pd.concat(parts, ignore_index=True)
    d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert(ET)
    d = d.drop(columns="ts_ns")
    d["date"] = d["ts"].dt.date
    d = d.sort_values("ts").reset_index(drop=True)
    _cache[root] = d
    return d


def load_fut(sym="MES", start="09:30", end="16:00", drop_nyse_closed=True):
    """Real CME 1-min bars, one contract per session (front month = most RTH volume).
    start/end are ET wall-clock, end exclusive (bar OPEN time < end). Missing minutes are NOT filled."""
    root = SPEC[sym]["root"]
    d = _raw(root)
    t = d["ts"].dt.strftime("%H:%M")
    win = d[(t >= start) & (t < end)].copy()
    if drop_nyse_closed:
        win = win[~win["date"].astype(str).isin(_NYSE_HOLIDAYS)]
    # front month = contract with the most RTH (09:30-16:00) volume that session
    rth = d[(d["ts"].dt.strftime("%H:%M") >= "09:30") & (d["ts"].dt.strftime("%H:%M") < "16:00")]
    vol_by = rth.groupby(["date", "contract"])["volume"].sum().reset_index()
    front = vol_by.loc[vol_by.groupby("date")["volume"].idxmax(), ["date", "contract"]]
    front_map = dict(zip(front["date"], front["contract"]))
    win = win[win.apply(lambda r: front_map.get(r["date"]) == r["contract"], axis=1)]
    return win.reset_index(drop=True)


def sessions(sym="MES"):
    df = load_fut(sym)
    return sorted(set(df["date"]))


def snap(px, tick=0.25):
    return round(round(px / tick) * tick, 10)


if __name__ == "__main__":
    for sym in ("MES", "MNQ"):
        df = load_fut(sym, "09:30", "11:01")
        days = df["date"].nunique()
        print(sym, "sessions", days, "rows", len(df), "contracts", df["contract"].nunique(),
              "first", df["date"].min(), "last", df["date"].max())
    print("SELF-TEST OK")
