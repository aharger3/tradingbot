import csv
import json
import subprocess
import sys
from pathlib import Path

import massive_futures as mf

# Docs "Sample Response" (aggregates.md), verbatim shape
SAMPLE = json.loads("""{"request_id":"b452e45b7eaad14151c3e1ce5129b558","results":[
{"close":2874.2,"dollar_volume":380717446,"high":2877.1,"low":2837.4,"open":2850.4,"session_end_date":"2025-02-04","settlement_price":2875.8,"ticker":"GCJ5","transactions":74262,"volume":133127,"window_start":1738540800000000000},
{"close":2884.8,"dollar_volume":448429944.1,"high":2906,"low":2870.1,"open":2873.7,"session_end_date":"2025-02-05","settlement_price":2893,"ticker":"GCJ5","transactions":83673,"volume":155170,"window_start":1738627200000000000}],"status":"OK"}""")

NS = 1_000_000_000


def sess(c, day, vol):
    return {"ticker": c, "session_end_date": day, "volume": vol}


def minute(ts, c="X"):
    return {"window_start": ts, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 3, "ticker": c}


def test_ticker_codes():
    assert mf.contract_ticker("MNQ", 2026, 12) == "MNQZ6"
    assert mf.contract_ticker("NQ", 2025, 3) == "NQH5"
    assert [mf.contract_ticker("NQ", 2026, m) for m in (3, 6, 9, 12)] == ["NQH6", "NQM6", "NQU6", "NQZ6"]


def test_quarterly_contracts():
    assert mf.quarterly_contracts("MNQ", "2026-09-01", "2026-09-30") == ["MNQU6", "MNQZ6"]
    assert mf.quarterly_contracts("NQ", "2026-09-25", "2026-10-05") == ["NQZ6"]


def test_url_matches_docs_path():
    u = mf.build_url("MNQZ6", "1min", "2026-10-01", "2026-10-02")
    assert u.startswith("https://api.massive.com/futures/v1/aggs/MNQZ6?resolution=1min")
    assert "window_start.gte=2026-10-01" in u and "window_start.lt=2026-10-02" in u


def test_paging_and_throttle():
    pages = {"u1": {"results": SAMPLE["results"][:1], "next_url": "u2"},
             "u2": {"results": SAMPLE["results"][1:]}}
    seen, ticks = [], []

    def fetch(url):
        seen.append(url)
        return pages["u1"] if len(seen) == 1 else pages["u2"]

    rows = mf.fetch_aggs("GCJ5", "1session", "2025-02-03", "2025-02-06", fetch, throttle=lambda: ticks.append(1))
    assert len(rows) == 2 and seen[1] == "u2" and len(ticks) == 2


def test_throttle_sleeps_between_calls():
    t = [100.0]
    sleeps = []
    th = mf.Throttle(12.0, sleep=lambda s: sleeps.append(s), clock=lambda: t[0])
    th()
    t[0] += 2
    th()
    assert sleeps == [10.0]


def test_roll_picks_higher_volume_and_never_backward():
    by = {"NQU6": [sess("NQU6", "2026-09-10", 900), sess("NQU6", "2026-09-11", 800),
                   sess("NQU6", "2026-09-14", 100), sess("NQU6", "2026-09-15", 500)],
          "NQZ6": [sess("NQZ6", "2026-09-10", 100), sess("NQZ6", "2026-09-11", 200),
                   sess("NQZ6", "2026-09-14", 700), sess("NQZ6", "2026-09-15", 300)]}
    f = mf.pick_front_by_volume(by)
    assert f == {"2026-09-10": "NQU6", "2026-09-11": "NQU6", "2026-09-14": "NQZ6", "2026-09-15": "NQZ6"}


def test_year_digit_wrap():
    by = {"NQZ9": [sess("NQZ9", "2029-12-10", 1)], "NQH0": [sess("NQH0", "2029-12-10", 5)]}
    assert mf.pick_front_by_volume(by)["2029-12-10"] == "NQH0"


def test_session_date():
    # Sun 2026-09-13 22:00 UTC = 18:00 EDT -> Monday's session
    ts = int(__import__("datetime").datetime(2026, 9, 13, 22, 0, tzinfo=__import__("datetime").timezone.utc).timestamp()) * NS
    assert mf.session_date(ts) == "2026-09-14"
    assert mf.session_date(ts + 3600 * 5 * NS) == "2026-09-14"   # 23:00 ET Sun still Monday's
    assert mf.session_date(ts + 20 * 3600 * NS) == "2026-09-14"  # Mon 14:00 ET


def test_stitch_monotonic_no_dupes():
    base = 1_789_000_000 * NS   # a weekday (Sep 2026)
    d = mf.session_date(base)
    u = [minute(base + i * 60 * NS) for i in range(0, 4)]
    z = [minute(base + i * 60 * NS) for i in range(2, 6)]      # overlaps u on i=2,3
    front = {d: "NQZ6"}
    out = mf.stitch({"NQU6": u, "NQZ6": z[::-1]}, front)
    ts = [b["window_start"] for b in out]
    assert ts == sorted(ts) and len(ts) == len(set(ts)) == 4
    assert {b["contract"] for b in out} == {"NQZ6"}


def test_write_csv_schema(tmp_path):
    p = tmp_path / "NQZ6_2026.csv"
    mf.write_csv(p, [{**minute(5 * NS), "contract": "NQZ6"}])
    rows = list(csv.reader(p.open()))
    assert rows[0] == ["ts_ns", "open", "high", "low", "close", "volume"]
    assert rows[1][0] == str(5 * NS)


def test_run_end_to_end_fake(tmp_path):
    base = 1_789_000_000 * NS
    d = mf.session_date(base)

    def fetch(url):
        t = url.split("/aggs/")[1].split("?")[0]
        if "1session" in url:
            return {"results": [sess(t, d, 10 if t.startswith("NQU") else 99)]}
        return {"results": [minute(base, t)]}

    paths = mf.run("NQ", "2026-09-01", "2026-09-30", tmp_path, fetch=fetch, throttle=lambda: None)
    assert [p.name for p in paths] == ["NQZ6_2026.csv"]


def test_missing_key_exit_2():
    env = {k: v for k, v in __import__("os").environ.items() if k != "POLYGON_API_KEY"}
    r = subprocess.run([sys.executable, str(Path(__file__).parent / "massive_futures.py"),
                        "MNQ", "2026-09-01", "2026-09-30", "--out", "x"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 2 and "POLYGON_API_KEY not set" in r.stderr
