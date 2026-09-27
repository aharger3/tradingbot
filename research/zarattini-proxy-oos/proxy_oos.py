"""Zarattini NQ925 on the QQQ-proxy OOS window (2024-01-02..2024-09-25), frozen zarattini.py/bt.py unchanged. Paper only.

Data: tradingbot/data_archive/QQQ/*.csv (1-min, 04:00-20:00 ET incl. pre-market), the same files v3-t-mnq/mnq.py
load_proxy() used for the mantra OOS; prices x41.35 snapped to 0.25 (same NQ scaling). Written as one bt-format
bars file (ticker QQQPX) so the frozen bt.sessions/pre_bars/book run untouched. The 09:25-09:30 filter bar comes
from QQQ pre-market minutes (proxy for Globex NQ).

Cells: NQ925, slip 1 tick (entry 1 / stop 2 / close 1), net $1.24 RT, 10R target, flat 15:59 (frozen) and 11:00
(session truncated to tod<660, exit = frozen close-exit rule on the 10:59 bar).
Gate (v3 sec 2): n>=20, R/trade >= +0.15, both halves R/trade > 0, p < .05; p = 5,000 random-direction shuffles on
the same trade days (each day's long and short R precomputed with the frozen trade()).
  python proxy_oos.py  -> zarattini_proxy_oos.json (+ trades) in this dir
"""
import os, sys, json, gzip, glob, hashlib
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).parent
ZDIR = HERE.parent / "zarattini"
FROZEN = {"zarattini.py": "b0ed2caff323dfec", "bt.py": "e1e1d9c4913b4f96"}   # sha256 prefix, LF-normalised
QQQ = os.environ.get("QQQ_DIR", r"C:\Users\aharg\Desktop\Projects\tradingbot\data_archive\QQQ")
BARS = Path(os.environ.get("PROXY_ROOT", r"C:\Users\aharg\Desktop\Projects\omen-data\qqq-proxy"))
START, END, SCALE, TICK, NSHUF, MNQ_PT = "2024-01-02", "2024-09-25", 41.35, 0.25, 5000, 2.0


def assert_frozen():
    for n, want in FROZEN.items():
        got = hashlib.sha256((ZDIR / n).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        assert got.startswith(want), f"{n} changed: {got[:16]}"


def build_bars():
    rows = []
    for f in sorted(glob.glob(os.path.join(QQQ, "*.csv"))):
        D = os.path.basename(f)[:10]
        if not (START <= D <= END): continue
        d = pd.read_csv(f)
        ts = pd.to_datetime(d["Datetime"], format="mixed", utc=True).astype("int64")
        px = {k: np.round(d[k].to_numpy() * SCALE / TICK) * TICK for k in ("Open", "High", "Low", "Close")}
        rows += [[int(t), o, h, l, c, int(v)] for t, o, h, l, c, v in
                 zip(ts, px["Open"], px["High"], px["Low"], px["Close"], d["Volume"].fillna(0))]
    (BARS / "bars").mkdir(parents=True, exist_ok=True)
    json.dump(dict(ticker="QQQPX", rows=rows), gzip.open(BARS / "bars" / "NQ_QQQPX.json.gz", "wt"))
    return len(rows)


def run():
    assert_frozen()
    nrows = build_bars()
    os.environ["BARS_ROOT"] = str(BARS); sys.path.insert(0, str(ZDIR))
    import zarattini as Z
    sess = Z.bt.sessions("NQ"); pre = Z.pre_bars("NQ")
    dates = sorted(sess); mid = dates[len(dates) // 2]; Z.bt.SPLIT = mid
    rng = np.random.default_rng(7)
    out = dict(window=[dates[0], dates[-1]], sessions=len(dates), bar_rows=nrows, split=mid, scale=SCALE,
               cell="NQ925/slip1", nshuf=NSHUF, frozen="research/zarattini@a93d2dfb", variants={})
    for tag, cut in (("1559", 960), ("1100", 660)):
        S2 = {D: {**S, **{k: S[k][S["tod"] < cut] for k in ("tod", "o", "h", "l", "c")}} for D, S in sess.items()}
        bk = Z.book({"NQ": S2}, {"NQ": pre}, "NQ925", 1)
        s = Z.summarize(bk, dates)
        D_ = sorted(bk); R = np.array([bk[D]["R"] for D in D_])
        h1 = R[[D < mid for D in D_]]; h2 = R[[D >= mid for D in D_]]
        both = np.array([[(Z.trade(S2[D], d, 1) or {"R": np.nan})["R"] for d in (1, -1)] for D in D_])
        pick = rng.integers(0, 2, (NSHUF, len(D_)))
        null = np.nanmean(both[np.arange(len(D_)), pick], axis=1)
        p = float((null >= R.mean()).mean())
        usd = [bk[D]["R"] * bk[D]["dist"] * MNQ_PT for D in D_]
        v = dict(n=len(R), R_trade=float(R.mean()), h1_n=len(h1), h1_R_trade=float(h1.mean()), h2_n=len(h2),
                 h2_R_trade=float(h2.mean()), h1_R_day=s["h1_R_day"], h2_R_day=s["h2_R_day"], p_shuffle=p,
                 p_signflip=s["p"], win=s["win"], usd_day_1mnq=float(sum(usd) / len(dates)), usd_total_1mnq=float(sum(usd)),
                 med_stop_pts=s["med_stop_pts"], exits=s["exits"], green=s["green"])
        ok = v["n"] >= 20 and v["R_trade"] >= 0.15 and v["h1_R_trade"] > 0 and v["h2_R_trade"] > 0 and p < 0.05
        v["verdict"] = "PASS" if ok else "FAIL"
        out["variants"][tag] = v
        json.dump({D: bk[D] for D in D_}, open(HERE / f"zarattini_proxy_oos_trades_{tag}.json", "w"), default=float)
        print(tag, json.dumps({k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items() if k != "exits"}), flush=True)
    out["verdict"] = (f"{out['variants']['1559']['verdict']} vs v3 sec2 bar (n>=20, R>=+0.15, both halves>0, p<.05) "
                      f"on primary 15:59 cell; 11:00 variant {out['variants']['1100']['verdict']}")
    json.dump(out, open(HERE / "zarattini_proxy_oos.json", "w"), indent=1, default=float)
    print("VERDICT", out["verdict"], flush=True)
    return out


if __name__ == "__main__":
    run()
