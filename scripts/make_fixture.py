import datetime
import pandas as pd

SRC = r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs\t01-orb5\fut\NQZ5_2025.csv"
OUT = r"C:\Users\aharg\Desktop\Projects\tradingbot-eye3\eye_card\tests\fixtures\replay_nq_2025.csv"

df = pd.read_csv(SRC)
df["ts"] = pd.to_datetime(df.ts_ns, unit="ns", utc=True).dt.tz_convert("America/New_York")
df["date"] = df.ts.dt.date
df["tod"] = df.ts.dt.strftime("%H:%M:%S")

counts = df.groupby("date").size()
cands = [d for d in counts.index if d.weekday() in (0, 1, 2, 3) and counts[d] > 1000]
pick = cands[len(cands) // 2]
day = df[df.date == pick]
window = day[(day.tod >= "09:30:00") & (day.tod <= "11:00:00")]
window = window[["tod", "open", "high", "low", "close", "volume"]].rename(columns={"tod": "time"})
window.to_csv(OUT, index=False)
print("picked", pick, "rows", len(window))
print(window.head(20).to_string())
