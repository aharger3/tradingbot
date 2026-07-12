"""Align extracted review trades to Polygon: resolve the year by matching the
stated entry price to the actual day's [low,high] (double-duty — validates the
level AND dates the trade), then scan forward from the level touch for 2R
target vs stop = a NON-survivorship outcome (review's claimed outcome ignored).

Entry time isn't in the reviews, so entry = first RTH bar that touches the
stated level. Approximation adds noise but removes the win-only curation bias.
Run: python align_reviews.py
"""
import json
from datetime import date
from calendar import month_name

import polygon_feed as pf

MONTHS = {m.lower(): i for i, m in enumerate(month_name) if m}
YEARS = [2025, 2024, 2023, 2022]
SKIP = {"SPX", "ES", "NQ", "MNQ", "MES", "RTY", "YM"}  # not on Polygon equity API


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


def resolve_and_score(r):
    tkr = r.get("ticker")
    if tkr in SKIP or not isinstance(r.get("entry_level"), (int, float)) \
            or not isinstance(r.get("stop_level"), (int, float)):
        return None
    md = parse_md(r.get("date_str"))
    if not md:
        return None
    entry, stop = r["entry_level"], r["stop_level"]
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
        if not (lo <= entry <= hi):
            continue  # price never near stated level this year -> wrong year
        # entry = first bar touching the level; forward scan 2R vs stop
        touch = next((i for i, b in enumerate(bars) if b.low <= entry <= b.high), None)
        if touch is None:
            continue
        risk = abs(entry - stop)
        if risk < 0.01:
            return {"date": d, "outcome": "bad_stop"}
        target = entry + 2 * risk if long else entry - 2 * risk
        outcome = "open"
        for b in bars[touch:]:
            hit_stop = (b.low <= stop) if long else (b.high >= stop)
            hit_tgt = (b.high >= target) if long else (b.low <= target)
            if hit_stop:  # conservative: stop wins ties
                outcome = "loss"; break
            if hit_tgt:
                outcome = "win"; break
        return {"date": d, "entry": entry, "stop": stop, "target": round(target, 2),
                "outcome": outcome, "claimed": r.get("outcome")}
    return None  # no year matched -> level implausible, extraction likely bad


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
    wins = sum(1 for a in scored if a["outcome"] == "win")
    agree = sum(1 for a in scored if a["outcome"] == a.get("claimed"))
    print(f"resolved (year matched + validated): {resolved}")
    print(f"scored win/loss: {len(scored)}  ({wins}W/{len(scored)-wins}L = "
          f"{wins/max(1,len(scored))*100:.0f}% real forward-scan win rate)")
    print(f"agreement with review's claimed outcome: {agree}/{len(scored)}"
          f" ({agree/max(1,len(scored))*100:.0f}%) — gap = survivorship + entry-timing noise")
    json.dump(aligned, open("reviews_aligned.json", "w"), indent=1)
    print("wrote reviews_aligned.json")
    print("--- sample ---")
    for a in scored[:12]:
        flag = "" if a["outcome"] == a.get("claimed") else "  <-DIFFERS"
        print(f"  {a['date']} {a['ticker']:5s} {a['direction']:5s} "
              f"real={a['outcome']:4s} claimed={str(a.get('claimed')):4s}{flag}")


if __name__ == "__main__":
    run()
