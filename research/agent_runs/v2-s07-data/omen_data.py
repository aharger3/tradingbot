"""OMEN v2 shared 1-min loader (s07). Read-only over files already on disk; no network, no keys.

Usage (from any agent_runs script):
    import sys; sys.path.insert(0, r"C:\\Users\\aharg\\Desktop\\Projects\\tradingbot\\research\\agent_runs\\v2-s07-data")
    from omen_data import load_fut, load_proxy, sessions, SPEC
    df = load_fut("MES")                      # real ES 1-min, front month per session, RTH 09:30-15:59 ET
    df = load_fut("MNQ", start="09:30", end="11:00")
    px = load_proxy("MES")                    # SPY 1-min scaled to ES points (older / cross-check only)

Columns: ts (tz-aware America/New_York, bar OPEN time), date, open, high, low, close, volume, contract.
MES/ES share ES bars (same index, micro tracks the e-mini within a tick at RTH); MNQ/NQ share NQ bars.
Only the dollar spec differs -> use SPEC[sym].
"""
from pathlib import Path
import pandas as pd

RUNS = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
FUT_DIR = RUNS / "t01-orb5" / "fut"          # {ROOT}{M}{Y}_{YYYY}.csv, ts_ns UTC, from Massive futures/v1/aggs
ARCHIVE = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\data_archive")
ET = "America/New_York"

# $/point, tick size, round-trip commission (approx retail/prop, per contract)
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
    d = pd.concat(parts, ignore_index=True)
    d["ts"] = pd.to_datetime(d["ts_ns"], unit="ns", utc=True).dt.tz_convert(ET)
    d = d.drop(columns="ts_ns")
    d["date"] = d["ts"].dt.date
    _cache[root] = d
    return d


def load_fut(sym="MES", start="09:30", end="16:00", drop_nyse_closed=True):
    """Real CME 1-min bars, one contract per session (the one with most RTH volume = front month).
    start/end are ET wall-clock, end exclusive (bar OPEN time < end). Missing minutes are NOT filled.
    drop_nyse_closed: drop CME-only sessions (NYSE holiday, CME open to 13:00 ET = <=212 RTH bars)."""
    root = SPEC[sym]["root"]
    d = _raw(root)
    t = d["ts"].dt.strftime("%H:%M")
    rth = d[(t >= "09:30") & (t < "16:00")]
    vol = rth.groupby(["date", "contract"])["volume"].sum().reset_index()
    pick = vol.loc[vol.groupby("date")["volume"].idxmax(), ["date", "contract"]]
    if drop_nyse_closed:
        cnt = rth.merge(pick, on=["date", "contract"]).groupby("date").size()
        pick = pick[pick["date"].map(cnt) > 212]
    out = d.merge(pick, on=["date", "contract"])
    t = out["ts"].dt.strftime("%H:%M")
    out = out[(t >= start) & (t < end)].sort_values("ts").reset_index(drop=True)
    return out[["ts", "date", "open", "high", "low", "close", "volume", "contract"]]


def load_proxy(sym="MES", start="09:30", end="16:00", ratio=None):
    """SPY/QQQ 1-min from data_archive scaled to futures points. ratio=None -> per-day ratio fitted on the
    real futures 09:30 open where both exist, else fixed 10.16 (SPY) / 41.35 (QQQ, unfitted)."""
    etf = SPEC[sym]["proxy"]
    parts = []
    for f in sorted((ARCHIVE / etf).glob("*.csv")):
        d = pd.read_csv(f)
        if not d.empty:
            parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    d["ts"] = pd.to_datetime(d["Datetime"], utc=True, format="ISO8601").dt.tz_convert(ET)
    d["date"] = d["ts"].dt.date
    t = d["ts"].dt.strftime("%H:%M")
    d = d[(t >= start) & (t < end)].copy()
    if ratio is None:
        r = pd.Series(10.16 if etf == "SPY" else 41.35, index=d["date"].unique())
        try:
            f = load_fut(sym, "09:30", "09:31").set_index("date")["open"]
            e = d[d["ts"].dt.strftime("%H:%M") == "09:30"].set_index("date")["Open"]
            fit = (f / e).dropna()
            r.loc[fit.index.intersection(r.index)] = fit
        except Exception:
            pass
        k = d["date"].map(r)
    else:
        k = ratio
    for c in ("Open", "High", "Low", "Close"):
        d[c.lower()] = d[c] * k
    d["volume"] = d["Volume"]
    d["contract"] = etf + "_proxy"
    return d[["ts", "date", "open", "high", "low", "close", "volume", "contract"]].reset_index(drop=True)


def sessions(df):
    """Dict date -> that session's bars (in the loaded window)."""
    return {k: g.reset_index(drop=True) for k, g in df.groupby("date")}


def snap(px, sym="MES"):
    tk = SPEC[sym]["tick"]
    return round(px / tk) * tk


if __name__ == "__main__":
    for s in ("MES", "MNQ"):
        df = load_fut(s)
        n = df.groupby("date").size()
        w = load_fut(s, "09:30", "11:00").groupby("date").size()
        print(s, "sessions", len(n), df["date"].min(), df["date"].max(),
              "rows", len(df), "RTH<380", int((n < 380).sum()), "0930-1100 full(90)", int((w == 90).sum()),
              "<85", int((w < 85).sum()), "contracts", df["contract"].nunique())
        p = load_proxy(s)
        print(s, "proxy sessions", p["date"].nunique(), p["date"].min(), p["date"].max())
