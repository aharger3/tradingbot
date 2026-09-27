# v2-t10: extend YM/RTY 1-min back to 2024-09 (reuses s11 fetch.py pull()). Key never printed.
import sys, runpy
from pathlib import Path
S11 = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\v2-s11-other-indices")
sys.argv = ["fetch.py", "snap_none"]
src = (S11 / "fetch.py").read_text()
src = src.split('if sys.argv[1] == "snap":')[0]
g = {"__file__": str(S11 / "fetch.py")}
exec(compile(src, "fetch_s11", "exec"), g)
for tk, gte, lt in [("YMU5","2025-05-30","2025-09-19"),("RTYU5","2025-05-30","2025-09-19"),
                    ("YMM5","2025-02-28","2025-06-20"),("RTYM5","2025-02-28","2025-06-20"),
                    ("YMH5","2024-11-29","2025-03-21"),("RTYH5","2024-11-29","2025-03-21"),
                    ("YMZ4","2024-09-20","2024-12-20"),("RTYZ4","2024-09-20","2024-12-20")]:
    g["pull"](tk, gte, lt, f"{tk}.csv")
print("DONE2", flush=True)
