"""Standalone analysis (not an engine change): counts how often the setup
candle's close breaks session_hi/session_lo under HODLOD_DEF's two
definitions, mirroring signal_runner.detect_signals's exact computation.
Read-only against the archive; does not call detect_signals or write a book.
"""
import sys, pathlib, os, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
os.environ["ARCHIVE_READONLY"] = "1"

import polygon_feed as pf
from signal_runner import in_session

SYMS = ["TSLA", "NVDA", "AAPL", "AMD", "META", "GOOGL", "AMZN", "MSFT", "PLTR", "QQQ", "SPY"]
DAYS = []
d = datetime.date(2024, 9, 4)
end = datetime.date(2026, 9, 4)
while d <= end:
    if d.weekday() < 5:
        DAYS.append(d.isoformat())
    d += datetime.timedelta(days=1)
DAYS = DAYS[::10]  # sample every 10th trading day for speed

off_break, on_break, total_bars = 0, 0, 0
for sym in SYMS:
    for day in DAYS:
        try:
            candles = pf.fetch_day(sym, day)
        except Exception:
            continue
        if not candles:
            continue
        session = [c for c in candles if in_session(c.timestamp)]
        for i in range(4, len(session)):
            window = session[:i + 1]  # candles up to and including current, as detect_signals sees it
            current = window[-1]
            hod_off = max(c.high for c in window)
            lod_off = min(c.low for c in window)
            if len(window) >= 2:
                hod_on = max(c.high for c in window[:-1])
                lod_on = min(c.low for c in window[:-1])
            else:
                hod_on, lod_on = hod_off, lod_off
            total_bars += 1
            if current.close > hod_off or current.close < lod_off:
                off_break += 1
            if current.close > hod_on or current.close < lod_on:
                on_break += 1

print("symbols:", len(SYMS), "sampled days/symbol:", len(DAYS), "total in-session bars checked:", total_bars)
print("OFF (inclusive, current behaviour) break count:", off_break)
print("ON (prior_bar) break count:", on_break)
