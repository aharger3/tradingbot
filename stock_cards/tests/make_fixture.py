"""Rebuild the test fixture from the local archive and the S2 tape (needs both; the tests do not).

  python -m stock_cards.tests.make_fixture

Writes fixtures/: PLTR_2026-08-04.csv and QQQ_2026-08-04.csv (premarket + RTH to 11:05, archive format),
context.json (prior-day numbers and HTF bias for both, built by the production code path) and
expected.json (the tape's PLTR rows for that day, which the detector must reproduce).
"""
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path

from .. import context
from ..config import ARCHIVE, PROD

DAY, SYM = "2026-08-04", "PLTR"
HERE = Path(__file__).parent / "fixtures"
TAPE = PROD / "research" / "tape" / "baseline_2026-09-13.json.gz"


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    ctx = {}
    prior = context.load_prior([SYM, "QQQ"], DAY, data_dir=HERE.parent / "_nocache")
    for s in (SYM, "QQQ"):
        src = ARCHIVE / s / f"{DAY}.csv"
        with open(src, newline="", encoding="utf-8") as fi, open(HERE / f"{s}_{DAY}.csv", "w", newline="", encoding="utf-8") as fo:
            r = csv.DictReader(fi)
            w = csv.writer(fo)
            w.writerow(["Datetime", "Open", "High", "Low", "Close", "Volume"])
            for row in r:
                if row["Datetime"][11:19] < "11:05:00":
                    w.writerow([row["Datetime"], row["Open"], row["High"], row["Low"], row["Close"], row["Volume"]])
        c = context.build_context(prior[s])
        ctx[s] = {"pdh": c.pdh, "pdl": c.pdl, "pdo": c.pdo, "pdc": c.pdc, "bias": c.bias, "prev_day": c.prev_day}
    (HERE / "context.json").write_text(json.dumps(ctx, indent=1), encoding="utf-8")
    exp = [{k: t[k] for k in ("sym", "day", "et", "dir", "stop", "status", "tags")}
           for t in json.load(gzip.open(TAPE))["trades"] if t["sym"] == SYM and t["day"] == DAY]
    (HERE / "expected.json").write_text(json.dumps(exp, indent=1), encoding="utf-8")
    print(len(exp), "tape rows;", sum("09:35" <= e["et"] <= "10:58" for e in exp), "in window")


if __name__ == "__main__":
    main()
