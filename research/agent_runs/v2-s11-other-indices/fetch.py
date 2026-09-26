# v2-s11: fetch YM/RTY 1-min (Massive futures v1) + one-day micro/e-mini liquidity snapshot. Key never printed.
import json, time, urllib.request, urllib.error, csv, sys
from pathlib import Path
OUT = Path(__file__).parent / "fut"; OUT.mkdir(exist_ok=True)
key = None
for l in Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\.env").read_text().splitlines():
    if l.startswith("POLYGON_API_KEY="): key = l.split("=", 1)[1].strip().strip('"')
def get(url):
    for i in range(6):
        u = url + ("&" if "?" in url else "?") + "apiKey=" + key
        try:
            with urllib.request.urlopen(u, timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:150].replace(key, "***")
            if e.code == 429: time.sleep(20); continue
            print("HTTP", e.code, msg, flush=True); return None
        except Exception as e:
            print("ERR", str(e)[:100], flush=True); time.sleep(10)
    return None
def pull(tk, gte, lt, fn):
    url = f"https://api.massive.com/futures/v1/aggs/{tk}?resolution=1min&window_start.gte={gte}&window_start.lt={lt}&limit=50000"
    rows = []; pages = 0
    while url:
        d = get(url); time.sleep(12.5); pages += 1
        if not d: break
        res = d.get("results") or []
        if pages == 1 and res: print(tk, "keys", list(res[0].keys()), flush=True)
        rows += res
        url = d.get("next_url")
    with open(OUT / fn, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ts_ns", "open", "high", "low", "close", "volume"])
        for r in rows:
            w.writerow([r.get("window_start"), r.get("open"), r.get("high"), r.get("low"), r.get("close"), r.get("volume")])
    print(tk, gte, lt, "rows", len(rows), "pages", pages, flush=True)
if sys.argv[1] == "snap":
    for tk in ["MYMZ6", "M2KZ6", "YMZ6", "RTYZ6", "MESZ6", "MNQZ6", "ESZ6", "NQZ6"]:
        pull(tk, "2026-09-24", "2026-09-25", f"snap_{tk}.csv")
else:
    for tk, gte, lt in [("YMU6","2026-05-29","2026-09-18"),("RTYU6","2026-05-29","2026-09-18"),
                        ("YMM6","2026-02-27","2026-06-19"),("RTYM6","2026-02-27","2026-06-19"),
                        ("YMH6","2025-11-28","2026-03-20"),("RTYH6","2025-11-28","2026-03-20"),
                        ("YMZ5","2025-08-29","2025-12-19"),("RTYZ5","2025-08-29","2025-12-19"),
                        ("YMZ6","2026-08-28","2026-09-26"),("RTYZ6","2026-08-28","2026-09-26")]:
        pull(tk, gte, lt, f"{tk}.csv")
print("DONE", flush=True)
