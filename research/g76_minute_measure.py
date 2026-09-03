"""g76_minute_measure.py -- the engine measured AT THE MINUTE, not at the day.

DIRECTION.md line 43 says the engine is "never silent" on Austin's S days and its
timing is "exact (median +0.0 bars)". Both sentences are true of the DAY and false
of the MINUTE, and they were computed two different ways:

  * "never silent"  = the engine produced at least one signal SOMEWHERE in the
                      09:30-11:00 window on that symbol-day.
  * "median +0.0"   = conditioned on the days where it already landed on his
                      minute. The 19 days it did not reach were dropped BEFORE
                      the median was taken.

This script re-measures both on two samples, with nothing conditioned away:

  sample A  research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl (30)
  sample B  research/marks/probe_s_sweep_2026-08-28.jsonl                  (100)

Both mark files are opened READ-ONLY. Nothing here touches engine code, the book,
or any judgement file. The engine is replayed live, bar by bar, through
research/t4_engine_recall.run_day -- the same rig T1 used -- so this is a
like-for-like correction, not a different measuring stick.

Writes ONE file: research/g76_minute_measure.json

    python research/g76_minute_measure.py
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from research.t4_engine_recall import run_day  # noqa: E402

MARKS_A = os.path.join(HERE, "marks",
                       "probe_g71_homework_s3_2026-08-29_complete.jsonl")
MARKS_B = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g76_minute_measure.json")

# Two bars either side. He types 9:41 for a candle he watched form from 9:40 and
# the engine stamps the bar it closed on. T1 used the same window; keeping it
# identical is the point.
NEAR = 2
BANDS = (0, 1, 2, 5)

CLOCK = re.compile(r"\b(\d{1,2}):([0-5]\d)\b")
# Anything that LOOKS like a time but is not one. "9:%5" is a typo. It is
# recorded as unparseable and never guessed -- guessing would invent a mark.
CLOCKISH = re.compile(r"\b\d{1,2}\s*[:;]\s*\S{0,3}")


# --------------------------------------------------------------- time intent
#
# A clock time inside a note is not automatically "the minute I would enter".
# Every one of the 26 clock tokens in sample A is classified here BY HAND with
# the sentence it came from, so the classification is auditable rather than
# implied. Three kinds:
#
#   entry      the minute he would have taken
#   candidate  a minute he evaluated and then rejected -- still his read of
#              where the setup was, so still usable for "was the engine there"
#   narration  a minute that is about something else on the chart entirely
#
INTENT = {
    "BABA_2024-09-05":  ("entry", '"9:56"'),
    "NFLX_2026-05-26":  ("entry", '"9:47 OCR stop green candle wick"'),
    "NVDA_2026-05-11":  ("entry", '"9:43"'),
    "NFLX_2025-07-08":  ("entry", '"9:38"'),
    "COIN_2025-07-10":  ("entry", '"9:41"'),
    "TSLA_2025-09-03":  ("entry", '"9:45"'),
    "AMD_2024-10-02":   ("entry", '"9:36 and 84 percent rule happens yes"'),
    "MSFT_2024-09-13":  ("narration",
                         '"9:47 is what you liked but it broke above those '
                         'levels and rejected them" -- the minute is the '
                         "ENGINE'S, quoted back. Not his entry."),
    "MSFT_2025-08-29":  ("entry", '"...9:38 is the entry"'),
    "GOOGL_2024-10-29": ("entry", '"10:47"'),
    "AAPL_2026-04-17":  ("entry", '"9:42"'),
    "TSM_2025-11-26":   ("narration",
                         '"hard to get past the green candle at 9:35" -- he is '
                         "naming an obstacle, not an entry"),
    "SPY_2025-05-21":   ("entry", '"9:45 BR OCR confluence"'),
    "INTC_2026-03-24":  ("entry", '"entry at 9:38 and then a 84 reclaim"'),
    "AVGO_2024-11-04":  ("entry", '"9:47"'),
    "AMD_2025-09-08":   ("candidate",
                         '"10:37 but really no displacement ... so i have to '
                         'downgrade" -- his read of where it was, then a no'),
    "IWM_2026-08-06":   ("unparseable", '"9:%5" -- a typo. Never guessed.'),
    "TSM_2026-07-07":   ("entry", '"9:38 and yes reclaim"'),
    "AMZN_2025-12-11":  ("entry", '"9:40"'),
    "ACHR_2026-06-16":  ("entry", '"9:57 as candle forming"'),
    "SPY_2026-06-17":   ("entry",
                         '"i see a fake out S trade at 9:48 ... and if you went '
                         'with my trade it wouldve stopped out and reclaimed"'),
    "ACHR_2026-04-13":  ("entry_not_tradeable",
                         '"10:09 would never trade because look how the candles '
                         'are but jsut good for you to know" -- the minute is '
                         "his, the TRADE is not"),
    "META_2026-06-22":  ("entry", '"9:59"'),
    "QQQ_2024-08-26":   ("entry",
                         '"9:56 but i may be biased here because a break retest '
                         'with no dispacement happens at 9:45" -- 9:56 is the '
                         "entry, 9:45 is narration of another candle"),
    "QQQ_2025-12-22":   ("candidate", '"9:45 its close i see what your seeing"'),
    "AVGO_2025-12-03":  ("candidate",
                         '"9:33 can be a great break of pdl but the retest '
                         'missed by a few cents"'),
}


def mins(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def hhmm(v) -> str:
    return None if v is None else "%d:%02d" % (v // 60, v % 60)


def bar_min(ts: str) -> int:
    t = ts[11:16] if "T" in ts else ts[:5]
    return mins(t)


def note_blob(rec: dict) -> str:
    n = rec.get("notes") or {}
    return " | ".join(str(v) for v in n.values() if v)


def his_minutes(blob: str):
    """Every well-formed clock time, in the order he typed it, plus the tokens
    that look like a time and are not."""
    good = [mins("%s:%s" % (h, m)) for h, m in CLOCK.findall(blob)]
    bad = [t for t in CLOCKISH.findall(blob) if not CLOCK.search(t)]
    return good, bad


def dist(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"n": len(vals), "median": statistics.median(vals),
            "mean": round(statistics.fmean(vals), 2),
            "min": min(vals), "max": max(vals),
            "within_2": sum(1 for v in vals if abs(v) <= 2)}


# ------------------------------------------------------------------ the engine

_CACHE = {}


def signals_for(symbol: str, day: str):
    """Every raw signal the engine emits on that symbol-day, undeduped. Raw is
    the honest denominator for 'was it silent here' -- dedupe can hide a signal
    that exists."""
    k = (symbol, day)
    if k not in _CACHE:
        entries, all_sigs, raw = run_day(symbol, day)
        _CACHE[k] = (entries, all_sigs, raw)
    return _CACHE[k]


def verdict_at(symbol, day, his, band=NEAR):
    """What is the engine doing at his minute, +/- band bars?

      no_bars   the archive has no candles -- the engine could not run at all
      SILENT    zero signals of any kind inside the band
      DETECTED  a signal exists but nothing with status 'fired'
      FIRED     it took an entry there
    """
    entries, all_sigs, raw = signals_for(symbol, day)
    if raw is None:
        return {"verdict": "no_bars"}
    near = [s for s in raw if abs(bar_min(s["timestamp"]) - his) <= band]
    fired = [s for s in near if s["status"] == "fired"]
    day_mins = sorted({bar_min(s["timestamp"]) for s in raw})
    fired_mins = sorted({bar_min(s["timestamp"]) for s in raw
                         if s["status"] == "fired"})
    nearest = min(day_mins, key=lambda t: abs(t - his)) if day_mins else None
    nearest_f = (min(fired_mins, key=lambda t: abs(t - his))
                 if fired_mins else None)
    if fired:
        v = "FIRED"
    elif near:
        v = "DETECTED"
    else:
        v = "SILENT"
    return {
        "verdict": v,
        "n_signals_in_band": len(near),
        "grades_in_band": sorted({s["grade"] for s in near}),
        "setups_in_band": sorted({s["signal_type"] for s in near}),
        "n_signals_that_day": len(raw),
        "engine_active_that_day": len(raw) > 0,
        "engine_first_et": hhmm(day_mins[0]) if day_mins else None,
        "engine_last_et": hhmm(day_mins[-1]) if day_mins else None,
        "nearest_any_et": hhmm(nearest),
        "offset_nearest_any": (nearest - his) if nearest is not None else None,
        "nearest_fired_et": hhmm(nearest_f),
        "offset_nearest_fired": (nearest_f - his) if nearest_f is not None else None,
        "took_any_trade_that_day": bool(fired_mins),
    }


# ------------------------------------------------------------------- sample A

def load_a():
    rows = []
    for line in open(MARKS_A, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        blob = note_blob(r)
        good, bad = his_minutes(blob)
        intent, quote = INTENT.get(r["card_id"], ("unclassified", ""))
        rows.append({
            "card_id": r["card_id"], "symbol": r["symbol"], "date": r["date"],
            "bucket": r.get("bucket"), "claimed_setup": r.get("claimed_setup"),
            "is_s": (r.get("answers", {}).get("is_s") or [None])[0] == "yes",
            "why_not": r.get("answers", {}).get("why_not") or [],
            "note": blob,
            "his_times": [hhmm(t) for t in good],
            "his_minute": good[0] if good else None,
            "unparseable_tokens": bad,
            "time_intent": intent, "intent_quote": quote,
        })
    return rows


def load_b():
    rows = []
    for line in open(MARKS_B, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        ans = (r.get("answers", {}).get("s") or [None])[0]
        blob = note_blob(r)
        good, bad = his_minutes(blob)
        rows.append({
            "card_id": r["card_id"], "symbol": r["symbol"], "date": r["date"],
            "is_s": ans == "s", "note": blob,
            "his_minute": good[0] if good else None,
            "unparseable_tokens": bad,
        })
    return rows


def measure(rows, label, only_s=False):
    out = []
    for r in rows:
        if only_s and not r["is_s"]:
            continue
        if r["his_minute"] is None:
            out.append(dict(r, verdict="no_minute_given"))
            continue
        v = verdict_at(r["symbol"], r["date"], r["his_minute"])
        rec = dict(r)
        rec.update(v)
        # the band sweep -- does the answer depend on the tolerance?
        rec["bands"] = {}
        for b in BANDS:
            rec["bands"][str(b)] = verdict_at(
                r["symbol"], r["date"], r["his_minute"], band=b)["verdict"]
        out.append(rec)
        print("  %-18s %-6s his %-5s -> %-9s  nearest %-5s (%+d)  day %d sigs"
              % (r["card_id"], "S" if r["is_s"] else "no",
                 hhmm(r["his_minute"]), rec["verdict"],
                 rec.get("nearest_any_et"), rec.get("offset_nearest_any") or 0,
                 rec.get("n_signals_that_day") or 0), flush=True)
    return out


def summarise(rows, label):
    have = [r for r in rows if r.get("verdict") in
            ("SILENT", "DETECTED", "FIRED", "no_bars")]
    c = {v: sum(1 for r in have if r["verdict"] == v)
         for v in ("SILENT", "DETECTED", "FIRED", "no_bars")}
    n = len(have)
    active = sum(1 for r in have if r.get("engine_active_that_day"))
    s = {
        "label": label,
        "cards_with_a_usable_minute": n,
        "AT THE MINUTE": {
            "SILENT_no_signal_at_all": c["SILENT"],
            "DETECTED_saw_it_refused_to_trade": c["DETECTED"],
            "FIRED_took_the_trade": c["FIRED"],
            "no_bars_archived": c["no_bars"],
            "took_the_trade_pct": round(100.0 * c["FIRED"] / n, 1) if n else None,
        },
        "AT THE DAY": {
            "engine_produced_at_least_one_signal": active,
            "never_silent_pct": round(100.0 * active / n, 1) if n else None,
            "took_at_least_one_trade": sum(
                1 for r in have if r.get("took_any_trade_that_day")),
        },
        "TIMING, every card, nothing dropped": dist(
            [r.get("offset_nearest_any") for r in have]),
        "TIMING, only the cards it reached (the conditioned number)": dist(
            [r["offset_nearest_any"] for r in have
             if r["verdict"] in ("DETECTED", "FIRED")]),
        "bands": {str(b): {v: sum(1 for r in have
                                  if r.get("bands", {}).get(str(b)) == v)
                           for v in ("SILENT", "DETECTED", "FIRED")}
                  for b in BANDS},
    }
    return s


def main():
    res = {"what": "the engine measured at Austin's stated entry minute, not at "
                   "the day", "near_bars": NEAR,
           "mark_files_readonly": [MARKS_A, MARKS_B]}

    print("SAMPLE A -- the 30 homework cards, 2026-08-29")
    a = load_a()
    a_rows = measure(a, "A")
    res["sample_A_rows"] = a_rows
    res["sample_A_all30"] = summarise(a_rows, "all 30 homework cards")
    res["sample_A_yes_only"] = summarise(
        [r for r in a_rows if r["is_s"]], "the 21 he graded S")
    # the strictest reading: only minutes he meant as an entry
    entry_only = [r for r in a_rows
                  if r.get("time_intent") in ("entry", "entry_not_tradeable")]
    res["sample_A_entry_intent_only"] = summarise(
        entry_only, "only clock times he meant as an entry")

    print("\nSAMPLE B -- the 34 S days of the 100-card blind sweep, 2026-08-28")
    b = load_b()
    b_rows = measure([r for r in b if r["is_s"]], "B")
    res["sample_B_rows"] = b_rows
    res["sample_B_S_days"] = summarise(b_rows, "the S days of the blind sweep")

    res["unparseable"] = {
        r["card_id"]: r["unparseable_tokens"]
        for r in a_rows + b_rows if r.get("unparseable_tokens")}

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)

    print("\n" + "=" * 72)
    for key in ("sample_A_all30", "sample_A_yes_only",
                "sample_A_entry_intent_only", "sample_B_S_days"):
        s = res[key]
        print("\n%s  (n=%d)" % (s["label"], s["cards_with_a_usable_minute"]))
        m = s["AT THE MINUTE"]
        print("  at the MINUTE: silent %d | saw it, refused %d | traded %d  (%s%%)"
              % (m["SILENT_no_signal_at_all"],
                 m["DETECTED_saw_it_refused_to_trade"],
                 m["FIRED_took_the_trade"], m["took_the_trade_pct"]))
        d = s["AT THE DAY"]
        print("  at the DAY:    active on %d of %d (%s%%), traded on %d"
              % (d["engine_produced_at_least_one_signal"],
                 s["cards_with_a_usable_minute"], d["never_silent_pct"],
                 d["took_at_least_one_trade"]))
        t1 = s["TIMING, every card, nothing dropped"]
        t2 = s["TIMING, only the cards it reached (the conditioned number)"]
        if t1:
            print("  offset, ALL cards        : median %+g  mean %+g  range %+d..%+d"
                  % (t1["median"], t1["mean"], t1["min"], t1["max"]))
        if t2:
            print("  offset, only reached ones: median %+g  mean %+g  (n=%d)"
                  % (t2["median"], t2["mean"], t2["n"]))
        print("  bands: " + "  ".join(
            "+/-%s -> %dS/%dD/%dF" % (b, s["bands"][b]["SILENT"],
                                      s["bands"][b]["DETECTED"],
                                      s["bands"][b]["FIRED"])
            for b in map(str, BANDS)))
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
