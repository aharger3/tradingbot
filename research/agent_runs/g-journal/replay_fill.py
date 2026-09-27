"""Integration: run the REAL eye_runner over N past Mon-Thu sessions with
ntfy stubbed (no pushes) and a synthetic tap policy (tap S iff engine grade S,
else not_s, instantly). Fills a scratch journal.db and writes weekly reviews.
Research-only driver; not committed."""
import csv, sys, json
from datetime import datetime, timezone
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
PROD = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot\research\agent_runs")
for sub in ("v2-s07-data", "v2-t01-orb-1m"):
    sys.path.append(str(PROD / sub))  # untracked in git; read-only use of prod copies
import eye_runner
OUT = REPO / "research" / "agent_runs" / "g-journal"
OUT.mkdir(parents=True, exist_ok=True)
DB = OUT / "journal.db"; LAB = OUT / "labels.csv"; ACKS = OUT / "acks_gjournal.jsonl"
for p in (DB, LAB, ACKS):
    if p.exists(): p.unlink()
with open(LAB, "w", newline="") as f:
    csv.writer(f).writerow(["logged_at", "candidate_id", "label", "mode", "source_ip"])

class R:  ok = True; status_code = 0
def fake_send(chart_cand, png, token, test_title_prefix=None):
    lab = "S" if chart_cand.candidate_id.startswith("S") else "NOT_S"
    with open(LAB, "a", newline="") as f:
        csv.writer(f).writerow([datetime.now(timezone.utc).isoformat(), chart_cand.candidate_id, lab, "REPLAY", "stub"])
    return R()
eye_runner.send_card = fake_send
eye_runner.CHART_DIR = OUT / "charts"

import candidates as eye2
from omen_data import load_fut
df = load_fut("MNQ", "09:30", "11:01")
eye_runner.load_fut = lambda *a, **k: df  # cache: one CSV load for all sessions
dates = sorted({str(d) for d in df["date"]})
mt = [d for d in dates if datetime.fromisoformat(d).weekday() <= 3]
n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
for d in mt[-n:]:
    eye_runner.main(["--date", d, "--speed", "1000000", "--title-prefix", "G-JOURNAL STUB",
                     "--journal-path", str(ACKS), "--labels-csv", str(LAB), "--journal-db", str(DB),
                     "--max-wall-minutes", "3"])
from trade_journal.journal import connect
from trade_journal.review import write_review, perm_p_diff, signflip_p
con = connect(DB)
rows = [dict(r) for r in con.execute("SELECT * FROM trades ORDER BY session_date")]
weeks = sorted({r["iso_week"] for r in rows})
for w in weeks: write_review(w, "PAPER", DB, OUT / "reviews")
tk = [r["r"] for r in rows if r["taken"]]
ps = [r["shadow_r"] for r in rows if not r["taken"] and r["shadow_r"] is not None]
shots = sum(1 for r in rows if r["screenshot"])
from statistics import mean
print(json.dumps({"sessions": len(mt[-n:]), "first": mt[-n], "last": mt[-1], "cards": len(rows), "shots": shots,
  "taken_n": len(tk), "taken_mean": round(mean(tk), 3) if tk else None,
  "taken_sum": round(sum(tk), 2), "signflip_p": signflip_p(tk) if tk else None,
  "passed_n": len(ps), "passed_mean": round(mean(ps), 3) if ps else None,
  "eye": round(mean(tk) - mean(ps), 3) if tk and ps else None, "perm_p": perm_p_diff(tk, ps) if tk and ps else None,
  "weeks": weeks, "grades": {g: sum(1 for r in rows if r["engine_grade"] == g) for g in ("S", "one-off", "two-off")}}))
