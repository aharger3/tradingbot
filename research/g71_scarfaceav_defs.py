"""G7.1 adversarial verify (track scarface): are T1's '0/34 silent' and
g71_scarface_recall's '107/200 silent' the same metric?

T1 (research/t1_entry_minute_autopsy.py:~110) calls a day SILENT only when
`not fired and not seen` -- no signal ANYWHERE, at any grade, incl. X-skips.
g71_scarface_recall.py:~34 calls a day silent when `entries` is empty -- no
FIRED entry. Different denominators of the same replay.

This scores BOTH definitions on BOTH sets. Read-only, writes only stdout+json.
"""
import json, os, sys
from collections import Counter
from pathlib import Path
ROOT = Path(r"C:\Users\aharg\Desktop\Projects\tradingbot")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research"))
from research.t4_engine_recall import run_day  # noqa: E402

def score(pairs, label):
    C = Counter(); rows = []
    for sym, day in pairs:
        try:
            entries, sigs, _raw = run_day(sym, day)
        except Exception as e:
            C["error"] += 1; rows.append((sym, day, "ERROR", type(e).__name__)); continue
        if entries is None:
            C["no_bars"] += 1; rows.append((sym, day, "NOBARS", "")); continue
        C["tested"] += 1
        f = bool(entries); s = bool(sigs)
        if f: C["fired_day"] += 1
        else: C["silent_scarface_def"] += 1
        if not f and not s: C["silent_t1_def"] += 1
        rows.append((sym, day, "FIRED" if f else ("SEEN_ONLY" if s else "SILENT_T1"),
                     "%d/%d" % (len(entries), len(sigs))))
    n = C["tested"]
    print("== %s ==  tested=%d  no_bars=%d  errors=%d" % (label, n, C["no_bars"], C["error"]))
    print("  fired-day (>=1 fired entry)      : %d  (%.1f%%)" % (C["fired_day"], 100*C["fired_day"]/max(1,n)))
    print("  SILENT by scarface def (no fire) : %d  (%.1f%%)" % (C["silent_scarface_def"], 100*C["silent_scarface_def"]/max(1,n)))
    print("  SILENT by T1 def (no signal ANY) : %d  (%.1f%%)" % (C["silent_t1_def"], 100*C["silent_t1_def"]/max(1,n)))
    return C, rows

# --- set A: Austin's 34 stated-minute S days (T1's own sample) -------------
MARKS = ROOT / "research/marks/probe_s_sweep_2026-08-28.jsonl"
sm = [json.loads(l) for l in open(MARKS, encoding="utf-8") if l.strip()]
sdays = sorted({(r["symbol"], r["date"]) for r in sm
                if r["answers"].get("s") == ["s"] and r["notes"].get("min")})
print("Austin S days with a stated minute: %d" % len(sdays))
CA, RA = score(sdays, "Austin S days (T1 sample)")

# --- set B: the Scarface T1+T2 in-universe days, same order/limit ----------
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 200
recs = [json.loads(l) for l in open(ROOT / "research/g71_scarface_candidates.jsonl", encoding="utf-8")]
cand = [r for r in recs if r["source"] == "Scarface" and r["in_backtest_universe"]
        and r["tier"] in ("T1", "T2")]
cand.sort(key=lambda r: r["day"])
cand = cand[:LIMIT]
CB, RB = score([(r["symbol"], r["day"]) for r in cand], "Scarface T1+T2 (n=%d)" % len(cand))

json.dump({"austin": dict(CA), "scarface": dict(CB),
           "austin_rows": RA, "scarface_rows": RB},
          open(ROOT / "research/_g71_scarfaceav_defs.json", "w"), indent=1)
