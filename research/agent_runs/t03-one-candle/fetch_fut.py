"""t03: fetch ES/NQ 1-min bars per quarterly contract from Massive, keep 08:00-11:05 ET.
Writes fut/<ROOT>_<CONTRACT>.csv.gz. Never prints the key."""
import json, time, urllib.request, urllib.error, sys, os
from pathlib import Path
import pandas as pd
HERE = Path(__file__).parent
OUT = HERE / "fut"; OUT.mkdir(exist_ok=True)
key = None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key = l.split("=", 1)[1].strip().strip('"')
EXP = {"Z4": "2024-12-20", "H5": "2025-03-21", "M5": "2025-06-20", "U5": "2025-09-19",
       "Z5": "2025-12-19", "H6": "2026-03-20", "M6": "2026-06-19", "U6": "2026-09-18", "Z6": "2026-12-18"}
roots = sys.argv[1:] or ["ES", "NQ"]
def get(url):
    for attempt in range(8):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("429, backoff", flush=True); time.sleep(65); continue
            raise RuntimeError(f"HTTP {e.code}: " + e.read().decode()[:200].replace(key, "***"))
        except Exception as e:
            print("err", type(e).__name__, flush=True); time.sleep(20)
    raise RuntimeError("gave up")
for root in roots:
    for code, exp in EXP.items():
        tk = root + code
        f = OUT / f"{tk}.csv.gz"
        if f.exists(): print("skip", tk); continue
        start = (pd.Timestamp(exp) - pd.Timedelta(days=100)).strftime("%Y-%m-%d")
        end = (pd.Timestamp(exp) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        url = (f"https://api.massive.com/futures/v1/aggs/{tk}?resolution=1min"
               f"&window_start.gte={start}&window_start.lt={end}&limit=50000&apiKey={key}")
        rows = []
        while url:
            d = get(url); res = d.get("results") or []
            rows += res
            nu = d.get("next_url")
            url = (nu + ("&" if "?" in nu else "?") + "apiKey=" + key) if nu else None
            print(tk, len(res), "total", len(rows), flush=True)
            time.sleep(13)
        if not rows:
            print(tk, "EMPTY"); pd.DataFrame().to_csv(f); continue
        df = pd.DataFrame(rows)
        df["ts"] = pd.to_datetime(df["window_start"], unit="ns", utc=True).dt.tz_convert("America/New_York")
        hm = df["ts"].dt.hour * 60 + df["ts"].dt.minute
        df = df[(hm >= 8 * 60) & (hm < 11 * 60 + 5)]
        df = df[["ts", "open", "high", "low", "close", "volume"]].sort_values("ts")
        df["ts"] = df["ts"].dt.strftime("%Y-%m-%d %H:%M")
        df.to_csv(f, index=False, compression="gzip")
        print("saved", tk, len(df), flush=True)
print("DONE")
