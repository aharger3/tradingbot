"""
loop_alert.py -- watch research/tape/nightly.md; alert if the loop has held
3 nights in a row.

Usage:
    python research/loop_alert.py            # check real nightly.md, print status
    python research/loop_alert.py --test     # run self-check against mock data, no file touched
"""
import re
import sys
from pathlib import Path

NIGHTLY_PATH = Path(__file__).resolve().parent / "tape" / "nightly.md"
HOLD_STREAK = 3


def parse_decisions(text):
    """Pull the 'decision' column from the nightly.md markdown table, in file order."""
    decisions = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[0].lower() == "date" or set(cells[0]) <= {"-"}:
            continue  # header or separator row
        decisions.append(cells[2])
    return decisions


def check_hold_streak(decisions, streak=HOLD_STREAK):
    """Return True if the last `streak` decisions are all 'hold'."""
    if len(decisions) < streak:
        return False
    last = decisions[-streak:]
    return all(d.lower() == "hold" for d in last)


def run(path=NIGHTLY_PATH):
    text = path.read_text(encoding="utf-8")
    decisions = parse_decisions(text)
    alert = check_hold_streak(decisions)
    if alert:
        print(f"ALERT: last {HOLD_STREAK} nightly decisions were all 'hold' -> {decisions[-HOLD_STREAK:]}")
    else:
        tail = decisions[-HOLD_STREAK:] if decisions else []
        print(f"ok: no {HOLD_STREAK}-hold streak (last decisions: {tail})")
    return alert


def self_test():
    ok = True

    # case 1: 3 holds in a row -> alert True
    d = ["ship", "hold", "hold", "hold"]
    if check_hold_streak(d) is not True:
        print("FAIL: 3-hold streak not detected")
        ok = False

    # case 2: mixed -> alert False
    d = ["hold", "ship", "hold"]
    if check_hold_streak(d) is not False:
        print("FAIL: mixed decisions falsely alerted")
        ok = False

    # case 3: fewer than 3 rows -> alert False
    d = ["hold", "hold"]
    if check_hold_streak(d) is not False:
        print("FAIL: under-threshold rows falsely alerted")
        ok = False

    # case 4: parse a mock markdown table (mirrors nightly.md shape)
    mock = (
        "# nightly loop receipts\n\n"
        "| date | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id |\n"
        "|---|---|---|---|---|---|\n"
        "| 2026-09-17 | - | hold | - | - | - |\n"
        "| 2026-09-18 | - | hold | - | - | - |\n"
        "| 2026-09-19 | FLAG_X | hold | -1 -> -1 | 1 -> 1 | a -> b |\n"
    )
    decisions = parse_decisions(mock)
    if decisions != ["hold", "hold", "hold"]:
        print(f"FAIL: markdown parse mismatch, got {decisions}")
        ok = False
    if check_hold_streak(decisions) is not True:
        print("FAIL: parsed mock table did not trigger alert")
        ok = False

    if ok:
        print("PASS")
    return ok


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(0 if self_test() else 1)
    sys.exit(0 if run() else 0)
