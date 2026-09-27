"""B1 real-NQ OOS: run the frozen v3-t-mnq / v2 orb1m engine, unchanged, on Databento NQ bars. Paper only.

  python oos_db.py            # window A (pre-registered gate): 2019-09-26 .. 2024-09-25
  python oos_db.py --window B # window B (report only, not a gate): 2010-06-07 .. 2019-09-25

Byte-identical: mnq.py and orb1m.py are imported from their production paths and their sha256 (LF-normalised)
is asserted before anything runs. Only two module globals are repointed, both data-only:
  mnq.AR  -> DB_ROOT\\win_<w> (load_real() globs <that>\\t01-orb5\\fut\\NQ*.csv, same format as recovered bars)
  mnq.HOL -> HOL | full NYSE closures 2010-2024 (mnq.HOL only lists 2024-2026; same rule, earlier years)
Gate (OMEN-SHIP-PLAN-v3 sec 2): mean R >= +0.15, both halves > 0, shuffle p < .05.
"""
import sys, json, hashlib, argparse, os
from pathlib import Path

AR = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs"
FROZEN = {AR + r"\v3-t-mnq\mnq.py": "b9068778d3ec871b",           # raw-bytes sha (untracked CRLF file)
          AR + r"\v2-t01-orb-1m\orb1m.py": "bafd7ce4e4f69250"}     # ship-plan sha, LF-normalised (raw = af5b8abb)
CELL = ("v2 baseline (OR5 D1.0 strong)", "10:30", "2R")
WINDOWS = {"A": ("2019-09-26", "2024-09-25"), "B": ("2010-06-07", "2019-09-25")}
DB_ROOT = os.environ.get("DB_ROOT", r"C:\Users\aharg\Desktop\Projects\omen-data\databento")
# NYSE full-day closures (CME equity runs a short 09:30-13:00 ET session on most of these, so they must be skipped)
HOL_EXTRA = set("""
2010-07-05 2010-09-06 2010-11-25 2010-12-24 2011-01-17 2011-02-21 2011-04-22 2011-05-30 2011-07-04 2011-09-05
2011-11-24 2011-12-26 2012-01-02 2012-01-16 2012-02-20 2012-04-06 2012-05-28 2012-07-04 2012-09-03 2012-10-29
2012-10-30 2012-11-22 2012-12-25 2013-01-01 2013-01-21 2013-02-18 2013-03-29 2013-05-27 2013-07-04 2013-09-02
2013-11-28 2013-12-25 2014-01-01 2014-01-20 2014-02-17 2014-04-18 2014-05-26 2014-07-04 2014-09-01 2014-11-27
2014-12-25 2015-01-01 2015-01-19 2015-02-16 2015-04-03 2015-05-25 2015-07-03 2015-09-07 2015-11-26 2015-12-25
2016-01-01 2016-01-18 2016-02-15 2016-03-25 2016-05-30 2016-07-04 2016-09-05 2016-11-24 2016-12-26 2017-01-02
2017-01-16 2017-02-20 2017-04-14 2017-05-29 2017-07-04 2017-09-04 2017-11-23 2017-12-25 2018-01-01 2018-01-15
2018-02-19 2018-03-30 2018-05-28 2018-07-04 2018-09-03 2018-11-22 2018-12-05 2018-12-25 2019-01-01 2019-01-21
2019-02-18 2019-04-19 2019-05-27 2019-07-04 2019-09-02 2019-11-28 2019-12-25 2020-01-01 2020-01-20 2020-02-17
2020-04-10 2020-05-25 2020-07-03 2020-09-07 2020-11-26 2020-12-25 2021-01-01 2021-01-18 2021-02-15 2021-04-02
2021-05-31 2021-07-05 2021-09-06 2021-11-25 2021-12-24 2022-01-17 2022-02-21 2022-04-15 2022-05-30 2022-06-20
2022-07-04 2022-09-05 2022-11-24 2022-12-26 2023-01-02 2023-01-16 2023-02-20 2023-04-07 2023-05-29 2023-06-19
2023-07-04 2023-09-04 2023-11-23 2023-12-25 2024-01-01 2024-01-15 2024-02-19 2024-03-29 2024-05-27 2024-06-19
2024-07-04 2024-09-02""".split())


def sha(path, lf):
    b = open(path, "rb").read()
    return hashlib.sha256(b.replace(b"\r\n", b"\n") if lf else b).hexdigest()


def assert_frozen():
    for p, want in FROZEN.items():
        got = sha(p, lf=p.endswith("orb1m.py"))
        assert got.startswith(want), f"{p} changed: {got[:16]} != {want}"


def stage(window):
    """Copy only the NQ contracts that can be front inside the window into DB_ROOT\\win_<w> (keeps load_real fast)."""
    import shutil, glob
    a, b = WINDOWS[window]; lo, hi = int(a[:4]), int(b[:4]) + 1
    dst = Path(DB_ROOT) / f"win_{window}" / "t01-orb5" / "fut"; dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in glob.glob(str(Path(DB_ROOT) / "t01-orb5" / "fut" / "NQ*.csv")):
        if lo <= int(Path(f).stem.split("_")[1]) <= hi:
            shutil.copy2(f, dst / Path(f).name); n += 1
    assert n, f"no NQ contract files for window {window} under {DB_ROOT}"
    return str(Path(DB_ROOT) / f"win_{window}")


def gate(s):
    ok = s.get("n", 0) >= 30 and s["R"] >= 0.15 and (s["h1"] or -1) > 0 and (s["h2"] or -1) > 0 and s["p"] < 0.05
    return "SHIP-ELIGIBLE (go to 1-month Lane R paper)" if ok else "NO-SHIP"


def main(window, nshuf=200, db_root=None):
    global DB_ROOT
    DB_ROOT = db_root or DB_ROOT
    assert_frozen()
    sys.path.insert(0, AR + r"\v3-t-mnq")
    import mnq
    mnq.AR = stage(window)
    mnq.HOL = set(mnq.HOL) | HOL_EXTRA
    a, b = WINDOWS[window]
    days = [A for A in mnq.load_real() if a <= A["date"] <= b]
    assert days, f"no Databento NQ days in {a}..{b} under {DB_ROOT}"
    T, sh = mnq.run_cell(days, *CELL, nshuf=nshuf)
    s = mnq.summ(T, sh, days)
    out = dict(window=window, span=[days[0]["date"], days[-1]["date"]], sessions=len(days), cell="|".join(CELL),
               frozen={Path(p).name: h for p, h in FROZEN.items()}, data=DB_ROOT, **s,
               verdict=gate(s) if window == "A" else "report-only")
    here = Path(os.environ.get("OOS_OUT") or Path(__file__).parent)
    json.dump(out, open(here / f"oos_{window}.json", "w"), indent=1, default=float)
    json.dump(T, open(here / f"oos_{window}_trades.json", "w"), default=float)
    print(json.dumps({k: out[k] for k in ("span", "sessions", "n", "R", "h1", "h2", "p", "usd_day", "verdict") if k in out}, default=float))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--window", default="A", choices=list(WINDOWS)); a = ap.parse_args()
    main(a.window)
