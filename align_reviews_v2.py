"""Align review trades using the REAL entry logic, not first-touch.

v1 entered at the first bar that touched the level -> measured "blindly buy
every level touch", which the methodology says never do (23% win, garbage).

v2 runs the actual BreakAndRetestDetector state machine per day:
  wait_break  -> price closes through the level (with the prev bar on the
                 other side)  [detect_breakout]
  wait_retest -> price comes back, touches the level, closes back through it
                 WITH strong price action / hammer  [detect_retest_entry]
  enter       -> entry = that bar's close; forward-scan 2R target vs stop.

Days where break->retest->hold never forms = no_entry (NOT counted W/L). That
is the point: the edge is the confirmation filter, so we only score trades the
real system would actually take.

Year still resolved by level-in-day-range (validates level + dates trade).
Run: python align_reviews_v2.py
"""
import json
from datetime import date
from calendar import month_name

import polygon_feed as pf
from omen_bot import BreakAndRetestDetector as BR

MONTHS = {m.lower(): i for i, m in enumerate(month_name) if m}
YEARS = [2025, 2024, 2023, 2022]
SKIP = {"SPX", "ES", "NQ", "MNQ", "MES", "RTY", "YM"}


def parse_md(date_str):
    if not date_str:
        return None
    parts = date_str.replace(",", "").split()
    mo = da = None
    for p in parts:
        if p.lower() in MONTHS:
            mo = MONTHS[p.lower()]
        elif p.rstrip("stndrh").isdigit():
            da = int(p.rstrip("stndrh"))
    return (mo, da) if mo and da else None


def score_day(bars, lvl, stop, long):
    """Run break->retest->hold state machine. Return outcome + entry, or no_entry."""
    state, broke = "wait_break", None
    for i in range(1, len(bars)):
        win = bars[: i + 1]
        if state == "wait_break":
            bc = BR.detect_breakout(win, lvl, lvl, long)
            if bc:
                broke, state = bc, "wait_retest"
        elif state == "wait_retest":
            ok, _ = BR.detect_retest_entry(win, broke, lvl, lvl, long)
            if ok:
                entry = bars[i].close
                risk = abs(entry - stop)
                if risk < 0.01:
                    return {"outcome": "bad_stop"}
                target = entry + 2 * risk if long else entry - 2 * risk
                outcome = "open"  # ran out of day = no 2R and no stop
                for b in bars[i:]:
                    hit_stop = (b.low <= stop) if long else (b.high >= stop)
                    hit_tgt = (b.high >= target) if long else (b.low <= target)
                    if hit_stop:  # conservative: stop wins ties
                        outcome = "loss"; break
                    if hit_tgt:
                        outcome = "win"; break
                return {"outcome": outcome, "entry": round(entry, 2),
                        "target": round(target, 2)}
    return {"outcome": "no_entry"}


def resolve_and_score(r):
    tkr = r.get("ticker")
    if tkr in SKIP or not isinstance(r.get("entry_level"), (int, float)) \
            or not isinstance(r.get("stop_level"), (int, float)):
        return None
    md = parse_md(r.get("date_str"))
    if not md:
        return None
    lvl, stop = r["entry_level"], r["stop_level"]
    long = r.get("direction") == "long"
    for yr in YEARS:
        try:
            d = date(yr, md[0], md[1]).isoformat()
        except ValueError:
            continue
        try:
            bars = pf.rth(pf.fetch_day(tkr, d))
        except Exception:
            continue
        if not bars:
            continue
        lo, hi = min(b.low for b in bars), max(b.high for b in bars)
        if not (lo <= lvl <= hi):
            continue  # wrong year
        res = score_day(bars, lvl, stop, long)
        res.update(date=d, claimed=r.get("outcome"))
        return res
    return None


def run():
    recs = json.load(open("reviews_extracted.json", encoding="utf-8"))
    aligned, resolved = [], 0
    for r in recs:
        res = resolve_and_score(r)
        if res is None:
            continue
        resolved += 1
        res.update(ticker=r.get("ticker"), direction=r.get("direction"),
                   setup=r.get("setup"))
        aligned.append(res)

    scored = [a for a in aligned if a["outcome"] in ("win", "loss")]
    no_entry = sum(1 for a in aligned if a["outcome"] == "no_entry")
    wins = sum(1 for a in scored if a["outcome"] == "win")
    agree = sum(1 for a in scored if a["outcome"] == a.get("claimed"))
    print(f"resolved (year matched): {resolved}")
    print(f"no_entry (break->retest->hold never formed): {no_entry}  "
          f"<- real system would skip these")
    n = max(1, len(scored))
    print(f"scored win/loss: {len(scored)}  ({wins}W/{len(scored)-wins}L = "
          f"{wins/n*100:.0f}% REAL win rate with confirmation entry)")
    print(f"agreement with claimed: {agree}/{len(scored)} ({agree/n*100:.0f}%)")
    json.dump(aligned, open("reviews_aligned_v2.json", "w"), indent=1)
    print("wrote reviews_aligned_v2.json")
    print("--- scored sample ---")
    for a in scored[:15]:
        mark = "" if a["outcome"] == a.get("claimed") else "  <-DIFFERS"
        print(f"  {a['date']} {a['ticker']:5s} {a['direction']:5s} "
              f"real={a['outcome']:4s} claimed={str(a.get('claimed')):4s}{mark}")


if __name__ == "__main__":
    run()
