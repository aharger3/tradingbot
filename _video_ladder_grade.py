"""
_video_ladder_grade.py - run T3's price_in_range grader over the T6 video rungs.

Converts the T6 video verdict from *yield* (did a stop come back) into *accuracy*
(was the price actually on the chart). Same rule as _vision_ladder_grade.py: a price
is in range when it falls within [low*0.98, high*1.02] of the day's 1-min session
bars for that ticker. Ground truth day = the video's upload_date from yt_worklist.jsonl
(a same-day recap; videos whose charts are historical will simply fail to grade and
are excluded, never penalized).

A SETUP is the unit here (not a row): T6 rows carry many setups each. A setup is
in-range only if EVERY non-null price it returns (entry, stop, target, key_levels)
is in range. Setups with no gradeable day range are excluded.

No model calls. Reads only files already on disk.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
RESEARCH = ROOT / "research"
ARCHIVE = ROOT / "data_archive"
WORKLIST = RESEARCH / "yt_worklist.jsonl"

RUNGS = [
    ("qwen", "qwen/qwen3.7-flash"),
    ("batch", "google/gemini-3.5-flash-lite"),
    ("flash", "gemini-3.6-flash"),
]
PRICE_FIELDS = ["entry", "stop", "target"]
NUMERIC = re.compile(r"^\s*\$?\d{1,7}(?:[.,]\d+)?\s*$")

TICKERS = sorted(d.name for d in ARCHIVE.iterdir() if d.is_dir())
ALIAS = {"ES1!": "SPY", "NQ1!": "QQQ", "ES": "SPY", "NQ": "QQQ",
         "SPX": "SPY", "NDX": "QQQ", "RTY1!": "IWM", "GOOGL": "GOOGL"}


def to_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not NUMERIC.match(s):
        return None
    return float(s.replace("$", "").replace(",", ""))


_cache = {}


def day_range(ticker, date):
    if not ticker or not date:
        return None
    key = (ticker, date)
    if key in _cache:
        return _cache[key]
    f = ARCHIVE / ticker / ("%s.csv" % date)
    if not f.exists():
        _cache[key] = None
        return None
    lows, highs = [], []
    with open(f, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                lows.append(float(row["Low"]))
                highs.append(float(row["High"]))
            except (ValueError, KeyError):
                continue
    rng = (min(lows), max(highs)) if lows else None
    _cache[key] = rng
    return rng


def resolve(t):
    if not t:
        return None
    t = str(t).strip().upper()
    t = ALIAS.get(t, t)
    return t if t in TICKERS else None


def main():
    upload = {}
    for line in WORKLIST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            upload[r["video_id"]] = r.get("upload_date")

    results = []
    for rung, model in RUNGS:
        f = RESEARCH / ("video_ladder_results_%s.jsonl" % rung)
        if not f.exists():
            continue
        n_setups = n_gradeable = n_in = 0
        n_prices = n_prices_in = 0
        no_ticker = no_bars = 0
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            date = upload.get(row.get("video_id"))
            for s in row.get("setups") or []:
                n_setups += 1
                prices = []
                for k in PRICE_FIELDS:
                    p = to_num(s.get(k))
                    if p is not None:
                        prices.append(p)
                kl = s.get("key_levels")
                if isinstance(kl, list):
                    for v in kl:
                        p = to_num(v)
                        if p is not None:
                            prices.append(p)
                if not prices:
                    continue
                tk = resolve(s.get("ticker"))
                if tk is None:
                    no_ticker += 1
                    continue
                rng = day_range(tk, date)
                if rng is None:
                    no_bars += 1
                    continue
                low, high = rng
                n_gradeable += 1
                hits = [low * 0.98 <= p <= high * 1.02 for p in prices]
                n_prices += len(prices)
                n_prices_in += sum(hits)
                if all(hits):
                    n_in += 1
        results.append({
            "rung": rung, "model": model, "setups": n_setups,
            "gradeable": n_gradeable, "in_range": n_in,
            "setup_pct": (n_in / n_gradeable * 100) if n_gradeable else 0.0,
            "price_pct": (n_prices_in / n_prices * 100) if n_prices else 0.0,
            "prices": n_prices,
            "no_ticker": no_ticker, "no_bars": no_bars,
        })

    print("| rung | model | setups | gradeable | price_in_range_pct | setup_all_in_range_pct | dropped_no_ticker | dropped_no_bars |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    for r in results:
        print("| %s | %s | %d | %d | %.1f%% (n=%d) | %.1f%% | %d | %d |" % (
            r["rung"], r["model"], r["setups"], r["gradeable"],
            r["price_pct"], r["prices"], r["setup_pct"],
            r["no_ticker"], r["no_bars"]))
    Path(RESEARCH / "_video_ladder_grade.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
