"""Databento GLBX.MDP3 ohlcv-1m pull for OMEN OOS (B1). Paper research only.

  python pull.py plan                 # list jobs (no key needed)
  python pull.py estimate             # free: metadata.get_cost per job, cumulative $, budget cut line
  python pull.py pull [--budget 120]  # downloads jobs in priority order until cumulative cost > budget
  python pull.py convert              # .dbn.zst -> t01 CSVs (mnq.py) + t02 json.gz bars (zarattini/bt.py)

Key: env DATABENTO_API_KEY (User env on the PC). Data lives OUTSIDE git in DB_ROOT.
Contracts are pulled by raw symbol (outright quarterlies only, no spreads): each root-year job asks for
H/M/U/Z of that year + H of the next year, which covers every front and roll date.
"""
import os, sys, json, gzip, glob, argparse
from pathlib import Path

DATASET, SCHEMA = "GLBX.MDP3", "ohlcv-1m"
DB_ROOT = Path(os.environ.get("DB_ROOT", r"C:\Users\aharg\Desktop\Projects\omen-data\databento"))
MONTHS = "HMUZ"
OOS_END = "2024-09-26"          # exclusive; IS (recovered bars) starts 2024-09-26
FIRST = {"NQ": "2010-06-06", "ES": "2010-06-06", "MNQ": "2019-05-05", "MES": "2019-05-05"}
# priority = order of pulling; the budget guard stops at the first job that would exceed it
PRIORITY = [("NQ", range(2019, 2025)), ("ES", range(2019, 2025)), ("NQ", range(2010, 2019)),
            ("ES", range(2010, 2019)), ("MNQ", range(2019, 2025)), ("MES", range(2019, 2025))]


def contracts(root, year):
    """[(raw_symbol, key)] for a job year. raw uses Databento/CME 1-digit year; key is decade-safe (NQH20)."""
    out = [(f"{root}{m}{year % 10}", f"{root}{m}{year % 100:02d}") for m in MONTHS]
    return out + [(f"{root}H{(year + 1) % 10}", f"{root}H{(year + 1) % 100:02d}")]


def jobs():
    J = []
    for root, years in PRIORITY:
        for y in years:
            start = max(f"{y}-01-01", FIRST[root])
            end = min(f"{y + 1}-01-01", OOS_END)
            if start >= end: continue
            J.append(dict(name=f"{root}_{y}", root=root, year=y, start=start, end=end, contracts=contracts(root, y)))
    return J


def _client():
    import databento as db
    return db.Historical(os.environ["DATABENTO_API_KEY"])


def _req(j):
    return dict(dataset=DATASET, schema=SCHEMA, stype_in="raw_symbol",
                symbols=[s for s, _ in j["contracts"]], start=j["start"], end=j["end"])


def estimate(budget):
    c = _client(); cum = 0.0; rows = []
    for j in jobs():
        cost = float(c.metadata.get_cost(**_req(j))); size = int(c.metadata.get_billable_size(**_req(j)))
        cum += cost; rows.append(dict(job=j["name"], usd=round(cost, 4), mb=round(size / 1e6, 1), cum=round(cum, 2), fits=cum <= budget))
        print(f'{j["name"]:10s} ${cost:8.4f} {size / 1e6:8.1f} MB  cum ${cum:8.2f} {"ok" if cum <= budget else "OVER"}', flush=True)
    DB_ROOT.mkdir(parents=True, exist_ok=True)
    json.dump(dict(budget=budget, total=cum, rows=rows), open(DB_ROOT / "estimate.json", "w"), indent=1)
    return cum


def pull(budget):
    c = _client(); cum = 0.0; raw = DB_ROOT / "raw"; raw.mkdir(parents=True, exist_ok=True)
    for j in jobs():
        f = raw / f'{j["name"]}.dbn.zst'
        if f.exists(): print("have", f.name); continue
        cost = float(c.metadata.get_cost(**_req(j)))
        if cum + cost > budget:
            print(f'STOP at {j["name"]}: cum ${cum:.2f} + ${cost:.2f} > budget ${budget}', flush=True); break
        c.timeseries.get_range(**_req(j), path=str(f)); cum += cost
        json.dump(j, open(raw / f'{j["name"]}.job.json', "w"))
        print(f'got {j["name"]} ${cost:.4f} cum ${cum:.2f}', flush=True)


def to_rows(df, contract_map):
    """Databento ohlcv df -> {key: [(ts_ns, o, h, l, c, v)]}. ts = bar OPEN time in UTC ns (same as recovered t01 files)."""
    import pandas as pd
    out = {}
    if df.empty: return out
    ts = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True)).asi8 if not isinstance(df.index, pd.RangeIndex) \
        else pd.to_datetime(df["ts_event"], utc=True).astype("int64").to_numpy()
    for sym, key in contract_map.items():
        m = (df["symbol"] == sym).to_numpy()
        if not m.any(): continue
        d = df[m]
        out[key] = list(zip(ts[m].tolist(), d["open"].astype(float), d["high"].astype(float),
                            d["low"].astype(float), d["close"].astype(float), d["volume"].astype(int)))
    return out


def write(rowsets, out_root):
    """Merge rows per contract key and write both loader formats. Returns {key: n_rows}."""
    fut = out_root / "t01-orb5" / "fut"; bars = out_root / "bars"; fut.mkdir(parents=True, exist_ok=True); bars.mkdir(parents=True, exist_ok=True)
    merged = {}
    for rs in rowsets:
        for k, r in rs.items(): merged.setdefault(k, {}).update({row[0]: row for row in r})
    counts = {}
    for k, d in merged.items():
        rows = [d[t] for t in sorted(d)]
        yr = 2000 + int(k[-2:])
        with open(fut / f"{k}_{yr}.csv", "w", newline="") as fh:
            fh.write("ts_ns,open,high,low,close,volume\n")
            fh.writelines(f"{t},{o},{h},{l},{c},{v}\n" for t, o, h, l, c, v in rows)
        root = k[:-3]
        with gzip.open(bars / f"{root}_{k}.json.gz", "wt") as fh:
            json.dump(dict(ticker=k, rows=[list(r) for r in rows]), fh)
        counts[k] = len(rows)
    return counts


def convert():
    import databento as db
    sets = []
    for f in sorted((DB_ROOT / "raw").glob("*.dbn.zst")):
        j = json.load(open(str(f).replace(".dbn.zst", ".job.json")))
        df = db.DBNStore.from_file(str(f)).to_df()
        sets.append(to_rows(df, {s: k for s, k in j["contracts"]}))
    counts = write(sets, DB_ROOT)
    json.dump(counts, open(DB_ROOT / "convert.json", "w"), indent=1)
    print(len(counts), "contracts,", sum(counts.values()), "rows ->", DB_ROOT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["plan", "estimate", "pull", "convert"])
    ap.add_argument("--budget", type=float, default=120.0); a = ap.parse_args()
    if a.cmd == "plan":
        for j in jobs(): print(j["name"], j["start"], j["end"], [s for s, _ in j["contracts"]])
    elif a.cmd == "estimate": estimate(a.budget)
    elif a.cmd == "pull": pull(a.budget)
    else: convert()
