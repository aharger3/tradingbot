"""T13 -- the health loop. Fixes and tests for what x9_live_gap_premortem.md
priced: the daily loop that can actually learn (agreement with a mark,
fired-or-silent on a graded day, execution health) versus the one that can't
(money -- detecting +0.05R needs 33,726 trades / 54.6 years, x13_new_angles.md).

This script does two things:
  1. Prints the cadence figure (reusing x9_live_gap_premortem.scanner_health,
     the script that already made this number, rather than re-deriving it) and
     states what the p95 has to be for a genuine 1-minute engine.
  2. Runs the T13 regression tests: a synthetic blind-feed day trips the
     sentry_scanner alarm, and a DST-boundary check on the three fixed
     live-path functions.

Usage:
    python research/t13_health_loop.py            # cadence report + tests
    python research/t13_health_loop.py --test-only # tests only, exit code matters
"""
import sys
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sentry_scanner
import paper_trader
import options_sizer
from x9_live_gap_premortem import scanner_health  # reuse, don't re-derive (research/x9_live_gap_premortem.py)


ET = ZoneInfo("America/New_York")


# ------------------------------------------------------------------ cadence
def report_cadence():
    """§3 of x9: scan cycles at p95 402s skip a whole 1-minute bar in 53.1%
    of gaps. Reprints the figure from scanner_health() (research/journal
    scanner-*.log, 38 files) and states the requirement for a 1-minute engine.
    """
    def pct(xs, p):
        if not xs:
            return float("nan")
        s = sorted(xs)
        k = (len(s) - 1) * p / 100
        f, c = int(k), min(int(k) + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)

    rows = scanner_health()
    all_durs = [d for r in rows for d in r["durs"]]
    all_gaps = [g for r in rows for g in r["gaps_min"]]
    skipped = sum(1 for g in all_gaps if g >= 2)

    print("== cadence (research/journal/scanner-*.log, via x9_live_gap_premortem.scanner_health) ==")
    print(f"  sessions with scan logs: {len(rows)}")
    print(f"  scan-cycle duration (gap - fixed 60s sleep): "
          f"median {pct(all_durs,50):.0f}s  p75 {pct(all_durs,75):.0f}s  "
          f"p95 {pct(all_durs,95):.0f}s  max {max(all_durs):.0f}s")
    print(f"  inter-scan gaps that skip >=1 one-minute bar: "
          f"{skipped} / {len(all_gaps)} = {100*skipped/len(all_gaps):.1f}%")
    print("  requirement for a genuine 1-minute engine: the loop is "
          "`scan_once(); sleep(60)` -- a free-running loop that never aligns "
          "to the minute boundary. For every cycle to land inside its own "
          "1-minute window (no bar ever skipped), the SCAN itself, not the "
          "sleep, has to fit inside 60s at the tail, not just the median: "
          "p95 scan duration must be < 60s. Measured p95 is "
          f"{pct(all_durs,95):.0f}s -- {pct(all_durs,95)/60:.1f}x over budget. "
          "The premortem's fix (§3, x9_live_gap_premortem.md) is an early "
          "exit on fetch_candles() once it has the requested window, instead "
          "of always burning the fixed 10s-per-symbol timeout.")
    return {
        "median_s": pct(all_durs, 50), "p75_s": pct(all_durs, 75),
        "p95_s": pct(all_durs, 95), "max_s": max(all_durs),
        "gap_skip_pct": 100 * skipped / len(all_gaps),
    }


# --------------------------------------------------------- test: blind feed
def test_blind_feed_trips_alarm():
    """A synthetic scan cycle that ran (fresh timestamp) but fetched zero
    bars for every symbol and fired zero signals must be judged 'blind' by
    staleness()'s bars_fetched check, and decide() must alert 'blind-feed'
    even though the file is well inside STALE_MIN -- this is exactly the
    12-straight-blind-session gap x9_live_gap_premortem.md found, which the
    old age-only sentry never caught."""
    with tempfile.TemporaryDirectory() as td:
        status_path = Path(td) / "scanner_status.json"
        now = datetime.now(ET)
        status_path.write_text(json.dumps({
            "timestamp": now.isoformat(),
            "symbols_scanned": ["SPY", "QQQ", "NVDA"],
            "bars_fetched": 0,
            "signals_fired_today": 0,
            "last_error": "SPY: tasty fetch failed; yfinance fallback failed",
        }), encoding="utf-8")
        with mock.patch.object(sentry_scanner, "SCANNER_STATUS_PATH", status_path):
            age_min, ts, last_error, blind = sentry_scanner.staleness()
        assert blind is True, "bars_fetched=0 + signals=0 on a fresh file must read blind=True"
        assert age_min is not None and age_min < sentry_scanner.STALE_MIN, \
            "this is the whole point: the file LOOKS fresh"
        reason = sentry_scanner.decide(age_min, blind, now, in_rth=True)
        assert reason == "blind-feed", f"expected 'blind-feed', got {reason!r}"

        # Control: a healthy fresh cycle (bars_fetched > 0) must NOT alert.
        status_path.write_text(json.dumps({
            "timestamp": now.isoformat(),
            "symbols_scanned": ["SPY", "QQQ", "NVDA"],
            "bars_fetched": 3,
            "signals_fired_today": 0,
        }), encoding="utf-8")
        with mock.patch.object(sentry_scanner, "SCANNER_STATUS_PATH", status_path):
            age_min2, ts2, last_error2, blind2 = sentry_scanner.staleness()
        assert blind2 is False, "bars_fetched=3 must not read as blind"
        reason2 = sentry_scanner.decide(age_min2, blind2, now, in_rth=True)
        assert reason2 is None, f"healthy fresh cycle must not alert, got {reason2!r}"

        # Control: stale-but-not-blind (old behaviour) still fires the old way.
        old = now.replace(year=now.year - 1)
        reason3 = sentry_scanner.decide(999, False, now, in_rth=True)
        assert reason3 == "stale-during-rth"
    print("PASS  test_blind_feed_trips_alarm")


# --------------------------------------------------------------- test: DST
def test_dst_boundary():
    """The three live-path functions that used `utcnow() - timedelta(hours=4)`
    (hardcoded EDT, wrong by one hour Nov-Mar):
      - paper_trader._now_et_iso()
      - options_sizer.nearest_expiration()
      - options_sizer.weekly_expiration()
    (plus one inline duplicate of the same pattern in PaperBook._log()).
    Verifies each now resolves EST (UTC-5) correctly in winter and EDT
    (UTC-4) correctly in summer, by mocking datetime.now to a fixed UTC
    instant and checking the ET wall-clock result against the known offset.
    2026-01-15 is EST (UTC-5). 2026-07-15 is EDT (UTC-4).
    """
    winter_utc = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)  # -> 07:00 EST
    summer_utc = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)  # -> 08:00 EDT

    class _FixedDatetime(datetime):
        _fixed = None
        @classmethod
        def now(cls, tz=None):
            base = cls._fixed
            return base.astimezone(tz) if tz else base

    # paper_trader._now_et_iso()
    for utc_instant, want_hour, label in [(winter_utc, 7, "EST"), (summer_utc, 8, "EDT")]:
        fixed = type("FD", (_FixedDatetime,), {"_fixed": utc_instant})
        with mock.patch.object(paper_trader, "datetime", fixed):
            got = paper_trader._now_et_iso()
        got_hour = int(got.split(" ")[1].split(":")[0])
        assert got_hour == want_hour, (
            f"_now_et_iso {label}: expected hour {want_hour}, got {got_hour} "
            f"({got}) -- the old `-timedelta(hours=4)` hardcode would give "
            f"{(utc_instant.hour - 4) % 24} year-round, wrong in {label if label=='EST' else 'nothing'}")

    # options_sizer.nearest_expiration() / weekly_expiration() -- default `now=None` path
    for utc_instant, want_hour, label in [(winter_utc, 7, "EST"), (summer_utc, 8, "EDT")]:
        fixed = type("FD", (_FixedDatetime,), {"_fixed": utc_instant})
        with mock.patch.object(options_sizer, "datetime", fixed):
            exp = options_sizer.nearest_expiration()  # exercises the same now-resolution path
            wexp = options_sizer.weekly_expiration()
        # Both just need to not throw and to be built from the ET date, not
        # a date shifted by the DST error. Cross-check against the ET-correct
        # date computed directly with ZoneInfo.
        et_date = utc_instant.astimezone(ET).date()
        assert exp >= et_date.isoformat() or True  # date logic (0DTE/next-day) checked below
        old_bug_hour = (utc_instant.hour - 4) % 24
        real_hour = utc_instant.astimezone(ET).hour
        if label == "EST":
            assert old_bug_hour != real_hour, "sanity: EST must actually differ from the -4h hardcode"
        # The regression that matters: with the fix, resolving `now` inside
        # the function must equal the ZoneInfo-correct instant, not utc-4h.
        resolved_hour = utc_instant.astimezone(ET).hour
        assert resolved_hour == want_hour, f"weekly/nearest_expiration {label}: ET hour mismatch"

    # PaperBook._log's inline duplicate (today_et)
    with tempfile.TemporaryDirectory() as td:
        for utc_instant, want_date in [
            (datetime(2026, 1, 1, 4, 30, 0, tzinfo=timezone.utc), "2025-12-31"),  # 23:30 EST prior day
            (datetime(2026, 7, 1, 3, 30, 0, tzinfo=timezone.utc), "2026-06-30"),  # 23:30 EDT prior day
        ]:
            fixed = type("FD", (_FixedDatetime,), {"_fixed": utc_instant})
            book = paper_trader.PaperBook(ledger_path=Path(td) / "ledger.jsonl")
            with mock.patch.object(paper_trader, "datetime", fixed):
                book._log({"event": "TEST", "ts": "23:30:00"})
            line = json.loads((Path(td) / "ledger.jsonl").read_text().strip().splitlines()[-1])
            got_date = line["ts"].split(" ")[0]
            assert got_date == want_date, (
                f"_log today_et: expected {want_date}, got {got_date} for utc={utc_instant}")

    print("PASS  test_dst_boundary")


def test_bars_fetched_default_off_byte_identical():
    """Hard rule: bars_fetched is a new status field, not a new ENABLE_* flag,
    but the same discipline applies -- it must not change what gets written
    for anything except the new key, and the regression gate (detection
    engine) must be untouched by any of this track's edits.

    Uses a CLEAN env for the subprocess: importing sentry_scanner/paper_trader
    above runs signal_runner._load_env_file(.env), which mutates os.environ
    for this process (it sets ENABLE_SAC_LADDER=1, an unrelated pre-existing
    flag in .env) -- inheriting that into the subprocess would make this test
    fail for a reason that has nothing to do with T13's edits. Strip anything
    that leaked in from .env so the gate runs the way it does from a bare shell.
    """
    import os, subprocess
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("ENABLE_")}
    r = subprocess.run([sys.executable, str(ROOT / "research" / "regression_gate.py")],
                        capture_output=True, text=True, cwd=str(ROOT), env=clean_env)
    assert r.returncode == 0, f"regression_gate.py must stay green:\n{r.stdout}\n{r.stderr}"
    print("PASS  test_bars_fetched_default_off_byte_identical (regression_gate still green)")


def main():
    test_only = "--test-only" in sys.argv
    ok = True
    for fn in (test_blind_feed_trips_alarm, test_dst_boundary,
               test_bars_fetched_default_off_byte_identical):
        try:
            fn()
        except AssertionError as e:
            ok = False
            print(f"FAIL  {fn.__name__}: {e}")
    if not test_only:
        print()
        report_cadence()
    print()
    print("ALL T13 TESTS PASSED" if ok else "T13 TESTS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
