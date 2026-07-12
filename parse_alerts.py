"""Parse jdub-alerts / futures-alerts Discord channels into labeled trades.

Each entry alert -> {ticker, direction, stop_level, ts_et, premium}. Stock
entry = Polygon price at alert time (premium alerts don't state a stock entry).
Outcome = scan forward: 2R target vs stop_level, whichever hits first.

This is the supervised label source: the pros' real entries, scored on real
price. Regex + price lookup, no LLM. Run: python parse_alerts.py [--align N]
"""
import json, re, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import polygon_feed as pf

UTC, ET = ZoneInfo("UTC"), ZoneInfo("America/New_York")

# Known underlyings Jdub/Scarface trade + index futures. Filters out chatter
# tokens (PDH, ATH, BE, LOD...) that also look like tickers.
TICKERS = {
    "SPY","QQQ","IWM","DIA","AAPL","TSLA","NVDA","AMD","AMZN","META","MSFT",
    "GOOGL","GOOG","NFLX","COIN","HOOD","PLTR","SMCI","MSTR","AVGO","MU",
    "BABA","SHOP","CRM","UBER","DIS","BA","INTC","GME","SOFI","RIVN","LCID",
}
FUTURES = {"NQ","ES","MNQ","MES","RTY","YM","CL","GC","MCL","MGC"}
FUT_UNDERLYING = {"NQ":"QQQ","MNQ":"QQQ","ES":"SPY","MES":"SPY","RTY":"IWM","YM":"DIA"}

STOP_RE = re.compile(r"stop\s+(?:above|below|at|under|over)?\s*\$?(\d+(?:\.\d+)?)", re.I)
PREM_RE = re.compile(r"@\s*\$?(\d+(?:\.\d+)?)")
NUM_RE  = re.compile(r"\b(\d{2,6}(?:\.\d+)?)\b")


def _dir(text: str):
    t = text.lower()
    if "puts" in t or re.search(r"\bshort\b", t):
        return "short"
    if "calls" in t or re.search(r"\b(long|bought|buying)\b", t):
        return "long"
    return None


def _ticker(text: str):
    for tok in re.findall(r"\b[A-Z]{1,5}\b", text):
        if tok in TICKERS:
            return tok, tok
        if tok in FUTURES:
            return tok, FUT_UNDERLYING.get(tok, tok)
    return None, None


def parse_channel(path: str):
    msgs = json.load(open(path, encoding="utf-8"))
    if isinstance(msgs, dict):
        msgs = msgs.get("messages", [])
    out = []
    for m in msgs:
        c = (m.get("content") or "").strip()
        if not c:
            continue
        direction = _dir(c)
        raw_tkr, underlying = _ticker(c)
        if not direction or not underlying:
            continue  # chatter / update, not an entry
        stop_m = STOP_RE.search(c)
        prem_m = PREM_RE.search(c)
        ts = m.get("ts")
        try:
            ts_et = datetime.fromisoformat(ts).replace(tzinfo=UTC).astimezone(ET)
        except Exception:
            ts_et = None
        out.append({
            "ts_utc": ts, "ts_et": ts_et.isoformat() if ts_et else None,
            "date": ts_et.date().isoformat() if ts_et else None,
            "hhmm": ts_et.strftime("%H:%M") if ts_et else None,
            "ticker": raw_tkr, "underlying": underlying, "direction": direction,
            "is_future": raw_tkr in FUTURES,
            "stop_level": float(stop_m.group(1)) if stop_m else None,
            "premium": float(prem_m.group(1)) if prem_m else None,
            "text": c[:200],
        })
    return out


def align(rec: dict):
    """Attach stock entry (price at alert), 2R target, outcome from Polygon.
    Only for equity/ETF underlyings with a numeric stop and RTH timestamp."""
    if rec["is_future"] or rec["stop_level"] is None or not rec["date"]:
        return None
    try:
        bars = pf.rth(pf.fetch_day(rec["underlying"], rec["date"]))
    except Exception as e:
        return {"outcome": f"fetch_err:{e}"}
    if not bars:
        return {"outcome": "no_data"}
    hhmm = rec["hhmm"]
    fwd = [b for b in bars if b.timestamp[:5] >= hhmm]
    if not fwd:
        return {"outcome": "after_hours"}
    entry = fwd[0].open
    stop = rec["stop_level"]
    risk = abs(entry - stop)
    if risk < 0.01:
        return {"outcome": "bad_stop"}
    long = rec["direction"] == "long"
    target = entry + 2 * risk if long else entry - 2 * risk
    outcome = "open"
    for b in fwd:
        hit_stop = b.high >= stop if not long else b.low <= stop
        hit_tgt = b.high >= target if long else b.low <= target
        if hit_stop and hit_tgt:  # same bar, assume stop first (conservative)
            outcome = "loss"; break
        if hit_stop:
            outcome = "loss"; break
        if hit_tgt:
            outcome = "win"; break
    return {"entry": round(entry, 2), "stop": stop, "target": round(target, 2),
            "risk": round(risk, 2), "outcome": outcome}


if __name__ == "__main__":
    files = ["discord_data/jdub-alerts.json", "discord_data/futures-alerts.json"]
    allrecs = []
    for f in files:
        if Path(f).exists():
            recs = parse_channel(f)
            allrecs += recs
            eq = sum(1 for r in recs if not r["is_future"])
            withstop = sum(1 for r in recs if r["stop_level"] is not None)
            print(f"{f}: {len(recs)} entries parsed ({eq} equity, {withstop} w/ numeric stop)")
    print(f"TOTAL entries: {len(allrecs)}")
    Path("labeled_alerts.json").write_text(json.dumps(allrecs, indent=1))
    print("wrote labeled_alerts.json (parsed, unaligned)")

    n = 0
    if "--align" in sys.argv:
        n = int(sys.argv[sys.argv.index("--align") + 1])
    if n:
        print(f"\n--- aligning {n} equity alerts to Polygon ---")
        aligned = []
        for r in allrecs:
            if r["is_future"] or r["stop_level"] is None:
                continue
            a = align(r)
            if a and a.get("outcome") in ("win", "loss"):
                aligned.append((r, a))
                print(f"  {r['date']} {r['hhmm']} {r['ticker']:5s} {r['direction']:5s} "
                      f"entry {a['entry']} stop {a['stop']} tgt {a['target']} -> {a['outcome']}")
            if len(aligned) >= n:
                break
        wins = sum(1 for _, a in aligned if a["outcome"] == "win")
        if aligned:
            print(f"sample: {wins}/{len(aligned)} win = {wins/len(aligned)*100:.0f}%")
