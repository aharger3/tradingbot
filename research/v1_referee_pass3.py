"""research/v1_referee_pass3.py -- V1 referee, pass 3 (2026-09-06).

Refereeing builder commit c84d0bd3 ("V1 repair: date-scope yfinance premarket
fallback"), which answered pass 2's refutation.

Nothing here is read out of the builder's report. Every claim is re-derived:

  1. The date mask actually excludes a prior session's premarket bars
     (the pass-2 defect is gone).
  2. The date mask does NOT kill the live path: with `today` set to the
     frame's own most recent session, the same function still returns a
     real PMH/PML. A fix that made the feature return n/a on EVERY day
     would also produce the Sunday n/a the builder verified, so this is
     the check that separates "fixed" from "disabled".
  3. The pre-fix code, run on the same frame, would have published that
     prior session's range under today's date -- i.e. pass 2's defect was
     real, and this is the number it would have printed.
  4. The sibling leg `_yf_batch_prevday` is inspected for the same defect
     class (a fallback row with no date scoping).

Run:  python research/v1_referee_pass3.py
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
for p in (str(ROOT), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import premarket_list as pl   # noqa: E402

ET = ZoneInfo("America/New_York")
SYMS = ["TSLA", "NVDA", "SPY"]


def pull():
    import yfinance as yf
    import pandas as pd
    data = yf.download(SYMS, period="1d", interval="1m", prepost=True,
                       group_by="ticker", threads=False, progress=False)
    multi = isinstance(data.columns, pd.MultiIndex)
    frames = {}
    for s in SYMS:
        df = data[s] if multi else data
        df = df.dropna(how="all")
        if df.index.tz is None:
            df = df.tz_localize("UTC")
        frames[s] = df.tz_convert(ET)
    return frames


def prefix_behaviour(df):
    """The mask exactly as it stood BEFORE c84d0bd3: clock only, no date."""
    pm = df[df.index.time < dt.time(9, 30)]
    if pm.empty:
        return (None, None)
    return (float(pm["High"].max()), float(pm["Low"].min()))


def main():
    today = dt.datetime.now(ET).date()
    print(f"referee pass 3 -- today (ET) = {today}  weekday={today.strftime('%a')}")

    frames = pull()
    for s, df in frames.items():
        dates = sorted({d for d in df.index.date})
        pm_dates = sorted({d for d in df[df.index.time < dt.time(9, 30)].index.date})
        print(f"\n[{s}] frame rows={len(df)} sessions={dates} premarket sessions={pm_dates}")

        # 1. fixed function, real today
        got = pl._yf_batch_premarket_today([s], today)[s]
        print(f"  fixed(today={today})            -> {got}")

        # 2. fixed function, the frame's own most recent session
        if pm_dates:
            asof = pm_dates[-1]
            got2 = pl._yf_batch_premarket_today([s], asof)[s]
            print(f"  fixed(today={asof})            -> {got2}   "
                  f"{'LIVE PATH OK' if got2[0] is not None else 'LIVE PATH DEAD'}")
        else:
            print("  no premarket bars in frame at all -- cannot test live path")

        # 3. what the pre-fix code would have published under today's title
        print(f"  pre-fix (clock only)            -> {prefix_behaviour(df)}")

    # 4. sibling leg: does _yf_batch_prevday date-scope its fallback?
    src = (HERE / "premarket_list.py").read_text(encoding="utf-8")
    body = src.split("def _yf_batch_prevday")[1].split("\ndef ")[0]
    print("\n[_yf_batch_prevday] fallback line(s):")
    for line in body.splitlines():
        if "iloc[-1]" in line or "prev_iso" in line:
            print("   " + line.strip())


if __name__ == "__main__":
    main()
