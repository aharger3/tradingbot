"""g213_verify.py -- T2's verify clause, part 1: hand-check 20 option rows.

Picks 20 rows from `research/tape/instruments_2026-09-05.json.gz` with
`instrument_source=="real"` (fixed seed, so the sample is reproducible) and
re-fetches the SAME contract/day/minute directly from Polygon -- a fresh
HTTP call, not a read of g213_instruments.py's own cache -- and diffs the
close price it stored against what Polygon returns right now. A real
options aggregate bar does not change after the fact, so any mismatch here
is a bug in g213_instruments.py's own pricing, not a data drift.

Part 2 of the row's verify clause -- the futures ratio checked against 7
days of ES/MES 1-minute overlap "if any is on disk" -- is reported here as
UNVERIFIED: `find data_archive -iname "*ES*" -o -iname "*MES*" -o -iname
"*NQ*" -o -iname "*MNQ*"` returns nothing on this box (checked 2026-09-05).
"""
from __future__ import annotations

import gzip
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.g73_polygon_fetch import _get  # noqa: E402

BOOK = ROOT / "research" / "tape" / "instruments_2026-09-05.json.gz"
N_CHECK = 20
SEED = 20260905


def fetch_fresh(ticker, day, hhmm):
    """A fresh (uncached) 1-minute bar close at hhmm ET, straight from Polygon."""
    j = _get("/v2/aggs/ticker/%s/range/1/minute/%s/%s" % (ticker, day, day),
              adjusted="true", sort="asc", limit=50000)
    if "_status" in j:
        return None, "HTTP %s" % j["_status"]
    import datetime as dt
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    for b in (j.get("results") or []):
        ts = dt.datetime.fromtimestamp(b["t"] / 1000, tz=dt.timezone.utc).astimezone(ET)
        if ts.strftime("%H:%M") == hhmm:
            return b["c"], None
    # nearest within 5 minutes, matching g213_instruments.nearest_minute
    h, m = int(hhmm[:2]), int(hhmm[3:])
    total = h * 60 + m
    best, best_d = None, 6
    for b in (j.get("results") or []):
        ts = dt.datetime.fromtimestamp(b["t"] / 1000, tz=dt.timezone.utc).astimezone(ET)
        d = abs((ts.hour * 60 + ts.minute) - total)
        if d < best_d:
            best_d, best = d, b["c"]
    return best, None if best is not None else "no bar within 5m"


def add_minutes(hhmm, n):
    h, m = int(hhmm[:2]), int(hhmm[3:])
    total = h * 60 + m + int(n)
    return "%02d:%02d" % (total // 60, total % 60)


def main():
    if not BOOK.exists():
        print("no instruments book at %s -- run g213_instruments.py --stage report first" % BOOK)
        return 1
    with gzip.open(BOOK, "rt", encoding="utf-8") as f:
        book = json.load(f)
    real_rows = [t for t in book["trades"] if t["options"].get("instrument_source") == "real"]
    print("instruments book has %d real-priced option rows out of %d total"
          % (len(real_rows), len(book["trades"])))
    if not real_rows:
        print("nothing to hand-check -- 0 real rows (fetch stage may not have run / all 403)")
        return 0
    random.Random(SEED).shuffle(real_rows)
    sample = real_rows[:N_CHECK]
    return _run(sample)


def _run(sample):
    n_pass, n_fail, n_err = 0, 0, 0
    lines = ["# g213_verify -- 20 hand-checked option rows\n"]
    for t in sample:
        opt = t["options"]
        ticker = opt["contract"]
        bars = t.get("bars", 1) or 1
        exit_clock = add_minutes(t["et"], bars)
        entry_fresh, e1 = fetch_fresh(ticker, t["day"], t["et"])
        exit_fresh, e2 = fetch_fresh(ticker, t["day"], exit_clock)
        if e1 or e2 or entry_fresh is None or exit_fresh is None:
            n_err += 1
            lines.append("- %s %s %s %s: FETCH ERROR (%s / %s)"
                          % (t["sym"], t["day"], t["et"], ticker, e1, e2))
            continue
        ok = (abs(entry_fresh - opt["entry_opt"]) < 0.01
              and abs(exit_fresh - opt["exit_opt"]) < 0.01)
        if ok:
            n_pass += 1
        else:
            n_fail += 1
        lines.append("- %s %s %s %s: stored entry=%.2f exit=%.2f -- fresh entry=%.2f exit=%.2f -- %s"
                      % (t["sym"], t["day"], t["et"], ticker, opt["entry_opt"], opt["exit_opt"],
                         entry_fresh, exit_fresh, "PASS" if ok else "FAIL"))
    lines.insert(1, "%d pass, %d fail, %d fetch error, of %d sampled\n"
                 % (n_pass, n_fail, n_err, len(sample)))
    out = ROOT / "research" / "g213_verify.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("\nFutures ratio check: UNVERIFIED -- no ES/MES or NQ/MNQ 1-minute bars on "
          "disk under data_archive/ (checked 2026-09-05).")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
