"""g81_marks30_score.py -- score Austin's 30 fresh judgements against the real engine.

WHAT THIS IS
------------
On 2026-08-29 Austin graded 30 charts from the g71 homework deck
(`research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl`). The charts
carried the 09:30-11:00 session, his six levels, and nothing else -- no entry
line, no stop line, no grade, no annotation. Zero repeats against the 1,548
symbol-days he had already been served. He said yes on 21 and no on 9, and on
21 of them he wrote down the minute he would have entered.

That makes this the first held-out sample this project has that carries BOTH a
yes/no verdict AND an entry time. This script scores the engine against it.

THE ROUTER MUST BE THE REAL ONE
-------------------------------
`research/t4_engine_recall.CaptureRunner._route` used to be a hand-written copy
of the shipped decision logic that never called `super()`, so every gate the
engine grew after the copy was written was invisible to the only rig that scores
recall. It flattered the published number by 3 days out of 278, always upward.
It was fixed in the commit before this one. This script asserts the fix is in
place before it measures anything -- see `assert_real_router()`. If that assert
ever fails, every number below is worthless.

WHAT IT MEASURES, PER CARD
--------------------------
1. DETECTED -- did the engine produce any signal at all on that symbol-day
   inside 09:30-11:00, at which minutes (this includes signals the router then
   threw away).
2. FIRED -- did the shipped router accept one, at which minutes.
3. TRADED -- did it survive to a booked entry (`backtest_week.simulate_day`,
   `SimTrade.counted`: fired AND grade is not C, since C is alert-only in the
   live scanner), at which minute.
4. BOTH GRADE LADDERS, side by side and never mixed: Austin's S/A/C from
   `research/downgrade.py` (level proxy = the trade's stop, the same convention
   `backtest_2y.py` uses so the two stay comparable) and the legacy A+/A/B/C/X
   from `signal_runner.py::_grade_pa` as it comes off the fired signal.
5. TIMING -- where he wrote a minute, engine minus Austin in minutes, signed.

Levels (PDH/PDL/PMH/PML, HTF bias) are reconstructed by `t4_engine_recall`, the
same way the recall rig does it, and both replays are fed the identical inputs
so the fired/traded columns differ only by the fill simulation. `qqq_breaks` is
None in both, matching the recall rig (`backtest_2y` feeds real QQQ breaks; that
tag affects tagging, not the gate, and is noted as a caveat in the report).

Every mark file is opened READ-ONLY.

    python research/g81_marks30_score.py [--out research/g81_marks30_score.json]
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as t4            # noqa: E402
import downgrade as dg                   # noqa: E402
import backtest_week as bw               # noqa: E402

MARKS = os.path.join(HERE, "marks", "probe_g71_homework_s3_2026-08-29_complete.jsonl")
MANIFEST = os.path.join(HERE, "decks", "g71-homework-s3-manifest.jsonl")


# --------------------------------------------------------------------------
# guard: are we on the fixed router?
# --------------------------------------------------------------------------

def assert_real_router():
    """The whole point of this measurement is that it runs the SHIPPED decision
    logic. Read the source of the capture subclass's router and refuse to run
    unless it delegates to the base class."""
    src = inspect.getsource(t4.CaptureRunner._route)
    if "super()._route(" not in src:
        raise SystemExit(
            "ABORT: t4_engine_recall.CaptureRunner._route does not call super(). "
            "That is the hand-rolled copy that flattered recall. Refusing to "
            "publish a number measured on it.")
    return {"delegates_to_super": True,
            "base_router": "%s.%s" % (t4.SignalRunner.__module__, "SignalRunner._route")}


# --------------------------------------------------------------------------
# Austin's stated minutes -- hand-coded, because a regex cannot read intent
# --------------------------------------------------------------------------
# Every note that contains a clock time is listed. `mine` is a minute Austin
# claims as HIS OWN entry. `not_his` is a time he mentions that is NOT his entry
# -- three of them are him naming the minute the ENGINE picked ("9:47 is what
# you liked", "9:45 its close i see what your seeing"), and three point at a
# candle or a hypothetical rather than an entry. Mixing those into the timing
# distribution would be scoring the engine against itself.
STATED = {
    # --- yes-days, his own entry minute -----------------------------------
    "BABA_2024-09-05":  {"mine": "9:56"},
    "NFLX_2026-05-26":  {"mine": "9:47"},
    "NVDA_2026-05-11":  {"mine": "9:43"},
    "NFLX_2025-07-08":  {"mine": "9:38"},
    "COIN_2025-07-10":  {"mine": "9:41"},
    "TSLA_2025-09-03":  {"mine": "9:45"},
    "AMD_2024-10-02":   {"mine": "9:36"},
    "MSFT_2025-08-29":  {"mine": "9:38"},        # "9:38 is the entry"
    "GOOGL_2024-10-29": {"mine": "10:47"},
    "AAPL_2026-04-17":  {"mine": "9:42"},
    "SPY_2025-05-21":   {"mine": "9:45"},
    "INTC_2026-03-24":  {"mine": "9:38"},        # "entry at 9:38"
    "AVGO_2024-11-04":  {"mine": "9:47"},
    "IWM_2026-08-06":   {"mine": "9:55", "typo": "9:%5"},   # shift held on the 5
    "TSM_2026-07-07":   {"mine": "9:38"},
    "AMZN_2025-12-11":  {"mine": "9:40"},
    "ACHR_2026-06-16":  {"mine": "9:57"},        # "as candle forming"
    "SPY_2026-06-17":   {"mine": "9:48", "note": "his alternative; he also blessed the engine's"},
    "ACHR_2026-04-13":  {"mine": "10:09", "note": "yes, but 'would never trade'"},
    "META_2026-06-22":  {"mine": "9:59"},
    "QQQ_2024-08-26":   {"mine": "9:56", "second": "9:45"},
    # --- no-days ----------------------------------------------------------
    "AMD_2025-09-08":   {"mine": "10:37", "note": "the setup he saw, then downgraded"},
    "MSFT_2024-09-13":  {"not_his": "9:47", "why": "naming the engine's minute"},
    "QQQ_2025-12-22":   {"not_his": "9:45", "why": "naming the engine's minute"},
    "TSM_2025-11-26":   {"not_his": "9:35", "why": "a candle, not an entry"},
    "AVGO_2025-12-03":  {"not_his": "9:33", "why": "a hypothetical break"},
}


def fisher_exact(a, b, c, d):
    """Two-sided Fisher exact on the 2x2 [[a,b],[c,d]]. No scipy dependency:
    sum the probability of every table at least as extreme as the observed one."""
    import math
    n = a + b + c + d
    r1, r2, c1 = a + b, c + d, a + c

    def p(x):
        return (math.comb(r1, x) * math.comb(r2, c1 - x)) / math.comb(n, c1)

    obs = p(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs * (1 + 1e-9)))


def to_min(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def fmt_min(n):
    return "%d:%02d" % (n // 60, n % 60)


# --------------------------------------------------------------------------
# the replay
# --------------------------------------------------------------------------

def dg_bars(candles):
    return [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
            for c in candles]


def score_card(symbol, day):
    """Run both replays on one symbol-day with identical reconstructed inputs."""
    candles = t4.rth_candles(symbol, day)
    if not candles:
        return {"error": "no archived bars"}
    pdh, pdl, pdo, pdc = t4.prior_day_levels(symbol, day)
    pmh, pml = t4.premarket_extremes(symbol, day)
    bias = t4.htf_bias(symbol, day)

    # 1-3: detection / router-fired, through the REAL router
    entries, all_sigs, raw_sigs = t4.run_day(symbol, day)

    # 4: booked entries, through the shipped fill simulation
    trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias,
                             pmh, pml, pdo, pdc, qqq=None)
    booked = [t for t in trades if t.counted]
    alerts = [t for t in trades if t.is_alert]

    bars = dg_bars(candles)
    fired = []
    for e in entries:
        rec = dg.score(bars, e["bar"], e["stop"], e["direction"] == "call", bias)
        fired.append({
            "minute": e["timestamp"][:5],
            "setup": e["signal_type"],
            "dir": e["direction"],
            "legacy_grade": e["grade"],
            "austin_grade": (rec or {}).get("grade"),
            "tripped": (rec or {}).get("tripped", []),
            "confluence": (rec or {}).get("confluence"),
            "level": e.get("stop_level"),
        })

    booked_rows = []
    for t in booked:
        rec = dg.score(bars, t.entry_idx, t.stop, t.direction == "call", bias)
        booked_rows.append({
            "minute": t.entry_time[:5],
            "setup": t.signal_type,
            "dir": t.direction,
            "legacy_grade": t.grade,
            "austin_grade": (rec or {}).get("grade"),
            "outcome": t.outcome,
            "level": t.stop_level_name,
        })

    return {
        "detected_minutes": sorted({s["timestamp"][:5] for s in all_sigs}),
        "n_raw_signals": len(raw_sigs),
        "fired": fired,
        "fired_minutes": sorted({f["minute"] for f in fired}),
        "booked": booked_rows,
        "booked_minutes": sorted({b["minute"] for b in booked_rows}),
        "alert_only_minutes": sorted({t.entry_time[:5] for t in alerts}),
    }


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "g81_marks30_score.json"))
    args = ap.parse_args()

    router = assert_real_router()
    print("router check: %s" % router)

    marks = [json.loads(l) for l in open(MARKS, encoding="utf-8") if l.strip()]
    manifest = {json.loads(l)["card_id"]: json.loads(l)
                for l in open(MANIFEST, encoding="utf-8") if l.strip()}
    assert len(marks) == 30, len(marks)

    cards = []
    for m in marks:
        cid = m["card_id"]
        verdict = (m["answers"].get("is_s") or [None])[0]
        man = manifest.get(cid, {})
        res = score_card(m["symbol"], m["date"])
        stated = STATED.get(cid, {})
        row = {
            "card_id": cid,
            "symbol": m["symbol"], "day": m["date"],
            "bucket": m["bucket"],
            "verdict": verdict,
            "why_not": m["answers"].get("why_not", []),
            "note": " | ".join(v for v in m.get("notes", {}).values() if v),
            "claimed_setup": m.get("claimed_setup"),
            "claimed_level": m.get("claimed_level"),
            "deck_legacy_grade": man.get("legacy_grade"),
            "deck_traded": man.get("traded"),
            "deck_entry_minute": man.get("et"),
            "austin_minute": stated.get("mine"),
            "austin_minute_notes": {k: v for k, v in stated.items() if k != "mine"},
            **res,
        }
        # timing: engine minus Austin, in minutes
        if row.get("austin_minute") and row.get("fired_minutes"):
            a = to_min(row["austin_minute"])
            fm = [to_min(x) for x in row["fired_minutes"]]
            row["delta_first_fire"] = min(fm) - a
            row["delta_nearest_fire"] = min(fm, key=lambda x: abs(x - a)) - a
        if row.get("austin_minute") and row.get("booked_minutes"):
            a = to_min(row["austin_minute"])
            bm = [to_min(x) for x in row["booked_minutes"]]
            row["delta_first_booked"] = min(bm) - a
            row["delta_nearest_booked"] = min(bm, key=lambda x: abs(x - a)) - a
        # The third comparison, and the most direct one: every card IS one
        # engine signal, and `et` is the minute that signal happened. This is
        # the engine's claim "I believe this is an S, here" against his answer.
        if row.get("austin_minute") and row.get("deck_entry_minute"):
            row["delta_deck_card"] = to_min(row["deck_entry_minute"]) - to_min(row["austin_minute"])
        cards.append(row)
        print("  %-18s %-3s %-4s detect=%-2d fire=%-2d book=%-2d  %s"
              % (cid, m["bucket"], verdict, len(row["detected_minutes"]),
                 len(row["fired_minutes"]), len(row["booked_minutes"]),
                 ",".join(row["booked_minutes"]) or "-"))

    # ---------------------------------------------------------------- summary
    yes = [c for c in cards if c["verdict"] == "yes"]
    no = [c for c in cards if c["verdict"] == "no"]

    def rate(rows, key):
        k = sum(1 for r in rows if r.get(key))
        return {"k": k, "n": len(rows),
                "pct": round(k / len(rows) * 100, 1) if rows else 0.0}

    def block(rows):
        return {"detected": rate(rows, "detected_minutes"),
                "fired": rate(rows, "fired_minutes"),
                "traded": rate(rows, "booked_minutes")}

    summary = {
        "recall_on_yes": block(yes),
        "false_fire_on_no": block(no),
        "discrimination": {
            "note": "every card is already an engine-claimed S, so this asks only "
                    "whether the subset the router BOOKS tracks his yes/no",
            "booked_and_yes": sum(1 for c in yes if c["booked_minutes"]),
            "booked_and_no": sum(1 for c in no if c["booked_minutes"]),
            "silent_and_yes": sum(1 for c in yes if not c["booked_minutes"]),
            "silent_and_no": sum(1 for c in no if not c["booked_minutes"]),
            "fisher_exact_two_sided_p": None,   # filled below
        },
        "by_bucket": {},
    }
    d_ = summary["discrimination"]
    d_["fisher_exact_two_sided_p"] = round(
        fisher_exact(d_["booked_and_yes"], d_["booked_and_no"],
                     d_["silent_and_yes"], d_["silent_and_no"]), 4)
    for b in ("84", "OCR", "BR"):
        summary["by_bucket"][b] = {
            "yes": block([c for c in yes if c["bucket"] == b]),
            "no": block([c for c in no if c["bucket"] == b]),
        }

    # deck-silent days: the cards the engine would NOT have booked when the deck
    # was built (manifest `traded` flag off), and the legacy-X cards, which is
    # the number research/g71_homework.md quoted.
    silent = [c for c in cards if not c["deck_traded"]]
    legacy_x = [c for c in cards if c["deck_legacy_grade"] == "X"]
    summary["deck_silent"] = {
        "n_not_traded_in_deck": len(silent),
        "yes_on_those": sum(1 for c in silent if c["verdict"] == "yes"),
        "n_legacy_X_in_deck": len(legacy_x),
        "yes_on_legacy_X": sum(1 for c in legacy_x if c["verdict"] == "yes"),
        "still_silent_today": sum(1 for c in silent if not c["booked_minutes"]),
        "yes_and_still_silent_today": sum(
            1 for c in silent if c["verdict"] == "yes" and not c["booked_minutes"]),
    }

    # grade ladders, side by side, never mixed
    lad = {"yes": {"legacy": Counter(), "austin": Counter()},
           "no": {"legacy": Counter(), "austin": Counter()}}
    for c in cards:
        side = lad.get(c["verdict"])
        if side is None:
            continue
        for f in c["fired"]:
            side["legacy"][f["legacy_grade"]] += 1
            side["austin"][f["austin_grade"]] += 1
    summary["grade_ladders_on_fired_signals"] = {
        k: {"legacy_A+ABCX": dict(sorted(v["legacy"].items())),
            "austin_SAC": dict(sorted(v["austin"].items()))}
        for k, v in lad.items()}

    # ------------------------------------------------------------- timing
    def dist(vals):
        if not vals:
            return None
        s = sorted(vals)
        return {"n": len(s), "min": s[0], "max": s[-1],
                "median": statistics.median(s),
                "mean": round(statistics.mean(s), 2),
                "early_engine_before_austin": sum(1 for v in s if v < 0),
                "exact": sum(1 for v in s if v == 0),
                "late_engine_after_austin": sum(1 for v in s if v > 0),
                "within_1min": sum(1 for v in s if abs(v) <= 1),
                "within_2min": sum(1 for v in s if abs(v) <= 2),
                "within_5min": sum(1 for v in s if abs(v) <= 5),
                "values": s}

    stated_yes = [c for c in yes if c.get("austin_minute")]

    # The funnel AT HIS MINUTE. +/-2 minutes is the same tolerance the recall rig
    # joins on (t4_engine_recall.TOL). This separates "the engine never saw the
    # setup" from "the engine saw it and the router threw it away".
    def near(c, field, tol=2):
        a = to_min(c["austin_minute"])
        return any(abs(to_min(m) - a) <= tol for m in c[field])

    def funnel(rows, tol):
        return {"n": len(rows),
                "detected": sum(1 for c in rows if near(c, "detected_minutes", tol)),
                "fired": sum(1 for c in rows if near(c, "fired_minutes", tol)),
                "booked": sum(1 for c in rows if near(c, "booked_minutes", tol))}

    summary["at_his_minute"] = {"tol_%d" % t: funnel(stated_yes, t)
                                for t in (0, 1, 2, 3, 5)}
    summary["at_his_minute_by_bucket_tol2"] = {
        b: funnel([c for c in stated_yes if c["bucket"] == b], 2)
        for b in ("84", "OCR", "BR")}

    summary["timing"] = {
        "n_yes_with_stated_minute": len(stated_yes),
        "n_yes_stated_and_engine_fired": sum(1 for c in stated_yes if c.get("fired_minutes")),
        "n_yes_stated_and_engine_booked": sum(1 for c in stated_yes if c.get("booked_minutes")),
        "first_fire_minus_austin": dist([c["delta_first_fire"] for c in stated_yes
                                         if "delta_first_fire" in c]),
        "nearest_fire_minus_austin": dist([c["delta_nearest_fire"] for c in stated_yes
                                           if "delta_nearest_fire" in c]),
        "first_booked_minus_austin": dist([c["delta_first_booked"] for c in stated_yes
                                           if "delta_first_booked" in c]),
        "nearest_booked_minus_austin": dist([c["delta_nearest_booked"] for c in stated_yes
                                             if "delta_nearest_booked" in c]),
        "deck_card_minus_austin": dist([c["delta_deck_card"] for c in stated_yes
                                        if "delta_deck_card" in c]),
        "deck_card_minus_austin_all30": dist([c["delta_deck_card"] for c in cards
                                              if "delta_deck_card" in c]),
        "per_card": [{"card_id": c["card_id"], "bucket": c["bucket"],
                      "austin": c["austin_minute"],
                      "first_fire": (c["fired_minutes"] or [None])[0],
                      "delta_first_fire": c.get("delta_first_fire"),
                      "delta_nearest_fire": c.get("delta_nearest_fire"),
                      "first_booked": (c["booked_minutes"] or [None])[0],
                      "delta_first_booked": c.get("delta_first_booked"),
                      "deck_card_minute": c["deck_entry_minute"],
                      "delta_deck_card": c.get("delta_deck_card")}
                     for c in stated_yes],
    }

    out = {"router_check": router, "n_cards": len(cards),
           "verdicts": dict(Counter(c["verdict"] for c in cards)),
           "summary": summary, "cards": cards}
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=2)
    print(json.dumps(summary, indent=2))
    print("wrote " + args.out)


if __name__ == "__main__":
    main()
