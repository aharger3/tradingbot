"""s-matcher data loaders: stock/ETF 1-min days from data_archive, real NQ 1-min days from t01-orb5/fut.

RESERVED WINDOW GUARD: real NQ bars dated <= 2024-09-25 are the pre-registered B1 out-of-sample window (2019-09-26 ..
2024-09-25). build_nq_days() drops every session on or before B1_END (and the first session after it, whose prior day
would sit inside the window), so nothing here can be fit or tuned on it.
"""
import os
import numpy as np
import pandas as pd
from sm_features import day_from_rows, RTH0, RTH1

ROOT = r"C:\Users\aharg\Desktop\Projects\tradingbot"
ARCHIVE = os.path.join(ROOT, "data_archive")
FUT_DIR = os.path.join(ROOT, r"research\agent_runs\t01-orb5\fut")
B1_END = "2024-09-25"
NYSE_HOL = set("2024-11-28 2024-12-25 2025-01-01 2025-01-09 2025-01-20 2025-02-17 2025-04-18 2025-05-26 2025-06-19 "
               "2025-07-04 2025-09-01 2025-11-27 2025-12-25 2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 "
               "2026-06-19 2026-07-03 2026-09-07".split())


def stock_dates(sym):
    p = os.path.join(ARCHIVE, sym)
    return sorted(f[:10] for f in os.listdir(p) if f.endswith(".csv")) if os.path.isdir(p) else []


def load_stock_day(sym, day):
    p = os.path.join(ARCHIVE, sym, day + ".csv")
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, usecols=["Datetime", "Open", "High", "Low", "Close", "Volume"])
    if d.empty:
        return None
    s = d["Datetime"].astype(str)
    mins = s.str.slice(11, 13).astype(int) * 60 + s.str.slice(14, 16).astype(int)
    return day_from_rows(mins.to_numpy(), d["Open"], d["High"], d["Low"], d["Close"], d["Volume"])


def build_nq_days(raw=None, root="NQ"):
    """-> {date_str: (day, prev_day_same_contract_or_None)} for sessions strictly after B1_END+1 trading day.
    `raw` = DataFrame with ts_ns/open/high/low/close/volume/contract (as written by fetch_fut); loaded from disk if None."""
    if raw is None:
        parts = []
        for f in sorted(os.listdir(FUT_DIR)):
            if f.startswith(root) and f.endswith(".csv"):
                d = pd.read_csv(os.path.join(FUT_DIR, f))
                if d.empty:
                    continue
                d["contract"] = f.split("_")[0]
                parts.append(d)
        raw = pd.concat(parts, ignore_index=True)
    raw = raw.copy()
    ts = pd.to_datetime(raw["ts_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York")
    raw["date"] = ts.dt.strftime("%Y-%m-%d")
    raw["m"] = ts.dt.hour * 60 + ts.dt.minute
    raw = raw[~raw["date"].isin(NYSE_HOL)]
    raw = raw[raw["date"].map(lambda x: pd.Timestamp(x).weekday() < 5)]
    rth = raw[(raw["m"] >= RTH0) & (raw["m"] < RTH1)]
    vol = rth.groupby(["date", "contract"])["volume"].sum().reset_index()
    front = vol.loc[vol.groupby("date")["volume"].idxmax()].set_index("date")["contract"].to_dict()
    dates = sorted(front)
    arr = {}
    sub = raw[(raw["m"] >= 240) & (raw["m"] < RTH1)]
    for (dt, k), g in sub.groupby(["date", "contract"]):
        if front.get(dt) == k or front.get(prev_date(dates, dt)) == k:
            arr[(dt, k)] = day_from_rows(g["m"].to_numpy(), g["open"], g["high"], g["low"], g["close"], g["volume"])
    out = {}
    for i, dt in enumerate(dates):
        if dt <= B1_END or i == 0:
            continue
        pd_ = dates[i - 1]
        if pd_ <= B1_END:          # prior session lies in the reserved window: skip this session too
            continue
        k = front[dt]
        day = arr.get((dt, k))
        if day is None:
            continue
        out[dt] = (day, arr.get((pd_, k)))
    return out


def prev_date(dates, dt):
    i = dates.index(dt)
    return dates[i - 1] if i > 0 else None
