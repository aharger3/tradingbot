"""g98 -- his entry minute against the engine's, on the same tape.

Austin, 2026-09-02: "I believe we have stats to show my eye knows better then
those stats u gave me."

He is right that g96 was unfair to him. g96 asked whether the days he graded S
were better days, using **the engine's own entry** on those days -- the entry he
says is three to six candles late ("b candle right but entry is 3 candles
earlier", "the entry shouldve been 6 candles earlier"). That measures the day,
not his trade. It cannot show what his eye is worth.

This measures his trade. 202 marks across research/marks/ carry an entry minute,
either in an `entry_minute` field or written into the prose. For each one that
lands on a symbol-day the engine also traded, both entries are run through the
SAME machinery -- same stop rule, same window, same R definition -- so the only
thing that differs is the minute.

THE STOP IS HIS, FOR BOTH ARMS, and that is the point. He stated it twice in the
stop-pick section: "this and last one have been stop below the candle entered
on". Using the engine's level-stop for the engine's arm and his candle-stop for
his would confound entry timing with stop placement and prove nothing. Both arms
get the entry candle's own extreme.

Reported per entry:
    R_alive       MFE in R strictly BEFORE adverse movement reaches 1R -- what
                  the entry was actually worth while the trade was still alive
    stopped       whether 1R adverse came before 11:00

    python research/g98_his_minute_vs_engine.py
    python research/g98_his_minute_vs_engine.py --endorsed-only

Applies nothing. 1R = |entry - stop|; rows whose risk is under a cent are dropped
(CLAUDE.md's size gate -- a one-cent denominator is arithmetic, not money).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import re
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import signal_runner as sr                        # noqa: E402
from research import g80_ordertype_grid as G      # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g98_his_minute_vs_engine.json")
OUT_MD = os.path.join(HERE, "g98_his_minute_vs_engine.md")
WIN_END = "11:00:00"
MINUTE = re.compile(r"\b((?:9|10|11):[0-5][0-9])\b")


def notestr(r):
    n = r.get("notes")
    if isinstance(n, dict):
        return " ".join(str(v) for v in n.values())
    return str(n or "")


def endorsed(r):
    """Did he actually say he would take it, as opposed to naming a minute
    while explaining why he would not?"""
    a = r.get("answers") or {}
    for k in ("s", "is_s", "take"):
        v = a.get(k)
        if v:
            return str(v[0]).lower() in ("s", "yes")
    return None


def harvest():
    """Every mark carrying (symbol, day, minute). Field first, prose second."""
    out = {}
    for f in sorted(glob.glob(os.path.join(HERE, "marks", "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            sym, day = r.get("symbol"), r.get("date") or r.get("day")
            if not sym or not day:
                cid = r.get("card_id") or ""
                if "_" in cid:
                    sym, day = cid.rsplit("_", 1)
            if not sym or not day or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(day)):
                continue
            m = r.get("entry_minute")
            if not m:
                hit = MINUTE.search(notestr(r))
                m = hit.group(1) if hit else None
            if not m:
                continue
            if len(m) == 4:
                m = "0" + m
            # Later files win: the standing export supersedes earlier partials.
            out[(sym, str(day), m)] = {"sym": sym, "day": str(day), "et": m,
                                       "endorsed": endorsed(r),
                                       "card": r.get("card_id"), "src": f}
    return list(out.values())


def bar_at(bars, hhmm):
    for i, b in enumerate(bars):
        if b.timestamp[:5] == hhmm:
            return i
    return None


def score(bars, i, long):
    """(mfe_while_alive, stopped, risk) for an entry at bars[i], his stop rule.

    BAR-ORDERED, and gated on `signal_runner.min_risk_floor` -- both corrections
    forced by g97, whose first two versions measured MFE and MAE as independent
    maxima over the whole window and divided by two-cent denominators. An
    unordered MFE credits a run that only happened after the stop would have
    taken us out; a sub-floor risk manufactures R out of nothing. A bar that
    reaches both target and stop is given to the stop.
    """
    e = bars[i]
    entry = e.close
    stop = e.low if long else e.high
    risk = abs(entry - stop)
    if risk < sr.min_risk_floor(entry):
        return None
    best = 0.0
    for b in bars[i + 1:]:
        if b.timestamp > WIN_END:
            break
        fav = ((b.high - entry) if long else (entry - b.low)) / risk
        adv = ((entry - b.low) if long else (b.high - entry)) / risk
        if adv >= 1.0:
            return best, True, risk
        best = max(best, fav)
    return best, False, risk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endorsed-only", action="store_true",
                    help="only minutes he said yes/S to")
    ap.add_argument("--trials", type=int, default=20000)
    a = ap.parse_args()

    marks = harvest()
    print("marks carrying (symbol, day, minute): %d" % len(marks))
    if a.endorsed_only:
        marks = [m for m in marks if m["endorsed"] is True]
        print("  endorsed only: %d" % len(marks))

    book = json.load(open(BOOK, encoding="utf-8"))["trades"]
    bysd = defaultdict(list)
    for r in book:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            bysd[(r["sym"], r["day"])].append(r)
    for v in bysd.values():
        v.sort(key=g86.ekey)

    pairs, skipped = [], defaultdict(int)
    for m in marks:
        eng = bysd.get((m["sym"], m["day"]))
        if not eng:
            skipped["engine never traded this symbol-day"] += 1
            continue
        bars, *_ = G.day_pack(m["sym"], m["day"])
        if not bars:
            skipped["no archived bars"] += 1
            continue
        hi = bar_at(bars, m["et"])
        e0 = eng[0]
        ei = e0.get("entry_i")
        if hi is None or ei is None or ei >= len(bars):
            skipped["minute not on the tape"] += 1
            continue
        # Direction is the engine's for BOTH arms: he rarely states one, and
        # giving his arm hindsight on direction would be the whole edge.
        long = e0["dir"] == "call"
        hs, es = score(bars, hi, long), score(bars, ei, long)
        if hs is None or es is None:
            skipped["risk below min_risk_floor"] += 1
            continue
        pairs.append({"sym": m["sym"], "day": m["day"], "his_et": m["et"],
                      "eng_et": e0["et"], "dir": e0["dir"],
                      "delta_min": hi - ei, "endorsed": m["endorsed"],
                      "his_R": hs[0], "his_stopped": hs[1], "his_risk": hs[2],
                      "eng_R": es[0], "eng_stopped": es[1], "eng_risk": es[2],
                      "eng_realised": e0["r"]})

    print("usable head-to-head pairs: %d" % len(pairs))
    for k, v in sorted(skipped.items(), key=lambda x: -x[1]):
        print("  skipped %-34s %d" % (k, v))
    if len(pairs) < 30:
        raise SystemExit("too few pairs to say anything")

    hR = [p["his_R"] for p in pairs]
    eR = [p["eng_R"] for p in pairs]
    obs = statistics.mean(hR) - statistics.mean(eR)
    # Paired permutation: each pair is the same tape, so the null is "it was a
    # coin flip which of the two entries got the better number on THIS tape".
    rng = random.Random(20260902)
    hits = 0
    diffs = [h - e for h, e in zip(hR, eR)]
    for _ in range(a.trials):
        if statistics.mean([d if rng.random() < 0.5 else -d for d in diffs]) >= obs:
            hits += 1
    p = (hits + 1) / (a.trials + 1)

    print("\n=== R AVAILABLE from each entry (MFE to 11:00 / that entry's risk) ===")
    print("  HIS minute    mean %+.3fR   median %+.3fR   risk $%.3f"
          % (statistics.mean(hR), statistics.median(hR),
             statistics.mean([q["his_risk"] for q in pairs])))
    print("  ENGINE minute mean %+.3fR   median %+.3fR   risk $%.3f"
          % (statistics.mean(eR), statistics.median(eR),
             statistics.mean([q["eng_risk"] for q in pairs])))
    print("  gap %+.3fR   paired permutation p = %.4f  %s"
          % (obs, p, "HIS EYE WINS" if p < 0.05 and obs > 0
             else ("engine wins" if p < 0.05 else "not separable")))

    his_better = sum(1 for q in pairs if q["his_R"] > q["eng_R"])
    print("\n  his entry offered more R on %d/%d tapes (%.1f%%)"
          % (his_better, len(pairs), 100 * his_better / len(pairs)))
    print("  survived to 11:00 without stopping -- his %.1f%%   engine %.1f%%"
          % (100 * sum(1 for q in pairs if not q["his_stopped"]) / len(pairs),
             100 * sum(1 for q in pairs if not q["eng_stopped"]) / len(pairs)))
    for t in (1.0, 2.0):
        print("  reached >=%.0fR while alive -- his %.1f%%   engine %.1f%%"
              % (t, 100 * sum(1 for q in pairs if q["his_R"] >= t) / len(pairs),
                 100 * sum(1 for q in pairs if q["eng_R"] >= t) / len(pairs)))
    d = [q["delta_min"] for q in pairs]
    print("  his minute vs engine's, in bars: median %+d, mean %+.1f "
          "(negative = he is earlier)" % (statistics.median(d), statistics.mean(d)))
    print("  he was earlier on %d/%d (%.1f%%)"
          % (sum(1 for x in d if x < 0), len(d),
             100 * sum(1 for x in d if x < 0) / len(d)))

    for lab, sel in (("endorsed (he said yes/S)", lambda q: q["endorsed"] is True),
                     ("named while refusing", lambda q: q["endorsed"] is False)):
        sub = [q for q in pairs if sel(q)]
        if len(sub) < 15:
            continue
        print("\n  %s (n=%d): his %+.3fR vs engine %+.3fR"
              % (lab, len(sub), statistics.mean([q["his_R"] for q in sub]),
                 statistics.mean([q["eng_R"] for q in sub])))

    out = {"pairs": len(pairs), "his_mean_R": round(statistics.mean(hR), 4),
           "eng_mean_R": round(statistics.mean(eR), 4), "gap": round(obs, 4),
           "p": round(p, 4), "his_better_pct": round(100 * his_better / len(pairs), 1),
           "median_delta_bars": statistics.median(d),
           "his_risk": round(statistics.mean([q["his_risk"] for q in pairs]), 4),
           "eng_risk": round(statistics.mean([q["eng_risk"] for q in pairs]), 4),
           "rows": pairs}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g98 -- his entry minute vs the engine's, same tape", "",
          "%d head-to-head pairs from %d marks carrying a minute. Both arms use "
          "HIS stop rule (the entry candle's own extreme), his direction taken "
          "from the engine so his arm gets no hindsight, MFE measured to 11:00, "
          "1R = |entry - stop|." % (len(pairs), len(marks)), "",
          "| entry | mean R available | median | mean risk |", "|---|---:|---:|---:|",
          "| **his minute** | %+.3fR | %+.3fR | $%.3f |"
          % (statistics.mean(hR), statistics.median(hR),
             statistics.mean([q["his_risk"] for q in pairs])),
          "| engine's minute | %+.3fR | %+.3fR | $%.3f |"
          % (statistics.mean(eR), statistics.median(eR),
             statistics.mean([q["eng_risk"] for q in pairs])), "",
          "Gap **%+.3fR**, paired permutation **p = %.4f**. His entry offered more "
          "R on **%.1f%%** of tapes. Median offset **%+d bars**."
          % (obs, p, 100 * his_better / len(pairs), statistics.median(d))]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
