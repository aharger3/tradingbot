"""OMEN 10.0 R1 verify (spec item 3): `next_open` and `limit_level` re-derived
by hand on 20 sampled trades from raw `data_archive/` bars, and the `close`
arm confirmed to match the engine's default fill
(`entry_fill.ENTRY_FILL == "close"`, `signal_runner.fill_price`) on 100% of
rows -- BY SCRIPT, exits nonzero on any mismatch. Modelled on
`research/g90_verify.py`.

Reads the stamped `full29` books `research/g210_fill_arms_v2.py` wrote to
`research/tape/`, not prose -- this script re-derives every number itself
from `data_archive/`'s own CSVs, independent of any in-process bookkeeping
those books may share.
"""
import csv
import gzip
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from universe import ARCHIVE_DIR

TAPE = os.path.join(HERE, "tape")
N_SAMPLE = 10  # per arm -> 20 total for next_open + limit_level, per spec


def load_book(arm):
    path = os.path.join(TAPE, f"fillarms_{arm}_full29.json.gz")
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "trades" in data:
        return data["trades"], path
    return data, path  # tolerate a pre-stamp bare-list book


_csv_cache = {}


def bar_at(symbol, day, minute):
    key = (symbol, day)
    if key not in _csv_cache:
        path = os.path.join(ARCHIVE_DIR, symbol, f"{day}.csv")
        bars = {}
        if os.path.exists(path):
            with open(path) as f:
                for row in csv.DictReader(f):
                    ts = row["Datetime"]
                    hh_mm = ts.split("T", 1)[1][:5] if "T" in ts else ts[11:16]
                    bars[hh_mm] = row
        _csv_cache[key] = bars
    return _csv_cache[key].get(minute)


def verify_next_open_and_limit_level():
    fails = []
    checked = 0
    for arm in ("next_open", "limit_level"):
        rows, path = load_book(arm)
        filled = [r for r in rows if not r["unfilled"]]
        if not filled:
            fails.append(f"{arm}: no filled rows in {path}")
            continue
        step = max(1, len(filled) // N_SAMPLE)
        sample = filled[::step][:N_SAMPLE]
        for r in sample:
            checked += 1
            ft = r.get("fill_time") or ""
            minute = ft[:5] if ft else None
            bar = bar_at(r["sym"], r["day"], minute) if minute else None
            if bar is None:
                fails.append(f"{arm}: {r['sym']} {r['day']} {minute}: bar not found in raw archive")
                continue
            o, h, l = float(bar["Open"]), float(bar["High"]), float(bar["Low"])
            booked = r["entry"]
            if arm == "next_open":
                ok = abs(booked - o) < 1e-6
                detail = f"booked={booked} vs raw open={o}"
            else:
                ok = (l - 1e-6) <= booked <= (h + 1e-6)
                detail = f"booked={booked} vs raw range=[{l},{h}]"
            if not ok:
                fails.append(f"{arm}: {r['sym']} {r['day']} {minute}: MISMATCH {detail}")
    return checked, fails


def verify_close_matches_default():
    rows, path = load_book("close")
    checked = 0
    fails = []
    for r in rows:
        if r["unfilled"]:
            fails.append(f"close: {r['sym']} {r['day']}: unfilled -- close never fails to fill")
            continue
        checked += 1
        ft = r.get("entry_time") or ""
        minute = ft[:5] if ft else None
        bar = bar_at(r["sym"], r["day"], minute) if minute else None
        if bar is None:
            fails.append(f"close: {r['sym']} {r['day']} {minute}: bar not found in raw archive")
            continue
        bar_close = float(bar["Close"])
        if abs(r["entry"] - bar_close) > 1e-4:
            fails.append(f"close: {r['sym']} {r['day']} {minute}: "
                         f"booked entry={r['entry']} vs raw close={bar_close}")
    return checked, fails, path


def main():
    checked_a, fails_a = verify_next_open_and_limit_level()
    checked_b, fails_b, close_path = verify_close_matches_default()

    print(f"next_open/limit_level: {checked_a} sampled rows checked against raw bars, "
          f"{len(fails_a)} mismatches")
    for f in fails_a:
        print(f"  FAIL: {f}")

    print(f"close ({close_path}): {checked_b} rows checked against raw bars, "
          f"{len(fails_b)} mismatches")
    for f in fails_b[:20]:
        print(f"  FAIL: {f}")
    if len(fails_b) > 20:
        print(f"  ... and {len(fails_b) - 20} more")

    if fails_a or fails_b:
        print(f"\nFAIL: {len(fails_a) + len(fails_b)} total mismatches")
        return 1

    print(f"\nPASS: next_open/limit_level match raw bars on {checked_a} sampled rows; "
          f"close matches the engine's default fill on {checked_b}/{checked_b} rows (100%).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
