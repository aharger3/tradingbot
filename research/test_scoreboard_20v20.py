"""scoreboard_20v20 -- checks on research/scoreboard.md.

Plain asserts, same shape as the other research/test_*.py files. Does not
re-run the scoreboard; asserts against the committed output.

    python research/test_scoreboard_20v20.py
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MD = os.path.join(HERE, "scoreboard.md")
OUT_JSON = os.path.join(HERE, "scoreboard.json")


def main():
    assert os.path.exists(OUT_MD), "missing %s -- run research/scoreboard_20v20.py" % OUT_MD
    text = open(OUT_MD, encoding="utf-8").read()
    assert len(text) > 100, "%s is suspiciously short" % OUT_MD

    for needle in ("last 20", "prior 20", "Kill rule", "ev/R"):
        assert needle in text, "%s missing expected section %r" % (OUT_MD, needle)

    # the delta line's sign must match the GREEN/RED call
    m = re.search(r"Delta \(last - prior\): ([+-][\d.]+) ev/R -- (GREEN|RED)", text)
    assert m, "%s missing a parseable delta line" % OUT_MD
    delta, call = float(m.group(1)), m.group(2)
    assert (delta > 0) == (call == "GREEN"), (
        "%s: delta %+.4f does not match its own GREEN/RED call %r" % (OUT_MD, delta, call))

    print("  ok   %s states last-20/prior-20/kill-rule sections, and the delta sign "
          "matches its own GREEN/RED call (delta=%+.4f, call=%s)" % (
              os.path.basename(OUT_MD), delta, call))

    # The historical-context fields (added after the 2026-09-03 adversarial
    # pass) must exist and be sane -- the whole point of them is that a bare
    # kill-rule/RED call is never reported again without this next to it.
    assert os.path.exists(OUT_JSON), "missing %s -- run research/scoreboard_20v20.py" % OUT_JSON
    blob = json.load(open(OUT_JSON, encoding="utf-8"))
    r60 = blob.get("rolling_60_context") or {}
    r20 = blob.get("rolling_20v20_context") or {}
    assert 0.0 <= r60.get("pct_at_or_below_zero", -1) <= 100.0, (
        "rolling_60_context.pct_at_or_below_zero out of [0,100]: %r" % r60.get("pct_at_or_below_zero"))
    assert 0.0 <= r20.get("pct_red", -1) <= 100.0, (
        "rolling_20v20_context.pct_red out of [0,100]: %r" % r20.get("pct_red"))
    if r60.get("current_percentile") is not None:
        assert 0.0 <= r60["current_percentile"] <= 100.0, (
            "rolling_60_context.current_percentile out of [0,100]: %r" % r60["current_percentile"])
    t250 = blob.get("trailing_250")
    if t250:
        assert t250["current_streak_sessions"] <= t250["longest_streak_ever"], (
            "current negative streak (%r) exceeds the longest-ever streak (%r) -- "
            "current cannot be longer than the max over all history including itself"
            % (t250["current_streak_sessions"], t250["longest_streak_ever"]))
        assert (t250["current_streak_sessions"] > 0) == t250["still_negative_at_book_end"], (
            "current_streak_sessions (%r) inconsistent with still_negative_at_book_end (%r)"
            % (t250["current_streak_sessions"], t250["still_negative_at_book_end"]))
    print("  ok   rolling-60 and rolling-20v20 historical-context fields are present and "
          "in-range, and trailing-250's streak fields are internally consistent")

    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
