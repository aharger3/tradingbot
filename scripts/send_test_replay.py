"""One real test push: replay candidate from real NQ 1-min data
(2025-11-03, ORB break + OR-low retest, SHORT). Title prefixed TEST.
PAPER only -- this only sends an ntfy notification, it never places
an order anywhere.

Run from repo root:  python scripts\\send_test_replay.py
"""
import csv
from pathlib import Path

from eye_card.chart import Candidate, render_candidate_chart
from eye_card.notify import send_card

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "eye_card" / "tests" / "fixtures" / "replay_nq_2025.csv"
OUT_PNG = ROOT / "eye_card" / "tests" / "fixtures" / "replay_card.png"


def main():
    bars = []
    with open(FIXTURE, newline="") as fh:
        for row in csv.DictReader(fh):
            bars.append({
                "time": row["time"],
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })

    cand = Candidate(
        candidate_id="REPLAY-20251103-0949",
        symbol="NQ",
        direction="SHORT",
        trigger_time="09:49:00",
        entry=26154.00,
        stop=26172.75,
        targets=[26126.00, 26107.00],
        level=26155.00,
        level_label="OR low",
        setup="ORB break + retest",
        reason="OR low break at 09:42, wick-only retest, rejected at 09:47",
        or_high=26266.00,
        or_low=26155.00,
    )

    render_candidate_chart(cand, bars, OUT_PNG)
    result = send_card(cand, OUT_PNG, token="dev-local-only", test_title_prefix="TEST")
    print(f"sent={result.ok} status={result.status_code} url={result.url}")


if __name__ == "__main__":
    main()
